# 13 - 可观测性：日志、指标、追踪

> 本章目标：回答"日志去哪了、怎么采集"，并建立完整的可观测性体系——
> 出问题时你能在 5 分钟内定位到是哪个服务、哪个副本、哪一行代码。
> 预计用时：3 小时（含实验）。

---

## 1. 可观测性三支柱

| 支柱 | 回答什么问题 | 特点 | 工具 |
|---|---|---|---|
| **Metrics（指标）** | 系统现在健康吗？趋势如何？ | 低成本、可长期存储、适合告警 | Prometheus + Grafana |
| **Logs（日志）** | 具体发生了什么？ | 高成本、细节丰富 | Loki / Elasticsearch |
| **Traces（追踪）** | 一个请求在分布式系统里走了哪些路？慢在哪？ | 采样存储、适合定位延迟 | Jaeger / Tempo |

**排障的标准路径**：
```
告警（Metrics 发现异常）
  → Dashboard（Metrics 定位到服务/实例）
    → Trace（找到慢的那个环节）
      → Log（看具体错误）
```

**串联三者的关键是 `trace_id`**：日志里带 trace_id，指标里带 exemplar（指向 trace），追踪里能跳到日志。

---

## 2. 日志

### 2.1 完整的日志链路

```
你的 Go 程序
   │ slog.Info(...) → os.Stdout
   ▼
容器运行时（containerd）捕获 stdout/stderr
   │ 写入节点文件
   ▼
/var/log/pods/<ns>_<pod>_<uid>/<container>/0.log
   │ （kubelet 负责轮转：containerLogMaxSize 默认 10Mi，containerLogMaxFiles 默认 5）
   │
   ├──► kubectl logs  ←── kubelet 直接读这个文件返回
   │
   └──► 日志采集 DaemonSet（Fluent Bit / Vector / Promtail）
          │ 读文件 + 解析 + 打上 K8s 元数据（namespace/pod/container/labels）
          ▼
       日志后端（Loki / Elasticsearch / 云日志服务）
          ▼
       查询界面（Grafana / Kibana）
```

在 kind 节点上亲眼看看：

```bash
docker exec learn-worker ls /var/log/pods/
docker exec learn-worker sh -c 'find /var/log/pods -name "*.log" | head -3'
docker exec learn-worker sh -c 'tail -2 $(find /var/log/pods -name "0.log" | head -1)'
# 2026-07-29T10:00:00.123456789Z stdout F {"time":"...","level":"INFO","msg":"..."}
#  ^时间戳                       ^流    ^F=Full行/P=Partial   ^你的日志
```

### 2.2 kubectl logs 的全部用法

```bash
kubectl logs <pod>
kubectl logs <pod> -c <container>            # 多容器 Pod
kubectl logs <pod> --previous                # ⭐ 崩溃前那次的日志（排查 CrashLoop 必用）
kubectl logs <pod> -f                        # 跟随
kubectl logs <pod> --tail=100
kubectl logs <pod> --since=10m
kubectl logs <pod> --since-time=2026-07-29T10:00:00Z
kubectl logs <pod> --timestamps
kubectl logs -l app=hello --all-containers --max-log-requests=20   # 按标签聚合
kubectl logs deployment/hello                # 从 Deployment 挑一个 Pod
kubectl logs job/migrate

# ⭐ stern：更好用的多 Pod 日志（强烈推荐）
stern hello                                  # 匹配名字含 hello 的所有 Pod
stern -n prod --since 5m 'api-.*'
stern hello -c server --include 'ERROR|WARN'
stern -l app=hello --output json
```

**`kubectl logs` 的局限**：
- Pod 删除后日志就没了（节点上的文件被清理）
- 只能看单个 Pod（或用 label 聚合，但数量有限）
- 不能全文检索、不能聚合统计
- 节点故障后完全拿不到

**所以生产必须有日志采集系统。**

### 2.3 采集方案

| 方案 | 说明 |
|---|---|
| **Node Agent（DaemonSet）** ⭐ | 每个节点一个采集器读 `/var/log/pods`。**标准做法**，应用零改造 |
| Sidecar | 每个 Pod 一个采集容器。适合必须写文件的遗留应用（用原生 sidecar，第 7 章） |
| 应用直推 | 应用直接写日志后端。**不推荐**：耦合、后端挂了会影响应用、丢日志 |

**Loki + Promtail/Alloy 栈**（轻量，推荐中小规模）：

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack -n observability --create-namespace \
  --set grafana.enabled=true --set promtail.enabled=true
```

Loki 的设计哲学：**只索引标签，不索引日志内容**（像 Prometheus）。所以成本远低于 Elasticsearch，但全文检索能力弱一些。查询用 LogQL：

```logql
{namespace="prod", app="hello"} |= "ERROR"
{namespace="prod", app="hello"} | json | level="ERROR" | duration_ms > 1000
sum(rate({namespace="prod"} |= "ERROR" [5m])) by (app)
```

**Fluent Bit 配置要点**（用 ELK 或云日志时）：

```ini
[INPUT]
    Name              tail
    Path              /var/log/containers/*.log
    Parser            cri
    Tag               kube.*
    Mem_Buf_Limit     50MB
    Skip_Long_Lines   On
    Refresh_Interval  10

[FILTER]
    Name                kubernetes
    Match               kube.*
    Merge_Log           On          # 把 JSON 日志展开成字段
    Keep_Log            Off
    K8S-Logging.Parser  On
    Annotations         Off

[OUTPUT]
    Name   es
    Match  *
    Host   elasticsearch
    Retry_Limit  5
```

### 2.4 日志实践清单

- [ ] **写 stdout**，不写文件（第 4 章）
- [ ] **结构化 JSON**（`log/slog`）
- [ ] 每条日志带 `trace_id`、`pod`、`version`
- [ ] 日志级别可通过环境变量控制
- [ ] **不打印**密钥、token、身份证、完整请求体
- [ ] 健康检查端点不打日志（否则被刷屏）
- [ ] 高频日志加采样（`slog` 可以包一层采样 Handler）
- [ ] 设置节点日志轮转（kubelet 的 `containerLogMaxSize`）
- [ ] 日志后端有保留策略和容量告警
- [ ] 有一条"从告警到日志"的可点击链路（Grafana 里配 datasource 关联）

**Go 里的完整日志初始化**：

```go
func initLogger() {
    level := slog.LevelInfo
    if err := level.UnmarshalText([]byte(os.Getenv("LOG_LEVEL"))); err != nil {
        level = slog.LevelInfo
    }
    h := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
        Level: level,
        ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
            if a.Key == "time" {              // 统一时间格式
                return slog.String("time", a.Value.Time().UTC().Format(time.RFC3339Nano))
            }
            return a
        },
    })
    slog.SetDefault(slog.New(h).With(
        "service", "hello",
        "version", os.Getenv("APP_VERSION"),
        "pod", os.Getenv("POD_NAME"),
        "node", os.Getenv("NODE_NAME"),
    ))
}

// 请求级：把 trace_id 放进 context，日志里自动带上
func loggerFromCtx(ctx context.Context) *slog.Logger {
    if sc := trace.SpanContextFromContext(ctx); sc.IsValid() {
        return slog.Default().With("trace_id", sc.TraceID().String(), "span_id", sc.SpanID().String())
    }
    return slog.Default()
}
```

---

## 3. 指标：Prometheus 体系

### 3.1 架构

```
     ┌──────────────────────────────────────────────────┐
     │  Prometheus Server                               │
     │   ① 服务发现（从 K8s API 找 target）               │
     │   ② 定期 HTTP 拉取 /metrics（pull 模型）            │
     │   ③ 存进本地 TSDB                                 │
     │   ④ 执行 recording rules 和 alerting rules        │
     └───────┬──────────────────────────────┬───────────┘
             │ 抓取                          │ 告警
   ┌─────────┼─────────┬──────────┐         ▼
   ▼         ▼         ▼          ▼   ┌──────────────┐
你的 Go   node-      kube-      cAdvisor│ Alertmanager │
应用      exporter   state-     (kubelet│ 去重/分组/静默│
/metrics  (节点指标)  metrics    内置)   │ → 钉钉/飞书/  │
                    (对象状态)          │   PagerDuty  │
                                       └──────────────┘
             ▲
             │ 查询 PromQL
        ┌────┴─────┐
        │ Grafana  │
        └──────────┘
```

**关键：Prometheus 是 pull（拉）模型**——它主动来抓你的 `/metrics`。所以你的服务只需要暴露一个 HTTP 端点。

（例外：短命的 Job 用 **Pushgateway** 推；或者用 OTel Collector 做转换。）

### 3.2 安装 kube-prometheus-stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set grafana.adminPassword=admin \
  --set prometheus.prometheusSpec.retention=7d \
  --set prometheus.prometheusSpec.resources.requests.memory=1Gi
```

这一个 Chart 装了：Prometheus Operator、Prometheus、Alertmanager、Grafana、node-exporter、kube-state-metrics、一堆默认 Dashboard 和告警规则。

```bash
kubectl -n monitoring get pods
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80 &
# 浏览器打开 localhost:3000，admin/admin
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 &
```

### 3.3 四类核心指标来源

| 来源 | 提供什么 | 例子 |
|---|---|---|
| **cAdvisor**（kubelet 内置） | 容器资源用量 | `container_cpu_usage_seconds_total`、`container_memory_working_set_bytes`、`container_cpu_cfs_throttled_seconds_total` |
| **kube-state-metrics** | K8s **对象状态** | `kube_deployment_status_replicas_available`、`kube_pod_status_phase`、`kube_pod_container_status_restarts_total` |
| **node-exporter** | 节点系统指标 | `node_cpu_seconds_total`、`node_filesystem_avail_bytes`、`node_load1` |
| **你的应用** | 业务指标 | `http_requests_total`、`order_created_total` |

⚠️ 注意区分 cAdvisor 和 kube-state-metrics：前者是"实际用了多少资源"，后者是"K8s 认为对象处于什么状态"。排障时经常两个都要看。

### 3.4 Go 应用埋点

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
    // ⭐ RED 方法：Rate（请求数）、Errors（错误数）、Duration（延迟）
    httpRequests = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "http_requests_total",
        Help: "Total HTTP requests",
    }, []string{"method", "path", "status"})

    httpDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "HTTP request latency",
        // ⭐ 桶要覆盖你关心的延迟范围，且数量别太多（每个桶是一条时间序列）
        Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10},
    }, []string{"method", "path"})

    inFlight = promauto.NewGauge(prometheus.GaugeOpts{
        Name: "http_requests_in_flight",
        Help: "Current in-flight requests",
    })

    // 业务指标
    ordersCreated = promauto.NewCounter(prometheus.CounterOpts{
        Name: "orders_created_total",
    })
)

func metricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        inFlight.Inc()
        defer inFlight.Dec()

        start := time.Now()
        rw := &responseWriter{ResponseWriter: w, status: 200}
        next.ServeHTTP(rw, r)

        // ⚠️ 关键：path 必须用"路由模板"而不是真实 URL！
        //    /users/12345 会导致每个用户一条时间序列 → 基数爆炸 → Prometheus OOM
        route := routePattern(r)          // 如 "/users/{id}"
        httpRequests.WithLabelValues(r.Method, route, strconv.Itoa(rw.status)).Inc()
        httpDuration.WithLabelValues(r.Method, route).Observe(time.Since(start).Seconds())
    })
}

func main() {
    // 业务端口
    mux := http.NewServeMux()
    mux.Handle("/", metricsMiddleware(appHandler))

    // ⭐ 指标单独一个端口，不暴露到公网
    metricsMux := http.NewServeMux()
    metricsMux.Handle("/metrics", promhttp.Handler())
    metricsMux.HandleFunc("/debug/pprof/", pprof.Index)       // 性能分析（第 5 节）
    metricsMux.HandleFunc("/debug/pprof/profile", pprof.Profile)
    metricsMux.HandleFunc("/debug/pprof/heap", pprof.Index)
    go http.ListenAndServe(":9090", metricsMux)

    http.ListenAndServe(":8080", mux)
}
```

**⚠️ 基数（cardinality）是 Prometheus 的头号杀手**：

```
时间序列数 = 指标数 × label1 取值数 × label2 取值数 × ...
```

绝对不要把这些放进 label：user_id、request_id、trace_id、完整 URL、IP、时间戳、错误信息全文。
一个指标的时间序列数应该控制在几百到几千。

### 3.5 让 Prometheus 发现你的服务

Prometheus Operator 用 CRD 声明抓取目标：

```yaml
# 先给 Service 加上指标端口
apiVersion: v1
kind: Service
metadata:
  name: hello
  labels: {app: hello}
spec:
  selector: {app: hello}
  ports:
    - {name: http, port: 80, targetPort: 8080}
    - {name: metrics, port: 9090, targetPort: 9090}    # ⭐
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: hello
  labels:
    release: monitoring         # ⭐ 必须匹配 Prometheus 的 serviceMonitorSelector
spec:
  selector:
    matchLabels: {app: hello}
  namespaceSelector:
    matchNames: [prod, staging]
  endpoints:
    - port: metrics             # ⭐ 用 Service 的端口"名字"
      path: /metrics
      interval: 30s
      scrapeTimeout: 10s
      relabelings:
        - sourceLabels: [__meta_kubernetes_pod_node_name]
          targetLabel: node
```

**ServiceMonitor 不生效的排查顺序**（高频问题）：
1. `labels.release` 是否匹配 Prometheus 的 `serviceMonitorSelector`？
   `kubectl -n monitoring get prometheus -o yaml | grep -A5 serviceMonitorSelector`
2. Service 的端口有 `name` 吗？ServiceMonitor 的 `port` 引用的是名字
3. `namespaceSelector` 覆盖了目标 namespace 吗？
4. Prometheus UI 的 Status → Targets 页面看有没有这个 target、报什么错

还有 **PodMonitor**（直接监控 Pod，不需要 Service）和 **ScrapeConfig**（监控集群外的目标）。

### 3.6 PromQL 速成

```promql
# ① QPS（Counter 必须配 rate）
sum(rate(http_requests_total[5m])) by (service)

# ② 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
  / sum(rate(http_requests_total[5m])) by (service)

# ③ P99 延迟（Histogram）
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))

# ④ Pod 内存使用（相对 limit 的比例）
sum(container_memory_working_set_bytes{container!=""}) by (pod)
  / sum(kube_pod_container_resource_limits{resource="memory"}) by (pod)

# ⑤ CPU 节流比例（第 7 章讲的坑）
sum(rate(container_cpu_cfs_throttled_periods_total[5m])) by (pod)
  / sum(rate(container_cpu_cfs_periods_total[5m])) by (pod)

# ⑥ 重启次数
sum(increase(kube_pod_container_status_restarts_total[1h])) by (namespace, pod)

# ⑦ 副本数不足
kube_deployment_status_replicas_available < kube_deployment_spec_replicas

# ⑧ 节点资源超卖比
sum(kube_pod_container_resource_requests{resource="cpu"}) by (node)
  / sum(kube_node_status_allocatable{resource="cpu"}) by (node)

# ⑨ PVC 快满了
kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes > 0.85
```

**记住 3 个函数**：
- `rate()` —— Counter 的每秒增长率（必须用，不能直接看 Counter）
- `increase()` —— 区间内的总增长
- `histogram_quantile()` —— 从 Histogram 算分位数

### 3.7 告警规则

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: hello-alerts
  labels: {release: monitoring}
spec:
  groups:
    - name: hello.rules
      interval: 30s
      rules:
        # Recording rule：预计算昂贵的查询
        - record: service:http_error_rate:5m
          expr: |
            sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
              / sum(rate(http_requests_total[5m])) by (service)

        # 告警
        - alert: HighErrorRate
          expr: service:http_error_rate:5m > 0.05
          for: 5m                       # ⭐ 持续 5 分钟才告警（避免抖动误报）
          labels: {severity: critical, team: backend}
          annotations:
            summary: "{{ $labels.service }} 错误率 {{ $value | humanizePercentage }}"
            runbook_url: "https://wiki.internal/runbooks/high-error-rate"

        - alert: PodCrashLooping
          expr: increase(kube_pod_container_status_restarts_total[15m]) > 3
          for: 5m
          labels: {severity: warning}
          annotations:
            summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} 频繁重启"

        - alert: HighMemoryUsage
          expr: |
            container_memory_working_set_bytes{container!=""}
              / on(namespace,pod,container) kube_pod_container_resource_limits{resource="memory"} > 0.9
          for: 10m
          labels: {severity: warning}

        - alert: CPUThrottling
          expr: |
            rate(container_cpu_cfs_throttled_periods_total[5m])
              / rate(container_cpu_cfs_periods_total[5m]) > 0.25
          for: 10m
          labels: {severity: warning}
          annotations:
            summary: "{{ $labels.pod }} CPU 被节流 25%+，考虑调高 limit"
```

**告警设计原则**（第 23 章展开）：
- **只对"需要人立刻行动"的事情告警**。CPU 高不需要告警，用户请求失败才需要
- 基于 **SLO**（错误预算燃烧率）而不是单一阈值
- 每条告警必须有 **runbook 链接**
- 用 `for` 避免抖动
- 分级：`critical` 打电话，`warning` 进工单

---

## 4. 事件（Events）

K8s 自己的"日志"，记录对象上发生的事：

```bash
kubectl get events --sort-by=.lastTimestamp
kubectl get events -w
kubectl get events --field-selector type=Warning
kubectl get events --field-selector involvedObject.name=hello-xxx
kubectl describe pod hello | tail -20       # 最常用：Events 在最下面
```

⚠️ **事件默认只保留 1 小时**（`--event-ttl`）。排障时要快，或者用 [kubernetes-event-exporter](https://github.com/resmoio/kubernetes-event-exporter) 把事件也送进日志系统。

常见事件原因：

| Reason | 含义 |
|---|---|
| `Scheduled` / `FailedScheduling` | 调度成功/失败 |
| `Pulling` / `Pulled` / `Failed` | 镜像拉取 |
| `Created` / `Started` / `Killing` | 容器生命周期 |
| `BackOff` | CrashLoopBackOff |
| `Unhealthy` | 探针失败 |
| `OOMKilling` | 内存超限 |
| `Evicted` | 被驱逐 |
| `FailedMount` / `FailedAttachVolume` | 存储问题 |
| `NodeNotReady` | 节点异常 |

---

## 5. 调试运行中的 Pod

### 5.1 `kubectl debug`：临时容器（⭐ distroless 救星）

生产镜像是 distroless，没有 shell。**临时容器**可以往运行中的 Pod 里注入一个调试容器，共享它的 namespace：

```bash
# 注入调试容器，共享目标容器的进程 namespace
kubectl debug -it hello --image=nicolaka/netshoot --target=server

# 在里面：
ps aux                    # 能看到目标进程（因为 --target 共享了 PID ns）
ls /proc/1/root/          # ⭐ 通过 /proc 访问目标容器的文件系统！
cat /proc/1/environ | tr '\0' '\n'
ss -tlnp
curl localhost:8080/healthz
tcpdump -i any -nn port 8080
```

**其他 debug 用法**：

```bash
# 复制一个 Pod 出来调试（不影响线上流量，因为副本没有 Service 的 label 匹配问题时要注意）
kubectl debug hello -it --copy-to=hello-debug --container=server -- sh

# 复制并改镜像（比如把 distroless 换成带 shell 的版本）
kubectl debug hello --copy-to=hello-dbg --set-image=server=busybox:1.37 -it -- sh

# 调试节点（起一个特权 Pod，挂载节点根文件系统到 /host）
kubectl debug node/learn-worker -it --image=busybox:1.37
chroot /host
```

### 5.2 端口转发

```bash
kubectl port-forward pod/hello 8080:8080
kubectl port-forward svc/hello 8080:80
kubectl port-forward deploy/hello 9090:9090      # 访问 metrics/pprof
```

### 5.3 Go 的性能分析（pprof）

在 K8s 里做 CPU/内存分析：

```bash
# 转发 pprof 端口
kubectl port-forward deploy/hello 9090:9090 &

# CPU profile（30 秒）
go tool pprof -http=:8081 http://localhost:9090/debug/pprof/profile?seconds=30

# 堆内存
go tool pprof -http=:8081 http://localhost:9090/debug/pprof/heap

# goroutine（排查泄漏）
curl -s http://localhost:9090/debug/pprof/goroutine?debug=1 | head -30

# 阻塞与锁竞争（需要在代码里 SetBlockProfileRate / SetMutexProfileFraction）
go tool pprof http://localhost:9090/debug/pprof/block
```

⚠️ **安全**：pprof 端点绝不能暴露到公网，也不要放在业务端口上。放在单独端口 + NetworkPolicy 限制只允许运维 namespace 访问。

**排查内存泄漏的标准流程**：

```bash
# 间隔取两个 heap profile，对比增量
curl -s localhost:9090/debug/pprof/heap > /tmp/h1.pb.gz
sleep 600
curl -s localhost:9090/debug/pprof/heap > /tmp/h2.pb.gz
go tool pprof -http=:8081 -base /tmp/h1.pb.gz /tmp/h2.pb.gz
# ⭐ -base 显示差异，直接看出是哪里在涨
```

---

## 6. 分布式追踪

### 6.1 OpenTelemetry（现在的标准）

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

func initTracer(ctx context.Context) (func(context.Context) error, error) {
    exp, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint(os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil { return nil, err }

    res, _ := resource.New(ctx, resource.WithAttributes(
        semconv.ServiceName("hello"),
        semconv.ServiceVersion(os.Getenv("APP_VERSION")),
        semconv.K8SPodName(os.Getenv("POD_NAME")),
        semconv.K8SNamespaceName(os.Getenv("POD_NAMESPACE")),
    ))

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exp),
        sdktrace.WithResource(res),
        sdktrace.WithSampler(sdktrace.ParentBased(   // ⭐ 采样：全量存不下
            sdktrace.TraceIDRatioBased(0.05),        // 5% 采样
        )),
    )
    otel.SetTracerProvider(tp)
    otel.SetTextMapPropagator(propagation.TraceContext{})   // W3C traceparent
    return tp.Shutdown, nil
}

// HTTP 服务端自动埋点
handler := otelhttp.NewHandler(mux, "hello")

// HTTP 客户端自动传播 trace context
client := &http.Client{Transport: otelhttp.NewTransport(http.DefaultTransport)}
```

部署 Collector + Tempo：

```bash
helm install tempo grafana/tempo -n observability
helm install otel-collector open-telemetry/opentelemetry-collector -n observability \
  --set mode=daemonset
```

### 6.2 三支柱串联

在 Grafana 里配好后，可以实现：

```
Metrics 图上点一个异常点（exemplar 带了 trace_id）
    → 跳转到 Tempo 看这个请求的完整调用链
        → 点某个 span 跳转到 Loki 看这个时间段该 Pod 的日志
```

配置要点：
- 日志里必须有 `trace_id` 字段
- 指标要开启 exemplar（`prometheus.WithExemplars`）
- Grafana 的 datasource 里配好 derived fields / trace-to-logs

---

## 7. 动手实验

### 实验 1：日志链路

```bash
kubectl create ns obs && kubectl config set-context --current --namespace=obs
kubectl create deployment hello --image=hello:v0.1.0 --replicas=3
kubectl patch deploy hello -p '{"spec":{"template":{"spec":{"containers":[{"name":"hello","imagePullPolicy":"IfNotPresent"}]}}}}'
kubectl rollout status deploy/hello

kubectl logs -l app=hello --all-containers --tail=5
stern hello --tail 5 &
sleep 5; kill %1

# 看节点上的原始日志文件
POD=$(kubectl get pod -l app=hello -o jsonpath='{.items[0].metadata.name}')
NODE=$(kubectl get pod $POD -o jsonpath='{.spec.nodeName}')
docker exec $NODE sh -c "find /var/log/pods -path '*$POD*' -name '*.log' -exec tail -3 {} \;"
```

### 实验 2：安装监控栈

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set grafana.adminPassword=admin \
  --set prometheus.prometheusSpec.retention=2d \
  --set prometheus.prometheusSpec.resources.requests.memory=512Mi \
  --set alertmanager.enabled=false

kubectl -n monitoring rollout status deploy/monitoring-grafana --timeout=300s
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80 &
# 浏览器 localhost:3000 (admin/admin)
# 看内置 Dashboard：Kubernetes / Compute Resources / Namespace (Pods)
```

### 实验 3：PromQL 练习

```bash
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 &
# 浏览器 localhost:9090，依次执行：
```

```promql
up
kube_pod_status_phase{namespace="obs"}
sum(rate(container_cpu_usage_seconds_total{namespace="obs"}[5m])) by (pod)
sum(container_memory_working_set_bytes{namespace="obs",container!=""}) by (pod)
kube_deployment_status_replicas_available{namespace="obs"}
sum(kube_pod_container_resource_requests{resource="cpu"}) by (node)
```

### 实验 4：给你的服务加指标

在第 3 章的 `main.go` 里加上 §3.4 的埋点代码，重新构建镜像并部署：

```bash
cd ~/lab/hello
go get github.com/prometheus/client_golang/prometheus
# ... 加代码 ...
docker build -t hello:v0.2.0 . && kind load docker-image hello:v0.2.0 --name learn
kubectl set image deploy/hello hello=hello:v0.2.0

# 加 Service（含 metrics 端口）和 ServiceMonitor
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata: {name: hello, namespace: obs, labels: {app: hello}}
spec:
  selector: {app: hello}
  ports:
    - {name: http, port: 80, targetPort: 8080}
    - {name: metrics, port: 9090, targetPort: 9090}
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata: {name: hello, namespace: obs, labels: {release: monitoring}}
spec:
  selector: {matchLabels: {app: hello}}
  endpoints: [{port: metrics, interval: 15s}]
EOF

# 在 Prometheus UI 的 Status → Targets 里确认 obs/hello 出现且是 UP
# 然后查询：sum(rate(http_requests_total[1m])) by (path)
```

### 实验 5：kubectl debug

```bash
POD=$(kubectl get pod -l app=hello -o name | head -1)
kubectl debug -it $POD --image=nicolaka/netshoot --target=hello -- bash
# 里面执行：
ps aux
ls /proc/1/root/
cat /proc/1/environ | tr '\0' '\n' | head
curl -s localhost:8080/healthz
ss -tlnp
exit
```

### 实验 6：事件观察

```bash
kubectl get events -w &
# 另一边制造事件
kubectl set image deploy/hello hello=hello:nonexistent
sleep 20
kubectl get events --sort-by=.lastTimestamp | tail -10
kubectl rollout undo deploy/hello
kill %1
```

### 清理

```bash
kubectl delete ns obs
# 保留 monitoring namespace，后面章节还要用
kubectl config set-context --current --namespace=default
```

---

## 8. 本章检查清单

- [ ] 画出从 `slog.Info` 到 Grafana 的完整日志链路
- [ ] `kubectl logs --previous` 什么时候用？
- [ ] 为什么日志采集要用 DaemonSet 而不是应用直推？
- [ ] Prometheus 是 push 还是 pull 模型？这意味着什么？
- [ ] cAdvisor、kube-state-metrics、node-exporter 分别提供什么？
- [ ] 什么是基数爆炸？哪些东西绝对不能做 label？
- [ ] RED 三个指标是什么？怎么用 PromQL 算 P99 和错误率？
- [ ] ServiceMonitor 不生效，排查顺序是什么？
- [ ] 告警的 `for` 字段解决什么问题？
- [ ] K8s Event 默认保留多久？这对排障有什么影响？
- [ ] distroless 镜像怎么调试？`kubectl debug --target` 的原理是什么？
- [ ] 怎么在 K8s 里对 Go 服务做内存泄漏分析？
- [ ] 三支柱怎么通过 trace_id 串联？
- [ ] 完成实验 2、4、5

---

## 9. 延伸阅读

- [Prometheus 官方文档](https://prometheus.io/docs/)
- [PromQL 教程](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [OpenTelemetry Go](https://opentelemetry.io/docs/languages/go/)
- [Google SRE Book - Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)（RED/USE/四个黄金信号）
- [Grafana Loki](https://grafana.com/docs/loki/latest/)

---

下一章：[14 - 安全与多租户](./14-security.md)
