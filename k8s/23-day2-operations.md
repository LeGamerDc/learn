# 23 - Day-2 运维：持续运营一个生产系统

> 本章目标：从"能部署"到"能持续运维"。SLO、告警设计、值班、事故响应、变更管理、
> 升级节奏、演练——这些是把系统长期跑好的东西。
> 预计用时：2.5 小时（本章是方法论 + 模板，可以直接拿去用）。

---

## 1. Day-0 / Day-1 / Day-2

| 阶段 | 内容 | 前面的章节 |
|---|---|---|
| **Day-0** | 设计、选型、架构决策 | 1、5、6、21 |
| **Day-1** | 搭建、部署、上线 | 7~20 |
| **Day-2** | **持续运营**：监控、告警、升级、扩容、排障、优化、演练 | 本章 |

**Day-2 占了系统生命周期 95% 以上的时间和成本。** 大多数团队在 Day-1 投入了 90% 的精力，然后在 Day-2 痛苦挣扎。

---

## 2. SLI / SLO / 错误预算

### 2.1 为什么需要 SLO

没有 SLO 的团队：
- "系统是不是健康？"——不知道，看感觉
- "能不能发布？"——不知道，看胆量
- "该投入优化性能还是做新功能？"——吵架

**SLO 把这些变成数据决策。**

| 概念 | 定义 | 例子 |
|---|---|---|
| **SLI**（指标） | 衡量服务质量的**具体数值** | 成功请求数 / 总请求数 |
| **SLO**（目标） | SLI 的**目标值** | 30 天内成功率 ≥ 99.9% |
| **SLA**（协议） | 对**外部**的承诺（违约有赔偿） | 99.5%，否则退款 |
| **错误预算** | `1 - SLO` | 99.9% → 0.1% → 30 天里可以有 **43 分钟**不可用 |

**错误预算是最有价值的概念**：它把"稳定性"和"迭代速度"的矛盾变成了一个可量化的账户。

```
预算充足（用了 20%）  → 大胆发布，可以上激进的变更
预算紧张（用了 80%）  → 放慢发布，优先修稳定性问题
预算耗尽（用了 100%）→ 冻结功能发布，全员修稳定性
```

### 2.2 定义 SLI（针对 Go HTTP 服务）

**用户视角的四个黄金信号**（Google SRE）：

| 信号 | SLI 定义 | PromQL |
|---|---|---|
| **可用性（Availability）** | 非 5xx 响应比例 | `sum(rate(http_requests_total{status!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` |
| **延迟（Latency）** | 延迟 < 阈值的请求比例 | `sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m])) / sum(rate(http_request_duration_seconds_count[5m]))` |
| **流量（Traffic）** | QPS | `sum(rate(http_requests_total[5m]))` |
| **饱和度（Saturation）** | 资源使用率 | CPU/内存/连接池/队列深度 |

⚠️ **要点**：
- SLI 要从**用户视角**衡量。"Pod 是 Running"不是 SLI，"用户请求成功"才是
- 排除掉不该算的：健康检查请求、爬虫、明确的客户端错误（400）
- 延迟 SLI 用"低于阈值的比例"而不是"P99 的值"——前者能直接算进错误预算

### 2.3 用 Prometheus 实现

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: orders-slo
  labels: {release: monitoring}
spec:
  groups:
    - name: orders.sli
      interval: 30s
      rules:
        # SLI：可用性
        - record: sli:availability:ratio_rate5m
          expr: |
            sum(rate(http_requests_total{service="orders",route!="/health",status!~"5.."}[5m]))
              / sum(rate(http_requests_total{service="orders",route!="/health"}[5m]))

        # SLI：延迟（300ms 内的比例）
        - record: sli:latency:ratio_rate5m
          expr: |
            sum(rate(http_request_duration_seconds_bucket{service="orders",le="0.3"}[5m]))
              / sum(rate(http_request_duration_seconds_count{service="orders"}[5m]))

        # 30 天错误预算消耗率
        - record: slo:error_budget_consumed:ratio30d
          expr: |
            (1 - (
              sum(increase(http_requests_total{service="orders",status!~"5.."}[30d]))
                / sum(increase(http_requests_total{service="orders"}[30d]))
            )) / 0.001
            # 分母 0.001 = 1 - 0.999（SLO 99.9%）
```

### 2.4 基于燃烧率的告警（⭐ 现代告警设计）

**传统告警的问题**：`错误率 > 1% 持续 5 分钟` → 半夜被一个 5 分钟的小抖动叫醒，但那对月度 SLO 毫无影响。

**燃烧率（burn rate）告警**：只在"以当前速度会烧光错误预算"时才告警。

```
燃烧率 = 当前错误率 / (1 - SLO)

燃烧率 = 1  → 正好在 30 天用完预算（正常）
燃烧率 = 14 → 2 天就用完 → 紧急！
```

多窗口多燃烧率（Google SRE Workbook 推荐）：

```yaml
        # ⭐ 快速燃烧：1 小时内烧掉 2% 预算 → 立即呼叫（会在 ~2 天烧光）
        - alert: OrdersErrorBudgetBurnFast
          expr: |
            (1 - sli:availability:ratio_rate5m) > (14.4 * 0.001)
            and
            (1 - sli:availability:ratio_rate1h) > (14.4 * 0.001)
          for: 2m
          labels: {severity: critical, team: payments}
          annotations:
            summary: "orders 错误预算快速消耗（燃烧率 14.4x）"
            runbook_url: "https://wiki.internal/runbooks/orders-high-error-rate"
            dashboard_url: "https://grafana.internal/d/orders"

        # ⭐ 慢速燃烧：6 小时窗口 → 进工单，工作时间处理
        - alert: OrdersErrorBudgetBurnSlow
          expr: |
            (1 - sli:availability:ratio_rate30m) > (6 * 0.001)
            and
            (1 - sli:availability:ratio_rate6h) > (6 * 0.001)
          for: 15m
          labels: {severity: warning, team: payments}
```

**双窗口（短 + 长）的作用**：短窗口保证响应快，长窗口过滤掉瞬时抖动。

---

## 3. 告警设计

### 3.1 三条铁律

1. **每条告警都必须要求人立刻做点什么。** 不需要行动的 → 做成 Dashboard，不要告警。
2. **每条告警必须有 runbook。** 半夜被叫醒的人不该现场思考。
3. **定期审查。** 每月看：哪些告警从没触发过（删掉）？哪些触发了但没人处理（降级或删掉）？哪些是误报（修）？

### 3.2 告警分级

| 级别 | 触发条件 | 通知方式 | 响应时间 |
|---|---|---|---|
| **P1 / critical** | 用户明显受影响，错误预算快速燃烧 | 电话 / PagerDuty，7×24 | 5 分钟 |
| **P2 / warning** | 有风险但用户未受影响（磁盘 80%、证书 7 天到期） | IM / 工单，工作时间 | 1 工作日 |
| **P3 / info** | 记录，无需响应 | Dashboard / 日志 | — |

### 3.3 必备的告警清单

**业务/服务层（SLO 驱动）**：
- [ ] 错误预算快速燃烧（P1）
- [ ] 错误预算慢速燃烧（P2）
- [ ] 服务完全不可用（所有副本不 Ready）（P1）

**工作负载层**：
- [ ] Pod CrashLoopBackOff 持续 > 15 分钟（P2）
- [ ] Deployment 可用副本数 < 期望值持续 > 15 分钟（P2）
- [ ] Pod 频繁重启（1 小时 > 5 次）（P2）
- [ ] OOMKilled 发生（P2）
- [ ] CPU 节流率 > 25% 持续 10 分钟（P3/P2）
- [ ] HPA 达到 maxReplicas（P2，说明容量不够）
- [ ] Job 失败 / CronJob 长时间没成功执行（P2）

**基础设施层**：
- [ ] 节点 NotReady（P1）
- [ ] 节点 DiskPressure / MemoryPressure（P2）
- [ ] 节点磁盘使用率 > 85%（P2）
- [ ] PVC 使用率 > 85%（P2）
- [ ] 证书 30 天内过期（P2）、7 天内（P1）
- [ ] etcd 数据库大小 > 70% 配额（P2）
- [ ] etcd fsync 延迟 P99 > 100ms（P2）
- [ ] apiserver 请求延迟 P99 异常（P2）
- [ ] apiserver 429 限流增加（P2）

**交付层**：
- [ ] Argo CD Application 长时间 OutOfSync / Degraded（P2）
- [ ] Argo Rollouts 分析失败导致自动回滚（P1，需要人看）
- [ ] 镜像仓库不可达（P2）

**可观测性自身**（**别忘了监控监控系统**）：
- [ ] Prometheus target down（P2）
- [ ] Prometheus 存储快满（P2）
- [ ] 指标停止上报（"死人开关"告警）（P1）

### 3.4 Alertmanager 配置要点

```yaml
route:
  group_by: [alertname, cluster, namespace, service]
  group_wait: 30s              # 等 30 秒攒一批
  group_interval: 5m
  repeat_interval: 4h
  receiver: default
  routes:
    - matchers: [severity="critical"]
      receiver: pagerduty
      group_wait: 10s
      repeat_interval: 1h
    - matchers: [severity="warning"]
      receiver: feishu
    - matchers: [namespace=~"dev|staging"]
      receiver: dev-channel
      repeat_interval: 24h

inhibit_rules:
  # ⭐ 节点挂了就别报上面所有 Pod 的告警了
  - source_matchers: [alertname="NodeNotReady"]
    target_matchers: [severity=~"warning|critical"]
    equal: [node]
  # 服务完全挂了就别报延迟告警
  - source_matchers: [alertname="ServiceDown"]
    target_matchers: [alertname="HighLatency"]
    equal: [service]
```

**抑制规则（inhibit）非常重要**：一个节点挂掉会触发几十条告警，抑制规则让值班的人只看到根因那一条。

---

## 4. Runbook 模板

每条 P1/P2 告警都要有一份。**放在 Git 里，和代码一起 review。**

```markdown
# Runbook: OrdersErrorBudgetBurnFast

## 影响
orders 服务错误率异常升高，用户下单可能失败。
影响面：所有下单用户。

## 快速判断（2 分钟内完成）
1. Dashboard: https://grafana.internal/d/orders
   - 错误集中在哪个路由？哪个版本？哪个 Pod？哪个可用区？
2. 最近有变更吗？
   - `argocd app history orders-prod`
   - `kubectl -n prod rollout history deploy/orders`
   - 配置仓最近的提交

## 常见原因与处置

### ① 刚发布过（最常见）
→ **立刻回滚**：
   git revert <commit> && git push    # GitOps 方式
   或 kubectl argo rollouts abort orders -n prod
   或 kubectl rollout undo deploy/orders -n prod
→ 确认错误率恢复后再定位根因

### ② 依赖故障（数据库/缓存/下游）
   kubectl -n prod get pods -l app=postgres
   kubectl -n prod logs deploy/orders --tail=100 | grep -i "error\|timeout"
→ 修依赖；如果依赖短时间恢复不了，考虑降级开关：
   （feature flag：关掉依赖该服务的功能）

### ③ 流量突增
   查看 QPS 面板
→ 手工扩容：kubectl -n prod scale deploy/orders --replicas=20
→ 确认 HPA 上限和节点容量

### ④ 资源问题（OOM / 节流）
   kubectl -n prod get pods | grep -v Running
   kubectl -n prod describe pod <pod> | grep -A5 "Last State"
→ 临时提高 limit；后续做 right-sizing

## 升级路径
15 分钟内未恢复 → 拉起故障群，通知 @backend-lead
30 分钟内未恢复 → 通知业务方，评估是否公告

## 相关
- 代码仓：github.com/yourorg/orders
- 配置仓：github.com/yourorg/k8s-config/apps/orders
- 负责团队：@payments-team
- SLO：99.9% 可用性
```

---

## 5. 变更管理

**统计上，绝大多数生产事故由变更引起。** 所以变更管理是稳定性投入回报率最高的地方。

### 5.1 变更的分级

| 级别 | 例子 | 要求 |
|---|---|---|
| **低风险** | dev 环境任何变更、日志级别调整、扩容 | 自动化，无需审批 |
| **中风险** | 生产的常规服务发布 | PR review + 自动金丝雀 + 可回滚 |
| **高风险** | 数据库 schema 变更、K8s 版本升级、CNI/存储变更、网络策略变更 | 计划 + 演练 + 审批 + 变更窗口 + 回滚预案 |

### 5.2 生产变更检查清单

发起任何生产变更前：

- [ ] 在 dev/staging 验证过
- [ ] 有明确的回滚方案，且回滚方案被验证过
- [ ] 变更是向后兼容的（新旧版本会共存，第 19 章）
- [ ] 不在业务高峰期 / 不在周五下午 / 不在长假前
- [ ] 错误预算充足
- [ ] 有人盯着监控（至少 30 分钟）
- [ ] 相关人知情（IM 通知）
- [ ] 变更记录可追溯（Git commit / 变更单）

### 5.3 变更冻结

约定明确的冻结期：大促、双十一、春节、重要发布前。冻结期只允许 P1 故障修复，且需要审批。

Argo CD 的 `syncWindows` 可以技术上强制（第 18 章）：

```yaml
syncWindows:
  - kind: deny
    schedule: '0 0 * * *'
    duration: 24h
    applications: ['*-prod']
    manualSync: true          # 紧急时人工可以强推
```

### 5.4 GitOps 让变更管理自动具备

用了 GitOps（第 18 章）之后，你**免费**获得：
- 变更记录（git log）
- 变更审批（PR review + CODEOWNERS）
- 回滚（git revert）
- 审计（谁批准的、什么时候合的）
- 漂移检测（有人绕过流程手工改会被发现）

**这是 GitOps 最被低估的价值**——它不只是技术方案，是流程的载体。

---

## 6. 事故响应

### 6.1 角色

事故规模大时明确分工（小事故一个人兼）：

| 角色 | 职责 |
|---|---|
| **Incident Commander (IC)** | 协调、决策、不亲自动手 |
| **Ops Lead** | 实际操作（改配置、回滚、扩容） |
| **Comms** | 对内对外沟通、更新状态页 |
| **Scribe** | 记录时间线（给复盘用） |

### 6.2 处理流程

```
① 确认（Detect）
   告警触发 / 用户报障 → 值班确认是否真实

② 止血（Mitigate）⭐ 最重要
   目标：恢复服务，不是找根因
   手段：回滚 / 扩容 / 摘流量 / 降级开关 / 切备用集群
   ⚠️ 决不要为了"搞清楚原因"而延迟止血

③ 沟通（Communicate）
   内部：故障群同步进展（每 15~30 分钟一次）
   外部：状态页 / 客户通知（如果影响外部用户）

④ 定位（Diagnose）
   服务恢复后再慢慢查（第 22 章）

⑤ 修复（Fix）
   根因修复，走正常发布流程

⑥ 复盘（Postmortem）
   48 小时内完成
```

### 6.3 复盘模板（无指责文化）

```markdown
# 事故复盘：orders 服务不可用 30 分钟

## 概要
- 时间：2026-07-29 14:20 ~ 14:52（32 分钟）
- 影响：下单接口成功率降至 12%，约 8000 个订单失败
- 严重级别：P1
- 错误预算消耗：本月预算的 74%

## 时间线（UTC+8）
| 时间 | 事件 |
|---|---|
| 14:15 | 发布 orders v2.3.0（Argo CD 自动同步） |
| 14:20 | 告警 OrdersErrorBudgetBurnFast 触发 |
| 14:22 | 值班确认，进入故障处理 |
| 14:31 | 定位到是新版本引起（对比版本标签的错误率） |
| 14:33 | 执行 git revert 并同步 |
| 14:52 | 错误率恢复正常 |

## 根因
v2.3.0 引入了对 Redis 的新调用，但生产的 Redis 连接池配置最大 10 个连接，
高峰期连接耗尽导致请求阻塞超时。staging 环境流量低，未暴露该问题。

## 为什么没有更早发现
1. 金丝雀分析窗口只有 1 分钟，连接池耗尽需要 3 分钟才出现
2. 连接池使用率没有指标，Dashboard 上看不到
3. staging 没有生产级流量回放

## 做得好的地方 ✅
- 告警在 5 分钟内触发
- GitOps 让回滚只用了 2 分钟
- 故障群沟通及时

## 改进项（有负责人和期限）
| # | 行动 | 负责人 | 期限 | 状态 |
|---|---|---|---|---|
| 1 | 给连接池加 Prometheus 指标和告警 | @alice | 08-05 | 进行中 |
| 2 | 金丝雀分析窗口从 1 分钟改为 5 分钟 | @bob | 08-02 | 完成 |
| 3 | staging 加流量回放（生产 5% 影子流量） | @carol | 08-30 | 待开始 |
| 4 | 把"依赖变更需要检查连接池配置"加进发布 checklist | @alice | 08-05 | 完成 |

## 无指责声明
本复盘关注系统和流程的改进，不追究个人责任。
任何人在同样的信息和压力下都可能做出同样的决定。
```

**"无指责（blameless）"不是形式主义**：如果复盘会变成追责会，下次就没人愿意如实说出细节，你就永远学不到真正的教训。

---

## 7. 例行运维节奏

### 每日
- [ ] 看值班交接（昨天有什么告警？处理了吗？）
- [ ] 扫一眼集群健康 Dashboard
- [ ] 检查失败的 Job / CronJob
- [ ] 检查 Argo CD 里 Degraded / OutOfSync 的应用

### 每周
- [ ] 审查告警：误报？漏报？没人处理的？
- [ ] 检查证书到期情况
- [ ] 检查备份是否成功
- [ ] 检查资源趋势（有没有异常增长）
- [ ] 处理安全扫描发现的高危漏洞

### 每月
- [ ] SLO 回顾：错误预算用了多少？趋势如何？
- [ ] 成本回顾：分配率/利用率/浪费率（第 21 章）
- [ ] 容量规划：按增长趋势，什么时候需要扩容？
- [ ] 依赖和基础镜像更新（拿 CVE 修复）
- [ ] 复盘改进项的进度跟踪

### 每季度
- [ ] **K8s 版本升级**（每年 3 个版本，别落后）
- [ ] **灾难恢复演练**（第 21 章）
- [ ] 权限审查（谁有什么权限，还需要吗）
- [ ] 混沌工程演练
- [ ] Runbook 有效性检查（找个新人按 runbook 走一遍）

---

## 8. 混沌工程

**在可控的条件下主动制造故障，验证系统的韧性。**

原则：
1. 从**非生产环境**开始
2. 有明确的**假设**（"杀掉一个 Pod，服务应该无感知"）
3. 最小化**爆炸半径**
4. 有**中止开关**
5. 在**工作时间**做，有人盯着

### 8.1 演练清单（从易到难）

| 演练 | 期望结果 | 怎么做 |
|---|---|---|
| 杀一个 Pod | 无感知 | `kubectl delete pod <pod>` |
| 杀掉某服务的全部 Pod | 短暂中断后自愈 | `kubectl delete pods -l app=x` |
| drain 一个节点 | 无感知（PDB + 多副本） | `kubectl drain <node>` |
| 关掉一个可用区的所有节点 | 无感知（拓扑分布） | cordon+drain 该 zone 的节点 |
| 注入网络延迟 | 超时和重试正常工作 | Chaos Mesh / Litmus |
| 注入 DNS 故障 | 有缓存/降级 | Chaos Mesh |
| 数据库主库故障 | 自动 failover | 停掉主库 Pod |
| 依赖服务返回 500 | 熔断/降级生效 | Chaos Mesh HTTP fault |
| 磁盘写满 | 有告警，不影响其他服务 | 往 emptyDir 写大文件 |
| 镜像仓库不可用 | 已运行的服务不受影响 | 断网/改 DNS |
| **删掉整个集群** | 从 Git 重建（第 21 章） | 新建集群 + apply root-app |

### 8.2 工具

```bash
# Chaos Mesh（CNCF）
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace
```

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata: {name: pod-kill-test, namespace: chaos-mesh}
spec:
  action: pod-kill
  mode: one                      # one | all | fixed | fixed-percent
  selector:
    namespaces: [staging]
    labelSelectors: {app: orders}
  duration: "30s"
---
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata: {name: delay-test, namespace: chaos-mesh}
spec:
  action: delay
  mode: all
  selector:
    namespaces: [staging]
    labelSelectors: {app: postgres}
  delay:
    latency: "200ms"
    jitter: "50ms"
  duration: "5m"
```

---

## 9. 容量规划

### 9.1 需要回答的问题

1. 当前容量能撑多久？（按增长趋势）
2. 大促/峰值需要多少容量？
3. 单个服务的极限 QPS 是多少？
4. 扩容需要多长时间？（节点扩容 + Pod 启动 + 预热）

### 9.2 方法

```promql
# 增长趋势：预测 30 天后的资源需求
predict_linear(sum(kube_pod_container_resource_requests{resource="cpu"})[7d:1h], 30*24*3600)

# 距离节点容量上限还有多远
sum(kube_pod_container_resource_requests{resource="cpu"}) / sum(kube_node_status_allocatable{resource="cpu"})

# 单服务的容量水位
sum(rate(http_requests_total{service="orders"}[5m])) / count(kube_pod_info{...})    # 每副本 QPS
```

### 9.3 压测

定期做（至少大促前）：

```bash
# k6（推荐，脚本用 JS，能跑在 K8s 里）
kubectl run k6 --image=grafana/k6:latest --restart=Never -- \
  run --vus 200 --duration 5m - <<'EOF'
import http from 'k6/http';
import { check } from 'k6';
export const options = {
  thresholds: {
    http_req_duration: ['p(99)<500'],
    http_req_failed: ['rate<0.01'],
  },
};
export default function () {
  const res = http.get('http://orders.prod.svc.cluster.local/');
  check(res, { 'status 200': (r) => r.status === 200 });
}
EOF
```

**压测时要观察的**：
- 服务的 QPS 上限和对应的延迟曲线（找拐点）
- HPA 是否及时扩容
- 依赖（数据库连接池、缓存）是否先成为瓶颈
- 节点是否够（会不会 Pending）
- 有没有触发限流/节流

---

## 10. 值班（On-Call）

### 10.1 健康的值班

| 指标 | 健康值 |
|---|---|
| 每次值班的告警数 | **< 2 次/天**（超过说明告警质量差） |
| 夜间被叫醒次数 | **< 1 次/周** |
| 值班轮换周期 | 1 周，至少 6 人一组（不要少于 4 人） |
| 值班后补偿 | 调休或补贴 |
| 告警误报率 | < 10% |

**如果值班很痛苦，问题在系统和告警质量，不在值班的人。** 把"减少告警噪音"作为明确的工程任务排期。

### 10.2 值班交接

```markdown
## 值班交接 2026-07-29

### 未解决的问题
- orders 服务偶发 5s 超时（怀疑 DNS，已提 issue #1234，@alice 跟进）

### 本周告警统计
- P1: 1 次（已复盘）
- P2: 7 次（5 次是磁盘告警误报，已调阈值）

### 需要注意
- 周三有 K8s 1.36 升级窗口，staging 已完成
- payments 团队周四发大版本

### 环境变更
- 新增 node-pool: memory-optimized（3 节点）
```

### 10.3 新人上岗前必须

- [ ] 完成本课程（或等价培训）
- [ ] 有生产环境的只读权限 + 明确的提权流程
- [ ] 跟班值守至少 2 轮
- [ ] 独立处理过至少 3 次 P2 告警
- [ ] 演练过一次回滚
- [ ] 知道所有 runbook 在哪、升级路径找谁

---

## 11. 文档

**最低限度必须有的文档**：

| 文档 | 内容 |
|---|---|
| **架构图** | 服务依赖关系、数据流、外部依赖 |
| **服务目录** | 每个服务：负责人、代码仓、配置仓、Dashboard、SLO、runbook |
| **Runbook** | 每条 P1/P2 告警一份 |
| **On-call 手册** | 权限申请、升级路径、沟通渠道、常用命令 |
| **变更流程** | 谁能改什么、需要什么审批 |
| **灾难恢复预案** | RTO/RPO、恢复步骤、演练记录 |
| **决策记录（ADR）** | 为什么选 A 不选 B（半年后你会感谢自己） |

**文档必须和代码在一起**（放 Git，走 PR），否则一定会过期。用 Backstage TechDocs 之类的工具做统一入口。

---

## 12. 成熟度自评

给自己的团队打分：

### 第 1 级：能跑
- [ ] 服务部署在 K8s 上
- [ ] 有基本监控和日志
- [ ] 出问题能手工恢复

### 第 2 级：可靠
- [ ] 所有服务有探针、资源限制、多副本、PDB
- [ ] 零停机滚动更新
- [ ] 有告警且有人响应
- [ ] 有备份

### 第 3 级：自动化
- [ ] GitOps 交付，回滚 = git revert
- [ ] CI 有质量门禁
- [ ] 自动扩缩容
- [ ] 配置和密钥规范管理

### 第 4 级：可度量
- [ ] 有 SLO 和错误预算
- [ ] 基于燃烧率的告警
- [ ] 每个告警有 runbook
- [ ] 事故有复盘和改进跟踪
- [ ] 成本可归因

### 第 5 级：持续改进
- [ ] 渐进式交付 + 自动回滚
- [ ] 定期混沌演练和 DR 演练
- [ ] 平台化（黄金路径，新服务 1 天上线）
- [ ] 容量规划前置
- [ ] 值班健康（告警 < 2 次/天）

**大多数团队卡在第 2~3 级。** 从第 3 级到第 4 级的关键是**SLO**——它把运维从"救火"变成"工程"。

---

## 13. 本章检查清单

- [ ] SLI / SLO / SLA / 错误预算的区别？错误预算怎么指导决策？
- [ ] 为什么延迟 SLI 要定义成"低于阈值的比例"而不是"P99 的值"？
- [ ] 燃烧率告警相比传统阈值告警好在哪？为什么要双窗口？
- [ ] 告警的三条铁律是什么？
- [ ] 告警抑制规则解决什么问题？
- [ ] 一份 runbook 应该包含哪些部分？
- [ ] 事故响应的 6 个步骤？为什么止血优先于定位？
- [ ] 为什么复盘必须是无指责的？
- [ ] GitOps 免费提供了哪些变更管理能力？
- [ ] 混沌工程的 5 条原则？列出 5 个你应该演练的场景
- [ ] 健康的值班应该是什么样的？
- [ ] 你的团队现在在哪个成熟度级别？下一步该做什么？

---

## 14. 阶段四小结 & 全课程结语

**你现在应该具备的能力**：

| 能力 | 对应章节 |
|---|---|
| 理解容器和编排的原理，能解释任何行为的成因 | 1~6 |
| 写出生产级的 K8s 清单，解释每个字段 | 7~14 |
| 建立自动化交付流水线 | 15~19 |
| 独立完成一次生产发布、回滚、节点维护 | 20 |
| 管理和扩展到多集群规模 | 21 |
| 独立排查绝大多数故障 | 22 |
| 持续运营：SLO、告警、值班、演练 | 23 |

**接下来可以做的**：

1. **把课程里的实验在真实环境重做一遍**（云上开一个小集群，或用 kubeadm 手工搭）
2. **考个认证**（可选，但考纲是很好的知识地图）：
   - **CKA**（管理员）—— 最对应本课程 6~14、21~22 章
   - **CKAD**（开发者）—— 对应 3~13 章
   - **CKS**（安全）—— 对应 14 章 + 深入
3. **读源码**：你有 Go 背景，`kubernetes/kubernetes` 的 `pkg/controller/` 是最好的分布式系统教材
4. **写一个 Operator**：用 kubebuilder，把你团队的某个运维流程自动化。这是把知识变成生产力的最快路径
5. **参与社区**：SIG 会议是公开的，K8s 的设计讨论（KEP）本身就是极好的架构学习材料

---

## 15. 延伸阅读

- [Google SRE Book](https://sre.google/sre-book/table-of-contents/)（免费在线，必读）
- [Google SRE Workbook](https://sre.google/workbook/table-of-contents/)（SLO 和告警的实操，第 2、5 章尤其重要）
- [Implementing Service Level Objectives](https://www.oreilly.com/library/view/implementing-service-level/9781492076803/)（Alex Hidalgo）
- [Chaos Mesh](https://chaos-mesh.org/) / [Litmus](https://litmuschaos.io/)
- [k6](https://k6.io/docs/) 压测
- [Backstage](https://backstage.io/) 开发者门户
- [Incident Response（PagerDuty 开源手册）](https://response.pagerduty.com/)

---

## 附录

- [附录 A - 命令与 YAML 速查](./A-cheatsheet.md)
- [附录 B - 术语表与延伸阅读](./B-glossary.md)

[← 返回课程总览](./README.md)
