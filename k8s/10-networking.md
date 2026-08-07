# 10 - Service 与网络

> 本章目标：搞懂集群里的流量是怎么走的——Pod 之间怎么通信、Service 怎么做负载均衡、
> 外部流量怎么进来、DNS 怎么解析、怎么做网络隔离。
> 这一章是"如何访问网络"在集群层面的完整答案。
> 预计用时：3.5 小时（含实验）。

---

## 1. Kubernetes 网络模型：四条铁律

K8s 不实现网络，它只**规定**网络必须满足的性质，具体实现交给 CNI 插件：

1. **每个 Pod 有独立 IP**（不是每个容器）
2. **所有 Pod 可以直接互通，不需要 NAT**——Pod A 看到的 Pod B 的 IP，就是 Pod B 自己看到的自己的 IP
3. **节点上的 agent（kubelet 等）可以直接访问该节点上的所有 Pod**
4. Pod 内的容器共享网络 namespace，用 `localhost` 互访

**第 2 条最重要**，它和 Docker 完全不同：

| | Docker 单机 | Kubernetes |
|---|---|---|
| 跨主机通信 | 需要端口映射 + NAT | **直接用 Pod IP，无 NAT** |
| 心智负担 | 要记住"外面看到的端口"和"里面的端口"不同 | **一致**，谁看到的都一样 |

这条规则让 K8s 网络"像一个扁平的大二层网络"，代价是需要 CNI 插件做隧道或路由。

### 1.1 CNI 插件

| 插件 | 数据面 | 特点 |
|---|---|---|
| **Cilium** ⭐ | **eBPF** | 性能最好、可替代 kube-proxy、L7 策略、可观测性（Hubble）、多集群。**当前首选** |
| **Calico** | iptables / eBPF / VXLAN / BGP | 成熟稳定、NetworkPolicy 功能强、大规模验证充分 |
| **Flannel** | VXLAN | 最简单，**不支持 NetworkPolicy**，适合学习和小集群 |
| **kindnet** | 简单网桥 + 路由 | kind 默认，仅用于本地 |
| 云厂商 CNI（AWS VPC CNI / Azure CNI） | 直接用云上 VPC IP | Pod IP 就是 VPC IP，与云网络原生集成；**注意 IP 数量限制** |

```bash
kubectl -n kube-system get pods | grep -Ei 'cilium|calico|flannel|kindnet'
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.podCIDR}{"\n"}{end}'
# 每个节点分到一段 Pod CIDR
```

### 1.2 三个 IP 段（不能重叠）

```bash
docker exec learn-control-plane cat /etc/kubernetes/manifests/kube-apiserver.yaml | grep -E 'service-cluster-ip-range'
```

| 网段 | 用途 | 典型值 | 谁分配 |
|---|---|---|---|
| **Node CIDR** | 节点的真实 IP | 10.0.0.0/16 | 你的 VPC/机房 |
| **Pod CIDR** | Pod IP | 10.244.0.0/16 | CNI（每个节点切一个 /24） |
| **Service CIDR** | Service 的 ClusterIP | 10.96.0.0/12 | kube-apiserver |

⚠️ **规划要点**：Pod CIDR 决定了集群的规模上限。`10.244.0.0/16` + 每节点 `/24` = 最多 256 个节点，每节点 254 个 Pod。生产上要提前算好，**这个值改起来极其痛苦**（要重建集群）。

---

## 2. Service：为什么需要它

Pod 的问题：
- IP 是临时的（重建就变）
- 有多个副本，客户端要自己负载均衡
- 副本会随时增减

**Service 提供一个稳定的虚拟 IP（ClusterIP）+ DNS 名，背后是一组动态变化的 Pod。**

```
              Service: hello (ClusterIP 10.96.5.20)
              DNS: hello.lab.svc.cluster.local
                            │
       ┌────────────────────┼────────────────────┐
       ▼                    ▼                    ▼
   Pod 10.244.1.5      Pod 10.244.2.7      Pod 10.244.3.9
   （随时可能变）        （随时可能变）        （随时可能变）
```

### 2.1 Service 与 EndpointSlice

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hello
spec:
  selector:                # ⭐ 靠 label 选择后端 Pod
    app: hello
  ports:
    - name: http
      port: 80             # Service 暴露的端口
      targetPort: http     # Pod 上的端口（可用名字，解耦端口号）
      protocol: TCP
```

**EndpointSlice 控制器**根据 selector 找到所有 **Ready** 的 Pod，把它们的 IP 写进 EndpointSlice：

```bash
kubectl get svc hello
kubectl get endpointslices -l kubernetes.io/service-name=hello
kubectl get endpointslices -l kubernetes.io/service-name=hello -o yaml
# endpoints:
#   - addresses: ["10.244.1.5"]
#     conditions: {ready: true, serving: true, terminating: false}
#     nodeName: learn-worker
#     zone: zone-a
```

> **Endpoints vs EndpointSlice**：老的 `Endpoints` 对象把所有后端塞进一个对象里，
> 5000 个 Pod 的 Service 会产生一个巨大的对象，每次变化都要全量推送给所有节点——这是早期 K8s 的
> 重大扩展性瓶颈。**EndpointSlice**（1.21 起默认）把它切成每片最多 100 个端点，
> 只推变化的那片。大集群里这是数量级的差异。

**关键点：只有 Ready 的 Pod 才在 EndpointSlice 里。** 这就是 readiness 探针控制流量的机制。

### 2.2 四种 Service 类型

```
ExternalName  →  只是一条 CNAME，不做代理
     ↑
ClusterIP     →  集群内部虚拟 IP（默认）
     ↑
NodePort      →  ClusterIP + 每个节点上开一个端口
     ↑
LoadBalancer  →  NodePort + 云厂商的外部负载均衡器
```

**它们是叠加关系**：LoadBalancer 类型的 Service 同时拥有 ClusterIP 和 NodePort。

#### ① ClusterIP（默认）

```yaml
spec:
  type: ClusterIP
  ports: [{port: 80, targetPort: 8080}]
```
只能集群内访问。**绝大多数服务用这个。**

特殊值 `clusterIP: None` = **Headless Service**：不分配虚拟 IP，DNS 直接返回所有 Pod IP。用于：
- StatefulSet 的稳定 DNS（第 9 章）
- 客户端需要自己做负载均衡（gRPC 客户端负载均衡）
- 需要知道所有后端地址的场景

#### ② NodePort

```yaml
spec:
  type: NodePort
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30080      # 30000-32767，不指定则随机分配
```

在**每个节点**上开这个端口，访问任意节点的 `:30080` 都会转发到后端 Pod（可能在别的节点）。

用途：本地开发、没有云 LB 的自建集群（前面套一个自己的 LB）。
缺点：端口范围受限、端口号不好记、需要知道节点 IP。

#### ③ LoadBalancer

```yaml
spec:
  type: LoadBalancer
  loadBalancerClass: service.k8s.aws/nlb    # 可选：指定用哪个 LB 实现
```

云厂商的 cloud-controller-manager 看到这个 Service 后，去创建一个真正的云负载均衡器（AWS NLB/ALB、阿里云 SLB…），并把 external IP 写回 `status`。

```bash
kubectl get svc
# NAME    TYPE           CLUSTER-IP     EXTERNAL-IP      PORT(S)
# hello   LoadBalancer   10.96.5.20     52.1.2.3         80:30080/TCP
```

⚠️ **自建集群里 EXTERNAL-IP 会永远是 `<pending>`**（没人来创建 LB）。解决方案：
- **MetalLB**：在裸金属集群里用 ARP/BGP 实现 LoadBalancer
- **kube-vip**
- kind 本地实验：`cloud-provider-kind`

⚠️ **成本陷阱**：每个 LoadBalancer Service 都会创建一个云 LB，每个每月几十美元。**不要给每个服务都配 LoadBalancer**——应该用一个 Ingress/Gateway 统一入口，后面挂几十个 ClusterIP Service。

#### ④ ExternalName

```yaml
spec:
  type: ExternalName
  externalName: rds.ap-east-1.amazonaws.com
```

只是给 CoreDNS 加一条 CNAME。用途：把集群外的服务（云数据库）包装成集群内的名字，
这样应用配置里统一写 `db.prod.svc.cluster.local`，迁移时只改 Service 不改应用。

### 2.3 Service 的重要可选字段

```yaml
spec:
  sessionAffinity: ClientIP           # 会话保持（默认 None）
  sessionAffinityConfig:
    clientIP: {timeoutSeconds: 10800}

  externalTrafficPolicy: Local        # ⭐ 见下
  internalTrafficPolicy: Local        # 集群内流量只发给本节点的 Pod

  publishNotReadyAddresses: false     # true：未就绪的 Pod 也发布（StatefulSet 自举时用）

  ipFamilyPolicy: SingleStack         # 或 PreferDualStack / RequireDualStack
  ipFamilies: [IPv4]

  ports:
    - name: http
      port: 80
      targetPort: http
      appProtocol: http               # 提示给 LB/mesh，用于协议感知
    - name: grpc
      port: 9000
      targetPort: grpc
      appProtocol: grpc
```

**`externalTrafficPolicy` 是个高频考点**：

| 值 | 行为 | 源 IP | 负载均衡 |
|---|---|---|---|
| `Cluster`（默认） | 流量到任意节点后，可能被转发到**其他节点**的 Pod | ❌ 被 SNAT 覆盖，看到的是节点 IP | ✅ 均匀 |
| `Local` | 流量只发给**本节点**的 Pod；本节点没有就丢弃 | ✅ **保留真实客户端 IP** | ⚠️ 取决于 Pod 在节点间的分布 |

需要真实客户端 IP（日志、限流、地理位置）时用 `Local`，但必须配合 `topologySpreadConstraints` 保证每个节点都有 Pod。云 LB 会用健康检查自动跳过没有 Pod 的节点。

### 2.4 拓扑感知路由（省跨可用区流量费）

```yaml
metadata:
  annotations:
    service.kubernetes.io/topology-mode: Auto
# 或 1.33+ 的新字段：
spec:
  trafficDistribution: PreferClose     # 优先路由到同可用区的后端
```

跨可用区流量在云上是要收费的（AWS 约 $0.01/GB 双向）。大流量服务开启后能省下可观的成本，但要注意：如果某个可用区的 Pod 不够，可能造成负载不均。

---

## 3. kube-proxy：Service 是怎么实现的

**关键认知：ClusterIP 是一个"假 IP"。** 它不属于任何网卡，ping 不通，也没有任何进程监听它。它只是**内核转发规则里的一个匹配条件**。

```bash
kubectl get svc hello -o jsonpath='{.spec.clusterIP}'    # 10.96.5.20
kubectl run t --rm -it --image=busybox:1.37 --restart=Never -- ping -c2 10.96.5.20
# 100% packet loss —— 但是 wget http://10.96.5.20 却能通！
```

### 3.1 三种模式

| 模式 | 原理 | 复杂度 | 适用规模 |
|---|---|---|---|
| **iptables**（默认） | 每个 Service 生成一串 iptables 规则，用 `statistic` 模块做随机负载均衡 | 规则数 O(Service × 后端)，**线性匹配** | < 5000 Service |
| **IPVS** | 用内核的 LVS，哈希表查找 O(1)，支持多种调度算法（rr/lc/sh/dh） | 规则更新快、查找快 | 大集群 ⭐ |
| **nftables**（1.31+ beta，逐步成为默认） | iptables 的现代替代，性能接近 IPVS | 更新和匹配都更快 | 未来方向 |
| **无 kube-proxy** | Cilium 用 eBPF 直接在内核里做转发 | 性能最好 | Cilium 集群 ⭐ |

看 iptables 规则（在 kind 节点上）：

```bash
docker exec learn-worker iptables -t nat -L KUBE-SERVICES -n | head -20
# KUBE-SVC-XXXX  tcp -- 0.0.0.0/0  10.96.5.20  tcp dpt:80

docker exec learn-worker iptables -t nat -L KUBE-SVC-XXXXXXXX -n
# KUBE-SEP-AAA  statistic mode random probability 0.33333333349
# KUBE-SEP-BBB  statistic mode random probability 0.50000000000
# KUBE-SEP-CCC                                        ← 兜底
#   ↑ 这就是负载均衡：三分之一概率走第一个，剩下的一半走第二个……
```

**iptables 模式的性能问题**：规则是**线性遍历**的。5000 个 Service × 平均 10 个后端 = 几万条规则，每个包都要匹配一遍，且规则更新时要全量重刷（O(n²) 行为）。这是大集群改用 IPVS/eBPF 的原因。

切换到 IPVS 后可以直接看：

```bash
ipvsadm -Ln
# TCP  10.96.5.20:80 rr
#   -> 10.244.1.5:8080   Masq  1  0  0
#   -> 10.244.2.7:8080   Masq  1  0  0
```

### 3.2 一个重要后果：Service 的负载均衡是 L4 的

kube-proxy 在**连接建立时**选一个后端，之后这条 TCP 连接上的所有数据都走同一个 Pod。

**这对 HTTP/2 和 gRPC 是个大问题**：gRPC 默认复用一条长连接，所以**一个客户端的所有请求永远打到同一个 Pod**，负载完全不均。

解决方案：

| 方案 | 说明 |
|---|---|
| **Headless Service + 客户端负载均衡** ⭐ | gRPC-Go 支持：`grpc.NewClient("dns:///hello-headless:9000", grpc.WithDefaultServiceConfig(`{"loadBalancingConfig":[{"round_robin":{}}]}`))` |
| **L7 代理**（Envoy / Gateway / Service Mesh） | 代理层做请求级负载均衡 |
| **定期断开连接** | 服务端设 `MaxConnectionAge`，强制客户端重连重新分布 |

```go
// gRPC 服务端：让长连接定期重建，配合 Service 负载均衡
grpc.NewServer(grpc.KeepaliveParams(keepalive.ServerParameters{
    MaxConnectionAge:      30 * time.Minute,
    MaxConnectionAgeGrace: 5 * time.Second,
}))
```

---

## 4. DNS：服务发现

CoreDNS 是集群 DNS 服务器，它 watch Service 和 EndpointSlice，动态生成 DNS 记录。

```bash
kubectl -n kube-system get pods -l k8s-app=kube-dns
kubectl -n kube-system get svc kube-dns        # ClusterIP 通常是 10.96.0.10
kubectl -n kube-system get cm coredns -o yaml  # Corefile 配置
```

### 4.1 DNS 记录格式

```
<service>.<namespace>.svc.cluster.local              → ClusterIP
<pod-ip-dashed>.<namespace>.pod.cluster.local        → Pod IP（如 10-244-1-5.lab.pod.cluster.local）
<pod>.<service>.<namespace>.svc.cluster.local        → StatefulSet 的稳定 Pod DNS
_<port-name>._<proto>.<service>.<ns>.svc.cluster.local  → SRV 记录（带端口）
```

**同 namespace 内可以简写**：

```go
// 同 namespace
http.Get("http://hello/")                    // 最简
// 跨 namespace
http.Get("http://hello.prod/")
// 完全限定（推荐生产使用，见下）
http.Get("http://hello.prod.svc.cluster.local./")
```

### 4.2 `ndots: 5` 的性能陷阱（⭐ 重要）

容器里的 `/etc/resolv.conf`：

```bash
kubectl exec deploy/hello -- cat /etc/resolv.conf
# nameserver 10.96.0.10
# search lab.svc.cluster.local svc.cluster.local cluster.local
# options ndots:5
```

**`ndots:5` 的意思**：如果域名里的点少于 5 个，先依次拼接 search 域再查询。

所以解析外部域名 `api.github.com`（2 个点 < 5）时，会依次查询：

```
① api.github.com.lab.svc.cluster.local     → NXDOMAIN
② api.github.com.svc.cluster.local         → NXDOMAIN
③ api.github.com.cluster.local             → NXDOMAIN
④ api.github.com                           → ✅ 终于成功
```

**4 次查询，而且 IPv4/IPv6 各一次 = 8 次 DNS 请求**！这是 K8s 里最经典的性能问题之一，会导致：
- 每个外部请求多几十毫秒延迟
- CoreDNS QPS 被放大 8 倍，成为瓶颈
- 高并发下 CoreDNS 被打挂，表现为间歇性"域名解析失败"

**三种解决方案**：

```yaml
# ① 应用只访问集群内服务时，降低 ndots
spec:
  dnsConfig:
    options:
      - {name: ndots, value: "2"}
```

```go
// ② 外部域名末尾加点（FQDN，跳过 search 域）
http.Get("https://api.github.com./")
```

```yaml
# ③ 部署 NodeLocalDNSCache（大集群强烈推荐）
# 每个节点跑一个 DNS 缓存 DaemonSet，Pod 查本地缓存，
# 大幅降低 CoreDNS 负载和延迟，还能避免 conntrack race 导致的 5 秒超时
```

### 4.3 DNS 相关故障速查

```bash
# 起一个调试 Pod
kubectl run -it --rm dnsutils --image=nicolaka/netshoot --restart=Never -- bash

# 内部
nslookup hello
nslookup hello.lab.svc.cluster.local
dig +search hello                 # 模拟 search 域展开
dig @10.96.0.10 hello.lab.svc.cluster.local

# 外部
nslookup github.com
dig +trace github.com

# 看查询次数（观察 ndots 的影响）
tcpdump -i any -nn port 53
```

CoreDNS 自身排查：

```bash
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=50
kubectl -n kube-system get cm coredns -o yaml
# 可以在 Corefile 里加 `log` 插件打开查询日志（调试用，生产会刷屏）
```

---

## 5. 外部流量入口：Ingress 与 Gateway API

### 5.1 为什么需要它们

每个服务一个 LoadBalancer → 几十个云 LB → 贵，且没有统一的 TLS/路由/认证。

**Ingress / Gateway = 一个入口，按域名和路径路由到不同 Service。**

```
                互联网
                   │
        ┌──────────▼──────────┐
        │  一个 LoadBalancer   │
        │  (Ingress/Gateway   │
        │   Controller)       │
        └──────────┬──────────┘
       ┌───────────┼───────────┐
   /api│       /web│      /admin│
       ▼           ▼           ▼
  Service api  Service web  Service admin
```

### 5.2 ⚠️ 重要现状：ingress-nginx 已退役

**2026 年 3 月 24 日，Kubernetes SIG Network 正式退役了 `ingress-nginx` 项目**——不再有新版本、不再有 bug 修复、**不再有安全补丁**。计划中的继任者 InGate 也已终止。

这曾是安装量最大的 Ingress 控制器（约一半集群在用），所以这是一次影响面很大的变更。

**官方建议**：迁移到 Gateway API，或迁移到其他仍在维护的控制器。

| 迁移目标 | 说明 |
|---|---|
| **Envoy Gateway** ⭐ | 纯 Gateway API 实现，从 nginx 迁移最"干净"，CNCF 项目 |
| **Traefik** | 同时支持 Ingress 和 Gateway API，配置友好 |
| **HAProxy Kubernetes Ingress / Gateway** | 高性能、低延迟 |
| **Cilium Gateway** | 已经用 Cilium 做 CNI 的话最自然 |
| **nginxinc/kubernetes-ingress** | F5/NGINX 官方维护的**另一个**控制器（注意与退役的 ingress-nginx 不是同一个项目） |
| 云厂商方案 | AWS Load Balancer Controller、GKE Gateway 等 |

官方还提供了迁移工具 **[ingress2gateway](https://github.com/kubernetes-sigs/ingress2gateway)**（1.0 已发布），可以把 Ingress 资源转换成 Gateway API 资源。

**所以：新项目直接学 Gateway API。** 下面 Ingress 部分只讲你维护存量系统时需要知道的。

### 5.3 Ingress（存量知识）

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello
  annotations:
    # ⚠️ Ingress 的最大问题：高级功能全靠控制器私有的 annotation，
    # 换控制器就要全部重写，完全不可移植
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    nginx.ingress.kubernetes.io/proxy-body-size: 50m
spec:
  ingressClassName: nginx
  tls:
    - hosts: [hello.example.com]
      secretName: hello-tls
  rules:
    - host: hello.example.com
      http:
        paths:
          - path: /api(/|$)(.*)
            pathType: ImplementationSpecific   # Prefix | Exact | ImplementationSpecific
            backend:
              service:
                name: hello
                port: {name: http}
```

**Ingress 的三大局限**（也是 Gateway API 诞生的原因）：
1. **表达能力弱**：只有 host + path。想按 header、method、权重路由？只能用 annotation
2. **不可移植**：annotation 是各控制器私有的
3. **没有角色分离**：基础设施团队和应用团队都在改同一个对象，无法做权限隔离

Ingress API 本身**没有被废弃**，但已经**功能冻结**——不会再加新特性。

### 5.4 Gateway API（现在和未来）⭐

Gateway API 当前版本 **v1.6.0**（2026-06 发布）。它以 CRD 形式提供，需要单独安装。

**核心设计：角色分离**

```
┌─────────────────────────────────────────────────────────┐
│ GatewayClass  ← 基础设施提供方（谁来实现，如 Envoy）         │
│    ↑                                                     │
│ Gateway       ← 集群运维（在哪监听、什么端口、什么证书）      │
│    ↑                                                     │
│ HTTPRoute     ← 应用开发者（我的流量怎么路由）              │
│ GRPCRoute                                                │
│ TLSRoute / TCPRoute / UDPRoute                           │
└─────────────────────────────────────────────────────────┘
```

三层由不同团队拥有，用 RBAC 分开管理——这是 Ingress 做不到的。

```yaml
# ① GatewayClass：由控制器提供方创建（装 Envoy Gateway 时会自带）
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata: {name: envoy}
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
---
# ② Gateway：集群运维创建，定义入口
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: main-gateway
  namespace: infra
spec:
  gatewayClassName: envoy
  listeners:
    - name: http
      protocol: HTTP
      port: 80
    - name: https
      protocol: HTTPS
      port: 443
      hostname: "*.example.com"
      tls:
        mode: Terminate
        certificateRefs:
          - {kind: Secret, name: wildcard-tls}
      allowedRoutes:              # ⭐ 控制哪些 namespace 能挂路由上来
        namespaces:
          from: Selector
          selector:
            matchLabels: {gateway-access: "true"}
---
# ③ HTTPRoute：应用团队创建，在自己的 namespace 里
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: hello
  namespace: lab
spec:
  parentRefs:
    - {name: main-gateway, namespace: infra}
  hostnames: ["hello.example.com"]
  rules:
    # 规则 1：按 header 路由（Ingress 做不到）
    - matches:
        - path: {type: PathPrefix, value: /api}
          headers:
            - {name: x-canary, value: "true"}
      backendRefs:
        - {name: hello-canary, port: 80}

    # 规则 2：⭐ 按权重灰度（金丝雀发布的基础，第 19 章）
    - matches:
        - path: {type: PathPrefix, value: /api}
      backendRefs:
        - {name: hello, port: 80, weight: 90}
        - {name: hello-canary, port: 80, weight: 10}

    # 规则 3：路径重写 + 加请求头（标准字段，不是 annotation！）
    - matches:
        - path: {type: PathPrefix, value: /legacy}
      filters:
        - type: URLRewrite
          urlRewrite:
            path: {type: ReplacePrefixMatch, replacePrefix: /}
        - type: RequestHeaderModifier
          requestHeaderModifier:
            add: [{name: X-Gateway, value: envoy}]
      backendRefs:
        - {name: legacy-svc, port: 8080}

    # 规则 4：超时与重试（1.6 已稳定）
    - matches:
        - path: {type: PathPrefix, value: /slow}
      timeouts:
        request: 30s
        backendRequest: 10s
      backendRefs:
        - {name: slow-svc, port: 80}
```

**Gateway API 相比 Ingress 的优势**：

| 能力 | Ingress | Gateway API |
|---|---|---|
| 按 header/query/method 路由 | ❌ annotation | ✅ 标准字段 |
| 流量按权重切分 | ❌ annotation | ✅ 标准字段（灰度发布） |
| 请求/响应头修改 | ❌ annotation | ✅ 标准 filter |
| 超时/重试 | ❌ annotation | ✅ 标准字段 |
| gRPC 一等公民 | ❌ | ✅ GRPCRoute |
| TCP/UDP/TLS 直通 | ❌ | ✅ |
| 跨 namespace 路由 | ❌ | ✅ ReferenceGrant |
| 角色分离 | ❌ | ✅ 三层模型 |
| 可移植性 | ❌ | ✅ 标准一致 |

安装（以 Envoy Gateway 为例）：

```bash
# ① 安装 Gateway API CRD
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.0/standard-install.yaml

# ② 安装一个实现
helm install eg oci://docker.io/envoyproxy/gateway-helm --version v1.6.0 \
  -n envoy-gateway-system --create-namespace

kubectl get gatewayclass
```

### 5.5 TLS 证书自动化：cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set crds.enabled=true
```

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata: {name: letsencrypt-prod}
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: you@example.com
    privateKeySecretRef: {name: letsencrypt-prod}
    solvers:
      - http01:
          gatewayHTTPRoute:
            parentRefs: [{name: main-gateway, namespace: infra, kind: Gateway}]
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata: {name: hello-tls, namespace: infra}
spec:
  secretName: hello-tls          # 自动生成/续期这个 Secret
  issuerRef: {name: letsencrypt-prod, kind: ClusterIssuer}
  dnsNames: ["hello.example.com"]
```

cert-manager 会自动申请证书、在到期前 30 天自动续期、更新 Secret。**这是 Operator 模式最优雅的应用之一**（第 6 章）。

---

## 6. NetworkPolicy：网络隔离

**默认情况下，集群里任何 Pod 都能访问任何其他 Pod**——这是巨大的安全隐患（一个被攻破的前端能直连数据库）。

NetworkPolicy 是 Pod 级的防火墙。⚠️ **需要 CNI 支持**（Calico/Cilium 支持，Flannel 和 kindnet **不支持**——策略会被静默忽略！）。

```yaml
# ① 默认拒绝该 namespace 内所有入站（零信任的起点）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: prod
spec:
  podSelector: {}          # 空 selector = 所有 Pod
  policyTypes: [Ingress]
---
# ② 只允许 api 访问 db
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-allow-api
  namespace: prod
spec:
  podSelector:
    matchLabels: {app: db}
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector: {matchLabels: {app: api}}       # 同 namespace 的 api
        - namespaceSelector: {matchLabels: {name: monitoring}}   # 监控 namespace
      ports:
        - {protocol: TCP, port: 5432}
  egress:
    # ⭐ 必须显式放行 DNS，否则 Pod 连域名都解析不了（最常见的踩坑）
    - to:
        - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}
          podSelector: {matchLabels: {k8s-app: kube-dns}}
      ports:
        - {protocol: UDP, port: 53}
        - {protocol: TCP, port: 53}
```

**语义要点**（容易搞错）：

1. **白名单模型**：没有任何 NetworkPolicy 选中的 Pod = 全通；**一旦有任何一条策略选中它，就变成"只允许明确列出的"**
2. **多条策略是 OR 关系**（并集），不是 AND
3. **Ingress 和 Egress 独立**：只写 ingress 规则不影响出站
4. **必须放行 DNS**，否则所有域名解析失败（表现为服务"莫名连不上"）
5. **`from` 里的多个条目是 OR**，但同一个条目里的 `namespaceSelector` + `podSelector` 是 **AND**

```yaml
# 注意这两个的区别！
from:
  - namespaceSelector: {matchLabels: {env: prod}}
    podSelector: {matchLabels: {app: api}}      # AND：prod namespace 里的 api Pod
---
from:
  - namespaceSelector: {matchLabels: {env: prod}}   # OR：prod namespace 里的所有 Pod
  - podSelector: {matchLabels: {app: api}}          #  或 本 namespace 里的 api Pod
```

**生产实践**：每个 namespace 先上 `default-deny`，再逐个放行。Cilium 的 `CiliumNetworkPolicy` 还支持 L7 规则（"只允许 GET /api/v1/*"）。

---

## 7. Service Mesh（简要）

当你需要：服务间 mTLS、细粒度流量切分、自动重试/熔断、分布式追踪自动注入、跨服务的统一策略——可以考虑 Service Mesh。

| 方案 | 数据面 | 特点 |
|---|---|---|
| **Istio**（ambient 模式） | ztunnel（L4）+ waypoint（L7） | 功能最全；ambient 模式去掉了每 Pod sidecar，资源开销大降 |
| **Linkerd** | 轻量 Rust 代理 | 简单、快、易运维 |
| **Cilium Service Mesh** | eBPF + Envoy | 无 sidecar，与 CNI 一体 |

**建议**：不要一开始就上 mesh。先问清楚"我到底要解决什么问题"：
- 只要 mTLS？→ 也许 Linkerd 或 Cilium 就够
- 只要灰度？→ Gateway API + Argo Rollouts 就够（第 19 章）
- 只要重试熔断？→ 在 Go 客户端库里做（`grpc-go` 的 retry policy、`sony/gobreaker`）更简单
- 服务数量 < 20？→ 大概率不需要 mesh

---

## 8. 动手实验

### 实验 1：Service 与 EndpointSlice

```bash
kubectl create ns net && kubectl config set-context --current --namespace=net
kubectl create deployment hello --image=hello:v0.1.0 --replicas=3
kubectl set image deployment/hello hello=hello:v0.1.0
kubectl patch deployment hello -p '{"spec":{"template":{"spec":{"containers":[{"name":"hello","imagePullPolicy":"IfNotPresent","readinessProbe":{"httpGet":{"path":"/readyz","port":8080},"periodSeconds":2}}]}}}}'
kubectl expose deployment hello --port=80 --target-port=8080
kubectl rollout status deploy/hello

kubectl get svc hello -o wide
kubectl get endpointslices -l kubernetes.io/service-name=hello -o yaml | grep -A3 addresses

# 验证负载均衡
kubectl run -it --rm client --image=busybox:1.37 --restart=Never -- \
  sh -c 'for i in $(seq 12); do wget -qO- http://hello/ | grep -o "\"hostname\":\"[^\"]*\""; done'
# 输出应在 3 个 Pod 名之间轮转
```

### 实验 2：⭐ readiness 控制流量（对比第 5 章的 DNS 轮询缺陷）

```bash
# 挑一个 Pod，把它的 readiness 弄失败（改标签让它脱离 Service 更简单）
POD=$(kubectl get pod -l app=hello -o name | head -1)
kubectl label $POD app=hello-excluded --overwrite

kubectl get endpointslices -l kubernetes.io/service-name=hello -o jsonpath='{.items[*].endpoints[*].addresses[*]}'
# 只剩 2 个 IP ✅ —— 流量自动摘除，没有任何请求失败

kubectl label $POD app=hello --overwrite    # 加回来
```

### 实验 3：ClusterIP 是假 IP

```bash
CIP=$(kubectl get svc hello -o jsonpath='{.spec.clusterIP}')
echo $CIP
kubectl run -it --rm t --image=nicolaka/netshoot --restart=Never -- \
  sh -c "ping -c2 -W1 $CIP; echo '--- 但 HTTP 能通 ---'; curl -s $CIP | head -c 100"

# 看 iptables 规则
docker exec learn-worker iptables -t nat -S | grep $CIP
```

### 实验 4：NodePort

```bash
kubectl patch svc hello -p '{"spec":{"type":"NodePort","ports":[{"port":80,"targetPort":8080,"nodePort":30080}]}}'
# kind 配置里已经把 30080 映射到 Mac 了（第 0 章）
curl -s localhost:30080 | jq
```

### 实验 5：DNS 全景

```bash
kubectl run -it --rm dns --image=nicolaka/netshoot --restart=Never -- bash
# 在里面执行：
cat /etc/resolv.conf
nslookup hello
nslookup hello.net.svc.cluster.local
dig +short hello.net.svc.cluster.local
dig SRV _http._tcp.hello.net.svc.cluster.local +short

# ⭐ 观察 ndots 的开销
time dig github.com +search
time dig github.com. +search      # 加了末尾点，快很多
exit
```

### 实验 6：Headless Service 与 gRPC 负载均衡

```bash
kubectl create service clusterip hello-headless --clusterip=None --tcp=80:8080
kubectl patch svc hello-headless -p '{"spec":{"selector":{"app":"hello"}}}'

kubectl run -it --rm dns --image=nicolaka/netshoot --restart=Never -- \
  sh -c 'dig +short hello-headless.net.svc.cluster.local'
# 直接返回 3 个 Pod IP（而不是一个 ClusterIP）
```

### 实验 7：NetworkPolicy（需要支持的 CNI）

kind 默认的 kindnet **不支持** NetworkPolicy。想做这个实验，用 Calico 重建集群：

```bash
kind delete cluster --name learn
# 在 kind 配置里加 networking.disableDefaultCNI: true 和 podSubnet
kind create cluster --config ~/kind-learn.yaml
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.30.0/manifests/calico.yaml
```

然后：

```bash
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: deny-all, namespace: net}
spec:
  podSelector: {}
  policyTypes: [Ingress]
EOF

kubectl run -it --rm t --image=busybox:1.37 --restart=Never -- \
  wget -qO- -T3 http://hello/     # 超时 ❌

# 放行
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: allow-client, namespace: net}
spec:
  podSelector: {matchLabels: {app: hello}}
  ingress:
    - from: [{podSelector: {matchLabels: {role: client}}}]
EOF

kubectl run -it --rm t --labels="role=client" --image=busybox:1.37 --restart=Never -- \
  wget -qO- -T3 http://hello/     # ✅
```

### 实验 8：Gateway API

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.0/standard-install.yaml
helm install eg oci://docker.io/envoyproxy/gateway-helm --version v1.6.0 \
  -n envoy-gateway-system --create-namespace
kubectl -n envoy-gateway-system rollout status deploy/envoy-gateway

kubectl apply -f - <<'EOF'
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata: {name: demo-gw, namespace: net}
spec:
  gatewayClassName: eg
  listeners:
    - {name: http, protocol: HTTP, port: 80, allowedRoutes: {namespaces: {from: Same}}}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata: {name: hello-route, namespace: net}
spec:
  parentRefs: [{name: demo-gw}]
  rules:
    - matches: [{path: {type: PathPrefix, value: /}}]
      backendRefs: [{name: hello, port: 80}]
EOF

kubectl get gateway,httproute -n net
kubectl -n envoy-gateway-system get svc      # 找到 Envoy 的 Service
kubectl -n envoy-gateway-system port-forward svc/<envoy-svc-name> 8888:80 &
curl -s localhost:8888 | jq
kill %1
```

### 清理

```bash
kubectl delete ns net
kubectl config set-context --current --namespace=default
```

---

## 9. 网络排障速查

| 现象 | 排查步骤 |
|---|---|
| Service 访问不通 | ① `kubectl get endpointslices -l kubernetes.io/service-name=X` 有后端吗？<br>② 没有 → selector 和 Pod label 对得上吗？Pod Ready 吗？<br>③ 有 → 直接 `curl <PodIP>:<port>` 通吗？<br>④ 通 → kube-proxy 有问题，看它的日志和 iptables 规则 |
| DNS 解析失败 | ① `kubectl -n kube-system get pods -l k8s-app=kube-dns`<br>② `nslookup kubernetes.default` 测基本功能<br>③ 检查 NetworkPolicy 是否挡了 53 端口<br>④ 看 CoreDNS 日志和资源使用 |
| 间歇性超时/5 秒延迟 | 经典的 conntrack race（DNS 并发查询）→ 上 NodeLocalDNSCache，或用 `single-request-reopen` |
| 跨节点 Pod 不通 | CNI 问题：检查 CNI Pod 状态、节点路由表、VXLAN/BGP 隧道、安全组/防火墙是否放行 CNI 端口 |
| LoadBalancer 一直 pending | 自建集群没有 LB 实现 → 装 MetalLB；云上检查 CCM 日志和配额 |
| 502/503 | 后端 Pod 未 Ready，或应用真的挂了；检查 Endpoint、探针、应用日志 |
| 拿不到真实客户端 IP | `externalTrafficPolicy: Local`，或用 L7 代理的 `X-Forwarded-For` |
| gRPC 负载不均 | 长连接复用 → 用 headless + 客户端 LB，或设 `MaxConnectionAge` |

---

## 10. 本章检查清单

- [ ] K8s 网络模型的四条铁律是什么？和 Docker 最大的区别？
- [ ] 三个 IP 段分别是什么？Pod CIDR 怎么影响集群规模上限？
- [ ] Service 的四种类型，各自适用什么场景？它们是什么关系？
- [ ] Headless Service 和普通 Service 的区别？什么时候用？
- [ ] EndpointSlice 相比 Endpoints 解决了什么问题？
- [ ] ClusterIP 能 ping 通吗？为什么？它是怎么实现的？
- [ ] kube-proxy 三种模式的区别？大集群该用哪个？
- [ ] `externalTrafficPolicy: Local` 和 `Cluster` 的取舍？
- [ ] 为什么 gRPC 在 Service 上负载不均？三种解法？
- [ ] `ndots: 5` 会造成什么问题？三种优化方案？
- [ ] ingress-nginx 现在的状态是什么？该迁移到哪里？
- [ ] Gateway API 的三层角色模型是什么？相比 Ingress 的 5 个优势？
- [ ] NetworkPolicy 的白名单语义是什么？为什么必须放行 DNS？
- [ ] 完成实验 1、2、5

---

## 11. 延伸阅读

- [Service](https://kubernetes.io/docs/concepts/services-networking/service/)
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Gateway API](https://gateway-api.sigs.k8s.io/)
- [ingress2gateway 迁移工具](https://kubernetes.io/blog/2026/03/20/ingress2gateway-1-0-release)
- [NetworkPolicy 教程](https://github.com/ahmetb/kubernetes-network-policy-recipes)（图解，非常好）
- [Cilium 文档](https://docs.cilium.io/)

---

下一章：[11 - 存储：Volume、PV、PVC 与 CSI](./11-storage.md)
