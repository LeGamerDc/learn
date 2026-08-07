# 20 - 端到端实战：Go 服务全链路交付

> 本章目标：把前 19 章的所有知识串成一条完整的生产级链路，从零跑通一遍。
> 这是一次"综合演练"，做完你就具备了独立交付和运维的能力。
> 预计用时：4~6 小时（分几次做完也可以）。

---

## 0. 我们要做什么

构建一个真实的订单服务 `orders`：

```
                          互联网
                             │
                    ┌────────▼─────────┐
                    │  Gateway API      │  HTTPRoute（含金丝雀权重）
                    └────────┬─────────┘
              ┌──────────────┴─────────────┐
              ▼                            ▼
      ┌──────────────┐            ┌──────────────┐
      │ orders-stable│            │ orders-canary│
      │  (Rollout)   │            │              │
      └───┬──────┬───┘            └──────────────┘
          │      │
    ┌─────▼──┐ ┌─▼──────┐
    │Postgres│ │ Redis  │
    │(StatefulSet)│(Deployment)│
    └────────┘ └────────┘

  可观测：Prometheus 抓 /metrics，Grafana 看板，日志 stdout
  交付：Git push → CI 构建镜像 → 更新配置仓 → Argo CD 同步 → Rollouts 灰度
```

**涉及的知识点**（做的时候对照回看）：

| 步骤 | 章节 |
|---|---|
| Go 应用（探针、优雅退出、指标、日志） | 3、4、7、13 |
| 多阶段 Dockerfile、多架构 | 3 |
| Deployment/StatefulSet/Service/PVC | 9、10、11 |
| ConfigMap/Secret | 8 |
| 资源、探针、拓扑分布、PDB、HPA | 7、12 |
| Gateway API | 10 |
| Prometheus/ServiceMonitor/告警 | 13 |
| RBAC/PSA/NetworkPolicy | 14 |
| Helm Chart | 15 |
| GitOps | 18 |
| 金丝雀 | 19 |

---

## 1. 准备环境

```bash
# 确认基础设施都在
kubectl get nodes
kubectl -n monitoring get pods | head -5      # 第 13 章装的
kubectl -n argocd get pods | head -5          # 第 18 章装的
kubectl -n argo-rollouts get pods             # 第 19 章装的

# 如果没装，快速补上
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace --set prometheus.prometheusSpec.retention=2d \
  --set alertmanager.enabled=false --wait --timeout 10m

kubectl create ns argocd 2>/dev/null
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s

kubectl create ns argo-rollouts 2>/dev/null
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Gateway API + Envoy Gateway
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.0/standard-install.yaml
helm upgrade --install eg oci://docker.io/envoyproxy/gateway-helm --version v1.6.0 \
  -n envoy-gateway-system --create-namespace --wait

# 本地 registry（第 0 章）
docker start kind-registry 2>/dev/null || \
  docker run -d --restart=always -p 5001:5000 --name kind-registry registry:2
docker network connect kind kind-registry 2>/dev/null || true
```

---

## 2. 第一步：写应用

```bash
mkdir -p ~/lab/orders/cmd/server && cd ~/lab/orders
go mod init example.com/orders
```

### `cmd/server/main.go`

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"runtime/debug"
	"strconv"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	_ "time/tzdata"

	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

var (
	version = "dev"
	commit  = "none"

	httpRequests = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "http_requests_total",
		Help: "Total HTTP requests",
	}, []string{"method", "route", "status", "version"})

	httpDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "http_request_duration_seconds",
		Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5},
	}, []string{"route", "version"})

	ordersCreated = promauto.NewCounter(prometheus.CounterOpts{
		Name: "orders_created_total",
	})
)

type app struct {
	db     *sql.DB
	rdb    *redis.Client
	ready  atomic.Bool
	logger *slog.Logger
}

func main() {
	initLogger()
	setMemLimit()

	a := &app{logger: slog.Default()}
	a.initDeps()
	a.ready.Store(true)

	// 业务端口
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", a.healthz)   // liveness：只看进程
	mux.HandleFunc("GET /readyz", a.readyz)     // readiness：看依赖
	mux.HandleFunc("GET /", a.index)
	mux.HandleFunc("GET /orders", a.listOrders)
	mux.HandleFunc("POST /orders", a.createOrder)
	mux.HandleFunc("GET /slow", a.slow)         // 演示延迟
	mux.HandleFunc("GET /error", a.errorEndpoint) // 演示错误率

	srv := &http.Server{
		Addr:              ":" + getenv("PORT", "8080"),
		Handler:           a.withMetrics(mux),
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	// 指标 + pprof 端口（不对外暴露）
	adminMux := http.NewServeMux()
	adminMux.Handle("/metrics", promhttp.Handler())
	go func() {
		if err := http.ListenAndServe(":"+getenv("METRICS_PORT", "9090"), adminMux); err != nil {
			slog.Error("admin server failed", "err", err)
		}
	}()

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	go func() {
		slog.Info("server starting", "addr", srv.Addr, "version", version, "commit", commit)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("listen failed", "err", err)
			os.Exit(1)
		}
	}()

	<-ctx.Done()
	slog.Info("SIGTERM received, draining")

	// ① 先摘流量（配合 preStop sleep，见第 7 章）
	a.ready.Store(false)

	// ② 等存量请求处理完
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		slog.Error("graceful shutdown failed", "err", err)
	}

	// ③ 关下游
	if a.db != nil {
		a.db.Close()
	}
	if a.rdb != nil {
		a.rdb.Close()
	}
	slog.Info("bye")
}

func (a *app) initDeps() {
	if dsn := os.Getenv("DB_DSN"); dsn != "" {
		db, err := sql.Open("pgx", dsn)
		if err != nil {
			slog.Error("db open failed", "err", err)
			os.Exit(1) // fail fast
		}
		db.SetMaxOpenConns(20)
		db.SetMaxIdleConns(5)
		db.SetConnMaxLifetime(30 * time.Minute)
		a.db = db

		// 建表（生产应该用独立的迁移 Job，这里为了实验简化）
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		for i := 0; i < 30; i++ {
			if err := db.PingContext(ctx); err == nil {
				break
			}
			slog.Warn("waiting for db", "attempt", i)
			time.Sleep(2 * time.Second)
		}
		if _, err := db.ExecContext(ctx, `
			CREATE TABLE IF NOT EXISTS orders (
				id SERIAL PRIMARY KEY,
				item TEXT NOT NULL,
				amount INT NOT NULL,
				created_at TIMESTAMPTZ DEFAULT now()
			)`); err != nil {
			slog.Error("migrate failed", "err", err)
		}
	}

	if addr := os.Getenv("REDIS_ADDR"); addr != "" {
		a.rdb = redis.NewClient(&redis.Options{
			Addr:     addr,
			Password: os.Getenv("REDIS_PASSWORD"),
		})
	}
}

// ⭐ liveness：绝不检查外部依赖（第 7 章）
func (a *app) healthz(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte("ok"))
}

// ⭐ readiness：检查依赖 + 支持优雅退出时主动摘流量
func (a *app) readyz(w http.ResponseWriter, r *http.Request) {
	if !a.ready.Load() {
		http.Error(w, "shutting down", http.StatusServiceUnavailable)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if a.db != nil {
		if err := a.db.PingContext(ctx); err != nil {
			http.Error(w, "db not ready: "+err.Error(), http.StatusServiceUnavailable)
			return
		}
	}
	if a.rdb != nil {
		if err := a.rdb.Ping(ctx).Err(); err != nil {
			http.Error(w, "redis not ready: "+err.Error(), http.StatusServiceUnavailable)
			return
		}
	}
	w.Write([]byte("ready"))
}

func (a *app) index(w http.ResponseWriter, r *http.Request) {
	host, _ := os.Hostname()
	writeJSON(w, 200, map[string]any{
		"service":  "orders",
		"version":  version,
		"commit":   commit,
		"pod":      host,
		"node":     os.Getenv("NODE_NAME"),
		"greeting": getenv("GREETING", "hello"),
		"time":     time.Now().Format(time.RFC3339),
	})
}

func (a *app) createOrder(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Item   string `json:"item"`
		Amount int    `json:"amount"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Item == "" {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	if a.db == nil {
		writeJSON(w, 503, map[string]string{"error": "db not configured"})
		return
	}
	var id int
	err := a.db.QueryRowContext(r.Context(),
		`INSERT INTO orders(item, amount) VALUES($1,$2) RETURNING id`, req.Item, req.Amount).Scan(&id)
	if err != nil {
		a.logger.Error("insert failed", "err", err)
		writeJSON(w, 500, map[string]string{"error": "insert failed"})
		return
	}
	ordersCreated.Inc()
	if a.rdb != nil {
		a.rdb.Del(r.Context(), "orders:list")
	}
	a.logger.Info("order created", "id", id, "item", req.Item, "amount", req.Amount)
	writeJSON(w, 201, map[string]any{"id": id})
}

func (a *app) listOrders(w http.ResponseWriter, r *http.Request) {
	if a.db == nil {
		writeJSON(w, 503, map[string]string{"error": "db not configured"})
		return
	}
	// 先查缓存
	if a.rdb != nil {
		if cached, err := a.rdb.Get(r.Context(), "orders:list").Result(); err == nil {
			w.Header().Set("X-Cache", "HIT")
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte(cached))
			return
		}
	}
	rows, err := a.db.QueryContext(r.Context(),
		`SELECT id, item, amount FROM orders ORDER BY id DESC LIMIT 20`)
	if err != nil {
		writeJSON(w, 500, map[string]string{"error": err.Error()})
		return
	}
	defer rows.Close()

	out := []map[string]any{}
	for rows.Next() {
		var id, amount int
		var item string
		if err := rows.Scan(&id, &item, &amount); err != nil {
			continue
		}
		out = append(out, map[string]any{"id": id, "item": item, "amount": amount})
	}
	b, _ := json.Marshal(out)
	if a.rdb != nil {
		a.rdb.Set(r.Context(), "orders:list", string(b), 30*time.Second)
	}
	w.Header().Set("X-Cache", "MISS")
	w.Header().Set("Content-Type", "application/json")
	w.Write(b)
}

// 演示用：可控的延迟和错误，方便测试金丝雀分析
func (a *app) slow(w http.ResponseWriter, r *http.Request) {
	ms, _ := strconv.Atoi(r.URL.Query().Get("ms"))
	if ms == 0 {
		ms = 500
	}
	time.Sleep(time.Duration(ms) * time.Millisecond)
	w.Write([]byte("slow done"))
}

func (a *app) errorEndpoint(w http.ResponseWriter, r *http.Request) {
	if os.Getenv("SIMULATE_ERRORS") == "true" {
		http.Error(w, "simulated failure", 500)
		return
	}
	w.Write([]byte("ok"))
}

// ⭐ 指标中间件：route 用模板而不是真实路径（避免基数爆炸，第 13 章）
func (a *app) withMetrics(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rw := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(rw, r)

		route := normalizeRoute(r.URL.Path)
		httpRequests.WithLabelValues(r.Method, route, strconv.Itoa(rw.status), version).Inc()
		httpDuration.WithLabelValues(route, version).Observe(time.Since(start).Seconds())
	})
}

func normalizeRoute(p string) string {
	switch {
	case p == "/" || p == "":
		return "/"
	case strings.HasPrefix(p, "/orders"):
		return "/orders"
	case strings.HasPrefix(p, "/health"), strings.HasPrefix(p, "/ready"):
		return "/health"
	case strings.HasPrefix(p, "/slow"):
		return "/slow"
	case strings.HasPrefix(p, "/error"):
		return "/error"
	}
	return "other"
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}

func initLogger() {
	lvl := slog.LevelInfo
	_ = lvl.UnmarshalText([]byte(strings.ToUpper(getenv("LOG_LEVEL", "INFO"))))
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: lvl})).With(
		"service", "orders",
		"version", version,
		"pod", os.Getenv("POD_NAME"),
		"node", os.Getenv("NODE_NAME"),
	))
}

// ⭐ 从 cgroup 读内存上限，设 GOMEMLIMIT 为 85%（第 7 章）
func setMemLimit() {
	b, err := os.ReadFile("/sys/fs/cgroup/memory.max")
	if err != nil {
		return
	}
	s := strings.TrimSpace(string(b))
	if s == "max" {
		return
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil || v <= 0 {
		return
	}
	limit := int64(float64(v) * 0.85)
	debug.SetMemoryLimit(limit)
	slog.Info("GOMEMLIMIT set", "bytes", limit)
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
```

```bash
go get github.com/jackc/pgx/v5 github.com/redis/go-redis/v9 github.com/prometheus/client_golang
go mod tidy
go build ./... && echo "build ok"
```

### `Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.26-alpine AS builder
ARG TARGETOS TARGETARCH VERSION=dev COMMIT=none
WORKDIR /src
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -trimpath -ldflags="-s -w -X main.version=${VERSION} -X main.commit=${COMMIT}" \
      -o /out/server ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
LABEL org.opencontainers.image.source="https://github.com/yourorg/orders"
COPY --from=builder /out/server /server
USER 65532:65532
EXPOSE 8080 9090
ENTRYPOINT ["/server"]
```

### `.dockerignore`

```
.git
*.md
Dockerfile*
.dockerignore
bin/
charts/
```

### 构建并推到本地仓库

```bash
cd ~/lab/orders
docker build --build-arg VERSION=v1.0.0 --build-arg COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo local) \
  -t localhost:5001/orders:v1.0.0 .
docker push localhost:5001/orders:v1.0.0
docker images localhost:5001/orders     # 应该在 15MB 左右
```

---

## 3. 第二步：写 Helm Chart

```bash
mkdir -p ~/lab/orders-chart/templates && cd ~/lab/orders-chart
```

### `Chart.yaml`

```yaml
apiVersion: v2
name: orders
description: Orders service
type: application
version: 0.1.0
appVersion: "1.0.0"
kubeVersion: ">=1.30.0-0"
```

### `values.yaml`

```yaml
replicaCount: 3

image:
  repository: localhost:5001/orders
  tag: ""
  pullPolicy: IfNotPresent

progressiveDelivery:
  enabled: false          # true 时用 Rollout 替代 Deployment

config:
  logLevel: info
  greeting: "hello from orders"
  simulateErrors: "false"

postgres:
  enabled: true
  image: postgres:17-alpine
  storage: 2Gi
  user: app
  password: app_password  # ⚠️ 演示用；生产用 External Secrets（第 8 章）
  database: orders

redis:
  enabled: true
  image: redis:7-alpine

resources:
  requests: {cpu: 100m, memory: 128Mi}
  limits: {memory: 512Mi}

autoscaling:
  enabled: false
  minReplicas: 3
  maxReplicas: 12
  targetCPUUtilizationPercentage: 70

pdb:
  enabled: true
  maxUnavailable: 1

serviceMonitor:
  enabled: true
  interval: 15s

networkPolicy:
  enabled: false          # kind 默认 CNI 不支持，装了 Calico 再打开

gateway:
  enabled: false
  hostname: orders.local
```

### `templates/_helpers.tpl`

```gotemplate
{{- define "orders.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "orders.fullname" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "orders.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{ include "orders.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "orders.selectorLabels" -}}
app.kubernetes.io/name: {{ include "orders.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* 共用的 Pod spec，Deployment 和 Rollout 都引用它 */}}
{{- define "orders.podSpec" -}}
terminationGracePeriodSeconds: 45
securityContext:
  runAsNonRoot: true
  runAsUser: 65532
  runAsGroup: 65532
  seccompProfile: {type: RuntimeDefault}
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        {{- include "orders.selectorLabels" . | nindent 8 }}
    matchLabelKeys: [pod-template-hash]
containers:
  - name: server
    image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
    imagePullPolicy: {{ .Values.image.pullPolicy }}
    ports:
      - {name: http, containerPort: 8080}
      - {name: metrics, containerPort: 9090}
    env:
      - name: POD_NAME
        valueFrom: {fieldRef: {fieldPath: metadata.name}}
      - name: NODE_NAME
        valueFrom: {fieldRef: {fieldPath: spec.nodeName}}
      {{- if .Values.postgres.enabled }}
      - name: DB_DSN
        valueFrom:
          secretKeyRef: {name: {{ include "orders.fullname" . }}-db, key: dsn}
      {{- end }}
      {{- if .Values.redis.enabled }}
      - name: REDIS_ADDR
        value: {{ include "orders.fullname" . }}-redis:6379
      {{- end }}
    envFrom:
      - configMapRef: {name: {{ include "orders.fullname" . }}-config}
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
      periodSeconds: 3
      timeoutSeconds: 2
      failureThreshold: 2
    lifecycle:
      preStop: {sleep: {seconds: 5}}
    resources:
      {{- toYaml .Values.resources | nindent 6 }}
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities: {drop: ["ALL"]}
    volumeMounts:
      - {name: tmp, mountPath: /tmp}
volumes:
  - name: tmp
    emptyDir: {medium: Memory, sizeLimit: 32Mi}
{{- end }}
```

### `templates/configmap.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "orders.fullname" . }}-config
  labels: {{- include "orders.labels" . | nindent 4 }}
data:
  LOG_LEVEL: {{ .Values.config.logLevel | quote }}
  GREETING: {{ .Values.config.greeting | quote }}
  SIMULATE_ERRORS: {{ .Values.config.simulateErrors | quote }}
  TZ: "Asia/Shanghai"
```

### `templates/secret.yaml`

```yaml
{{- if .Values.postgres.enabled }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "orders.fullname" . }}-db
  labels: {{- include "orders.labels" . | nindent 4 }}
type: Opaque
stringData:
  username: {{ .Values.postgres.user }}
  password: {{ .Values.postgres.password }}
  dsn: "postgres://{{ .Values.postgres.user }}:{{ .Values.postgres.password }}@{{ include "orders.fullname" . }}-postgres:5432/{{ .Values.postgres.database }}?sslmode=disable"
{{- end }}
```

### `templates/deployment.yaml`

```yaml
{{- if not .Values.progressiveDelivery.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "orders.fullname" . }}
  labels: {{- include "orders.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  minReadySeconds: 10
  strategy:
    type: RollingUpdate
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
  selector:
    matchLabels: {{- include "orders.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels: {{- include "orders.labels" . | nindent 8 }}
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
    spec:
      {{- include "orders.podSpec" . | nindent 6 }}
{{- end }}
```

### `templates/rollout.yaml`

```yaml
{{- if .Values.progressiveDelivery.enabled }}
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: {{ include "orders.fullname" . }}
  labels: {{- include "orders.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  strategy:
    canary:
      canaryService: {{ include "orders.fullname" . }}-canary
      stableService: {{ include "orders.fullname" . }}-stable
      steps:
        - setWeight: 20
        - pause: {duration: 60s}
        - setWeight: 50
        - pause: {duration: 60s}
        - setWeight: 100
      maxSurge: "25%"
      maxUnavailable: 0
  selector:
    matchLabels: {{- include "orders.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels: {{- include "orders.labels" . | nindent 8 }}
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
    spec:
      {{- include "orders.podSpec" . | nindent 6 }}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ include "orders.fullname" . }}-canary
  labels: {{- include "orders.labels" . | nindent 4 }}
spec:
  selector: {{- include "orders.selectorLabels" . | nindent 4 }}
  ports:
    - {name: http, port: 80, targetPort: http}
    - {name: metrics, port: 9090, targetPort: metrics}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ include "orders.fullname" . }}-stable
  labels: {{- include "orders.labels" . | nindent 4 }}
spec:
  selector: {{- include "orders.selectorLabels" . | nindent 4 }}
  ports:
    - {name: http, port: 80, targetPort: http}
    - {name: metrics, port: 9090, targetPort: metrics}
{{- end }}
```

### `templates/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "orders.fullname" . }}
  labels: {{- include "orders.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  selector: {{- include "orders.selectorLabels" . | nindent 4 }}
  ports:
    - {name: http, port: 80, targetPort: http}
    - {name: metrics, port: 9090, targetPort: metrics}
```

### `templates/postgres.yaml`

```yaml
{{- if .Values.postgres.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "orders.fullname" . }}-postgres
spec:
  clusterIP: None
  selector:
    app.kubernetes.io/component: postgres
    app.kubernetes.io/instance: {{ .Release.Name }}
  ports: [{name: pg, port: 5432}]
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "orders.fullname" . }}-postgres
spec:
  serviceName: {{ include "orders.fullname" . }}-postgres
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: postgres
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/component: postgres
        app.kubernetes.io/instance: {{ .Release.Name }}
    spec:
      securityContext:
        runAsUser: 999
        runAsGroup: 999
        fsGroup: 999
        fsGroupChangePolicy: OnRootMismatch
      containers:
        - name: postgres
          image: {{ .Values.postgres.image }}
          ports: [{name: pg, containerPort: 5432}]
          env:
            - name: POSTGRES_USER
              valueFrom: {secretKeyRef: {name: {{ include "orders.fullname" . }}-db, key: username}}
            - name: POSTGRES_PASSWORD
              valueFrom: {secretKeyRef: {name: {{ include "orders.fullname" . }}-db, key: password}}
            - name: POSTGRES_DB
              value: {{ .Values.postgres.database }}
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          readinessProbe:
            exec: {command: ["pg_isready", "-U", "{{ .Values.postgres.user }}"]}
            periodSeconds: 5
          resources:
            requests: {cpu: 100m, memory: 256Mi}
            limits: {memory: 1Gi}
          volumeMounts:
            - {name: data, mountPath: /var/lib/postgresql/data}
  volumeClaimTemplates:
    - metadata: {name: data}
      spec:
        accessModes: [ReadWriteOnce]
        resources: {requests: {storage: {{ .Values.postgres.storage }}}}
{{- end }}
```

### `templates/redis.yaml`

```yaml
{{- if .Values.redis.enabled }}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "orders.fullname" . }}-redis
spec:
  selector:
    app.kubernetes.io/component: redis
    app.kubernetes.io/instance: {{ .Release.Name }}
  ports: [{name: redis, port: 6379}]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "orders.fullname" . }}-redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/component: redis
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/component: redis
        app.kubernetes.io/instance: {{ .Release.Name }}
    spec:
      securityContext: {runAsNonRoot: true, runAsUser: 999, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: redis
          image: {{ .Values.redis.image }}
          args: ["--maxmemory", "128mb", "--maxmemory-policy", "allkeys-lru", "--save", ""]
          ports: [{name: redis, containerPort: 6379}]
          readinessProbe:
            exec: {command: ["redis-cli", "ping"]}
            periodSeconds: 5
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {memory: 200Mi}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities: {drop: ["ALL"]}
{{- end }}
```

### `templates/hpa.yaml` / `pdb.yaml` / `servicemonitor.yaml`

```yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "orders.fullname" . }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "orders.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: {type: Utilization, averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies: [{type: Percent, value: 25, periodSeconds: 60}]
    scaleUp:
      stabilizationWindowSeconds: 0
      policies: [{type: Percent, value: 100, periodSeconds: 30}]
{{- end }}
---
{{- if .Values.pdb.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "orders.fullname" . }}
spec:
  maxUnavailable: {{ .Values.pdb.maxUnavailable }}
  selector:
    matchLabels: {{- include "orders.selectorLabels" . | nindent 6 }}
  unhealthyPodEvictionPolicy: AlwaysAllow
{{- end }}
---
{{- if .Values.serviceMonitor.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ include "orders.fullname" . }}
  labels:
    release: monitoring
    {{- include "orders.labels" . | nindent 4 }}
spec:
  selector:
    matchLabels: {{- include "orders.selectorLabels" . | nindent 6 }}
  endpoints:
    - port: metrics
      interval: {{ .Values.serviceMonitor.interval }}
{{- end }}
```

### 验证与安装

```bash
cd ~/lab/orders-chart
helm lint .
helm template orders . | head -50
helm template orders . | kubectl apply --dry-run=client -f - | tail -5

kubectl create ns orders
kubectl label ns orders pod-security.kubernetes.io/warn=restricted

helm upgrade --install orders . -n orders --wait --timeout 5m

kubectl -n orders get all
kubectl -n orders get pvc
```

### 冒烟测试

```bash
kubectl -n orders port-forward svc/orders 8080:80 &
sleep 2

curl -s localhost:8080 | jq
curl -s -X POST localhost:8080/orders -d '{"item":"laptop","amount":9999}' | jq
curl -s -X POST localhost:8080/orders -d '{"item":"mouse","amount":199}' | jq
curl -s localhost:8080/orders | jq
curl -sI localhost:8080/orders | grep X-Cache     # 第二次应该是 HIT
curl -s localhost:8080/readyz

kill %1
```

---

## 4. 第三步：验证生产特性

### 4.1 ⭐ 零停机滚动更新

```bash
# 压测终端
kubectl -n orders run load --image=busybox:1.37 --restart=Never -- \
  sh -c 'while true; do wget -q -T2 -O- http://orders/ 2>/dev/null | grep -o "\"pod\":\"[^\"]*\"" || echo FAILED; sleep 0.2; done'
sleep 3
kubectl -n orders logs -f load &

# 触发更新
helm upgrade orders . -n orders --set config.greeting="version 2" --wait
kubectl -n orders rollout status deploy/orders

sleep 10; kill %1
kubectl -n orders logs load | grep -c FAILED       # ⭐ 应该是 0
kubectl -n orders logs load | tail -20
```

### 4.2 数据持久化

```bash
# 删掉 postgres Pod，数据应该还在
kubectl -n orders delete pod orders-postgres-0
kubectl -n orders wait --for=condition=Ready pod/orders-postgres-0 --timeout=120s

kubectl -n orders port-forward svc/orders 8080:80 &
sleep 3
curl -s localhost:8080/orders | jq        # ⭐ 订单还在
kill %1
```

### 4.3 自愈

```bash
kubectl -n orders get pods -w &
kubectl -n orders delete pod -l app.kubernetes.io/name=orders --wait=false
sleep 25; kill %1
kubectl -n orders get pods
```

### 4.4 节点维护迁移

```bash
kubectl -n orders get pods -o wide
NODE=$(kubectl -n orders get pods -l app.kubernetes.io/name=orders -o jsonpath='{.items[0].spec.nodeName}')
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=180s
kubectl -n orders get pods -o wide      # ⭐ 迁走了，PDB 保证了过程中容量
kubectl uncordon $NODE
```

### 4.5 指标与监控

```bash
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 &
# 浏览器 localhost:9090，Status → Targets 确认 orders 是 UP
```

查询：

```promql
sum(rate(http_requests_total{service=~"orders.*"}[2m])) by (route)
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[2m])) by (le, route))
orders_created_total
sum(container_memory_working_set_bytes{namespace="orders",container="server"}) by (pod)
```

生成一些流量再看：

```bash
kubectl -n orders port-forward svc/orders 8080:80 &
for i in $(seq 200); do
  curl -s -o /dev/null localhost:8080/
  curl -s -o /dev/null "localhost:8080/slow?ms=$((RANDOM % 300))"
  curl -s -o /dev/null -X POST localhost:8080/orders -d "{\"item\":\"item-$i\",\"amount\":$i}"
done
kill %1
```

### 4.6 HPA

```bash
helm upgrade orders . -n orders --set autoscaling.enabled=true --wait
kubectl -n orders get hpa -w &

kubectl -n orders run stress --image=busybox:1.37 --restart=Never -- \
  sh -c 'while true; do wget -q -O- http://orders/ >/dev/null 2>&1; done'

# 观察 REPLICAS 增长（可能要几分钟）
sleep 180; kill %1
kubectl -n orders get hpa
kubectl -n orders delete pod stress
```

### 4.7 排障演练

```bash
# ① 模拟依赖故障 → readiness 失败 → 流量摘除但不重启
kubectl -n orders scale deploy orders-redis --replicas=0
sleep 20
kubectl -n orders get pods         # ⭐ READY 0/1，但 RESTARTS 仍是 0（liveness 没被影响）
kubectl -n orders describe pod -l app.kubernetes.io/name=orders | grep -A5 "Readiness"

kubectl -n orders scale deploy orders-redis --replicas=1
sleep 20
kubectl -n orders get pods         # 自动恢复

# ② 模拟错误率上升
helm upgrade orders . -n orders --set config.simulateErrors=true --wait
kubectl -n orders port-forward svc/orders 8080:80 &
for i in $(seq 50); do curl -s -o /dev/null -w "%{http_code} " localhost:8080/error; done; echo
kill %1
# 在 Prometheus 里查询错误率：
# sum(rate(http_requests_total{status="500"}[2m])) / sum(rate(http_requests_total[2m]))
helm upgrade orders . -n orders --set config.simulateErrors=false --wait
```

---

## 5. 第四步：接入 GitOps

### 5.1 建配置仓

```bash
mkdir -p ~/lab/k8s-config/apps/orders/envs/{dev,prod} && cd ~/lab/k8s-config
git init -b main 2>/dev/null

# 把 chart 放进配置仓（也可以推到 OCI 仓库后引用）
cp -r ~/lab/orders-chart charts-orders
mkdir -p charts && mv charts-orders charts/orders

cat > apps/orders/envs/dev/values.yaml <<'EOF'
replicaCount: 2
image:
  repository: localhost:5001/orders
  tag: v1.0.0                      # ⭐ CI 只改这一行
config:
  logLevel: debug
  greeting: "orders DEV"
resources:
  requests: {cpu: 50m, memory: 64Mi}
  limits: {memory: 256Mi}
postgres: {enabled: true, storage: 1Gi}
redis: {enabled: true}
autoscaling: {enabled: false}
pdb: {enabled: false}
EOF

cat > apps/orders/envs/prod/values.yaml <<'EOF'
replicaCount: 4
image:
  repository: localhost:5001/orders
  tag: v1.0.0
config:
  logLevel: warn
  greeting: "orders PROD"
resources:
  requests: {cpu: 200m, memory: 256Mi}
  limits: {memory: 1Gi}
postgres: {enabled: true, storage: 5Gi}
redis: {enabled: true}
autoscaling: {enabled: true, minReplicas: 4, maxReplicas: 12}
pdb: {enabled: true, maxUnavailable: 1}
EOF

git add -A && git commit -m "init orders config"
```

推到 GitHub（Argo CD 需要能拉到）：

```bash
# gh repo create k8s-config --private --source=. --push
# 或手工在 GitHub 建仓后：
# git remote add origin git@github.com:YOURNAME/k8s-config.git && git push -u origin main
```

### 5.2 创建 Application

```bash
REPO=https://github.com/YOURNAME/k8s-config.git

for ENV in dev prod; do
kubectl apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: orders-$ENV
  namespace: argocd
  finalizers: [resources-finalizer.argocd.argoproj.io]
spec:
  project: default
  source:
    repoURL: $REPO
    targetRevision: main
    path: charts/orders
    helm:
      releaseName: orders
      valueFiles:
        - ../../apps/orders/envs/$ENV/values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: orders-$ENV
  syncPolicy:
    automated: {prune: true, selfHeal: true}
    syncOptions: [CreateNamespace=true, ServerSideApply=true]
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers: [/spec/replicas]      # ⭐ HPA 在管这个字段
EOF
done

argocd app list
argocd app wait orders-dev --health --timeout 600
kubectl -n orders-dev get all
```

> 说明：`valueFiles` 用 `../../` 引用 chart 目录外的文件需要 Argo CD 允许（`--helm-values-file-schemes` / 仓库级配置）。
> 如果报错，最简单的做法是把 values 文件放进 chart 目录下的 `envs/` 子目录，或者用 `helm.values` 内联。

### 5.3 ⭐ 体验 GitOps 发布

```bash
cd ~/lab/k8s-config

# ① 构建新版本镜像
cd ~/lab/orders
sed -i '' 's/"greeting": getenv("GREETING", "hello")/"greeting": getenv("GREETING", "hello v2")/' cmd/server/main.go 2>/dev/null || true
docker build --build-arg VERSION=v1.1.0 -t localhost:5001/orders:v1.1.0 .
docker push localhost:5001/orders:v1.1.0

# ② 更新配置仓（这一步在真实环境里由 CI 做，第 17 章）
cd ~/lab/k8s-config
yq -i '.image.tag = "v1.1.0"' apps/orders/envs/dev/values.yaml
git commit -am "chore(orders): bump dev to v1.1.0"
git push

# ③ Argo CD 自动同步（或手工触发）
argocd app sync orders-dev
argocd app wait orders-dev --health

kubectl -n orders-dev get deploy orders -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

### 5.4 ⭐ 体验自愈

```bash
kubectl -n orders-dev scale deploy orders --replicas=8
kubectl -n orders-dev get deploy orders -w
# 几十秒内变回 2 ✅（Git 里写的是 2）
```

### 5.5 ⭐ 体验回滚

```bash
cd ~/lab/k8s-config
git revert HEAD --no-edit && git push
argocd app sync orders-dev
kubectl -n orders-dev get deploy orders -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
# 回到 v1.0.0
```

---

## 6. 第五步：金丝雀发布

```bash
cd ~/lab/k8s-config
yq -i '.progressiveDelivery.enabled = true' apps/orders/envs/prod/values.yaml
yq -i '.autoscaling.enabled = false' apps/orders/envs/prod/values.yaml   # Rollout 和 HPA 要单独配
git commit -am "feat(orders): enable progressive delivery in prod" && git push
argocd app sync orders-prod
argocd app wait orders-prod --health --timeout 600

kubectl argo rollouts get rollout orders -n orders-prod
```

**执行一次金丝雀发布**：

```bash
# 观察终端
kubectl argo rollouts get rollout orders -n orders-prod --watch &

# 发布新版本
cd ~/lab/k8s-config
yq -i '.image.tag = "v1.1.0"' apps/orders/envs/prod/values.yaml
git commit -am "release(orders): prod v1.1.0" && git push
argocd app sync orders-prod

# 观察：20% → 暂停 60s → 50% → 暂停 60s → 100%
sleep 200; kill %1
```

**演练一次中止**：

```bash
cd ~/lab/k8s-config
yq -i '.image.tag = "v9.9.9-broken"' apps/orders/envs/prod/values.yaml   # 不存在的镜像
git commit -am "release: broken version" && git push
argocd app sync orders-prod

sleep 60
kubectl argo rollouts get rollout orders -n orders-prod
kubectl -n orders-prod get pods
# ⭐ canary Pod 是 ImagePullBackOff，但 stable 的 Pod 全部健康，服务没有受影响

kubectl argo rollouts abort orders -n orders-prod

# 修复：回滚 Git
git revert HEAD --no-edit && git push
argocd app sync orders-prod
kubectl argo rollouts promote orders -n orders-prod --full 2>/dev/null || true
```

---

## 7. 第六步：CI 接入（可选，需要 Jenkins）

如果你做了第 17 章的实验，把 Jenkinsfile 放进 `~/lab/orders/Jenkinsfile`，把最后的 "Update Config Repo" stage 改成：

```groovy
sh '''
  git clone <你的配置仓> /tmp/config
  cd /tmp/config
  yq -i ".image.tag = \\"${IMAGE_TAG}\\"" apps/orders/envs/dev/values.yaml
  git -c user.email=ci@local -c user.name=CI commit -am "chore(orders): dev → ${IMAGE_TAG}"
  git push
'''
```

**完整链路就通了**：

```
git push（应用代码）
  → Jenkins：test → build → push image:build-42-a3f9c21
    → Jenkins：改配置仓 dev/values.yaml 的 tag
      → Argo CD：3 分钟内检测到 → 同步到 dev
        → 验证 OK → 人工把 prod/values.yaml 也改成这个 tag（PR + review）
          → Argo CD 同步 prod → Argo Rollouts 金丝雀 20%→50%→100%
```

---

## 8. 验收清单

全部打勾说明你已经具备独立交付和运维的能力：

### 应用层
- [ ] Go 服务有 liveness / readiness / startup 三种探针，且 liveness 不检查依赖
- [ ] 实现了优雅退出（先摘流量 → drain → 关依赖）
- [ ] 结构化 JSON 日志写 stdout，带 pod/version 字段
- [ ] 暴露 Prometheus 指标（RED），路由标签是模板不是真实路径
- [ ] GOMEMLIMIT 从 cgroup 自动推导
- [ ] 配置全部来自环境变量，启动时 fail fast

### 镜像层
- [ ] 多阶段构建，distroless 基础镜像，< 20MB
- [ ] 非 root 运行
- [ ] 不可变 tag，不用 latest
- [ ] 构建缓存生效（改代码时不重新下依赖）

### 编排层
- [ ] Deployment 配了 `maxSurge: 1 / maxUnavailable: 0` + `minReadySeconds`
- [ ] 配了 resources、securityContext、preStop、terminationGracePeriodSeconds
- [ ] 配了 topologySpreadConstraints
- [ ] 有 PDB
- [ ] 有状态依赖用 StatefulSet + PVC，Pod 删除后数据还在
- [ ] ConfigMap 变更能触发滚动更新（checksum）
- [ ] 密钥用 Secret（生产用 External Secrets）
- [ ] 滚动更新期间压测 0 失败

### 交付层
- [ ] Helm Chart 参数化，多环境用不同 values
- [ ] 配置仓和代码仓分离
- [ ] Argo CD 自动同步 + selfHeal
- [ ] 手工改集群会被自动改回来
- [ ] `git revert` 能回滚
- [ ] 金丝雀发布能正常推进和中止

### 运维层
- [ ] Prometheus 抓到了应用指标
- [ ] 能用 PromQL 查 QPS、错误率、P99
- [ ] 能 `kubectl drain` 节点且服务不中断
- [ ] 能用 `kubectl debug` 调试 distroless 容器
- [ ] HPA 能根据负载扩缩容

---

## 9. 清理

```bash
argocd app delete orders-dev --cascade -y 2>/dev/null
argocd app delete orders-prod --cascade -y 2>/dev/null
helm uninstall orders -n orders 2>/dev/null
kubectl delete ns orders orders-dev orders-prod --ignore-not-found

# 保留 monitoring / argocd / argo-rollouts，后面章节还要用
```

---

## 10. 下一步

这条链路是**最小可用的生产级形态**。真实生产还需要补充（第 21、23 章）：

- 多集群 / 多地域
- 外部密钥管理（Vault / ESO）
- 日志采集系统（Loki / ELK）
- 分布式追踪（Tempo / Jaeger）
- 告警接入值班系统
- 数据库用托管服务或 Operator
- 备份与灾难恢复（Velero）
- 网络策略、镜像签名验证
- 成本监控与容量规划

---

下一章：[21 - 大规模集群管理](./21-large-scale-ops.md)
