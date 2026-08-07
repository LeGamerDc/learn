# 05 - 从单机到集群：Compose 与它的天花板

> 本章目标：用 Docker Compose 搭一套真实的多服务应用，然后**亲手撞上它的每一堵墙**。
> 撞完之后，你对 Kubernetes 每个组件的存在理由会有切肤的理解，而不是死记概念。
> 预计用时：2 小时（含实验）。

---

## 1. 为什么需要 Compose

第 4 章你已经会用 `docker run` 跑单个容器了。但真实应用长这样：

```
    [Nginx 网关] → [API 服务 ×3] → [Postgres]
                          ↓
                      [Redis]
                          ↑
                   [Worker 服务 ×2]
```

用 `docker run` 起这套东西，你需要：

```bash
docker network create appnet
docker volume create pgdata
docker run -d --name db --network appnet -v pgdata:/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=... postgres:17-alpine
docker run -d --name redis --network appnet redis:7-alpine
docker run -d --name api1 --network appnet -e DB_DSN=... -p 8081:8080 myapi
docker run -d --name api2 ...     # 复制粘贴
docker run -d --name api3 ...     # 复制粘贴
docker run -d --name worker1 ...
# ... 还要保证启动顺序，db 先起来 api 才能连上
```

问题很明显：**命令不可版本化、启动顺序靠人肉、参数复制粘贴、没人知道生产上到底跑着什么配置。**

Compose 把这一坨命令变成一个**声明式的 YAML 文件**——这是你第一次接触"声明式"，也是通往 K8s 的桥。

---

## 2. 实战：搭一套完整应用

### 2.1 扩展我们的 Go 服务

在第 3 章的 `~/lab/hello` 基础上，加上数据库和缓存依赖。新建 `cmd/server/deps.go`：

```go
package main

import (
	"context"
	"database/sql"
	"log/slog"
	"net/http"
	"os"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/redis/go-redis/v9"
)

type deps struct {
	db  *sql.DB
	rdb *redis.Client
}

func initDeps(ctx context.Context) *deps {
	d := &deps{}

	if dsn := os.Getenv("DB_DSN"); dsn != "" {
		db, err := sql.Open("pgx", dsn)
		if err != nil {
			slog.Error("db open failed", "err", err)
			os.Exit(1) // fail fast：配置错就别启动
		}
		db.SetMaxOpenConns(10)
		db.SetMaxIdleConns(5)
		db.SetConnMaxLifetime(30 * time.Minute)
		d.db = db
	}

	if addr := os.Getenv("REDIS_ADDR"); addr != "" {
		d.rdb = redis.NewClient(&redis.Options{Addr: addr})
	}
	return d
}

// readiness：依赖不可用时返回 503，让负载均衡把我摘掉
func (d *deps) readyHandler(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	if d.db != nil {
		if err := d.db.PingContext(ctx); err != nil {
			http.Error(w, "db not ready: "+err.Error(), http.StatusServiceUnavailable)
			return
		}
	}
	if d.rdb != nil {
		if err := d.rdb.Ping(ctx).Err(); err != nil {
			http.Error(w, "redis not ready: "+err.Error(), http.StatusServiceUnavailable)
			return
		}
	}
	w.Write([]byte("ready"))
}

// liveness：只检查进程自己是否还活着，绝不检查外部依赖（重要！第 7 章解释）
func livenessHandler(w http.ResponseWriter, r *http.Request) {
	w.Write([]byte("ok"))
}
```

在 `main.go` 里替换对应的路由注册：

```go
d := initDeps(context.Background())
mux.HandleFunc("GET /healthz", livenessHandler)
mux.HandleFunc("GET /readyz", d.readyHandler)
```

```bash
go get github.com/jackc/pgx/v5 github.com/redis/go-redis/v9
go mod tidy
```

> **划重点：liveness 和 readiness 的区别**
> - **liveness（存活）**：进程是否还能工作？失败 → **重启容器**。绝不能检查数据库！数据库抖一下就把所有 API 副本重启，会把整个系统打崩（雪崩）。
> - **readiness（就绪）**：现在能不能接流量？失败 → **摘掉流量，但不重启**。这里才检查依赖。
>
> 这个区分是 K8s 里最容易配错、后果最严重的地方之一。第 7 章展开。

### 2.2 compose.yaml

```yaml
# ~/lab/hello/compose.yaml
name: hello-stack

services:
  api:
    build:
      context: .
      args:
        VERSION: dev
    image: hello:dev
    environment:
      PORT: "8080"
      LOG_LEVEL: debug
      GREETING: "hello from compose"
      DB_DSN: "postgres://app:app_password@db:5432/app?sslmode=disable"
      REDIS_ADDR: "cache:6379"
      TZ: Asia/Shanghai
      GOMEMLIMIT: 200MiB
    ports:
      - "8080:8080"
    depends_on:
      db:
        condition: service_healthy      # 等 db 健康了再启动
      cache:
        condition: service_started
    healthcheck:
      test: ["CMD", "/server", "-healthcheck"]   # distroless 没有 curl，见下方说明
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 5s
    deploy:
      resources:
        limits:   {cpus: "1.0", memory: 256M}
        reservations: {cpus: "0.1", memory: 64M}
    restart: unless-stopped
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "3"}

  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app_password
      POSTGRES_DB: app
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 5s
      timeout: 3s
      retries: 10
    # 注意：没有 ports —— 数据库不该暴露到宿主机

  cache:
    image: redis:7-alpine
    command: ["redis-server", "--maxmemory", "128mb", "--maxmemory-policy", "allkeys-lru"]
    volumes:
      - redisdata:/data

  gateway:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on: [api]

volumes:
  pgdata:
  redisdata:
```

辅助文件：

```bash
mkdir -p ~/lab/hello/sql
cat > ~/lab/hello/sql/init.sql <<'EOF'
CREATE TABLE IF NOT EXISTS visits (
  id SERIAL PRIMARY KEY,
  hostname TEXT NOT NULL,
  at TIMESTAMPTZ DEFAULT now()
);
EOF

cat > ~/lab/hello/nginx.conf <<'EOF'
upstream api_upstream { server api:8080; }
server {
  listen 80;
  location / {
    proxy_pass http://api_upstream;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
EOF
```

> **healthcheck 的小插曲**：distroless 镜像没有 `curl`/`wget`，Docker 的 `HEALTHCHECK` 没法用。
> 通用做法是在 Go 程序里加一个 `-healthcheck` flag，自己 `http.Get("http://127.0.0.1:8080/healthz")` 然后按结果 `os.Exit`。
> **好消息是**：K8s 的 `httpGet` 探针由 kubelet 从外部发起，**不需要容器里有任何工具**——这是 K8s 比 Docker HEALTHCHECK 好的地方（第 7 章）。
> 想在 Compose 里省事，先临时把 healthcheck 去掉即可。

### 2.3 跑起来

```bash
cd ~/lab/hello
docker compose up -d --build

docker compose ps
docker compose logs -f api
curl -s localhost:8080 | jq        # 直连 api
curl -s localhost:80   | jq        # 走 nginx 网关

# 扩容 api 到 3 个副本（注意：要先删掉 ports 里的固定端口映射，否则冲突）
docker compose up -d --scale api=3
docker compose ps
```

### 2.4 Compose 常用命令

```bash
docker compose up -d              # 创建并启动（幂等：已存在且配置没变的不动）
docker compose up -d --build      # 顺便重新构建镜像
docker compose ps                 # 看状态
docker compose logs -f --tail=50 api
docker compose exec api sh        # 进容器（distroless 进不去）
docker compose restart api
docker compose stop / start
docker compose down               # 停止并删除容器和网络（保留 volume）
docker compose down -v            # 连 volume 一起删（数据没了，谨慎）
docker compose config             # 渲染最终配置（调试变量替换用）
docker compose top                # 看进程
docker compose --profile debug up # 按 profile 启动部分服务
```

### 2.5 多环境：Compose 的 override 机制

```bash
# compose.yaml            基础配置
# compose.override.yaml   本地开发覆盖（默认自动加载）
# compose.prod.yaml       生产覆盖

docker compose -f compose.yaml -f compose.prod.yaml up -d
```

`compose.override.yaml`（开发用，挂载源码热重载）：

```yaml
services:
  api:
    build:
      target: builder          # 用构建阶段的镜像，里面有 go 工具链
    volumes:
      - .:/src
    command: ["go", "run", "./cmd/server"]
    environment:
      LOG_LEVEL: debug
```

**记住这个"基础 + 环境覆盖"的模式**——它就是第 16 章 Kustomize 的 base/overlay，也是第 15 章 Helm 多 values 文件的思路。**同一个问题的三种解法。**

---

## 3. 现在，撞墙

Compose 在单机上已经很好用了。下面逐个演示它撞到的墙——**每一堵墙，都是 Kubernetes 的一个组件**。

### 墙 ①：只有一台机器

```bash
docker compose up -d --scale api=50
```

50 个副本全在你这台机器上。机器一挂，全没了。

Compose 有个 `docker compose --host` 可以指定远程 Docker，但它**没有调度器**——你必须自己决定哪个服务放哪台机器，自己维护清单。

> **K8s 的答案**：**Scheduler**。你只说"我要 50 个副本"，调度器根据每个节点的剩余资源、亲和性规则、污点、拓扑分布约束，自动决定放哪。第 12 章。

### 墙 ②：容器挂了能重启，节点挂了没救

`restart: unless-stopped` 只能救本机上的容器。Docker daemon 挂了、内核 panic 了、机房断电了，服务就是没了。

```bash
# 模拟：直接杀掉容器
docker kill hello-stack-api-1
sleep 3 && docker compose ps      # 它自己起来了 ✅

# 但如果整台机器没了呢？没有任何东西会把它调度到别的机器上 ❌
```

> **K8s 的答案**：**控制器 + 节点心跳**。节点失联超过阈值，Node 控制器标记它 `NotReady`，
> Pod 被驱逐，ReplicaSet 控制器发现副本数不够，在其他节点上重建。第 6、9、12 章。

### 墙 ③：滚动更新要自己写脚本

```bash
docker compose up -d --build      # Compose 的更新 = 停掉旧容器，起新容器
```

期间**服务是中断的**。Compose 没有"先起新的、健康后再摘旧的、分批进行、失败自动回滚"这套逻辑。你得自己写：

```bash
# 你需要手写的伪代码（每个团队都会重写一遍，且各有各的 bug）
for i in 1 2 3; do
  start api_new_$i
  wait_until_healthy api_new_$i || { rollback; exit 1; }
  remove_from_lb api_old_$i
  drain_connections api_old_$i
  stop api_old_$i
done
```

> **K8s 的答案**：**Deployment 的 RollingUpdate 策略**。`maxSurge`、`maxUnavailable`、
> `minReadySeconds`、`progressDeadlineSeconds` 几个参数就搞定，还自带版本历史和一键回滚。第 9 章。

### 墙 ④：服务发现只到容器名，不到副本

`--scale api=3` 后，`nginx.conf` 里的 `server api:8080` 会被 Docker 内嵌 DNS 解析成 3 个 IP（DNS 轮询）。但是：

- **DNS 缓存问题**：nginx 默认只在启动时解析一次域名。你扩容到 5 个，nginx 还在往旧的 3 个转发。
- **没有健康摘除**：某个副本挂了，DNS 里可能还有它的记录，流量继续打过去报错。
- **没有会话保持、没有权重、没有跨节点负载均衡**。

```bash
# 观察 DNS 轮询
docker compose exec gateway sh -c 'for i in $(seq 5); do nslookup api | tail -3; done'
```

> **K8s 的答案**：**Service + Endpoints/EndpointSlice + kube-proxy**。Service 有一个稳定的虚拟 IP，
> 后端列表由控制器根据**探针结果**实时维护，kube-proxy 在每个节点上做内核级负载均衡。第 10 章。

### 墙 ⑤：配置和密钥是明文散落的

`compose.yaml` 里的 `POSTGRES_PASSWORD: app_password` 是明文，提交到 Git 就泄漏了。
Compose 有 `secrets:`，但它只是把宿主机文件挂进去——密钥怎么安全地到达那台宿主机，Compose 不管。

> **K8s 的答案**：**Secret 对象 + RBAC + 加密存储 + 外部密钥系统集成**（External Secrets Operator / Vault）。第 8、14 章。

### 墙 ⑥：没有自动扩缩容

流量涨了，你得半夜起来敲 `--scale api=10`。

> **K8s 的答案**：**HPA**（按 CPU/内存/自定义指标自动调副本数）+ **Cluster Autoscaler**（节点不够时自动加机器）。第 12 章。

### 墙 ⑦：没有资源隔离保障

`deploy.resources.limits` 在 Compose（非 Swarm 模式）下部分生效，但**没有"预留"概念**——Docker 不会因为机器资源不足而拒绝启动容器。结果是超卖到所有服务一起变慢。

> **K8s 的答案**：**requests（调度依据）+ limits（运行时上限）+ QoS 分级 + 驱逐机制**。第 7、12 章。

### 墙 ⑧：状态与存储绑死在单机

`pgdata` volume 在这台机器的 `/var/lib/docker/volumes/` 下。这台机器挂了，数据在里面出不来。想把数据库迁到别的机器？手工 `tar` 打包搬运。

> **K8s 的答案**：**PV/PVC/StorageClass/CSI**——存储被抽象成可被任何节点挂载的网络卷，Pod 漂移时数据跟着走。第 11 章。

### 墙 ⑨：没有声明式的持续调谐

Compose 是**一次性**的：`up` 的那一刻它对齐一次期望状态，之后就不管了。有人手工 `docker rm` 了一个容器，Compose 不会自动补。你必须再跑一次 `up`。

> **K8s 的答案**：**控制器永不停止的调谐循环**。这是 K8s 与 Compose 最本质的区别，第 6 章的全部内容。

### 墙 ⑩：没有多租户、权限、审计

谁能改什么？谁在什么时候改了？Compose 完全没有概念——能 SSH 上机器的人就能干任何事。

> **K8s 的答案**：**Namespace + RBAC + ResourceQuota + 审计日志**。第 14 章。

---

## 4. 把这十堵墙翻译成 K8s 组件

这张表是本章最重要的产出，它是你的**学习地图**：

| 撞到的墙 | Kubernetes 的答案 | 对应章节 |
|---|---|---|
| ① 只有一台机器 | Scheduler（调度器） | 12 |
| ② 节点挂了没救 | Node Controller + ReplicaSet Controller | 6、9、12 |
| ③ 滚动更新要手写 | Deployment 的 RollingUpdate 策略 | 9 |
| ④ 服务发现太弱 | Service + EndpointSlice + kube-proxy + CoreDNS | 10 |
| ⑤ 配置密钥明文 | ConfigMap / Secret / External Secrets | 8、14 |
| ⑥ 无自动扩缩容 | HPA / VPA / Cluster Autoscaler | 12 |
| ⑦ 无资源保障 | requests/limits + QoS + 驱逐 | 7、12 |
| ⑧ 存储绑死单机 | PV / PVC / StorageClass / CSI | 11 |
| ⑨ 无持续调谐 | 控制器模式（Reconcile Loop） | 6 |
| ⑩ 无权限审计 | Namespace + RBAC + Quota + Audit | 14 |

**Kubernetes 不是"更复杂的 Compose"，它是把上面这十件事全部产品化的系统。** 它复杂，是因为这十件事本身就复杂——你自己实现同样绕不开。

---

## 5. Compose 还有价值吗？

有，而且很大。**不要因为学了 K8s 就在所有地方用 K8s。**

| 场景 | 推荐 |
|---|---|
| 本地开发环境（起依赖：db、redis、kafka） | **Compose** ✅ 简单、快、零学习成本 |
| CI 里跑集成测试 | **Compose** 或 testcontainers |
| 单机部署的内部工具、demo | **Compose** ✅ |
| 生产、多副本、需要高可用 | **Kubernetes** |
| 就一个静态站点 / 一个 API | 云托管服务（Cloud Run / App Runner）往往更划算 |

一个健康的团队常见形态是：**本地用 Compose 开发，CI 用 Compose 跑测试，生产用 K8s 部署**。

> 有工具可以把 `compose.yaml` 转成 K8s 清单（[kompose](https://kompose.io/)），
> 可以拿来快速对照学习，但**转换结果不能直接上生产**（没有探针、没有资源限制、没有 PDB、Service 类型往往不对）。
> 拿它当"K8s YAML 长什么样"的启蒙工具即可。

---

## 6. 动手实验

### 实验 1：完整跑通上面那套栈

包括：`up -d --build`、看日志、访问网关、`--scale api=3`、观察 `hostname` 字段在多次请求间变化（nginx 轮询）。

### 实验 2：亲手撞墙 ③

```bash
# 一边持续压测
while true; do curl -s -o /dev/null -w "%{http_code} " localhost:80; sleep 0.2; done &

# 一边更新
docker compose up -d --build api

# 观察输出里出现的 502 —— 这就是"没有滚动更新"的代价
kill %1
```

记住这个 502 的数量。第 9 章你会用 Deployment 做同样的更新，那时它应该**一个 502 都没有**。

### 实验 3：亲手撞墙 ⑨

```bash
docker rm -f hello-stack-cache-1
docker compose ps               # cache 没了，Compose 不会自己补
curl -s localhost:8080/readyz   # 503，服务不可用
docker compose up -d            # 必须手工再跑一次
```

第 9 章你会 `kubectl delete pod`，然后眼睁睁看着它几秒内自己回来。

### 实验 4：观察 DNS 轮询的缺陷

```bash
docker compose up -d --scale api=3
docker compose exec gateway nginx -s reload    # 必须 reload 才认识新副本
# 停掉一个副本
docker stop hello-stack-api-2
# 继续压测，观察部分请求 502 —— nginx 还在往死掉的副本转发
```

---

## 7. 本章检查清单

- [ ] 写出一个包含 4 个服务、有依赖顺序、有健康检查、有 volume 的 `compose.yaml`
- [ ] `depends_on` 的 `service_started` 和 `service_healthy` 有什么区别？
- [ ] liveness 和 readiness 探针的区别是什么？为什么 liveness **绝对不能**检查数据库？
- [ ] 说出 Compose 的 10 堵墙，以及 K8s 分别用什么组件解决
- [ ] 为什么说 Compose 是"一次性对齐"而 K8s 是"持续调谐"？
- [ ] 什么场景下你**不应该**用 K8s？

---

## 8. 阶段一小结

到这里你应该已经具备：

- ✅ 理解容器 = 进程 + namespace + cgroup + rootfs
- ✅ 能写生产级 Dockerfile，镜像 10MB 级别，多架构
- ✅ 掌握容器的网络映射、环境变量、文件挂载、日志、资源限制、信号处理
- ✅ 能用 Compose 编排多服务应用
- ✅ **清楚地知道单机编排的边界在哪**

现在，你准备好了。

---

下一章：[06 - Kubernetes 架构与设计哲学](./06-k8s-architecture.md)
