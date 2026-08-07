# 21 - 大规模集群管理

> 本章目标：回答你的第四个关键问题——**如何管理大规模集群**。
> 从"一个集群跑几十个服务"到"几十个集群跑几千个服务"，会遇到哪些质变，怎么应对。
> 预计用时：3 小时（本章以原理和决策为主，实验较少）。

---

## 1. 规模的三个维度

"大规模"至少有三个正交的维度，它们的瓶颈完全不同：

| 维度 | 小 | 中 | 大 |
|---|---|---|---|
| **集群内节点数** | < 50 | 50~500 | 500~5000 |
| **集群数量** | 1~3 | 5~30 | 50~1000+ |
| **服务/团队数** | < 20 | 20~200 | 200+ |

大多数团队面对的是"集群数量"和"服务数量"的增长，而不是单集群节点数。**但两者的解法完全不同**，先搞清楚你在解决哪个问题。

---

## 2. 单集群的规模上限与瓶颈

### 2.1 官方声明的上限

Kubernetes 官方的规模上限（同时满足）：

| 指标 | 上限 |
|---|---|
| 节点数 | **5000** |
| Pod 总数 | **150,000** |
| 容器总数 | 300,000 |
| 每节点 Pod 数 | **110**（默认，可调到 250） |

⚠️ 这是"在标准测试负载下不出问题"的上限，**不是推荐值**。实践中：
- **托管集群**（EKS/GKE/AKS）：500~1000 节点是舒适区
- **自建集群**：200~500 节点更稳妥
- 超过就该考虑拆集群了

### 2.2 真正的瓶颈在哪

**不是节点数，而是"对象数量 × 变更频率"。**

一个 200 节点但有 5 万个 Service 和大量 CronJob 的集群，可能比 1000 节点但对象很少的集群压力大得多。

| 组件 | 瓶颈表现 | 关键指标 | 应对 |
|---|---|---|---|
| **etcd** | 写入延迟飙升、defrag 卡顿、达到容量上限后**整个集群变只读** | `etcd_disk_wal_fsync_duration_seconds` P99 < 10ms<br>`etcd_server_quota_backend_bytes` | NVMe 磁盘、独立部署、`--quota-backend-bytes` 调到 8G、把 Event 存到独立 etcd、压缩+defrag 定期跑 |
| **kube-apiserver** | list 请求慢、watch 缓存内存暴涨、429 限流 | `apiserver_request_duration_seconds`<br>`apiserver_flowcontrol_rejected_requests_total` | 多副本 + LB、开启 APF（API Priority and Fairness）、禁止全量 list（用分页和 watch）、加内存 |
| **kube-controller-manager** | 调谐延迟大 | 队列深度、`workqueue_depth` | 调 `--concurrent-*-syncs`、`--kube-api-qps/burst` |
| **kube-scheduler** | Pod 长时间 Pending | `scheduler_pending_pods`<br>`scheduler_scheduling_attempt_duration_seconds` | 调 `percentageOfNodesToScore`、减少昂贵的 Pod 反亲和 |
| **kube-proxy (iptables)** | Service 变更后规则同步要几十秒 | `kubeproxy_sync_proxy_rules_duration_seconds` | 换 IPVS / nftables / Cilium eBPF |
| **CoreDNS** | 解析超时、间歇性失败 | `coredns_dns_request_duration_seconds`<br>`coredns_forward_healthcheck_failures_total` | 扩副本、NodeLocalDNSCache、调 `ndots`（第 10 章） |
| **CNI / IP 池** | Pod 卡在 ContainerCreating，`failed to allocate IP` | 已分配 IP 数 / CIDR 容量 | 提前规划 CIDR（**改不了！**）、用前缀委派模式 |
| **镜像拉取** | 大量 Pod 同时启动时拉镜像打满带宽 | 节点网络 | 镜像仓库就近部署 + P2P 分发（Dragonfly/Kraken）、镜像瘦身 |
| **节点上的 kubelet** | PLEG 超时、节点 NotReady | `kubelet_pleg_relist_duration_seconds` | 减少单节点 Pod 数、用 evented PLEG |

### 2.3 大集群的关键调优

```yaml
# etcd
--quota-backend-bytes=8589934592          # 8GB（默认 2GB 太小）
--auto-compaction-retention=1h            # 自动压缩历史版本
--max-request-bytes=10485760
# 定期 defrag（碎片整理会短暂阻塞，逐个节点做）

# kube-apiserver
--max-requests-inflight=3000              # 默认 400
--max-mutating-requests-inflight=1000     # 默认 200
--watch-cache-sizes=pods#10000,nodes#1000
--etcd-servers-overrides=/events#https://event-etcd:2379   # ⭐ Event 单独存
--event-ttl=30m                           # 默认 1h，大集群降低
--default-watch-cache-size=1000

# kube-controller-manager
--kube-api-qps=200 --kube-api-burst=400
--concurrent-deployment-syncs=20
--concurrent-endpoint-syncs=20
--node-monitor-grace-period=40s

# kube-scheduler
--kube-api-qps=200 --kube-api-burst=400
# percentageOfNodesToScore: 大集群设 10~30，避免每次给 5000 个节点打分

# kubelet
--max-pods=110                            # 视节点规格
--image-gc-high-threshold=80
--serialize-image-pulls=false             # 并行拉镜像
--kube-api-qps=20 --kube-api-burst=40
```

### 2.4 应用层的"规模杀手"

大集群出问题，**80% 是因为某个应用写得不好**：

| 反模式 | 后果 |
|---|---|
| 应用直接 `list` 全部 Pod，且高频轮询 | apiserver CPU 打满。**改用 informer**（第 6 章） |
| 自己写的 Operator 没有限速、没有缓存 | 同上 |
| 大量 CronJob 每分钟跑 + 不设 `ttlSecondsAfterFinished` | 对象数暴涨、etcd 撑爆 |
| 频繁更新 status 的 CRD | etcd 写入压力 |
| ConfigMap/Secret 挂载在几千个 Pod 上且频繁变更 | kubelet 和 apiserver 压力 → 用 `immutable: true` |
| 巨大的 Service（几千个后端）+ 用老的 Endpoints | 已被 EndpointSlice 缓解，但仍要注意 |
| 每个 Pod 都 `automountServiceAccountToken` | token 轮转带来的 apiserver 请求 |

**治理手段**：
- 用 APF（API Priority and Fairness）给不同客户端分优先级和配额
- 监控 `apiserver_request_total` 按 `client` 分组，找出高频调用者
- 代码 review 时检查是否用了 informer

```promql
# 找出谁在打爆 apiserver
topk(10, sum(rate(apiserver_request_total[5m])) by (client, resource, verb))
```

---

## 3. 一个大集群 vs 多个小集群

这是最重要的架构决策。

| 维度 | 单个大集群 | 多个小集群 |
|---|---|---|
| **资源利用率** | ✅ 高（统一调度，碎片少） | ❌ 每个集群都要留 buffer |
| **运维成本** | ✅ 一套东西要维护 | ❌ N 套（但可以自动化） |
| **控制面成本** | ✅ 一份 | ❌ N 份（托管集群每个每月几十~上百美元） |
| **爆炸半径** | ❌ **一挂全挂** | ✅ 隔离 |
| **升级风险** | ❌ 一次影响所有 | ✅ 可以逐个灰度 |
| **隔离性** | ❌ 软隔离（namespace） | ✅ 硬隔离 |
| **合规/数据主权** | ❌ 难 | ✅ 按地域/合规域分 |
| **跨服务调用** | ✅ 直接 Service | ❌ 需要跨集群方案 |
| **规模上限** | ❌ 有天花板 | ✅ 水平扩展 |

### 3.1 常见的拆分维度

```
按环境：      dev / staging / prod            ← ⭐ 最基本，必须拆
按地域：      cn-north / us-east / eu-west     ← 延迟和合规
按业务线：    payments / logistics / search    ← 隔离和成本归属
按工作负载：  online / batch / ml-gpu          ← 资源特性差异大
按合规域：    pci-dss / general                ← 审计边界
```

### 3.2 实践建议

**一条经验法则**：
> **生产和非生产必须分开。**
> 生产集群的数量取决于你的爆炸半径容忍度和地域需求，而不是节点数。
> 单集群超过 500 节点或超过 100 个团队在用，就该考虑拆。

**典型的中型公司拓扑**（50~200 工程师）：

```
├── mgmt-cluster        （管理集群：Argo CD、CI、监控聚合、Cluster API）
├── dev-cluster         （所有开发环境，namespace 隔离）
├── staging-cluster
├── prod-cn-cluster     （每地域一个）
└── prod-us-cluster
```

---

## 4. 多集群管理

### 4.1 集群生命周期：Cluster API

**Cluster API (CAPI)** 把"集群"本身变成 K8s 资源——用声明式的方式创建和管理集群。

```yaml
apiVersion: cluster.x-k8s.io/v1beta1
kind: Cluster
metadata:
  name: prod-us-east
spec:
  clusterNetwork:
    pods: {cidrBlocks: ["10.244.0.0/16"]}
    services: {cidrBlocks: ["10.96.0.0/12"]}
  infrastructureRef:
    kind: AWSCluster
    name: prod-us-east
  controlPlaneRef:
    kind: KubeadmControlPlane
    name: prod-us-east-cp
---
apiVersion: controlplane.cluster.x-k8s.io/v1beta1
kind: KubeadmControlPlane
metadata: {name: prod-us-east-cp}
spec:
  replicas: 3
  version: v1.36.2          # ⭐ 改这一行就能滚动升级控制面
  machineTemplate:
    infrastructureRef: {kind: AWSMachineTemplate, name: cp-template}
```

**价值**：集群创建、扩缩容、版本升级全部变成 Git 里的声明 → **可以用 GitOps 管理集群本身**。

```
mgmt-cluster (装了 Cluster API + Argo CD)
     │
     ├──► 创建/管理 prod-cn-cluster
     ├──► 创建/管理 prod-us-cluster
     └──► 创建/管理 staging-cluster
```

云厂商也有等价方案：EKS Blueprints、GKE Fleet、AKS Fleet Manager，或者直接用 Terraform/Pulumi。

### 4.2 应用分发：Argo CD ApplicationSet

第 18 章讲过。核心模式：

```yaml
generators:
  - clusters:
      selector:
        matchLabels: {environment: production}
template:
  spec:
    destination: {server: '{{.server}}'}
```

配合 **Progressive Sync**（Argo CD 3.3+）分批更新集群，控制爆炸半径。

### 4.3 跨集群服务发现

| 方案 | 说明 |
|---|---|
| **全局负载均衡（GSLB）+ DNS** ⭐ | 最简单：每个集群有自己的入口，用 DNS 或全局 LB 分流。**大多数场景够用** |
| **多集群 Service (MCS API)** | K8s 官方的 `ServiceExport`/`ServiceImport`，实现还不成熟 |
| **Service Mesh 多集群** | Istio/Linkerd 的多集群模式：跨集群 mTLS + 服务发现。功能强，运维复杂 |
| **Cilium Cluster Mesh** | eBPF 层打通多集群 Pod 网络，性能好 |
| **自己的服务注册中心** | 已有 Consul/Nacos 的话继续用 |

**建议**：先用最简单的（每个集群自包含 + GSLB），确实有跨集群调用需求再上 mesh。**跨集群调用本身就是个架构信号**——通常意味着服务边界划错了。

### 4.4 统一策略与合规

用 GitOps 把策略推到所有集群：

```
policy-repo/
├── base/
│   ├── kyverno-policies/         # 第 14 章的策略
│   ├── network-policies/
│   ├── resource-quotas/
│   └── priority-classes/
└── overlays/
    ├── prod/                     # 生产更严格
    └── dev/
```

用 ApplicationSet 的 cluster 生成器铺到所有集群。**新集群加进来，策略自动生效。**

---

## 5. 节点管理

### 5.1 节点池设计

不要用单一规格的节点。按工作负载特性分池：

| 节点池 | 规格 | 污点/标签 | 用途 |
|---|---|---|---|
| `system` | 中等，按需 | `CriticalAddonsOnly=true:NoSchedule` | 系统组件、Ingress、监控 |
| `general` | 中等，按需 | `node-pool=general` | 在线服务 |
| `memory` | 内存优化 | `node-pool=memory` | 缓存、内存密集型 |
| `batch-spot` | 大规格，**Spot/抢占式** | `node-pool=batch:NoSchedule` | 批处理、CI（可容忍中断） |
| `gpu` | GPU 机型 | `nvidia.com/gpu:NoSchedule` | 训练/推理 |

**Spot/抢占式实例是成本优化的最大杠杆**（便宜 60~90%），但要求：
- 工作负载可中断（有 PDB、能优雅退出、有重试）
- 部署 **Node Termination Handler**：收到中断通知（AWS 提前 2 分钟）后自动 cordon + drain
- 混合部署：关键服务用按需，弹性部分用 Spot

```yaml
# 混合调度：优先 Spot，不够时用按需
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
            - {key: karpenter.sh/capacity-type, operator: In, values: [spot]}
```

### 5.2 节点自动伸缩

第 12 章讲过 Cluster Autoscaler 和 Karpenter。大规模下的要点：

- **Karpenter 的整合（consolidation）能力**在大规模下能省 20~40% 成本：它会主动把分散的 Pod 挪到更少的节点上，然后回收空节点
- 给关键工作负载设 `do-not-disrupt` 注解防止被整合打断
- 配置 `expireAfter` 强制节点定期轮转（自动获得最新的安全补丁）

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata: {name: general}
spec:
  template:
    spec:
      requirements:
        - {key: karpenter.sh/capacity-type, operator: In, values: [spot, on-demand]}
        - {key: kubernetes.io/arch, operator: In, values: [arm64, amd64]}
        - {key: karpenter.k8s.aws/instance-category, operator: In, values: [c, m, r]}
      nodeClassRef: {name: default}
      expireAfter: 720h                # ⭐ 30 天强制轮转
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 1m
    budgets:
      - nodes: "10%"                   # ⭐ 一次最多打扰 10% 的节点
      - nodes: "0"                     # 业务高峰期不打扰
        schedule: "0 9 * * mon-fri"
        duration: 10h
  limits:
    cpu: 2000
```

### 5.3 版本升级（Day-2 最重要的操作）

**K8s 每年 3 个小版本，每个支持约 1 年。你必须每年至少升 2~3 次。** 落后超过 2 个版本会很痛苦（要连续升，不能跳版本）。

**标准流程**：

```
① 阅读目标版本的 Release Notes 和 Deprecation 列表
   kubectl 插件：kubent（kube-no-trouble）扫描废弃 API
   kubectl deprecations（1.31+）

② 在 dev 集群升级，跑全量测试

③ staging 集群升级，观察 1 周

④ 生产集群逐个升级，每个之间间隔观察

顺序（重要）：
  a. 先升控制面（apiserver → controller-manager → scheduler）
  b. 再升节点（kubelet 版本不能高于 apiserver，最多低 3 个小版本）
  c. 最后升 CRD/Operator/插件（CNI、CSI、ingress、监控）
```

**节点升级的两种方式**：

| 方式 | 说明 |
|---|---|
| **原地升级** | 在节点上升级 kubelet 并重启。快，但节点上的历史状态会累积 |
| **替换升级（推荐）** ⭐ | 创建新版本的节点 → cordon+drain 旧节点 → 删除旧节点。符合不可变基础设施，回滚容易 |

```bash
# 替换升级的手工流程（Karpenter/托管节点组会自动做）
kubectl cordon <old-node>
kubectl drain <old-node> --ignore-daemonsets --delete-emptydir-data --timeout=600s
# 等 Pod 全部迁移完成、服务指标正常
kubectl delete node <old-node>
# 云上删除对应的实例
```

**升级前的检查清单**：

- [ ] 用 `kubent` 扫描废弃 API，全部修完
- [ ] 所有关键服务有 PDB（否则 drain 会中断服务）
- [ ] etcd 有可恢复的备份（**升级前必做**）
- [ ] 关键 Operator/CRD 的版本兼容性已确认
- [ ] 有回滚预案（控制面回滚很难，所以要在低环境充分验证）
- [ ] 升级窗口避开业务高峰和发布冻结期
- [ ] 监控和告警正常工作（升级时最需要它们）

---

## 6. 容量规划与成本

### 6.1 核心矛盾：requests vs 实际用量

```bash
# 集群里 requests 之和 / allocatable
kubectl get nodes -o json | jq -r '.items[] | .metadata.name'
```

```promql
# ⭐ 最重要的两个成本指标
# ① 分配率：requests 占了多少
sum(kube_pod_container_resource_requests{resource="cpu"})
  / sum(kube_node_status_allocatable{resource="cpu"})

# ② 利用率：实际用了多少
sum(rate(container_cpu_usage_seconds_total{container!=""}[5m]))
  / sum(kube_node_status_allocatable{resource="cpu"})

# ③ 浪费率 = ① − ②
```

**典型的糟糕状况**：分配率 85%（看起来集群满了，加不了新服务），利用率 12%（实际 CPU 几乎空着）。**中间 73% 全是浪费**——因为所有人的 requests 都拍脑袋填了个大值。

### 6.2 Right-sizing 流程

```
① 用 VPA 的 recommendation 模式（updateMode: "Off"，第 12 章）收集建议
② 或用 Goldilocks / KRR / Kubecost 生成报告
③ 按服务出"当前 vs 建议"的对比
④ 推动团队改（或者平台团队直接改，走 PR）
⑤ 建立回归机制：CI 检查 requests 是否远超实际用量
```

```bash
# KRR：一条命令生成 right-sizing 报告
krr simple --clusterName prod
```

**经验值**（起点，不是终点）：
- CPU requests：设为 P50~P70 实际用量
- Memory requests：设为 P95~P99 实际用量（内存不可压缩，宁可高一点）
- CPU limit：在线服务不设或设很宽松；批处理设
- Memory limit：requests 的 1.5~2 倍

### 6.3 成本归属与 FinOps

**前提：标签规范。** 没有标签就无法归因。

```yaml
labels:
  app.kubernetes.io/name: orders
  team: payments             # ⭐ 成本归属
  cost-center: "CC-1234"
  environment: production
```

用 Kyverno 强制要求（第 14 章）。

**工具**：
- **OpenCost**（CNCF）/ **Kubecost**：按 namespace/label/团队算成本
- 云厂商的成本分摊标签

**大规模省钱的杠杆（按效果排序）**：

| 措施 | 典型节省 |
|---|---|
| Right-sizing（改 requests） | **20~50%** ⭐ |
| Spot / 抢占式实例 | 30~60%（可中断负载） |
| 节点整合（Karpenter consolidation） | 15~30% |
| 关掉闲置的非生产环境（夜间/周末） | 30%（非生产部分） |
| 用 ARM 实例（Graviton 等） | 20%（Go 服务天然支持多架构！第 3 章） |
| 预留实例 / Savings Plan | 30~50%（基线部分） |
| 减少跨可用区流量（拓扑感知路由，第 10 章） | 视流量而定 |
| 日志/指标的采样和保留策略 | 可观测性成本常占总成本 10~30% |

---

## 7. 平台工程：让 200 个开发者不用都学 K8s

规模上去后，最大的瓶颈不是技术，是**认知负荷**。你不可能让 200 个业务开发都精通本课程的内容。

### 7.1 分层抽象

```
┌──────────────────────────────────────────────┐
│ 业务开发者看到的：                              │
│   一个 service.yaml（10 行）+ git push         │
│   或者一个 Backstage 页面点几下                  │
└───────────────────┬──────────────────────────┘
                    │ 平台层展开
┌───────────────────▼──────────────────────────┐
│ 平台团队维护的：                                │
│   通用 Helm Chart / CRD + Operator            │
│   → Deployment + Service + HPA + PDB          │
│     + ServiceMonitor + NetworkPolicy          │
│     + 探针 + 资源 + securityContext + 拓扑分布   │
│     + 告警规则 + Dashboard                      │
└──────────────────────────────────────────────┘
```

**开发者写的**：

```yaml
# service.yaml
apiVersion: platform.yourorg.io/v1
kind: Service
metadata:
  name: orders
spec:
  language: go
  port: 8080
  size: medium              # small/medium/large → 平台翻译成具体 resources
  replicas: {min: 3, max: 20}
  dependencies: [postgres, redis]
  public: true
  team: payments
```

**平台生成的**：上面那一大堆最佳实践，全部自动带上。

### 7.2 实现方式

| 方式 | 说明 |
|---|---|
| **通用 Helm Chart** ⭐ | 最简单：一个 chart，每个服务只写 values。**从这个开始** |
| **CRD + Operator** | 更强的抽象，能做复杂逻辑（你有 Go 背景，用 kubebuilder 写不难） |
| **Crossplane** | 用 K8s API 管理云资源（数据库、S3、队列），Composition 做抽象 |
| **Backstage / Port** | 开发者门户：服务目录、软件模板（scaffolding）、文档、TechDocs |
| **Score / Radius** | 工作负载规格标准 |

### 7.3 黄金路径（Golden Path）

平台工程的核心理念：**提供一条"铺好的路"，走这条路什么都是自动的；但不禁止走别的路（只是要自己负责）。**

一条黄金路径应该包含：

```
① 服务脚手架（cookiecutter / backstage template）
   → 生成：Go 项目骨架 + Dockerfile + Chart values + CI 配置 + 监控 Dashboard

② CI 模板（shared library / reusable workflow）
   → 测试、构建、扫描、签名、推仓库、更新配置仓

③ 配置仓自动 PR

④ 自动生成：告警规则、Dashboard、SLO、runbook 模板

⑤ 文档和 on-call 手册
```

**衡量平台好坏的指标**：新服务从"零"到"生产可用"要多久？黄金路径应该做到 **1 天以内**。

### 7.4 组织与责任边界

| 角色 | 负责 |
|---|---|
| **平台团队** | 集群、平台组件、黄金路径、策略、可观测性基础设施、成本治理 |
| **业务团队** | 自己服务的代码、配置、SLO、on-call |
| **共享** | 事故响应、容量规划 |

**"You build it, you run it"** 的前提是平台团队把运维门槛降到业务团队能承受的程度。否则要么平台团队变成瓶颈，要么业务团队被迫成为 K8s 专家。

---

## 8. 备份与灾难恢复

### 8.1 三层备份

| 层 | 内容 | 工具 | RPO 目标 |
|---|---|---|---|
| **① Git（配置）** | 所有 K8s 清单、Chart、策略 | Git 本身（多个远程 + 定期打包） | 0（Git 就是真相源） |
| **② etcd（集群状态）** | 集群里所有对象 | `etcdctl snapshot` / 托管集群自带 | 1 小时 |
| **③ 数据（PV）** | 数据库、文件 | Velero + CSI 快照 / 数据库自己的备份 | 视业务，15 分钟~1 小时 |

**⭐ 有了 GitOps，第 ② 层的重要性大幅下降**——因为集群可以从 Git 重建。真正不可再生的只有第 ③ 层的数据。

### 8.2 etcd 备份与恢复

```bash
# 备份
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-$(date +%F-%H%M).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

etcdctl snapshot status /backup/etcd-xxx.db --write-out=table

# 恢复（⚠️ 需要停掉所有 apiserver，在所有 etcd 节点上做）
etcdctl snapshot restore /backup/etcd-xxx.db \
  --data-dir=/var/lib/etcd-restored \
  --name=<node-name> \
  --initial-cluster=<...> \
  --initial-advertise-peer-urls=<...>
```

**备份必须**：加密、异地存储、**定期演练恢复**（没演练过的备份等于没有备份）。

### 8.3 Velero

```bash
velero install --provider aws --bucket k8s-backups --secret-file ./creds \
  --use-node-agent --default-volumes-to-fs-backup

velero schedule create daily-prod \
  --schedule="0 2 * * *" \
  --include-namespaces prod,prod-data \
  --ttl 720h

velero backup describe daily-prod-20260729020000
velero restore create --from-backup daily-prod-20260729020000
```

### 8.4 灾难恢复演练

**至少每季度演练一次**：

| 场景 | 演练内容 | 目标 |
|---|---|---|
| 集群完全丢失 | 新建集群 → 装 Argo CD → apply root-app → 恢复数据 | RTO < 2 小时 |
| etcd 损坏 | 从快照恢复 | RTO < 1 小时 |
| 单个可用区故障 | 关掉一个 zone 的所有节点 | 服务不中断（依赖拓扑分布 + 多副本） |
| 数据误删 | 从备份恢复某个 PVC | RPO 符合承诺 |
| 镜像仓库不可用 | 节点上有缓存吗？能降级吗？ | — |

**演练要写成 runbook，并且让不熟悉的人来执行**——这样才能发现文档的缺失。

---

## 9. 大规模可观测性

规模上去后，可观测性系统本身会成为最大的成本和最大的故障源。

| 问题 | 应对 |
|---|---|
| **单个 Prometheus 存不下** | 分片（按 namespace/团队）+ **Thanos** 或 **Mimir** 做全局查询和长期存储 |
| **指标基数爆炸** | 用 `metric_relabel_configs` drop 掉高基数指标；监控 `prometheus_tsdb_head_series` |
| **日志成本失控** | 采样、分级保留（错误日志留 30 天，info 留 3 天）、Loki 的标签模型 |
| **告警疲劳** | 基于 SLO 的告警（第 23 章）、告警分组和抑制、定期审查告警有效性 |
| **Dashboard 太多没人看** | 每个服务一个标准 Dashboard（平台自动生成），而不是每个人手工建 |
| **跨集群查询** | Thanos Query / Mimir 做全局视图；或者用云厂商托管方案 |

```promql
# 找出基数最高的指标（Prometheus 自身的指标）
topk(20, count by (__name__)({__name__=~".+"}))
```

---

## 10. 大规模管理检查清单

### 集群层
- [ ] 生产/非生产集群分离
- [ ] 有明确的拆分维度和上限阈值（"超过 X 就拆"）
- [ ] 集群创建/升级是声明式的（Cluster API / IaC），不是手工
- [ ] CIDR 规划留了足够冗余（**这个改不了**）
- [ ] etcd 独立部署、NVMe 磁盘、有监控、有备份、备份演练过
- [ ] apiserver 多副本 + APF 配置
- [ ] 大集群用 IPVS/nftables/eBPF 而不是 iptables
- [ ] NodeLocalDNSCache 已部署
- [ ] 有集群版本升级的固定节奏和流程

### 节点层
- [ ] 按工作负载分节点池
- [ ] 关键服务不和批处理混跑
- [ ] 用了 Spot（可中断负载）+ 中断处理
- [ ] 节点定期轮转（拿最新补丁）
- [ ] 节点数自动伸缩

### 治理层
- [ ] 所有集群的策略由 GitOps 统一分发
- [ ] 强制标签规范（成本归属 + 责任人）
- [ ] 所有 namespace 有 ResourceQuota + LimitRange
- [ ] PSA restricted + Kyverno 策略
- [ ] 定期审查 RBAC 权限

### 成本层
- [ ] 有分配率/利用率/浪费率的监控看板
- [ ] 定期 right-sizing（至少季度）
- [ ] 成本能归因到团队
- [ ] 非生产环境有自动关停策略

### 平台层
- [ ] 有黄金路径（新服务 1 天内上生产）
- [ ] 通用 Chart / Operator 承载最佳实践
- [ ] 平台变更本身也走 GitOps 和灰度
- [ ] 有开发者文档和自助能力

### 韧性层
- [ ] 三层备份齐全且演练过
- [ ] 关键服务跨可用区部署
- [ ] 有 DR 预案和 RTO/RPO 承诺
- [ ] 定期做故障演练

---

## 11. 动手实验（有限，主要是观察）

### 实验 1：测量你的集群

```bash
# 分配率
kubectl get nodes -o json | jq -r '
  .items[] | "\(.metadata.name)\tCPU: \(.status.allocatable.cpu)\tMem: \(.status.allocatable.memory)"'

kubectl describe nodes | grep -A5 "Allocated resources" | head -40

# 对象数量统计
for r in pods services configmaps secrets endpoints events deployments; do
  echo -n "$r: "; kubectl get $r -A --no-headers 2>/dev/null | wc -l
done

# etcd 数据库大小（kind）
docker exec learn-control-plane sh -c \
  'ETCDCTL_API=3 etcdctl --cacert=/etc/kubernetes/pki/etcd/ca.crt \
   --cert=/etc/kubernetes/pki/etcd/server.crt --key=/etc/kubernetes/pki/etcd/server.key \
   endpoint status --write-out=table'
```

### 实验 2：观察 apiserver 压力

```bash
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 &
```

```promql
sum(rate(apiserver_request_total[5m])) by (verb, resource)
topk(10, sum(rate(apiserver_request_total[5m])) by (client))
histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket[5m])) by (le, verb))
etcd_db_total_size_in_bytes
```

### 实验 3：制造一次"坏客户端"

```bash
# 一个疯狂 list 的客户端（模拟写得不好的 Operator）
kubectl run bad-client --image=bitnami/kubectl:latest --restart=Never -- \
  sh -c 'while true; do kubectl get pods -A > /dev/null; done'
# 给它权限
kubectl create clusterrolebinding bad-client --clusterrole=view --serviceaccount=default:default

# 观察 apiserver 指标变化
# sum(rate(apiserver_request_total{verb="LIST"}[1m]))

kubectl delete pod bad-client
kubectl delete clusterrolebinding bad-client
```

### 实验 4：计算浪费率

```promql
# 分配率
sum(kube_pod_container_resource_requests{resource="cpu"}) / sum(kube_node_status_allocatable{resource="cpu"})
# 利用率
sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) / sum(kube_node_status_allocatable{resource="cpu"})
```

两者的差就是你的优化空间。

---

## 12. 本章检查清单

- [ ] "大规模"的三个维度是什么？它们的解法有什么不同？
- [ ] 单集群的官方上限是多少？实践中的推荐值？
- [ ] 真正的瓶颈是节点数还是别的？说出至少 5 个瓶颈组件和它们的关键指标
- [ ] 哪些应用层反模式会拖垮大集群？
- [ ] 单大集群 vs 多小集群的 8 个权衡维度？
- [ ] 什么时候该拆集群？拆分维度有哪些？
- [ ] Cluster API 解决什么问题？
- [ ] 跨集群服务发现的方案有哪些？为什么建议先用最简单的？
- [ ] 节点池该怎么划分？Spot 实例的使用前提是什么？
- [ ] 集群版本升级的顺序和检查清单？
- [ ] 分配率、利用率、浪费率分别怎么算？典型的糟糕数值是多少？
- [ ] 省钱杠杆按效果排序，前三是什么？
- [ ] 平台工程要解决什么问题？黄金路径包含什么？
- [ ] 三层备份分别是什么？GitOps 如何降低了 etcd 备份的重要性？
- [ ] 灾难恢复演练应该演练哪些场景？

---

## 13. 延伸阅读

- [Kubernetes 规模上限](https://kubernetes.io/docs/setup/best-practices/cluster-large/)
- [Considerations for large clusters](https://kubernetes.io/docs/setup/best-practices/cluster-large/)
- [Cluster API](https://cluster-api.sigs.k8s.io/)
- [Karpenter](https://karpenter.sh/)
- [OpenCost](https://opencost.io/) / [KRR](https://github.com/robusta-dev/krr)
- [Team Topologies](https://teamtopologies.com/)（平台团队的组织设计）
- [Platform Engineering](https://platformengineering.org/)
- [Thanos](https://thanos.io/) / [Mimir](https://grafana.com/oss/mimir/)

---

下一章：[22 - 故障排查手册](./22-troubleshooting.md)
