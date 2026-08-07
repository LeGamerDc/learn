# 附录 B - 术语表与延伸阅读

---

## 1. 术语表（中英对照）

### 容器基础

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| Namespace (Linux) | 命名空间 | 内核隔离机制（PID/NET/MNT/UTS/IPC/USER/CGROUP/TIME） | 02 |
| cgroup | 控制组 | 内核资源限制与计量机制 | 02 |
| OverlayFS / UnionFS | 联合文件系统 | 镜像分层的实现 | 02 |
| CoW (Copy-on-Write) | 写时复制 | 修改只读层文件时先复制 | 02 |
| OCI | 开放容器倡议 | 镜像/运行时/分发的标准 | 02 |
| runc | — | OCI 低层运行时参考实现 | 02 |
| containerd | — | 高层容器运行时，CRI 事实标准 | 02 |
| CRI | 容器运行时接口 | kubelet 与运行时之间的 gRPC 接口 | 02 |
| dockershim | — | 已移除的 Docker 适配层 | 02 |
| Image manifest | 镜像清单 | 描述镜像的层和配置 | 03 |
| Digest | 摘要 | 内容哈希，不可变引用 | 03 |
| Multi-arch image | 多架构镜像 | 一个 tag 对应多个平台 | 03 |
| Distroless | — | 只含运行时依赖、无 shell 的基础镜像 | 03 |
| SBOM | 软件物料清单 | 镜像内所有组件的清单 | 03、14 |
| Registry | 镜像仓库 | 存储和分发镜像 | 03 |

### Kubernetes 核心

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| Control Plane | 控制平面 | apiserver + etcd + scheduler + controller-manager | 06 |
| Data Plane | 数据平面 | 节点上的 kubelet + kube-proxy + 运行时 | 06 |
| Declarative API | 声明式 API | 描述期望状态而非操作步骤 | 06 |
| Reconciliation Loop | 调谐循环 | 持续让实际状态向期望状态收敛 | 06 |
| Level-triggered | 水平触发 | 关注当前状态而非事件（vs 边沿触发） | 06 |
| Controller | 控制器 | 实现调谐循环的组件 | 06 |
| Operator | — | CRD + 控制器，把运维知识代码化 | 06、21 |
| CRD | 自定义资源定义 | 扩展 K8s API 的机制 | 06 |
| Informer | — | client-go 的本地缓存 + 事件分发机制 | 06 |
| List-Watch | — | 全量拉取 + 增量监听的协议 | 06 |
| resourceVersion | 资源版本 | 乐观锁版本号 | 06 |
| SSA (Server-Side Apply) | 服务端应用 | 按字段管理者精确合并 | 06、18 |
| Admission Controller | 准入控制器 | 请求写入 etcd 前的拦截与改写 | 06、14 |
| Finalizer | 终结器 | 阻止对象被删除，直到清理完成 | 06 |
| ownerReference | 属主引用 | 对象间的父子关系，用于级联删除 | 06 |
| Static Pod | 静态 Pod | kubelet 直接从文件启动，不经 apiserver | 06 |

### 工作负载

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| Pod | — | 最小调度单元，一组共享网络的容器 | 07 |
| pause container | — | 持有 Pod namespace 的占位容器 | 02、07 |
| Sidecar | 边车容器 | 与主容器同生命周期的辅助容器 | 07 |
| Init Container | 初始化容器 | 主容器启动前顺序执行 | 07 |
| Ephemeral Container | 临时容器 | 用于调试，`kubectl debug` 注入 | 07、13 |
| Liveness Probe | 存活探针 | 失败则重启容器 | 07 |
| Readiness Probe | 就绪探针 | 失败则摘除流量 | 07 |
| Startup Probe | 启动探针 | 保护慢启动应用 | 07 |
| requests / limits | 请求 / 限制 | 调度依据 / 运行时上限 | 07 |
| QoS Class | 服务质量等级 | Guaranteed / Burstable / BestEffort | 07 |
| OOMKilled | 内存超限被杀 | 退出码 137 | 07、22 |
| Throttling | 节流 | CPU 配额用尽被强制暂停 | 07、22 |
| In-place resize | 原地扩缩容 | 不重启容器改资源（1.35 GA） | 07 |
| ReplicaSet | 副本集 | 维持 N 个相同 Pod | 09 |
| Deployment | 部署 | 管理 ReplicaSet，提供滚动更新 | 09 |
| StatefulSet | 有状态副本集 | 稳定身份 + 稳定存储 + 有序操作 | 09 |
| DaemonSet | 守护进程集 | 每节点一个 Pod | 09 |
| Job / CronJob | 任务 / 定时任务 | 一次性 / 周期性任务 | 09 |
| Rolling Update | 滚动更新 | 逐步替换旧副本 | 09 |
| maxSurge / maxUnavailable | 最大超出 / 最大不可用 | 滚动更新的两个关键参数 | 09 |
| PDB | Pod 中断预算 | 保证自愿中断期间的最小可用数 | 09 |
| Voluntary Disruption | 自愿中断 | drain、升级、缩容（PDB 生效） | 09 |

### 配置与存储

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| ConfigMap | 配置字典 | 非敏感配置 | 08 |
| Secret | 密钥 | 敏感配置（base64，非加密） | 08 |
| Downward API | 向下 API | 让容器获取自身元数据 | 08 |
| Projected Volume | 投影卷 | 多来源合并挂载 | 08 |
| Volume | 卷 | Pod 级的存储抽象 | 11 |
| emptyDir | — | 与 Pod 同生命周期的临时卷 | 11 |
| PV / PVC | 持久卷 / 持久卷声明 | 存储供给 / 存储申请 | 11 |
| StorageClass | 存储类 | 动态供给的模板 | 11 |
| CSI | 容器存储接口 | 存储插件标准 | 11 |
| Access Mode | 访问模式 | RWO / ROX / RWX / RWOP | 11 |
| Reclaim Policy | 回收策略 | Delete / Retain | 11 |
| fsGroup | 文件系统属组 | 修正挂载卷的属组 | 11 |
| VolumeSnapshot | 卷快照 | CSI 快照 | 11 |

### 网络

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| CNI | 容器网络接口 | 网络插件标准 | 10 |
| Pod CIDR / Service CIDR | — | Pod / Service 的 IP 段 | 10 |
| Service | 服务 | 稳定虚拟 IP + 负载均衡 | 10 |
| ClusterIP | 集群 IP | 内部虚拟 IP（不属于任何网卡） | 10 |
| NodePort | 节点端口 | 每节点开放一个端口 | 10 |
| LoadBalancer | 负载均衡器 | 云厂商的外部 LB | 10 |
| Headless Service | 无头服务 | `clusterIP: None`，DNS 直返 Pod IP | 10 |
| EndpointSlice | 端点切片 | Service 的后端列表（分片存储） | 10 |
| kube-proxy | — | 把 Service 变成转发规则 | 10 |
| CoreDNS | — | 集群 DNS 服务器 | 10 |
| ndots | — | DNS search 域展开阈值（默认 5） | 10 |
| Ingress | 入口 | L7 入口（**功能冻结**） | 10 |
| Gateway API | 网关 API | Ingress 的继任者，角色分离 | 10 |
| HTTPRoute / GRPCRoute | — | Gateway API 的路由规则 | 10 |
| NetworkPolicy | 网络策略 | Pod 级防火墙（需 CNI 支持） | 10 |
| externalTrafficPolicy | 外部流量策略 | Cluster / Local（是否保留源 IP） | 10 |
| Service Mesh | 服务网格 | mTLS、流量治理、可观测性 | 10 |

### 调度与弹性

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| Scheduler | 调度器 | 给 Pod 选节点 | 12 |
| Filter / Score | 过滤 / 打分 | 调度的两个阶段 | 12 |
| Allocatable | 可分配量 | 节点减去预留后的可调度资源 | 12 |
| nodeSelector / nodeAffinity | 节点选择器 / 节点亲和性 | Pod 选节点的规则 | 12 |
| podAffinity / podAntiAffinity | Pod 亲和 / 反亲和 | Pod 之间的位置关系 | 12 |
| Topology Spread Constraints | 拓扑分布约束 | 跨域均匀分布（推荐） | 12 |
| Taint / Toleration | 污点 / 容忍 | 节点排斥 Pod / Pod 容忍污点 | 12 |
| PriorityClass | 优先级类 | 抢占的依据 | 12 |
| Preemption | 抢占 | 高优先级驱逐低优先级 | 12 |
| Eviction | 驱逐 | kubelet 因资源压力杀 Pod | 12 |
| HPA / VPA | 水平 / 垂直 Pod 自动伸缩 | 调副本数 / 调资源配置 | 12 |
| Cluster Autoscaler / Karpenter | 集群自动伸缩 | 自动增减节点 | 12、21 |
| KEDA | — | 事件驱动的自动伸缩（可缩到 0） | 12 |
| cordon / drain / uncordon | 封锁 / 排空 / 解封 | 节点维护三部曲 | 12 |
| Descheduler | 重调度器 | 定期驱逐位置不合理的 Pod | 12 |

### 可观测性

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| Metrics / Logs / Traces | 指标 / 日志 / 追踪 | 可观测性三支柱 | 13 |
| Prometheus | — | 指标采集与存储（pull 模型） | 13 |
| PromQL | — | Prometheus 查询语言 | 13 |
| cAdvisor | — | kubelet 内置的容器资源指标 | 13 |
| kube-state-metrics | — | K8s 对象状态指标 | 13 |
| ServiceMonitor | — | Prometheus Operator 的抓取配置 CRD | 13 |
| Cardinality | 基数 | 时间序列数量（爆炸是头号杀手） | 13 |
| RED / USE | — | Rate-Errors-Duration / Utilization-Saturation-Errors | 13 |
| Exemplar | 样例 | 指标里指向具体 trace 的链接 | 13 |
| OpenTelemetry | — | 可观测性数据的开放标准 | 13 |
| Loki / Tempo / Mimir | — | Grafana 的日志 / 追踪 / 指标后端 | 13、21 |
| pprof | — | Go 的性能分析工具 | 13、22 |

### 安全

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| RBAC | 基于角色的访问控制 | Role/ClusterRole + Binding | 14 |
| ServiceAccount | 服务账号 | Pod 的身份 | 14 |
| Projected Token | 投影令牌 | 短期、自动轮转、绑定受众的 SA token | 14 |
| PSA | Pod 安全准入 | privileged / baseline / restricted | 14 |
| securityContext | 安全上下文 | Pod/容器的安全设置 | 07、14 |
| Capabilities | 能力 | 拆分后的 root 权限 | 02、14 |
| seccomp | — | 系统调用过滤 | 02、14 |
| User Namespace | 用户命名空间 | 容器 root 映射到宿主机非特权用户（1.36 GA） | 02、14 |
| ResourceQuota / LimitRange | 资源配额 / 限制范围 | namespace 级的总量 / 单对象约束 | 14 |
| Kyverno / OPA Gatekeeper | — | 策略引擎（准入控制） | 14 |
| Audit Log | 审计日志 | 谁在何时做了什么 | 14 |
| Supply Chain Security | 供应链安全 | 扫描、SBOM、签名、验签 | 03、14 |

### 交付

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| CI / CD | 持续集成 / 持续交付 | 构建验证 / 部署 | 17、18 |
| Immutable Artifact | 不可变构件 | 打了唯一 tag 的镜像 | 01、17 |
| Pipeline as Code | 流水线即代码 | Jenkinsfile 等 | 17 |
| BuildKit / Buildah | — | 无需 docker.sock 的镜像构建 | 17 |
| GitOps | — | Git 作为唯一真相源的持续调谐 | 18 |
| Push / Pull model | 推 / 拉 模型 | CI 推向集群 / 集群拉取 Git | 18 |
| Drift | 漂移 | 集群实际状态偏离 Git | 18 |
| selfHeal / prune | 自愈 / 修剪 | 自动改回 Git 状态 / 删除 Git 里没有的 | 18 |
| Application / ApplicationSet | — | Argo CD 的部署单元 / 批量生成器 | 18 |
| App of Apps | — | 用一个根 App 管理所有 App | 18 |
| Sync Wave | 同步波次 | 控制资源部署顺序 | 18 |
| Progressive Delivery | 渐进式交付 | 灰度 + 指标验证 + 自动回滚 | 19 |
| Blue-Green | 蓝绿部署 | 起两套环境整体切流 | 19 |
| Canary | 金丝雀发布 | 少量流量逐步放大 | 19 |
| Shadow Traffic | 影子流量 | 复制真实流量但丢弃响应 | 19 |
| AnalysisTemplate | 分析模板 | Argo Rollouts 的指标验证定义 | 19 |
| Expand-Contract | 扩展-收缩 | 向后兼容的 schema 演进模式 | 19 |
| Feature Flag | 特性开关 | 把"部署"和"发布"解耦 | 19 |

### 运维

| 英文 | 中文 | 说明 | 章节 |
|---|---|---|---|
| Day-0 / Day-1 / Day-2 | — | 设计 / 部署 / 持续运营 | 23 |
| SLI / SLO / SLA | 服务级别指标 / 目标 / 协议 | 度量 / 内部目标 / 对外承诺 | 23 |
| Error Budget | 错误预算 | `1 - SLO`，可容忍的不可用量 | 23 |
| Burn Rate | 燃烧率 | 错误预算的消耗速度 | 23 |
| Runbook | 处置手册 | 每条告警对应的操作指南 | 23 |
| Postmortem | 复盘 | 事故后的无指责分析 | 23 |
| Blameless | 无指责 | 复盘的文化前提 | 23 |
| Chaos Engineering | 混沌工程 | 主动制造故障验证韧性 | 23 |
| RTO / RPO | 恢复时间 / 恢复点目标 | 多久恢复 / 能丢多少数据 | 21、23 |
| Cluster API | — | 用 K8s API 管理集群本身 | 21 |
| Right-sizing | 规格优化 | 把 requests 调到合理值 | 21 |
| Bin Packing | 装箱 | 把 Pod 紧凑放置以省节点 | 21 |
| Platform Engineering | 平台工程 | 为开发者提供内部平台 | 21 |
| Golden Path | 黄金路径 | 铺好的最佳实践通道 | 21 |
| Velero | — | 集群备份恢复工具 | 11、21 |

---

## 2. 版本基线（2026-07）

| 组件 | 版本 | 备注 |
|---|---|---|
| Kubernetes | 1.36 "Haru" | 维护 1.34/1.35/1.36；每年 3 个小版本，各约 1 年支持 |
| containerd | 2.x | CRI 事实标准 |
| Helm | 4.2.x | Helm 3 安全补丁到 2027-02 |
| Argo CD | 3.4.x | 3.5 RC（内部 mTLS、提交签名验证） |
| Argo Rollouts | 1.9.x | |
| Jenkins LTS | 2.555.x | 需要 Java 21+ |
| Gateway API | 1.6.0 | |
| Prometheus Operator | — | kube-prometheus-stack |
| Cilium / Calico | — | 主流 CNI |

**重要的生态变化**：

- **ingress-nginx 已于 2026-03-24 退役**，无安全补丁。继任项目 InGate 也已终止。迁移到 Gateway API（Envoy Gateway / Traefik / HAProxy / Cilium）或 nginxinc/kubernetes-ingress。官方工具：[ingress2gateway](https://github.com/kubernetes-sigs/ingress2gateway)
- **Kaniko 已于 2025-06 归档**，集群内构建镜像改用 BuildKit 或 Buildah
- **PodSecurityPolicy 已在 1.25 移除**，用 Pod Security Admission + Kyverno
- **dockershim 已在 1.24 移除**，节点用 containerd/CRI-O（不影响 Docker 构建的镜像）
- **In-place Pod Resize 在 1.35 GA**，1.36 支持 Pod 级资源的原地调整
- **User Namespaces 在 1.36 GA**
- **原生 Sidecar 在 1.33 GA**
- **DRA（动态资源分配）在 1.34 GA**，GPU 场景的新标准

---

## 3. 官方文档地图

| 主题 | 链接 |
|---|---|
| 概念总览 | https://kubernetes.io/docs/concepts/ |
| API 参考 | https://kubernetes.io/docs/reference/kubernetes-api/ |
| kubectl 参考 | https://kubernetes.io/docs/reference/kubectl/ |
| 任务指南（怎么做 X） | https://kubernetes.io/docs/tasks/ |
| 教程 | https://kubernetes.io/docs/tutorials/ |
| 发布说明与废弃列表 | https://kubernetes.io/releases/ |
| KEP（设计提案，学架构最好的材料） | https://github.com/kubernetes/enhancements/tree/master/keps |
| API 类型源码（最权威的字段文档） | https://github.com/kubernetes/kubernetes/tree/master/staging/src/k8s.io/api |

**生态项目**：

| 项目 | 链接 |
|---|---|
| Helm | https://helm.sh/docs/ |
| Kustomize | https://kubectl.docs.kubernetes.io/references/kustomize/ |
| Argo CD | https://argo-cd.readthedocs.io/ |
| Argo Rollouts | https://argo-rollouts.readthedocs.io/ |
| Gateway API | https://gateway-api.sigs.k8s.io/ |
| Prometheus | https://prometheus.io/docs/ |
| cert-manager | https://cert-manager.io/docs/ |
| External Secrets | https://external-secrets.io/ |
| Kyverno | https://kyverno.io/docs/ |
| Cilium | https://docs.cilium.io/ |
| Karpenter | https://karpenter.sh/ |
| Velero | https://velero.io/docs/ |
| kubebuilder（写 Operator） | https://book.kubebuilder.io/ |
| CNCF 全景图 | https://landscape.cncf.io/ |
| Artifact Hub（找 Chart） | https://artifacthub.io/ |

---

## 4. 推荐书单

| 书 | 适合 |
|---|---|
| **Kubernetes in Action**（第 2 版，Marko Lukša） | 最好的 K8s 入门书，讲原理讲得透 |
| **Programming Kubernetes**（Hausenblas & Schimanski） | ⭐ Go 开发者写 Operator 必读 |
| **Kubernetes Patterns**（Ibryam & Huß） | 云原生设计模式 |
| **Container Security**（Liz Rice） | 第 2、14 章的深入版 |
| **Google SRE Book / Workbook** | ⭐ 免费在线，第 23 章的完整版 |
| **Site Reliability Workbook 第 2、5 章** | SLO 和告警设计的实操 |
| **Designing Data-Intensive Applications** | 分布式系统的底层原理（不限于 K8s） |
| **Team Topologies** | 平台团队的组织设计 |
| **Accelerate**（DORA） | 用数据证明为什么要做这些实践 |

---

## 5. 认证对照

| 认证 | 内容 | 对应本课程 |
|---|---|---|
| **CKA**（管理员） | 集群架构安装配置 25%、工作负载调度 15%、服务网络 20%、存储 10%、排障 30% | 06~14、21、22 |
| **CKAD**（开发者） | 应用设计构建 20%、部署 20%、可观测性维护 15%、环境配置安全 25%、服务网络 20% | 03~13 |
| **CKS**（安全，需先有 CKA） | 集群加固、系统加固、供应链安全、运行时安全、监控与审计 | 14 + 深入 |
| **KCNA**（入门） | 云原生基础概念 | 01~09 |

**备考建议**：CKA/CKAD/CKS 都是**纯实操**考试，允许查官方文档。核心是手速和对 `kubectl` 的熟练度。本课程的实验做完，再刷一遍 [killer.sh](https://killer.sh/) 的模拟题基本就够了。

---

## 6. 从这里继续

**如果你想深入某个方向**：

| 方向 | 下一步 |
|---|---|
| **写 Operator / 平台开发** | kubebuilder 教程 → 读 `sample-controller` → 读某个真实 Operator（cert-manager 代码质量很高） |
| **网络** | 读 Cilium 文档 → 学 eBPF → 读 CNI spec |
| **存储** | 读 CSI spec → 部署 Rook/Ceph 或 Longhorn |
| **调度** | 读 Scheduler Framework → 写一个调度插件 → 看 Volcano（批调度） |
| **安全** | CKS 考纲 → kube-bench → 读 CVE 分析 |
| **可观测性** | Prometheus 内部原理 → OpenTelemetry Collector → Thanos/Mimir |
| **SRE / 运维** | Google SRE Book → 在自己的团队推行 SLO |
| **成本优化** | OpenCost → FinOps Foundation 的材料 |

**保持更新的渠道**：
- [Kubernetes Blog](https://kubernetes.io/blog/)（每个版本的发布说明必看）
- [CNCF Blog](https://www.cncf.io/blog/)
- [KubeWeekly](https://www.cncf.io/kubeweekly/) 周报
- KubeCon 的会议录像（YouTube 上免费）
- SIG 会议（公开，可以直接参加）

---

[← 返回课程总览](./README.md) · [附录 A - 速查表](./A-cheatsheet.md)
