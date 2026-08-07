# 03 - 镜像与 Dockerfile：把 Go 服务打成 10MB

> 本章目标：彻底搞懂"如何配置镜像"。你会写出一个生产级的 Go 服务 Dockerfile，理解每一行的代价，
> 并掌握多架构构建、镜像仓库、tag 策略、安全扫描。
> 预计用时：2.5 小时（含实验）。

---

## 1. 镜像到底是什么

**镜像不是一个文件**，它是一组内容寻址的对象：

```
镜像 (myapp:v1.2.3)
 │
 ├── manifest（清单）        ← 一个 JSON，列出下面所有部分的 digest
 │     ├── config digest
 │     └── layers[] digest
 │
 ├── config（配置）          ← 一个 JSON：ENTRYPOINT、CMD、ENV、WORKDIR、USER、
 │                             暴露端口、labels、架构、以及各层的 diff_id
 │
 └── layers[]（层）           ← 每层是一个 tar.gz，内容是"相对上一层的文件系统差异"
       ├── sha256:aaa...  (base 系统文件)
       ├── sha256:bbb...  (RUN apk add 产生的变化)
       └── sha256:ccc...  (你的二进制)
```

亲手看一下：

```bash
docker pull nginx:alpine
docker manifest inspect nginx:alpine | head -40   # 多架构 index
docker image inspect nginx:alpine | jq '.[0].Config'     # config：ENTRYPOINT/CMD/ENV
docker image inspect nginx:alpine | jq '.[0].RootFS.Layers'   # 层列表
docker history nginx:alpine       # 每层是哪条指令产生的、多大
```

### 内容寻址：tag vs digest

```bash
docker inspect nginx:alpine -f '{{index .RepoDigests 0}}'
# nginx@sha256:abc123...
```

| | tag（`nginx:alpine`） | digest（`nginx@sha256:abc...`） |
|---|---|---|
| 可变性 | **可变**——同一个 tag 明天可能指向不同镜像 | **不可变**——内容哈希，永远是同一份 |
| 用途 | 人类可读 | 机器精确引用 |

**生产环境的铁律**：
- ❌ 永远不要用 `latest`（你无法知道现在跑的是哪个版本，也无法回滚）
- ✅ 用不可变 tag：`v1.2.3`、`git-a3f9c21`、`2026-07-29-a3f9c21`
- ✅✅ 关键系统直接用 digest 部署（Argo CD Image Updater 支持，第 18 章）

**为什么 `latest` 是灾难**：节点 A 在周一拉了 `latest`（是 v1），节点 B 在周三拉了 `latest`（是 v2）。同一个 Deployment 的副本跑着不同代码，而 `kubectl describe` 里看到的镜像名一模一样。这种故障能排查一整天。

---

## 2. Dockerfile 指令：每一行都是一层

先看一个**反面教材**：

```dockerfile
# ❌ 不要这样写
FROM golang:1.26
WORKDIR /app
COPY . .
RUN go build -o server ./cmd/server
EXPOSE 8080
CMD ["./server"]
```

问题：
1. 镜像 **1.2 GB**（整个 Go 工具链、源码、模块缓存都在里面）
2. 攻击面巨大（有编译器、有 shell、有 git、有 curl）
3. 源码泄漏在镜像里
4. 每次改一行代码，`COPY . .` 缓存失效，所有依赖重新下载

### 指令速查

| 指令 | 作用 | 是否产生新层 | 注意 |
|---|---|---|---|
| `FROM` | 基础镜像 | - | 多阶段构建可以有多个 |
| `RUN` | 构建时执行命令 | ✅ 产生层 | 用 `&&` 合并，减少层数 |
| `COPY` | 复制文件（推荐） | ✅ | 支持 `--from=stage`、`--chown` |
| `ADD` | 复制 + 自动解压 + 支持 URL | ✅ | **少用**，行为不可预测；只在解压 tar 时用 |
| `WORKDIR` | 设置工作目录 | 元数据 | 不存在会自动创建；别用 `RUN cd` |
| `ENV` | 环境变量（**构建时和运行时都生效**） | 元数据 | 会被 `docker run -e` 覆盖 |
| `ARG` | 仅构建时变量 | 元数据 | `docker build --build-arg`；**不要传密钥**（会留在历史里） |
| `EXPOSE` | 声明端口（**纯文档，不做任何事**） | 元数据 | 真正的映射靠 `-p` |
| `CMD` | 默认命令/默认参数 | 元数据 | 会被 `docker run <cmd>` 覆盖 |
| `ENTRYPOINT` | 入口可执行文件 | 元数据 | 与 CMD 配合，见下 |
| `USER` | 以哪个用户运行 | 元数据 | **生产必须设为非 root** |
| `VOLUME` | 声明匿名卷挂载点 | 元数据 | K8s 里基本无用，甚至有害，建议不写 |
| `HEALTHCHECK` | 健康检查 | 元数据 | **K8s 会忽略它**，用 K8s 的探针（第 7 章） |
| `LABEL` | 元数据标签 | 元数据 | 用 OCI 标准标签记录版本、来源 |

### ENTRYPOINT vs CMD（高频困惑点）

| 写法 | `docker run img` 执行 | `docker run img foo` 执行 |
|---|---|---|
| `CMD ["a","b"]` | `a b` | `foo` |
| `ENTRYPOINT ["a"]` | `a` | `a foo` |
| `ENTRYPOINT ["a"]` + `CMD ["b"]` | `a b` | `a foo` |

**推荐**：`ENTRYPOINT` 写程序，`CMD` 写默认参数。

```dockerfile
ENTRYPOINT ["/server"]
CMD ["--config=/etc/app/config.yaml"]
```

### exec 形式 vs shell 形式（这个坑很致命）

```dockerfile
CMD ./server              # shell 形式 → 实际执行 /bin/sh -c "./server"
CMD ["./server"]          # exec 形式  → 直接 execve("./server")
```

**shell 形式的问题**：PID 1 是 `sh`，你的程序是它的子进程。`docker stop` / K8s 发的 **SIGTERM 会发给 `sh`，而 `sh` 不会转发给子进程**。结果：你的优雅退出代码永远不执行，10 秒后被 SIGKILL 强杀，正在处理的请求全部断开。

**永远用 exec 形式（JSON 数组）**。第 4 章会详细讲信号处理。

### K8s 里的对应关系（重要）

| Dockerfile | K8s Pod spec |
|---|---|
| `ENTRYPOINT` | `command` |
| `CMD` | `args` |

注意这个映射很反直觉：K8s 的 `command` 覆盖的是 `ENTRYPOINT`，不是 `CMD`。**只写 `args` 而不写 `command`，会用镜像的 ENTRYPOINT + 你的 args。**

---

## 3. 构建缓存：为什么你的 CI 这么慢

Docker 逐条执行指令，每条指令产生一层并缓存。缓存命中的判据：

- `RUN`：**指令字符串**完全一致（不看命令实际会不会产生不同结果！所以 `RUN apt-get update` 会拿到很旧的缓存）
- `COPY` / `ADD`：文件**内容哈希**一致

**一旦某层缓存失效，后面所有层全部失效。**

所以黄金法则：**按"变化频率从低到高"排列指令**。

```dockerfile
# ✅ 依赖变化少，放前面
COPY go.mod go.sum ./
RUN go mod download          # 只要 go.mod/go.sum 没变，这层就命中缓存

# ✅ 源码变化频繁，放后面
COPY . .
RUN go build -o /server ./cmd/server
```

改一行业务代码时，`go mod download` 直接命中缓存——CI 从 3 分钟变成 20 秒。

### .dockerignore（必写）

`COPY . .` 会把整个目录（包括 `.git`、`node_modules`、本地二进制）塞进构建上下文，既慢又会莫名破坏缓存。

```gitignore
# .dockerignore
.git
.gitignore
*.md
Dockerfile*
.dockerignore
bin/
dist/
vendor/          # 如果不用 vendor 模式
**/*_test.go     # 视情况
.env
*.log
.idea/
.vscode/
```

### BuildKit 的缓存挂载（大幅加速）

现代 Docker 默认用 BuildKit。它支持**跨构建持久化的缓存目录**：

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build -o /server ./cmd/server
```

这样 Go 的模块缓存和编译缓存在多次构建间复用，增量编译从 60 秒降到 5 秒。

**注意**：缓存挂载在 CI 上需要 runner 有持久化存储，或者用 `--cache-from`/`--cache-to` 推到远程（第 17 章讲 CI 时会配）。

### 构建时的密钥（不要用 ARG）

```dockerfile
# ❌ 密钥会永久留在镜像历史里，docker history 就能看到
ARG GITHUB_TOKEN
RUN git clone https://$GITHUB_TOKEN@github.com/private/repo

# ✅ BuildKit secret：只在这条 RUN 期间存在，不进任何层
RUN --mount=type=secret,id=gh_token \
    GITHUB_TOKEN=$(cat /run/secrets/gh_token) go mod download
```

```bash
docker build --secret id=gh_token,env=GITHUB_TOKEN -t myapp .
```

私有 Go 模块的完整写法：

```dockerfile
ENV GOPRIVATE=github.com/yourorg/*
RUN --mount=type=secret,id=netrc,target=/root/.netrc,mode=0600 \
    --mount=type=cache,target=/go/pkg/mod \
    go mod download
```

---

## 4. 基础镜像怎么选

| 基础镜像 | 大小 | 有 shell | libc | 适用 |
|---|---|---|---|---|
| `scratch` | **0 B** | ❌ | 无 | 纯静态 Go 二进制（`CGO_ENABLED=0`） |
| `gcr.io/distroless/static-debian12` | ~2 MB | ❌ | 无 | **静态 Go 的最佳选择**（自带 CA 证书、tzdata、nonroot 用户） |
| `gcr.io/distroless/base-debian12` | ~20 MB | ❌ | glibc | 需要 CGO 的 Go |
| `alpine:3.22` | ~8 MB | ✅ sh | **musl** | 需要调试；⚠️ CGO 下有 musl 兼容坑 |
| `debian:12-slim` | ~75 MB | ✅ bash | glibc | 需要系统包 |
| `ubuntu:24.04` | ~78 MB | ✅ bash | glibc | 团队熟悉度优先 |

### 用 `scratch` 必须自己解决的三件事

纯静态 Go 二进制放进 `scratch` 后，会遇到：

**① HTTPS 请求失败：`x509: certificate signed by unknown authority`**
因为没有 CA 根证书。解决：从构建阶段复制 `/etc/ssl/certs/ca-certificates.crt`。

**② 时区永远是 UTC：`time.LoadLocation("Asia/Shanghai")` 报错**
因为没有 tzdata。解决：复制 `/usr/share/zoneinfo`，或在 Go 代码里 `import _ "time/tzdata"`（Go 1.15+，把时区库编进二进制，约 +450KB，**推荐**）。

**③ 用户名解析失败 / 只能以 root 跑**
因为没有 `/etc/passwd`。解决：构建阶段生成一个，或直接用 `USER 65532:65532` 数字 UID。

**distroless 帮你把这三件事都解决了**，所以推荐用 distroless 而不是 scratch。

### Alpine 的 musl 坑

Alpine 用 musl libc 而非 glibc。如果你的 Go 程序用了 CGO（`go-sqlite3`、`confluent-kafka-go`、部分图像库），在 Alpine 上会遇到：

- 编译需要 `apk add gcc musl-dev`
- 在 glibc 机器上编译的 CGO 二进制**放进 Alpine 跑不了**
- 已知 musl 的 DNS 解析行为与 glibc 不同（不支持 `search` 域的某些用法、并发查询行为差异），在 K8s 里可能导致**间歇性 DNS 解析失败**——这是个经典生产事故
- musl 的 malloc 在高并发下性能不如 glibc

**建议**：`CGO_ENABLED=0` → distroless static；必须 CGO → debian-slim 或 distroless base。

---

## 5. 生产级 Go Dockerfile（逐行讲解）

先准备一个示例应用。创建 `~/lab/hello/`：

```bash
mkdir -p ~/lab/hello/cmd/server && cd ~/lab/hello
go mod init example.com/hello
```

`cmd/server/main.go`：

```go
package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"

	_ "time/tzdata" // 把时区数据编进二进制，scratch/distroless 下也能用 LoadLocation
)

var (
	version = "dev"  // 通过 -ldflags 注入
	commit  = "none"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ok"))
	})
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ready"))
	})
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		host, _ := os.Hostname()
		json.NewEncoder(w).Encode(map[string]any{
			"message":    getenv("GREETING", "hello"),
			"version":    version,
			"commit":     commit,
			"hostname":   host, // 在 K8s 里就是 Pod 名，用来观察负载均衡
			"gomaxprocs": runtime.GOMAXPROCS(0),
			"time":       time.Now().Format(time.RFC3339),
		})
	})

	srv := &http.Server{
		Addr:              ":" + getenv("PORT", "8080"),
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	// 优雅退出：收到 SIGTERM 后停止接收新连接，等待存量请求处理完
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()

	go func() {
		slog.Info("server starting", "addr", srv.Addr, "version", version)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("listen failed", "err", err)
			os.Exit(1)
		}
	}()

	<-ctx.Done()
	slog.Info("shutdown signal received, draining...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		slog.Error("graceful shutdown failed", "err", err)
	}
	slog.Info("bye")
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
```

```bash
go mod tidy
go run ./cmd/server &   # 本地先跑通
curl localhost:8080; kill %1
```

### Dockerfile

```dockerfile
# syntax=docker/dockerfile:1

########################  阶段 1：构建  ########################
FROM golang:1.26-alpine AS builder

# 交叉编译需要的目标平台变量，由 buildx 自动注入
ARG TARGETOS
ARG TARGETARCH
ARG VERSION=dev
ARG COMMIT=none

WORKDIR /src

# ① 先只拷依赖描述文件 —— 这一层的缓存能命中 95% 的构建
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# ② 再拷源码
COPY . .

# ③ 编译
#    CGO_ENABLED=0  → 纯静态，可放 scratch/distroless-static
#    -trimpath      → 去掉本地路径，构建可复现
#    -ldflags="-s -w" → 去符号表和调试信息，二进制小 30%
#    -X             → 注入版本号
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -trimpath \
      -ldflags="-s -w -X main.version=${VERSION} -X main.commit=${COMMIT}" \
      -o /out/server ./cmd/server

########################  阶段 2：运行  ########################
FROM gcr.io/distroless/static-debian12:nonroot

# OCI 标准标签：让镜像自描述来源，供应链工具会读
LABEL org.opencontainers.image.source="https://github.com/yourorg/hello" \
      org.opencontainers.image.description="Hello service" \
      org.opencontainers.image.licenses="MIT"

COPY --from=builder /out/server /server

# distroless:nonroot 已经内置 UID 65532 的 nonroot 用户
USER 65532:65532

EXPOSE 8080
ENTRYPOINT ["/server"]
```

构建并查看：

```bash
docker build \
  --build-arg VERSION=v0.1.0 \
  --build-arg COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo dev) \
  -t hello:v0.1.0 .

docker images hello:v0.1.0
# REPOSITORY  TAG      SIZE
# hello       v0.1.0   ~9MB      ← 对比最开始的 1.2GB

docker run --rm -p 8080:8080 hello:v0.1.0 &
curl -s localhost:8080 | jq
docker rm -f $(docker ps -lq)
```

### 无 shell 镜像怎么调试？

distroless 没有 shell，`docker exec -it xxx sh` 会失败。三种办法：

```bash
# ① debug 变体（带 busybox shell），仅用于排查
FROM gcr.io/distroless/static-debian12:debug-nonroot

# ② 用另一个容器加入它的 namespace（生产推荐）
docker run --rm -it --pid=container:<id> --network=container:<id> \
  --cap-add SYS_PTRACE nicolaka/netshoot

# ③ K8s 里用临时容器（第 13 章详解）
kubectl debug -it <pod> --image=nicolaka/netshoot --target=<container>
```

---

## 6. 多架构镜像（Apple Silicon 必修）

你的 Mac 是 arm64，生产服务器多半是 amd64。构建时不注意，部署到线上就是：

```
exec /server: exec format error
```

### 原理：manifest list（OCI image index）

一个 tag 可以指向一个"索引"，索引里按平台列出多个真实镜像：

```
myapp:v1  →  index
                ├── linux/amd64  → manifest A → layers...
                └── linux/arm64  → manifest B → layers...
```

客户端拉取时，runtime 自动挑选匹配本机架构的那个。

### 用 buildx 构建

```bash
# 创建一个支持多平台的 builder（一次性）
docker buildx create --name multi --driver docker-container --use --bootstrap
docker buildx ls

# 构建并推送多架构镜像（多架构必须 --push，本地 docker images 存不了 index）
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg VERSION=v0.1.0 \
  -t localhost:5001/hello:v0.1.0 \
  --push .

# 验证
docker buildx imagetools inspect localhost:5001/hello:v0.1.0
```

**为什么 Go 特别适合多架构**：因为交叉编译是原生能力。上面的 Dockerfile 用 `GOARCH=${TARGETARCH}`，builder 阶段始终在**本机架构**上跑（快），只是产出目标架构的二进制。

对比其他语言（需要 QEMU 模拟目标架构跑整个构建，慢 5~10 倍）：

```dockerfile
# ❌ 慢：整个构建都在 QEMU 模拟下跑
FROM --platform=$TARGETPLATFORM golang:1.26 AS builder

# ✅ 快：构建在本机跑，交叉编译出目标架构
FROM --platform=$BUILDPLATFORM golang:1.26 AS builder
RUN GOARCH=$TARGETARCH go build ...
```

| 变量 | 含义 |
|---|---|
| `BUILDPLATFORM` | 执行构建的机器架构（你的 Mac = linux/arm64） |
| `TARGETPLATFORM` | 目标平台（如 linux/amd64） |
| `TARGETOS` / `TARGETARCH` / `TARGETVARIANT` | 拆解后的分量 |

---

## 7. 镜像仓库（Registry）

### 仓库地址的解析规则

```
nginx                        → docker.io/library/nginx:latest
myorg/myapp:v1               → docker.io/myorg/myapp:v1
ghcr.io/myorg/myapp:v1       → GitHub Container Registry
registry.example.com:5000/team/app:v1  → 私有仓库
localhost:5001/hello:v0.1.0  → 本地仓库
```

**规则**：第一段包含 `.` 或 `:` 或等于 `localhost` 时才被当作仓库地址，否则默认 Docker Hub。

### 常见选择

| 仓库 | 说明 |
|---|---|
| Docker Hub | 公共，有**匿名拉取限流**（这是生产事故常见原因，见第 22 章） |
| **Harbor** | CNCF 毕业的自建仓库：RBAC、镜像扫描、复制、配额、代理缓存。**企业自建首选** |
| GHCR / GitLab Registry | 与代码仓库集成，CI 友好 |
| AWS ECR / 阿里云 ACR / GCP AR | 云厂商托管，与 IAM 集成 |

### 推送与认证

```bash
docker login ghcr.io -u <user>              # 凭据存到 ~/.docker/config.json
docker tag hello:v0.1.0 ghcr.io/yourorg/hello:v0.1.0
docker push ghcr.io/yourorg/hello:v0.1.0
```

**K8s 拉私有镜像**需要 imagePullSecret（第 8 章详细讲）：

```bash
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io \
  --docker-username=<user> \
  --docker-password=<token>
```

```yaml
spec:
  imagePullSecrets:
    - name: regcred
```

### imagePullPolicy（高频困惑）

| 值 | 行为 | 默认何时生效 |
|---|---|---|
| `Always` | 每次启动都去仓库查 digest | tag 是 `latest` 或未写 tag 时的默认 |
| `IfNotPresent` | 本地有就不拉 | 指定了具体 tag 时的默认 |
| `Never` | 只用本地，没有就失败 | 需显式指定 |

**坑**：你用 `kind load` 把镜像塞进节点，但 tag 写成 `latest`，K8s 默认 `Always`，去 Docker Hub 拉 → `ImagePullBackOff`。解决：用具体 tag，或显式 `imagePullPolicy: IfNotPresent`。

---

## 8. 镜像安全与供应链

生产环境的镜像必须过这几关（第 14 章展开，这里先建立意识）：

```bash
# ① 漏洞扫描
brew install trivy
trivy image hello:v0.1.0
trivy image --severity HIGH,CRITICAL --exit-code 1 hello:v0.1.0   # CI 里当门禁

# ② SBOM（软件物料清单）：记录镜像里所有组件，出 CVE 时能快速定位影响面
docker buildx build --sbom=true --provenance=true -t myapp:v1 --push .
trivy image --format cyclonedx -o sbom.json hello:v0.1.0

# ③ 签名（确保部署的镜像确实来自你的 CI）
brew install cosign
cosign sign --key cosign.key ghcr.io/yourorg/hello:v0.1.0
cosign verify --key cosign.pub ghcr.io/yourorg/hello:v0.1.0
```

集群侧可以用准入控制器（Kyverno / OPA Gatekeeper / Sigstore Policy Controller）强制"只允许运行已签名镜像"。

### 镜像的安全基线检查表

- [ ] 非 root 运行（`USER 65532:65532`）
- [ ] 最小基础镜像（distroless / scratch），不含 shell、包管理器、编译器
- [ ] 不含密钥（检查 `docker history --no-trunc` 和构建 ARG）
- [ ] 固定基础镜像版本（`debian:12-slim` 而不是 `debian:latest`；更严格用 digest）
- [ ] 定期重建（基础镜像的 CVE 修复需要你重新构建才能拿到）
- [ ] 扫描无 HIGH/CRITICAL 漏洞
- [ ] 有 SBOM 和签名

---

## 9. 动手实验

### 实验 1：观察缓存行为

```bash
cd ~/lab/hello
docker build -t hello:cache .              # 首次，慢
docker build -t hello:cache .              # 再次，全部 CACHED

# 改一行源码
echo "// touch" >> cmd/server/main.go
docker build -t hello:cache .              # 观察：go mod download 仍是 CACHED，只有 build 层重跑

# 改 go.mod
go get github.com/google/uuid
docker build -t hello:cache .              # 观察：从 go mod download 开始全部失效
```

### 实验 2：对比镜像大小

写三个 Dockerfile，构建后对比：

```bash
# Dockerfile.fat     单阶段 golang:1.26
# Dockerfile.alpine  多阶段 + alpine
# Dockerfile.distroless  多阶段 + distroless（上面那个）

docker images | grep hello
# hello  fat         1.2GB
# hello  alpine      17MB
# hello  distroless  9MB
```

再对比拉取时间和攻击面：

```bash
trivy image hello:fat --severity HIGH,CRITICAL | tail -5
trivy image hello:distroless --severity HIGH,CRITICAL | tail -5
```

### 实验 3：亲手制造 `exec format error`

```bash
docker buildx build --platform linux/amd64 -t hello:amd64 --load .
docker run --rm hello:amd64
# 在 arm64 Mac 上：exec /server: exec format error（或 Docker 帮你用 QEMU 跑，但极慢）
```

### 实验 4：把镜像装进集群

```bash
docker build -t hello:v0.1.0 .
kind load docker-image hello:v0.1.0 --name learn

kubectl run hello --image=hello:v0.1.0 --image-pull-policy=IfNotPresent
kubectl wait --for=condition=Ready pod/hello --timeout=60s
kubectl port-forward pod/hello 8080:8080 &
curl -s localhost:8080 | jq
kill %1; kubectl delete pod hello
```

---

## 10. 本章检查清单

- [ ] 镜像由哪几部分组成？digest 和 tag 的区别与各自用途？
- [ ] 为什么生产环境不能用 `latest`？举一个具体故障场景
- [ ] `ENTRYPOINT` 和 `CMD` 的区别？它们分别对应 K8s 的哪个字段？
- [ ] `CMD ./server` 和 `CMD ["./server"]` 的区别会导致什么生产问题？
- [ ] 为什么 `COPY go.mod go.sum ./` 要写在 `COPY . .` 前面？
- [ ] `scratch` 镜像跑 Go 服务需要额外处理哪三件事？
- [ ] Alpine 的 musl 在 K8s 里可能引发什么故障？
- [ ] 多架构镜像的原理是什么？`BUILDPLATFORM` 和 `TARGETPLATFORM` 的区别？
- [ ] 把自己的 Go 服务镜像做到 10MB 以内，并通过 trivy 扫描

---

## 11. 延伸阅读

- [Dockerfile 官方参考](https://docs.docker.com/reference/dockerfile/)
- [BuildKit / Dockerfile 前端语法](https://docs.docker.com/build/buildkit/dockerfile-release-notes/)
- [Distroless 镜像](https://github.com/GoogleContainerTools/distroless)
- [Docker 构建最佳实践](https://docs.docker.com/build/building/best-practices/)
- [SLSA 供应链安全框架](https://slsa.dev/)

---

下一章：[04 - 容器运行时配置：网络、环境变量、文件系统、日志](./04-runtime-config.md)
