# 04 - 容器运行时配置：网络、环境变量、文件系统、日志

> 本章目标：把你的四个核心问题在**单机层面**彻底答清楚——容器怎么访问网络、怎么拿环境变量、
> 怎么读配置文件、日志去哪了。这些机制在 K8s 里几乎原样保留，只是换了个声明方式。
> 学完这章，第 7~11 章的 K8s 配置对你来说就只是"换一套 YAML 写法"。
> 预计用时：3 小时（含实验）。

---

## 1. 网络：端口映射到底做了什么

### 1.1 Docker 的四种网络模式

| 模式 | `--network` | 容器有独立 IP | 说明 | K8s 里的对应 |
|---|---|---|---|---|
| **bridge**（默认） | `bridge` 或自定义 | ✅ | 容器接到虚拟网桥 `docker0`，通过 NAT 出网 | Pod 网络（但 K8s 无 NAT，见第 10 章） |
| **host** | `host` | ❌ 用宿主机网络栈 | 不做隔离，容器直接监听宿主机端口 | `hostNetwork: true` |
| **none** | `none` | ✅ 但只有 lo | 完全无网络 | 极少用 |
| **container** | `container:<id>` | 共享另一个容器的 | 加入已有 NET namespace | **Pod 内多容器就是这个** |

### 1.2 bridge 模式与 `-p` 的原理

```bash
docker run -d --name web -p 8080:80 nginx:alpine
```

这条命令背后发生了什么：

```
     你的 Mac / Linux 宿主机
     ┌──────────────────────────────────────────────┐
     │  eth0 / lo    :8080  ◄── 你 curl 这里          │
     │      │                                        │
     │      │ iptables DNAT: 8080 → 172.17.0.2:80    │
     │      ▼                                        │
     │  ┌────────────┐                               │
     │  │  docker0   │ 172.17.0.1  (网桥)             │
     │  └─────┬──────┘                               │
     │        │ veth pair（一对虚拟网卡，像管道两端）      │
     │  ┌─────┴──────────────────┐                   │
     │  │ 容器 NET namespace      │                   │
     │  │   eth0: 172.17.0.2      │                   │
     │  │   nginx 监听 :80         │                   │
     │  └────────────────────────┘                   │
     └──────────────────────────────────────────────┘
```

具体步骤：
1. 创建 NET namespace
2. 创建一对 **veth**（虚拟以太网设备），一端放进容器叫 `eth0`，一端留在宿主机接到 `docker0` 网桥
3. 从网桥子网分配 IP（如 `172.17.0.2`），设默认路由指向 `172.17.0.1`
4. 加 iptables 规则：`DNAT` 把宿主机 `:8080` 的入站流量改写目标地址到 `172.17.0.2:80`；`MASQUERADE` 让容器出站流量伪装成宿主机 IP

验证（在 `colima ssh` 的 Linux 里）：

```bash
docker run -d --name web -p 8080:80 nginx:alpine

# 看容器 IP
docker inspect web -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
# 172.17.0.2

# 看 NAT 规则
sudo iptables -t nat -L DOCKER -n --line-numbers
# DNAT  tcp -- 0.0.0.0/0  0.0.0.0/0  tcp dpt:8080 to:172.17.0.2:80

# 看网桥
ip link show docker0
bridge link                    # 看挂在网桥上的 veth

# 从宿主机直接访问容器 IP（不走映射）
curl -s 172.17.0.2:80 | head -3
```

### 1.3 `-p` 的完整语法

```bash
-p 8080:80              # 宿主机所有网卡的 8080 → 容器 80
-p 127.0.0.1:8080:80    # 只监听宿主机回环，外网访问不到（更安全）
-p 8080:80/udp          # UDP
-p 80                   # 容器 80 → 宿主机随机高位端口（docker port 查）
-P                      # 把 Dockerfile 里所有 EXPOSE 的端口随机映射
```

**常见错误 ①：容器监听 `127.0.0.1`**

```go
// ❌ 容器里这样写，外面永远连不上
http.ListenAndServe("127.0.0.1:8080", nil)

// ✅ 必须监听所有接口
http.ListenAndServe(":8080", nil)     // 等价于 0.0.0.0:8080
```

因为 `-p` 的 DNAT 把包送到 `172.17.0.2:8080`，而程序只在 `127.0.0.1:8080` 上听。**这是新手第一号故障**。

**常见错误 ②：以为 `EXPOSE` 会开放端口**
`EXPOSE` 纯粹是文档，不做任何事。真正开放要靠 `-p`。

### 1.4 host 网络模式

```bash
docker run -d --network=host nginx:alpine
curl localhost:80          # 直接就通，不需要 -p
```

- 优点：零 NAT 开销（高性能网络场景，如 DPDK、大流量代理）
- 缺点：**端口冲突**（两个容器不能都监听 80）、失去网络隔离
- **macOS/Windows 上不可用**（因为有 VM 那层，`--network=host` 是 VM 的 host 而不是你的 Mac）

K8s 里对应 `hostNetwork: true`，主要用于 CNI 插件、ingress controller、监控 agent 这类系统组件。

### 1.5 容器间通信

**默认 bridge 网络没有 DNS**，容器间只能用 IP。**自定义 bridge 网络有内置 DNS**：

```bash
docker network create appnet
docker run -d --name db  --network appnet postgres:17-alpine -e POSTGRES_PASSWORD=x
docker run -d --name api --network appnet myapi

# 在 api 容器里可以直接用容器名解析
docker exec api ping -c1 db          # db 解析到 db 容器的 IP ✅
```

这就是**服务发现**的雏形。K8s 把它做成了集群级的 Service + CoreDNS（第 10 章）。

```bash
docker network ls
docker network inspect appnet        # 看这个网络里有哪些容器
docker network connect appnet web    # 把已有容器加进网络（一个容器可加入多个网络）
```

### 1.6 容器怎么访问宿主机

这是你明确问到的点。四种情况：

| 场景 | 方法 |
|---|---|
| 容器 → 宿主机上的服务（Docker Desktop / OrbStack / Colima） | `host.docker.internal`（内置 DNS 名） |
| 容器 → 宿主机（Linux 原生 Docker） | `--add-host=host.docker.internal:host-gateway`，或直接用网桥网关 IP `172.17.0.1` |
| 容器 → 宿主机（用 host 网络） | `localhost` 即宿主机 |
| 容器 → 外网 | 默认就通（走 MASQUERADE NAT） |

```bash
# Linux 上让容器能用 host.docker.internal
docker run --rm --add-host=host.docker.internal:host-gateway alpine \
  ping -c1 host.docker.internal
```

> **K8s 里的等价物**：Pod 访问节点用 Downward API 拿 `status.hostIP`（第 8 章）；
> 或者用 `hostNetwork: true`。但要注意——**在 K8s 里依赖节点上的服务是反模式**，
> 因为 Pod 可能被调度到任何节点。正确做法是把那个服务也做成 Service。

### 1.7 容器的 DNS 与 /etc/hosts

```bash
docker run --rm alpine cat /etc/resolv.conf
# nameserver 127.0.0.11        ← Docker 内嵌 DNS（自定义网络下）

docker run --rm alpine cat /etc/hosts
# 172.17.0.2  <container-id>

# 自定义
docker run --rm --dns=8.8.8.8 --add-host=myhost:1.2.3.4 alpine cat /etc/hosts
```

K8s 里对应 `dnsPolicy`、`dnsConfig`、`hostAliases`（第 10 章）。

### 1.8 网络排查工具箱

生产镜像是 distroless，没有任何工具。用 `netshoot`：

```bash
# 加入目标容器的网络 namespace 排查
docker run --rm -it --network=container:web nicolaka/netshoot
# 里面有：dig nslookup curl tcpdump ss iptables mtr netstat tshark ...

ss -tlnp              # 看谁在监听
dig db                # 测 DNS
curl -v localhost:80
tcpdump -i eth0 -nn port 80
```

**记住 `nicolaka/netshoot`**，第 22 章排障会反复用它。

---

## 2. 环境变量：配置的第一入口

### 2.1 三种设置方式与优先级

```bash
# ① Dockerfile 里的 ENV —— 镜像默认值
ENV PORT=8080 LOG_LEVEL=info

# ② docker run -e —— 覆盖镜像默认值
docker run -e PORT=9090 -e LOG_LEVEL=debug myapp

# ③ 从文件读
docker run --env-file ./app.env myapp

# ④ 透传宿主机的同名变量（不写值）
export API_KEY=secret
docker run -e API_KEY myapp
```

优先级：`-e` / `--env-file` > Dockerfile `ENV`。

`app.env` 格式（注意：**不支持** shell 展开、引号会被当成值的一部分）：

```
PORT=9090
LOG_LEVEL=debug
DB_DSN=postgres://user:pass@db:5432/app?sslmode=disable
```

### 2.2 验证与调试

```bash
docker run --rm -e FOO=bar myapp env       # 打印容器内所有环境变量
docker inspect <container> -f '{{json .Config.Env}}' | jq
docker exec <container> env                 # 运行中的容器
```

### 2.3 Go 里的读取模式

```go
// 简单场景
port := os.Getenv("PORT")

// 生产场景：用结构体 + 校验，启动时 fail fast
type Config struct {
    Port     string        `env:"PORT" envDefault:"8080"`
    LogLevel string        `env:"LOG_LEVEL" envDefault:"info"`
    DBDSN    string        `env:"DB_DSN,required"`
    Timeout  time.Duration `env:"TIMEOUT" envDefault:"5s"`
}
// 推荐库：github.com/caarlos0/env/v11、github.com/kelseyhightower/envconfig
// 或 spf13/viper（支持 env + 文件 + flag 多来源合并）
```

**原则（12-Factor App 第三条）**：配置来自环境，代码里不写死任何环境相关的东西。

**启动时校验必填项并直接退出**，比运行到一半才发现配置缺失好一万倍——K8s 里这会表现为 `CrashLoopBackOff`，`kubectl logs` 一眼就能看到原因。

### 2.4 环境变量的边界

| 适合放环境变量 | 不适合 |
|---|---|
| 端口、日志级别、超时、功能开关 | 大段的 YAML/JSON 配置（换行难处理，`kubectl describe` 刷屏） |
| 依赖服务的地址 | 证书、私钥（二进制、多行） |
| 环境标识（dev/staging/prod） | 需要热更新的配置（环境变量**无法**在进程运行时改变） |
| 少量密钥（配合 Secret） | 超过 1MB 的内容（有大小限制） |

**关键限制：环境变量在进程启动时就固定了，之后无法改变。** 想改就得重启进程。这是后面第 8 章"ConfigMap 改了为什么不生效"的根本原因。

### 2.5 密钥不要放环境变量里（至少要知道风险）

环境变量会出现在：
- `docker inspect` 的输出
- `/proc/<pid>/environ`（同宿主机的其他进程可能读到）
- 崩溃时的 core dump
- 很多 APM/错误上报 SDK 默认会上报环境变量

**更安全的做法**：密钥挂载为文件（tmpfs），程序读文件。第 8、14 章展开。

---

## 3. 文件系统：配置文件与数据持久化

### 3.1 三种挂载类型

| 类型 | 语法 | 数据存在哪 | 用途 |
|---|---|---|---|
| **bind mount** | `-v /host/path:/container/path` | 宿主机指定目录 | 开发时挂源码/配置；生产慎用 |
| **volume** | `-v myvol:/data` | Docker 管理的目录（`/var/lib/docker/volumes/`） | **数据持久化首选** |
| **tmpfs** | `--tmpfs /tmp` | 内存 | 临时文件、密钥（不落盘） |

现代推荐用 `--mount` 语法（更明确，出错时报错更清楚）：

```bash
docker run -d \
  --mount type=bind,source="$PWD/config",target=/etc/app,readonly \
  --mount type=volume,source=appdata,target=/var/lib/app \
  --mount type=tmpfs,target=/tmp,tmpfs-size=64m \
  myapp
```

对比 `-v` 的坑：`-v /nonexistent/path:/data` 时 Docker 会**默默创建一个空目录**，你的配置文件"消失"了；`--mount` 会直接报错。

### 3.2 注入配置文件

```bash
# 准备配置
mkdir -p ~/lab/hello/config
cat > ~/lab/hello/config/app.yaml <<'EOF'
server:
  port: 8080
  timeout: 5s
features:
  new_ui: true
EOF

# 只读挂载进容器
docker run -d --name app \
  --mount type=bind,source="$HOME/lab/hello/config",target=/etc/app,readonly \
  -e CONFIG_PATH=/etc/app/app.yaml \
  myapp

docker exec app cat /etc/app/app.yaml
```

**只读挂载（`readonly` / `:ro`）是好习惯**：防止容器意外写坏宿主机文件，也符合不可变基础设施。

**挂单个文件的坑**：

```bash
-v $PWD/app.yaml:/etc/app/app.yaml     # 挂单文件
```

宿主机上的文件被替换（很多编辑器保存时是"写新文件+rename"，inode 变了）后，容器里看到的**还是旧文件**——因为 bind mount 绑的是 inode。这个坑在 K8s 里以另一种形式出现（ConfigMap 用 subPath 挂载不会热更新，第 8 章）。

**推荐做法**：挂目录而不是单个文件。

### 3.3 权限问题（高频踩坑）

容器里的 UID 和宿主机是**同一个数字空间**（除非开了 user namespace）。

```bash
# 容器以 UID 65532 运行，往宿主机目录写
docker run --rm -u 65532:65532 \
  -v $PWD/data:/data alpine touch /data/test
# touch: /data/test: Permission denied      ← 宿主机目录属于你（UID 501/1000）
```

解决方案：

```bash
# ① 改宿主机目录属主
sudo chown -R 65532:65532 ./data

# ② 用你自己的 UID 跑容器（开发时常用）
docker run -u $(id -u):$(id -g) -v $PWD/data:/data alpine touch /data/test

# ③ 用 volume 而不是 bind mount（Docker 会处理初始权限）
docker volume create appdata
docker run -u 65532 -v appdata:/data alpine touch /data/test    # ✅
```

> K8s 里对应的解法是 `securityContext.fsGroup`——kubelet 会把挂载卷的属组改成指定 GID。
> 第 11 章详解。这是**有状态服务最常见的启动失败原因**。

### 3.4 只读根文件系统

安全加固的重要一环：

```bash
docker run --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount type=volume,source=appdata,target=/var/lib/app \
  myapp
```

容器根文件系统只读，只有明确挂载的地方可写。这样即使被攻破，攻击者也无法写入 webshell。

**Go 服务通常天然满足这个要求**（不写临时文件），只要注意：
- 有些库会写 `/tmp`（挂 tmpfs）
- 日志写 stdout 而不是文件（见下一节）

K8s 对应：`securityContext.readOnlyRootFilesystem: true`。

### 3.5 volume 管理

```bash
docker volume create appdata
docker volume ls
docker volume inspect appdata      # 看 Mountpoint
docker volume rm appdata
docker volume prune                # 清理未使用的（危险，会删数据）

# 备份 volume
docker run --rm -v appdata:/data -v $PWD:/backup alpine \
  tar czf /backup/appdata-$(date +%F).tar.gz -C /data .
```

---

## 4. 日志：为什么必须写 stdout

### 4.1 核心原则

**容器化应用不应该管理自己的日志文件。** 它应该把日志当作事件流，无缓冲地写到 `stdout`/`stderr`，由运行环境去收集、路由、归档。（12-Factor App 第十一条）

**为什么？**

| 写日志文件的问题 | 写 stdout 的好处 |
|---|---|
| 文件在容器可写层里，容器一删就没了 | 运行时接管，容器删了日志还在 |
| 要自己处理轮转，写错就撑爆磁盘 | 运行时统一轮转 |
| 每个应用日志路径不同，采集配置千奇百怪 | 统一路径，采集器零配置 |
| 多副本时要区分是哪个实例写的 | 运行时自动打上容器/Pod 元数据 |
| `kubectl logs` 看不到 | `kubectl logs` 直接可用 |

### 4.2 日志去哪了

```bash
docker run -d --name app myapp
docker logs app
docker logs -f --tail 100 app
docker logs --since 5m app
docker logs -t app                  # 带时间戳

# 日志文件的真实位置（json-file 驱动，Linux）
docker inspect app -f '{{.LogPath}}'
# /var/lib/docker/containers/<id>/<id>-json.log
sudo tail -2 $(docker inspect app -f '{{.LogPath}}')
# {"log":"...\n","stream":"stdout","time":"2026-07-29T..."}
```

### 4.3 日志驱动与轮转

**默认 `json-file` 驱动不限制大小**——这是经典的"磁盘写满导致节点宕机"事故来源。

```bash
docker run -d \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  myapp
```

或全局配置 `/etc/docker/daemon.json`：

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
```

其他驱动：`local`（更高效的二进制格式）、`journald`、`fluentd`、`syslog`、`awslogs`、`none`。

> **K8s 里**：kubelet 负责轮转，参数是 `containerLogMaxSize`（默认 10Mi）和 `containerLogMaxFiles`（默认 5）。
> 日志落在节点的 `/var/log/pods/<ns>_<pod>_<uid>/<container>/0.log`。第 13 章详解采集链路。

### 4.4 结构化日志（生产必须）

纯文本日志在几十个副本、每秒几千条的规模下无法查询。用 JSON：

```go
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: parseLevel(os.Getenv("LOG_LEVEL")),
}))
slog.SetDefault(logger)

slog.Info("request handled",
    "method", r.Method,
    "path", r.URL.Path,
    "status", 200,
    "duration_ms", 12.3,
    "trace_id", traceID,   // 关键：把 trace_id 打进去，第 13 章串联日志和追踪
)
// {"time":"2026-07-29T10:00:00Z","level":"INFO","msg":"request handled",
//  "method":"GET","path":"/","status":200,"duration_ms":12.3,"trace_id":"abc"}
```

Go 1.21+ 的标准库 `log/slog` 就够用，无需第三方库（zap/zerolog 性能更好，超高吞吐时再考虑）。

**几条实践**：
- 应用日志和访问日志都写 stdout；只有需要区分严重级别时才用 stderr
- **不要**在日志里打印密钥、token、身份证号、完整请求体
- 加上 `trace_id` / `request_id`，否则分布式系统里无法串联
- 日志级别通过环境变量控制，支持不重启调整最好（暴露一个 `/debug/loglevel` 端点）

### 4.5 缓冲的坑

```go
// ❌ 用了带缓冲的 writer，容器被 kill 时日志丢失
w := bufio.NewWriter(os.Stdout)

// ✅ 直接写 os.Stdout（无缓冲）
```

其他语言更常见（Python 需要 `PYTHONUNBUFFERED=1`，Node 的 stdout 在管道模式下是异步的）。Go 的 `os.Stdout` 默认无缓冲，天然正确。

---

## 5. 资源限制

```bash
docker run -d \
  --memory=512m \              # 内存硬限制，超了 OOMKill
  --memory-reservation=256m \  # 软限制（内存压力时优先回收）
  --memory-swap=512m \         # 内存+swap 总量；等于 memory 即禁用 swap
  --cpus=1.5 \                 # CPU 配额（1.5 核）
  --cpu-shares=1024 \          # 相对权重（争抢时的比例）
  --pids-limit=200 \           # 最大进程数，防 fork 炸弹
  myapp

docker stats                   # 实时看用量
docker stats --no-stream
```

### Go 服务必配的两个环境变量

```bash
docker run -d \
  --memory=512m --cpus=1 \
  -e GOMEMLIMIT=450MiB \       # 内存软上限，让 GC 在接近上限时更激进
  -e GOMAXPROCS=1 \            # 与 CPU limit 对齐（Go 1.25+ 可自动感知）
  myapp
```

**为什么 `GOMEMLIMIT` 设成 limit 的 ~85%？**
Go 的 GC 默认只按 `GOGC=100`（堆翻倍时回收）工作，不知道容器有内存上限。堆一路涨到 512MB 就被内核 OOMKill（退出码 137），而 Go 完全来不及反应。设了 `GOMEMLIMIT` 后，接近 450MiB 时 GC 会持续触发，把内存压回去。留 15% 余量给 goroutine 栈、mmap、运行时元数据这些不在堆里的部分。

第 7 章会讲怎么在 K8s 里用 Downward API 自动从 limit 推导出这两个值。

---

## 6. 信号与优雅退出（生产事故重灾区）

### 6.1 完整的停止流程

```bash
docker stop app          # ① 发 SIGTERM → ② 等 10 秒（默认）→ ③ 发 SIGKILL
docker stop -t 30 app    # 改成等 30 秒
docker kill app          # 直接 SIGKILL
docker kill -s HUP app   # 发指定信号
```

> **K8s 里完全一样**：先 SIGTERM，等 `terminationGracePeriodSeconds`（默认 30 秒），再 SIGKILL。

### 6.2 PID 1 的特殊性

容器里的 PID 1 有两个特殊行为（内核规定）：

**① PID 1 默认忽略所有没有注册处理函数的信号**
普通进程收到未处理的 SIGTERM 会默认终止；PID 1 不会。所以如果你的程序没写信号处理，`docker stop` 会**傻等 10 秒然后强杀**。

**② PID 1 要负责回收孤儿进程（僵尸进程）**
如果你的程序会 fork 子进程且不 `wait`，僵尸进程会堆积。

### 6.3 三个必须避免的写法

```dockerfile
# ❌ ① shell 形式：PID 1 是 sh，它不转发 SIGTERM
CMD ./server

# ❌ ② 用 shell 脚本包装但没有 exec
# entrypoint.sh:
#   ./prepare.sh
#   ./server          ← server 是 sh 的子进程，收不到信号
ENTRYPOINT ["/entrypoint.sh"]

# ✅ ③ 正确：脚本最后一行用 exec 替换掉 shell 进程
# entrypoint.sh:
#   ./prepare.sh
#   exec ./server     ← server 变成 PID 1
```

需要处理僵尸进程时（比如你的程序会起子进程）：

```bash
docker run --init myapp        # Docker 注入 tini 作为 PID 1
```

K8s 里没有 `--init` 等价物，需要在镜像里自己加 `tini` 或 `dumb-init`：

```dockerfile
ENTRYPOINT ["/usr/bin/tini", "--", "/server"]
```

纯 Go 服务通常不需要（不 fork 子进程）。

### 6.4 优雅退出的正确顺序

第 3 章的示例代码已经写对了，这里说清楚**为什么**每一步都必要：

```go
ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
<-ctx.Done()

// ① 先让健康检查变成不健康（K8s 场景关键！见下）
readiness.Store(false)
time.Sleep(5 * time.Second)   // 等负载均衡把你摘掉

// ② 停止接受新连接，等存量请求处理完
srv.Shutdown(shutdownCtx)

// ③ 关闭下游资源
db.Close(); redis.Close(); kafkaProducer.Flush()
```

**为什么第 ① 步必须有 sleep？**（这是 K8s 里最隐蔽的"发布掉请求"根因）

K8s 删 Pod 时，两件事**并发**发生，没有先后保证：
- kubelet 给容器发 SIGTERM
- Endpoint 控制器把 Pod IP 从 Service 摘掉 → kube-proxy 更新 iptables → 各节点生效

如果你收到 SIGTERM 立刻 `Shutdown()`，而 iptables 规则还没更新完（跨节点传播要几百毫秒到几秒），流量还在往你这儿送 → **连接被拒绝，用户看到 502**。

正确做法是收到 SIGTERM 后**先摆手**（readiness 探针失败），睡几秒等流量摘干净，再关服务。第 7、9 章会给出完整的 K8s 配置（`preStop` hook + `terminationGracePeriodSeconds` 的配合）。

### 6.5 实验：亲眼看到区别

```bash
# 用 shell 形式的镜像
cat > /tmp/Dockerfile.bad <<'EOF'
FROM alpine
RUN printf '#!/bin/sh\ntrap "echo GOT SIGTERM; exit 0" TERM\nwhile true; do sleep 1; done\n' > /app.sh && chmod +x /app.sh
CMD /app.sh
EOF
docker build -t sig:bad -f /tmp/Dockerfile.bad /tmp
docker run -d --name bad sig:bad
time docker stop bad          # 约 10 秒（超时强杀）
docker logs bad               # 没有 "GOT SIGTERM"

# exec 形式
sed 's|^CMD /app.sh|CMD ["/app.sh"]|' /tmp/Dockerfile.bad > /tmp/Dockerfile.good
docker build -t sig:good -f /tmp/Dockerfile.good /tmp
docker run -d --name good sig:good
time docker stop good         # 立即返回
docker logs good              # GOT SIGTERM ✅

docker rm -f bad good
```

---

## 7. 其他常用运行时配置

```bash
# 重启策略
docker run --restart=always myapp            # 总是重启（含 daemon 重启后）
docker run --restart=on-failure:3 myapp      # 非零退出时最多重启 3 次
docker run --restart=unless-stopped myapp    # 除非手工停止

# 时区（容器默认 UTC）
docker run -e TZ=Asia/Shanghai myapp
docker run -v /etc/localtime:/etc/localtime:ro myapp     # Linux 上同步宿主机时区

# 主机名 / hosts
docker run -h myhost --add-host=api.internal:10.0.0.5 myapp

# 安全加固组合拳（生产模板）
docker run -d \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop=ALL --security-opt=no-new-privileges \
  -u 65532:65532 \
  --memory=512m --cpus=1 --pids-limit=200 \
  --restart=unless-stopped \
  --log-opt max-size=10m --log-opt max-file=3 \
  myapp
```

`--restart` 在 K8s 里的对应是 Pod 的 `restartPolicy`，但语义不同（K8s 只有 `Always`/`OnFailure`/`Never`，且由 kubelet 用指数退避重启，见第 7 章）。

---

## 8. 单机配置 → K8s 对应关系速查

这张表是本章的核心产出。**后面学 K8s 时随时回来看**：

| 你想做的事 | Docker | Kubernetes |
|---|---|---|
| 暴露端口 | `-p 8080:80` | Service（`NodePort`/`LoadBalancer`）或 `hostPort` |
| 用宿主机网络 | `--network=host` | `spec.hostNetwork: true` |
| 容器间共享网络 | `--network=container:x` | 放进**同一个 Pod** |
| 服务发现 | 自定义网络 + 容器名 | Service + CoreDNS（`svc.ns.svc.cluster.local`） |
| 设环境变量 | `-e KEY=V` | `env:` / `envFrom:`（ConfigMap、Secret） |
| 环境变量文件 | `--env-file` | `envFrom.configMapRef` |
| 挂配置文件 | `-v ./conf:/etc/app:ro` | ConfigMap/Secret 作为 volume 挂载 |
| 持久化数据 | `-v myvol:/data` | PVC + PV（StorageClass 动态供给） |
| 内存盘 | `--tmpfs /tmp` | `emptyDir: {medium: Memory}` |
| 资源限制 | `--memory --cpus` | `resources.limits` / `resources.requests` |
| 只读根文件系统 | `--read-only` | `securityContext.readOnlyRootFilesystem: true` |
| 指定用户 | `-u 65532:65532` | `securityContext.runAsUser/runAsGroup` |
| 文件属组修正 | 手工 `chown` | `securityContext.fsGroup` |
| 丢弃能力 | `--cap-drop=ALL` | `securityContext.capabilities.drop: [ALL]` |
| 看日志 | `docker logs -f` | `kubectl logs -f`（或 `stern`） |
| 日志轮转 | `--log-opt max-size` | kubelet 的 `containerLogMaxSize` |
| 健康检查 | `HEALTHCHECK`（K8s 忽略） | `livenessProbe` / `readinessProbe` / `startupProbe` |
| 重启策略 | `--restart=always` | `restartPolicy` + kubelet 退避 |
| 优雅停止超时 | `docker stop -t 30` | `terminationGracePeriodSeconds: 30` |
| 进入容器 | `docker exec -it sh` | `kubectl exec -it -- sh` |
| 时区 | `-e TZ=` | `env: [{name: TZ, value: Asia/Shanghai}]` |
| 额外 hosts | `--add-host` | `spec.hostAliases` |
| 自定义 DNS | `--dns` | `spec.dnsConfig` / `dnsPolicy` |

---

## 9. 动手实验

### 实验 1：端口映射全景

```bash
cd ~/lab/hello && docker build -t hello:v0.1.0 .

# ① 不映射 —— 外面访问不到，但容器 IP 能访问（在 colima ssh 里）
docker run -d --name t1 hello:v0.1.0
curl -s --max-time 2 localhost:8080 || echo "❌ 不通，符合预期"
IP=$(docker inspect t1 -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
curl -s $IP:8080 | jq -r .message      # ✅ 通

# ② 映射
docker run -d --name t2 -p 8080:8080 hello:v0.1.0
curl -s localhost:8080 | jq -r .hostname

# ③ 只绑回环
docker run -d --name t3 -p 127.0.0.1:8081:8080 hello:v0.1.0
sudo iptables -t nat -S DOCKER | grep 8081

docker rm -f t1 t2 t3
```

### 实验 2：制造并修复"监听 127.0.0.1"的故障

改 `main.go` 的 `Addr` 为 `"127.0.0.1:8080"`，重新构建，`docker run -p 8080:8080`，观察 `curl` 失败。然后用 netshoot 进去 `ss -tlnp` 看到它只在回环上监听。改回 `:8080` 修复。

### 实验 3：配置文件 + 环境变量组合

```bash
mkdir -p ~/lab/hello/conf && echo "greeting: 你好" > ~/lab/hello/conf/app.yaml
docker run -d --name t4 -p 8080:8080 \
  -e GREETING="from env" \
  -e TZ=Asia/Shanghai \
  --mount type=bind,source="$HOME/lab/hello/conf",target=/etc/app,readonly \
  hello:v0.1.0
curl -s localhost:8080 | jq
docker exec t4 /server --help 2>/dev/null || docker inspect t4 -f '{{json .Config.Env}}' | jq
docker rm -f t4
```

### 实验 4：内存限制与 OOM

```bash
docker run -d --name t5 --memory=32m -p 8080:8080 hello:v0.1.0
docker stats --no-stream t5
# 观察 MEM USAGE / LIMIT 那列显示 32MiB
docker rm -f t5
```

### 实验 5：优雅退出

跑第 3 章的 hello 服务，`docker stop` 观察日志里出现 `shutdown signal received, draining...` 和 `bye`，且 `docker stop` 立即返回（而不是等 10 秒）。

---

## 10. 本章检查清单

- [ ] 画出 `docker run -p 8080:80` 的数据路径（宿主机端口 → iptables → veth → 容器）
- [ ] 程序监听 `127.0.0.1` 时为什么外部访问不到？
- [ ] `EXPOSE` 到底做了什么？
- [ ] 容器怎么访问宿主机上的服务？为什么这在 K8s 里是反模式？
- [ ] 环境变量能在进程运行时改变吗？这意味着什么？
- [ ] bind mount / volume / tmpfs 各用在什么场景？
- [ ] 容器以 UID 65532 跑，往 bind mount 目录写文件失败，怎么解决？（说出 3 种）
- [ ] 为什么日志要写 stdout 而不是文件？（说出 3 个理由）
- [ ] `CMD ./server` 会导致什么生产问题？
- [ ] 收到 SIGTERM 后立刻 `srv.Shutdown()` 为什么可能丢请求？
- [ ] Go 服务在容器里必须设置哪两个环境变量？为什么？
- [ ] 把第 8 节的对照表默写一遍（至少 15 行）

---

下一章：[05 - 从单机到集群：Compose 与它的天花板](./05-compose-to-orchestration.md)
