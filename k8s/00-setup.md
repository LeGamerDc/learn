# 00 - 环境准备

> 本章目标：在你的 macOS (Apple Silicon) 上装好整个课程需要的工具链，并起一个**多节点** Kubernetes 集群。
> 预计用时：40 分钟（大部分时间在等下载）。

你的机器：macOS 26.4 / arm64 / 已装 Go 1.26。当前 `docker`、`kubectl`、`helm` 都没有。下面从零开始。

---

## 1. 先理解你在装什么

macOS 上**跑不了 Linux 容器**——容器不是虚拟化，它复用宿主机内核，而容器镜像里装的是 Linux 用户态。所以 Mac 上所有容器方案的本质都是：

```
  macOS
    └── 一个轻量 Linux 虚拟机 (Apple Virtualization.framework)
          └── 容器运行时 (containerd / dockerd)
                └── 你的容器
```

`docker` 命令行只是个客户端，它通过 socket 跟 VM 里的守护进程说话。这解释了两个后面会遇到的现象：

- **文件挂载慢**：`-v $PWD:/app` 要跨 VM 边界做文件共享。
- **`localhost` 语义微妙**：容器里的 `localhost` 是容器自己，不是你的 Mac，也不是 VM。第 4 章详解。

Linux 用户没有这层 VM，`docker` 直接和本机内核对话。

### 方案选择

| 方案 | 说明 | 建议 |
|---|---|---|
| **Colima** | 开源、命令行、基于 Lima + Virtualization.framework，装 Docker CLI 用 | ✅ **本课程推荐**：轻、免费、可控、贴近 Linux 真实行为 |
| **OrbStack** | 商业软件，个人免费，最快最省电，Mac 集成最好 | ✅ 也很好，图形界面党可选 |
| **Rancher Desktop** | SUSE 出品，开源，自带 k3s | 可选，稍重 |
| **Docker Desktop** | 官方，大企业（>250 人或年营收 >1000 万美元）需付费订阅 | ⚠️ 注意商业授权 |
| **Podman Desktop** | 无守护进程、rootless，与 Docker CLI 兼容 | 可选 |

下面按 Colima 走。用 OrbStack 的话跳过 1.2，其余相同。

---

## 2. 安装

### 2.1 Homebrew（如果还没有）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2.2 容器运行时

```bash
brew install colima docker docker-buildx docker-compose
# colima 是 VM 管理器；docker 是 CLI（不含 Desktop）；buildx 用于多架构构建
```

注册 CLI 插件（buildx / compose 是 docker 的子命令插件）：

```bash
mkdir -p ~/.docker/cli-plugins
ln -sfn $(brew --prefix)/opt/docker-buildx/bin/docker-buildx ~/.docker/cli-plugins/docker-buildx
ln -sfn $(brew --prefix)/opt/docker-compose/bin/docker-compose ~/.docker/cli-plugins/docker-compose
```

启动 VM（4 核 / 8G 内存 / 60G 磁盘，跑本课程的多节点集群够用；内存小于 6G 后面装监控栈会 OOM）：

```bash
colima start --cpu 4 --memory 8 --disk 60 --vm-type=vz --mount-type=virtiofs
```

- `--vm-type=vz`：用 Apple 原生虚拟化（比 QEMU 快很多）
- `--mount-type=virtiofs`：文件挂载性能最好

验证：

```bash
docker version          # Client 和 Server 都要有输出
docker run --rm hello-world
colima status
```

> **停止 / 重启**：`colima stop` / `colima start`。VM 状态持久化，镜像不会丢。
> **彻底重来**：`colima delete`（会删掉所有镜像和容器）。

### 2.3 Kubernetes 工具链

```bash
brew install kubectl kind helm k9s stern kubectx
brew install argocd            # Argo CD CLI（第 18 章用）
brew install kustomize         # 第 16 章
```

| 工具 | 作用 |
|---|---|
| `kubectl` | K8s 官方 CLI，你 80% 的时间都在用它 |
| `kind` | Kubernetes IN Docker：用容器当"节点"，秒级起多节点集群 |
| `helm` | 包管理器（第 15 章） |
| `k9s` | 终端 UI，浏览集群资源，排障神器 |
| `stern` | 多 Pod 日志聚合 tail（第 13 章） |
| `kubectx` / `kubens` | 快速切换集群和命名空间 |

配置 kubectl 自动补全（zsh）：

```bash
echo 'source <(kubectl completion zsh)' >> ~/.zshrc
echo 'alias k=kubectl' >> ~/.zshrc
echo 'compdef __start_kubectl k' >> ~/.zshrc
source ~/.zshrc
```

---

## 3. 起一个多节点集群

单节点集群学不到调度、亲和性、节点故障、Pod 分布这些核心内容。我们直接起 **1 控制面 + 3 工作节点**。

创建 `~/kind-learn.yaml`：

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: learn
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:          # 把 Mac 的端口透到集群里，方便本地访问
      - containerPort: 30080    # NodePort 范围
        hostPort: 30080
        protocol: TCP
      - containerPort: 30443
        hostPort: 30443
        protocol: TCP
  - role: worker
    labels:
      topology.kubernetes.io/zone: zone-a
      node-pool: general
  - role: worker
    labels:
      topology.kubernetes.io/zone: zone-b
      node-pool: general
  - role: worker
    labels:
      topology.kubernetes.io/zone: zone-c
      node-pool: memory-optimized
```

> 这里给节点打了假的"可用区"标签，第 12 章讲拓扑分布约束时会用到——本地也能模拟跨机房调度。

创建集群：

```bash
kind create cluster --config ~/kind-learn.yaml
```

验证：

```bash
kubectl get nodes -o wide
# NAME                  STATUS   ROLES           AGE   VERSION
# learn-control-plane   Ready    control-plane   1m    v1.3x.x
# learn-worker          Ready    <none>          1m    v1.3x.x
# learn-worker2         Ready    <none>          1m    v1.3x.x
# learn-worker3         Ready    <none>          1m    v1.3x.x

kubectl get pods -A         # 看控制面组件都在跑
```

**这里有个"啊哈"时刻**：在 Mac 上执行

```bash
docker ps
```

你会看到 4 个容器——**kind 的"节点"就是容器**。每个容器里跑着 kubelet 和 containerd，容器里再跑容器。这直观说明了"节点"对 K8s 而言只是一个能跑容器的执行单元。

常用集群管理命令：

```bash
kind get clusters
kind delete cluster --name learn      # 删掉重来（本课程会重来很多次，这很正常）
kubectl config get-contexts
kubectl config use-context kind-learn
```

### 3.1 装 metrics-server（`kubectl top` 需要）

kind 的 kubelet 证书是自签的，需要加 `--kubelet-insecure-tls`：

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# 等 1 分钟后验证
kubectl top nodes
kubectl top pods -A
```

---

## 4. 本地镜像仓库（重要）

kind 集群**看不到**你 Mac 上 `docker build` 出来的镜像——它们在不同的 containerd 里。有三种解决方式，课程里都会用到：

**方式 A：直接把镜像塞进 kind 节点（最简单，日常实验用）**

```bash
docker build -t myapp:v1 .
kind load docker-image myapp:v1 --name learn
```

**方式 B：起一个本地 registry（更接近真实流程，第 17 章 CI 会用）**

```bash
# 起 registry
docker run -d --restart=always -p 5001:5000 --name kind-registry registry:2

# 把它连到 kind 的网络上
docker network connect kind kind-registry

# 告诉集群里的 containerd：localhost:5001 是可信的 http 仓库
for node in $(kind get nodes --name learn); do
  docker exec "$node" mkdir -p /etc/containerd/certs.d/localhost:5001
  cat <<EOF | docker exec -i "$node" cp /dev/stdin /etc/containerd/certs.d/localhost:5001/hosts.toml
server = "http://kind-registry:5000"
[host."http://kind-registry:5000"]
  capabilities = ["pull", "resolve"]
EOF
done
```

之后：`docker tag myapp:v1 localhost:5001/myapp:v1 && docker push localhost:5001/myapp:v1`，
清单里写 `image: localhost:5001/myapp:v1`。

**方式 C：用公网仓库**（Docker Hub / GHCR）——第 17 章讲 CI 时用。

---

## 5. 验收清单

全部通过再进入第 1 章：

```bash
# 1. 容器能跑
docker run --rm alpine echo "container ok"

# 2. 集群 4 个节点全 Ready
kubectl get nodes | grep -c Ready        # 应输出 4

# 3. 能跑起一个 Pod 并访问
kubectl run nginx --image=nginx:alpine
kubectl wait --for=condition=Ready pod/nginx --timeout=60s
kubectl port-forward pod/nginx 8080:80 &
curl -s localhost:8080 | head -3          # 应看到 nginx 欢迎页 HTML
kill %1; kubectl delete pod nginx

# 4. metrics 可用
kubectl top nodes

# 5. helm 可用
helm version                              # 应该是 v4.x

# 6. k9s 能进（按 q 退出）
k9s
```

---

## 6. 可选：一台真正的 Linux 机器

kind 有几个学不到的东西：真实的 CNI 网络插件、真实的负载均衡器、节点重启/故障、内核参数调优、真实的存储。

如果你有云服务器或本地 Linux 机器，强烈建议在阶段二结束后按第 21 章的指引，用 `kubeadm` **手工搭一遍集群**（哪怕单节点）。手工搭一遍是理解控制面组件的最快方式——你会被迫处理证书、etcd、CNI、kubelet 配置这些 kind 帮你藏起来的东西。

最轻量的真实体验：一台 2C4G 的 Linux VM 上装 k3s：

```bash
curl -sfL https://get.k3s.io | sh -
sudo k3s kubectl get nodes
```

---

## 7. 磁盘与清理

Colima 的 VM 磁盘只增不减，镜像层会堆积。定期清理：

```bash
docker system df                  # 看占用
docker system prune -a --volumes  # 清理所有未使用的镜像/容器/卷（谨慎）
kind delete cluster --name learn  # 删集群
```

---

## 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| `docker: Cannot connect to the Docker daemon` | Colima 没启动，或 `DOCKER_HOST` 没设 | `colima start`；`docker context use colima` |
| `kind create cluster` 卡在 "Starting control-plane" | VM 内存/CPU 不足 | `colima stop && colima start --cpu 4 --memory 8` |
| 镜像 pull 极慢或超时 | 网络到 Docker Hub 不通 | 配置镜像加速器：`colima start --docker '{"registry-mirrors":["https://<你的加速地址>"]}'` |
| `exec format error` | 拉到了 amd64 镜像在 arm64 上跑 | 构建时加 `--platform linux/arm64`，见第 3 章多架构小节 |
| `kubectl top` 报 `Metrics API not available` | metrics-server 未装或证书问题 | 见 §3.1 |
| 集群重启后 Pod 全 Pending | Colima VM 重启，kind 节点容器没起 | `docker start $(kind get nodes --name learn)` |

---

下一章：[01 - 部署的演进史：我们到底在解决什么问题](./01-evolution.md)
