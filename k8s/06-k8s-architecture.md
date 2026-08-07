# 06 - Kubernetes 架构与设计哲学

> 本章目标：理解 K8s 的**灵魂**——声明式 API + 控制器模式。这一章不教你敲命令，教你建立心智模型。
> 你有 Go 背景，所以我们会直接看伪代码：K8s 的所有"魔法"本质上就是一组 `for` 循环。
> 学完这章，后面所有资源类型你都能自己推导出行为。
> 预计用时：2.5 小时。

---

## 1. 一句话概括 Kubernetes

> **Kubernetes 是一个"带有可插拔控制器的、以 etcd 为后端的、声明式对象存储系统"。**
> 它管理容器只是因为默认装了一组管理容器的控制器。

这句话听起来很绕，但它是理解 K8s 可扩展性的钥匙。K8s 本身不知道什么是"容器"、什么是"部署"——
它只知道"对象"和"监听对象变化的控制器"。你完全可以用它管理数据库实例、云上的 S3 桶、甚至咖啡机
（真的有 [CoffeeMachine CRD](https://github.com/kubernetes/sample-controller) 这种玩具项目）。

---

## 2. 声明式 API：从"怎么做"到"要什么"

### 2.1 对比

```bash
# 命令式（Docker）：描述过程
docker run -d --name api1 myapp
docker run -d --name api2 myapp
docker run -d --name api3 myapp
# 挂了一个？你得自己发现、自己重启
```

```yaml
# 声明式（K8s）：描述结果
apiVersion: apps/v1
kind: Deployment
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: api
          image: myapp:v1
# 挂了一个？系统自己发现、自己补
```

### 2.2 所有 K8s 对象的统一结构

**每一个** K8s 对象——不管是 Pod、Service、还是你自定义的资源——都是这个结构：

```yaml
apiVersion: apps/v1        # 属于哪个 API 组和版本
kind: Deployment           # 类型
metadata:                  # 元数据：身份和标记
  name: my-api
  namespace: default
  labels:                  # 标签：用于"选择"（本质是索引）
    app: my-api
    tier: backend
  annotations:             # 注解：任意元数据，给工具用，不能用于选择
    kubernetes.io/change-cause: "upgrade to v1.2"
spec:                      # 期望状态（你写的）
  replicas: 3
status:                    # 实际状态（系统写的，你写了也会被覆盖）
  readyReplicas: 3
  conditions: [...]
```

用 Go 的话说：

```go
type Object struct {
    TypeMeta                    // apiVersion + kind
    ObjectMeta                  // name, namespace, labels, annotations, uid,
                                // resourceVersion, ownerReferences, finalizers...
    Spec   interface{}          // 你的意图
    Status interface{}          // 系统观测到的现实
}
```

**`spec` 和 `status` 的分离是整个系统的核心契约**：
- 用户（和 CI/CD）只写 `spec`
- 控制器只写 `status`
- 控制器的工作就是：**让 `status` 向 `spec` 收敛**

### 2.3 labels vs annotations（高频混淆）

| | labels | annotations |
|---|---|---|
| 用途 | **选择和分组**（Service 找 Pod、控制器找自己管的对象） | 存储任意元数据 |
| 可查询 | ✅ `kubectl get pods -l app=api` | ❌ 不能作为选择条件 |
| 大小限制 | 值 ≤ 63 字符，有字符集限制 | 可以很大（总计 256KB） |
| 典型内容 | `app`、`version`、`env`、`tier` | 变更原因、配置哈希、Ingress 的控制器参数、last-applied-configuration |

```bash
kubectl get pods -l 'app=api,env in (prod,staging)'
kubectl get pods -l '!canary'
kubectl label pod nginx tier=frontend --overwrite
kubectl annotate deploy my-api kubernetes.io/change-cause="rollback to v1.1"
```

**推荐的标准标签**（Helm 和大多数工具默认使用）：

```yaml
labels:
  app.kubernetes.io/name: hello
  app.kubernetes.io/instance: hello-prod
  app.kubernetes.io/version: "1.2.3"
  app.kubernetes.io/component: api
  app.kubernetes.io/part-of: hello-stack
  app.kubernetes.io/managed-by: Helm
```

---

## 3. 控制器模式：K8s 的引擎

### 3.1 核心循环

**每一个**控制器都在跑这个循环（Go 伪代码）：

```go
func (c *Controller) Run(ctx context.Context) {
    for {
        // 1. 观察（Observe）：从 API Server 拿期望状态和实际状态
        desired := c.getDesiredState()   // 用户写的 spec
        actual  := c.getActualState()    // 现实中真实存在的东西

        // 2. 比较（Diff）
        diff := compare(desired, actual)

        // 3. 行动（Act）：只做能让现实靠近期望的一步
        c.reconcile(diff)

        // 4. 更新 status，然后重来
        c.updateStatus()
    }
}
```

以 ReplicaSet 控制器为例（这是真实逻辑的简化版）：

```go
func (rsc *ReplicaSetController) syncReplicaSet(key string) error {
    rs := rsc.lister.Get(key)                        // 期望：replicas = 3
    pods := rsc.podLister.List(rs.Spec.Selector)     // 实际：现在有几个 Pod

    diff := len(pods) - int(*rs.Spec.Replicas)
    switch {
    case diff < 0:
        rsc.createPods(-diff, rs)                    // 少了就创建
    case diff > 0:
        victims := selectPodsToDelete(pods, diff)    // 多了就删（有淘汰优先级！）
        rsc.deletePods(victims)
    }

    return rsc.updateStatus(rs, pods)                // 写回 status
}
```

> **淘汰优先级很有意思**：缩容时删哪个 Pod 不是随机的。K8s 按以下顺序优先删：
> 未调度的 > Pending 的 > 未就绪的 > 就绪时间短的 > 重启次数多的 > 创建时间晚的。
> 这保证缩容时优先干掉"最不健康、最年轻"的副本。

### 3.2 关键性质

| 性质 | 含义 | 实践影响 |
|---|---|---|
| **幂等** | 同一个输入跑 100 遍，结果一样 | 控制器可以随时重启、重复执行 |
| **水平触发（level-triggered）** | 关注"当前状态"，不关注"发生了什么事件" | **事件丢了没关系**，下次循环还会发现差异并修复。这是 K8s 极其健壮的原因 |
| **最终一致** | 不保证立即完成，保证最终收敛 | `kubectl apply` 返回 ≠ 部署完成，要 `kubectl rollout status` 等 |
| **单一职责** | 每个控制器只管一件事 | 复杂行为由多个控制器**级联**产生 |

**"水平触发"这个概念非常重要**，用 Go 类比：

```go
// ❌ 边沿触发（edge-triggered）：处理事件。事件丢了就永久不一致
for event := range eventChan {
    switch event.Type {
    case Added:   createPod()
    case Deleted: deletePod()
    }
}

// ✅ 水平触发（level-triggered）：事件只是"该看一眼了"的提示，
//    真正的逻辑是比较全量状态。所以丢事件、重复事件都不影响正确性
for range triggerChan {
    reconcile(getDesired(), getActual())
}
```

这就是为什么 K8s 敢于在网络分区、组件重启、消息丢失的情况下依然工作。

### 3.3 控制器级联：一次 `kubectl apply` 到底发生了什么

这是本章最重要的一张图。当你 `kubectl apply -f deployment.yaml`：

```
  你 ──► kubectl ──► API Server ──► 认证 → 鉴权 → 准入控制 → 校验 → 写入 etcd
                                                                        │
        ┌───────────────────────────────────────────────────────────────┘
        │ (所有组件都在 watch API Server)
        ▼
  ① Deployment 控制器：
       "有个新 Deployment，没有对应的 ReplicaSet" → 创建 ReplicaSet(replicas=3)
        ▼
  ② ReplicaSet 控制器：
       "有个 RS 要 3 个 Pod，实际 0 个" → 创建 3 个 Pod（spec.nodeName 为空）
        ▼
  ③ Scheduler：
       "有 3 个 Pod 没有 nodeName" → 过滤+打分算出最优节点 → 写回 pod.spec.nodeName
        ▼
  ④ kubelet（在被选中的节点上）：
       "有个 Pod 的 nodeName 是我" → 调 CRI 拉镜像、调 CNI 配网络、调 CSI 挂卷、起容器
        ▼                                → 持续把容器状态写回 pod.status
  ⑤ EndpointSlice 控制器：
       "有 Pod 的 label 匹配某个 Service，且 Ready" → 把 Pod IP 加进 EndpointSlice
        ▼
  ⑥ kube-proxy（每个节点上）：
       "EndpointSlice 变了" → 更新本节点的 iptables/IPVS 规则
        ▼
  流量可达 ✅
```

**没有任何一个组件知道完整流程。** 每个组件只看自己关心的对象，做一个小转换。这种"松耦合的流水线"设计，正是 K8s 能被扩展到今天这个规模的原因。

亲手观察这个级联：

```bash
kubectl create deployment demo --image=nginx:alpine --replicas=3
kubectl get deploy,rs,pods -l app=demo
# deployment.apps/demo         3/3
# replicaset.apps/demo-5d4c8   3         ← Deployment 控制器创建的
# pod/demo-5d4c8-abcde         Running   ← ReplicaSet 控制器创建的

# 看所有权链条（ownerReferences）
kubectl get pod -l app=demo -o jsonpath='{.items[0].metadata.ownerReferences}' | jq
# [{"kind":"ReplicaSet","name":"demo-5d4c8",...,"controller":true}]

kubectl get events --sort-by=.lastTimestamp | tail -20
# 能看到 ScalingReplicaSet → SuccessfulCreate → Scheduled → Pulling → Created → Started
```

### 3.4 ownerReferences 与垃圾回收

对象之间通过 `ownerReferences` 建立父子关系。删除父对象时，**垃圾回收控制器**会级联删除子对象。

```bash
kubectl delete deployment demo
# ReplicaSet 和 Pod 会被自动删除，因为它们的 ownerReference 指向 Deployment
```

三种删除策略：

```bash
kubectl delete deploy demo --cascade=background     # 默认：先删父，后台异步删子
kubectl delete deploy demo --cascade=foreground     # 先删完所有子，再删父
kubectl delete deploy demo --cascade=orphan         # 只删父，子对象变成孤儿（保留 Pod）
```

**Finalizer**：对象上的 `metadata.finalizers` 列表非空时，删除会**卡住**（对象进入 `Terminating` 状态但不消失），直到负责的控制器完成清理工作并移除自己的 finalizer。

```bash
# 经典故障：namespace 卡在 Terminating 删不掉
kubectl get ns stuck -o json | jq .spec.finalizers
# 通常是某个 CRD 的控制器已经删了，但它的 finalizer 还挂着，没人来清理
```

第 22 章会讲怎么正确处理这类问题（**注意：强行删 finalizer 会导致资源泄漏**，比如云上的负载均衡器不会被回收，持续计费）。

---

## 4. 组件全景

```
┌─────────────────────── 控制平面（Control Plane）───────────────────────┐
│                                                                       │
│  ┌───────────────┐   唯一能读写 etcd 的组件                             │
│  │  kube-        │◄──────── kubectl / 控制器 / kubelet / 所有人         │
│  │  apiserver    │   REST + watch，无状态，可水平扩展                    │
│  └───────┬───────┘                                                     │
│          │                                                             │
│      ┌───▼────┐  分布式 KV，Raft 一致性，整个集群唯一的持久状态            │
│      │  etcd  │  所有对象都在这儿：/registry/pods/default/nginx          │
│      └────────┘                                                        │
│                                                                        │
│  ┌────────────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ kube-controller-   │  │ kube-        │  │ cloud-controller-      │  │
│  │ manager            │  │ scheduler    │  │ manager                │  │
│  │ (内置 ~40 个控制器)  │  │ (Pod→Node)   │  │ (云厂商的 LB/节点/路由)  │  │
│  └────────────────────┘  └──────────────┘  └────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                  ▲
                                  │ 只通过 API Server 通信
                                  ▼
┌─────────────────────── 数据平面（每个 Node 上）────────────────────────┐
│  ┌──────────┐   ┌────────────┐   ┌──────────────┐                     │
│  │ kubelet  │   │ kube-proxy │   │ 容器运行时     │                     │
│  │ 管 Pod    │   │ 管 Service │   │ containerd    │                     │
│  │ 生命周期  │   │ 转发规则    │   │ + runc        │                     │
│  └──────────┘   └────────────┘   └──────────────┘                     │
│  ┌──────────────────────────────────────────────┐                     │
│  │  CNI 插件（网络） / CSI 插件（存储） / DevicePlugin │                     │
│  └──────────────────────────────────────────────┘                     │
└───────────────────────────────────────────────────────────────────────┘
```

### 4.1 kube-apiserver

**职责**：集群的唯一入口和唯一真相的守门人。

一个请求进来要过 5 关：

```
HTTP 请求
  │
  ├─► ① 认证（Authentication）    你是谁？
  │      客户端证书 / Bearer Token / ServiceAccount Token / OIDC / Webhook
  │
  ├─► ② 鉴权（Authorization）     你能做这个操作吗？
  │      RBAC（主流）/ ABAC / Node / Webhook
  │
  ├─► ③ 准入控制（Admission）      要不要改一改 / 允不允许？
  │      Mutating（改）：给 Pod 注入 sidecar、默认值、SA token
  │      Validating（校验）：拒绝不符合策略的对象
  │      → 这是 Istio 注入 sidecar、OPA/Kyverno 强制策略的挂载点
  │
  ├─► ④ 对象校验 + 版本转换       schema 校验、默认值填充、多版本互转
  │
  └─► ⑤ 持久化到 etcd            带乐观锁（resourceVersion）
```

**API 的组织方式**：

```
/api/v1                          核心组（core/legacy）：Pod、Service、ConfigMap、Node...
/apis/apps/v1                    apps 组：Deployment、StatefulSet、DaemonSet
/apis/batch/v1                   Job、CronJob
/apis/networking.k8s.io/v1       Ingress、NetworkPolicy
/apis/rbac.authorization.k8s.io/v1
/apis/gateway.networking.k8s.io/v1   Gateway API（CRD 提供）
/apis/<你的组>/v1                 你的 CRD
```

```bash
kubectl api-resources          # 所有资源类型、简称、是否 namespaced
kubectl api-versions           # 所有 API 组/版本
kubectl explain pod.spec.containers.resources    # 字段文档（活的！）
kubectl get --raw /api/v1 | jq '.resources[].name'
```

**版本成熟度**：`v1alpha1`（可能随时改、默认关闭）→ `v1beta1`（默认开启、可能有破坏性变更）→ `v1`（稳定，保证向后兼容）。生产上避免依赖 alpha。

### 4.2 etcd

- 基于 **Raft** 的强一致 KV 存储，集群唯一的持久状态
- 通常 3 或 5 个节点（奇数，容忍 (n-1)/2 个故障）
- **对磁盘延迟极其敏感**——必须用 SSD/NVMe，`fsync` 延迟 P99 应 < 10ms

```bash
# 在 kind 控制面节点上直接看 etcd 里的原始数据
docker exec learn-control-plane sh -c \
  'ETCDCTL_API=3 etcdctl \
   --cacert=/etc/kubernetes/pki/etcd/ca.crt \
   --cert=/etc/kubernetes/pki/etcd/server.crt \
   --key=/etc/kubernetes/pki/etcd/server.key \
   get /registry/namespaces/default --keys-only'
```

**运维要点（第 21、23 章展开）**：
- 默认单对象 1.5MB 上限，总容量默认 2GB（可调到 8GB），**超了整个集群变只读**
- 必须定期备份（`etcdctl snapshot save`）——etcd 没了 = 集群全没了
- Secret 默认在 etcd 里是 **base64 明文**，生产必须开静态加密（第 14 章）
- 高频写入的对象（Event、频繁更新 status 的 CRD）是 etcd 压力的主要来源

### 4.3 kube-scheduler

只做一件事：给 `spec.nodeName == ""` 的 Pod 挑一个节点。

两阶段：
1. **过滤（Filter / Predicates）**：哪些节点**能**放？资源够吗？端口冲突吗？污点容忍吗？亲和性满足吗？卷能挂吗？
2. **打分（Score / Priorities）**：能放的节点里哪个**最好**？资源均衡度、镜像本地性、拓扑分布、亲和性权重……

第 12 章会完整展开，包括怎么写调度约束。

### 4.4 kube-controller-manager

一个二进制里跑着约 40 个控制器：Deployment、ReplicaSet、StatefulSet、DaemonSet、Job、CronJob、Node、Endpoint、EndpointSlice、ServiceAccount、Namespace、PV/PVC binder、GC、TTL、HPA……

```bash
kubectl -n kube-system get pod -l component=kube-controller-manager
kubectl -n kube-system logs -l component=kube-controller-manager --tail=30
```

多副本时通过 **Lease 对象做 leader 选举**，同一时刻只有一个实例在工作：

```bash
kubectl -n kube-system get lease
```

### 4.5 kubelet

节点上的"包工头"，是唯一直接操作容器的组件。

职责：
- watch API Server，找 `spec.nodeName == 本节点` 的 Pod
- 调用 **CRI** 起停容器、**CNI** 配网络、**CSI** 挂卷
- 跑探针（liveness/readiness/startup）
- 上报节点状态（心跳 = 更新 Lease，默认 10 秒一次）和 Pod 状态
- 管理资源：驱逐（磁盘/内存压力）、cgroup 层级、镜像 GC
- 日志轮转

```bash
docker exec learn-worker systemctl status kubelet
docker exec learn-worker journalctl -u kubelet -n 50 --no-pager
docker exec learn-worker cat /var/lib/kubelet/config.yaml    # kubelet 配置
```

**static Pod**：kubelet 会读 `/etc/kubernetes/manifests/` 下的 YAML 直接起 Pod，不经过 API Server。控制面组件（apiserver 自己、etcd、scheduler、controller-manager）就是这么启动的——**这解决了鸡生蛋问题**。

```bash
docker exec learn-control-plane ls /etc/kubernetes/manifests/
# etcd.yaml  kube-apiserver.yaml  kube-controller-manager.yaml  kube-scheduler.yaml
```

### 4.6 kube-proxy

把 Service 的虚拟 IP 变成真实的转发规则。第 10 章详解。模式：`iptables`（默认）、`ipvs`（大规模更优）、`nftables`（新，逐步成为默认）。

注意：**用 Cilium 等 eBPF CNI 时，kube-proxy 可以完全去掉**，转发在 eBPF 里做，性能更好。

---

## 5. list-watch：K8s 的"消息总线"

这是 Go 开发者最该理解的部分——**K8s 没有消息队列，所有组件的协同都靠 API Server 的 watch 机制。**

### 5.1 协议层

```bash
# 一次 list：拿到当前全量 + 一个 resourceVersion（etcd 的全局逻辑时钟）
kubectl get --raw '/api/v1/namespaces/default/pods?limit=500' | jq '.metadata.resourceVersion'

# 从这个版本开始 watch：长连接，chunked 传输，有变化就推一条
kubectl get --raw '/api/v1/namespaces/default/pods?watch=true&resourceVersion=12345'
# {"type":"ADDED","object":{...}}
# {"type":"MODIFIED","object":{...}}
# {"type":"DELETED","object":{...}}
```

用 kubectl 直观感受：

```bash
kubectl get pods -w        # 底层就是 watch
```

### 5.2 客户端：Informer 机制

每个控制器直接 watch 会把 API Server 压垮。`client-go` 提供了 **Informer**：

```
API Server
    │ ① List（全量）+ Watch（增量）
    ▼
┌─────────────┐
│  Reflector  │  负责与 API Server 保持连接，把事件塞进 DeltaFIFO
└──────┬──────┘
       ▼
┌─────────────┐
│  DeltaFIFO  │  增量队列
└──────┬──────┘
       ▼
┌─────────────────────────────────┐
│  Indexer / Store（本地缓存）        │  ← 一份内存里的全量对象副本，带索引
│  你的所有"读"都从这里读，不打 API Server │
└──────┬──────────────────────────┘
       │ ② 触发 EventHandler
       ▼
┌─────────────┐
│  WorkQueue  │  去重 + 限速 + 失败重试（指数退避）
└──────┬──────┘
       ▼
   你的 Reconcile 函数
```

关键设计：

| 机制 | 作用 |
|---|---|
| **本地缓存（Indexer）** | 控制器读对象是**内存操作**，不打 API Server。这是 K8s 能扩展到上万节点的关键 |
| **WorkQueue 去重** | 一个对象在处理期间变了 10 次，只会被再处理 1 次（因为 key 相同） |
| **限速 + 指数退避** | 失败重试不会打垮 API Server |
| **Resync** | 定期（默认几分钟到几十分钟）把缓存里所有对象重新过一遍 reconcile，**兜底修复丢失的事件**——这就是"水平触发"的兜底保障 |
| **SharedInformer** | 多个控制器共享同一份缓存，避免重复 watch |

一个最小的 controller-runtime 示例（现代写法，`kubebuilder` 生成的就是这个）：

```go
import (
    ctrl "sigs.k8s.io/controller-runtime"
    appsv1 "k8s.io/api/apps/v1"
)

type MyReconciler struct{ client.Client }

func (r *MyReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    var deploy appsv1.Deployment
    if err := r.Get(ctx, req.NamespacedName, &deploy); err != nil {
        // NotFound 说明对象被删了，通常直接返回（GC 会处理子对象）
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // ==== 你的调谐逻辑：让现实向 deploy.Spec 收敛 ====

    // 返回值决定重试行为：
    // - 返回 error         → 按指数退避重试
    // - RequeueAfter: 30s  → 30 秒后再来一次（轮询外部系统时用）
    // - 空的 Result        → 完成，等下次事件
    return ctrl.Result{}, nil
}

func (r *MyReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&appsv1.Deployment{}).
        Owns(&corev1.Pod{}).      // 子对象变化也会触发父对象的 Reconcile
        Complete(r)
}
```

**这就是 K8s 的全部魔法。** 所有 40 多个内置控制器、所有 Operator，都是这个结构。

### 5.3 并发控制：乐观锁

每个对象都有 `metadata.resourceVersion`。更新时带上它，如果服务端的版本已经变了，返回 **409 Conflict**。

```bash
kubectl get pod nginx -o jsonpath='{.metadata.resourceVersion}'
```

```go
// 标准的重试模式（client-go 提供）
retry.RetryOnConflict(retry.DefaultRetry, func() error {
    obj, err := client.Get(ctx, name, metav1.GetOptions{})   // 重新读最新版本
    if err != nil { return err }
    obj.Spec.Replicas = ptr.To(int32(5))                     // 重新应用修改
    _, err = client.Update(ctx, obj, metav1.UpdateOptions{})
    return err                                                // 冲突则自动重试
})
```

**实践含义**：不要用 `kubectl get -o yaml > f && vim f && kubectl apply -f f` 这种流程处理高频变更的对象（比如被 HPA 管理的 Deployment），容易冲突。用 `kubectl patch` 或 server-side apply。

### 5.4 Server-Side Apply（现代方式）

传统 `kubectl apply` 靠 annotation 里存的 `last-applied-configuration` 做三方合并，脆弱且有诸多边界问题。

**Server-Side Apply**（1.22 GA）让 API Server 记录**每个字段是谁设置的**（field manager），从而精确处理多方共同管理一个对象的场景。

```bash
kubectl apply --server-side -f deploy.yaml
kubectl get deploy my-api -o yaml --show-managed-fields | yq '.metadata.managedFields'

# 冲突时（比如 HPA 也在改 replicas）
kubectl apply --server-side --force-conflicts -f deploy.yaml
```

Argo CD 3.x 和 Helm 4 都支持/默认使用 SSA。第 15、18 章会用到。

---

## 6. 可扩展性：K8s 为什么能变成"平台的平台"

K8s 的每个环节都留了插件点：

| 扩展点 | 接口 | 例子 |
|---|---|---|
| **容器运行时** | CRI | containerd、CRI-O、Kata、gVisor |
| **网络** | CNI | Calico、Cilium、Flannel |
| **存储** | CSI | AWS EBS、Ceph、Longhorn、local-path |
| **设备** | Device Plugin / DRA | NVIDIA GPU、FPGA、RDMA |
| **认证/鉴权** | Webhook | OIDC、企业 SSO |
| **准入控制** | Mutating/Validating Webhook | Istio 注入、Kyverno、OPA |
| **自定义资源** | **CRD** | Argo CD 的 Application、Prometheus 的 ServiceMonitor |
| **调度** | Scheduler Framework 插件 | 批量调度（Volcano）、拓扑感知 |
| **API 聚合** | APIService | metrics-server |

### 6.1 CRD + 控制器 = Operator

**Operator 模式**是 K8s 最有影响力的设计思想：**把人类运维专家的知识写成控制器**。

```yaml
# 你定义一个新资源类型
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: postgresclusters.db.example.com
spec:
  group: db.example.com
  names: {kind: PostgresCluster, plural: postgresclusters, shortNames: [pgc]}
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                replicas: {type: integer, minimum: 1}
                version:  {type: string}
              required: [replicas, version]
      subresources:
        status: {}          # 启用 /status 子资源（spec/status 分离写权限）
        scale:              # 启用 /scale，这样 kubectl scale 和 HPA 就能用了
          specReplicasPath: .spec.replicas
          statusReplicasPath: .status.replicas
```

有了 CRD，`kubectl get postgresclusters` 就能用了——**API Server 帮你实现了完整的 REST + watch + 校验 + 版本管理**。你只需要写那个 reconcile 循环。

然后你的 Operator 里实现：
- 创建时：起 StatefulSet、配置主从复制、初始化用户
- 扩容时：加从库、等同步完成、加进服务
- 版本升级时：先升从库、验证、再切主、升级旧主
- 备份：定期跑 Job 打快照到 S3
- 故障：主库挂了自动 failover

**这就是"把 DBA 的知识变成代码"**。生产上你会用到的 Operator：

| Operator | 管什么 |
|---|---|
| Prometheus Operator | ServiceMonitor、PrometheusRule、Alertmanager |
| cert-manager | Certificate（自动申请/续期 TLS 证书） |
| Argo CD | Application、ApplicationSet |
| External Secrets Operator | 从 Vault/AWS SM 同步密钥 |
| CloudNativePG / Zalando Postgres Operator | PostgreSQL 集群 |
| Strimzi | Kafka |
| Velero | 备份恢复 |

```bash
kubectl get crd                                   # 集群里装了哪些 CRD
kubectl api-resources --api-group=argoproj.io     # 某个组下的资源
```

**你有 Go 背景，写 Operator 对你来说门槛很低。** 用 `kubebuilder init && kubebuilder create api` 脚手架，核心就是填那个 `Reconcile` 函数。第 21 章会讲什么时候该写 Operator（以及什么时候不该）。

---

## 7. 读源码：当文档说不清时

K8s 是 Go 写的，源码是最终答案。几个高价值入口：

| 想搞清楚 | 去看 |
|---|---|
| Deployment 滚动更新的确切算法 | `pkg/controller/deployment/rolling.go` |
| 缩容时删哪个 Pod | `pkg/controller/controller_utils.go` 的 `ActivePods.Less` |
| 调度器的过滤和打分插件 | `pkg/scheduler/framework/plugins/` |
| kubelet 怎么处理 Pod | `pkg/kubelet/kubelet.go` 的 `syncPod` |
| 探针逻辑 | `pkg/kubelet/prober/` |
| API 类型定义（**最常查**） | `staging/src/k8s.io/api/`（如 `core/v1/types.go`、`apps/v1/types.go`） |

```bash
# 本地拿一份类型定义，比看网页文档快
go doc k8s.io/api/apps/v1 DeploymentStrategy
go doc k8s.io/api/core/v1 Probe
```

`staging/src/k8s.io/api/core/v1/types.go` 里每个字段都有详细注释，是**最权威的字段文档**。

---

## 8. 动手实验

### 实验 1：观察调谐循环

```bash
kubectl create deployment nginx --image=nginx:alpine --replicas=3
kubectl get pods -w &

# 手工删一个 Pod，观察它几秒内被重建
kubectl delete pod $(kubectl get pod -l app=nginx -o name | head -1)
# 你会看到：一个 Terminating，同时一个新的 Pending → ContainerCreating → Running

kill %1
```

### 实验 2：控制器不会放弃

```bash
# 写个循环不停删 Pod，观察控制器一直在补
for i in $(seq 10); do
  kubectl delete pod -l app=nginx --wait=false 2>/dev/null
  sleep 2
  kubectl get pod -l app=nginx --no-headers | wc -l
done
# 副本数始终在向 3 收敛
```

### 实验 3：手工改 status 会被打回

```bash
kubectl scale deployment nginx --replicas=5
kubectl get rs -l app=nginx
# 手工删掉 ReplicaSet，观察 Deployment 控制器立刻重建一个
kubectl delete rs -l app=nginx
sleep 3; kubectl get rs,pods -l app=nginx
```

### 实验 4：看清所有权链条

```bash
POD=$(kubectl get pod -l app=nginx -o name | head -1)
kubectl get $POD -o jsonpath='{.metadata.ownerReferences[0].name}'   # → ReplicaSet 名
RS=$(kubectl get $POD -o jsonpath='{.metadata.ownerReferences[0].name}')
kubectl get rs $RS -o jsonpath='{.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}'
# → Deployment/nginx

# orphan 删除：Pod 会活下来
kubectl delete deploy nginx --cascade=orphan
kubectl get pods -l app=nginx     # 还在！变成孤儿了
kubectl delete pods -l app=nginx  # 手工清理
```

### 实验 5：直接跟 API Server 对话

```bash
kubectl proxy --port=8001 &
curl -s localhost:8001/api/v1/namespaces/default/pods | jq '.items | length'
curl -s localhost:8001/apis/apps/v1/namespaces/default/deployments | jq -r '.items[].metadata.name'

# watch 一下（另开终端 create/delete Pod 观察输出）
curl -s "localhost:8001/api/v1/namespaces/default/pods?watch=true" | jq -c '{type, name: .object.metadata.name}'
kill %1
```

### 实验 6：看看控制面组件长什么样

```bash
kubectl -n kube-system get pods
docker exec learn-control-plane ls /etc/kubernetes/manifests/
docker exec learn-control-plane cat /etc/kubernetes/manifests/kube-apiserver.yaml | head -40
# 看它的启动参数：--etcd-servers、--authorization-mode、--enable-admission-plugins ...
```

---

## 9. 本章检查清单

- [ ] 解释 `spec` 和 `status` 的分工，以及谁写谁
- [ ] labels 和 annotations 的区别？各举 3 个用途
- [ ] 用伪代码写出一个控制器的核心循环
- [ ] "水平触发"是什么意思？为什么它让 K8s 更健壮？
- [ ] 完整叙述 `kubectl apply -f deployment.yaml` 后 6 个组件的级联过程
- [ ] API Server 处理请求要过哪 5 关？准入控制能做什么？
- [ ] Informer 的本地缓存解决了什么问题？Resync 的意义是什么？
- [ ] `resourceVersion` 和 409 Conflict 是什么关系？
- [ ] CRD + 控制器 = Operator，举一个你会用到的 Operator 例子
- [ ] etcd 出问题会有什么后果？为什么要单独备份它？

---

## 10. 延伸阅读

- [Kubernetes 架构概念](https://kubernetes.io/docs/concepts/architecture/)
- [Kubernetes API 概念](https://kubernetes.io/docs/reference/using-api/api-concepts/)（list-watch、SSA 的权威说明）
- [client-go 的 controller 示例](https://github.com/kubernetes/sample-controller)
- [controller-runtime 文档](https://book.kubebuilder.io/)（写 Operator 的必读书）
- [K8s API 类型定义](https://github.com/kubernetes/kubernetes/tree/master/staging/src/k8s.io/api)
- [Kubernetes: The Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way)（手工装一遍，最深刻的理解方式）

---

下一章：[07 - Pod 详解：最小调度单元](./07-pod.md)
