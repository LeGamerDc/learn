# 15 - Helm：Kubernetes 的包管理器

> 本章目标：解决"同一套服务要部署到 5 个环境，难道维护 5 份 YAML？"的问题。
> 你会学会用 Helm 4 把第 9 章的清单变成一个可参数化、可版本化、可回滚的 Chart。
> 预计用时：3 小时（含实验）。

---

## 1. 问题背景

假设你的服务在 4 个环境跑：

| | dev | staging | prod-cn | prod-us |
|---|---|---|---|---|
| 副本数 | 1 | 2 | 20 | 10 |
| 资源 | 100m/128Mi | 200m/256Mi | 1/2Gi | 1/2Gi |
| 镜像 tag | latest-dev | v1.2.3-rc1 | v1.2.2 | v1.2.2 |
| 域名 | dev.internal | stg.example.com | api.example.cn | api.example.com |
| 数据库 | 本地 postgres | RDS-staging | RDS-cn | RDS-us |
| HPA | 关 | 关 | 开 | 开 |
| 日志级别 | debug | info | warn | warn |

**朴素做法**：复制 4 份 YAML 目录。后果：
- 改一个公共字段（比如加个 securityContext）要改 4 遍，改漏一个就是事故
- 4 份文件会渐渐分叉，谁也说不清 prod 和 staging 到底差在哪
- 新增一个环境要复制粘贴 500 行

**这是所有配置管理系统要解决的核心问题：如何表达"90% 相同、10% 不同"。**

两条技术路线：

| 路线 | 代表 | 思路 |
|---|---|---|
| **模板化** | **Helm** | 写模板 + 变量，渲染出最终 YAML |
| **叠加/打补丁** | **Kustomize** | 写完整的 base YAML + overlay 补丁（第 16 章） |

Helm 除了模板化，还提供了**包管理**能力：版本化、依赖、仓库分发、release 生命周期管理。

---

## 2. Helm 4（2026 年的现状）

- **Helm 4.0** 于 2025-11 发布，是 6 年来第一个大版本。当前稳定版 **4.2.x**
- **Helm 3 生命周期**：最后一个功能版本 2026-09，安全补丁到 2027-02。**新项目直接上 Helm 4**

### Helm 4 相比 Helm 3 的主要变化

| 变化 | 说明 |
|---|---|
| **默认 Server-Side Apply** | 新安装的 release 默认用 SSA（第 6 章）。已有 Helm 3 release 升级时会沿用客户端 apply，不会突然改变行为 |
| **基于 kstatus 的等待** | `--wait` 用 kstatus 判断资源就绪，更准确。⚠️ **需要额外的 RBAC `watch` 权限** |
| **插件系统重构** | 支持 WebAssembly 插件；post-renderer 变成插件（不能再直接传可执行文件路径） |
| **CLI 标志更名** | `--atomic` → `--rollback-on-failure`；`--force` → `--force-replace`（旧名暂时可用但有弃用警告） |
| **registry login 语法** | 4.1 起不接受 `https://` 前缀，只写域名 |
| **本地内容寻址缓存** | 依赖拉取更快 |
| **可复现的 chart 打包** | 同样输入产出字节一致的 `.tgz` |
| **slog 日志** | SDK 使用结构化日志 |
| **Chart apiVersion** | v2 chart 继续正常工作；v3 是实验性的新格式 |

**迁移要点**：Helm 3 和 Helm 4 可以同机共存，v2 chart 兼容。改脚本里的 `--atomic`/`--force`，检查 post-renderer 用法，给 CI 的 SA 加 `watch` 权限。

```bash
helm version      # v4.2.x
```

---

## 3. 核心概念

| 概念 | 含义 | 类比 |
|---|---|---|
| **Chart** | 一个包（模板 + 默认值 + 元数据） | Go module / npm package |
| **Values** | 参数（可分层覆盖） | 配置文件 |
| **Release** | Chart 在集群里的一次**具名安装实例** | 一个运行中的进程 |
| **Revision** | Release 的版本号，每次 upgrade 递增 | git commit |
| **Repository** | Chart 的分发仓库（HTTP 或 OCI） | Docker Registry / Go proxy |

**关键理解**：同一个 Chart 可以在同一个集群里安装多次，形成多个 Release：

```bash
helm install hello-dev  ./hello -f values-dev.yaml  -n dev
helm install hello-prod ./hello -f values-prod.yaml -n prod
```

Helm 把每个 Release 的完整状态（渲染后的清单 + values + 元数据）以 **Secret** 的形式存在对应的 namespace 里：

```bash
kubectl get secret -n dev -l owner=helm
# sh.helm.release.v1.hello-dev.v1
# sh.helm.release.v1.hello-dev.v2      ← 每个 revision 一个
```

**所以：Helm 是客户端工具，集群里没有 Helm 服务端**（Helm 2 的 Tiller 已被废弃）。你的权限就是 kubeconfig 的权限。

---

## 4. Chart 结构

```bash
helm create hello
tree hello
```

```
hello/
├── Chart.yaml           # 元数据：名字、版本、依赖
├── values.yaml          # 默认参数（文档作用很重要）
├── values.schema.json   # ⭐ JSON Schema，校验 values（强烈建议写）
├── charts/              # 子 chart（依赖）
├── crds/                # CRD（先于其他资源安装，且不会被升级/删除）
├── templates/
│   ├── NOTES.txt        # 安装后打印的提示
│   ├── _helpers.tpl     # 可复用的模板片段
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── serviceaccount.yaml
│   ├── hpa.yaml
│   ├── ingress.yaml
│   └── tests/
│       └── test-connection.yaml   # helm test 用
└── .helmignore
```

### 4.1 Chart.yaml

```yaml
apiVersion: v2                 # chart 格式版本（v2 = Helm 3/4 通用）
name: hello
description: A Go HTTP service
type: application              # application | library
version: 0.1.0                 # ⭐ Chart 自身的版本（改模板就要改它）
appVersion: "1.2.3"            # ⭐ 应用版本（默认镜像 tag，仅信息性）
kubeVersion: ">=1.30.0-0"      # 要求的 K8s 版本
keywords: [go, api]
home: https://github.com/yourorg/hello
maintainers:
  - {name: Backend Team, email: backend@example.com}

dependencies:                  # 依赖的子 chart
  - name: postgresql
    version: "16.x.x"
    repository: https://charts.bitnami.com/bitnami
    condition: postgresql.enabled     # ⭐ 按 values 开关决定是否安装
  - name: redis
    version: "20.x.x"
    repository: oci://registry-1.docker.io/bitnamicharts
    condition: redis.enabled
    alias: cache
```

⚠️ **区分两个版本号**：
- `version`：Chart 的版本。**改了模板就要 bump**（否则 Argo CD 和 helm repo 认不出变化）
- `appVersion`：里面装的应用版本

### 4.2 values.yaml（设计得好坏决定 Chart 好不好用）

```yaml
# values.yaml —— 默认值同时是文档，每个字段都要有注释
replicaCount: 2

image:
  repository: ghcr.io/yourorg/hello
  tag: ""                        # 留空则用 Chart.appVersion
  pullPolicy: IfNotPresent
imagePullSecrets: []

nameOverride: ""
fullnameOverride: ""

serviceAccount:
  create: true
  name: ""
  annotations: {}
  automount: false

podAnnotations: {}
podLabels: {}

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 65532
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]

service:
  type: ClusterIP
  port: 80
  metricsPort: 9090

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    memory: 512Mi

autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70

pdb:
  enabled: true
  maxUnavailable: 1

# 应用配置：会渲染成 ConfigMap
config:
  logLevel: info
  greeting: "hello"
  timeout: 5s

# 敏感配置：生产应改用 External Secrets（第 8 章）
secrets:
  dbPassword: ""

env: []                          # 额外环境变量
extraVolumes: []
extraVolumeMounts: []

nodeSelector: {}
tolerations: []
affinity: {}
topologySpreadConstraints: []

serviceMonitor:
  enabled: false
  interval: 30s

postgresql:
  enabled: false                 # dev 用内置 postgres，生产用外部 RDS
```

**values 设计原则**：
1. **默认值要能直接跑起来**（`helm install` 不传任何参数就能工作）
2. **默认值要安全**（非 root、有资源限制、副本数 ≥ 2）
3. 层级不要太深（超过 3 层就难用了）
4. 布尔开关用 `xxx.enabled` 的惯例
5. 提供 `extraXxx` 逃生舱（让用户能加你没预料到的东西）
6. **写 `values.schema.json`**——它能在渲染前就报出拼写错误

### 4.3 模板语法

Helm 用 Go 的 `text/template` + [Sprig 函数库](http://masterminds.github.io/sprig/)。**你有 Go 背景，这部分几乎零成本**。

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "hello.fullname" . }}
  labels:
    {{- include "hello.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}     {{/* ⭐ 开了 HPA 就不要写 replicas */}}
  {{- end }}
  selector:
    matchLabels:
      {{- include "hello.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      annotations:
        {{- /* ⭐ 配置变了自动触发滚动更新（第 8 章的技巧） */}}
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
        {{- with .Values.podAnnotations }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
      labels:
        {{- include "hello.labels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "hello.serviceAccountName" . }}
      automountServiceAccountToken: {{ .Values.serviceAccount.automount }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      terminationGracePeriodSeconds: 45
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          ports:
            - {name: http, containerPort: 8080}
            - {name: metrics, containerPort: 9090}
          env:
            - name: POD_NAME
              valueFrom: {fieldRef: {fieldPath: metadata.name}}
            {{- range $k, $v := .Values.config }}
            - name: {{ $k | snakecase | upper }}
              value: {{ $v | quote }}          {{/* ⭐ 必须 quote，否则 true/123 会变成非字符串 */}}
            {{- end }}
            {{- with .Values.env }}
            {{- toYaml . | nindent 12 }}
            {{- end }}
          {{- if .Values.secrets.dbPassword }}
          envFrom:
            - secretRef: {name: {{ include "hello.fullname" . }}-secret}
          {{- end }}
          readinessProbe:
            httpGet: {path: /readyz, port: http}
            periodSeconds: 5
          livenessProbe:
            httpGet: {path: /healthz, port: http}
            periodSeconds: 10
          lifecycle:
            preStop: {sleep: {seconds: 5}}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          volumeMounts:
            - {name: tmp, mountPath: /tmp}
            {{- with .Values.extraVolumeMounts }}
            {{- toYaml . | nindent 12 }}
            {{- end }}
      volumes:
        - name: tmp
          emptyDir: {medium: Memory, sizeLimit: 64Mi}
        {{- with .Values.extraVolumes }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.topologySpreadConstraints }}
      topologySpreadConstraints:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

### 4.4 内置对象

| 对象 | 内容 |
|---|---|
| `.Values` | values.yaml + `-f` + `--set` 合并后的结果 |
| `.Chart` | Chart.yaml 的内容（`.Chart.Name`、`.Chart.Version`、`.Chart.AppVersion`） |
| `.Release` | `.Name`、`.Namespace`、`.Revision`、`.IsInstall`、`.IsUpgrade`、`.Service` |
| `.Capabilities` | `.KubeVersion`、`.APIVersions.Has "batch/v1"`（做版本兼容判断） |
| `.Files` | 读取 chart 里的非模板文件：`.Files.Get "config/app.yaml"`、`.Files.Glob` |
| `.Template` | `.Name`（当前模板路径）、`.BasePath` |

### 4.5 `_helpers.tpl`

```gotemplate
{{/* 名字（可被 nameOverride 覆盖，且截断到 63 字符——K8s 标签的限制） */}}
{{- define "hello.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "hello.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/* 标准标签（第 6 章） */}}
{{- define "hello.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "hello.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* ⭐ selectorLabels 必须稳定！它对应 Deployment.spec.selector，创建后不可变。
     绝不能把 version 之类会变的东西放进来 */}}
{{- define "hello.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hello.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "hello.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "hello.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
```

### 4.6 模板语法要点（踩坑集中区）

**① 空白控制**

```gotemplate
{{ .Values.x }}      普通
{{- .Values.x }}     去掉左边的空白（含换行）
{{ .Values.x -}}     去掉右边的空白
{{- .Values.x -}}    两边都去
```

**YAML 对缩进极其敏感**，`{{-` 用错就是渲染失败。永远用 `helm template` 检查输出。

**② `indent` vs `nindent`**

```gotemplate
{{ toYaml .Values.resources | indent 12 }}     # 每行加 12 空格（第一行也加，通常不是你要的）
{{- toYaml .Values.resources | nindent 12 }}   # ⭐ 先换行再加 12 空格（推荐）
```

**③ `with` 改变作用域**

```gotemplate
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}      {{/* 这里的 . 是 .Values.nodeSelector，不是根！ */}}
{{- end }}

{{- with .Values.x }}
  {{ $.Release.Name }}             {{/* ⭐ 想访问根对象要用 $ */}}
{{- end }}
```

**④ 类型陷阱**

```gotemplate
port: {{ .Values.port }}                 # 8080（数字）✅
version: {{ .Values.version }}           # 1.20 → YAML 解析成浮点数！❌
version: {{ .Values.version | quote }}   # "1.20" ✅

enabled: {{ .Values.enabled }}           # true（布尔）
value: {{ .Values.enabled | quote }}     # "true"（env 的 value 必须是字符串）✅
```

⭐ **规则：环境变量的 value、annotation 的值、任何"看起来像数字/布尔但其实是字符串"的地方，一律 `| quote`。**

**⑤ 常用 Sprig 函数**

```gotemplate
{{ .Values.x | default "fallback" }}
{{ .Values.x | quote }} {{ .Values.x | toYaml }} {{ .Values.x | toJson }}
{{ .Values.name | trunc 63 | trimSuffix "-" }}
{{ .Values.name | upper | lower | title | snakecase | camelcase }}
{{ list "a" "b" | join "," }}
{{ .Values.s | b64enc }} {{ .Values.s | b64dec }}
{{ now | date "2006-01-02" }}
{{ randAlphaNum 32 }}                    {{/* ⚠️ 每次渲染都变！见下 */}}
{{ required "image.repository 必须设置" .Values.image.repository }}
{{ fail "不支持的配置组合" }}
{{ .Values.dict | dig "a" "b" "default" }}
{{ include "other.template" . }}         {{/* ⭐ 用 include 不用 template，因为能接管道 */}}
{{ tpl .Values.someTemplateString . }}   {{/* 把 values 里的字符串当模板渲染 */}}
{{ lookup "v1" "Secret" .Release.Namespace "my-secret" }}   {{/* 查询集群里已有对象 */}}
```

⚠️ **`randAlphaNum` 的陷阱**：每次 `helm upgrade` 都会生成新值 → 密码每次升级都变 → 应用连不上数据库。正确写法是配合 `lookup` 保留已有值：

```gotemplate
{{- $existing := lookup "v1" "Secret" .Release.Namespace (include "hello.fullname" .) }}
{{- $pass := "" }}
{{- if $existing }}
  {{- $pass = index $existing.data "password" | b64dec }}
{{- else }}
  {{- $pass = randAlphaNum 32 }}
{{- end }}
```

（更好的做法：别用 Helm 生成密码，用 External Secrets。）

---

## 5. Values 的优先级

从低到高（后面覆盖前面）：

```
① 子 chart 的 values.yaml
② 父 chart 的 values.yaml
③ -f values-a.yaml
④ -f values-b.yaml          （多个 -f 按顺序，后面覆盖前面）
⑤ --set key=value
⑥ --set-string / --set-file / --set-json
```

```bash
helm install hello ./hello \
  -f values-prod.yaml \
  -f values-prod-cn.yaml \
  --set image.tag=v1.2.3 \
  --set-string config.version=1.20 \
  --set-file config.cert=./tls.crt \
  --set-json 'resources={"requests":{"cpu":"200m"}}'
```

**合并规则的重要细节**：
- **map 是深度合并**（递归合并同名 key）
- **数组是整体替换**（不是合并！）——这经常出乎意料

```yaml
# values.yaml
env:
  - {name: A, value: "1"}
  - {name: B, value: "2"}
# values-prod.yaml
env:
  - {name: C, value: "3"}
# 结果：只有 C！A 和 B 没了
```

**想"删除"一个默认值**，设为 `null`：

```bash
helm upgrade hello ./hello --set resources.limits.cpu=null
```

```bash
# 看最终生效的 values
helm get values hello              # 用户提供的
helm get values hello --all        # 合并后的全部
```

---

## 6. 常用命令

```bash
# ============ 开发 ============
helm create mychart
helm lint ./hello                          # 静态检查
helm template hello ./hello -f values-prod.yaml    # ⭐ 本地渲染，不连集群
helm template hello ./hello --debug --set x=y | kubectl apply --dry-run=server -f -
helm install hello ./hello --dry-run --debug       # 连集群做服务端校验

# ============ 安装与升级 ============
helm install hello ./hello -n prod --create-namespace -f values-prod.yaml
helm upgrade hello ./hello -n prod -f values-prod.yaml
helm upgrade --install hello ./hello -n prod -f values-prod.yaml   # ⭐ 幂等，CI 里用这个

# 生产推荐的完整参数
helm upgrade --install hello ./hello \
  -n prod --create-namespace \
  -f values-prod.yaml \
  --set image.tag=$GIT_SHA \
  --wait --timeout 10m \          # 等所有资源就绪（Helm 4 用 kstatus，需要 watch 权限）
  --rollback-on-failure \         # ⭐ Helm 4：失败自动回滚（原 --atomic）
  --history-max 20

# ============ 查看 ============
helm list -n prod
helm list -A                               # 所有 namespace
helm list -A --pending --failed
helm status hello -n prod
helm get manifest hello -n prod            # ⭐ 当前部署的完整 YAML
helm get values hello -n prod --all
helm get notes hello -n prod
helm get hooks hello -n prod

# ============ 回滚 ============
helm history hello -n prod
helm rollback hello -n prod                # 回上一版
helm rollback hello 3 -n prod --wait       # 回到 revision 3

# ============ 卸载 ============
helm uninstall hello -n prod
helm uninstall hello -n prod --keep-history    # 保留历史，可以再 rollback

# ============ 仓库 ============
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm search repo postgres
helm search hub prometheus                 # 搜 Artifact Hub
helm show values bitnami/postgresql        # ⭐ 看一个 chart 有哪些参数
helm show readme bitnami/postgresql
helm pull bitnami/postgresql --untar        # 下载下来研究

# ============ OCI 仓库（现代方式）============
helm registry login ghcr.io -u USER        # ⚠️ Helm 4.1+ 不要写 https://
helm package ./hello                        # 产出 hello-0.1.0.tgz
helm push hello-0.1.0.tgz oci://ghcr.io/yourorg/charts
helm install hello oci://ghcr.io/yourorg/charts/hello --version 0.1.0

# ============ 依赖 ============
helm dependency update ./hello             # 下载依赖到 charts/，生成 Chart.lock
helm dependency build ./hello              # 按 Chart.lock 下载（CI 里用这个，可复现）
helm dependency list ./hello

# ============ 测试 ============
helm test hello -n prod                    # 运行 templates/tests/ 里的 Pod
```

### 6.1 `helm diff` 插件（强烈推荐）

```bash
helm plugin install https://github.com/databus23/helm-diff
helm diff upgrade hello ./hello -f values-prod.yaml -n prod
```

**升级前一定要看 diff。** 这个习惯能避免大量事故。

---

## 7. Hooks：生命周期钩子

用于数据库迁移、备份、预检查等：

```yaml
# templates/migrate-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "hello.fullname" . }}-migrate
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-5"                    # 数字小的先执行
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  backoffLimit: 2
  activeDeadlineSeconds: 600
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          command: ["/migrate", "up"]
          envFrom: [{secretRef: {name: {{ include "hello.fullname" . }}-secret}}]
```

**Hook 类型**：`pre-install`、`post-install`、`pre-upgrade`、`post-upgrade`、`pre-delete`、`post-delete`、`pre-rollback`、`post-rollback`、`test`。

**Hook 删除策略**：
- `before-hook-creation`（默认）：创建新 hook 前删掉上次的
- `hook-succeeded`：成功后删除
- `hook-failed`：失败后删除（**不设的话失败的 Job 会留下，方便排查**）

⚠️ **Hook 资源不被 Helm 当作 release 的一部分管理**——`helm uninstall` 不会删它们（除非有删除策略），`helm rollback` 也不管。

⚠️ **数据库迁移放 Hook 的优缺点**：
- ✅ 保证在新版本 Pod 启动前完成
- ❌ 迁移失败时 release 卡住，且回滚不会撤销 schema 变更
- 所以迁移脚本必须**幂等**且**向后兼容**（第 9 章的 expand-contract 模式）

---

## 8. 子 Chart 与依赖

```yaml
# Chart.yaml
dependencies:
  - name: postgresql
    version: "16.x.x"
    repository: https://charts.bitnami.com/bitnami
    condition: postgresql.enabled
```

```yaml
# values.yaml —— 给子 chart 传参
postgresql:
  enabled: true
  auth:
    username: app
    database: app
  primary:
    persistence:
      size: 20Gi

# ⭐ 全局值：所有子 chart 都能访问 .Values.global.*
global:
  imageRegistry: registry.internal
  storageClass: fast-ssd
```

```bash
helm dependency update ./hello    # 下载到 charts/，生成 Chart.lock
```

**实践建议**：
- ✅ 开发/测试环境用子 chart 拉起依赖（一条命令起全套）
- ❌ **生产不要用 Helm 部署数据库**（第 9 章讲过）。生产的 `values-prod.yaml` 里设 `postgresql.enabled: false`，用外部 RDS
- 把 `charts/` 加进 `.gitignore`，用 `Chart.lock` 保证可复现（CI 用 `helm dependency build`）

### Library Chart（复用模板）

多个服务共用一套模板时：

```yaml
# common-lib/Chart.yaml
type: library                # 不能被直接安装，只能被引用
```

各服务的 chart 引用它，只写 values。这是大团队维护几十个微服务的常见做法（也可以考虑直接用统一的"通用 chart" + 每个服务只有 values 文件）。

---

## 9. 生产实践与陷阱

### 9.1 Chart 与应用代码的仓库关系

| 模式 | 说明 |
|---|---|
| **Chart 和代码同仓** | 简单，chart 跟着代码演进。适合单个服务 |
| **Chart 独立仓库** ⭐ | 配置仓与代码仓分离，GitOps 的标准做法（第 18 章） |
| **通用 Chart + 每服务只有 values** ⭐ | 大规模微服务的最优解：一个 chart 管 50 个服务，统一升级安全基线 |

### 9.2 常见陷阱

| 陷阱 | 后果 | 解法 |
|---|---|---|
| **改了 selector labels** | Deployment 的 selector 不可变 → 升级失败 | selectorLabels 里只放稳定字段，绝不放 version |
| **`--set` 里的逗号和点** | 解析错误 | 用 `--set-json` 或 `-f` 文件 |
| **数组被整体替换** | 以为是合并，结果默认值全丢 | 明确知道数组语义；必要时用 `--set-json` |
| **忘了 `quote`** | `version: 1.20` 变成 1.2 | 字符串一律 quote |
| **`randAlphaNum` 每次变** | 密码每次升级都变 | 用 `lookup` 或外部密钥系统 |
| **Chart version 不 bump** | Argo CD/仓库认不出变更 | CI 自动 bump 或用 git sha 做版本 |
| **HPA 和 replicas 打架** | 每次 helm upgrade 把副本数改回去 | HPA 开启时模板里不渲染 `replicas` |
| **release 卡在 pending-upgrade** | 无法再操作 | `helm rollback` 或删掉最新的 release Secret |
| **CRD 升级** | `crds/` 目录里的 CRD **不会被升级和删除** | CRD 用单独的 chart 或用 Operator 管 |
| **Helm 4 的 `--wait` 权限不足** | 升级卡住/报错 | 给 SA 加 `watch` 权限 |

### 9.3 release 卡住的处理

```bash
helm list -A --pending
# STATUS: pending-upgrade

# 方案 1：回滚到上一个成功版本
helm rollback hello -n prod

# 方案 2：删掉那条 pending 的 release 记录
kubectl get secret -n prod -l owner=helm,name=hello --sort-by=.metadata.creationTimestamp
kubectl delete secret -n prod sh.helm.release.v1.hello.v12
```

### 9.4 values.schema.json

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["image"],
  "properties": {
    "replicaCount": {"type": "integer", "minimum": 1, "maximum": 100},
    "image": {
      "type": "object",
      "required": ["repository"],
      "properties": {
        "repository": {"type": "string", "pattern": "^[a-z0-9./-]+$"},
        "tag": {"type": "string"},
        "pullPolicy": {"enum": ["Always", "IfNotPresent", "Never"]}
      }
    },
    "resources": {
      "type": "object",
      "properties": {
        "requests": {
          "type": "object",
          "required": ["cpu", "memory"]
        }
      }
    }
  }
}
```

`helm install/upgrade/lint/template` 都会校验。**拼错一个 key 立刻报错，而不是渲染出一个缺字段的清单**——这个收益非常大。

---

## 10. 动手实验

### 实验 1：把第 9 章的清单改造成 Chart

```bash
mkdir -p ~/lab/charts && cd ~/lab/charts
helm create hello
rm hello/templates/tests/test-connection.yaml    # 先简化
```

按 §4 修改 `Chart.yaml`、`values.yaml`、`templates/deployment.yaml`。然后：

```bash
helm lint ./hello
helm template hello ./hello | head -60
helm template hello ./hello --set replicaCount=5 | grep replicas
```

### 实验 2：多环境 values

```bash
cat > ~/lab/charts/hello/values-dev.yaml <<'EOF'
replicaCount: 1
image: {repository: hello, tag: v0.1.0, pullPolicy: IfNotPresent}
config: {logLevel: debug, greeting: "hello from DEV"}
resources:
  requests: {cpu: 50m, memory: 64Mi}
  limits: {memory: 128Mi}
autoscaling: {enabled: false}
pdb: {enabled: false}
EOF

cat > ~/lab/charts/hello/values-prod.yaml <<'EOF'
replicaCount: 4
image: {repository: hello, tag: v0.1.0, pullPolicy: IfNotPresent}
config: {logLevel: warn, greeting: "hello from PROD"}
resources:
  requests: {cpu: 200m, memory: 256Mi}
  limits: {memory: 1Gi}
autoscaling: {enabled: true, minReplicas: 4, maxReplicas: 20}
pdb: {enabled: true, maxUnavailable: 1}
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        app.kubernetes.io/name: hello
EOF

# ⭐ 对比两个环境渲染出的差异
diff <(helm template hello ./hello -f ./hello/values-dev.yaml) \
     <(helm template hello ./hello -f ./hello/values-prod.yaml) | head -40
```

### 实验 3：安装到两个环境

```bash
helm upgrade --install hello-dev ./hello -n dev --create-namespace \
  -f ./hello/values-dev.yaml --wait --timeout 3m
helm upgrade --install hello-prod ./hello -n prod --create-namespace \
  -f ./hello/values-prod.yaml --wait --timeout 3m

helm list -A
kubectl get all -n dev
kubectl get all -n prod

# ⭐ 同一个 chart，两个 release，配置完全不同
kubectl -n dev  get deploy -o jsonpath='{.items[0].spec.replicas}{"\n"}'
kubectl -n prod get deploy -o jsonpath='{.items[0].spec.replicas}{"\n"}'
```

### 实验 4：升级、diff 与回滚

```bash
helm plugin install https://github.com/databus23/helm-diff 2>/dev/null || true

# 先看 diff
helm diff upgrade hello-prod ./hello -n prod -f ./hello/values-prod.yaml \
  --set config.greeting="v2 greeting"

# 执行升级
helm upgrade hello-prod ./hello -n prod -f ./hello/values-prod.yaml \
  --set config.greeting="v2 greeting" --wait

helm history hello-prod -n prod
# REVISION  STATUS      DESCRIPTION
# 1         superseded  Install complete
# 2         deployed    Upgrade complete

kubectl -n prod get cm -o yaml | grep -i greeting

# 回滚
helm rollback hello-prod 1 -n prod --wait
helm history hello-prod -n prod
kubectl -n prod get cm -o yaml | grep -i greeting     # 回到 v1
```

### 实验 5：⭐ 失败自动回滚

```bash
# 用一个不存在的镜像升级，加上 --rollback-on-failure
helm upgrade hello-prod ./hello -n prod -f ./hello/values-prod.yaml \
  --set image.tag=does-not-exist \
  --wait --timeout 90s --rollback-on-failure

# 会失败，然后自动回滚
helm history hello-prod -n prod
kubectl -n prod get pods       # 旧版本仍在正常运行 ✅
```

### 实验 6：checksum 触发滚动更新

```bash
kubectl -n prod get rs
helm upgrade hello-prod ./hello -n prod -f ./hello/values-prod.yaml \
  --set config.logLevel=info --wait
kubectl -n prod get rs         # ⭐ 新的 ReplicaSet —— ConfigMap 变化触发了滚动更新
```

### 实验 7：Hook

在 `templates/` 下加一个 `hook-job.yaml`（用 §7 的内容，command 改成 `["sh","-c","echo migrating; sleep 5"]`，镜像用 busybox），然后：

```bash
helm upgrade hello-prod ./hello -n prod -f ./hello/values-prod.yaml --wait
kubectl -n prod get jobs
kubectl -n prod logs job/hello-prod-hello-migrate
```

### 实验 8：打包与 OCI 仓库

```bash
helm package ./hello
ls hello-0.1.0.tgz

# 推到本地 registry（第 0 章起的那个）
helm registry login localhost:5001 --insecure 2>/dev/null || true
helm push hello-0.1.0.tgz oci://localhost:5001/charts --plain-http
helm show chart oci://localhost:5001/charts/hello --version 0.1.0 --plain-http
```

### 清理

```bash
helm uninstall hello-dev -n dev
helm uninstall hello-prod -n prod
kubectl delete ns dev prod
```

---

## 11. 本章检查清单

- [ ] Helm 解决什么问题？和 Kustomize 是两条什么路线？
- [ ] Chart、Release、Revision、Repository 分别是什么？
- [ ] Helm 有服务端吗？release 状态存在哪？
- [ ] `Chart.version` 和 `appVersion` 的区别？什么时候必须 bump？
- [ ] values 的优先级顺序？map 和数组的合并规则有什么不同？
- [ ] `indent` 和 `nindent` 的区别？`with` 块里怎么访问根对象？
- [ ] 什么时候必须用 `| quote`？举 3 个例子
- [ ] `selectorLabels` 里为什么绝不能放 version？
- [ ] `checksum/config` 注解的作用和原理？
- [ ] HPA 和 `replicas` 怎么共存？
- [ ] `randAlphaNum` 生成密码的陷阱是什么？
- [ ] Hook 资源会被 `helm uninstall` 删除吗？
- [ ] Helm 4 相比 3 有哪些需要改脚本的地方？
- [ ] release 卡在 `pending-upgrade` 怎么处理？
- [ ] `values.schema.json` 的价值是什么？
- [ ] 完成实验 1~5

---

## 12. 延伸阅读

- [Helm 官方文档](https://helm.sh/docs/)
- [Chart 模板开发指南](https://helm.sh/docs/chart_template_guide/)
- [Chart 最佳实践](https://helm.sh/docs/chart_best_practices/)
- [Sprig 函数库](http://masterminds.github.io/sprig/)
- [Artifact Hub](https://artifacthub.io/)（找现成的 chart）
- [helm-diff](https://github.com/databus23/helm-diff) / [helmfile](https://helmfile.readthedocs.io/)

---

下一章：[16 - Kustomize 与配置管理选型](./16-kustomize.md)
