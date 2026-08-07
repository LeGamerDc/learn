# 09 - 工作负载控制器：无状态与有状态

> 本章目标：回答你的三个关键问题——**如何把服务部署成集群、有状态与无状态服务的本质差异、如何滚动更新**。
> 这是全课程最实用的一章。
> 预计用时：3.5 小时（含实验）。

---

## 1. 工作负载全家福

Pod 是最小单位，但你**几乎不应该直接创建 Pod**——裸 Pod 没人管，节点挂了就永远没了。

| 控制器 | 管什么 | 用途 |
|---|---|---|
| **ReplicaSet** | 维持 N 个相同的 Pod | 底层组件，通常不直接用 |
| **Deployment** | 管理 ReplicaSet，提供滚动更新和回滚 | **无状态服务的标准选择** ⭐ |
| **StatefulSet** | 有稳定标识、稳定存储、有序操作的 Pod | 数据库、消息队列、需要固定身份的服务 |
| **DaemonSet** | 每个（符合条件的）节点上跑一个 | 日志采集、监控 agent、CNI、存储插件 |
| **Job** | 跑到成功完成为止 | 批处理、数据迁移、一次性任务 |
| **CronJob** | 定时创建 Job | 定时任务 |
| **ReplicationController** | Deployment 的前身 | ⚠️ 已废弃，不要用 |

---

## 2. Deployment：无状态服务的标准答案

### 2.1 三层关系

```
Deployment  (管理版本和更新策略)
    │ 每次 template 变化创建一个新的
    ├── ReplicaSet v1 (replicas: 0)   ← 旧版本，保留用于回滚
    └── ReplicaSet v2 (replicas: 3)   ← 当前版本
            ├── Pod-abc
            ├── Pod-def
            └── Pod-ghi
```

**关键理解**：Deployment 不直接管 Pod。它通过"创建新 RS + 逐步调整两个 RS 的副本数"来实现滚动更新。

### 2.2 完整定义

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
  labels:
    app.kubernetes.io/name: hello
spec:
  replicas: 3

  # ⚠️ selector 创建后不可变！必须匹配 template.metadata.labels
  selector:
    matchLabels:
      app.kubernetes.io/name: hello

  revisionHistoryLimit: 10      # 保留多少个旧 ReplicaSet 用于回滚（默认 10）
  minReadySeconds: 10           # ⭐ Pod Ready 后还要稳定存活多久才算"可用"
  progressDeadlineSeconds: 600  # 多久没进展就标记 Progressing=False（失败）
  paused: false                 # 暂停滚动更新

  strategy:
    type: RollingUpdate         # 或 Recreate
    rollingUpdate:
      maxSurge: 25%             # 最多可以超出 replicas 多少个（向上取整）
      maxUnavailable: 25%       # 最多可以有多少个不可用（向下取整）

  template:                     # ← 这就是第 7 章的 Pod 模板
    metadata:
      labels:
        app.kubernetes.io/name: hello
      annotations:
        checksum/config: "abc123"   # 配置变了触发滚动更新（第 8 章）
    spec:
      terminationGracePeriodSeconds: 45
      containers:
        - name: server
          image: hello:v0.1.0
          ports: [{name: http, containerPort: 8080}]
          readinessProbe:
            httpGet: {path: /readyz, port: http}
            periodSeconds: 5
          livenessProbe:
            httpGet: {path: /healthz, port: http}
            periodSeconds: 10
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits:   {memory: 512Mi}
          lifecycle:
            preStop: {sleep: {seconds: 5}}
```

### 2.3 两种更新策略

**`Recreate`**：先全删，再全建。

```
旧: ███  →  (全部删除)  →  (服务中断)  →  新: ███
```
适用：不能有两个版本共存的场景（数据库 schema 不兼容、独占某个资源、单例应用）。**会有停机**。

**`RollingUpdate`**（默认）：新旧交替，逐步替换。

```
初始:  旧 旧 旧
step1: 旧 旧 旧 新↑        maxSurge 允许多起一个
step2: 旧 旧 ✗   新        新的 Ready 后，删一个旧的
step3: 旧 旧     新 新↑
...
最终:            新 新 新
```

### 2.4 maxSurge 与 maxUnavailable 详解

这两个参数决定了滚动更新的**速度**和**容量保障**：

| 配置 | 更新期间容量 | 特点 | 适用 |
|---|---|---|---|
| `maxSurge: 25%`<br>`maxUnavailable: 25%` | 75% ~ 125% | 默认，快 | 一般服务 |
| `maxSurge: 1`<br>`maxUnavailable: 0` | **100% ~ 100%+1** | ⭐ **容量不下降**，最安全 | 生产在线服务 |
| `maxSurge: 100%`<br>`maxUnavailable: 0` | 100% ~ 200% | 最快，但瞬间需要双倍资源 | 资源充足、要求极快 |
| `maxSurge: 0`<br>`maxUnavailable: 1` | 67% ~ 100% | 不需要额外资源 | 资源紧张时 |

⚠️ **两个都设为 0 是非法的**（会永远卡住）。

**生产推荐**：

```yaml
strategy:
  rollingUpdate:
    maxSurge: 1           # 或 25%
    maxUnavailable: 0     # ⭐ 关键：保证容量不下降
minReadySeconds: 10       # ⭐ 关键：给新 Pod 一个"观察期"
```

**`minReadySeconds` 为什么重要**：没有它，Pod 一 Ready 就被认为可用，立刻删下一个旧 Pod。但很多问题（连接池初始化失败、JIT 预热不足、内存泄漏）要几秒后才暴露。设 10~30 秒能让明显有问题的版本在更新过程中就被卡住，而不是全部替换完才发现。

### 2.5 精确的滚动更新算法

Deployment 控制器每轮循环做的事（简化的真实逻辑）：

```go
// 期望：replicas=3, maxSurge=1, maxUnavailable=0
maxTotal := replicas + maxSurge          // 4：所有 RS 的 Pod 总数上限
minAvailable := replicas - maxUnavailable // 3：可用 Pod 数下限

for !rolloutComplete() {
    // ① 尽可能扩新 RS（在总数上限内）
    if currentTotal < maxTotal {
        scaleUp(newRS, maxTotal - currentTotal)
    }

    // ② 在可用数不低于下限的前提下，缩旧 RS
    //    注意：available 的判定包含 minReadySeconds
    if currentAvailable > minAvailable {
        scaleDown(oldRS, currentAvailable - minAvailable)
    }

    // ③ 超过 progressDeadlineSeconds 没进展 → 标记失败（但不自动回滚！）
    if noProgressFor(progressDeadlineSeconds) {
        setCondition(Progressing, False, "ProgressDeadlineExceeded")
    }
    wait()
}
```

⚠️ **重要：`progressDeadlineSeconds` 超时后 K8s 不会自动回滚**，只是把 Deployment 标记为失败状态。自动回滚需要：CI/CD 流水线检查 `kubectl rollout status` 的返回码后主动回滚（第 17 章），或者用 Argo Rollouts（第 19 章）。

### 2.6 rollout 命令族

```bash
# 更新镜像（会记录 change-cause）
kubectl set image deployment/hello server=hello:v0.2.0
kubectl annotate deployment/hello kubernetes.io/change-cause="upgrade to v0.2.0"

# ⭐ 等待更新完成（CI 里必须用，返回码非 0 表示失败）
kubectl rollout status deployment/hello --timeout=300s

# 查看历史
kubectl rollout history deployment/hello
# REVISION  CHANGE-CAUSE
# 1         initial deploy
# 2         upgrade to v0.2.0
kubectl rollout history deployment/hello --revision=2

# 回滚
kubectl rollout undo deployment/hello                  # 回上一版
kubectl rollout undo deployment/hello --to-revision=1  # 回指定版本

# 暂停 / 恢复（用于金丝雀：先更新一部分，观察后再继续）
kubectl rollout pause deployment/hello
kubectl set image deployment/hello server=hello:v0.3.0   # 暂停期间改动不会触发更新
kubectl rollout resume deployment/hello

# 强制重启所有 Pod（配置变更后常用）
kubectl rollout restart deployment/hello

# 扩缩容
kubectl scale deployment/hello --replicas=5
kubectl scale deployment/hello --current-replicas=5 --replicas=10   # 带前置条件
```

### 2.7 什么变化会触发滚动更新？

**只有 `spec.template` 的任何字段变化才会触发。**

| 操作 | 触发滚动更新？ |
|---|---|
| 改 `template.spec.containers[].image` | ✅ |
| 改 `template.metadata.annotations` | ✅（这就是 checksum 技巧的原理） |
| 改 `template.spec.resources` | ✅ |
| 改 `spec.replicas` | ❌ 只是扩缩容 |
| 改 `spec.strategy` | ❌ |
| 改被引用的 ConfigMap 的内容 | ❌ **（第 8 章的重点）** |
| `kubectl rollout restart` | ✅（它给 template 加了个时间戳 annotation） |

---

## 3. 无状态 vs 有状态：本质差异

这是你明确问到的问题。先建立判断标准。

### 3.1 什么是"无状态"

**无状态 ≠ 没有数据**，而是：**任意一个副本都可以处理任意一个请求，副本之间完全可替换。**

| | 无状态（Deployment） | 有状态（StatefulSet） |
|---|---|---|
| **身份** | Pod 名随机（`hello-7d4b-x9k2`），无意义 | Pod 名固定有序（`db-0`、`db-1`、`db-2`） |
| **网络标识** | IP 随机，只能通过 Service 访问 | 每个 Pod 有稳定 DNS：`db-0.db-headless.ns.svc.cluster.local` |
| **存储** | 通常无（或共享只读） | **每个 Pod 独占一个 PVC**，重建后仍挂回原来那个 |
| **启动顺序** | 并行，无序 | **有序**：0 → 1 → 2（前一个 Ready 才起下一个） |
| **停止顺序** | 并行，无序 | **逆序**：2 → 1 → 0 |
| **更新** | 随机顺序替换 | **逆序**，一次一个 |
| **扩容** | 随便加 | 有序加，且新副本可能需要从现有副本同步数据 |
| **缩容** | 随便删 | 逆序删（先删序号最大的），PVC 默认保留 |
| **可替换性** | 完全可替换 | 每个都是独一无二的（`db-0` 可能是主库） |

### 3.2 判断你的服务属于哪种

```
你的服务是否满足以下全部条件？
  □ 任何副本都能处理任何请求
  □ 副本之间不需要互相知道对方是谁
  □ 重启后不需要恢复本地数据
  □ 可以任意顺序启停
  □ 扩容时新副本不需要从老副本同步状态
        │
   全是 ─┴─ 有任一否
    ↓          ↓
Deployment  StatefulSet（或考虑用 Operator）
```

**典型无状态**：HTTP API、gRPC 服务、Web 前端、无状态计算 worker
**典型有状态**：MySQL/PostgreSQL、Redis Cluster、Kafka、ZooKeeper、etcd、Elasticsearch

**注意**：`session` 存内存的 Web 服务是"伪无状态"——扩缩容会丢 session。正确做法是把 session 外置到 Redis，让服务真正无状态。**能改造成无状态就一定要改造**，有状态服务的运维代价高一个数量级。

### 3.3 一个重要的实践建议

> **不要在 K8s 上自己用 StatefulSet 裸跑生产数据库**，除非你有很强的把握。
>
> 用 Operator（CloudNativePG、Zalando Postgres Operator、Strimzi for Kafka、Redis Operator）——
> 它们封装了备份、failover、版本升级、连接池、监控这些 StatefulSet 本身不提供的能力。
>
> 或者干脆用云托管服务（RDS、ElastiCache、MSK）。**数据库放 K8s 里省下的成本，
> 往往抵不过一次数据丢失的代价。** 这不是保守，是很多团队交过学费的经验。
>
> StatefulSet 适合的场景：你自己写的、有状态但相对简单的服务；或者作为学习和非关键环境。

---

## 4. StatefulSet 详解

### 4.1 完整定义

```yaml
# ① 必须先有一个 Headless Service（clusterIP: None）提供稳定 DNS
apiVersion: v1
kind: Service
metadata:
  name: db-headless
spec:
  clusterIP: None              # ⭐ headless：不分配虚拟 IP，DNS 直接返回 Pod IP
  selector:
    app: db
  ports:
    - {name: pg, port: 5432}
  publishNotReadyAddresses: true   # 未就绪的 Pod 也发布 DNS（集群自举时需要）
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: db
spec:
  serviceName: db-headless     # ⭐ 关联的 headless service，决定 DNS 后缀
  replicas: 3
  selector:
    matchLabels: {app: db}

  podManagementPolicy: OrderedReady   # 或 Parallel（不需要有序时用，启动快得多）

  updateStrategy:
    type: RollingUpdate        # 或 OnDelete（只有手工删 Pod 才更新）
    rollingUpdate:
      partition: 0             # ⭐ 只更新序号 >= partition 的 Pod（金丝雀神器）
      maxUnavailable: 1        # 1.24+ beta，允许并行更新几个

  # ⭐ 缩容/删除时 PVC 怎么处理（1.27+ beta，1.32+ 稳定）
  persistentVolumeClaimRetentionPolicy:
    whenDeleted: Retain        # 删除 StatefulSet 时：Retain（保留，默认）| Delete
    whenScaled: Retain         # 缩容时：Retain | Delete

  template:
    metadata:
      labels: {app: db}
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: postgres
          image: postgres:17-alpine
          ports: [{name: pg, containerPort: 5432}]
          env:
            - name: POD_NAME
              valueFrom: {fieldRef: {fieldPath: metadata.name}}
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          volumeMounts:
            - {name: data, mountPath: /var/lib/postgresql/data}
          readinessProbe:
            exec: {command: ["pg_isready", "-U", "app"]}
            periodSeconds: 5

  # ⭐ 每个 Pod 会自动创建一个属于自己的 PVC
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: standard
        resources:
          requests:
            storage: 10Gi
```

创建后：

```bash
kubectl get pods -l app=db
# db-0   Running
# db-1   Running
# db-2   Running

kubectl get pvc
# data-db-0   Bound   pvc-xxx   10Gi
# data-db-1   Bound   pvc-yyy   10Gi
# data-db-2   Bound   pvc-zzz   10Gi
#  ^^^^ PVC 名 = <volumeClaimTemplate 名>-<statefulset 名>-<序号>
```

### 4.2 稳定的网络标识

```bash
# 每个 Pod 有自己的 DNS 记录
db-0.db-headless.default.svc.cluster.local  →  10.244.1.5
db-1.db-headless.default.svc.cluster.local  →  10.244.2.7
db-2.db-headless.default.svc.cluster.local  →  10.244.3.9

# headless service 本身解析到所有 Pod IP（A 记录列表）
db-headless.default.svc.cluster.local → 10.244.1.5, 10.244.2.7, 10.244.3.9
```

**这是有状态服务的关键**：应用配置里可以写死"主库是 `db-0.db-headless`"，Pod 重建、换节点、换 IP 都不影响这个名字。

```bash
kubectl run -it --rm dnstest --image=busybox:1.37 --restart=Never -- \
  nslookup db-0.db-headless.default.svc.cluster.local
```

### 4.3 有序保证

```bash
# 启动：0 → 1 → 2（前一个 Ready 后才创建下一个）
kubectl get pods -w -l app=db

# 缩容：逆序，2 → 1 → 0
kubectl scale statefulset db --replicas=1
# db-2 先删，然后 db-1

# 注意：PVC 不会被删（默认 Retain），扩容回去时数据还在！
kubectl get pvc     # data-db-1、data-db-2 仍然存在
kubectl scale statefulset db --replicas=3   # db-1、db-2 重建，挂回原来的 PVC
```

**`podManagementPolicy: Parallel`** 让启停并行——如果你的应用不需要严格顺序（比如 Redis Cluster 各节点对等），这能把 30 个副本的启动时间从几分钟降到几秒。

### 4.4 partition：StatefulSet 的金丝雀发布

```yaml
updateStrategy:
  rollingUpdate:
    partition: 2      # 只更新序号 >= 2 的 Pod
```

5 个副本时的操作流程：

```bash
# ① 设 partition=4，只更新 db-4（一个金丝雀）
kubectl patch statefulset db -p '{"spec":{"updateStrategy":{"rollingUpdate":{"partition":4}}}}'
kubectl set image statefulset/db postgres=postgres:18-alpine
# 只有 db-4 被更新，db-0~3 保持旧版本

# ② 观察 db-4 一段时间，没问题就继续
kubectl patch statefulset db -p '{"spec":{"updateStrategy":{"rollingUpdate":{"partition":2}}}}'
# db-3、db-2 被更新

# ③ 全量
kubectl patch statefulset db -p '{"spec":{"updateStrategy":{"rollingUpdate":{"partition":0}}}}'

# 出问题？把 partition 调回去，再把 image 改回旧版本
```

### 4.5 StatefulSet 的限制（必须知道）

| 限制 | 说明 | 应对 |
|---|---|---|
| 删除 StatefulSet 不删 PVC | 默认 `Retain`，防止误删数据 | 用 `persistentVolumeClaimRetentionPolicy` 或手工清理 |
| **扩容不能改 PVC 大小** | `volumeClaimTemplates` 创建后不可变 | 手工逐个 `kubectl edit pvc` 扩容（需 StorageClass 支持 `allowVolumeExpansion`） |
| Pod 卡在 Terminating 会阻塞后续 | 有序策略的代价 | 排查根因；紧急时 `--force --grace-period=0`（⚠️ 有数据风险） |
| 没有内置的备份/failover/主从切换 | StatefulSet 只保证"身份和存储稳定" | 用 Operator，或自己实现 |
| 更新是**逆序一个一个**来的 | 30 个副本的滚动更新会很慢 | `maxUnavailable > 1`，或 `podManagementPolicy: Parallel` |

---

## 5. DaemonSet

**每个（符合条件的）节点上跑一个 Pod。** 新节点加入时自动部署，节点移除时自动清理。

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-agent
  namespace: kube-system
spec:
  selector:
    matchLabels: {app: log-agent}
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1      # 一次更新一个节点
      maxSurge: 0            # 1.25+ 支持（先起新的再删旧的，需要节点能容纳两个）
  template:
    metadata:
      labels: {app: log-agent}
    spec:
      # ⭐ 容忍所有污点，保证在控制面节点、有特殊污点的节点上也能跑
      tolerations:
        - operator: Exists
      nodeSelector:
        kubernetes.io/os: linux
      priorityClassName: system-node-critical   # 高优先级，不会被抢占驱逐
      hostNetwork: false
      containers:
        - name: agent
          image: fluent/fluent-bit:3.2
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits:   {memory: 200Mi}
          volumeMounts:
            - {name: varlog, mountPath: /var/log, readOnly: true}
            - {name: pods, mountPath: /var/log/pods, readOnly: true}
      volumes:
        - name: varlog
          hostPath: {path: /var/log}
        - name: pods
          hostPath: {path: /var/log/pods}
```

**典型用途**：日志采集（Fluent Bit / Vector）、监控（node-exporter）、网络插件（Calico/Cilium）、存储插件、安全 agent。

```bash
kubectl -n kube-system get ds
kubectl -n kube-system get pods -o wide -l app=log-agent    # 每个节点一个
```

**要点**：
- DaemonSet 的 Pod **不经过默认调度器的常规打分**（由 DaemonSet 控制器直接设 nodeName，但仍受污点/亲和性约束）
- 一定要设 `tolerations`，否则控制面节点、有污点的节点上不会部署
- 一定要设 resources，否则一个失控的 agent 能拖垮所有节点
- 用 `nodeSelector` 可以只在部分节点跑（如只在 GPU 节点跑 GPU 监控）

---

## 6. Job 与 CronJob

### 6.1 Job

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
spec:
  completions: 1              # 需要成功完成几次
  parallelism: 1              # 同时跑几个 Pod
  backoffLimit: 3             # 失败重试次数（超过则 Job 失败）
  activeDeadlineSeconds: 600  # ⭐ 总超时（含重试），超时直接终止
  ttlSecondsAfterFinished: 3600  # ⭐ 完成后 1 小时自动删除（否则会堆积）
  completionMode: NonIndexed  # 或 Indexed（每个 Pod 有 JOB_COMPLETION_INDEX）
  suspend: false              # true 则暂停（不创建 Pod）

  podFailurePolicy:           # 1.31+ 稳定：按退出码精细控制重试
    rules:
      - action: FailJob       # 退出码 42 = 不可重试的错误，直接失败整个 Job
        onExitCodes:
          containerName: migrate
          operator: In
          values: [42]
      - action: Ignore        # 被抢占导致的中断，不计入 backoffLimit
        onPodConditions:
          - type: DisruptionTarget

  template:
    spec:
      restartPolicy: OnFailure    # Job 必须是 OnFailure 或 Never
      containers:
        - name: migrate
          image: hello:v0.1.0
          command: ["/migrate", "up"]
          envFrom: [{secretRef: {name: db-credentials}}]
```

```bash
kubectl apply -f job.yaml
kubectl get job db-migrate -w
kubectl logs job/db-migrate
kubectl wait --for=condition=complete job/db-migrate --timeout=300s
kubectl delete job db-migrate
```

**并行模式**：

| 场景 | 配置 |
|---|---|
| 跑一次 | `completions: 1, parallelism: 1` |
| 固定次数、并行 | `completions: 10, parallelism: 3` |
| 工作队列（每个 Pod 自己从队列取任务，取完就退出） | 只设 `parallelism: 5`，不设 `completions` |
| 索引任务（每个 Pod 处理固定分片） | `completionMode: Indexed` + 读 `JOB_COMPLETION_INDEX` 环境变量 |

**Indexed Job 的 Go 用法**：

```go
idx, _ := strconv.Atoi(os.Getenv("JOB_COMPLETION_INDEX"))   // 0, 1, 2, ...
shard := allData[idx*shardSize : (idx+1)*shardSize]
```

⚠️ **`ttlSecondsAfterFinished` 一定要设**，否则完成的 Job 和 Pod 会一直堆在集群里，几个月后 etcd 里会有几万个对象。

### 6.2 CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-report
spec:
  schedule: "0 2 * * *"           # 标准 cron 语法
  timeZone: "Asia/Shanghai"       # ⭐ 1.27+ 稳定。不设则用控制面的时区（通常是 UTC）
  concurrencyPolicy: Forbid       # Allow | Forbid（上次没跑完就跳过）| Replace（杀掉上次的）
  startingDeadlineSeconds: 300    # 错过调度时间超过 5 分钟就跳过这次
  successfulJobsHistoryLimit: 3   # 保留几个成功的 Job
  failedJobsHistoryLimit: 3
  suspend: false
  jobTemplate:
    spec:
      backoffLimit: 2
      activeDeadlineSeconds: 3600
      ttlSecondsAfterFinished: 86400
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: report
              image: hello:v0.1.0
              command: ["/report", "--date=yesterday"]
```

```bash
kubectl get cronjob
kubectl create job --from=cronjob/nightly-report manual-run-1    # 手工触发一次
kubectl patch cronjob nightly-report -p '{"spec":{"suspend":true}}'   # 暂停
```

**CronJob 的坑**：
- **不保证精确执行时间**（控制器 10 秒轮询一次，负载高时会延迟）
- **不保证 exactly-once**：极端情况下可能跑两次或跳过。**你的任务必须幂等**
- 控制面重启期间错过的调度，超过 `startingDeadlineSeconds` 就永久跳过
- `timeZone` 不设的话是 UTC，"每天凌晨 2 点"会变成北京时间上午 10 点

---

## 7. PodDisruptionBudget：保护你的服务

**PDB 保证"自愿中断"期间至少有多少副本可用。**

两种中断：

| 类型 | 例子 | PDB 是否生效 |
|---|---|---|
| **自愿中断（voluntary）** | `kubectl drain`（节点维护）、集群升级、Cluster Autoscaler 缩容、Descheduler 重平衡 | ✅ 会被 PDB 阻挡 |
| **非自愿中断（involuntary）** | 节点硬件故障、内核 panic、OOM 驱逐、网络分区 | ❌ 无法阻挡 |

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: hello-pdb
spec:
  minAvailable: 2          # 至少保留 2 个可用
  # 或者
  # maxUnavailable: 1      # 最多同时不可用 1 个（推荐，与副本数解耦）
  selector:
    matchLabels:
      app.kubernetes.io/name: hello
  unhealthyPodEvictionPolicy: AlwaysAllow   # 1.31+：不健康的 Pod 总是允许驱逐
                                            # （否则全部不健康时会卡死无法自愈）
```

```bash
kubectl get pdb
# NAME        MIN AVAILABLE   ALLOWED DISRUPTIONS
# hello-pdb   2               1
```

**没有 PDB 的后果**：运维执行 `kubectl drain node-1`，你的 3 个副本正好都在这个节点上 → 全被驱逐 → **服务完全中断**。有了 PDB，drain 会被阻塞，直到副本在其他节点上重建完成。

**常见错误**：
- `minAvailable` 等于 `replicas` → drain 永远无法进行，节点维护卡死
- 单副本服务设 `minAvailable: 1` → 同样卡死（单副本本来就无法做到无中断，应该先扩容）
- 忘了给关键服务配 PDB → 集群升级时全线中断

第 12、21、23 章会在节点维护和集群升级中反复用到 PDB。

---

## 8. 零停机发布完整清单

这是本章的实战精华。**做到以下全部，才能真正做到滚动更新零 502**：

| # | 要点 | 配置 |
|---|---|---|
| 1 | 多副本（至少 2，推荐 3+） | `replicas: 3` |
| 2 | 副本分散在不同节点/可用区 | `topologySpreadConstraints`（第 12 章） |
| 3 | 更新期间容量不下降 | `maxSurge: 1, maxUnavailable: 0` |
| 4 | 新 Pod 有观察期 | `minReadySeconds: 10` |
| 5 | **readiness 探针正确反映"能否接流量"** | 检查依赖，快速失败 |
| 6 | **liveness 不检查外部依赖** | 只检查进程自身 |
| 7 | 慢启动用 startupProbe 保护 | 见第 7 章 |
| 8 | **preStop 留出 Endpoint 摘除窗口** | `preStop: {sleep: {seconds: 5}}` |
| 9 | **应用实现优雅退出** | 收到 SIGTERM → `srv.Shutdown()` |
| 10 | 宽限期足够长 | `terminationGracePeriodSeconds: 45` |
| 11 | PDB 保护自愿中断 | `maxUnavailable: 1` |
| 12 | 客户端有重试（幂等请求） | 应用层 |
| 13 | 数据库变更向后兼容 | **新旧版本会共存几分钟**，schema 必须双向兼容 |
| 14 | CI 检查 rollout 结果并能回滚 | `kubectl rollout status \|\| kubectl rollout undo` |

**第 13 条特别重要**：滚动更新期间，v1 和 v2 会同时在跑。如果 v2 的迁移脚本删了一个 v1 还在用的列，v1 的副本会立刻报错。正确做法是**扩展-收缩（expand-contract）模式**：

```
发布 1：加新列（可空），代码同时写新旧列，读旧列
发布 2：代码读新列
发布 3：代码不再写旧列
发布 4：删除旧列
```

---

## 9. 动手实验

### 实验 1：部署你的服务并观察三层结构

```bash
kubectl create ns lab && kubectl config set-context --current --namespace=lab

cat > ~/lab/k8s/deploy.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
spec:
  replicas: 3
  selector: {matchLabels: {app: hello}}
  minReadySeconds: 5
  strategy:
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
  template:
    metadata:
      labels: {app: hello}
    spec:
      terminationGracePeriodSeconds: 45
      containers:
        - name: server
          image: hello:v0.1.0
          imagePullPolicy: IfNotPresent
          ports: [{name: http, containerPort: 8080}]
          env:
            - {name: GREETING, value: "v1"}
            - name: POD_NAME
              valueFrom: {fieldRef: {fieldPath: metadata.name}}
          readinessProbe:
            httpGet: {path: /readyz, port: http}
            periodSeconds: 2
          livenessProbe:
            httpGet: {path: /healthz, port: http}
            periodSeconds: 10
          lifecycle:
            preStop: {sleep: {seconds: 5}}
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {memory: 256Mi}
---
apiVersion: v1
kind: Service
metadata: {name: hello}
spec:
  selector: {app: hello}
  ports: [{port: 80, targetPort: http}]
EOF

kubectl apply -f ~/lab/k8s/deploy.yaml
kubectl get deploy,rs,pods
kubectl rollout status deployment/hello
```

### 实验 2：⭐ 自愈（对比第 5 章的 Compose）

```bash
kubectl get pods -w &
kubectl delete pod -l app=hello --wait=false
# 观察：3 个 Terminating，同时 3 个新 Pod 被创建，几秒内恢复
sleep 20; kill %1
kubectl get pods
```

**对比第 5 章实验 3**：Compose 里删掉容器它不会回来，这里几秒就自愈了。

### 实验 3：⭐ 零停机滚动更新（对比第 5 章的 502）

```bash
# 起一个持续压测的 Pod
kubectl run load --image=busybox:1.37 --restart=Never -- \
  sh -c 'while true; do wget -q -T 2 -O- http://hello/ 2>/dev/null | grep -o "\"message\":\"[^\"]*\"" || echo "FAILED"; sleep 0.2; done'

kubectl logs -f load &

# 另开一个终端（或直接执行）滚动更新
kubectl set image deployment/hello server=hello:v0.1.0
kubectl set env deployment/hello GREETING=v2
kubectl rollout status deployment/hello

# 观察日志：只有 "v1" 和 "v2" 交替出现，没有 FAILED ✅
sleep 10; kill %1
kubectl logs load | grep -c FAILED      # 应该是 0
```

**这就是第 5 章那个 502 实验的正确版本。** 对比一下你就懂 Deployment 的价值了。

### 实验 4：故意破坏，观察它保护你

```bash
# 部署一个不存在的镜像
kubectl set image deployment/hello server=hello:does-not-exist
kubectl rollout status deployment/hello --timeout=60s     # 会超时失败

kubectl get pods
# 3 个旧 Pod 仍然 Running ✅
# 1 个新 Pod ImagePullBackOff
# 因为 maxUnavailable=0，新 Pod 没 Ready 就不会删旧的 —— 服务没有中断！

kubectl rollout undo deployment/hello
kubectl rollout status deployment/hello
```

**这是 `maxUnavailable: 0` 的价值**：坏版本根本上不去，服务完全不受影响。

### 实验 5：回滚

```bash
kubectl rollout history deployment/hello
kubectl set env deployment/hello GREETING=v3
kubectl rollout status deployment/hello
kubectl exec deploy/hello -- wget -qO- localhost:8080 2>/dev/null | grep message

kubectl rollout undo deployment/hello
kubectl rollout status deployment/hello
# 回到 v2
```

### 实验 6：StatefulSet 的身份与存储

```bash
cat > ~/lab/k8s/sts.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata: {name: web-headless}
spec:
  clusterIP: None
  selector: {app: web-sts}
  ports: [{port: 80}]
---
apiVersion: apps/v1
kind: StatefulSet
metadata: {name: web}
spec:
  serviceName: web-headless
  replicas: 3
  selector: {matchLabels: {app: web-sts}}
  template:
    metadata: {labels: {app: web-sts}}
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports: [{containerPort: 80}]
          command: ['sh','-c','echo "I am $HOSTNAME, my data:" > /usr/share/nginx/html/index.html; cat /data/id >> /usr/share/nginx/html/index.html 2>/dev/null || echo "$HOSTNAME-$(date +%s)" | tee /data/id >> /usr/share/nginx/html/index.html; nginx -g "daemon off;"']
          volumeMounts: [{name: data, mountPath: /data}]
  volumeClaimTemplates:
    - metadata: {name: data}
      spec:
        accessModes: ["ReadWriteOnce"]
        resources: {requests: {storage: 100Mi}}
EOF

kubectl apply -f ~/lab/k8s/sts.yaml
kubectl get pods -w -l app=web-sts    # 观察有序启动：web-0 → web-1 → web-2
# Ctrl-C

kubectl get pvc
# data-web-0  Bound
# data-web-1  Bound
# data-web-2  Bound

# 记下 web-1 的数据
kubectl exec web-1 -- cat /data/id

# 删掉它，观察：同名重建、挂回同一个 PVC、数据还在
kubectl delete pod web-1
kubectl wait --for=condition=Ready pod/web-1 --timeout=60s
kubectl exec web-1 -- cat /data/id       # ⭐ 数据一模一样！

# DNS 标识
kubectl run -it --rm dns --image=busybox:1.37 --restart=Never -- \
  nslookup web-1.web-headless.lab.svc.cluster.local
```

### 实验 7：缩容后 PVC 保留

```bash
kubectl scale statefulset web --replicas=1
kubectl get pods -l app=web-sts     # 只剩 web-0，逆序删除
kubectl get pvc                     # ⭐ 3 个 PVC 都还在！

kubectl scale statefulset web --replicas=3
kubectl wait --for=condition=Ready pod/web-2 --timeout=120s
kubectl exec web-2 -- cat /data/id  # 数据回来了
```

### 实验 8：PDB 阻止危险的 drain

```bash
cat > /tmp/pdb.yaml <<'EOF'
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: hello-pdb}
spec:
  minAvailable: 3          # 故意设成等于副本数
  selector: {matchLabels: {app: hello}}
EOF
kubectl apply -f /tmp/pdb.yaml
kubectl get pdb

NODE=$(kubectl get pod -l app=hello -o jsonpath='{.items[0].spec.nodeName}')
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=30s
# ⛔ 卡住："Cannot evict pod as it would violate the pod's disruption budget"

kubectl uncordon $NODE
kubectl patch pdb hello-pdb -p '{"spec":{"minAvailable":2}}'
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=120s   # ✅ 现在可以了
kubectl get pods -o wide                # Pod 迁移到其他节点了
kubectl uncordon $NODE
```

**这个实验同时演示了"迁移"**——`drain` 就是节点维护时把 Pod 迁走的标准手段，第 12 章会详细讲。

### 实验 9：Job 与 CronJob

```bash
kubectl create job pi --image=perl:5.40 -- perl -Mbignum=bpi -wle 'print bpi(2000)'
kubectl wait --for=condition=complete job/pi --timeout=120s
kubectl logs job/pi | head -c 200

# 失败重试
kubectl create job fail --image=busybox:1.37 -- sh -c 'exit 1'
kubectl get job fail -w      # 观察重试，backoffLimit 默认 6 次后 Failed
kubectl delete job pi fail

# CronJob 每分钟跑一次
kubectl create cronjob tick --image=busybox:1.37 --schedule="* * * * *" -- date
sleep 130
kubectl get jobs
kubectl delete cronjob tick
```

### 清理

```bash
kubectl delete ns lab
kubectl config set-context --current --namespace=default
```

---

## 10. 本章检查清单

- [ ] Deployment、ReplicaSet、Pod 的三层关系是什么？
- [ ] `maxSurge` 和 `maxUnavailable` 分别控制什么？生产推荐怎么配？为什么？
- [ ] `minReadySeconds` 解决什么问题？
- [ ] `progressDeadlineSeconds` 超时后 K8s 会自动回滚吗？
- [ ] 哪些字段变化会触发滚动更新？改 ConfigMap 会吗？
- [ ] 无状态和有状态的 6 个本质差异（身份、网络、存储、启停顺序、更新、扩缩容）
- [ ] StatefulSet 为什么必须配 headless Service？
- [ ] `db-1` 被删除后重建，还能拿到原来的数据吗？为什么？
- [ ] StatefulSet 的 `partition` 怎么做金丝雀？
- [ ] 缩容 StatefulSet 后 PVC 会被删吗？
- [ ] DaemonSet 为什么必须配 tolerations？
- [ ] Job 的 `ttlSecondsAfterFinished` 不设会有什么后果？
- [ ] CronJob 保证 exactly-once 吗？这对你的任务有什么要求？
- [ ] PDB 保护哪种中断？`minAvailable` 等于 `replicas` 会怎样？
- [ ] 默写零停机发布 14 条清单中的至少 10 条
- [ ] 完成实验 3（零停机滚动更新）和实验 6（StatefulSet 身份）

---

## 11. 延伸阅读

- [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [StatefulSet](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [StatefulSet 基础教程](https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/)
- [Job](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [PodDisruptionBudget](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)
- `pkg/controller/deployment/rolling.go`（滚动更新的真实算法）

---

下一章：[10 - Service 与网络](./10-networking.md)
