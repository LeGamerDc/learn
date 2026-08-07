# 02 - 容器的本质：namespace、cgroup 与联合文件系统

> 本章目标：拆开 Docker 这个黑盒。学完你应该能**不用 Docker，用几条 shell 命令手工造一个容器**，
> 并且能解释清楚 Docker / containerd / runc / CRI 到底谁是谁。
> 预计用时：2 小时（含实验）。

---

## 1. 一句话回顾

> **容器 = 一个普通 Linux 进程 + 被 namespace 限制了"能看到什么" + 被 cgroup 限制了"能用多少" + 用 chroot/pivot_root 换掉了根文件系统。**

三个关键词分别对应内核的三组能力：

| 能力 | 内核机制 | 解决什么 |
|---|---|---|
| **隔离视野**（我看到的世界） | namespace | 进程、网络、挂载、主机名、用户、IPC 的隔离 |
| **限制资源**（我能用多少） | cgroup | CPU、内存、IO、PID 数量的配额 |
| **独立文件系统**（我的根目录） | chroot / pivot_root + OverlayFS | 应用带着自己的 `/usr`、`/lib`、`/etc` |
| （附加）**削减权限** | capabilities / seccomp / LSM | 即使 root 也不能为所欲为 |

---

## 2. Namespace：限制"能看到什么"

Linux 内核目前有 8 种 namespace：

| Namespace | 隔离的对象 | 你会在哪遇到 |
|---|---|---|
| **PID** | 进程号 | 容器里 `ps` 只看到自己的进程；容器内 PID 1 是你的应用（信号处理，见第 4 章） |
| **NET** | 网卡、IP、路由表、iptables、端口 | 容器有独立 IP；端口映射的根源；**K8s 里一个 Pod 内所有容器共享它** |
| **MNT** | 挂载点 | 容器有自己的 `/`；volume 挂载的根源 |
| **UTS** | hostname、domainname | `docker run -h myhost` |
| **IPC** | System V IPC、POSIX 消息队列、共享内存 | 同 Pod 内容器可共享 |
| **USER** | UID/GID 映射 | rootless 容器；容器内 root ≠ 宿主机 root（K8s 1.36 GA） |
| **CGROUP** | cgroup 根目录视图 | 容器内看不到宿主机的 cgroup 层级 |
| **TIME** | 系统时钟偏移（5.6+） | 很少用 |

### 关键点：namespace 可以独立组合

这是理解 **Pod** 的钥匙。容器不是"要么全隔离要么不隔离"，每种 namespace 都能单独选择"新建"还是"加入已有的"。

```bash
# 容器 B 加入容器 A 的网络 namespace —— 它们共享 IP 和端口空间
docker run -d --name a nginx:alpine
docker run --rm --network=container:a nicolaka/netshoot curl -s localhost:80 | head -3
#                    ^^^^^^^^^^^^^^^^ 关键：不新建 NET ns，加入 a 的
```

**这正是 K8s Pod 的实现方式**：一个 Pod 内的所有容器共享 NET + IPC + UTS namespace（可选共享 PID），但**各自有独立的 MNT namespace**（所以文件系统互相看不见，要共享得靠 volume）。

所以 Pod 里的容器：
- 可以用 `localhost` 互相访问 ✅（共享 NET）
- 端口不能冲突 ⚠️（共享 NET）
- 看不到对方的文件 ❌（独立 MNT），要共享得挂同一个 `emptyDir`

### 实验：手工造一个 namespace

macOS 上要先进 Linux VM：

```bash
colima ssh          # 进入 Lima VM，下面都在 Linux 里操作
```

```bash
# 新建 UTS + PID + MNT namespace，并在里面跑 bash
sudo unshare --uts --pid --mount --fork --mount-proc /bin/bash

# 进去之后：
hostname container-demo     # 改主机名
hostname                    # container-demo
ps aux                      # 只看得到 bash 和 ps —— 这就是 PID namespace
echo $$                     # 1 —— 你就是 PID 1

exit
hostname                    # 回到宿主机，主机名没变 —— 隔离生效
```

`--mount-proc` 很关键：`ps` 读的是 `/proc`，不重新挂载 `/proc` 的话你还是会看到宿主机全部进程。**这说明"隔离"不是自动的，是要一件件做的。**

### 看一个真实容器的 namespace

```bash
docker run -d --name demo nginx:alpine
PID=$(docker inspect -f '{{.State.Pid}}' demo)
sudo ls -l /proc/$PID/ns/
# lrwxrwxrwx ... ipc -> 'ipc:[4026532...]'
# lrwxrwxrwx ... mnt -> 'mnt:[4026532...]'
# lrwxrwxrwx ... net -> 'net:[4026532...]'
# lrwxrwxrwx ... pid -> 'pid:[4026532...]'

# 对比宿主机自己的（PID 1）
sudo ls -l /proc/1/ns/
# 编号不同 = 不同 namespace
```

**在宿主机上直接能看到容器进程**：

```bash
ps -ef | grep nginx      # 就在宿主机进程表里，只是它自己看不到别人
```

这再次印证：容器就是进程。没有"容器"这个内核对象。

---

## 3. cgroup：限制"能用多少"

cgroup（control group）是内核的资源计量与限制机制。现代系统用 **cgroup v2**（统一层级，K8s 1.31+ 要求 v2）。

```bash
# 起一个限内存 50MB、CPU 0.5 核的容器
docker run -d --name limited --memory=50m --cpus=0.5 nginx:alpine

# 在宿主机上看它的 cgroup（cgroup v2 路径）
PID=$(docker inspect -f '{{.State.Pid}}' limited)
cat /proc/$PID/cgroup
# 0::/system.slice/docker-<id>.scope

cd /sys/fs/cgroup/system.slice/docker-*.scope
cat memory.max        # 52428800  = 50MB
cat cpu.max           # 50000 100000  → 每 100ms 周期最多用 50ms CPU = 0.5 核
cat memory.current    # 当前用量
cat pids.current      # 当前进程数
```

### 关键概念：CPU 限制是"时间片配额"

`cpu.max = 50000 100000` 的意思是：每 100ms 的调度周期里，这个 cgroup 最多能用 50ms 的 CPU 时间。

**这会带来一个后面 K8s 章节的重大陷阱**：CPU limit 是硬性节流（throttling）。如果你的 Go 服务突发需要 CPU（比如 GC），配额用完就会被**强制暂停**到下个周期，表现为**莫名其妙的 P99 延迟毛刺**。第 7、12 章会详细讲 requests/limits 该怎么配。

Go 的另一个大坑：`runtime.GOMAXPROCS` 默认读的是**宿主机的 CPU 核数**（`/proc/cpuinfo`），不是 cgroup 配额。宿主机 64 核、你限 0.5 核，Go 会开 64 个 P 疯狂调度，导致严重的上下文切换和节流。

> 解决方案：
> - Go 1.25+ 起，runtime 已经能感知 cgroup CPU limit 并自动设置 GOMAXPROCS（在 Linux 上，容器化环境）。
> - 更早版本或需要确定性行为：用 [`go.uber.org/automaxprocs`](https://github.com/uber-go/automaxprocs)，一行 `import _ "go.uber.org/automaxprocs"` 即可。
> - 或者在部署清单里显式 `GOMAXPROCS` 环境变量（第 8 章会用 Downward API 从 limit 推导）。
>
> 内存侧同理：`GOMEMLIMIT`（Go 1.19+）应设为容器 memory limit 的 ~80%，否则 Go 堆会一路涨到被 OOMKill。第 7 章有完整配置。

### 实验：亲眼看到 OOMKill

```bash
# 限制 20MB 内存，然后申请 100MB
docker run --rm --memory=20m --memory-swap=20m alpine \
  sh -c 'dd if=/dev/zero of=/dev/shm/fill bs=1M count=100'
# 会被 kill

docker run -d --name oomtest --memory=20m --memory-swap=20m alpine \
  sh -c 'dd if=/dev/zero of=/dev/shm/fill bs=1M count=100; sleep 1000'
sleep 3
docker inspect oomtest -f '{{.State.OOMKilled}} {{.State.ExitCode}}'
# true 137          ← 137 = 128 + 9 (SIGKILL)。K8s 里看到 137 就是这个
docker rm -f oomtest
```

**记住 137 这个退出码**，第 22 章排障时天天见。

---

## 4. 联合文件系统：镜像分层的物理基础

容器的根文件系统来自镜像。镜像是**分层只读**的，容器启动时在最上面加一个**可写层**（copy-on-write）。

```
        ┌──────────────────────────┐
容器层   │  可写层 (upperdir)         │  ← 容器运行时的所有写入都在这里，删容器就没了
        ├──────────────────────────┤
        │  layer 3: COPY myapp /    │  ┐
镜像层   ├──────────────────────────┤  │ 只读 (lowerdir)
（只读） │  layer 2: RUN apk add ca… │  │ 可被多个容器共享
        ├──────────────────────────┤  │
        │  layer 1: alpine base     │  ┘
        └──────────────────────────┘
             ↓ OverlayFS 合并
        容器看到的 /  （merged）
```

Linux 上用 **OverlayFS**（`overlay2` 驱动）。看一个真实容器的挂载：

```bash
docker run -d --name overlay-demo alpine sleep 1000
docker inspect overlay-demo -f '{{json .GraphDriver.Data}}' | tr ',' '\n'
# "LowerDir":"/var/lib/docker/overlay2/xxx/diff:/var/lib/docker/overlay2/yyy/diff"
# "UpperDir":"/var/lib/docker/overlay2/zzz/diff"
# "MergedDir":"/var/lib/docker/overlay2/zzz/merged"
# "WorkDir":  "/var/lib/docker/overlay2/zzz/work"

sudo ls /var/lib/docker/overlay2/*/merged/    # 就是容器看到的根目录
mount | grep overlay
```

### 三个重要推论

**① 容器是"临时"的**
删掉容器，可写层就没了。所以**任何要持久化的数据都必须挂 volume**——这是第 11 章存储的根本原因。

**② copy-on-write 的性能陷阱**
修改一个只读层里的大文件，OverlayFS 要先把整个文件复制到可写层。所以：
- 数据库数据目录**必须**挂 volume，不能写在容器层（否则每次写都触发 CoW，性能灾难）
- 日志文件同理

**③ 层共享节省空间**
10 个基于 `alpine` 的镜像，`alpine` 那层在磁盘上只存一份。这也是为什么**统一基础镜像**能极大节省存储和拉取时间（第 3 章会讲）。

```bash
docker system df -v | head -20     # 看层的实际共享情况
```

---

## 5. 削减权限：capabilities / seccomp / user namespace

"容器里的 root"默认**不是**宿主机的完整 root——Docker 默认丢弃了大部分 capability。

```bash
# 默认容器里改不了系统时间（缺 CAP_SYS_TIME）
docker run --rm alpine date -s "2020-01-01"
# date: can't set date: Operation not permitted

# 加上就能改（不要在生产这么干）
docker run --rm --cap-add=SYS_TIME alpine date -s "2020-01-01"
```

| 机制 | 作用 | K8s 里的对应字段 |
|---|---|---|
| **capabilities** | 把 root 的权限拆成 40 多个细粒度能力 | `securityContext.capabilities.add/drop` |
| **seccomp** | 过滤系统调用（默认 profile 屏蔽了约 40 个危险 syscall） | `securityContext.seccompProfile` |
| **AppArmor / SELinux** | 强制访问控制 | `securityContext.appArmorProfile` / `seLinuxOptions` |
| **user namespace** | 容器内 UID 0 映射到宿主机的高位非特权 UID | Pod 的 `hostUsers: false`（**K8s 1.36 GA**） |
| **read-only rootfs** | 根文件系统只读 | `securityContext.readOnlyRootFilesystem: true` |

**user namespace 是近年最重要的安全改进**：即使容器逃逸，攻击者拿到的也只是宿主机上一个无权限的普通用户。K8s 1.36 起它已 GA，生产集群应该开启（第 14 章详解）。

**安全的边界在哪**：容器共享内核，所以内核漏洞 = 逃逸风险。需要强隔离（多租户、跑不可信代码）时，用 **gVisor**（用户态内核）或 **Kata Containers**（每个 Pod 一个轻量 VM）。

---

## 6. 手工造一个"容器"（不用 Docker）

这个实验是本章的高潮。在 `colima ssh` 进去的 Linux 里执行：

```bash
# 1. 准备一个根文件系统（直接从镜像里导出）
mkdir -p /tmp/myroot
docker export $(docker create alpine:latest) | tar -C /tmp/myroot -xf -
ls /tmp/myroot          # bin dev etc lib ... 一个完整的 Linux 用户态

# 2. 创建 cgroup 并设限（cgroup v2）
sudo mkdir -p /sys/fs/cgroup/mycontainer
echo "50M" | sudo tee /sys/fs/cgroup/mycontainer/memory.max
echo "20000 100000" | sudo tee /sys/fs/cgroup/mycontainer/cpu.max   # 0.2 核

# 3. 在新 namespace 里、切换根目录、加入 cgroup，跑 shell
sudo unshare --uts --pid --mount --ipc --net --fork --mount-proc \
  sh -c 'echo $$ > /sys/fs/cgroup/mycontainer/cgroup.procs;
         hostname my-container;
         exec chroot /tmp/myroot /bin/sh'
```

进去之后验证：

```sh
hostname          # my-container      ← UTS namespace
ps aux            # 只有自己           ← PID namespace
ls /              # alpine 的文件系统   ← chroot
ip a              # 只有 lo，没网       ← NET namespace（新建的网络 ns 是空的！）
cat /etc/os-release  # Alpine Linux
```

**你刚刚在没有 Docker 的情况下造了一个容器。**

注意最后一点：新建的 NET namespace 里**只有 lo，完全没有网络**。要让它上网，得手工创建 veth pair、配 IP、配路由、配 NAT——这正是 `docker run` 默认帮你做的事，也正是 K8s 里 **CNI 插件**的职责（第 10 章）。

清理：

```sh
exit
sudo rmdir /sys/fs/cgroup/mycontainer
sudo rm -rf /tmp/myroot
```

---

## 7. 生态：Docker / containerd / runc / CRI 到底谁是谁

这是新手最容易糊涂的地方。先看分层：

```
┌────────────────────────────────────────────────────────┐
│  用户/编排层                                             │
│  docker CLI      nerdctl        kubelet (Kubernetes)   │
└────────┬──────────────┬──────────────────┬─────────────┘
         │              │                  │ CRI (gRPC 接口)
         ▼              ▼                  ▼
┌────────────────────────────────────────────────────────┐
│  高层运行时（管镜像、管生命周期、管快照）                    │
│    dockerd  ──────►  containerd  ◄────  CRI-O           │
│                      （CNCF 毕业，事实标准）               │
└──────────────────────────┬─────────────────────────────┘
                           │ OCI Runtime Spec (JSON + 命令行)
                           ▼
┌────────────────────────────────────────────────────────┐
│  低层运行时（真正调用 clone/setns/cgroup 造容器）           │
│    runc  |  crun  |  gVisor(runsc)  |  Kata            │
└──────────────────────────┬─────────────────────────────┘
                           ▼
                      Linux 内核
```

| 组件 | 是什么 | 谁在用 |
|---|---|---|
| **runc** | OCI 参考实现，一个 Go 二进制。输入 rootfs + `config.json`，调 `clone()`/`setns()`/cgroup 造容器。**造完就退出**（真正守护容器的是 `containerd-shim`） | 所有人的底座 |
| **containerd** | 高层运行时：拉镜像、管快照、管容器生命周期、管网络插件调用 | Docker 底层用它；K8s 直接用它 |
| **dockerd** | 面向开发者的完整套件：镜像构建（BuildKit）、Compose、Swarm、卷管理、REST API | 开发者本地 |
| **CRI-O** | 专为 K8s 写的精简运行时，只实现 CRI 需要的功能 | Red Hat OpenShift |
| **CRI** | K8s 定义的 gRPC 接口（`RuntimeService` + `ImageService`），让 kubelet 与运行时解耦 | kubelet ↔ containerd |

### 那个著名的"Kubernetes 弃用 Docker"事件

2020 年 K8s 宣布弃用 dockershim，1.24（2022）正式移除，当时引发大范围恐慌。真相：

- kubelet 只会说 **CRI**。containerd 和 CRI-O 原生支持 CRI。
- 但 dockerd **不支持** CRI（它比 CRI 出现得早）。所以 K8s 曾内置一个适配器叫 **dockershim** 来翻译。
- 维护这个适配器的成本越来越高，而且路径很绕：`kubelet → dockershim → dockerd → containerd → runc`。
- 于是移除 dockershim，路径变成：`kubelet → containerd → runc`。

**对你的影响：零。**
- **Docker 构建的镜像照常能用**——因为镜像格式是 OCI 标准，跟运行时无关。
- 只是节点上不再需要装 Docker，`docker ps` 在 K8s 节点上看不到 Pod 了，改用 `crictl ps`。

```bash
# 在 kind 节点上（节点本身就是容器）
docker exec -it learn-worker crictl ps          # 看容器
docker exec -it learn-worker crictl images      # 看镜像
docker exec -it learn-worker crictl pods        # 看 Pod（sandbox）
```

### OCI 三个标准

| 标准 | 内容 |
|---|---|
| **Image Spec** | 镜像的格式：manifest、config、layer 的组织方式 |
| **Runtime Spec** | 怎么把 rootfs + config.json 变成运行中的容器 |
| **Distribution Spec** | 镜像仓库的 HTTP API（push/pull 协议） |

正因为有这三个标准，你才能用 Docker 构建、推到 Harbor、被 containerd 拉取、由 runc 运行——**全链路可替换**。

---

## 8. Pause 容器：Pod 的"骨架"

K8s 里每个 Pod 都有一个你在 YAML 里看不到的容器，叫 **pause**（或 sandbox）。

它的作用：**持有 namespace**。

```bash
docker exec learn-worker crictl pods         # 每个 Pod 有一个 sandbox
```

流程是：
1. kubelet 先起 pause 容器，它创建 NET/IPC/UTS namespace，然后 `pause()` 挂起（几乎不耗资源，源码就几十行 C）
2. CNI 插件给这个 namespace 配网卡和 IP
3. 你的业务容器**加入** pause 的 namespace（还记得 §2 的 `--network=container:a` 吗？）

**为什么要这样设计？** 因为业务容器可能重启。如果 IP 挂在业务容器上，重启就换 IP 了。挂在 pause 上，业务容器崩溃重启期间 Pod IP 保持不变。

这就解释了：
- 为什么 Pod 有一个 IP，而不是每个容器一个 IP
- 为什么 Pod 内容器能用 `localhost` 互访
- 为什么容器重启（`RESTARTS` 计数增加）不会改变 Pod IP，而 Pod 重建会

---

## 9. 本章检查清单

- [ ] 说出 namespace 和 cgroup 分别解决什么问题，各举 3 个例子
- [ ] 为什么 Pod 内的容器能用 `localhost` 互相访问，但看不到对方的文件？
- [ ] 退出码 137 意味着什么？怎么在宿主机上确认？
- [ ] 为什么数据库的数据目录一定要挂 volume？（从 OverlayFS 角度回答）
- [ ] Go 服务在有 CPU limit 的容器里，为什么可能出现延迟毛刺？怎么解决？
- [ ] `kubelet → ? → ? → 内核` 的调用链是什么？dockershim 移除影响了什么？
- [ ] pause 容器存在的意义是什么？
- [ ] 手工用 `unshare` + `chroot` 造一个容器（真的去敲一遍）

---

## 10. 延伸阅读

- [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec)
- [containerd 架构文档](https://github.com/containerd/containerd/blob/main/docs/)
- [Kubernetes: Don't Panic: Kubernetes and Docker](https://kubernetes.io/blog/2020/12/02/dont-panic-kubernetes-and-docker/)
- Liz Rice, *Container Security*（O'Reilly）——把本章内容展开成一本书，非常值得读
- 用 Go 手写容器：[containers-from-scratch](https://github.com/lizrice/containers-from-scratch)（Liz Rice 的 500 行 Go 实现，你有 Go 基础，读起来会很爽）

---

下一章：[03 - 镜像与 Dockerfile：把 Go 服务打成 10MB](./03-images.md)
