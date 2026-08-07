# 07 - Pod 详解：最小调度单元

> 本章目标：彻底回答"如何配置一个 K8s Pod、有哪些参数"。这是全课程字段最密集的一章，
> 也是最值得反复回看的一章。学完你应该能不查文档写出一个生产级的 Pod 定义，并解释每个字段的作用。
> 预计用时：3.5 小时（含实验）。

---

## 1. 为什么最小单位是 Pod 而不是容器

**Pod = 一组共享网络和存储的容器，被作为一个整体调度、启动、终止。**

回顾第 2 章：namespace 可以按需组合。Pod 的实现就是：

| namespace | Pod 内是否共享 |
|---|---|
| **NET**（IP、端口、网卡） | ✅ 共享 → 所以能用 `localhost` 互访，端口不能冲突 |
| **IPC** | ✅ 共享 |
| **UTS**（hostname） | ✅ 共享 |
| **PID** | 默认 ❌ 独立（可用 `shareProcessNamespace: true` 打开） |
| **MNT**（文件系统） | ❌ 独立 → 所以要共享文件必须挂同一个 volume |

**为什么需要这个抽象？** 因为存在一类"辅助进程"，它们必须和主进程同生共死、同机部署、共享网络或文件：

| 模式 | 例子 |
|---|---|
| **Sidecar（边车）** | 日志采集器读主容器写的文件；Istio 的 Envoy 代理接管网络；配置同步器 |
| **Ambassador（大使）** | 本地代理，主容器连 `localhost:3306`，代理负责连真正的分库分表集群 |
| **Adapter（适配器）** | 把应用的私有格式指标转换成 Prometheus 格式暴露 |

**判断标准**：这两个进程是否必须**同生共死**、**同机部署**？
- 是 → 放一个 Pod
- 否 → 拆成两个 Pod（用 Service 通信）

**常见错误**：把"应用 + 它依赖的数据库"放一个 Pod。它们不需要同生共死，也不需要同机——应该是两个独立的工作负载。

---

## 2. 一个完整的生产级 Pod（逐字段讲解）

先看全貌，后面分节展开。**建议先通读一遍，混过去也没关系，后面每节会回来讲。**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hello
  namespace: default
  labels:
    app.kubernetes.io/name: hello
    app.kubernetes.io/version: "0.1.0"
  annotations:
    kubernetes.io/change-cause: "initial deploy"
spec:
  # ============ 调度相关（第 12 章详解）============
  nodeSelector:
    kubernetes.io/os: linux
  tolerations: []
  affinity: {}
  topologySpreadConstraints: []
  priorityClassName: ""             # 优先级（抢占）
  schedulerName: default-scheduler

  # ============ 网络 ============
  hostNetwork: false                # true = 用节点网络栈（慎用）
  dnsPolicy: ClusterFirst           # 用集群 DNS
  dnsConfig:
    options:
      - name: ndots
        value: "2"                  # 重要优化，见第 10 章
  hostAliases:                      # 等价于 docker --add-host
    - ip: "10.0.0.10"
      hostnames: ["legacy.internal"]

  # ============ 安全（Pod 级，作用于所有容器）============
  securityContext:
    runAsNonRoot: true
    runAsUser: 65532
    runAsGroup: 65532
    fsGroup: 65532                  # 挂载卷的属组（第 11 章关键字段）
    fsGroupChangePolicy: OnRootMismatch
    seccompProfile:
      type: RuntimeDefault
    # hostUsers: false              # user namespace（1.36 GA），强隔离

  serviceAccountName: hello         # 身份（第 14 章）
  automountServiceAccountToken: false  # 不需要访问 API 就关掉

  # ============ 生命周期 ============
  restartPolicy: Always             # Always | OnFailure | Never
  terminationGracePeriodSeconds: 45 # SIGTERM 到 SIGKILL 的宽限期
  enableServiceLinks: false         # 关掉自动注入的 <SVC>_SERVICE_HOST 环境变量

  imagePullSecrets:
    - name: regcred

  # ============ Init 容器（顺序执行，全部成功后主容器才启动）============
  initContainers:
    - name: wait-for-db
      image: busybox:1.37
      command: ['sh', '-c', 'until nc -z db 5432; do echo waiting for db; sleep 2; done']
      resources:
        requests: {cpu: 10m, memory: 16Mi}
        limits:   {cpu: 100m, memory: 64Mi}

    # ---- 原生 Sidecar（K8s 1.33 GA）：initContainer + restartPolicy: Always ----
    - name: log-shipper
      image: fluent/fluent-bit:3.2
      restartPolicy: Always         # ← 这一行让它变成 sidecar：
                                    #   先于主容器启动、贯穿整个 Pod 生命周期、晚于主容器终止
      volumeMounts:
        - name: applogs
          mountPath: /var/log/app
      resources:
        requests: {cpu: 20m, memory: 32Mi}
        limits:   {memory: 128Mi}

  # ============ 主容器 ============
  containers:
    - name: server
      image: localhost:5001/hello:v0.1.0
      imagePullPolicy: IfNotPresent

      command: ["/server"]          # 覆盖镜像 ENTRYPOINT
      args: ["--config=/etc/app/config.yaml"]   # 覆盖镜像 CMD

      ports:
        - name: http                # 命名端口，Service 可以按名字引用
          containerPort: 8080
          protocol: TCP
        - name: metrics
          containerPort: 9090

      env:
        - name: PORT
          value: "8080"
        - name: LOG_LEVEL
          value: "info"
        - name: POD_NAME            # Downward API：拿自己的元数据
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        - name: POD_IP
          valueFrom:
            fieldRef:
              fieldPath: status.podIP
        - name: GOMAXPROCS          # 从 CPU limit 自动推导（向上取整）
          valueFrom:
            resourceFieldRef:
              containerName: server
              resource: limits.cpu
        - name: GOMEMLIMIT          # 从内存 limit 推导（这里给的是字节数）
          valueFrom:
            resourceFieldRef:
              containerName: server
              resource: limits.memory
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: password

      envFrom:                      # 批量导入
        - configMapRef:
            name: hello-config
        - secretRef:
            name: hello-secrets

      resources:
        requests:                   # 调度依据 + QoS 依据
          cpu: 100m
          memory: 128Mi
          ephemeral-storage: 100Mi
        limits:                     # 运行时硬上限
          cpu: "1"
          memory: 512Mi
          ephemeral-storage: 1Gi

      # ============ 三种探针 ============
      startupProbe:                 # 启动探针：慢启动应用的保护伞
        httpGet: {path: /healthz, port: http}
        periodSeconds: 5
        failureThreshold: 60        # 最多容忍 5×60 = 300 秒启动时间

      livenessProbe:                # 存活：失败 → 重启容器
        httpGet: {path: /healthz, port: http}
        periodSeconds: 10
        timeoutSeconds: 3
        failureThreshold: 3

      readinessProbe:               # 就绪：失败 → 从 Service 摘掉（不重启）
        httpGet: {path: /readyz, port: http}
        periodSeconds: 5
        timeoutSeconds: 2
        failureThreshold: 2
        successThreshold: 1

      lifecycle:
        preStop:                    # 容器被终止前执行（与 SIGTERM 配合，见 §7）
          sleep:
            seconds: 5              # K8s 1.30+ 原生 sleep，无需容器里有 sh

      securityContext:              # 容器级（覆盖 Pod 级）
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]

      volumeMounts:
        - name: config
          mountPath: /etc/app
          readOnly: true
        - name: tmp
          mountPath: /tmp
        - name: applogs
          mountPath: /var/log/app
        - name: data
          mountPath: /var/lib/app

  # ============ 卷定义 ============
  volumes:
    - name: config
      configMap:
        name: hello-config
        items:
          - key: config.yaml
            path: config.yaml
    - name: tmp
      emptyDir:
        medium: Memory
        sizeLimit: 64Mi
    - name: applogs
      emptyDir: {}
    - name: data
      persistentVolumeClaim:
        claimName: hello-data
```

**别被吓到。** 90% 的日常工作只用到其中 20% 的字段。但每个字段都是某个生产事故的产物，你迟早会用到。

---

## 3. Pod 的生命周期

### 3.1 Phase（阶段）

```bash
kubectl get pod hello -o jsonpath='{.status.phase}'
```

| Phase | 含义 |
|---|---|
| `Pending` | 已被 API Server 接受，但还没在节点上跑起来（等调度 / 拉镜像 / 挂卷） |
| `Running` | 已绑定节点，**至少一个**容器在运行 |
| `Succeeded` | 所有容器成功退出（exit 0），且不会重启 |
| `Failed` | 所有容器终止，**至少一个**失败退出 |
| `Unknown` | 无法获取状态（通常是节点失联） |

⚠️ **`Running` 不代表"可用"！** 判断可用要看 `Ready` 条件（readiness 探针的结果）。

### 3.2 Conditions（更精细的状态）

```bash
kubectl get pod hello -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}'
# PodScheduled=True Initialized=True ContainersReady=True Ready=True
```

| Condition | 含义 |
|---|---|
| `PodScheduled` | 已被分配到节点 |
| `PodReadyToStartContainers` | 网络和卷已就绪 |
| `Initialized` | 所有 init 容器成功完成 |
| `ContainersReady` | 所有容器都 Ready |
| `Ready` | Pod 可以接收流量（= ContainersReady + 所有 readinessGate 通过） |
| `DisruptionTarget` | Pod 即将被驱逐（抢占、节点压力、drain） |

### 3.3 完整启动流程

```
API Server 接受 Pod（Pending）
   │
   ▼ Scheduler 分配节点 → spec.nodeName（PodScheduled=True）
   │
   ▼ kubelet 发现"这是我的 Pod"
   │
   ├─► 创建 sandbox（pause 容器）→ CNI 分配 IP
   ├─► CSI 挂载卷（fsGroup 生效）
   │
   ▼ 顺序执行 initContainers（一个成功才跑下一个）
   │    ├─ restartPolicy: Always 的 init 容器（sidecar）启动后即视为"完成"，继续下一个
   │    └─ 普通 init 容器必须退出 0
   │   （Initialized=True）
   │
   ▼ 并行启动所有 containers
   │    ├─► postStart hook（如果有）
   │    ├─► startupProbe 通过前，liveness/readiness 不生效
   │    ├─► startupProbe 成功 → liveness + readiness 开始工作
   │    └─► readinessProbe 成功 → Pod IP 加入 Service Endpoints（Ready=True）
   │
   ▼ Running，开始接流量
```

### 3.4 容器重启：指数退避

容器崩溃时，kubelet 按 **10s → 20s → 40s → 80s → 160s → 300s（封顶 5 分钟）** 重启。
连续 10 分钟正常运行后，退避计数重置。

`CrashLoopBackOff` 就是"正在退避等待中"的状态。**它不是错误原因，只是现象**——真正的原因要看日志：

```bash
kubectl logs <pod> --previous     # 看崩溃前那次的日志（关键！）
```

### 3.5 restartPolicy

| 值 | 语义 | 适用 |
|---|---|---|
| `Always`（默认） | 容器退出（无论 0 还是非 0）都重启 | 长期服务 |
| `OnFailure` | 只有非 0 退出才重启 | Job |
| `Never` | 从不重启 | 一次性任务、调试 |

**注意**：`restartPolicy` 是 Pod 级的，作用于**容器重启**，不是"Pod 重启"。Pod 本身从来不会"重启"——它要么活着，要么被删除后由控制器重建（新 Pod、新名字、新 IP）。

---

## 4. 探针：三种，用途完全不同

这是**最容易配错、后果最严重**的部分。

### 4.1 三种探针的职责

| 探针 | 失败后果 | 该检查什么 | 绝不能检查什么 |
|---|---|---|---|
| **livenessProbe** | **重启容器** | 进程是否卡死（死锁、goroutine 泄漏到无响应） | ❌ 数据库、下游服务、任何外部依赖 |
| **readinessProbe** | **从 Service 摘除流量**（不重启） | 现在能不能正确处理请求（含依赖是否可用） | — |
| **startupProbe** | 重启容器 | 慢启动应用是否完成初始化 | — |

### 4.2 为什么 liveness 绝不能检查数据库

```go
// ❌ 灾难写法
mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
    if err := db.Ping(); err != nil {
        http.Error(w, "db down", 500)     // liveness 失败 → 容器被重启
        return
    }
    w.Write([]byte("ok"))
})
```

数据库抖动 5 秒 → **所有 50 个 API 副本的 liveness 同时失败** → 全部重启 → 重启后一起冲击数据库 → 数据库更慢 → 再次全部重启 → **雪崩，服务永久不可用**。

正确的分工：

```go
// liveness：只证明"进程还能响应 HTTP"
mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("ok"))
})

// readiness：依赖不可用时摘流量，但不重启。依赖恢复后自动重新加回
mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
    ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
    defer cancel()
    if err := db.PingContext(ctx); err != nil {
        http.Error(w, "db not ready", http.StatusServiceUnavailable)
        return
    }
    w.Write([]byte("ready"))
})
```

> **进阶思考**：如果所有副本的 readiness 都失败，Service 后端为空，请求直接失败——这也不理想。
> 更成熟的做法是"降级而非摘除"：依赖不可用时返回降级响应而不是让 readiness 失败。
> 具体取舍看业务，但**liveness 检查外部依赖永远是错的**。

### 4.3 四种探测方式

```yaml
# ① HTTP GET（最常用）
livenessProbe:
  httpGet:
    path: /healthz
    port: http                  # 可以用端口名
    scheme: HTTP                # 或 HTTPS
    httpHeaders:
      - name: X-Probe
        value: kubelet
# 判定：状态码 200-399 = 成功

# ② TCP Socket（非 HTTP 服务，如 gRPC 老版本、数据库）
livenessProbe:
  tcpSocket:
    port: 5432
# 判定：能建立 TCP 连接 = 成功。注意：只能证明端口在听，不能证明服务正常

# ③ gRPC（K8s 1.27 GA，需要服务实现 grpc.health.v1.Health）
livenessProbe:
  grpc:
    port: 9000
    service: ""                 # 空字符串 = 检查整体健康

# ④ Exec（在容器里执行命令，开销最大）
livenessProbe:
  exec:
    command: ["/bin/sh", "-c", "pg_isready -U app"]
# 判定：退出码 0 = 成功。注意：distroless 镜像没有 shell，用不了
```

**gRPC 服务的 Go 实现**：

```go
import (
    "google.golang.org/grpc/health"
    healthpb "google.golang.org/grpc/health/grpc_health_v1"
)

hs := health.NewServer()
healthpb.RegisterHealthServer(grpcServer, hs)
hs.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)
// 优雅退出时：hs.SetServingStatus("", healthpb.HealthCheckResponse_NOT_SERVING)
```

### 4.4 探针参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `initialDelaySeconds` | 0 | 容器启动后等多久开始探测（**有 startupProbe 时不需要它**） |
| `periodSeconds` | 10 | 探测间隔 |
| `timeoutSeconds` | 1 | 单次探测超时（**默认 1 秒经常太短**，Go 服务 GC 停顿都可能超） |
| `successThreshold` | 1 | 连续几次成功算成功（liveness/startup 只能是 1） |
| `failureThreshold` | 3 | 连续几次失败算失败 |
| `terminationGracePeriodSeconds` | 继承 Pod | liveness 失败杀容器时的宽限期（可单独设，1.28+） |

**最坏检测时间** = `periodSeconds × failureThreshold + timeoutSeconds`

### 4.5 startupProbe 解决什么问题

假设你的服务要 2 分钟才能启动（加载大模型、预热缓存、跑数据库迁移）：

```yaml
# ❌ 没有 startupProbe：为了让慢启动不被误杀，只能把 liveness 调得很宽松
livenessProbe:
  initialDelaySeconds: 150      # 等 150 秒才开始检查
  periodSeconds: 10
  failureThreshold: 3
# 副作用：运行期间真的卡死了，要 150+30 秒才能发现 ❌

# ✅ 用 startupProbe 把"启动期"和"运行期"分开
startupProbe:
  httpGet: {path: /healthz, port: http}
  periodSeconds: 5
  failureThreshold: 30          # 最多容忍 150 秒启动
livenessProbe:
  httpGet: {path: /healthz, port: http}
  periodSeconds: 10
  failureThreshold: 3           # 运行期 30 秒内发现卡死 ✅
```

**规则**：startupProbe 成功之前，liveness 和 readiness **完全不执行**。

### 4.6 探针配置的常见错误

| 错误 | 后果 |
|---|---|
| liveness 检查依赖 | 依赖抖动 → 全体重启 → 雪崩 |
| `timeoutSeconds: 1`（默认）+ 探针端点有 IO | 偶发超时 → 无故重启 |
| readiness 和 liveness 用同一个重量级端点 | 探测本身成为负载 |
| 没有 readiness | 滚动更新时新 Pod 还没准备好就接流量 → 502 |
| 探针端点需要认证 | 探测永远失败 |
| 探针端点会写日志 | 日志被健康检查刷屏（每 10 秒 ×N 副本） |
| liveness 的 `failureThreshold` 太小 | 一次 GC 停顿就重启 |

---

## 5. 资源：requests、limits 与 QoS

### 5.1 requests vs limits

| | requests | limits |
|---|---|---|
| 作用 | **调度依据**：调度器找一个"剩余 allocatable ≥ requests"的节点 | **运行时上限**：cgroup 的硬限制 |
| CPU 超了 | 无事（可以超用空闲 CPU） | **被节流**（throttling），延迟飙升 |
| 内存超了 | 无事（但节点压力大时优先被驱逐） | **OOMKill**（退出码 137） |

**关键理解**：调度只看 requests！节点上所有 Pod 的 **requests 之和**不能超过节点 allocatable，但 **limits 之和可以远超**（超卖）。

### 5.2 单位

```yaml
resources:
  requests:
    cpu: 100m          # 100 millicore = 0.1 核。1 = 1000m = 一个核的时间片
    memory: 128Mi      # Mi=1024^2, M=1000^2。永远用 Mi/Gi，别用 M/G
    ephemeral-storage: 1Gi   # 容器可写层 + emptyDir + 日志的磁盘配额
  limits:
    cpu: "1"
    memory: 512Mi
```

### 5.3 QoS 等级（决定内存不足时谁先死）

kubelet 根据 requests/limits 自动给 Pod 分级：

| QoS | 条件 | 被驱逐顺序 | 适用 |
|---|---|---|---|
| **Guaranteed** | 每个容器的 requests == limits（CPU 和内存都是） | 最后 | 数据库、关键服务 |
| **Burstable** | 至少设了 requests，但不满足 Guaranteed | 中间 | **大多数业务服务** |
| **BestEffort** | 完全没设 requests 和 limits | **最先被杀** | 不要在生产用 |

```bash
kubectl get pod hello -o jsonpath='{.status.qosClass}'
```

节点内存不足时，kubelet 按 `BestEffort → Burstable（超出 requests 越多越先死）→ Guaranteed` 的顺序驱逐。

### 5.4 该怎么配（实践建议）

```yaml
resources:
  requests:
    cpu: 100m           # 按 P50 实际用量设，宁可略低（调度密度）
    memory: 256Mi       # 按 P95~P99 实际用量设
  limits:
    # cpu: 不设！        ← 见下面的争议
    memory: 512Mi       # 设为 requests 的 1.5~2 倍
```

**争议点：要不要设 CPU limit？**

| 观点 | 理由 |
|---|---|
| **不设 CPU limit**（很多大厂的做法） | CPU 是可压缩资源。设了 limit 会导致**节流**：即使节点 CPU 空闲，你的 Pod 也用不了，突发流量下 P99 延迟严重恶化。只设 requests 就能保证最低份额，空闲时还能超用 |
| **设 CPU limit** | 防止某个 Pod 的 bug（死循环）拖垮整个节点；多租户环境下需要确定性；成本核算清晰 |

**折中建议**：
- 延迟敏感的在线服务：**不设 CPU limit**，只设 requests（配合监控和 LimitRange 兜底）
- 批处理、离线任务、不可信负载：**设 CPU limit**
- **内存 limit 永远要设**（内存是不可压缩资源，一个泄漏的 Pod 能拖垮整个节点）

**如何验证是否被节流**：

```bash
kubectl exec <pod> -- cat /sys/fs/cgroup/cpu.stat
# nr_throttled 和 throttled_usec 持续增长 = 正在被节流
```
Prometheus 指标：`container_cpu_cfs_throttled_seconds_total`。

### 5.5 Go 服务的资源配置（重点）

```yaml
env:
  # Go 1.25+ 已能自动感知 cgroup CPU limit；早期版本或想要确定性时显式设置
  - name: GOMAXPROCS
    valueFrom:
      resourceFieldRef:
        resource: limits.cpu       # 自动向上取整；没设 limit 时会拿到节点核数（注意！）
  - name: GOMEMLIMIT
    valueFrom:
      resourceFieldRef:
        resource: limits.memory    # 得到字节数，如 536870912
        divisor: "1"
resources:
  requests: {cpu: 200m, memory: 256Mi}
  limits:   {memory: 512Mi}
```

⚠️ 上面的 `GOMEMLIMIT` 直接等于 limit 是**危险的**——堆达到 limit 时 GC 才发力，但此时已经 OOM 了。更好的做法：

```yaml
- name: GOMEMLIMIT
  value: "450MiB"          # 手工设为 limit(512Mi) 的 ~85%
```

或者在 Go 代码里读 limit 自己算：

```go
// 从 cgroup v2 读容器内存上限，取 85% 作为 GOMEMLIMIT
if b, err := os.ReadFile("/sys/fs/cgroup/memory.max"); err == nil {
    if v, err := strconv.ParseInt(strings.TrimSpace(string(b)), 10, 64); err == nil {
        debug.SetMemoryLimit(int64(float64(v) * 0.85))
    }
}
// 也可以直接用 github.com/KimMachineGun/automemlimit
```

**没设 CPU limit 时 `resourceFieldRef: limits.cpu` 会拿到节点的总核数**——64 核节点上你的小服务会开 64 个 P。所以不设 CPU limit 时，请用 `automaxprocs` 库（它读 cgroup 配额，没配额时保持默认）。

### 5.6 原地扩缩容（In-Place Pod Resize，K8s 1.35 GA）

传统上改 `resources` 会重建 Pod。1.35 起可以**原地调整**，不重启容器：

```bash
kubectl patch pod hello --subresource resize --patch \
  '{"spec":{"containers":[{"name":"server","resources":{"requests":{"cpu":"500m"},"limits":{"cpu":"1"}}}]}}'

kubectl get pod hello -o jsonpath='{.status.conditions}' | jq
# 关注 PodResizePending / PodResizeInProgress
```

配合 `resizePolicy` 声明每种资源改变时是否需要重启：

```yaml
containers:
  - name: server
    resizePolicy:
      - resourceName: cpu
        restartPolicy: NotRequired    # CPU 变更不重启
      - resourceName: memory
        restartPolicy: RestartContainer  # 内存变更需要重启（因为 GOMEMLIMIT 等要重读）
```

这对有状态服务意义重大——以前给数据库扩内存必须重启，现在可以在线做。

> K8s 1.36 进一步支持了 **Pod 级资源**（`spec.resources`，容器共享一个总配额）及其原地调整。

---

## 6. Init 容器与 Sidecar

### 6.1 Init 容器

- **顺序**执行，前一个成功退出后才跑下一个
- 全部完成后主容器才启动
- 失败会按 `restartPolicy` 重试整个 init 序列
- 可以有独立的镜像和权限（**常用来做需要高权限的准备工作，让主容器保持最小权限**）

典型用途：

```yaml
initContainers:
  # 等待依赖就绪
  - name: wait-for-db
    image: busybox:1.37
    command: ['sh','-c','until nc -z db 5432; do sleep 2; done']

  # 跑数据库迁移（注意：多副本时会并发执行，迁移工具必须幂等且带锁！）
  - name: migrate
    image: myapp:v1
    command: ["/migrate", "up"]
    envFrom: [{secretRef: {name: db-credentials}}]

  # 修正卷权限（需要 root，但主容器仍是非 root）
  - name: fix-perms
    image: busybox:1.37
    command: ['sh','-c','chown -R 65532:65532 /data']
    securityContext: {runAsUser: 0}
    volumeMounts: [{name: data, mountPath: /data}]
```

> **数据库迁移的正确姿势**：放 initContainer 在多副本时会并发执行。更好的方案是用独立的
> Job（Helm 的 pre-upgrade hook / Argo CD 的 PreSync hook，第 15、18 章），或者让迁移工具
> 自己用数据库咨询锁（`pg_advisory_lock`）保证串行。

### 6.2 原生 Sidecar（1.33 GA，重要特性）

在 1.29 之前，sidecar 只能作为普通容器放在 `containers` 里，导致三个老问题：

1. **启动顺序不保证**：主容器可能先启动，此时 Envoy 代理还没就绪 → 连接失败
2. **Job 永远不结束**：主容器跑完退出了，但 sidecar 还在跑，Pod 永远不 Complete
3. **终止顺序不保证**：日志采集器可能先死，主容器最后那批日志丢失

**原生 sidecar 用 `initContainers` + `restartPolicy: Always` 解决了全部三个问题**：

```yaml
initContainers:
  - name: envoy-proxy
    image: envoyproxy/envoy:v1.35
    restartPolicy: Always       # ← 关键
```

语义变成：

| 特性 | 普通 container | 原生 sidecar |
|---|---|---|
| 启动时机 | 与其他容器并行 | **在主容器之前**启动完成 |
| 终止时机 | 与其他容器并行 | **在所有主容器终止之后**才终止 |
| 退出后 | 按 Pod restartPolicy | **总是重启**（即使 Pod 是 Job） |
| 对 Job 完成的影响 | 阻止 Job 完成 ❌ | 不阻止 ✅ |

**这是近几年 Pod 层面最重要的改进**，Istio、日志采集、指标代理都受益。

---

## 7. 优雅终止：完整流程（生产必修）

第 4 章讲了单机的信号处理，这里是 K8s 的完整版。

### 7.1 删除 Pod 时发生了什么

```
kubectl delete pod / 滚动更新 / 驱逐
   │
   ├──────────────────────┬───────────────────────────────┐
   │                      │  ⚠️ 以下两条是并发的，没有顺序保证 │
   ▼                      ▼                               │
① Pod 标记为 Terminating   ② Endpoint 控制器把 Pod IP        │
   （deletionTimestamp）       从 EndpointSlice 移除          │
   │                          │                            │
   │                          ▼                            │
   │                       kube-proxy 更新每个节点的           │
   │                       iptables/IPVS 规则（有延迟！）      │
   ▼                                                       │
③ 执行 preStop hook（如果有）—— 阻塞式，计入宽限期               │
   │                                                       │
   ▼                                                       │
④ 给容器 PID 1 发 SIGTERM                                    │
   │                                                       │
   ▼ 等待 terminationGracePeriodSeconds（默认 30s）            │
   │                                                       │
⑤ 还没退出 → SIGKILL 强杀                                     │
   │                                                       │
   ▼                                                       │
⑥ 原生 sidecar 此时才收到 SIGTERM                             │
   │                                                       │
   ▼                                                       │
⑦ 从 API Server 删除对象                                      │
```

**②的延迟是丢请求的根源**：iptables 规则更新要跨所有节点传播，在大集群可能要几秒。如果你的进程收到 SIGTERM 立刻关闭监听，这几秒内到达的请求就会被 connection refused。

### 7.2 正确配置

```yaml
spec:
  terminationGracePeriodSeconds: 45     # 要 > preStop + 最长请求处理时间
  containers:
    - name: server
      lifecycle:
        preStop:
          sleep:
            seconds: 5     # K8s 1.30+ 原生 sleep（不需要容器里有 shell，distroless 友好）
            # 老版本写法：exec: {command: ["/bin/sh","-c","sleep 5"]}
```

**`preStop: sleep 5` 的作用**：给 Endpoint 摘除和 iptables 更新留出时间窗口。这 5 秒里 Pod 仍在正常服务，但已经在被摘除的过程中。

配合应用侧：

```go
<-ctx.Done()                                // 收到 SIGTERM
slog.Info("SIGTERM received, draining")
srv.Shutdown(ctxWithTimeout(30*time.Second)) // 停止接受新连接，等存量请求完成
```

**时间预算示例**（`terminationGracePeriodSeconds: 45`）：
```
0s   ─ preStop 开始 sleep(5)，同时 Endpoint 摘除在进行
5s   ─ preStop 结束，SIGTERM 发出
5s   ─ 应用开始 graceful shutdown，最长等 30 秒处理存量请求
35s  ─ 应用正常退出（理想情况）
45s  ─ 若还没退出，SIGKILL
```

### 7.3 长连接的额外处理

WebSocket、gRPC 流、SSE 这类长连接不会自己断开：

```go
// gRPC
grpcServer.GracefulStop()   // 停止接受新连接，等已有 RPC 完成

// HTTP/2 & WebSocket：主动通知客户端重连
srv.RegisterOnShutdown(func() { closeAllWebsockets() })

// HTTP/1.1 keep-alive：Shutdown 会等空闲连接关闭，
// 但活跃连接要等请求结束。设置合理的 Server.IdleTimeout 很重要
```

---

## 8. Pod 级网络配置

```yaml
spec:
  hostNetwork: false      # true：用节点网络栈，Pod IP = 节点 IP，端口直接占用节点端口
  hostPID: false          # true：能看到节点上所有进程（监控/调试 agent 用）
  hostIPC: false

  dnsPolicy: ClusterFirst
  # ClusterFirst              默认，用集群 DNS（CoreDNS），解析不了的转发到上游
  # ClusterFirstWithHostNet   hostNetwork=true 时想用集群 DNS 必须显式设这个
  # Default                   继承节点的 /etc/resolv.conf（不用集群 DNS）
  # None                      完全自定义，必须配 dnsConfig

  dnsConfig:
    nameservers: ["10.96.0.10"]
    searches: ["mysvc.default.svc.cluster.local"]
    options:
      - name: ndots
        value: "2"          # 见第 10 章，这是重要的 DNS 性能优化

  hostAliases:              # 写进 /etc/hosts
    - ip: "10.0.0.10"
      hostnames: ["legacy.internal"]

  enableServiceLinks: false # 默认 true：把所有 Service 注入成环境变量
                            # 集群 Service 一多，环境变量爆炸，建议关掉
```

**容器里的端口配置**：

```yaml
ports:
  - name: http              # 名字 ≤ 15 字符，Service 可以按名引用（解耦端口号）
    containerPort: 8080
    protocol: TCP
    # hostPort: 8080        # ⚠️ 直接占用节点端口，破坏调度灵活性（一个节点只能跑一个副本），慎用
```

⚠️ **`containerPort` 是纯声明性的**（跟 Dockerfile 的 `EXPOSE` 一样）——不写它，容器监听的端口照样能被访问。写它的价值是：文档、`kubectl describe` 可见、Service 可以用 `targetPort: http` 按名引用。

---

## 9. securityContext：Pod 级 vs 容器级

```yaml
spec:
  securityContext:                    # Pod 级：作用于所有容器 + 卷
    runAsNonRoot: true                # 镜像里 USER 是 root 就拒绝启动
    runAsUser: 65532
    runAsGroup: 65532
    fsGroup: 65532                    # 挂载卷的属组（只对支持的卷类型生效）
    fsGroupChangePolicy: OnRootMismatch   # 大卷时避免每次启动都递归 chown（很慢）
    supplementalGroups: [1000]
    seccompProfile:
      type: RuntimeDefault            # 用运行时的默认 seccomp（应当默认开启）
    sysctls:
      - name: net.core.somaxconn      # 只有"安全的" sysctl 可以设
        value: "1024"
    # hostUsers: false                # user namespace（1.36 GA）

  containers:
    - name: server
      securityContext:                # 容器级：覆盖 Pod 级
        allowPrivilegeEscalation: false   # 禁止 setuid 提权
        readOnlyRootFilesystem: true      # 根文件系统只读
        privileged: false                 # 绝不要开
        capabilities:
          drop: ["ALL"]
          # add: ["NET_BIND_SERVICE"]     # 需要监听 <1024 端口时（更好的做法是监听高位端口）
```

**生产基线**（第 14 章会讲怎么用 Pod Security Admission 强制）：

```yaml
runAsNonRoot: true
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities: {drop: ["ALL"]}
seccompProfile: {type: RuntimeDefault}
```

---

## 10. 日常操作命令

```bash
# 创建与查看
kubectl apply -f pod.yaml
kubectl get pods -o wide                    # 看 IP 和所在节点
kubectl get pod hello -o yaml               # 完整对象（含 status）
kubectl describe pod hello                  # ⭐ 最有用：事件、状态、探针结果、挂载

# 日志
kubectl logs hello                          # 单容器
kubectl logs hello -c server                # 指定容器
kubectl logs hello --previous               # ⭐ 崩溃前那次的日志
kubectl logs hello -f --tail=100 --timestamps
kubectl logs -l app=hello --all-containers --max-log-requests=10   # 按标签聚合
stern hello                                 # 更好用的多 Pod 日志（第 13 章）

# 调试
kubectl exec -it hello -- sh
kubectl exec hello -c server -- env
kubectl debug -it hello --image=nicolaka/netshoot --target=server   # ⭐ distroless 救星
kubectl debug node/learn-worker -it --image=busybox                 # 调试节点

# 网络
kubectl port-forward pod/hello 8080:8080
kubectl port-forward svc/hello 8080:80

# 文件
kubectl cp hello:/etc/app/config.yaml ./config.yaml
kubectl cp ./local.txt hello:/tmp/local.txt

# 资源
kubectl top pod hello --containers
kubectl get pod hello -o jsonpath='{.status.qosClass}'

# 删除
kubectl delete pod hello
kubectl delete pod hello --grace-period=0 --force    # ⚠️ 强删，可能导致数据损坏，最后手段

# 生成模板（不记得字段时的救命稻草）
kubectl run tmp --image=nginx --dry-run=client -o yaml
kubectl create deployment x --image=nginx --dry-run=client -o yaml
kubectl explain pod.spec.containers.livenessProbe --recursive
```

---

## 11. 动手实验

### 实验 1：部署第 3 章的 Go 服务

```bash
cd ~/lab/hello
docker build -t hello:v0.1.0 .
kind load docker-image hello:v0.1.0 --name learn
```

`~/lab/k8s/pod.yaml`：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hello
  labels: {app: hello}
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 65532
    seccompProfile: {type: RuntimeDefault}
  terminationGracePeriodSeconds: 45
  containers:
    - name: server
      image: hello:v0.1.0
      imagePullPolicy: IfNotPresent
      ports:
        - {name: http, containerPort: 8080}
      env:
        - {name: GREETING, value: "hello from k8s"}
        - name: POD_NAME
          valueFrom: {fieldRef: {fieldPath: metadata.name}}
        - name: NODE_NAME
          valueFrom: {fieldRef: {fieldPath: spec.nodeName}}
      resources:
        requests: {cpu: 100m, memory: 64Mi}
        limits:   {memory: 256Mi}
      startupProbe:
        httpGet: {path: /healthz, port: http}
        periodSeconds: 2
        failureThreshold: 30
      livenessProbe:
        httpGet: {path: /healthz, port: http}
        periodSeconds: 10
        timeoutSeconds: 3
      readinessProbe:
        httpGet: {path: /readyz, port: http}
        periodSeconds: 5
        timeoutSeconds: 2
      lifecycle:
        preStop: {sleep: {seconds: 5}}
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities: {drop: ["ALL"]}
      volumeMounts:
        - {name: tmp, mountPath: /tmp}
  volumes:
    - name: tmp
      emptyDir: {medium: Memory, sizeLimit: 32Mi}
```

```bash
kubectl apply -f ~/lab/k8s/pod.yaml
kubectl get pod hello -w
kubectl describe pod hello | tail -25        # 看 Events
kubectl port-forward pod/hello 8080:8080 &
curl -s localhost:8080 | jq
kill %1
```

### 实验 2：观察探针行为

```bash
# 让 readiness 失败，观察 Ready 变 False 但容器不重启
kubectl exec hello -- sh 2>/dev/null || echo "distroless 没有 shell，改用下面的方法"

# 换个办法：改探针路径到一个不存在的端点
kubectl patch pod hello --type=json \
  -p='[{"op":"replace","path":"/spec/containers/0/readinessProbe/httpGet/path","value":"/nope"}]' \
  2>&1 | head -2
# Pod 的探针字段是不可变的！会报错 —— 这本身就是重要一课：
# Pod 的绝大部分字段创建后不能改，要改必须重建。所以我们才需要 Deployment（第 9 章）
```

改成用 Deployment 做这个实验（第 9 章会做）。这里先记住：**Pod 是不可变的**（只有 image、resources 等极少数字段可改）。

### 实验 3：QoS 分级

```bash
# BestEffort
kubectl run be --image=nginx:alpine
kubectl get pod be -o jsonpath='{.status.qosClass}{"\n"}'      # BestEffort

# Burstable
kubectl run bu --image=nginx:alpine --overrides='
{"spec":{"containers":[{"name":"bu","image":"nginx:alpine",
"resources":{"requests":{"cpu":"50m","memory":"64Mi"},"limits":{"memory":"128Mi"}}}]}}'
kubectl get pod bu -o jsonpath='{.status.qosClass}{"\n"}'      # Burstable

# Guaranteed
kubectl run gu --image=nginx:alpine --overrides='
{"spec":{"containers":[{"name":"gu","image":"nginx:alpine",
"resources":{"requests":{"cpu":"100m","memory":"128Mi"},"limits":{"cpu":"100m","memory":"128Mi"}}}]}}'
kubectl get pod gu -o jsonpath='{.status.qosClass}{"\n"}'      # Guaranteed

kubectl delete pod be bu gu
```

### 实验 4：制造 OOMKilled

```bash
kubectl run oom --image=polinux/stress --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"oom","image":"polinux/stress",
"command":["stress","--vm","1","--vm-bytes","250M","--vm-hang","1"],
"resources":{"limits":{"memory":"100Mi"}}}]}}'

sleep 15
kubectl get pod oom
kubectl describe pod oom | grep -A3 "Last State"
# Last State: Terminated
#   Reason: OOMKilled
#   Exit Code: 137
kubectl delete pod oom
```

### 实验 5：CPU 节流

```bash
kubectl run throttle --image=busybox --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"t","image":"busybox",
"command":["sh","-c","while true; do :; done"],
"resources":{"limits":{"cpu":"100m"}}}]}}'

sleep 20
kubectl exec throttle -- cat /sys/fs/cgroup/cpu.stat
# nr_throttled 和 throttled_usec 在快速增长 ← 这就是节流
kubectl delete pod throttle
```

### 实验 6：原生 Sidecar

```yaml
# ~/lab/k8s/sidecar.yaml
apiVersion: v1
kind: Pod
metadata: {name: sidecar-demo}
spec:
  restartPolicy: Never
  initContainers:
    - name: log-tailer
      image: busybox:1.37
      restartPolicy: Always              # ← 原生 sidecar
      command: ['sh','-c','tail -F /shared/app.log 2>/dev/null || sleep 3600']
      volumeMounts: [{name: shared, mountPath: /shared}]
  containers:
    - name: app
      image: busybox:1.37
      command: ['sh','-c','for i in 1 2 3 4 5; do echo "log line $i" >> /shared/app.log; sleep 2; done; echo done']
      volumeMounts: [{name: shared, mountPath: /shared}]
  volumes:
    - name: shared
      emptyDir: {}
```

```bash
kubectl apply -f ~/lab/k8s/sidecar.yaml
kubectl logs -f sidecar-demo -c log-tailer &
sleep 15
kubectl get pod sidecar-demo
# STATUS: Completed  ← sidecar 没有阻止 Pod 完成！这就是原生 sidecar 的价值
kill %1; kubectl delete pod sidecar-demo
```

### 实验 7：优雅终止

```bash
kubectl apply -f ~/lab/k8s/pod.yaml
kubectl logs -f hello &
time kubectl delete pod hello
# 观察：
#   ① delete 命令要 ~10 秒返回（preStop 5s + 应用退出）
#   ② 日志里有 "shutdown signal received, draining..." 和 "bye"
kill %1
```

对比不优雅的：把 `preStop` 去掉、`terminationGracePeriodSeconds` 设成 1，再删一次，观察日志被截断。

---

## 12. 本章检查清单

- [ ] Pod 内容器共享哪些 namespace？哪些不共享？这决定了什么？
- [ ] 什么情况下两个进程该放同一个 Pod？判断标准是什么？
- [ ] Pod 的 5 个 phase 和 6 个 condition 分别是什么？`Running` 等于可用吗？
- [ ] liveness、readiness、startup 三种探针的职责和失败后果分别是什么？
- [ ] 为什么 liveness 探针绝对不能检查数据库？描述雪崩过程
- [ ] requests 和 limits 分别影响什么？调度只看哪个？
- [ ] 三种 QoS 是怎么判定的？内存不足时驱逐顺序如何？
- [ ] 该不该设 CPU limit？你的理由是什么？
- [ ] Go 服务在 K8s 里必须配哪两个环境变量？GOMEMLIMIT 为什么不能等于 memory limit？
- [ ] 原生 sidecar 相比普通 sidecar 解决了哪三个问题？
- [ ] 完整描述删除 Pod 的 7 个步骤，指出哪一步是丢请求的根源
- [ ] `preStop: sleep 5` 存在的意义是什么？
- [ ] `containerPort` 不写，端口还能访问吗？
- [ ] 生产 securityContext 的 5 条基线是什么？
- [ ] 完成上面 7 个实验

---

## 13. 延伸阅读

- [Pod 概念](https://kubernetes.io/docs/concepts/workloads/pods/)
- [Pod 生命周期](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [配置探针](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Sidecar 容器](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)
- [资源管理](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- `go doc k8s.io/api/core/v1 PodSpec` —— 最权威的字段参考

---

下一章：[08 - 配置与密钥：ConfigMap 和 Secret](./08-config-secret.md)
