# 从服务器开发到 Kubernetes 运维：系统性学习课程

> 面向对象：有 Go 服务端开发经验、熟悉基本 Linux 操作、**没有**运维/部署背景的工程师。
> 学完之后你应该能够：独立把一个 Go 服务打包成镜像、设计出它的 K8s 部署清单、用 Helm 参数化、
> 用 Jenkins + Argo CD 建立自动化交付流水线、并在生产环境中持续运维（升级、扩容、排障、迁移）。

本课程编写于 **2026 年 7 月**，基线版本：

| 组件 | 版本基线 | 说明 |
|---|---|---|
| Kubernetes | **1.36**（"Haru"，2026-04 发布） | 官方同时维护 1.34 / 1.35 / 1.36 三个小版本，每个约 1 年支持期，每年 3 个小版本 |
| containerd | 2.x | CRI 运行时事实标准 |
| Helm | **4.2.x**（v4.0 于 2025-11 发布） | Helm 3 只剩安全补丁，2027-02 彻底停 |
| Argo CD | **3.4.x** | 3.5 在 RC |
| Argo Rollouts | 1.9.x | 渐进式交付 |
| Jenkins | **2.555.x LTS** | 需要 Java 21+ |
| Gateway API | **1.6.0** | Ingress 的继任者；`ingress-nginx` 已于 **2026-03-24 退役**，见第 10 章 |

---

## 0. 先说结论：这些软件到底怎么协作

这是你的第一个关键问题，先给一张全景图，后面每一章都是在把这张图的某个方框拆开讲。

```
   你（Go 开发者）
        │  git push
        ▼
 ┌──────────────┐
 │  Git 仓库     │  ① 应用代码仓（Go 源码 + Dockerfile）
 │  (代码 / 配置)│  ② 配置仓（Helm Chart / Kustomize，声明"集群该长什么样"）
 └──────┬───────┘
        │ webhook 触发
        ▼
 ┌──────────────┐   docker build / buildkit
 │   Jenkins    │──────────────────────────────►┌───────────────┐
 │    (CI)      │   构建、测试、打镜像、推镜像      │ 镜像仓库       │
 │              │                               │ (Harbor/ECR..) │
 └──────┬───────┘                               └───────┬───────┘
        │ 只做一件事：把新镜像 tag 写回"配置仓"                │
        ▼                                                │
 ┌──────────────┐                                        │
 │  配置仓更新   │  image.tag: v1.4.2                      │
 └──────┬───────┘                                        │
        │ Argo CD 持续 watch 这个仓库                       │
        ▼                                                │
 ┌──────────────┐   helm template 渲染成 YAML             │
 │   Argo CD    │   然后 apply 到集群                      │
 │    (CD)      │───────────────┐                        │
 └──────────────┘               │                        │
                                ▼                        │
                    ┌────────────────────────┐           │
                    │   Kubernetes 集群       │           │
                    │  ┌──────────────────┐  │           │
                    │  │ API Server(声明)  │  │           │
                    │  └────────┬─────────┘  │           │
                    │           ▼            │           │
                    │  ┌──────────────────┐  │  kubelet  │
                    │  │ Controller 调谐   │  │  拉镜像 ◄─┘
                    │  └────────┬─────────┘  │
                    │           ▼            │
                    │   Node1  Node2  Node3  │
                    │   [Pod]  [Pod]  [Pod]  │
                    └────────────────────────┘
```

一句话版本的分工：

| 组件 | 一句话职责 | 类比（Go 开发者视角） |
|---|---|---|
| **容器 / 镜像** | 把"进程 + 它的整个文件系统依赖"打成一个可分发的不可变包 | `go build` 产出的静态二进制，但连 `/etc`、CA 证书、时区库一起打包 |
| **Kubernetes** | 一个"集群级操作系统"：你声明期望状态，它负责让现实收敛过去 | 一个巨大的 `for { reconcile(desired, actual) }` 循环 |
| **Helm** | K8s YAML 的包管理器 + 模板引擎，解决"同一套服务部署到多环境" | `text/template` + `go.mod`（版本化依赖） |
| **Kustomize** | 无模板的 YAML 叠加（base + overlay） | 结构体嵌入 + 字段覆盖 |
| **Jenkins（CI）** | 代码变更 → 编译/测试/打镜像/推仓库，产出**不可变构件** | `make test && make docker-push` 的托管执行器 |
| **Argo CD（CD）** | 持续把 Git 里的"期望状态"同步到集群，并检测漂移 | 一个以 Git 为唯一真相源的 reconcile 循环 |
| **Argo Rollouts** | 把"一次性替换"变成"按比例灰度 + 指标校验 + 自动回滚" | 带熔断的渐进式发布状态机 |

**为什么 CI 和 CD 要分开？**（这是新手最容易困惑的点）

- CI（Jenkins）在**集群外**，它需要 Docker、编译器、测试依赖，是"推"模型：拿着 kubeconfig 往集群里推。
- CD（Argo CD）在**集群内**，是"拉"模型：集群自己去 Git 拉期望状态。
- 分开的好处：① CI 系统不需要生产集群的写权限（凭据泄露风险大幅降低）；② 集群的真实状态永远等于 Git 里能看到的内容，任何手工 `kubectl edit` 都会被标记为 drift（漂移）并可自动回滚；③ 回滚 = `git revert`，不需要理解 Helm release 历史。

---

## 1. 课程结构（四个阶段，26 篇）

学习顺序是**严格递进**的，每一章的"为什么"都建立在前一章的"痛点"之上。不要跳着看第 6 章之前的内容。

### 阶段一：容器 —— 一切的地基（第 1~5 章）

不理解容器就学 K8s，等于不懂 TCP 就学 HTTP 框架。这一阶段的目标是让你能回答："容器到底是什么？为什么它不是虚拟机？"

| 章节 | 内容 | 解答你的哪个问题 |
|---|---|---|
| [01 - 部署的演进史](./01-evolution.md) | 从物理机 → 虚拟机 → 容器 → 编排，每一步解决了什么痛点 | 问题背景 |
| [02 - 容器的本质](./02-container-internals.md) | namespace / cgroup / OverlayFS / OCI 标准；Docker、containerd、runc 的关系；为什么 K8s 删掉了 dockershim | 工作原理 |
| [03 - 镜像与 Dockerfile](./03-images.md) | 分层机制、多阶段构建 Go 应用、镜像瘦身到 10MB、多架构、镜像仓库、tag vs digest | **"如何配置镜像"** |
| [04 - 容器运行时配置](./04-runtime-config.md) | 端口映射与 host 网络、环境变量、卷挂载与配置文件、日志、资源限制、信号与优雅退出 | **"访问宿主机网络/环境变量/配置/日志"** |
| [05 - 从单机到集群](./05-compose-to-orchestration.md) | Docker Compose 实战，然后**亲手撞上**它的天花板，理解为什么需要编排系统 | 演进过程 |

### 阶段二：Kubernetes 核心 —— 编排系统的原理与用法（第 6~14 章）

| 章节 | 内容 | 解答你的哪个问题 |
|---|---|---|
| [06 - 架构与设计哲学](./06-k8s-architecture.md) | 控制面/数据面组件、声明式 API、控制器模式、list-watch/informer（配 Go 伪代码）、etcd | 设计原理 |
| [07 - Pod 详解](./07-pod.md) | 为什么最小单位是 Pod 不是容器、生命周期、探针、initContainer、原生 sidecar、资源与 QoS | **"如何配置一个 Pod、有哪些参数"** |
| [08 - 配置与密钥](./08-config-secret.md) | ConfigMap/Secret 的 4 种消费方式、热更新的真相、Downward API、外部密钥管理 | **"环境变量/配置文件"** |
| [09 - 工作负载控制器](./09-workloads.md) | Deployment / StatefulSet / DaemonSet / Job / CronJob；**有状态 vs 无状态的本质差异**；滚动更新全部参数、回滚、暂停、PDB | **"部署成集群、状态化服务差异、滚动更新"** |
| [10 - Service 与网络](./10-networking.md) | Pod 网络模型、CNI、Service 四种类型、kube-proxy 的 iptables/IPVS/nftables 实现、CoreDNS、Ingress、**Gateway API**、NetworkPolicy | **"如何访问网络"** 的集群版 |
| [11 - 存储](./11-storage.md) | Volume 类型、PV/PVC/StorageClass/CSI、访问模式、动态供给、StatefulSet 的 volumeClaimTemplates、数据迁移 | **"文件系统"** 的集群版 |
| [12 - 调度、资源与弹性](./12-scheduling-scaling.md) | 调度器工作流程、亲和性/污点/拓扑分布、优先级与抢占、HPA/VPA/Cluster Autoscaler、原地扩缩容、`drain` **节点迁移** | **"迁移"** |
| [13 - 可观测性](./13-observability.md) | 日志采集链路、Prometheus 指标体系（含 Go 应用埋点）、事件、`kubectl debug` 临时容器、分布式追踪 | **"日志"** 的集群版 |
| [14 - 安全与多租户](./14-security.md) | RBAC、ServiceAccount 与投影令牌、Pod Security Admission、ResourceQuota、镜像供应链安全 | 大规模管理的前提 |

### 阶段三：交付流水线 —— 让部署自动化（第 15~19 章）

| 章节 | 内容 |
|---|---|
| [15 - Helm](./15-helm.md) | 为什么需要模板化、Chart 结构、values 优先级、模板函数、依赖、release 与 revision、Helm 4 新特性、生产实践与陷阱 |
| [16 - Kustomize 与配置管理选型](./16-kustomize.md) | base/overlay 模型、与 Helm 的对比与组合、如何选 |
| [17 - Jenkins 与 CI](./17-jenkins-ci.md) | CI 的本质、Jenkins 架构、Pipeline as Code、在 K8s 上跑动态 agent、构建 Go 镜像并推仓库、凭据管理、与 GitHub Actions/GitLab CI 的对比 |
| [18 - Argo CD 与 GitOps](./18-argocd-gitops.md) | GitOps 四原则、Argo CD 架构与内部工作方式、Application/ApplicationSet、同步策略、漂移处理、多环境多集群、镜像更新回路 |
| [19 - 渐进式交付](./19-progressive-delivery.md) | 蓝绿/金丝雀/影子流量的原理、Argo Rollouts 的 Rollout CRD、基于 Prometheus 指标的自动分析与回滚 |

### 阶段四：运维实战 —— 从"能跑"到"能扛"（第 20~23 章 + 附录）

| 章节 | 内容 |
|---|---|
| [20 - 端到端实战](./20-end-to-end-lab.md) | 一个真实 Go 微服务（HTTP + gRPC + Postgres + Redis）走完：代码 → CI → 镜像 → Chart → Argo CD → 多环境 → 监控 → 灰度 → 回滚 |
| [21 - 大规模集群管理](./21-large-scale-ops.md) | **"如何管理大规模集群"**：单集群规模上限与瓶颈、多集群拓扑、节点池、集群版本升级、容量与成本、平台工程、备份与灾难恢复 |
| [22 - 故障排查手册](./22-troubleshooting.md) | 按"现象 → 排查路径 → 根因 → 修复"组织：CrashLoopBackOff、ImagePullBackOff、Pending、OOMKilled、DNS 故障、502、节点 NotReady、证书过期…… |
| [23 - Day-2 运维](./23-day2-operations.md) | 值班 SOP、变更管理、SLO 与告警设计、升级演练、混沌与容量测试、on-call 手册模板 |
| [附录 A - 速查表](./A-cheatsheet.md) | kubectl / helm / argocd / docker 命令速查 + YAML 骨架速查 |
| [附录 B - 术语表与延伸阅读](./B-glossary.md) | 中英对照术语表、官方文档地图、认证考试（CKA/CKAD/CKS）对照 |

---

## 2. 你的四个关键问题 → 章节索引

| 你的问题 | 主要章节 | 补充章节 |
|---|---|---|
| 这些软件的工作方式，之间如何协作 | 本页第 0 节、[06](./06-k8s-architecture.md)、[17](./17-jenkins-ci.md)、[18](./18-argocd-gitops.md) | [20](./20-end-to-end-lab.md) 完整串一遍 |
| 如何配置镜像（docker/container） | [02](./02-container-internals.md)、[03](./03-images.md) | [14](./14-security.md) 镜像安全 |
| 镜像如何访问宿主机网络（映射） | [04 §1](./04-runtime-config.md)（单机） | [10](./10-networking.md)（集群里的等价物：hostNetwork/hostPort/NodePort） |
| 如何访问环境变量、配置（文件系统）、日志 | [04 §2~§4](./04-runtime-config.md)（单机） | [08](./08-config-secret.md)、[11](./11-storage.md)、[13](./13-observability.md)（集群） |
| 如何配置一个 Pod、有哪些参数 | [07](./07-pod.md) | [附录 A](./A-cheatsheet.md) 字段速查 |
| 如何把它们部署成集群 | [09](./09-workloads.md)、[10](./10-networking.md) | [00](./00-setup.md) 本地起多节点集群 |
| 状态化 vs 无状态服务的差异 | [09 §3](./09-workloads.md) | [11](./11-storage.md) 存储、[21](./21-large-scale-ops.md) 有状态服务的运维代价 |
| 如何滚动更新、迁移 | [09 §4](./09-workloads.md)、[12 §6](./12-scheduling-scaling.md) | [19](./19-progressive-delivery.md) 灰度 |
| 如何管理大规模集群 | [21](./21-large-scale-ops.md) | [14](./14-security.md)、[23](./23-day2-operations.md) |

---

## 3. 怎么学（很重要，请认真读）

**这门课不是读物，是实验手册。** 每一章都有 `动手实验` 小节，必须敲。K8s 的知识 90% 是"手感"，看懂和会用之间隔着一整个 `kubectl describe`。

建议节奏（按每天投入 1.5~2 小时估算）：

| 阶段 | 章节 | 预计用时 | 阶段验收标准 |
|---|---|---|---|
| 一 | 01~05 | 约 1 周 | 能手写一个 20MB 以内的 Go 服务镜像，能解释 `docker run -p` 到底做了什么 |
| 二 | 06~14 | 约 3 周 | 能不查文档写出一个带探针、资源限制、ConfigMap、PVC 的 Deployment+Service，并解释每个字段 |
| 三 | 15~19 | 约 2 周 | 能把上面的清单改造成 Chart，用 Argo CD 部署到两套环境 |
| 四 | 20~23 | 约 2 周 | 能独立完成一次生产级发布 + 一次回滚 + 一次节点维护 |

**几条学习原则：**

1. **先问"没有它会怎样"**。每引入一个概念，先想清楚它替代了什么手工操作。K8s 的所有对象都是某个运维痛点的固化。
2. **善用 `kubectl explain`**。它是活的字段文档，比任何速查表都准：
   ```bash
   kubectl explain deployment.spec.strategy.rollingUpdate --recursive
   ```
3. **一切都是 API 对象**。当你困惑"这东西怎么配"时，答案永远是 `kubectl get <资源> -o yaml` 看真实结构。
4. **失败是课程的一部分**。第 22 章的每个故障，建议你在本地**主动制造**一遍。
5. **不要背 YAML**。你要理解的是字段背后的控制器行为。

**Go 开发者的特殊优势**：K8s 本身是 Go 写的，所有控制器都是可读的 Go 代码。当文档说不清某个行为时，去读源码往往是最快的路径。第 6 章会教你怎么定位。

---

## 4. 前置知识自检

开始前，确认你能回答（不能也没关系，对应章节会补）：

- [ ] `fork` / `exec` / 进程组 / 信号（SIGTERM vs SIGKILL）—— 第 2、4 章会用
- [ ] 文件描述符、stdout/stderr —— 第 4 章日志的基础
- [ ] TCP 端口、NAT、iptables 的存在（不需要精通）—— 第 4、10 章
- [ ] Linux 挂载点、`/proc` —— 第 2、11 章
- [ ] Git 分支与 PR 流程 —— 第 17、18 章
- [ ] YAML 语法（缩进、列表、锚点）—— 全程

---

## 5. 开始

先做 [00 - 环境准备](./00-setup.md)，把本地实验环境搭起来（macOS Apple Silicon 有专门说明），然后从 [01 - 部署的演进史](./01-evolution.md) 开始。
