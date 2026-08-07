# 08 - 配置与密钥：ConfigMap 和 Secret

> 本章目标：回答"K8s 里怎么给应用注入环境变量和配置文件"，以及最容易踩的坑——
> **改了 ConfigMap 为什么不生效**。还会讲密钥的正确管理方式。
> 预计用时：2 小时。

---

## 1. 为什么要把配置和镜像分开

回顾不可变基础设施：**同一个镜像应该能跑在 dev / staging / prod**，差异只在配置。

```
                ┌── dev  配置 ──► dev  环境
镜像 v1.2.3 ─────┼── stg  配置 ──► stg  环境
（唯一不变的构件） └── prod 配置 ──► prod 环境
```

如果配置打进镜像，你就得为每个环境构建一次——那么"prod 跑的镜像"和"你测过的镜像"就**不是同一个二进制**了。这是最经典的发布事故来源。

K8s 提供两个对象：

| | ConfigMap | Secret |
|---|---|---|
| 用途 | 非敏感配置 | 密码、token、证书、私钥 |
| 存储 | etcd 明文 | etcd 里是 **base64**（**不是加密！**），需额外开启静态加密 |
| 大小上限 | 1 MiB | 1 MiB |
| 挂载为文件时 | 普通文件 | **tmpfs（内存）**，不落盘 |
| RBAC | 通常宽松 | 应严格限制 |

⚠️ **base64 不是加密**。`echo eGX6 | base64 -d` 就还原了。Secret 相比 ConfigMap 的真正区别是：
以 tmpfs 挂载、支持静态加密、可被 RBAC 单独管控、`kubectl describe` 不显示内容、云厂商有额外集成。

---

## 2. 创建 ConfigMap

### 2.1 命令式（快速试验）

```bash
# 从字面值
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=PORT=8080

# 从文件（key = 文件名，value = 文件内容）
kubectl create configmap app-files --from-file=./config.yaml
kubectl create configmap app-files --from-file=app.yaml=./config.yaml   # 指定 key
kubectl create configmap app-files --from-file=./conf-dir/              # 整个目录

# 从 env 文件（每行一个 KEY=VALUE，生成多个 key）
kubectl create configmap app-env --from-env-file=./app.env

kubectl get cm app-config -o yaml
kubectl describe cm app-config
```

### 2.2 声明式（生产用这个）

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hello-config
  namespace: default
immutable: false          # 设为 true 后不可修改，见 §6
data:                     # 字符串键值
  LOG_LEVEL: "info"
  PORT: "8080"
  GREETING: "hello from configmap"
  # 整个文件作为一个 key（注意 | 保留换行）
  config.yaml: |
    server:
      port: 8080
      timeout: 5s
      max_conns: 100
    features:
      new_ui: true
      beta_api: false
  nginx.conf: |
    upstream backend { server hello:80; }
    server { listen 80; location / { proxy_pass http://backend; } }
binaryData:               # 二进制内容用 base64
  cert.der: <base64>
```

**key 的命名规则**：只能包含字母、数字、`-`、`_`、`.`。所以 `my/key` 这种是非法的。

---

## 3. 四种消费方式

### 方式 ①：单个 key → 环境变量

```yaml
env:
  - name: LOG_LEVEL
    valueFrom:
      configMapKeyRef:
        name: hello-config
        key: LOG_LEVEL
        optional: false      # false（默认）：key 不存在则 Pod 启动失败
```

**特点**：精确控制、可重命名。`optional: false` 让配置缺失时**快速失败**，比运行到一半才出错好。

### 方式 ②：整个 ConfigMap → 环境变量

```yaml
envFrom:
  - configMapRef:
      name: hello-config
    prefix: APP_          # 可选：所有 key 加前缀，变成 APP_LOG_LEVEL 等
  - secretRef:
      name: hello-secrets
```

**特点**：省事。**缺点**：
- 如果 ConfigMap 里有 `config.yaml` 这种多行内容，也会变成环境变量（巨长，`kubectl describe` 刷屏）
- key 名不合法（含 `.` 等）会被**静默跳过**
- 你无法从 Pod spec 看出到底注入了哪些变量

**建议**：`envFrom` 用于纯 KV 的 ConfigMap；文件型内容单独放一个 ConfigMap 用挂载方式。

### 方式 ③：挂载为文件（推荐用于配置文件）

```yaml
volumes:
  - name: config
    configMap:
      name: hello-config
      defaultMode: 0444
      items:                    # 可选：只挂指定的 key，并重命名
        - key: config.yaml
          path: app/config.yaml    # 相对于 mountPath
containers:
  - volumeMounts:
      - name: config
        mountPath: /etc/app
        readOnly: true
```

不写 `items` 时，**ConfigMap 的每个 key 变成一个文件**：

```
/etc/app/LOG_LEVEL       内容: info
/etc/app/PORT            内容: 8080
/etc/app/config.yaml     内容: server:\n  port: 8080...
```

写了 `items` 后只挂列出的 key。上面的例子挂载结果是 `/etc/app/app/config.yaml`。

**挂载会覆盖目录**：如果 `mountPath` 是 `/etc/nginx`，容器镜像里 `/etc/nginx` 下原有的所有文件都会**看不见**（被挂载点遮住）。这是高频故障。

### 方式 ④：subPath 挂载单个文件（⚠️ 有重大陷阱）

想在已有目录里加一个文件而不覆盖整个目录：

```yaml
volumeMounts:
  - name: config
    mountPath: /etc/nginx/conf.d/default.conf
    subPath: nginx.conf         # 只挂这一个 key，作为一个文件
```

**陷阱：`subPath` 挂载的文件不会自动更新！** ConfigMap 改了，这个文件永远是旧的，只有重建 Pod 才更新。原因和第 4 章 bind mount 单文件的坑一样——绑的是具体 inode。

**替代方案**：挂到独立目录，然后在应用里指定路径；或用 `initContainer` 拷贝；或干脆接受"配置变更要重建 Pod"（推荐，见 §5）。

---

## 4. Secret

### 4.1 创建

```bash
# 通用 Secret
kubectl create secret generic db-credentials \
  --from-literal=username=app \
  --from-literal=password='S3cr3t!'

# 从文件
kubectl create secret generic tls-key --from-file=./server.key

# TLS 类型（Ingress/Gateway 用）
kubectl create secret tls hello-tls --cert=./tls.crt --key=./tls.key

# 镜像仓库凭据
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io \
  --docker-username=myuser \
  --docker-password=ghp_xxx
```

声明式：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:              # ⭐ 用 stringData，K8s 自动做 base64（可读性好）
  username: app
  password: "S3cr3t!"
data:                    # 如果用 data，值必须是你自己 base64 过的
  token: dG9rZW4tdmFsdWU=
```

**常见 Secret 类型**：

| type | 用途 | 必需的 key |
|---|---|---|
| `Opaque` | 通用（默认） | 任意 |
| `kubernetes.io/tls` | TLS 证书 | `tls.crt`、`tls.key` |
| `kubernetes.io/dockerconfigjson` | 镜像仓库凭据 | `.dockerconfigjson` |
| `kubernetes.io/service-account-token` | SA token（现在很少手工建） | — |
| `kubernetes.io/basic-auth` | 用户名密码 | `username`、`password` |
| `kubernetes.io/ssh-auth` | SSH 私钥 | `ssh-privatekey` |

### 4.2 消费方式与 ConfigMap 完全一致

```yaml
# 环境变量
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef: {name: db-credentials, key: password}

# 批量
envFrom:
  - secretRef: {name: db-credentials}

# 挂载为文件（推荐！）
volumes:
  - name: creds
    secret:
      secretName: db-credentials
      defaultMode: 0400          # 只有属主可读
volumeMounts:
  - name: creds
    mountPath: /etc/secrets
    readOnly: true
```

**为什么密钥推荐挂文件而不是环境变量**（第 4 章提过，这里给完整理由）：

| 环境变量 | 文件挂载 |
|---|---|
| 会出现在 `/proc/<pid>/environ`（同 Pod 其他容器、有 hostPID 的进程可读） | 只在 tmpfs，权限可控 |
| 会被子进程继承（可能泄漏给第三方 CLI） | 不继承 |
| 崩溃时可能进 core dump | 不会 |
| 很多 APM/日志 SDK 默认上报环境变量 | 不会 |
| **无法轮转**（改了要重启） | **可以热更新**（见 §5） |
| `kubectl describe pod` 会显示引用关系 | 同样显示引用，但更容易做 RBAC 隔离 |

### 4.3 查看与解码

```bash
kubectl get secret db-credentials -o jsonpath='{.data.password}' | base64 -d
kubectl get secret db-credentials -o go-template='{{range $k,$v := .data}}{{$k}}={{$v|base64decode}}{{"\n"}}{{end}}'
```

---

## 5. 热更新：真相与最佳实践

这是本章最重要的一节。**很多人以为改了 ConfigMap 应用就会自动生效——这是错的。**

### 5.1 三种消费方式的更新行为

| 方式 | ConfigMap 改变后 |
|---|---|
| **环境变量**（`env` / `envFrom`） | ❌ **永不更新**。环境变量在进程启动时确定，Linux 层面就无法改变 |
| **volume 挂载**（不带 subPath） | ✅ 文件内容会更新，但有延迟（kubelet 同步周期，默认 ~1 分钟 + kubelet 缓存 TTL） |
| **volume 挂载 + subPath** | ❌ **永不更新** |

### 5.2 volume 更新的原子性

kubelet 用符号链接实现原子更新：

```bash
kubectl exec hello -- ls -la /etc/app/
# config.yaml -> ..data/config.yaml
# ..data -> ..2026_07_29_10_30_00.123456789      ← 时间戳目录
```

更新时 kubelet 创建一个新的时间戳目录，写入新内容，然后**原子地**把 `..data` 符号链接指过去。所以你**不会**读到写了一半的文件。

### 5.3 但是——文件变了，你的程序知道吗？

不知道。除非你的程序主动监听文件变化：

```go
import "github.com/fsnotify/fsnotify"

func watchConfig(path string, onChange func()) error {
    w, err := fsnotify.NewWatcher()
    if err != nil { return err }
    // ⚠️ 关键：监听目录而不是文件！
    // 因为 kubelet 是"换符号链接"，直接 watch 文件收不到事件
    if err := w.Add(filepath.Dir(path)); err != nil { return err }

    go func() {
        defer w.Close()
        for {
            select {
            case ev, ok := <-w.Events:
                if !ok { return }
                // ConfigMap 更新表现为 ..data 链接的 Create/Rename
                if filepath.Base(ev.Name) == "..data" {
                    onChange()
                }
            case err, ok := <-w.Errors:
                if !ok { return }
                slog.Error("config watcher error", "err", err)
            }
        }
    }()
    return nil
}
```

`spf13/viper` 的 `WatchConfig()` 也能用，但同样要注意符号链接问题。

**哪些配置适合热更新？**
- ✅ 日志级别、功能开关、限流阈值、超时时间
- ❌ 监听端口、数据库连接串、TLS 证书路径（这些改了必须重启才安全）

### 5.4 推荐做法：配置变更 = 滚动重启

**对绝大多数服务，热加载不值得那份复杂度。** 更简单、更符合不可变基础设施的做法是：**ConfigMap 变了就滚动更新 Pod**。

实现方式：把 ConfigMap 内容的哈希写进 Pod 模板的 annotation。内容变 → 哈希变 → Pod 模板变 → Deployment 触发滚动更新。

Helm 里的标准写法（第 15 章）：

```yaml
spec:
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
        checksum/secret: {{ include (print $.Template.BasePath "/secret.yaml") . | sha256sum }}
```

Kustomize 里更省事——`configMapGenerator` 自动给 ConfigMap 名字加内容哈希后缀（第 16 章）：

```yaml
configMapGenerator:
  - name: hello-config
    literals: [LOG_LEVEL=debug]
# 生成 hello-config-7t2gk8m9bf，内容变则名字变 → 引用它的 Deployment 自动更新
```

手工触发：

```bash
kubectl rollout restart deployment/hello
```

或者用工具自动化：[Reloader](https://github.com/stakater/Reloader)（给 Deployment 打个 annotation，它 watch 关联的 ConfigMap/Secret，变了就自动 `rollout restart`）。

### 5.5 immutable ConfigMap/Secret（性能优化）

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hello-config-v3
immutable: true       # 创建后不可修改，只能删除重建
data: {...}
```

好处：
- kubelet 不再需要周期性 watch 它 → **大集群里显著降低 API Server 负载**
- 语义上强制了"配置版本化"（改配置 = 创建新的 ConfigMap + 更新引用）

大规模集群（几千个 Pod）推荐配合"带版本后缀的 ConfigMap 名"使用。

---

## 6. Downward API：拿到自己的元数据

让容器知道"我是谁、我在哪、我有多少资源"。

### 6.1 环境变量方式

```yaml
env:
  # 通过 fieldRef 拿 Pod 字段
  - name: POD_NAME
    valueFrom: {fieldRef: {fieldPath: metadata.name}}
  - name: POD_NAMESPACE
    valueFrom: {fieldRef: {fieldPath: metadata.namespace}}
  - name: POD_UID
    valueFrom: {fieldRef: {fieldPath: metadata.uid}}
  - name: POD_IP
    valueFrom: {fieldRef: {fieldPath: status.podIP}}
  - name: NODE_NAME
    valueFrom: {fieldRef: {fieldPath: spec.nodeName}}
  - name: HOST_IP
    valueFrom: {fieldRef: {fieldPath: status.hostIP}}
  - name: SERVICE_ACCOUNT
    valueFrom: {fieldRef: {fieldPath: spec.serviceAccountName}}
  - name: APP_VERSION
    valueFrom: {fieldRef: {fieldPath: metadata.labels['app.kubernetes.io/version']}}

  # 通过 resourceFieldRef 拿资源配置
  - name: CPU_LIMIT
    valueFrom:
      resourceFieldRef: {containerName: server, resource: limits.cpu}
  - name: MEM_LIMIT
    valueFrom:
      resourceFieldRef: {containerName: server, resource: limits.memory, divisor: "1Mi"}
```

### 6.2 文件方式（能拿到 labels/annotations 全集，且会更新）

```yaml
volumes:
  - name: podinfo
    downwardAPI:
      items:
        - path: "labels"
          fieldRef: {fieldPath: metadata.labels}
        - path: "annotations"
          fieldRef: {fieldPath: metadata.annotations}
volumeMounts:
  - {name: podinfo, mountPath: /etc/podinfo}
```

⚠️ 环境变量方式**不支持** `metadata.labels` 整体（只能取单个 label）；文件方式可以，且 label 变化时文件会更新。

### 6.3 实际用途

```go
// 日志里带上 Pod 身份，方便定位是哪个副本出的问题
slog.SetDefault(slog.Default().With(
    "pod", os.Getenv("POD_NAME"),
    "node", os.Getenv("NODE_NAME"),
    "version", os.Getenv("APP_VERSION"),
))

// 指标打标签
prometheus.Labels{"pod": os.Getenv("POD_NAME")}

// 分布式系统里做实例标识 / leader 选举
instanceID := os.Getenv("POD_NAME")

// StatefulSet 里从 Pod 名解析序号（hello-0 → 0）
ordinal, _ := strconv.Atoi(podName[strings.LastIndex(podName, "-")+1:])
```

---

## 7. Projected Volume：多来源合并挂载

把 ConfigMap、Secret、Downward API、SA token 挂到同一个目录：

```yaml
volumes:
  - name: all-config
    projected:
      defaultMode: 0400
      sources:
        - configMap:
            name: hello-config
            items: [{key: config.yaml, path: config.yaml}]
        - secret:
            name: db-credentials
            items: [{key: password, path: db-password}]
        - downwardAPI:
            items: [{path: pod-name, fieldRef: {fieldPath: metadata.name}}]
        - serviceAccountToken:
            path: token
            expirationSeconds: 3600      # 短期令牌，自动轮转
            audience: my-api             # 限定受众，防止令牌被滥用
```

**`serviceAccountToken` 投影是现代 K8s 的重要安全改进**：以前 SA token 是永不过期的 Secret，泄漏就完蛋；现在是短期（默认 1 小时）自动轮转的投影令牌，且绑定受众。第 14 章详解。

---

## 8. 密钥的真正管理方式（生产必读）

前面讲的 Secret 有个致命问题：**它不能提交到 Git**（GitOps 的前提是所有东西在 Git 里）。

### 8.1 方案对比

| 方案 | 原理 | 优点 | 缺点 |
|---|---|---|---|
| **明文 Secret 提交 Git** | — | 简单 | ❌ 绝对不行 |
| **手工 `kubectl create secret`** | 带外创建 | 简单 | 无审计、无版本、难以复制到新集群、易遗忘 |
| **Sealed Secrets** | 用集群公钥加密，密文可提交 Git，控制器在集群内解密 | 简单、纯 GitOps | 密钥与集群绑定（换集群要重新加密）、不支持轮转 |
| **External Secrets Operator (ESO)** ⭐ | 定义 `ExternalSecret` CR，控制器从 Vault/AWS SM/GCP SM 拉取并生成 Secret | 密钥集中管理、支持轮转、审计完善、多集群友好 | 需要外部密钥系统 |
| **Vault Agent Injector** | sidecar 直接把密钥写进 Pod 的内存卷，不经过 K8s Secret | 密钥不落 etcd | 侵入 Pod 定义、运维复杂 |
| **Secrets Store CSI Driver** | 用 CSI 卷从外部系统挂载密钥 | 标准化、不落 etcd | 只能挂文件 |
| **SOPS + age/KMS** | 加密后的 YAML 提交 Git，用 helm-secrets / Argo CD 插件解密 | 灵活、支持部分字段加密 | 解密密钥的分发仍需解决 |

### 8.2 推荐：External Secrets Operator

```yaml
# 定义密钥来源（一次性）
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata: {name: vault-backend}
spec:
  provider:
    vault:
      server: "https://vault.internal:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "hello-app"        # 用 Pod 的 SA token 认证，无需静态凭据
---
# 声明"我要哪些密钥"（这个文件可以安全地提交 Git）
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata: {name: db-credentials}
spec:
  refreshInterval: 1h              # 自动轮转
  secretStoreRef: {name: vault-backend, kind: SecretStore}
  target:
    name: db-credentials           # 生成的 K8s Secret 名
    creationPolicy: Owner
  data:
    - secretKey: password          # 生成的 Secret 里的 key
      remoteRef:
        key: database/prod         # Vault 里的路径
        property: password
```

Pod 照常引用 `db-credentials` 这个 Secret，完全无感知。

### 8.3 etcd 静态加密（必做）

不开启的话，任何能读 etcd 备份文件的人都能拿到所有密钥。

```yaml
# /etc/kubernetes/enc/encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources: ["secrets", "configmaps"]
    providers:
      - aescbc:              # 或 kms（推荐，密钥由外部 KMS 管理）
          keys:
            - name: key1
              secret: <32 字节 base64>
      - identity: {}         # 兜底：允许读取未加密的旧数据
```

apiserver 加 `--encryption-provider-config=...`。已存在的 Secret 需要重写一遍才会被加密：

```bash
kubectl get secrets -A -o json | kubectl replace -f -
```

托管集群（EKS/GKE/AKS）通常在控制台一键开启 KMS 加密。

### 8.4 密钥卫生检查表

- [ ] etcd 静态加密已开启（最好是 KMS provider）
- [ ] Secret 的 RBAC 严格限制（**注意：能创建 Pod 的人就能读到该 namespace 的任何 Secret**——挂进去打印出来即可。所以 namespace 隔离很重要）
- [ ] `automountServiceAccountToken: false`（不需要访问 API 的 Pod）
- [ ] 密钥挂文件而不是环境变量
- [ ] 有轮转机制（ESO 的 `refreshInterval`）
- [ ] Git 里有防泄漏扫描（gitleaks / trufflehog / GitHub secret scanning）
- [ ] 审计日志记录 Secret 的读取
- [ ] CI 的日志里不打印密钥（Jenkins 的 `maskPasswords`，第 17 章）

---

## 9. 动手实验

### 实验 1：三种消费方式对比

```bash
kubectl create configmap demo-config \
  --from-literal=LOG_LEVEL=debug \
  --from-literal=GREETING="from configmap"

cat > /tmp/cm-demo.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: cm-demo}
spec:
  restartPolicy: Never
  containers:
    - name: c
      image: busybox:1.37
      command: ['sh','-c','echo "--- env ---"; env | grep -E "LOG_LEVEL|GREETING|CM_"; echo "--- files ---"; ls -la /etc/config/; cat /etc/config/LOG_LEVEL; echo; sleep 3600']
      env:
        - name: CM_SINGLE
          valueFrom: {configMapKeyRef: {name: demo-config, key: LOG_LEVEL}}
      envFrom:
        - configMapRef: {name: demo-config}
      volumeMounts:
        - {name: cfg, mountPath: /etc/config}
  volumes:
    - name: cfg
      configMap: {name: demo-config}
EOF

kubectl apply -f /tmp/cm-demo.yaml
sleep 5
kubectl logs cm-demo
kubectl exec cm-demo -- ls -la /etc/config/    # 看到符号链接结构
```

### 实验 2：验证热更新行为

```bash
# 改 ConfigMap
kubectl create configmap demo-config \
  --from-literal=LOG_LEVEL=trace \
  --from-literal=GREETING="UPDATED" \
  --dry-run=client -o yaml | kubectl apply -f -

# 环境变量：永远不变
kubectl exec cm-demo -- sh -c 'echo "env: $LOG_LEVEL"'
# env: debug     ← 还是旧值 ❌

# 文件：等 1~2 分钟后会变
for i in $(seq 12); do
  echo -n "$(date +%T) file: "; kubectl exec cm-demo -- cat /etc/config/LOG_LEVEL; echo
  sleep 10
done
# 大约 1 分钟后变成 trace ✅

kubectl delete pod cm-demo
```

**这个实验必须亲手做一遍**，它会让你永远记住这个区别。

### 实验 3：subPath 不更新

```bash
cat > /tmp/subpath-demo.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: subpath-demo}
spec:
  restartPolicy: Never
  containers:
    - name: c
      image: busybox:1.37
      command: ['sh','-c','while true; do echo "$(date +%T) $(cat /app/level)"; sleep 10; done']
      volumeMounts:
        - {name: cfg, mountPath: /app/level, subPath: LOG_LEVEL}
  volumes:
    - {name: cfg, configMap: {name: demo-config}}
EOF
kubectl apply -f /tmp/subpath-demo.yaml
sleep 5
kubectl create configmap demo-config --from-literal=LOG_LEVEL=CHANGED_AGAIN \
  --dry-run=client -o yaml | kubectl apply -f -
sleep 120
kubectl logs subpath-demo --tail=3      # 一直是旧值 ❌
kubectl delete pod subpath-demo
```

### 实验 4：Secret 挂载是 tmpfs

```bash
kubectl create secret generic demo-secret --from-literal=password=s3cr3t
kubectl run sec-demo --image=busybox:1.37 --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"sec-demo","image":"busybox:1.37",
"command":["sh","-c","mount | grep secret; cat /etc/sec/password; echo; sleep 3600"],
"volumeMounts":[{"name":"s","mountPath":"/etc/sec"}]}],
"volumes":[{"name":"s","secret":{"secretName":"demo-secret"}}]}}'
sleep 5
kubectl logs sec-demo
# tmpfs on /etc/sec type tmpfs (ro,relatime,...)     ← 内存文件系统，不落盘
kubectl delete pod sec-demo
```

### 实验 5：Downward API

```bash
kubectl run dapi --image=busybox:1.37 --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"dapi","image":"busybox:1.37",
"command":["sh","-c","env | grep -E \"POD_|NODE_|MEM_\"; sleep 3600"],
"env":[
 {"name":"POD_NAME","valueFrom":{"fieldRef":{"fieldPath":"metadata.name"}}},
 {"name":"POD_IP","valueFrom":{"fieldRef":{"fieldPath":"status.podIP"}}},
 {"name":"NODE_NAME","valueFrom":{"fieldRef":{"fieldPath":"spec.nodeName"}}},
 {"name":"MEM_LIMIT","valueFrom":{"resourceFieldRef":{"resource":"limits.memory","divisor":"1Mi"}}}],
"resources":{"limits":{"memory":"256Mi"}}}]}}'
sleep 5
kubectl logs dapi
kubectl delete pod dapi
```

### 实验 6：配置变更触发滚动更新

```bash
kubectl create deployment cfgtest --image=nginx:alpine
kubectl set env deployment/cfgtest --from=configmap/demo-config
kubectl rollout status deployment/cfgtest

# 改 ConfigMap —— Deployment 不会有任何反应
kubectl create configmap demo-config --from-literal=LOG_LEVEL=X \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl get rs -l app=cfgtest        # 还是同一个 ReplicaSet，没有滚动更新

# 手工触发
kubectl rollout restart deployment/cfgtest
kubectl rollout status deployment/cfgtest
kubectl get rs -l app=cfgtest        # 新的 ReplicaSet

kubectl delete deploy cfgtest
kubectl delete cm demo-config; kubectl delete secret demo-secret
```

---

## 10. 本章检查清单

- [ ] Secret 和 ConfigMap 的真正区别是什么？base64 算加密吗？
- [ ] 列出四种消费方式，各自的适用场景
- [ ] 改了 ConfigMap，三种消费方式分别会不会生效？为什么？
- [ ] kubelet 用什么机制保证配置文件更新的原子性？这对 fsnotify 有什么影响？
- [ ] subPath 挂载的陷阱是什么？有哪些替代方案？
- [ ] 为什么密钥推荐挂文件而不是环境变量？（说出 4 个理由）
- [ ] 生产上"改配置"的推荐流程是什么？
- [ ] `immutable: true` 的好处是什么？
- [ ] Downward API 能拿到哪些信息？举 3 个实际用途
- [ ] 密钥怎样才能安全地进 Git？（至少说出 2 种方案）
- [ ] 为什么说"能创建 Pod 的人就能读到该 namespace 的所有 Secret"？
- [ ] 完成实验 2 和实验 3（必做）

---

## 11. 延伸阅读

- [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Secret](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Downward API](https://kubernetes.io/docs/concepts/workloads/pods/downward-api/)
- [静态加密配置](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
- [External Secrets Operator](https://external-secrets.io/)
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)

---

下一章：[09 - 工作负载控制器：无状态与有状态](./09-workloads.md)
