# 22 - 故障排查手册

> 本章是**查阅型手册**，按"现象 → 排查路径 → 根因 → 修复"组织。
> 建议先通读一遍建立索引，然后在真正出问题时回来查。
> **强烈建议**：把每个故障在本地主动制造一遍（每节都给了复现方法）。

---

## 1. 通用排查方法论

### 1.1 万能起手式

```bash
# ① 看状态和事件（80% 的问题在这里就有答案）
kubectl get pods -o wide
kubectl describe pod <pod>          # ⭐ 重点看最下面的 Events

# ② 看日志
kubectl logs <pod> --tail=100
kubectl logs <pod> --previous       # ⭐ 崩溃前那次

# ③ 看集群事件
kubectl get events --sort-by=.lastTimestamp -A | tail -30

# ④ 看控制器状态
kubectl describe deploy/statefulset/job <name>
kubectl rollout status deploy/<name>

# ⑤ 看节点
kubectl get nodes
kubectl describe node <node> | grep -A15 Conditions
kubectl top nodes; kubectl top pods -A --sort-by=memory
```

### 1.2 分层定位

```
用户报错
  │
  ├─ 入口层？   Gateway/Ingress 的日志、证书、路由规则
  ├─ Service？  EndpointSlice 有后端吗？kube-proxy 规则对吗？
  ├─ Pod？      Running 吗？Ready 吗？重启了吗？
  ├─ 容器？     日志有错吗？OOM 了吗？被节流了吗？
  ├─ 依赖？     数据库/缓存/下游服务正常吗？
  └─ 节点？     Ready 吗？资源够吗？磁盘满了吗？
```

**关键原则**：
1. **先看变更**：99% 的故障是变更引起的。最近发布了什么？改了什么配置？升级了什么？
2. **先止血再定位**：先回滚/扩容/摘流量恢复服务，再慢慢查根因
3. **别只看一个 Pod**：是所有副本都有问题，还是只有一个？是所有节点都有问题，还是特定节点？

### 1.3 常用武器

```bash
# 调试容器（distroless 也能用）
kubectl debug -it <pod> --image=nicolaka/netshoot --target=<container>
kubectl debug node/<node> -it --image=busybox:1.37

# 多 Pod 日志
stern <pattern> -n <ns> --since 10m

# 交互式浏览
k9s

# 网络测试
kubectl run -it --rm netshoot --image=nicolaka/netshoot --restart=Never -- bash
```

---

## 2. Pod 起不来

### 2.1 `Pending`

```bash
kubectl describe pod <pod> | tail -20
```

| Events 里的信息 | 根因 | 修复 |
|---|---|---|
| `Insufficient cpu` / `Insufficient memory` | 没有节点有足够的**可分配**资源（看的是 requests！） | 降低 requests / 扩容节点 / 检查是否有 Pod 占了过多 requests |
| `node(s) had untolerated taint` | 节点有污点，Pod 没有对应容忍 | 加 toleration（第 12 章） |
| `node(s) didn't match Pod's node affinity/selector` | nodeSelector/affinity 太严 | 检查节点标签 `kubectl get nodes --show-labels` |
| `node(s) didn't match pod topology spread constraints` | 拓扑约束无法满足 | 改 `whenUnsatisfiable: ScheduleAnyway`，或加 `matchLabelKeys` |
| `node(s) didn't find available persistent volumes to bind` | PVC 没绑上 | 见 §5 |
| `node(s) had volume node affinity conflict` | PV 在 zone-a，Pod 被要求调到 zone-b | 用 `WaitForFirstConsumer`（第 11 章） |
| `node(s) exceed max volume count` | 节点挂载的卷数达上限（云盘有限制） | 分散到更多节点 |
| `0/N nodes are available` 但没细节 | 可能是 quota | `kubectl describe quota -n <ns>` |
| 没有任何 Event | 调度器挂了？或者 Pod 被 admission webhook 卡住 | `kubectl -n kube-system get pods \| grep scheduler` |

**复现**：

```bash
kubectl run huge --image=nginx --overrides='{"spec":{"containers":[{"name":"huge","image":"nginx","resources":{"requests":{"cpu":"200"}}}]}}'
kubectl describe pod huge | tail -6
kubectl delete pod huge
```

**特殊情况：整个集群都 Pending**
检查是不是 quota 用尽、admission webhook 挂了（会阻塞所有对象创建）：

```bash
kubectl get validatingwebhookconfigurations,mutatingwebhookconfigurations
kubectl -n <webhook-ns> get pods       # webhook 服务挂了会阻塞一切
```

⚠️ **这是个经典的死锁**：webhook 的 Pod 挂了 → 无法创建新 Pod → 包括 webhook 自己的 Pod。解法：临时删掉 webhook 配置。所以生产的 webhook 一定要配 `failurePolicy: Ignore` 或 `namespaceSelector` 排除自己所在的 namespace。

### 2.2 `ImagePullBackOff` / `ErrImagePull`

```bash
kubectl describe pod <pod> | grep -A5 Events
```

| 信息 | 根因 | 修复 |
|---|---|---|
| `not found` / `manifest unknown` | 镜像名或 tag 拼错、镜像没推上去 | 核对 `kubectl get pod -o jsonpath='{.spec.containers[*].image}'` |
| `unauthorized` / `denied` | 私有仓库没有凭据 | 建 `imagePullSecrets`（第 3、8 章） |
| `toomanyrequests` | **Docker Hub 匿名拉取限流**（100 次/6 小时/IP） | 登录、用镜像代理、自建仓库 |
| `connection refused` / `i/o timeout` | 节点访问不了仓库 | 检查网络、DNS、代理、防火墙 |
| `no match for platform` | 架构不匹配（arm64 vs amd64） | 构建多架构镜像（第 3 章） |
| 本地 `kind load` 了但还去拉 | tag 是 `latest` → `imagePullPolicy` 默认 `Always` | 用具体 tag，或显式设 `IfNotPresent` |

**在节点上直接验证**：

```bash
docker exec learn-worker crictl pull <image>
docker exec learn-worker crictl images | grep <image>
```

### 2.3 `CrashLoopBackOff`

**`CrashLoopBackOff` 不是原因，是现象**——容器起来就退出，kubelet 在指数退避重启。

```bash
# ⭐ 第一步永远是看崩溃前的日志
kubectl logs <pod> --previous
kubectl logs <pod> --previous -c <container>

# 看退出码和原因
kubectl describe pod <pod> | grep -A8 "Last State"
```

| 退出码 | 含义 |
|---|---|
| `0` | 正常退出——但 `restartPolicy: Always` 会重启它。说明你的程序不该退出却退出了（比如 main 跑完了） |
| `1` | 通用错误。看日志 |
| `2` | shell 用法错误 |
| `126` | 命令不可执行（权限问题） |
| `127` | **命令不存在**——常见于 distroless 镜像里写了 `sh -c` |
| `137` | **SIGKILL** = OOMKilled，或者优雅期超时被强杀 |
| `139` | SIGSEGV，段错误 |
| `143` | SIGTERM，正常终止 |

**常见根因**：

| 根因 | 表现 | 修复 |
|---|---|---|
| 配置缺失/错误 | 日志里有 "required env not set"、"connection refused" | 检查 ConfigMap/Secret 是否存在、key 是否对 |
| 依赖没起来 | 连数据库超时 | 用 initContainer 等依赖，或让应用重试而不是退出 |
| OOMKilled | 退出码 137，`Reason: OOMKilled` | 加内存 limit、设 GOMEMLIMIT、查内存泄漏（第 13 章 pprof） |
| 权限问题 | "permission denied" | `fsGroup`、`runAsUser`、`readOnlyRootFilesystem` 挡了写入 |
| 命令/入口错误 | 退出码 127 | 检查 `command`/`args`；distroless 没有 shell |
| liveness 探针配错 | 反复被杀，`Liveness probe failed` | 探针路径/端口/超时；用 startupProbe 保护慢启动 |
| 架构不匹配 | `exec format error` | 多架构镜像 |
| 程序正常退出 | 退出码 0 | 应该是 Job 而不是 Deployment；或者 main 里少了阻塞 |

**复现**：

```bash
kubectl run crash --image=busybox:1.37 --restart=Always -- sh -c 'echo "starting"; sleep 3; echo "fatal: config missing" >&2; exit 1'
sleep 40
kubectl get pod crash
kubectl logs crash --previous
kubectl describe pod crash | grep -A8 "Last State"
kubectl delete pod crash
```

**排查技巧：让它别崩，进去看看**

```bash
# 复制一个 Pod，把 command 改成 sleep，然后进去手工执行
kubectl debug <pod> --copy-to=debug-pod --container=server -- sleep 3600
kubectl exec -it debug-pod -- sh
# 手工跑你的程序，看真实报错
kubectl delete pod debug-pod
```

### 2.4 `Init:xxx` / `Init:CrashLoopBackOff`

```bash
kubectl logs <pod> -c <init-container-name>
kubectl describe pod <pod> | grep -A10 "Init Containers"
```

init 容器失败会阻塞整个 Pod。常见：等待依赖的脚本永远等不到、迁移脚本失败。

### 2.5 `Running` 但 `READY 0/1`

**readiness 探针失败。** 这是"服务不可用但容器没死"的典型。

```bash
kubectl describe pod <pod> | grep -A5 "Readiness"
# Warning  Unhealthy  Readiness probe failed: HTTP probe failed with statuscode: 503

# 从集群内直接测探针
POD_IP=$(kubectl get pod <pod> -o jsonpath='{.status.podIP}')
kubectl run -it --rm t --image=nicolaka/netshoot --restart=Never -- \
  curl -v http://$POD_IP:8080/readyz
```

| 根因 | 修复 |
|---|---|
| 依赖不可用（数据库、缓存） | 修依赖；确认这是 readiness 而不是 liveness（第 7 章） |
| 探针路径/端口写错 | 核对 |
| 探针超时太短（默认 1 秒） | 调大 `timeoutSeconds` |
| 应用启动慢 | 加 `startupProbe` |
| 探针端点需要认证 | 换一个不需要认证的端点 |

### 2.6 `Terminating` 卡住

```bash
kubectl get pod <pod> -o yaml | grep -A5 deletionTimestamp
kubectl get pod <pod> -o jsonpath='{.metadata.finalizers}'
```

| 根因 | 修复 |
|---|---|
| 应用没处理 SIGTERM，等宽限期 | 正常，等 `terminationGracePeriodSeconds` |
| 应用有未完成的长请求 | 正常 |
| 卷卸载失败 | 看 kubelet 日志；可能要手工 umount |
| finalizer 没被移除 | 找负责的控制器；确认它还在运行 |
| 节点失联 | Pod 会卡在 Terminating 直到节点恢复或被删除 |

```bash
# ⚠️ 强制删除（最后手段，有数据损坏风险，StatefulSet 尤其危险）
kubectl delete pod <pod> --grace-period=0 --force

# 移除 finalizer
kubectl patch pod <pod> -p '{"metadata":{"finalizers":null}}' --type=merge
```

---

## 3. 资源问题

### 3.1 OOMKilled

```bash
kubectl describe pod <pod> | grep -A6 "Last State"
#   Reason: OOMKilled
#   Exit Code: 137
```

**排查顺序**：

```bash
# ① 看实际用量趋势（Prometheus）
# container_memory_working_set_bytes{pod="xxx"}

# ② 是缓慢泄漏还是瞬间尖峰？
kubectl top pod <pod> --containers

# ③ Go 服务：看堆
kubectl port-forward <pod> 9090:9090
go tool pprof -http=:8081 http://localhost:9090/debug/pprof/heap
# 对比两次快照找泄漏：
go tool pprof -http=:8081 -base h1.pb.gz h2.pb.gz
```

| 根因 | 修复 |
|---|---|
| limit 设得太低 | 按 P99 用量调整 |
| 没设 `GOMEMLIMIT` | 设为 limit 的 85%（第 7 章） |
| 真的内存泄漏 | pprof 定位（goroutine 泄漏、大 slice 未释放、cache 无上限） |
| 一次读入大文件/大查询结果 | 流式处理、分页 |
| `emptyDir: {medium: Memory}` 写太多 | 它算容器内存！设 `sizeLimit` |
| 请求突增导致并发内存暴涨 | 限流、连接池上限、请求体大小限制 |

**复现**：

```bash
kubectl run oom --image=polinux/stress --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"oom","image":"polinux/stress","command":["stress","--vm","1","--vm-bytes","300M","--vm-hang","1"],"resources":{"limits":{"memory":"100Mi"}}}]}}'
sleep 15; kubectl describe pod oom | grep -A5 "Last State"; kubectl delete pod oom
```

### 3.2 CPU 节流（延迟毛刺的隐形杀手）

**现象**：CPU 使用率看起来不高，但 P99 延迟很差。

```bash
kubectl exec <pod> -- cat /sys/fs/cgroup/cpu.stat
# nr_throttled 和 throttled_usec 在持续增长 = 正在被节流
```

```promql
rate(container_cpu_cfs_throttled_periods_total[5m])
  / rate(container_cpu_cfs_periods_total[5m]) > 0.1
```

| 修复 | 说明 |
|---|---|
| 提高 CPU limit | 直接有效 |
| **去掉 CPU limit** | 在线服务的常见做法（第 7 章的讨论） |
| 设对 `GOMAXPROCS` | 用 `automaxprocs`，避免 Go 开太多 P 加剧节流 |
| 减少突发（预热、异步化） | 应用层优化 |

### 3.3 Pod 被驱逐（Evicted）

```bash
kubectl get pods -A --field-selector status.phase=Failed
kubectl describe pod <pod> | grep -A5 "Status\|Message"
# The node was low on resource: ephemeral-storage / memory
```

| 资源 | 根因 | 修复 |
|---|---|---|
| `memory` | 节点内存不足 | 提高该 Pod 的 requests（提升 QoS 等级）、给节点加内存、排查内存大户 |
| `ephemeral-storage` | 容器写了太多本地文件 | 日志写 stdout、限制 `emptyDir.sizeLimit`、设 `ephemeral-storage` requests/limits |
| `inodes` | 大量小文件 | 同上 |

```bash
# 清理已驱逐的 Pod
kubectl get pods -A --field-selector status.phase=Failed -o json | \
  kubectl delete -f - 2>/dev/null

# 看节点磁盘
kubectl describe node <node> | grep -A10 Conditions
docker exec learn-worker df -h
docker exec learn-worker crictl images     # 镜像占了多少
```

---

## 4. 网络问题

### 4.1 Service 访问不通

**按顺序排查**：

```bash
# ① Service 存在且有 ClusterIP？
kubectl get svc <svc>

# ② ⭐ EndpointSlice 有后端吗？（最关键的一步）
kubectl get endpointslices -l kubernetes.io/service-name=<svc>
kubectl get endpointslices -l kubernetes.io/service-name=<svc> -o yaml | grep -A5 addresses
```

**如果 endpoints 为空**：

| 检查 | 命令 |
|---|---|
| Service 的 selector 和 Pod 的 label 匹配吗？ | `kubectl get svc <svc> -o jsonpath='{.spec.selector}'`<br>`kubectl get pods --show-labels` |
| Pod 是 Ready 状态吗？ | `kubectl get pods`（**只有 Ready 的才在 endpoints 里**） |
| targetPort 对吗？ | 核对 Service 的 `targetPort` 和容器的实际监听端口 |

**如果 endpoints 有值但还是不通**：

```bash
# ③ 直接访问 Pod IP（绕过 Service）
POD_IP=$(kubectl get pod <pod> -o jsonpath='{.status.podIP}')
kubectl run -it --rm t --image=nicolaka/netshoot --restart=Never -- curl -v $POD_IP:8080
# 通 → 问题在 Service/kube-proxy 层
# 不通 → 问题在 Pod/应用层

# ④ 应用监听在正确的地址吗？（第 4 章的经典坑）
kubectl debug -it <pod> --image=nicolaka/netshoot --target=<container> -- ss -tlnp
# 如果是 127.0.0.1:8080 而不是 0.0.0.0:8080 → 就是这个问题

# ⑤ kube-proxy 正常吗？
kubectl -n kube-system get pods -l k8s-app=kube-proxy
kubectl -n kube-system logs -l k8s-app=kube-proxy --tail=50
docker exec learn-worker iptables -t nat -S | grep <clusterIP>

# ⑥ NetworkPolicy 挡了吗？
kubectl get networkpolicy -n <ns>
```

### 4.2 DNS 解析失败

```bash
kubectl run -it --rm dns --image=nicolaka/netshoot --restart=Never -- bash

# 基本测试
nslookup kubernetes.default
nslookup <svc>.<ns>.svc.cluster.local
cat /etc/resolv.conf
dig @10.96.0.10 <svc>.<ns>.svc.cluster.local
```

| 现象 | 根因 | 修复 |
|---|---|---|
| 全部解析失败 | CoreDNS 挂了 | `kubectl -n kube-system get pods -l k8s-app=kube-dns`，看日志和资源 |
| 内部能解析、外部不能 | CoreDNS 的上游 DNS 不通 | 检查 `forward . /etc/resolv.conf` 配置和节点 DNS |
| **间歇性失败 / 5 秒超时** | conntrack race（DNS 并发 A/AAAA 查询的内核 bug） | 部署 NodeLocalDNSCache；或 `dnsConfig.options: single-request-reopen` |
| 外部域名解析慢 | `ndots:5` 导致多次无效查询（第 10 章） | 降 `ndots`、域名加末尾点、NodeLocalDNSCache |
| 加了 NetworkPolicy 后全挂 | 没放行 UDP/TCP 53 | 加 egress 规则放行 kube-dns（第 10 章） |
| CoreDNS CPU 打满 | 查询量太大 | 扩副本、加缓存、修 ndots |

```bash
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=100
kubectl -n kube-system get cm coredns -o yaml
kubectl -n kube-system top pod -l k8s-app=kube-dns
```

### 4.3 502 / 503 / 504

| 状态码 | 层次 | 常见原因 |
|---|---|---|
| **502 Bad Gateway** | 网关 → 后端 | 后端 Pod 挂了/正在重启；后端返回了非法响应；发布期间 endpoint 摘除不及时（第 7 章的 preStop） |
| **503 Service Unavailable** | 网关 | 没有可用后端（endpoints 为空）；限流；应用主动返回 |
| **504 Gateway Timeout** | 网关 → 后端 | 后端处理太慢；网关超时配置太短；后端卡死 |

**发布期间的 502 排查**（最常见）：

```
检查清单：
□ readinessProbe 配了吗？
□ preStop 有 sleep 吗？（第 7 章）
□ 应用实现优雅退出了吗？
□ terminationGracePeriodSeconds 够长吗？
□ maxUnavailable 是 0 吗？
□ 副本数够吗？
```

### 4.4 跨节点 Pod 不通

```bash
# 从 node A 的 Pod ping node B 的 Pod
kubectl get pods -o wide
kubectl exec <podA> -- ping -c3 <podB-ip>

# 检查 CNI
kubectl -n kube-system get pods | grep -Ei 'calico|cilium|flannel|kindnet'
kubectl -n kube-system logs -l k8s-app=calico-node --tail=50

# 节点路由表
docker exec learn-worker ip route
docker exec learn-worker ip a
```

云上还要检查：安全组是否放行 Pod CIDR、VXLAN(4789)/BGP(179)/WireGuard 端口、MTU 设置（隧道封装会减小有效 MTU，导致大包丢失——表现为"小请求正常，大请求超时"）。

---

## 5. 存储问题

### 5.1 PVC 一直 `Pending`

```bash
kubectl describe pvc <pvc> | tail -15
```

| 信息 | 根因 | 修复 |
|---|---|---|
| `waiting for first consumer` | `volumeBindingMode: WaitForFirstConsumer` | **正常**，等 Pod 调度 |
| `storageclass not found` | SC 名字写错或不存在 | `kubectl get sc` |
| `no persistent volumes available` | 静态供给且没有匹配的 PV | 创建 PV 或用动态供给 |
| `failed to provision volume` | CSI driver 报错（配额、权限、参数错） | `kubectl -n kube-system logs <csi-controller-pod>` |
| 没有默认 SC | PVC 没写 `storageClassName` 且集群没默认 SC | 指定 SC 或设默认 |

### 5.2 Pod 卡在 `ContainerCreating`

```bash
kubectl describe pod <pod> | tail -15
```

| 信息 | 根因 | 修复 |
|---|---|---|
| `FailedAttachVolume` / `Multi-Attach error` | RWO 卷被另一个节点上的 Pod 占着 | 等旧 Pod 完全删除；检查是否有 Pod 卡在 Terminating；改用 RWX 或 StatefulSet |
| `FailedMount ... timeout expired` | 卷挂载超时 | 看 kubelet 日志；检查 CSI driver；检查存储后端 |
| `MountVolume.SetUp failed ... not found` | 引用的 ConfigMap/Secret 不存在 | 创建它 |
| `failed to allocate IP` | CNI IP 池耗尽 | 扩 CIDR（难）、清理僵尸 Pod、检查 CNI 状态 |
| 卡很久没有事件 | 镜像在拉（大镜像） | `crictl pull` 看进度 |

### 5.3 容器内 `Permission denied`

```bash
kubectl exec <pod> -- ls -ld /data
kubectl get pod <pod> -o jsonpath='{.spec.securityContext}'
```

修复：加 `fsGroup`（第 11 章），或用 initContainer chown。

### 5.4 磁盘满

```bash
kubectl describe node <node> | grep -A10 Conditions
# DiskPressure  True

docker exec learn-worker df -h
docker exec learn-worker du -sh /var/lib/containerd/* 2>/dev/null
docker exec learn-worker crictl images
```

| 占用大户 | 清理 |
|---|---|
| 镜像 | `crictl rmi --prune`；调 kubelet 的 `imageGCHighThresholdPercent` |
| 容器日志 | 设 `containerLogMaxSize`/`containerLogMaxFiles` |
| emptyDir | 设 `sizeLimit` |
| 应用写的临时文件 | 设 `ephemeral-storage` limit |

---

## 6. 节点问题

### 6.1 节点 `NotReady`

```bash
kubectl describe node <node> | grep -A15 Conditions
kubectl get events --field-selector involvedObject.name=<node>
```

| Condition | 含义 | 排查 |
|---|---|---|
| `Ready: False/Unknown` | kubelet 没上报心跳 | kubelet 挂了？网络断了？节点宕机？ |
| `MemoryPressure: True` | 内存不足 | 找内存大户 |
| `DiskPressure: True` | 磁盘不足 | 见 §5.4 |
| `PIDPressure: True` | 进程数太多 | 找 fork 炸弹；设 `pids-limit` |
| `NetworkUnavailable: True` | CNI 没配好 | 看 CNI Pod |

```bash
# 上节点排查
docker exec learn-worker systemctl status kubelet
docker exec learn-worker journalctl -u kubelet -n 100 --no-pager
docker exec learn-worker systemctl status containerd
docker exec learn-worker crictl info
```

**节点 NotReady 后会发生什么**：
1. Node 控制器给节点打 `node.kubernetes.io/unreachable:NoExecute` 污点
2. 默认 300 秒后（`tolerationSeconds`），Pod 被驱逐并在其他节点重建
3. **但原节点上的 Pod 可能还在跑**（如果只是网络分区）——这就是为什么 StatefulSet 的 Pod 不会自动重建（防止脑裂），必须人工确认

### 6.2 节点上 Pod 数达上限

```bash
kubectl describe node <node> | grep -i "pods"
# Allocatable: pods: 110
```

调 kubelet 的 `--max-pods`（注意也受 CNI 的每节点 IP 数限制）。

---

## 7. 控制面问题

### 7.1 kubectl 连不上

```bash
kubectl cluster-info
kubectl get --raw /healthz
kubectl get --raw /livez?verbose
kubectl get --raw /readyz?verbose
```

| 现象 | 排查 |
|---|---|
| `connection refused` | apiserver 挂了。上控制面节点看 static Pod：`crictl ps -a \| grep apiserver` |
| `Unable to connect ... x509` | 证书过期！见下 |
| `Unauthorized` | kubeconfig 的凭据失效 |
| 极慢 | apiserver 过载 / etcd 慢 |

**证书过期**（kubeadm 集群的经典事故，默认证书 1 年有效期）：

```bash
kubeadm certs check-expiration
kubeadm certs renew all
# 然后重启控制面组件（删掉 static Pod 的容器让 kubelet 重建）
```

### 7.2 etcd 问题

```bash
kubectl -n kube-system logs etcd-<node> --tail=100

docker exec learn-control-plane sh -c 'ETCDCTL_API=3 etcdctl \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key endpoint health --write-out=table'
```

| 现象 | 根因 | 修复 |
|---|---|---|
| 集群突然变只读，写操作全部失败 | **etcd 空间配额用尽**（`mvcc: database space exceeded`） | 压缩历史 + defrag + 解除告警（见下） |
| 写入慢 | 磁盘慢 | 换 NVMe；检查 `etcd_disk_wal_fsync_duration_seconds` |
| leader 频繁切换 | 网络抖动或磁盘慢 | 同上 |

```bash
# 空间用尽的紧急处理
REV=$(etcdctl endpoint status --write-out=json | jq -r '.[0].Status.header.revision')
etcdctl compact $REV
etcdctl defrag --cluster
etcdctl alarm disarm
```

### 7.3 Webhook 阻塞一切

```bash
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations

# 症状：创建任何对象都超时
# Error: failed calling webhook "xxx": context deadline exceeded
```

紧急处理：删掉那个 webhook 配置（**先备份**）。

```bash
kubectl get validatingwebhookconfiguration <name> -o yaml > /tmp/backup.yaml
kubectl delete validatingwebhookconfiguration <name>
```

**预防**：webhook 配 `failurePolicy: Ignore`（除非是安全策略必须 Fail）、`timeoutSeconds: 5`、排除 kube-system 和自己的 namespace。

---

## 8. 交付流程问题

### 8.1 Deployment 卡住不更新

```bash
kubectl rollout status deploy/<name>
kubectl describe deploy <name> | grep -A10 Conditions
```

| Condition | 含义 |
|---|---|
| `Progressing: False, ProgressDeadlineExceeded` | 超时了。新 Pod 起不来 |
| `Available: False` | 可用副本数不够 |
| `ReplicaFailure: True` | 无法创建 Pod（quota、PSA、webhook 拒绝） |

```bash
kubectl get rs -l app=<name>          # 看新旧 RS 的副本数
kubectl describe rs <new-rs>          # ⭐ 看创建 Pod 失败的原因
kubectl get pods -l app=<name>        # 新 Pod 什么状态？
```

其他可能：`paused: true`；`kubectl rollout resume deploy/<name>`。

### 8.2 Helm release 卡住

```bash
helm list -A --pending
helm history <release> -n <ns>
```

```bash
helm rollback <release> -n <ns>
# 或者删掉最新的 pending release Secret
kubectl -n <ns> get secret -l owner=helm,name=<release> --sort-by=.metadata.creationTimestamp
kubectl -n <ns> delete secret sh.helm.release.v1.<release>.v<N>
```

### 8.3 Argo CD `OutOfSync` 但看不出差异

```bash
argocd app diff <app>
argocd app get <app> --show-operation
kubectl -n argocd logs deploy/argocd-application-controller --tail=100
```

常见原因：
- 有其他控制器在改字段（HPA 改 replicas、webhook 注入 sidecar）→ 配 `ignoreDifferences`
- SSA 的 field manager 冲突 → `ServerSideApply=true`
- 模板渲染带了时间戳/随机数 → 改模板

### 8.4 Argo Rollouts 卡在 Degraded

```bash
kubectl argo rollouts get rollout <name>
kubectl get analysisrun
kubectl describe analysisrun <name>
```

分析失败会中止发布。看具体是哪个 metric 失败、查询返回了什么。

---

## 9. 性能问题排查（Go 服务）

```bash
# ① 确认是应用问题还是基础设施问题
# 从集群内直接压 Pod IP，绕过 Service 和网关
kubectl run -it --rm bench --image=nicolaka/netshoot --restart=Never -- \
  sh -c 'for i in $(seq 100); do curl -s -o /dev/null -w "%{time_total}\n" http://<pod-ip>:8080/; done'

# ② 检查是否被节流
kubectl exec <pod> -- cat /sys/fs/cgroup/cpu.stat

# ③ CPU profile
kubectl port-forward <pod> 9090:9090 &
go tool pprof -http=:8081 http://localhost:9090/debug/pprof/profile?seconds=30

# ④ goroutine 泄漏
curl -s localhost:9090/debug/pprof/goroutine?debug=1 | head -40
# goroutine 数持续增长 = 泄漏

# ⑤ 阻塞和锁竞争（需要代码里开启）
# runtime.SetBlockProfileRate(1); runtime.SetMutexProfileFraction(1)
go tool pprof http://localhost:9090/debug/pprof/block
go tool pprof http://localhost:9090/debug/pprof/mutex

# ⑥ trace
curl -s "localhost:9090/debug/pprof/trace?seconds=5" > trace.out
go tool trace trace.out
```

**常见的 K8s 特有性能问题**：

| 现象 | 根因 |
|---|---|
| P99 有规律的毛刺 | CPU 节流；GC 停顿；`GOMAXPROCS` 没设对 |
| 冷启动慢 | 连接池没预热；JIT；镜像大 |
| 偶发超时 | DNS 5 秒超时（conntrack race）；网络重传 |
| 扩容后延迟不降 | 长连接没重新分布（gRPC，第 10 章） |
| 内存缓慢增长 | 泄漏；或者只是 Go 的堆没归还 OS（看 `GOMEMLIMIT`） |

---

## 10. 快速索引

| 现象 | 去看 |
|---|---|
| Pod Pending | §2.1 |
| ImagePullBackOff | §2.2 |
| CrashLoopBackOff | §2.3 |
| 退出码 137 | §2.3、§3.1 |
| Running 但 0/1 Ready | §2.5 |
| Terminating 卡住 | §2.6 |
| OOMKilled | §3.1 |
| 延迟毛刺 / CPU 节流 | §3.2、§9 |
| Pod 被 Evicted | §3.3 |
| Service 不通 | §4.1 |
| DNS 失败 / 5 秒超时 | §4.2 |
| 502 / 503 / 504 | §4.3 |
| 跨节点不通 | §4.4 |
| PVC Pending | §5.1 |
| ContainerCreating 卡住 | §5.2 |
| Permission denied | §5.3 |
| 节点 NotReady / DiskPressure | §6 |
| kubectl 连不上 / 证书过期 | §7.1 |
| 集群突然变只读 | §7.2 |
| 创建任何对象都超时 | §7.3、§2.1 |
| Deployment 不更新 | §8.1 |
| Helm 卡住 | §8.2 |
| Argo CD OutOfSync | §8.3 |

---

## 11. 主动演练清单

**建议花一个下午，把这些故障在 kind 集群里全部制造一遍：**

- [ ] 创建一个 requests 超大的 Pod → Pending
- [ ] 用不存在的镜像 → ImagePullBackOff
- [ ] 容器启动就 `exit 1` → CrashLoopBackOff，用 `--previous` 看日志
- [ ] 内存 limit 100Mi 跑 stress 300M → OOMKilled，确认退出码 137
- [ ] CPU limit 100m 跑死循环 → 观察 `cpu.stat` 的节流计数
- [ ] Service 的 selector 写错 → endpoints 为空
- [ ] 应用监听 127.0.0.1 → Service 不通
- [ ] readiness 探针指向不存在的路径 → 0/1 Ready
- [ ] liveness 探针指向不存在的路径 → 无限重启
- [ ] 加一个 default-deny NetworkPolicy 但不放行 DNS → 全部解析失败（需要 Calico）
- [ ] 非 root 用户写 PVC 且不设 fsGroup → Permission denied
- [ ] 设 PDB `minAvailable` = replicas 然后 drain → 卡住
- [ ] 手工改被 Argo CD 管理的 Deployment → 被改回去
- [ ] 用坏镜像触发滚动更新 → 观察 `maxUnavailable: 0` 保护了服务

**能独立解决这 14 个，你的排障能力就基本合格了。**

---

下一章：[23 - Day-2 运维](./23-day2-operations.md)
