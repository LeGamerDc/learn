# 19 - 渐进式交付：金丝雀与蓝绿

> 本章目标：从"滚动更新"进化到"带指标验证的自动灰度"。学完你能做到：
> 新版本先给 5% 流量，自动比对错误率和延迟，达标就继续推进，不达标自动回滚——全程无人值守。
> 预计用时：2.5 小时（含实验）。

---

## 1. 为什么滚动更新还不够

第 9 章的 RollingUpdate 已经做到零停机了。但它有个根本缺陷：

**它只检查"Pod 是否 Ready"，不检查"新版本是否正确"。**

考虑这些场景：

| 问题 | RollingUpdate 能发现吗 |
|---|---|
| 新版本启动失败 | ✅ 能（Pod 不 Ready，更新卡住） |
| 新版本健康检查通过，但业务逻辑错了（返回 500） | ❌ 不能 |
| 新版本 P99 延迟从 50ms 涨到 800ms | ❌ 不能 |
| 新版本内存泄漏，10 分钟后才 OOM | ❌ 不能（那时已全量替换完） |
| 新版本把订单金额算错了 | ❌ 不能 |

RollingUpdate 会**开开心心地把 100% 流量切到坏版本上**，然后你从监控告警或用户投诉里得知出事了。

**渐进式交付（Progressive Delivery）= 滚动更新 + 流量控制 + 指标验证 + 自动回滚。**

---

## 2. 发布策略全景

| 策略 | 原理 | 停机 | 资源开销 | 回滚速度 | 风险控制 |
|---|---|---|---|---|---|
| **Recreate** | 全停再全起 | ❌ 有 | 1× | 慢（要重新部署） | 无 |
| **Rolling** | 逐步替换 | ✅ 无 | ~1.25× | 中（滚回去） | 弱 |
| **Blue-Green** | 起一套完整新环境，验证后整体切流 | ✅ 无 | **2×** | ⭐ **极快**（切回去） | 中（切流是瞬间的，全有或全无） |
| **Canary** ⭐ | 少量流量给新版本，逐步放大 | ✅ 无 | ~1.1× | 快 | ⭐ **强**（爆炸半径可控） |
| **A/B Testing** | 按 header/cookie/用户特征路由 | ✅ 无 | ~1.1× | 快 | 强（可定向到内部用户） |
| **Shadow（影子流量）** | 复制真实流量到新版本，**丢弃响应** | ✅ 无 | 2× | — | ⭐ 最强（零用户影响） |

### 2.1 Blue-Green

```
        ┌─────────┐
流量 ───►│  Service │───► Blue (v1) ×5    ← 当前生产
        └─────────┘
                     Green (v2) ×5   ← 新版本，已启动，用 preview Service 验证
                          │
        切换 selector      │
        ┌─────────┐       │
流量 ───►│  Service │───────┘
        └─────────┘
             Blue (v1) ×5  ← 保留一段时间，出问题秒切回
```

- ✅ 回滚就是改一个 selector，秒级
- ✅ 可以在切流前对 green 做完整的自动化验证
- ❌ 需要 2 倍资源
- ❌ 切流是"全有或全无"，有问题时 100% 用户受影响（只是持续时间短）
- ⚠️ 数据库 schema 必须同时兼容两个版本

### 2.2 Canary

```
第 1 步:  v1 ×95%  |  v2 ×5%    ← 观察指标 5 分钟
第 2 步:  v1 ×80%  |  v2 ×20%   ← 观察
第 3 步:  v1 ×50%  |  v2 ×50%   ← 观察
第 4 步:  v1 ×0%   |  v2 ×100%  ← 完成

任一步指标异常 → 立刻把流量全部切回 v1，销毁 v2
```

- ✅ 爆炸半径小（5% 用户受影响 vs 100%）
- ✅ 有真实流量的验证
- ✅ 资源开销小
- ❌ 需要能按比例切流的能力（Gateway API / Ingress / Service Mesh）
- ❌ 发布周期长（几十分钟）

**两种流量切分方式**：

| 方式 | 原理 | 精度 |
|---|---|---|
| **副本数比例**（穷人版金丝雀） | v1 起 9 个、v2 起 1 个，共用一个 Service，靠 kube-proxy 随机分配 | 粗糙，且受 Pod 分布影响；长连接下完全失效 |
| **流量权重**（正确做法）⭐ | 在 L7 代理（Gateway API / Envoy / Istio）上按 weight 分流 | 精确，且可按 header 定向 |

---

## 3. Argo Rollouts

**Argo Rollouts** 用一个 `Rollout` CRD 替代 `Deployment`，提供上述所有策略 + 指标分析 + 自动回滚。当前版本 **1.9.x**。

### 3.1 安装

```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# CLI 插件（非常好用）
brew install argoproj/tap/kubectl-argo-rollouts
kubectl argo rollouts version
```

### 3.2 Rollout：金丝雀

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: hello
spec:
  replicas: 10
  revisionHistoryLimit: 5
  selector:
    matchLabels: {app: hello}

  # ⭐ template 和 Deployment 完全一样，可以无缝迁移
  template:
    metadata:
      labels: {app: hello}
    spec:
      containers:
        - name: server
          image: ghcr.io/yourorg/hello:v2.0.0
          ports: [{name: http, containerPort: 8080}]
          readinessProbe:
            httpGet: {path: /readyz, port: http}
            periodSeconds: 3
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {memory: 512Mi}

  strategy:
    canary:
      canaryService: hello-canary      # 只指向新版本 Pod
      stableService: hello-stable      # 只指向稳定版 Pod

      # ⭐ 用 Gateway API 做精确的流量切分（第 10 章）
      trafficRouting:
        plugins:
          argoproj-labs/gatewayAPI:
            httpRoute: hello-route
            namespace: prod
        # 也支持：istio、nginx、alb、smi、traefik、apisix 等

      # ⭐ 金丝雀的步骤定义
      steps:
        - setWeight: 5
        - pause: {duration: 5m}          # 暂停 5 分钟（期间 analysis 在跑）
        - setWeight: 20
        - pause: {duration: 5m}
        - setWeight: 50
        - pause: {duration: 10m}
        - setWeight: 100
        # - pause: {}                     # 无参数 = 无限期暂停，等人工 promote

      # ⭐ 后台持续分析：任何一步失败立即回滚
      analysis:
        templates:
          - templateName: success-rate
          - templateName: latency-p99
        startingStep: 1                  # 从第 1 步开始分析
        args:
          - name: service-name
            value: hello-canary

      # 更保守的做法：每一步单独分析
      # steps:
      #   - setWeight: 5
      #   - analysis:
      #       templates: [{templateName: success-rate}]
      #   - setWeight: 20

      maxSurge: "25%"
      maxUnavailable: 0

      antiAffinity:                      # 让 canary 和 stable 分开部署
        preferredDuringSchedulingIgnoredDuringExecution:
          weight: 100
```

### 3.3 AnalysisTemplate：指标验证

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata: {name: success-rate}
spec:
  args:
    - name: service-name
  metrics:
    - name: success-rate
      interval: 1m                       # 每分钟查一次
      count: 5                           # 一共查 5 次
      successCondition: result[0] >= 0.99
      failureLimit: 2                    # 允许 2 次失败（避免抖动误判）
      inconclusiveLimit: 3
      provider:
        prometheus:
          address: http://monitoring-kube-prometheus-prometheus.monitoring:9090
          query: |
            sum(rate(http_requests_total{
              service="{{args.service-name}}", status!~"5.."
            }[2m]))
            /
            sum(rate(http_requests_total{
              service="{{args.service-name}}"
            }[2m]))
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata: {name: latency-p99}
spec:
  args:
    - name: service-name
  metrics:
    - name: p99
      interval: 1m
      count: 5
      successCondition: result[0] <= 0.5      # P99 ≤ 500ms
      failureLimit: 2
      provider:
        prometheus:
          address: http://monitoring-kube-prometheus-prometheus.monitoring:9090
          query: |
            histogram_quantile(0.99,
              sum(rate(http_request_duration_seconds_bucket{
                service="{{args.service-name}}"
              }[2m])) by (le))
```

**支持的指标源**：Prometheus、Datadog、New Relic、Wavefront、CloudWatch、Graphite、InfluxDB、Kayenta（Netflix 的自动金丝雀分析）、Job（跑一个 Job 做任意检查）、Web（调 HTTP 接口）。

**用 Job 做自定义验证**（很实用）：

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata: {name: smoke-test}
spec:
  metrics:
    - name: smoke
      provider:
        job:
          spec:
            backoffLimit: 0
            template:
              spec:
                restartPolicy: Never
                containers:
                  - name: test
                    image: ghcr.io/yourorg/e2e-tests:latest
                    command: ["./run-smoke-tests.sh", "http://hello-canary"]
```

### 3.4 Blue-Green

```yaml
strategy:
  blueGreen:
    activeService: hello-active         # 生产流量
    previewService: hello-preview       # 预览（内部验证用）

    autoPromotionEnabled: false         # ⭐ false = 需要人工/自动分析后才切流
    autoPromotionSeconds: 300           # 或者等 5 分钟自动切

    scaleDownDelaySeconds: 600          # ⭐ 切流后旧版本保留 10 分钟（方便秒回滚）
    scaleDownDelayRevisionLimit: 2

    prePromotionAnalysis:               # ⭐ 切流前跑验证（对 preview service）
      templates: [{templateName: smoke-test}]
      args:
        - name: service-name
          value: hello-preview

    postPromotionAnalysis:              # 切流后继续验证
      templates: [{templateName: success-rate}]
      args:
        - name: service-name
          value: hello-active

    antiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution: {}
```

### 3.5 操作命令

```bash
# ⭐ 实时观察发布进度（最常用）
kubectl argo rollouts get rollout hello --watch

# 触发发布
kubectl argo rollouts set image hello server=ghcr.io/yourorg/hello:v2.0.0

# 控制
kubectl argo rollouts promote hello              # 推进到下一步
kubectl argo rollouts promote hello --full       # 跳过所有剩余步骤，直接完成
kubectl argo rollouts pause hello
kubectl argo rollouts abort hello                # ⭐ 中止并回滚到 stable
kubectl argo rollouts retry hello
kubectl argo rollouts undo hello                 # 回到上一个版本
kubectl argo rollouts undo hello --to-revision=3

kubectl argo rollouts status hello               # CI 里等待用
kubectl argo rollouts list rollouts

# Dashboard（本地 UI）
kubectl argo rollouts dashboard      # → localhost:3100
```

---

## 4. 与 Argo CD 集成

Argo CD 原生认识 `Rollout` 对象（有内置的健康检查逻辑）：

```
Git 里 image tag 变化
  → Argo CD 同步 Rollout 对象
    → Argo Rollouts 控制器开始渐进式发布
      → 指标分析
        → 通过：继续；失败：自动回滚（Rollout 回到 stable）
```

⚠️ **一个重要的交互细节**：Rollouts 自动回滚后，集群状态（stable 版本）≠ Git 状态（新版本），Argo CD 会显示 `OutOfSync`，且如果开了 `selfHeal` 会试图再次同步 → **可能陷入"发布-回滚-再发布"的循环**。

**处理方式**：
- Rollout 中止后是 `Degraded` 状态，Argo CD 不会认为它 Healthy，但 selfHeal 仍可能重试
- 实践中：让告警通知人来处理，或在 Argo CD 里对该 App 关闭 selfHeal
- 或者用 Rollouts 的 `progressDeadlineAbort` + 通知，让人工介入决策

---

## 5. 数据库与向后兼容（最容易被忽视的部分）

**任何渐进式发布都意味着新旧版本会同时在跑。** 这对数据层提出硬性要求：

### 5.1 Expand-Contract（扩展-收缩）模式

想给 `users` 表把 `name` 拆成 `first_name` + `last_name`：

```
❌ 错误做法：一次发布搞定
   迁移脚本：ALTER TABLE users DROP COLUMN name, ADD first_name, ADD last_name
   → 旧版本代码立刻全部报错

✅ 正确做法：4 次发布
   发布 1（Expand）：加 first_name/last_name 列（可空）
                     代码：写时双写（name + first/last），读 name
   发布 2：          代码：读 first/last（有值则用，没值 fallback 到 name）
                     数据回填：UPDATE users SET first_name=... WHERE first_name IS NULL
   发布 3：          代码：不再写 name
   发布 4（Contract）：DROP COLUMN name
```

每一步都保证**新旧版本能同时工作**。

### 5.2 API 兼容性

同样的道理适用于 gRPC/HTTP API：
- 加字段：安全（proto3 的字段都是可选的）
- 删字段/改语义：必须走 expand-contract
- 改字段编号（proto）：绝对禁止

### 5.3 其他共享状态

| 共享状态 | 注意事项 |
|---|---|
| 缓存（Redis） | 序列化格式变了 → 新旧版本互相读不懂。加版本前缀 key |
| 消息队列 | 新版本发的消息，旧版本消费者要能处理（或反之） |
| 定时任务 | 两个版本可能同时跑同一个任务 → 加分布式锁 |
| 文件格式 | 同上 |

---

## 6. 特性开关（Feature Flags）：另一个维度

渐进式**部署**和渐进式**发布功能**是两回事：

```
部署（deploy）：把新代码放到生产环境       ← Argo Rollouts 解决
发布（release）：让用户看到新功能           ← Feature Flag 解决
```

**把两者解耦的好处**：
- 代码可以随时部署（哪怕功能没做完，藏在 flag 后面）
- 功能可以随时开关，**不需要重新部署**（秒级止损）
- 可以按用户/地区/百分比精细控制
- A/B 测试、灰度放量都在应用层完成

```go
// 用 OpenFeature（CNCF 标准）或 Unleash / Flagsmith / LaunchDarkly
if flags.BoolVariation(ctx, "new-checkout-flow", user, false) {
    return newCheckout(ctx, req)
}
return legacyCheckout(ctx, req)
```

**实践建议**：
- 高风险的业务逻辑变更 → 用 feature flag（能秒级关掉）
- 基础设施/依赖升级 → 用金丝雀部署（没法用 flag 控制）
- 两者结合威力最大：金丝雀部署新代码 + flag 控制功能开启

⚠️ **flag 债务**：flag 用完要清理，否则代码里会积累几百个永远为 true 的分支。给每个 flag 设过期日期。

---

## 7. 动手实验

### 实验 1：安装 Argo Rollouts

```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
kubectl -n argo-rollouts rollout status deploy/argo-rollouts --timeout=180s
brew install argoproj/tap/kubectl-argo-rollouts
kubectl argo rollouts version
```

### 实验 2：⭐ 基于副本数的金丝雀（不需要流量路由，最容易上手）

```bash
kubectl create ns rollouts && kubectl config set-context --current --namespace=rollouts

kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata: {name: hello}
spec:
  replicas: 10
  strategy:
    canary:
      steps:
        - setWeight: 10
        - pause: {duration: 30s}
        - setWeight: 30
        - pause: {duration: 30s}
        - setWeight: 60
        - pause: {duration: 30s}
        - setWeight: 100
      maxSurge: "25%"
      maxUnavailable: 0
  selector:
    matchLabels: {app: hello}
  template:
    metadata: {labels: {app: hello}}
    spec:
      containers:
        - name: server
          image: argoproj/rollouts-demo:blue
          ports: [{name: http, containerPort: 8080}]
          readinessProbe:
            httpGet: {path: /color, port: http}
            periodSeconds: 2
          resources:
            requests: {cpu: 10m, memory: 32Mi}
---
apiVersion: v1
kind: Service
metadata: {name: hello}
spec:
  selector: {app: hello}
  ports: [{port: 80, targetPort: http}]
EOF

kubectl argo rollouts get rollout hello --watch
# Ctrl-C 退出观察
```

**触发一次金丝雀发布**：

```bash
# 一个终端持续观察
kubectl argo rollouts get rollout hello --watch &

# 另一个（或直接执行）触发更新
kubectl argo rollouts set image hello server=argoproj/rollouts-demo:yellow
```

观察输出（这个可视化非常直观）：

```
Name:            hello
Status:          ॥ Paused
Message:         CanaryPauseStep
Strategy:        Canary
  Step:          1/7
  SetWeight:     10
  ActualWeight:  10
Images:          argoproj/rollouts-demo:blue (stable)
                 argoproj/rollouts-demo:yellow (canary)
Replicas:
  Desired:       10
  Current:       11
  Updated:       1        ← 只有 1 个新版本
  Ready:         11
  Available:     11

NAME                               KIND        STATUS     AGE  INFO
⟳ hello                            Rollout     ॥ Paused   5m
├──# revision:2
│  └──⧉ hello-6cf78c9f5            ReplicaSet  ✔ Healthy  30s  canary
│     └──□ hello-6cf78c9f5-xk2mn   Pod         ✔ Running  30s  ready:1/1
└──# revision:1
   └──⧉ hello-7d4b8c6d9            ReplicaSet  ✔ Healthy  5m   stable
      ├──□ hello-7d4b8c6d9-abc12   Pod         ✔ Running  5m   ready:1/1
      └── ... (9 个)
```

### 实验 3：⭐ 手工推进与中止

```bash
# 把 steps 改成无限期暂停
kubectl patch rollout hello --type merge -p '
{"spec":{"strategy":{"canary":{"steps":[
  {"setWeight":10},{"pause":{}},
  {"setWeight":50},{"pause":{}},
  {"setWeight":100}]}}}}'

kubectl argo rollouts set image hello server=argoproj/rollouts-demo:green
kubectl argo rollouts get rollout hello        # Paused at step 1

# 推进
kubectl argo rollouts promote hello
kubectl argo rollouts get rollout hello        # 50%

# ⭐ 发现问题！中止
kubectl argo rollouts abort hello
kubectl argo rollouts get rollout hello
# Status: ✖ Degraded，所有流量回到 stable（green 的 Pod 被缩到 0）

kubectl get pods -l app=hello
# 只剩 stable 版本 ✅

# 恢复（回到稳定版）
kubectl argo rollouts undo hello
```

### 实验 4：Blue-Green

```bash
kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata: {name: bg}
spec:
  replicas: 4
  strategy:
    blueGreen:
      activeService: bg-active
      previewService: bg-preview
      autoPromotionEnabled: false
      scaleDownDelaySeconds: 60
  selector:
    matchLabels: {app: bg}
  template:
    metadata: {labels: {app: bg}}
    spec:
      containers:
        - name: server
          image: argoproj/rollouts-demo:blue
          ports: [{name: http, containerPort: 8080}]
          readinessProbe: {httpGet: {path: /color, port: http}, periodSeconds: 2}
          resources: {requests: {cpu: 10m, memory: 32Mi}}
---
apiVersion: v1
kind: Service
metadata: {name: bg-active}
spec: {selector: {app: bg}, ports: [{port: 80, targetPort: http}]}
---
apiVersion: v1
kind: Service
metadata: {name: bg-preview}
spec: {selector: {app: bg}, ports: [{port: 80, targetPort: http}]}
EOF

kubectl argo rollouts get rollout bg --watch &
sleep 20; kill %1

# 发新版本
kubectl argo rollouts set image bg server=argoproj/rollouts-demo:red
sleep 20
kubectl argo rollouts get rollout bg
# ⭐ 8 个 Pod（4 blue + 4 red），但 active service 还指向 blue

# 验证 preview
kubectl run -it --rm t --image=busybox:1.37 --restart=Never -- \
  sh -c 'echo "active:"; wget -qO- http://bg-active/color; echo; echo "preview:"; wget -qO- http://bg-preview/color'
# active: "blue"   preview: "red"   ⭐ 可以在 preview 上做完整验证

# 满意了，切流
kubectl argo rollouts promote bg
sleep 10
kubectl run -it --rm t --image=busybox:1.37 --restart=Never -- \
  sh -c 'wget -qO- http://bg-active/color'
# "red" ✅ 瞬间切换

# 60 秒内旧版本还在，可以秒回滚
kubectl argo rollouts undo bg
```

### 实验 5：Analysis 自动回滚

需要 Prometheus（第 13 章装的）。用一个必然失败的 analysis 演示自动回滚：

```bash
kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata: {name: always-fail}
spec:
  metrics:
    - name: fail
      interval: 10s
      count: 2
      failureLimit: 0
      successCondition: "result == 'ok'"
      provider:
        job:
          spec:
            backoffLimit: 0
            template:
              spec:
                restartPolicy: Never
                containers:
                  - name: check
                    image: busybox:1.37
                    command: ["sh","-c","echo 'simulating bad metrics'; exit 1"]
EOF

kubectl patch rollout hello --type merge -p '
{"spec":{"strategy":{"canary":{
  "steps":[{"setWeight":20},{"analysis":{"templates":[{"templateName":"always-fail"}]}},{"setWeight":100}]
}}}}'

kubectl argo rollouts set image hello server=argoproj/rollouts-demo:purple
kubectl argo rollouts get rollout hello --watch
# ⭐ 观察：canary 起来 → analysis 跑 → 失败 → 自动 Degraded 并回滚
# Ctrl-C

kubectl get analysisrun
kubectl describe analysisrun | tail -20
kubectl get pods -l app=hello        # 全是 stable 版本 ✅
```

**这就是渐进式交付的核心价值：坏版本永远上不了 100% 流量。**

### 实验 6：可视化 Dashboard

```bash
kubectl argo rollouts dashboard &
# 浏览器 localhost:3100 —— 图形化观察发布过程
```

### 清理

```bash
kubectl delete ns rollouts
kubectl config set-context --current --namespace=default
```

---

## 8. 实践建议

### 8.1 什么服务用什么策略

| 服务类型 | 推荐策略 |
|---|---|
| 无状态 HTTP API（高流量） | **Canary + 指标分析** ⭐ |
| 内部服务、低流量（金丝雀样本不足） | Blue-Green + 冒烟测试 |
| 后台 worker / 消息消费者 | Rolling（无 HTTP 流量可切分）+ 监控消费延迟 |
| 有状态服务（数据库） | StatefulSet 的 `partition`（第 9 章）+ 极度谨慎 |
| 高风险业务逻辑变更 | Canary + **Feature Flag** |
| 定时任务 | 蓝绿（新旧不能同时跑）或直接 Recreate |

### 8.2 金丝雀步骤设计

```yaml
# ❌ 太激进：5% → 100%，中间没有验证
steps: [{setWeight: 5}, {pause: {duration: 1m}}, {setWeight: 100}]

# ❌ 太保守：发布要 3 小时，团队会绕过流程
steps: [{setWeight: 1}, {pause: {duration: 30m}}, ...]

# ✅ 平衡：总耗时 20~30 分钟，指标有足够样本
steps:
  - setWeight: 5
  - pause: {duration: 5m}      # 5% 流量 × 5 分钟，足够统计错误率
  - setWeight: 25
  - pause: {duration: 5m}
  - setWeight: 50
  - pause: {duration: 5m}
  - setWeight: 100
```

**样本量考虑**：如果你的服务 QPS 是 10，5% 流量 = 0.5 QPS，5 分钟只有 150 个请求——统计上判断不出 1% 的错误率变化。**低流量服务不适合细粒度金丝雀**，用蓝绿 + 合成流量测试。

### 8.3 常见坑

| 坑 | 说明 |
|---|---|
| 指标没有区分 canary 和 stable | 必须在指标里带版本/Pod 标签，否则分析的是混合数据 |
| analysis 查询窗口太短 | `rate(...[2m])` 在刚发布时数据不足 → 加 `pause` 让指标积累 |
| 长连接不受权重控制 | gRPC/WebSocket 客户端连着不断开，权重改了也没用 → 设 `MaxConnectionAge` |
| 忘了数据库兼容 | 新旧版本同时跑，schema 必须双向兼容 |
| Argo CD selfHeal 和 Rollouts 打架 | 见 §4 |
| 回滚后 canary Pod 还在 | 检查 `scaleDownDelaySeconds` |
| 发布流程太长团队绕过 | 设计成 20~30 分钟内完成，并且要有"紧急直发"通道 |

---

## 9. 本章检查清单

- [ ] RollingUpdate 的根本缺陷是什么？举 3 个它发现不了的问题
- [ ] 蓝绿和金丝雀的取舍是什么？各自的资源开销和爆炸半径？
- [ ] 两种流量切分方式的区别？为什么副本数比例不够精确？
- [ ] Rollout CRD 和 Deployment 的关系？迁移成本大吗？
- [ ] AnalysisTemplate 的 `successCondition`、`failureLimit`、`count`、`interval` 分别是什么意思？
- [ ] Argo CD 的 selfHeal 和 Rollouts 的自动回滚会怎么冲突？
- [ ] Expand-Contract 模式的 4 个步骤是什么？为什么必须这样做？
- [ ] "部署"和"发布"的区别？Feature Flag 解决什么问题？
- [ ] 低流量服务为什么不适合细粒度金丝雀？
- [ ] 完成实验 2、3、4、5

---

## 10. 阶段三小结

到这里你应该已经具备：

- ✅ 用 Helm 或 Kustomize 把清单参数化，管理多环境
- ✅ 用 Jenkins（或任意 CI）构建不可变镜像并推仓库
- ✅ 用 Argo CD 建立 GitOps 交付流程
- ✅ 用 Argo Rollouts 做带自动回滚的渐进式发布
- ✅ 理解 CI/CD 分离、拉模型、Git 作为唯一真相源

**完整链路**：

```
git push（代码）
  → Jenkins：test → build → scan → push image
    → Jenkins：更新配置仓的 image.tag
      → Argo CD：检测到 Git 变化 → 同步 Rollout
        → Argo Rollouts：5% → 分析 → 25% → 分析 → 100%
          → 指标异常 → 自动回滚 + 告警
```

第 20 章会把这条链路完整地跑一遍。

---

## 11. 延伸阅读

- [Argo Rollouts 文档](https://argo-rollouts.readthedocs.io/)
- [Progressive Delivery（Weaveworks）](https://www.weave.works/blog/progressive-delivery-checklist)
- [Flagger](https://flagger.app/)（Flux 生态的渐进式交付工具）
- [OpenFeature](https://openfeature.dev/)（CNCF 的 feature flag 标准）
- Martin Fowler, [BlueGreenDeployment](https://martinfowler.com/bliki/BlueGreenDeployment.html) / [CanaryRelease](https://martinfowler.com/bliki/CanaryRelease.html)
- [Evolutionary Database Design](https://martinfowler.com/articles/evodb.html)（expand-contract 的出处）

---

下一章：[20 - 端到端实战：Go 服务全链路交付](./20-end-to-end-lab.md)
