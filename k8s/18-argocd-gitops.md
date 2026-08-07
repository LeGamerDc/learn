# 18 - Argo CD 与 GitOps

> 本章目标：搞懂 GitOps 是什么、为什么它是当前部署的最佳实践、Argo CD 内部怎么工作，
> 并建立起一套能管几十个服务、多个环境、多个集群的交付体系。
> 预计用时：3.5 小时（含实验）。

---

## 1. 从"推"到"拉"：GitOps 解决什么

### 1.1 传统的推模型（Push）

```
CI 系统 ──持有 kubeconfig──► kubectl apply / helm upgrade ──► 生产集群
```

问题：

| 问题 | 说明 |
|---|---|
| **凭据风险** | CI 持有生产集群的写权限。CI 被攻破 = 集群沦陷。而 CI 通常是攻击面最大的系统（跑着各种第三方 Action/插件） |
| **网络暴露** | 集群 API Server 必须能被 CI 访问 → 往往要暴露到公网 |
| **漂移不可见** | 有人手工 `kubectl edit` 改了副本数，没人知道。下次部署又被改回去，行为诡异 |
| **真实状态不可知** | "生产现在跑的是哪个版本？"——要去集群里查，而不是看 Git |
| **回滚困难** | 要知道上一个版本是什么、用什么参数部署的 |
| **审计缺失** | 谁在什么时候改了什么？只有 CI 日志（还会过期） |
| **多集群噩梦** | 20 个集群 = CI 里配 20 套凭据 |

### 1.2 GitOps 的拉模型（Pull）

```
CI ──► 镜像仓库
 │
 └──► Git（配置仓）◄──持续拉取──── Argo CD（运行在集群内）──► 本集群
```

**[OpenGitOps](https://opengitops.dev/) 的四条原则**：

1. **声明式**：整个系统的期望状态用声明式的方式描述
2. **版本化且不可变**：期望状态存在 Git 里，有完整历史，可回溯
3. **自动拉取**：软件 agent 自动把期望状态拉到系统里
4. **持续调谐**：agent 持续观测实际状态，并让它向期望状态收敛

**收益**：

| 收益 | 说明 |
|---|---|
| **CI 不需要集群权限** | 巨大的安全改进。CI 只需要往 Git push 的权限 |
| **集群不需要暴露** | Argo CD 在集群内部，主动出站访问 Git |
| **Git 是唯一真相源** | 想知道生产跑什么，看 Git |
| **回滚 = `git revert`** | 不需要理解 Helm release 历史 |
| **审计天然完备** | PR review + git log + git blame |
| **漂移自动检测和修复** | 手工改了会被标记 OutOfSync，可自动改回去 |
| **多集群统一管理** | 一个 Argo CD 管几十个集群 |
| **灾难恢复简单** | 集群全没了？新建一个空集群，指向同一个 Git，几分钟恢复 |

**Argo CD vs Flux**：两个主流 GitOps 工具，都是 CNCF 毕业项目。Argo CD 有强大的 UI 和更丰富的功能（ApplicationSet、Rollouts 生态），Flux 更轻量、更"Unix 哲学"（一组独立的控制器）。本章讲 Argo CD（社区更大，UI 对学习更友好）。

---

## 2. Argo CD 架构

当前稳定版 **3.4.x**（3.5 在 RC）。

```
                        ┌──────────────────────────────────┐
                        │  Git 仓库（配置仓）                │
                        │  apps/hello/values-prod.yaml     │
                        └────────────┬─────────────────────┘
                                     │ ① 定期 poll / webhook
   ┌─────────────────────────────────▼───────────────────────────────────┐
   │  Argo CD（运行在集群内）                                              │
   │                                                                      │
   │  ┌───────────────┐  ② 拉取仓库、渲染清单（helm template/kustomize）  │
   │  │  repo-server  │     ⭐ 无状态，可水平扩展；渲染结果有缓存           │
   │  └───────┬───────┘                                                   │
   │          │ 渲染后的 YAML                                             │
   │  ┌───────▼───────────────┐  ③ 与集群实际状态 diff                    │
   │  │ application-controller │  ④ 执行 sync（apply）                     │
   │  │ （核心调谐循环）        │  ⑤ 评估健康状态                           │
   │  └───────┬───────────────┘                                          │
   │          │                                                          │
   │  ┌───────▼───────┐   ┌──────────┐   ┌──────────────────┐            │
   │  │  api-server   │   │  redis   │   │ applicationset-  │            │
   │  │ (UI/CLI/gRPC) │   │ (缓存)    │   │   controller     │            │
   │  └───────────────┘   └──────────┘   └──────────────────┘            │
   │  ┌───────────────┐   ┌──────────────────┐                           │
   │  │ dex (SSO)     │   │ notifications    │                           │
   │  └───────────────┘   └──────────────────┘                           │
   └──────────────────────────┬───────────────────────────────────────────┘
                              │ ⑥ apply
                    ┌─────────▼──────────┐
                    │  目标集群（可以是   │
                    │  自己，也可以是远程）│
                    └────────────────────┘
```

| 组件 | 职责 |
|---|---|
| **application-controller** | 核心。watch Application 对象和集群资源，做 diff 和 sync。是个标准的 K8s 控制器（第 6 章） |
| **repo-server** | 拉 Git、渲染清单（调用 helm template / kustomize build / 自定义插件）。无状态，CPU/内存消耗大户 |
| **api-server** | UI 和 CLI 的后端，处理认证鉴权 |
| **redis** | 缓存渲染结果和集群状态（挂了不丢数据，只是变慢） |
| **applicationset-controller** | 根据生成器批量生成 Application |
| **dex** | SSO 集成（可选，也可直接对接 OIDC） |
| **notifications-controller** | 同步结果通知（Slack/飞书/邮件） |

**Argo CD 3.5 的安全增强**：内部组件间强制 mTLS、Git 提交签名验证。

---

## 3. Application：核心对象

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hello-prod
  namespace: argocd            # ⭐ Application 对象必须在 Argo CD 所在的 namespace
  finalizers:
    - resources-finalizer.argocd.argoproj.io   # ⭐ 删除 App 时级联删除它部署的资源
spec:
  project: production          # AppProject，用于权限隔离（见 §7）

  source:
    repoURL: https://github.com/yourorg/k8s-config.git
    targetRevision: main       # 分支 / tag / commit sha
    path: apps/hello           # 仓库里的路径
    helm:                      # 用 Helm 渲染
      releaseName: hello
      valueFiles:
        - values.yaml
        - values-prod.yaml
      values: |                # 内联覆盖
        replicaCount: 6
      parameters:
        - name: image.tag
          value: v1.2.3
      skipCrds: false
    # 或者用 Kustomize：
    # kustomize:
    #   namePrefix: prod-
    #   images: [ghcr.io/yourorg/hello:v1.2.3]

  destination:
    server: https://kubernetes.default.svc    # 本集群（或远程集群 URL）
    # name: prod-cluster                       # 也可以用注册时的集群名
    namespace: prod

  syncPolicy:
    automated:
      prune: true              # ⭐ Git 里删掉的资源，集群里也删掉
      selfHeal: true           # ⭐ 手工改了集群，自动改回 Git 的状态
      allowEmpty: false        # 防止 Git 出错导致渲染为空 → 删光所有资源
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true         # 先创建新的，最后再删旧的
      - ServerSideApply=true   # ⭐ 用 SSA（第 6 章），大清单必备
      - RespectIgnoreDifferences=true
      - ApplyOutOfSyncOnly=true    # 只 apply 有差异的资源（大 App 提速）
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m

  revisionHistoryLimit: 10

  # ⭐ 忽略某些字段的差异（否则会一直显示 OutOfSync）
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas          # HPA 在改这个字段，别跟它打架
    - group: ""
      kind: Secret
      name: hello-tls
      jsonPointers:
        - /data                   # cert-manager 在管这个
    - group: apps
      kind: Deployment
      managedFieldsManagers:      # ⭐ 更精确：忽略某个 field manager 改的所有字段
        - kube-controller-manager
```

### 3.1 三个核心状态

```bash
argocd app get hello-prod
```

| 状态 | 取值 | 含义 |
|---|---|---|
| **Sync Status** | `Synced` / `OutOfSync` / `Unknown` | 集群状态是否等于 Git 状态 |
| **Health Status** | `Healthy` / `Progressing` / `Degraded` / `Suspended` / `Missing` / `Unknown` | 资源是否正常运行 |
| **Operation State** | `Running` / `Succeeded` / `Failed` | 最近一次同步操作的结果 |

**Sync 和 Health 是正交的**：
- `Synced` + `Degraded` = 部署的就是 Git 里的版本，但它跑不起来（比如镜像不存在）
- `OutOfSync` + `Healthy` = 现在跑的东西是好的，但和 Git 不一致（有人手工改了，或 Git 更新了还没同步）

Argo CD 内置了各种资源的健康判定逻辑（Deployment 看 `availableReplicas`、Ingress 看 `loadBalancer.ingress`……），也可以用 Lua 自定义 CRD 的健康检查。

### 3.2 自动同步策略详解

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

| 选项 | 不开启 | 开启 |
|---|---|---|
| （无 automated） | 需要手工点 Sync 或 `argocd app sync` | — |
| `automated` | — | Git 变了自动同步 |
| `prune: false`（默认） | Git 里删了资源，集群里**保留**（安全但会残留） | — |
| `prune: true` | — | Git 里删了，集群里也删（⚠️ Git 出错可能删光生产） |
| `selfHeal: false`（默认） | 手工改了集群，标记 OutOfSync 但不改回去 | — |
| `selfHeal: true` | — | 自动改回 Git 状态（⭐ 真正的 GitOps） |

**生产建议**：
- staging/dev：`automated + prune + selfHeal` 全开
- production：`automated + selfHeal` 开，`prune` 视团队成熟度（开了要配好 `allowEmpty: false` 和分支保护）
- 极关键的系统：不开 automated，人工点 Sync（保留"最后一道人工确认"）

### 3.3 Sync Waves 与 Hooks（控制顺序）

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-1"      # 数字小的先同步（默认 0）
```

典型顺序：

```
wave -2: Namespace、CRD
wave -1: ConfigMap、Secret、ServiceAccount、RBAC
wave  0: Deployment、Service（默认）
wave  1: Ingress/HTTPRoute
wave  2: 冒烟测试 Job
```

**Hook**（类似 Helm hook，但由 Argo CD 管理）：

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
  annotations:
    argocd.argoproj.io/hook: PreSync            # PreSync|Sync|PostSync|SyncFail|Skip
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
    argocd.argoproj.io/sync-wave: "-1"
spec:
  ...
```

⚠️ **Argo CD 会忽略 Helm hook 的部分语义**，且 Helm hook 和 Argo hook 可以共存但容易混乱。**用 Argo CD 时建议统一用 Argo 的 hook 注解**。

---

## 4. 仓库结构设计

这是实践中最需要想清楚的事。

### 4.1 应用代码仓 vs 配置仓（强烈建议分离）

| | 应用代码仓 | 配置仓 |
|---|---|---|
| 内容 | Go 源码、Dockerfile、Jenkinsfile | Helm values / Kustomize overlay / Application 定义 |
| 谁改 | 开发者 | 开发者 + 平台团队 |
| 变更频率 | 高 | 中 |
| CI 触发 | 构建镜像 | 不触发构建 |

**为什么分离**：
- 改配置不应该触发重新构建镜像
- 配置变更的 review 关注点不同（谁能批准上生产？）
- 一个配置仓可以管多个服务、多个环境
- 避免 CI 提交 tag 变更时触发自己（无限循环）

### 4.2 推荐的配置仓结构

```
k8s-config/
├── bootstrap/                        # ⭐ App of Apps 的根
│   ├── root-app.yaml
│   └── projects/
│       ├── platform.yaml
│       └── production.yaml
│
├── infrastructure/                   # 平台组件（用 Helm 装第三方）
│   ├── cert-manager/
│   │   └── application.yaml
│   ├── ingress/
│   ├── monitoring/
│   └── external-secrets/
│
├── charts/                           # 自研的通用 chart
│   └── go-service/                   # ⭐ 一个 chart 管所有 Go 服务
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│
└── apps/
    ├── hello/
    │   ├── base-values.yaml          # 所有环境共享
    │   ├── envs/
    │   │   ├── dev/
    │   │   │   ├── application.yaml
    │   │   │   └── values.yaml       # ⭐ CI 只改这个文件的 image.tag
    │   │   ├── staging/
    │   │   └── prod/
    └── orders/
        └── ...
```

### 4.3 环境隔离方式

| 方式 | 说明 | 评价 |
|---|---|---|
| **不同目录**（推荐） ⭐ | `apps/hello/envs/{dev,staging,prod}/` | 清晰、diff 可读、PR 里能看出改的是哪个环境 |
| 不同分支 | `dev` / `staging` / `main` 分支 | ⚠️ **不推荐**：分支间 cherry-pick 容易漏、配置漂移、和"Git 是真相源"的理念冲突 |
| 不同仓库 | 每个环境一个仓库 | 隔离最强，但同步成本高。多集群/多租户时可考虑 |

**关于"分支即环境"**：这是 GitOps 早期的常见做法，现在**社区共识是不推荐**。用目录 + 不同的 Application 指向不同 path 更清晰。

---

## 5. ApplicationSet：批量生成 Application

50 个服务 × 3 个环境 = 150 个 Application，手写不现实。ApplicationSet 用**生成器**批量生成。

### 5.1 Git 目录生成器（最常用）

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: all-apps-dev
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - git:
        repoURL: https://github.com/yourorg/k8s-config.git
        revision: main
        directories:
          - path: apps/*/envs/dev          # ⭐ 每个匹配的目录生成一个 Application
          - path: apps/excluded/envs/dev
            exclude: true
  template:
    metadata:
      name: '{{index .path.segments 1}}-dev'      # apps/hello/envs/dev → hello-dev
    spec:
      project: default
      source:
        repoURL: https://github.com/yourorg/k8s-config.git
        targetRevision: main
        path: '{{.path.path}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{index .path.segments 1}}-dev'
      syncPolicy:
        automated: {prune: true, selfHeal: true}
        syncOptions: [CreateNamespace=true]
```

**新增一个服务 = 建一个目录并提交**，Application 自动出现。

### 5.2 Matrix 生成器（服务 × 环境）

```yaml
generators:
  - matrix:
      generators:
        - git:                    # 所有服务
            repoURL: https://github.com/yourorg/k8s-config.git
            revision: main
            directories: [{path: apps/*}]
        - list:                   # 所有环境
            elements:
              - env: dev
                cluster: https://kubernetes.default.svc
                autoSync: "true"
              - env: staging
                cluster: https://staging.example.com
                autoSync: "true"
              - env: prod
                cluster: https://prod.example.com
                autoSync: "false"
```

### 5.3 Cluster 生成器（一个应用铺到所有集群）

```yaml
generators:
  - clusters:                     # 自动遍历 Argo CD 注册的所有集群
      selector:
        matchLabels:
          environment: production
template:
  spec:
    destination:
      server: '{{.server}}'
      namespace: monitoring
```

### 5.4 Progressive Sync（Argo CD 3.3+）

大规模 fleet 更新时分批推进，控制爆炸半径：

```yaml
spec:
  strategy:
    type: RollingSync
    rollingSync:
      steps:
        - matchExpressions:
            - {key: env, operator: In, values: [dev]}
        - matchExpressions:
            - {key: env, operator: In, values: [staging]}
          maxUpdate: 100%
        - matchExpressions:
            - {key: env, operator: In, values: [prod]}
          maxUpdate: 20%          # ⭐ 生产每次只更新 20% 的集群
```

前一批全部 Healthy 才推进下一批。

### 5.5 App of Apps（引导模式）

一个"根 Application"指向一个装满 Application/ApplicationSet 定义的目录：

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourorg/k8s-config.git
    targetRevision: main
    path: bootstrap                 # 这个目录里全是 Application/ApplicationSet
    directory: {recurse: true}
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated: {prune: true, selfHeal: true}
```

**新建集群的完整流程变成**：

```bash
① 建集群
② 装 Argo CD
③ kubectl apply -f root-app.yaml
④ 喝咖啡，等所有东西自己长出来 ☕
```

**这就是"灾难恢复只要几分钟"的原理。**

---

## 6. 镜像更新：CI 和 CD 的交接

三种方式：

### ① CI 提交（第 17 章用的，最直白）⭐

```bash
yq -i '.image.tag = "v1.2.3"' apps/hello/envs/staging/values.yaml
git commit -am "bump hello staging to v1.2.3" && git push
```

- ✅ 简单、审计清晰、和 PR 流程天然结合
- ⚠️ CI 需要配置仓的写权限；注意别触发 CI 自己（用 `[skip ci]` 或路径过滤）

### ② Argo CD Image Updater

一个独立组件，watch 镜像仓库，发现新 tag 就更新 Application（可以写回 Git）：

```yaml
metadata:
  annotations:
    argocd-image-updater.argoproj.io/image-list: hello=ghcr.io/yourorg/hello
    argocd-image-updater.argoproj.io/hello.update-strategy: semver
    argocd-image-updater.argoproj.io/hello.allow-tags: regexp:^v[0-9]+\.[0-9]+\.[0-9]+$
    argocd-image-updater.argoproj.io/write-back-method: git
```

- ✅ CI 不需要配置仓权限
- ⚠️ 自动更新生产要慎重；语义化版本要求严格

### ③ Source Hydrator（Argo CD 3.x 的新方案）

Argo CD 自己把"DRY 源"（Helm/Kustomize）渲染成"hydrated 清单"并提交到另一个分支，让人能直接看到最终 YAML 的 diff。3.5 起为 beta。

**推荐**：从方式 ① 开始（最容易理解和排查），团队成熟后再考虑其他。

---

## 7. 多集群与权限

### 7.1 注册集群

```bash
argocd cluster add prod-context --name prod-cluster --label environment=production
argocd cluster list
```

Argo CD 会在目标集群里创建一个 SA 和 ClusterRoleBinding，把 token 存成 Secret。

**架构选择**：

| 模式 | 说明 |
|---|---|
| **中央 Argo CD 管所有集群** | 一处管理，但爆炸半径大、网络要求高 |
| **每集群一个 Argo CD** ⭐ | 隔离好、故障域小；配一个中央的"元 Argo CD"管它们 |
| 混合 | 生产每集群一个，非生产用中央的 |

### 7.2 AppProject：权限边界

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: production
  namespace: argocd
spec:
  description: 生产环境应用

  sourceRepos:                       # ⭐ 只允许从这些仓库部署
    - https://github.com/yourorg/k8s-config.git

  destinations:                      # ⭐ 只允许部署到这些集群/namespace
    - server: https://prod.example.com
      namespace: 'prod-*'

  clusterResourceWhitelist:          # 允许的集群级资源
    - {group: '', kind: Namespace}

  namespaceResourceBlacklist:        # ⭐ 禁止的资源
    - {group: 'rbac.authorization.k8s.io', kind: ClusterRole}
    - {group: '', kind: ResourceQuota}

  roles:
    - name: developer
      policies:
        - p, proj:production:developer, applications, get, production/*, allow
        - p, proj:production:developer, applications, sync, production/*, allow
        # 注意：没给 delete 和 override
      groups: [yourorg:backend-team]

  syncWindows:                       # ⭐ 变更窗口：禁止在特定时间同步
    - kind: deny
      schedule: '0 0 * * 5'          # 周五全天
      duration: 24h
      applications: ['*']
      manualSync: true               # 但允许人工同步（紧急修复）
```

### 7.3 Argo CD RBAC

```
# argocd-rbac-cm ConfigMap
policy.csv: |
  p, role:developer, applications, get, */*, allow
  p, role:developer, applications, sync, dev/*, allow
  p, role:developer, applications, action/*, */*, deny
  p, role:sre, applications, *, */*, allow
  p, role:sre, clusters, get, *, allow

  g, yourorg:backend-team, role:developer
  g, yourorg:sre-team, role:sre
policy.default: role:readonly
```

---

## 8. 密钥怎么办

配置仓在 Git 里，**密钥不能明文进 Git**（第 8 章）。三种方案：

| 方案 | 说明 |
|---|---|
| **External Secrets Operator** ⭐ | Git 里只有 `ExternalSecret` 声明，真实密钥在 Vault/AWS SM。**推荐** |
| **Sealed Secrets** | 加密后的 `SealedSecret` 进 Git，集群内解密 |
| **SOPS + argocd-vault-plugin / helm-secrets** | 加密的 YAML 进 Git，Argo CD 渲染时解密 |

**绝对不要**：把明文 Secret 提交到 Git，即使是私有仓库。

---

## 9. 动手实验

### 实验 1：安装 Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s

# 初始密码
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo

kubectl -n argocd port-forward svc/argocd-server 8081:443 &
# 浏览器 https://localhost:8081（忽略证书警告），admin / 上面的密码

# CLI 登录
argocd login localhost:8081 --username admin --password <上面的密码> --insecure
argocd version
```

### 实验 2：⭐ 部署第一个应用

用官方的示例仓库先跑通：

```bash
argocd app create guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace guestbook \
  --sync-policy automated \
  --auto-prune --self-heal \
  --sync-option CreateNamespace=true

argocd app get guestbook
argocd app sync guestbook
argocd app wait guestbook --health

kubectl -n guestbook get all
```

在 UI 里看资源拓扑图——这是 Argo CD 最好用的功能之一。

### 实验 3：⭐⭐ 自愈（selfHeal）—— GitOps 的核心体验

```bash
kubectl -n guestbook get deploy guestbook-ui
kubectl -n guestbook scale deploy guestbook-ui --replicas=5
kubectl -n guestbook get deploy guestbook-ui -w
# ⭐ 几十秒内自动变回 1！因为 Git 里写的是 1

argocd app get guestbook | grep -i sync
kubectl get events -n argocd --sort-by=.lastTimestamp | tail -5
```

**再试试删除资源**：

```bash
kubectl -n guestbook delete svc guestbook-ui
sleep 30
kubectl -n guestbook get svc      # ⭐ 自己回来了
```

**这就是"持续调谐"的威力**：任何偏离 Git 的手工改动都会被纠正。也意味着：**紧急情况下想手工改，必须先在 Argo CD 里禁用 selfHeal 或把 App 设为 unmanaged**，否则你的改动会被打回去。

### 实验 4：用自己的配置仓

创建一个本地 Git 仓库（也可以推到 GitHub）：

```bash
mkdir -p ~/lab/k8s-config/apps/hello/envs/dev && cd ~/lab/k8s-config
git init -b main

cat > apps/hello/envs/dev/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
spec:
  replicas: 2
  selector: {matchLabels: {app: hello}}
  template:
    metadata: {labels: {app: hello}}
    spec:
      containers:
        - name: server
          image: hello:v0.1.0
          imagePullPolicy: IfNotPresent
          ports: [{name: http, containerPort: 8080}]
          env: [{name: GREETING, value: "from gitops v1"}]
          readinessProbe:
            httpGet: {path: /readyz, port: http}
            periodSeconds: 3
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {memory: 256Mi}
---
apiVersion: v1
kind: Service
metadata: {name: hello}
spec:
  selector: {app: hello}
  ports: [{port: 80, targetPort: http}]
EOF

git add -A && git commit -m "init hello dev"
```

推到 GitHub（或用本地路径 —— Argo CD 需要能访问到，最简单是推到 GitHub 私有仓 + 加凭据，或用公开仓）：

```bash
# 假设已推到 https://github.com/YOURNAME/k8s-config
argocd app create hello-dev \
  --repo https://github.com/YOURNAME/k8s-config.git \
  --path apps/hello/envs/dev \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace hello-dev \
  --sync-policy automated --auto-prune --self-heal \
  --sync-option CreateNamespace=true

argocd app wait hello-dev --health
kubectl -n hello-dev get all
```

### 实验 5：⭐ 模拟一次发布

```bash
cd ~/lab/k8s-config
sed -i '' 's/from gitops v1/from gitops v2/' apps/hello/envs/dev/deployment.yaml
sed -i '' 's/replicas: 2/replicas: 4/' apps/hello/envs/dev/deployment.yaml
git commit -am "release: hello v2, scale to 4"
git push

# 等待自动同步（默认 3 分钟轮询；也可以手工触发）
argocd app get hello-dev
argocd app sync hello-dev       # 立刻同步
argocd app wait hello-dev --health

kubectl -n hello-dev get deploy hello -o jsonpath='{.spec.replicas}{"\n"}'
kubectl -n hello-dev get pods
```

**回滚 = git revert**：

```bash
git revert HEAD --no-edit && git push
argocd app sync hello-dev
kubectl -n hello-dev get deploy hello -o jsonpath='{.spec.replicas}{"\n"}'    # 回到 2
```

**或者用 Argo CD 的历史回滚**：

```bash
argocd app history hello-dev
argocd app rollback hello-dev <REVISION-ID>
# ⚠️ 注意：这会让 App 变成 OutOfSync（因为集群状态不等于 Git HEAD）
#    正统 GitOps 应该用 git revert
```

### 实验 6：Webhook 加速（可选）

默认 3 分钟轮询一次。配置 Git webhook 指向 `https://<argocd>/api/webhook` 可以做到秒级响应。

```bash
kubectl -n argocd get cm argocd-cm -o yaml
# 在 GitHub 仓库 Settings → Webhooks 里加
```

### 实验 7：App of Apps

```bash
mkdir -p ~/lab/k8s-config/bootstrap
cat > ~/lab/k8s-config/bootstrap/hello-dev.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hello-dev
  namespace: argocd
  finalizers: [resources-finalizer.argocd.argoproj.io]
spec:
  project: default
  source:
    repoURL: https://github.com/YOURNAME/k8s-config.git
    targetRevision: main
    path: apps/hello/envs/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: hello-dev
  syncPolicy:
    automated: {prune: true, selfHeal: true}
    syncOptions: [CreateNamespace=true]
EOF
cd ~/lab/k8s-config && git add -A && git commit -m "add bootstrap" && git push

argocd app create root \
  --repo https://github.com/YOURNAME/k8s-config.git \
  --path bootstrap \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace argocd \
  --sync-policy automated --auto-prune --self-heal \
  --directory-recurse

argocd app list        # root 生成了 hello-dev ⭐
```

### 实验 8：观察 diff

```bash
kubectl -n hello-dev patch deploy hello -p '{"spec":{"template":{"spec":{"containers":[{"name":"server","env":[{"name":"GREETING","value":"MANUAL HACK"}]}]}}}}'
argocd app diff hello-dev       # ⭐ 精确显示差异
# selfHeal 会很快改回去
```

### 清理

```bash
argocd app delete root --cascade -y 2>/dev/null
argocd app delete hello-dev --cascade -y 2>/dev/null
argocd app delete guestbook --cascade -y
kubectl delete ns guestbook hello-dev --ignore-not-found
```

---

## 10. 排障速查

| 现象 | 排查 |
|---|---|
| App 一直 `OutOfSync` 但看不出差异 | ① `argocd app diff <app>` 看具体字段<br>② 通常是有其他控制器在改（HPA 改 replicas、webhook 注入 sidecar）→ 配 `ignoreDifferences`<br>③ 或者是 SSA 的 field manager 冲突 → 开 `ServerSideApply=true` |
| `ComparisonError` / 渲染失败 | `kubectl -n argocd logs deploy/argocd-repo-server`；本地跑一遍 `helm template` 复现 |
| Sync 卡住 | 看 hook Job 是否失败；`argocd app get <app>` 看每个资源的状态 |
| Health 一直 `Progressing` | Pod 起不来（回到第 22 章排查）；或者 CRD 没有健康检查逻辑 → 写自定义 Lua |
| 权限错误 | `argocd app get` 报 permission denied → 检查 AppProject 的 destinations/sourceRepos 白名单 |
| repo-server OOM | 大仓库/大 chart 渲染耗内存 → 加内存、开 `--parallelismlimit`、拆分仓库 |
| 同步很慢 | 开 `ApplyOutOfSyncOnly=true`；调 `--app-resync`；用 webhook 代替轮询 |
| prune 删掉了不该删的 | 加 `Prune=false` 注解到该资源；或用 `argocd.argoproj.io/sync-options: Delete=false` |

---

## 11. 本章检查清单

- [ ] GitOps 的四条原则是什么？
- [ ] 推模型有哪 7 个问题？拉模型分别怎么解决？
- [ ] Argo CD 的 5 个核心组件各自做什么？
- [ ] Sync Status 和 Health Status 是什么关系？举一个"Synced + Degraded"的例子
- [ ] `prune` 和 `selfHeal` 分别做什么？生产上怎么配？
- [ ] `ignoreDifferences` 解决什么问题？HPA 场景为什么需要它？
- [ ] sync wave 和 hook 怎么控制部署顺序？
- [ ] 为什么建议应用代码仓和配置仓分离？
- [ ] 为什么不推荐"分支即环境"？
- [ ] ApplicationSet 的 git 生成器和 matrix 生成器分别用在什么场景？
- [ ] App of Apps 模式让灾难恢复变成什么样？
- [ ] CI 和 CD 交接的三种方式，各自优缺点？
- [ ] AppProject 能限制什么？
- [ ] GitOps 下密钥怎么管？
- [ ] 完成实验 2、3（自愈体验是本章精髓）、5

---

## 12. 延伸阅读

- [Argo CD 官方文档](https://argo-cd.readthedocs.io/)
- [OpenGitOps 原则](https://opengitops.dev/)
- [ApplicationSet 文档](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)
- [Argo CD 最佳实践](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)
- [Flux（另一个 GitOps 工具）](https://fluxcd.io/)
- [External Secrets Operator](https://external-secrets.io/)

---

下一章：[19 - 渐进式交付：金丝雀与蓝绿](./19-progressive-delivery.md)
