# 12 - 调度、资源与弹性伸缩

> 本章目标：搞懂"Pod 为什么被放在这个节点"、"怎么控制它放哪"、"怎么自动扩缩容"、
> 以及你问到的"**如何迁移**"——节点维护时把 Pod 平滑搬走。
> 预计用时：3 小时（含实验）。

---

## 1. 调度器怎么工作

调度器只做一件事：给 `spec.nodeName == ""` 的 Pod 选一个节点，然后写回 `nodeName`（这个动作叫 **Binding**）。

### 1.1 两个阶段

```
所有节点（比如 100 个）
      │
      ▼  ① Filter（过滤 / Predicates）—— 硬性条件，不满足直接排除
   ┌──────────────────────────────────────────────┐
   │ NodeResourcesFit    剩余 allocatable ≥ requests？│
   │ NodeAffinity        满足 nodeSelector/affinity？ │
   │ TaintToleration     能容忍节点的污点？            │
   │ NodePorts           hostPort 冲突吗？            │
   │ VolumeBinding       卷能在这个节点挂载吗？(可用区)  │
   │ NodeUnschedulable   节点被 cordon 了吗？          │
   │ PodTopologySpread   违反拓扑约束吗？              │
   │ InterPodAffinity    满足 Pod 间亲和/反亲和？       │
   └──────────────────────────────────────────────┘
      │  剩下 20 个可行节点（feasible）
      ▼  ② Score（打分 / Priorities）—— 每个插件打 0~100 分，加权求和
   ┌──────────────────────────────────────────────┐
   │ NodeResourcesBalancedAllocation  CPU/内存使用率均衡的得分高│
   │ NodeResourcesFit(LeastAllocated) 剩余资源多的得分高       │
   │ ImageLocality                    已有该镜像的节点得分高    │
   │ InterPodAffinity                 满足亲和偏好的得分高      │
   │ PodTopologySpread                分布更均匀的得分高        │
   │ TaintToleration                  容忍 PreferNoSchedule    │
   └──────────────────────────────────────────────┘
      │
      ▼ 选最高分（同分随机），写 spec.nodeName（Binding）
```

```bash
# 看某个 Pod 为什么调度失败
kubectl describe pod <pod> | tail -20
# Events:
#   Warning  FailedScheduling  0/4 nodes are available:
#     1 node(s) had untolerated taint {node-role.kubernetes.io/control-plane: },
#     3 Insufficient cpu.
#   ↑ 这行信息极其有用，逐条读
```

### 1.2 节点的 Allocatable

调度器看的不是节点总容量，而是 **allocatable**：

```
Node Capacity（总量）
  − kube-reserved      （给 kubelet、containerd 预留）
  − system-reserved    （给 OS、sshd、systemd 预留）
  − eviction-threshold （驱逐阈值预留，默认 memory.available<100Mi）
  = Allocatable        （调度器能分配的量）
```

```bash
kubectl describe node learn-worker | grep -A8 "Allocatable"
kubectl describe node learn-worker | grep -A6 "Allocated resources"
# 这里显示的是所有 Pod 的 requests 之和，以及占 allocatable 的百分比
```

⚠️ **重要**：`Allocated resources` 显示的是 **requests 总和**，不是实际使用量。看实际使用要用 `kubectl top node`。**节点可能显示 "CPU 95% allocated" 但实际 CPU 只用了 10%**——这说明大家的 requests 设得太高了（浪费），第 21 章会讲怎么优化。

---

## 2. 控制调度：从简单到复杂

### 2.1 nodeSelector（最简单）

```yaml
spec:
  nodeSelector:
    disktype: ssd
    kubernetes.io/os: linux
```

硬性条件，AND 关系。简单但不灵活（不能表达"或"、"优先"、"不等于"）。

```bash
kubectl label node learn-worker3 disktype=ssd
kubectl get nodes --show-labels
```

### 2.2 Node Affinity（更强的 nodeSelector）

```yaml
spec:
  affinity:
    nodeAffinity:
      # 硬性要求（不满足就不调度）
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:                     # 同一个 term 内是 AND
              - {key: node-pool, operator: In, values: [general, compute]}
              - {key: kubernetes.io/arch, operator: In, values: [amd64, arm64]}
          # 多个 term 之间是 OR

      # 软性偏好（尽量满足，不满足也调度）
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100                             # 1~100
          preference:
            matchExpressions:
              - {key: topology.kubernetes.io/zone, operator: In, values: [zone-a]}
        - weight: 50
          preference:
            matchExpressions:
              - {key: node-pool, operator: In, values: [spot]}
```

**operator**：`In`、`NotIn`、`Exists`、`DoesNotExist`、`Gt`、`Lt`

⚠️ **`IgnoredDuringExecution` 的含义**：调度时检查，**运行期间节点标签变了不会重新调度**。想让运行中的 Pod 因为不满足条件而被驱逐，需要 Descheduler（见 §7）。

### 2.3 Pod Affinity / Anti-Affinity（Pod 之间的关系）

```yaml
spec:
  affinity:
    # 亲和：想和某些 Pod 放一起（比如和缓存放同一个可用区，降低延迟）
    podAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels: {app: redis}
            topologyKey: topology.kubernetes.io/zone

    # ⭐ 反亲和：不要和自己的其他副本放一起（高可用的关键）
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchLabels: {app: hello}
          topologyKey: kubernetes.io/hostname     # ⭐ 拓扑域 = 节点
```

**`topologyKey` 决定"分散/聚集"的粒度**：

| topologyKey | 含义 |
|---|---|
| `kubernetes.io/hostname` | 按节点 |
| `topology.kubernetes.io/zone` | 按可用区 |
| `topology.kubernetes.io/region` | 按地域 |

⚠️ **Pod 反亲和的性能陷阱**：`requiredDuringScheduling` 的 Pod 反亲和计算复杂度很高（每个候选节点都要检查上面所有 Pod 的 label）。**几千个 Pod 的集群里会显著拖慢调度**。官方建议：优先用 **topologySpreadConstraints**（下一节），它是为这个场景专门优化的。

### 2.4 Topology Spread Constraints（⭐ 推荐）

比反亲和更精细：不是"绝对不能同节点"，而是"最多相差几个"。

```yaml
spec:
  topologySpreadConstraints:
    # 约束 1：跨可用区均匀分布，最多相差 1 个
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule      # 或 ScheduleAnyway（软约束）
      labelSelector:
        matchLabels: {app: hello}
      matchLabelKeys: [pod-template-hash]   # ⭐ 1.27+：滚动更新时只跟同版本的比较

    # 约束 2：跨节点尽量分散（软约束，节点不够时也能调度）
    - maxSkew: 1
      topologyKey: kubernetes.io/hostname
      whenUnsatisfiable: ScheduleAnyway
      labelSelector:
        matchLabels: {app: hello}
      minDomains: 3                         # 至少要分布在 3 个域上
      nodeAffinityPolicy: Honor             # 计算时是否考虑 nodeAffinity 过滤后的节点
      nodeTaintsPolicy: Honor
```

**`maxSkew` 的含义**：任意两个拓扑域中该 Pod 数量的最大差值。

```
maxSkew=1, topologyKey=zone, 6 个副本, 3 个可用区
✅ 2/2/2      （skew=0）
✅ 3/2/1      （skew=2 ❌ 不行！）
✅ 2/2/2 或 3/2/2（7 个副本时 skew=1）
```

**`matchLabelKeys: [pod-template-hash]` 很重要**：不加的话，滚动更新期间新旧版本的 Pod 会被算作同一组，导致新 Pod 因为"分布不均"而无法调度，滚动更新卡死。

**生产推荐组合**：

```yaml
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule       # 跨可用区必须均匀（硬）
    labelSelector: {matchLabels: {app: hello}}
    matchLabelKeys: [pod-template-hash]
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway      # 跨节点尽量均匀（软）
    labelSelector: {matchLabels: {app: hello}}
    matchLabelKeys: [pod-template-hash]
```

### 2.5 Taints & Tolerations（节点的"排斥"）

前面的机制都是 Pod 主动选节点。**污点是节点主动排斥 Pod**。

```bash
# 给节点打污点
kubectl taint node learn-worker3 dedicated=gpu:NoSchedule
kubectl taint node learn-worker3 dedicated=gpu:NoSchedule-      # 去掉（末尾加 -）
kubectl describe node learn-worker3 | grep -A3 Taints
```

三种 effect：

| effect | 行为 |
|---|---|
| `NoSchedule` | 不容忍的 Pod **不能调度**上来（已在上面的不动） |
| `PreferNoSchedule` | 尽量不调度（软） |
| `NoExecute` | 不容忍的 Pod **立即被驱逐**（包括已经在跑的） |

Pod 侧的容忍：

```yaml
spec:
  tolerations:
    - key: dedicated
      operator: Equal          # 或 Exists（不看 value）
      value: gpu
      effect: NoSchedule

    - key: node.kubernetes.io/not-ready
      operator: Exists
      effect: NoExecute
      tolerationSeconds: 30    # ⭐ 节点失联后等 30 秒才驱逐（默认 300 秒）

    - operator: Exists         # 容忍一切（DaemonSet 常用）
```

**内置污点**（K8s 自动打的）：

| 污点 | 何时打 |
|---|---|
| `node.kubernetes.io/not-ready` | 节点 NotReady |
| `node.kubernetes.io/unreachable` | 节点失联 |
| `node.kubernetes.io/memory-pressure` | 内存压力 |
| `node.kubernetes.io/disk-pressure` | 磁盘压力 |
| `node.kubernetes.io/pid-pressure` | PID 压力 |
| `node.kubernetes.io/unschedulable` | 被 `cordon` |
| `node-role.kubernetes.io/control-plane` | 控制面节点（防止业务 Pod 上去） |

**`tolerationSeconds` 的实践意义**：默认节点失联 300 秒后才驱逐 Pod（保守，避免网络抖动导致大规模迁移）。对可用性要求高的服务可以调短到 30~60 秒，但要权衡"网络抖动引起的无谓迁移"。

**典型用途：专用节点池**

```bash
# GPU 节点：打污点 + 打标签
kubectl taint node gpu-node-1 nvidia.com/gpu=true:NoSchedule
kubectl label node gpu-node-1 node-pool=gpu
```

```yaml
# GPU 任务：容忍污点 + 选择标签（两个都要！）
spec:
  tolerations:
    - {key: nvidia.com/gpu, operator: Exists, effect: NoSchedule}
  nodeSelector:
    node-pool: gpu
```

⚠️ **只有 toleration 没有 nodeSelector 是不够的**：toleration 只是"我能忍受这个污点"，不是"我要去那儿"。没有 nodeSelector 的话它照样可能被调度到普通节点。

### 2.6 优先级与抢占

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: high-priority}
value: 1000000                    # 数字越大优先级越高
globalDefault: false
preemptionPolicy: PreemptLowerPriority   # 或 Never（高优先但不抢占）
description: "关键在线服务"
```

```yaml
spec:
  priorityClassName: high-priority
```

**抢占**：高优先级 Pod 调度不上时，调度器会驱逐低优先级 Pod 腾地方。被抢占的 Pod 会收到 `DisruptionTarget` 条件和优雅终止期。

**内置优先级类**：
- `system-cluster-critical`（2000000000）—— 集群级关键组件
- `system-node-critical`（2000001000）—— 节点级关键组件（CNI、kube-proxy）

**实践建议**：定义 3~4 个等级即可。
```
critical (1000000)   数据库、网关
high     (100000)    核心在线服务
default  (0)         普通服务
low      (-100)      批处理、离线任务（可被随时抢占）
```

---

## 3. 驱逐：kubelet 什么时候杀 Pod

### 3.1 节点压力驱逐

kubelet 监控节点资源，超过阈值就驱逐 Pod：

```yaml
# kubelet 配置（/var/lib/kubelet/config.yaml）
evictionHard:
  memory.available: "100Mi"
  nodefs.available: "10%"
  nodefs.inodesFree: "5%"
  imagefs.available: "15%"
evictionSoft:
  memory.available: "300Mi"
evictionSoftGracePeriod:
  memory.available: "1m30s"
evictionMaxPodGracePeriod: 60
```

**驱逐顺序**：
1. 先看 QoS：`BestEffort` → `Burstable`（超出 requests 越多越先）→ `Guaranteed`
2. 同级别看 Pod 优先级（priorityClass）
3. 再看资源使用超出 requests 的程度

```bash
kubectl get events -A --field-selector reason=Evicted
kubectl describe node learn-worker | grep -A5 Conditions
```

### 3.2 OOMKill vs 驱逐（容易混淆）

| | OOMKilled | Evicted |
|---|---|---|
| 谁触发 | Linux 内核的 OOM killer | kubelet |
| 原因 | **容器**超过自己的 memory limit | **节点**整体内存/磁盘不足 |
| 表现 | 容器退出码 137，Pod 原地重启 | Pod 状态变 `Failed`，reason=`Evicted`，会被重新调度到别的节点 |
| 排查 | `kubectl describe pod` 看 Last State | `kubectl get events` |

---

## 4. 自动扩缩容三件套

```
        流量增加
            │
            ▼
  ┌──────────────────────┐
  │  HPA                 │  副本数 3 → 10（水平扩容 Pod）
  │  (Horizontal Pod     │
  │   Autoscaler)        │
  └──────────┬───────────┘
             │ 节点资源不够，新 Pod Pending
             ▼
  ┌──────────────────────┐
  │  Cluster Autoscaler  │  节点数 5 → 8（扩容节点）
  │  / Karpenter         │
  └──────────────────────┘

  ┌──────────────────────┐
  │  VPA                 │  单个 Pod 的 requests/limits 调整（垂直）
  │  (Vertical Pod       │
  │   Autoscaler)        │
  └──────────────────────┘
```

### 4.1 HPA（水平 Pod 自动扩缩容）

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {name: hello}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hello
  minReplicas: 3
  maxReplicas: 50

  metrics:
    # ① 资源指标（需要 metrics-server）
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70      # ⭐ 是相对 requests 的百分比，不是绝对值！
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80

    # ② Pod 自定义指标（需要 prometheus-adapter）
    - type: Pods
      pods:
        metric: {name: http_requests_per_second}
        target: {type: AverageValue, averageValue: "1000"}

    # ③ 外部指标（如 Kafka lag、SQS 队列长度）
    - type: External
      external:
        metric:
          name: kafka_consumergroup_lag
          selector: {matchLabels: {topic: orders}}
        target: {type: AverageValue, averageValue: "1000"}

  # ⭐ 扩缩容行为（2.x 的关键能力，防止抖动）
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0      # 扩容不等待，立刻响应
      policies:
        - {type: Percent, value: 100, periodSeconds: 30}   # 30 秒内最多翻倍
        - {type: Pods, value: 10, periodSeconds: 30}       # 30 秒内最多加 10 个
      selectPolicy: Max                  # 取最激进的
    scaleDown:
      stabilizationWindowSeconds: 300    # ⭐ 缩容前观察 5 分钟（取窗口内最大值）
      policies:
        - {type: Percent, value: 20, periodSeconds: 60}    # 每分钟最多缩 20%
      selectPolicy: Min                  # 取最保守的
```

**HPA 的计算公式**：

```
期望副本数 = ceil( 当前副本数 × ( 当前指标值 / 目标指标值 ) )
```

例：3 个副本，平均 CPU 使用率 90%，目标 70%
→ `ceil(3 × 90/70) = ceil(3.86) = 4`

**关键理解：`averageUtilization: 70` 是相对 `requests` 的百分比。** 如果 `requests.cpu: 100m`，那 70% 就是 70m。**没设 CPU requests 的 Pod，HPA 完全无法工作**。

```bash
kubectl get hpa
# NAME    REFERENCE          TARGETS           MINPODS  MAXPODS  REPLICAS
# hello   Deployment/hello   45%/70%, 30%/80%  3        50       3
kubectl describe hpa hello       # 看扩缩容决策和事件
```

**HPA 的坑**：

| 坑 | 说明 |
|---|---|
| CPU 指标滞后 | metrics-server 15 秒采集一次，HPA 15 秒同步一次 → 响应有 30~60 秒延迟。突发流量扛不住 → 用自定义指标（QPS）或预留缓冲 |
| 冷启动 | 新 Pod 启动要时间（拉镜像 + 预热）。用 `startupProbe` + 提前扩容 |
| 与 VPA 冲突 | **同时用 HPA(CPU) 和 VPA 会互相打架**，绝对不要 |
| 与手工 scale 冲突 | HPA 会把你手工设的副本数改回去 |
| 与 GitOps 冲突 | Argo CD 会把 replicas 改回 Git 里的值 → Chart 里**不要写 replicas**，或让 Argo CD 忽略该字段（第 18 章） |
| 缩容抖动 | 一定要设 `scaleDown.stabilizationWindowSeconds` |

### 4.2 KEDA（事件驱动扩缩容）

HPA 只能用 CPU/内存和有限的自定义指标。**KEDA** 扩展了 60+ 种触发器（Kafka、RabbitMQ、Redis、SQS、Prometheus、cron……），并且支持**缩容到 0**：

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata: {name: consumer}
spec:
  scaleTargetRef: {name: order-consumer}
  minReplicaCount: 0          # ⭐ 可以缩到 0
  maxReplicaCount: 100
  pollingInterval: 15
  cooldownPeriod: 300
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: orders
        topic: orders
        lagThreshold: "100"    # 每 100 条 lag 加一个副本
```

批处理、消息消费类负载强烈推荐 KEDA。

### 4.3 VPA（垂直扩缩容）

自动调整 requests/limits：

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata: {name: hello}
spec:
  targetRef: {apiVersion: apps/v1, kind: Deployment, name: hello}
  updatePolicy:
    updateMode: "Off"     # ⭐ Off（只推荐不改）| Initial（只在创建时）| Auto（自动，会重建 Pod）
  resourcePolicy:
    containerPolicies:
      - containerName: server
        minAllowed: {cpu: 50m, memory: 64Mi}
        maxAllowed: {cpu: 2, memory: 2Gi}
        controlledResources: [cpu, memory]
```

```bash
kubectl describe vpa hello
# Recommendation:
#   Target:  cpu: 250m, memory: 300Mi     ← 建议值
#   Lower Bound / Upper Bound
```

**强烈建议用 `updateMode: "Off"`**：把 VPA 当作"资源配置推荐引擎"，人工审核后写进 Git。`Auto` 模式会重建 Pod（在 1.35 原地扩缩容 GA 后这个问题正在改善，但生态还没完全跟上）。

**VPA 的最大价值**：告诉你"你的 requests 设得离谱"。第 21 章讲成本优化时会用到。

### 4.4 Cluster Autoscaler / Karpenter（节点扩缩容）

| | Cluster Autoscaler | **Karpenter** |
|---|---|---|
| 原理 | 基于**预定义的节点组**（ASG/节点池）增减节点 | 直接根据 Pending Pod 的**实际需求**创建最合适的节点 |
| 灵活性 | 受节点组规格限制 | 自动选实例类型、可用区、Spot/按需 |
| 速度 | 较慢（几分钟） | 快（几十秒） |
| 支持 | 所有云 + 自建 | AWS 成熟，其他云逐步支持 |
| 整合（bin-packing） | 弱 | 强，会主动整合以降低成本 |

**触发条件**：
- 扩容：有 Pod 因为资源不足而 `Pending`
- 缩容：节点利用率长时间低于阈值（默认 50%），且上面的 Pod 都能被搬到别处

**缩容的阻碍**（这些 Pod 会让节点无法被回收）：
- 没有控制器管理的裸 Pod
- 使用 local storage / emptyDir 的 Pod（除非加了 `cluster-autoscaler.kubernetes.io/safe-to-evict: "true"`）
- PDB 不允许驱逐
- 有 `cluster-autoscaler.kubernetes.io/safe-to-evict: "false"` 注解的 Pod
- kube-system 里没有 PDB 的 Pod

---

## 5. 节点维护与 Pod 迁移（⭐ 你问的"迁移"）

### 5.1 标准流程

```bash
# ① cordon：标记为不可调度（新 Pod 不再来，已有 Pod 不动）
kubectl cordon learn-worker
kubectl get nodes
# learn-worker   Ready,SchedulingDisabled

# ② drain：驱逐节点上的所有 Pod（会自动 cordon）
kubectl drain learn-worker \
  --ignore-daemonsets \           # DaemonSet 的 Pod 不驱逐（驱逐了也会立刻重建）
  --delete-emptydir-data \        # 允许删除使用 emptyDir 的 Pod（数据会丢！）
  --grace-period=60 \             # 优雅终止期
  --timeout=300s \                # 整体超时
  --force                         # 允许驱逐没有控制器管理的裸 Pod（数据会丢！）

# ③ 维护：升级内核、换硬件、升级 kubelet……
docker exec learn-worker apt update   # 示意

# ④ uncordon：恢复调度
kubectl uncordon learn-worker
```

### 5.2 drain 的内部机制

`drain` 用的是 **Eviction API**（`POST /api/v1/namespaces/x/pods/y/eviction`），不是直接 delete。区别：

- Eviction API 会**检查 PDB**：违反 PDB 就返回 429，drain 会重试等待
- 这就是第 9 章 PDB 的作用场景

驱逐后发生什么（以 Deployment 为例）：

```
① Pod 被驱逐（进入 Terminating，preStop → SIGTERM → 优雅退出）
② ReplicaSet 控制器发现副本数少了
③ 创建新 Pod
④ 调度器把新 Pod 放到其他节点（原节点已 cordon）
⑤ 新 Pod 启动、Ready、加入 Service
```

**注意步骤 ③④⑤ 是在 ① 之后才开始的**——也就是说，**驱逐期间容量是下降的**。所以：
- 副本数要 > PDB 的 `minAvailable`
- 一次只 drain 一个节点
- 大规模维护要分批，且监控服务指标

### 5.3 有状态服务的迁移

StatefulSet 的 Pod 被驱逐后：
1. Pod 在新节点上以**同样的名字**重建
2. PVC 跟着走——但**前提是存储能在新节点挂载**

⚠️ **可用区约束**：云盘绑定在某个可用区。如果 `db-0` 的 PVC 在 zone-a，那 `db-0` 只能调度到 zone-a 的节点。zone-a 全挂了 → Pod 永远 Pending。

**跨可用区迁移有状态数据的方案**：
- 应用层复制（Postgres 流复制、Kafka 副本、etcd Raft）——**这才是正确答案**
- 存储层跨区复制（部分云盘支持，性能有损耗）
- 快照 + 在新可用区恢复（有 RPO，不适合在线迁移）

### 5.4 集群升级时的节点轮转（第 21、23 章展开）

生产上更推荐**替换而非原地升级**：

```
① 创建新版本的节点组（新 AMI / 新 kubelet 版本）
② 逐个 cordon + drain 旧节点
③ Pod 自动迁移到新节点
④ 删除旧节点
```

这符合不可变基础设施，且回滚容易（把新节点组删掉即可）。

### 5.5 Descheduler：重平衡

调度是"一次性"的——Pod 一旦调度就不会因为集群状态变化而重新分布。时间久了会出现：
- 新加的节点很空，老节点很满
- 反亲和/拓扑约束因为节点变化而不再满足
- 某些节点上堆积了大量 Pod

**Descheduler** 定期驱逐"位置不合理"的 Pod，让它们被重新调度：

```yaml
# 常用策略
profiles:
  - name: default
    pluginConfig:
      - name: RemoveDuplicates                    # 同一个 RS 的多个 Pod 在同节点
      - name: LowNodeUtilization                  # 从高负载节点搬到低负载节点
        args:
          thresholds: {cpu: 20, memory: 20, pods: 20}
          targetThresholds: {cpu: 50, memory: 50, pods: 50}
      - name: RemovePodsViolatingTopologySpreadConstraint
      - name: RemovePodsViolatingInterPodAntiAffinity
      - name: RemovePodsViolatingNodeTaints
      - name: PodLifeTime                         # 驱逐运行超过 N 天的 Pod
```

⚠️ Descheduler 会**主动杀 Pod**，务必配好 PDB 和优雅退出，并且从保守的阈值开始。

---

## 6. 动手实验

### 实验 1：观察调度决策

```bash
kubectl create ns sched && kubectl config set-context --current --namespace=sched
kubectl create deployment hello --image=hello:v0.1.0 --replicas=6
kubectl patch deploy hello -p '{"spec":{"template":{"spec":{"containers":[{"name":"hello","imagePullPolicy":"IfNotPresent"}]}}}}'
kubectl get pods -o wide      # 观察分布在哪些节点
kubectl get pods -o custom-columns='NAME:.metadata.name,NODE:.spec.nodeName' | sort -k2
```

### 实验 2：制造 Pending

```bash
kubectl run huge --image=nginx:alpine \
  --overrides='{"spec":{"containers":[{"name":"huge","image":"nginx:alpine",
"resources":{"requests":{"cpu":"100","memory":"200Gi"}}}]}}'
sleep 5
kubectl get pod huge
kubectl describe pod huge | tail -8
# Warning FailedScheduling: 0/4 nodes are available: 4 Insufficient cpu, 4 Insufficient memory
kubectl delete pod huge
```

### 实验 3：nodeSelector 与污点

```bash
kubectl label node learn-worker3 node-pool=special
kubectl taint node learn-worker3 dedicated=special:NoSchedule

# 普通 Pod 不会去 worker3
kubectl create deployment normal --image=nginx:alpine --replicas=6
kubectl get pods -l app=normal -o wide | grep worker3     # 无输出 ✅

# 带 toleration + nodeSelector 的会去
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata: {name: special}
spec:
  replicas: 2
  selector: {matchLabels: {app: special}}
  template:
    metadata: {labels: {app: special}}
    spec:
      nodeSelector: {node-pool: special}
      tolerations: [{key: dedicated, operator: Equal, value: special, effect: NoSchedule}]
      containers: [{name: c, image: nginx:alpine}]
EOF
kubectl get pods -l app=special -o wide    # 都在 worker3 ✅
```

### 实验 4：⭐ 拓扑分布约束（用第 0 章打的 zone 标签）

```bash
kubectl get nodes -L topology.kubernetes.io/zone

kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata: {name: spread}
spec:
  replicas: 6
  selector: {matchLabels: {app: spread}}
  template:
    metadata: {labels: {app: spread}}
    spec:
      tolerations: [{key: dedicated, operator: Exists}]
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector: {matchLabels: {app: spread}}
          matchLabelKeys: [pod-template-hash]
      containers:
        - name: c
          image: nginx:alpine
          resources: {requests: {cpu: 10m, memory: 16Mi}}
EOF

kubectl get pods -l app=spread -o custom-columns='NAME:.metadata.name,NODE:.spec.nodeName' | tail -n +2 | \
  awk '{print $2}' | sort | uniq -c
# 应该是每个 zone 2 个 ✅
```

### 实验 5：Pod 反亲和

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata: {name: anti}
spec:
  replicas: 5              # 只有 3 个可调度节点（worker3 有污点）
  selector: {matchLabels: {app: anti}}
  template:
    metadata: {labels: {app: anti}}
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector: {matchLabels: {app: anti}}
              topologyKey: kubernetes.io/hostname
      containers: [{name: c, image: nginx:alpine, resources: {requests: {cpu: 10m}}}]
EOF
sleep 10
kubectl get pods -l app=anti -o wide
# 3 个 Running（每节点一个），2 个 Pending ← 硬性反亲和的代价
kubectl describe pod -l app=anti | grep -A3 "FailedScheduling" | head -5
```

### 实验 6：⭐ 节点维护与迁移（drain）

```bash
kubectl get pods -l app=hello -o wide
NODE=learn-worker

# 加 PDB 保护
kubectl apply -f - <<'EOF'
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: hello-pdb}
spec:
  maxUnavailable: 1
  selector: {matchLabels: {app: hello}}
EOF

# 一边观察
kubectl get pods -l app=hello -o wide -w &

# 一边 drain
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=180s

sleep 5; kill %1
kubectl get pods -l app=hello -o wide      # ⭐ 全部迁到其他节点了
kubectl get node $NODE                     # SchedulingDisabled

kubectl uncordon $NODE
kubectl get nodes
```

**注意**：uncordon 之后，已经迁走的 Pod **不会自动搬回来**——调度是一次性的。需要重平衡就用 Descheduler，或 `kubectl rollout restart`。

### 实验 7：HPA

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata: {name: php-apache}
spec:
  replicas: 1
  selector: {matchLabels: {run: php-apache}}
  template:
    metadata: {labels: {run: php-apache}}
    spec:
      containers:
        - name: php-apache
          image: registry.k8s.io/hpa-example
          ports: [{containerPort: 80}]
          resources:
            requests: {cpu: 200m}
            limits: {cpu: 500m}
---
apiVersion: v1
kind: Service
metadata: {name: php-apache}
spec:
  selector: {run: php-apache}
  ports: [{port: 80}]
EOF

kubectl autoscale deployment php-apache --cpu-percent=50 --min=1 --max=10
kubectl get hpa -w &

# 加压
kubectl run -it --rm load --image=busybox:1.37 --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://php-apache; done"
# 观察 TARGETS 从 0% 涨到 200%+，REPLICAS 从 1 涨到 4~8

# Ctrl-C 停止加压，观察 5 分钟后开始缩容（stabilizationWindow）
kill %1
kubectl describe hpa php-apache | tail -15    # 看扩缩容事件
```

### 实验 8：优先级与抢占

```bash
kubectl apply -f - <<'EOF'
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: low-prio}
value: -100
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: high-prio}
value: 1000000
EOF

# 先用低优先级 Pod 把节点占满
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata: {name: filler}
spec:
  replicas: 12
  selector: {matchLabels: {app: filler}}
  template:
    metadata: {labels: {app: filler}}
    spec:
      priorityClassName: low-prio
      containers:
        - name: c
          image: nginx:alpine
          resources: {requests: {cpu: 300m, memory: 200Mi}}
EOF
sleep 15
kubectl get pods -l app=filler | grep -c Running

# 再来一个高优先级的大 Pod
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: vip}
spec:
  priorityClassName: high-prio
  containers:
    - name: c
      image: nginx:alpine
      resources: {requests: {cpu: 1, memory: 1Gi}}
EOF
sleep 15
kubectl get pods | grep -E "vip|filler" | head
kubectl get events --field-selector reason=Preempted
# ⭐ 一些 filler 被抢占（Terminating），vip 成功调度
```

### 清理

```bash
kubectl delete ns sched
kubectl taint node learn-worker3 dedicated=special:NoSchedule-
kubectl label node learn-worker3 node-pool-
kubectl delete priorityclass low-prio high-prio
kubectl config set-context --current --namespace=default
```

---

## 7. 本章检查清单

- [ ] 调度的两个阶段是什么？各自做什么？
- [ ] `Allocated resources` 显示的是实际用量还是 requests？这个区别为什么重要？
- [ ] nodeSelector、nodeAffinity、podAntiAffinity、topologySpreadConstraints 的区别与选用
- [ ] `IgnoredDuringExecution` 意味着什么？
- [ ] 为什么官方建议用 topologySpreadConstraints 而不是 Pod 反亲和？
- [ ] `matchLabelKeys: [pod-template-hash]` 不加会导致什么问题？
- [ ] 污点的三种 effect 分别是什么？
- [ ] 只加 toleration 不加 nodeSelector，Pod 会被调度到专用节点吗？
- [ ] OOMKilled 和 Evicted 的区别？
- [ ] HPA 的 `averageUtilization: 70` 是相对什么的百分比？没设 requests 会怎样？
- [ ] HPA 和 VPA 能同时用吗？HPA 和 GitOps 有什么冲突？
- [ ] 完整描述节点维护的迁移流程（cordon → drain → uncordon）
- [ ] drain 用的是 delete 还是 eviction API？区别是什么？
- [ ] 有状态服务跨可用区迁移的正确方案是什么？
- [ ] uncordon 后 Pod 会自动搬回来吗？
- [ ] 完成实验 4（拓扑分布）、6（drain 迁移）、7（HPA）

---

## 8. 延伸阅读

- [调度器工作原理](https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/)
- [Pod 拓扑分布约束](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
- [污点和容忍](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [HPA 详解](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Karpenter](https://karpenter.sh/) / [KEDA](https://keda.sh/) / [Descheduler](https://github.com/kubernetes-sigs/descheduler)

---

下一章：[13 - 可观测性：日志、指标、追踪](./13-observability.md)
