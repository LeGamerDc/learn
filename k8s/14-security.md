# 14 - 安全与多租户

> 本章目标：把集群从"能跑"变成"能放心跑"。RBAC、Pod 安全策略、资源配额、准入控制、供应链安全——
> 这些也是"管理大规模集群"（第 21 章）的前提。
> 预计用时：2.5 小时。

---

## 1. 威胁模型：你在防什么

| 威胁 | 场景 | 对策 |
|---|---|---|
| **凭据泄漏** | CI 的 kubeconfig 被拿到，攻击者能删整个集群 | RBAC 最小权限、GitOps 拉模型（第 18 章）、短期令牌 |
| **容器逃逸** | 应用漏洞 → 容器内执行 → 逃到宿主机 | 非 root、drop capabilities、seccomp、user namespace |
| **横向移动** | 攻破前端 → 直连数据库 → 拖库 | NetworkPolicy、namespace 隔离 |
| **供应链投毒** | 依赖库/基础镜像被植入后门 | 镜像扫描、签名验证、SBOM、固定 digest |
| **权限提升** | 普通用户能创建特权 Pod → 拿到节点 root | Pod Security Admission、RBAC 审查 |
| **资源耗尽** | 一个 namespace 吃光集群资源 | ResourceQuota、LimitRange、PriorityClass |
| **密钥泄漏** | etcd 备份被拿到，里面全是明文密钥 | 静态加密、外部密钥系统 |
| **误操作** | 手滑删了生产 namespace | RBAC、GitOps、审计、备份 |

---

## 2. 认证：你是谁

K8s **没有"用户"这个对象**。用户来自外部身份系统，K8s 只验证凭据。

| 方式 | 用于 | 说明 |
|---|---|---|
| **客户端 X.509 证书** | 人、集群组件 | 证书的 `CN` = 用户名，`O` = 组。⚠️ **无法吊销**（除非换 CA），不适合给人用 |
| **ServiceAccount Token** | **Pod（集群内工作负载）** | JWT，现代版本是短期投影令牌 |
| **OIDC** ⭐ | 人 | 对接企业 SSO（Google/Okta/Keycloak/AD），支持 MFA 和吊销。**生产给人用的正确方式** |
| **Webhook Token** | 自定义 | 对接自建认证系统 |
| 云厂商 IAM | 人 + 工作负载 | EKS 的 IAM、GKE 的 Workload Identity |

```bash
# 我是谁？（1.28+ 内置）
kubectl auth whoami
# ATTRIBUTE   VALUE
# Username    kubernetes-admin
# Groups      [system:masters system:authenticated]
```

⚠️ `system:masters` 组**绕过所有 RBAC 检查**。kubeadm 生成的 admin.conf 就是这个组——**不要把它分发给任何人**，也不要在 CI 里用。

### 2.1 ServiceAccount

每个 namespace 有一个 `default` SA，Pod 不指定就用它。

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: hello
  namespace: prod
  annotations:
    # 云上的工作负载身份（Pod 直接拿云 IAM 权限，无需静态 AK/SK）
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/hello-role
automountServiceAccountToken: false     # ⭐ 默认不挂载
---
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: hello
  automountServiceAccountToken: false   # ⭐ 不需要访问 K8s API 就关掉
```

**现代 SA token（投影令牌）**：
- 有过期时间（默认 1 小时），kubelet 自动轮转
- 绑定受众（audience）和 Pod（Pod 删了 token 立即失效）
- 挂载在 `/var/run/secrets/kubernetes.io/serviceaccount/token`

```bash
kubectl exec <pod> -- cat /var/run/secrets/kubernetes.io/serviceaccount/token | \
  cut -d. -f2 | base64 -d 2>/dev/null | jq
```

**安全基线**：绝大多数业务 Pod 不需要访问 K8s API → **一律设 `automountServiceAccountToken: false`**。
一个泄漏的 SA token + 过宽的 RBAC = 集群沦陷。

---

## 3. 授权：RBAC

### 3.1 四个对象

```
    Role（namespace 级）          ClusterRole（集群级）
         │                              │
    RoleBinding                   ClusterRoleBinding
         │                              │
         └──────► Subject（User / Group / ServiceAccount）◄──┘
```

| 对象 | 作用域 |
|---|---|
| `Role` | 定义某个 namespace 内的权限 |
| `ClusterRole` | 定义集群级权限（或可被复用到任意 namespace 的权限模板） |
| `RoleBinding` | 把 Role **或** ClusterRole 绑定到主体，**权限只在本 namespace 生效** |
| `ClusterRoleBinding` | 把 ClusterRole 绑定到主体，**全集群生效** |

⚠️ **重要组合**：`RoleBinding` + `ClusterRole` = 用集群级的权限模板，但只在这一个 namespace 生效。这是最常用的模式（比如给某人在某 namespace 的 `edit` 权限）。

### 3.2 写一个 Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: prod
  name: app-operator
rules:
  - apiGroups: [""]                     # "" = core group
    resources: ["pods", "pods/log", "services", "configmaps"]
    verbs: ["get", "list", "watch"]

  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["get", "list", "watch", "update", "patch"]

  - apiGroups: ["apps"]
    resources: ["deployments/scale"]    # 子资源
    verbs: ["update", "patch"]

  - apiGroups: [""]
    resources: ["pods/exec"]            # ⚠️ 危险：能 exec 进 Pod
    verbs: ["create"]

  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["app-config"]       # 限定到具体对象（只对 get/update/delete 有效，list 无效）
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  namespace: prod
  name: app-operator
subjects:
  - kind: User
    name: alice@example.com             # 来自 OIDC
    apiGroup: rbac.authorization.k8s.io
  - kind: Group
    name: backend-team
    apiGroup: rbac.authorization.k8s.io
  - kind: ServiceAccount
    name: ci-deployer
    namespace: ci
roleRef:
  kind: Role
  name: app-operator
  apiGroup: rbac.authorization.k8s.io
```

**verbs 全集**：`get`、`list`、`watch`、`create`、`update`、`patch`、`delete`、`deletecollection`、
以及特殊的 `impersonate`、`bind`、`escalate`、`use`（用于 PSP，已废弃）。

**RBAC 是纯白名单，无 deny 规则**。多个绑定的权限取并集。

### 3.3 内置 ClusterRole

```bash
kubectl get clusterroles | grep -v '^system:'
```

| 名称 | 权限 |
|---|---|
| `cluster-admin` | 一切（`*` on `*`） |
| `admin` | namespace 内一切（含 RBAC 管理），但不能改 namespace 本身和 quota |
| `edit` | 读写大多数对象，不能改 RBAC |
| `view` | 只读，**不含 Secret** |

```bash
# 快速授权（生产建议用 YAML 而不是命令式）
kubectl create rolebinding alice-edit --clusterrole=edit --user=alice -n prod
kubectl create clusterrolebinding ci-view --clusterrole=view --serviceaccount=ci:deployer
```

### 3.4 权限检查工具

```bash
# 我能做这个吗？
kubectl auth can-i create deployments -n prod
kubectl auth can-i delete nodes
kubectl auth can-i '*' '*'                       # 我是超管吗？

# 别人能做吗？（需要 impersonate 权限）
kubectl auth can-i get secrets -n prod --as=alice@example.com
kubectl auth can-i list pods --as=system:serviceaccount:prod:hello

# 列出某人的所有权限
kubectl auth can-i --list --as=system:serviceaccount:prod:hello -n prod

# 谁能做某件事（需要装 rbac-lookup 或 kubectl-who-can 插件）
kubectl who-can delete pods -n prod
```

### 3.5 RBAC 的危险权限（审计重点）

以下权限等价于（或很容易升级为）集群管理员：

| 权限 | 为什么危险 |
|---|---|
| `pods/exec`、`pods/attach`、`pods/portforward` | 能进任意 Pod，读它的所有 Secret 和文件 |
| `create pods`（在任意 namespace） | 能挂载该 namespace 的**任何 Secret**、能用高权限 SA、能挂 hostPath 逃逸 |
| `secrets: get/list` | 直接读密钥 |
| `escalate` on roles | 能给自己加权限 |
| `bind` on rolebindings | 能把 cluster-admin 绑给自己 |
| `impersonate` | 能扮演任何人 |
| `nodes/proxy` | 直接访问 kubelet API，等于节点 root |
| `create` on `certificatesigningrequests/approval` | 能签发任意身份的证书 |
| `patch` on `nodes` | 能改节点标签/污点，操纵调度 |
| 对 CRD 的 `*` | 视 CRD 而定，Argo CD 的 Application 就能部署任意东西 |

**关键认知**：`create pods` 是最被低估的危险权限。有了它，攻击者可以：

```yaml
# 挂载 hostPath 逃逸到节点
volumes:
  - name: host
    hostPath: {path: /}
# 或者用高权限的 SA
serviceAccountName: some-admin-sa
```

**所以 RBAC 必须和 Pod Security Admission 配合使用**（下一节）。

### 3.6 最小权限设计模板

```
集群角色划分：
├── platform-admin      cluster-admin（2~3 人，走审批）
├── sre                 集群只读 + 节点操作 + 所有 namespace 的 edit
├── team-lead           自己 namespace 的 admin
├── developer           自己 namespace 的 edit（不含 secrets 写、不含 exec 到生产）
├── viewer              全集群 view
└── ci-deployer (SA)    ⭐ 极小权限：只能 patch 指定 Deployment 的 image
```

CI 部署账号的最小 Role：

```yaml
kind: Role
metadata: {namespace: prod, name: ci-deployer}
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    resourceNames: ["hello"]           # 只能动这一个 Deployment
    verbs: ["get", "patch"]
  - apiGroups: ["apps"]
    resources: ["deployments/status"]
    resourceNames: ["hello"]
    verbs: ["get"]
```

> 用 GitOps（第 18 章）后，CI **完全不需要集群权限**——它只往 Git 里写。这是安全上的巨大改进。

---

## 4. Pod Security Admission（PSA）

PodSecurityPolicy 在 1.25 被删除了，替代品是 **Pod Security Admission**——一个内置的准入控制器，按 namespace 打标签生效。

### 4.1 三个级别

| 级别 | 说明 |
|---|---|
| `privileged` | 不限制（系统组件用） |
| `baseline` | 阻止已知的提权：禁止 privileged、hostNetwork/PID/IPC、hostPath、危险 capabilities、非默认 sysctl |
| **`restricted`** ⭐ | baseline + 强制：非 root、`allowPrivilegeEscalation: false`、drop ALL capabilities、seccomp RuntimeDefault、只允许安全的卷类型 |

### 4.2 三种模式

| 模式 | 行为 |
|---|---|
| `enforce` | 违规 Pod **被拒绝创建** |
| `audit` | 允许，但记录到审计日志 |
| `warn` | 允许，但给 kubectl 返回警告 |

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: prod
  labels:
    # 生产标准配置
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: v1.36
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**渐进式落地策略**（生产改造的正确姿势）：

```bash
# 第 1 步：只 warn，不阻塞。观察哪些负载会违规
kubectl label ns prod pod-security.kubernetes.io/warn=restricted

# 第 2 步：加 audit，从审计日志统计违规量
kubectl label ns prod pod-security.kubernetes.io/audit=restricted

# 第 3 步：修复所有违规的工作负载

# 第 4 步：enforce
kubectl label ns prod pod-security.kubernetes.io/enforce=restricted
```

### 4.3 满足 restricted 的 Pod 模板

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 65532
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: server
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
        readOnlyRootFilesystem: true    # restricted 不强制，但强烈建议
```

**PSA 的局限**：只有三个固定级别，无法自定义（比如"禁止用 latest tag"、"必须设 resources"）。需要更细的策略 → 用 Kyverno 或 OPA Gatekeeper。

---

## 5. 准入控制：自定义策略

### 5.1 Kyverno（推荐，策略即 YAML，不用学新语言）

```bash
helm repo add kyverno https://kyverno.github.io/kyverno
helm install kyverno kyverno/kyverno -n kyverno --create-namespace
```

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata: {name: production-standards}
spec:
  validationFailureAction: Enforce      # 或 Audit
  background: true
  rules:
    # ① 禁止 latest tag
    - name: disallow-latest-tag
      match:
        any: [{resources: {kinds: [Pod], namespaces: [prod, staging]}}]
      validate:
        message: "禁止使用 :latest 或不带 tag 的镜像"
        pattern:
          spec:
            containers:
              - image: "!*:latest | !*"

    # ② 必须设置 resources
    - name: require-resources
      match:
        any: [{resources: {kinds: [Pod], namespaces: [prod]}}]
      validate:
        message: "必须设置 requests 和 memory limit"
        pattern:
          spec:
            containers:
              - resources:
                  requests: {cpu: "?*", memory: "?*"}
                  limits: {memory: "?*"}

    # ③ 必须有探针
    - name: require-probes
      match:
        any: [{resources: {kinds: [Deployment], namespaces: [prod]}}]
      validate:
        message: "生产工作负载必须配置 readinessProbe"
        pattern:
          spec:
            template:
              spec:
                containers:
                  - readinessProbe: {"?*": "?*"}

    # ④ 必须有标准标签
    - name: require-labels
      match:
        any: [{resources: {kinds: [Deployment, StatefulSet]}}]
      validate:
        message: "必须有 app.kubernetes.io/name 和 owner 标签"
        pattern:
          metadata:
            labels:
              app.kubernetes.io/name: "?*"
              owner: "?*"

    # ⑤ 只允许可信仓库
    - name: allowed-registries
      match:
        any: [{resources: {kinds: [Pod]}}]
      validate:
        message: "镜像只能来自 registry.internal 或 ghcr.io/yourorg"
        pattern:
          spec:
            containers:
              - image: "registry.internal/* | ghcr.io/yourorg/*"

    # ⑥ 自动注入（mutate）：给所有 Pod 加默认 securityContext
    - name: add-default-securitycontext
      match:
        any: [{resources: {kinds: [Pod], namespaces: [prod]}}]
      mutate:
        patchStrategicMerge:
          spec:
            securityContext:
              +(runAsNonRoot): true
              +(seccompProfile): {type: RuntimeDefault}
```

Kyverno 还能做：**验证镜像签名**（cosign）、生成资源（新 namespace 自动创建 NetworkPolicy + ResourceQuota）、清理过期资源。

```yaml
    # 验证镜像签名
    - name: verify-image-signature
      match:
        any: [{resources: {kinds: [Pod]}}]
      verifyImages:
        - imageReferences: ["ghcr.io/yourorg/*"]
          attestors:
            - entries:
                - keys:
                    publicKeys: |
                      -----BEGIN PUBLIC KEY-----
                      ...
```

### 5.2 OPA Gatekeeper（另一个选择）

用 Rego 语言写策略，表达能力更强但学习曲线陡。大型企业、已有 OPA 体系时用。

---

## 6. 多租户与资源配额

### 6.1 Namespace 是基本隔离单元

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: team-a
  labels:
    pod-security.kubernetes.io/enforce: restricted
    team: team-a
    environment: production
```

**Namespace 隔离的是什么、不隔离什么**：

| 隔离 ✅ | 不隔离 ❌ |
|---|---|
| 对象命名空间 | **网络**（默认全通，需要 NetworkPolicy） |
| RBAC 权限边界 | **节点**（Pod 混跑在同一批节点上） |
| ResourceQuota | **内核**（共享，逃逸风险） |
| 默认的 Service DNS 域 | **集群级资源**（Node、PV、CRD、StorageClass） |

**所以"软多租户"（namespace 隔离）不适合互不信任的租户。** 强隔离需要：独立集群 / 虚拟集群（vCluster）/ 独立节点池 + 沙箱运行时（gVisor、Kata）。

### 6.2 ResourceQuota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata: {name: team-a-quota, namespace: team-a}
spec:
  hard:
    # 计算资源
    requests.cpu: "50"
    requests.memory: 100Gi
    limits.cpu: "100"
    limits.memory: 200Gi
    requests.storage: 1Ti
    requests.nvidia.com/gpu: "4"

    # 对象数量（防止对象数爆炸拖垮 etcd）
    pods: "200"
    services: "50"
    services.loadbalancers: "2"        # ⭐ 控制云 LB 成本
    services.nodeports: "5"
    persistentvolumeclaims: "50"
    configmaps: "100"
    secrets: "100"
    count/deployments.apps: "50"
    count/jobs.batch: "100"
---
# 按优先级分配配额
apiVersion: v1
kind: ResourceQuota
metadata: {name: high-prio-quota, namespace: team-a}
spec:
  hard:
    requests.cpu: "20"
    pods: "50"
  scopeSelector:
    matchExpressions:
      - {scopeName: PriorityClass, operator: In, values: [high-priority]}
```

⚠️ **一旦设置了 ResourceQuota 的 CPU/内存项，该 namespace 里的每个容器都必须显式设置对应的 requests/limits**，否则 Pod 创建会被拒绝。所以要配合 LimitRange。

### 6.3 LimitRange（默认值 + 边界）

```yaml
apiVersion: v1
kind: LimitRange
metadata: {name: team-a-limits, namespace: team-a}
spec:
  limits:
    - type: Container
      default:                       # 没写 limits 时的默认值
        cpu: 500m
        memory: 512Mi
      defaultRequest:                # 没写 requests 时的默认值
        cpu: 100m
        memory: 128Mi
      max:                           # 单容器上限
        cpu: "4"
        memory: 8Gi
      min:
        cpu: 10m
        memory: 16Mi
      maxLimitRequestRatio:          # ⭐ limit/request 比值上限，防止过度超卖
        cpu: "10"
        memory: "4"
    - type: PersistentVolumeClaim
      max: {storage: 500Gi}
      min: {storage: 1Gi}
```

```bash
kubectl describe quota -n team-a
kubectl describe limitrange -n team-a
```

---

## 7. 供应链安全

### 7.1 完整链路

```
源码 → 依赖 → 构建 → 镜像 → 仓库 → 部署 → 运行
  │      │      │      │       │      │      │
签名   SCA扫描  可复现  扫描   访问控制 验签   运行时检测
提交   SBOM    构建   SBOM   保留策略 策略   (Falco)
```

### 7.2 具体措施

```bash
# ① 依赖扫描（Go）
govulncheck ./...                        # 官方漏洞扫描，只报真正可达的漏洞
go list -m -u all                        # 检查过期依赖

# ② 镜像扫描（CI 门禁）
trivy image --severity HIGH,CRITICAL --exit-code 1 myapp:v1
trivy fs --scanners vuln,secret,misconfig .    # 扫源码里的密钥和错误配置

# ③ 生成 SBOM + 构建溯源
docker buildx build --sbom=true --provenance=mode=max -t myapp:v1 --push .

# ④ 签名与验签
cosign sign --key cosign.key ghcr.io/org/myapp:v1
cosign verify --key cosign.pub ghcr.io/org/myapp:v1

# ⑤ 集群侧强制验签（Kyverno verifyImages，见 §5.1）

# ⑥ 清单扫描
kubectl apply --dry-run=client -f deploy.yaml -o yaml | trivy config -
```

### 7.3 运行时安全

**Falco**（CNCF）用 eBPF 监控系统调用，检测异常行为：

```yaml
# 规则示例：容器里起了 shell
- rule: Terminal shell in container
  condition: spawned_process and container and shell_procs
  output: "Shell spawned in container (user=%user.name container=%container.name)"
  priority: WARNING
```

典型检测项：容器内起 shell、写入敏感目录、异常网络连接、读取 `/etc/shadow`、加载内核模块。

---

## 8. 审计日志

记录"谁在什么时候对什么做了什么"：

```yaml
# audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
omitStages: ["RequestReceived"]
rules:
  # 不记录高频的只读请求（否则日志量爆炸）
  - level: None
    verbs: ["get", "list", "watch"]
    resources:
      - group: ""
        resources: ["events", "endpoints", "endpointslices"]

  # ⭐ Secret 的所有操作记录元数据（不记录内容！）
  - level: Metadata
    resources:
      - group: ""
        resources: ["secrets", "configmaps"]

  # ⭐ 所有写操作记录完整请求和响应
  - level: RequestResponse
    verbs: ["create", "update", "patch", "delete"]
    resources:
      - group: ""
      - group: "apps"
      - group: "rbac.authorization.k8s.io"

  - level: Metadata      # 其余记元数据
```

apiserver 参数：`--audit-policy-file`、`--audit-log-path`、`--audit-log-maxage`。托管集群一般在控制台开启并送到云日志服务。

**必须告警的审计事件**：
- 创建 `cluster-admin` 级别的绑定
- 对 `kube-system` 的写操作
- `pods/exec` 到生产 namespace
- Secret 的批量 list
- 删除 namespace / CRD
- 匿名用户的成功请求

---

## 9. 安全基线检查清单

### 集群级

- [ ] API Server 不暴露到公网（或有 IP 白名单 + OIDC + MFA）
- [ ] etcd 静态加密（KMS provider 最佳），且备份也加密
- [ ] 审计日志开启并外送
- [ ] 匿名访问关闭（`--anonymous-auth=false`）
- [ ] kubelet 认证授权开启（`--anonymous-auth=false --authorization-mode=Webhook`）
- [ ] 只读端口关闭（`--read-only-port=0`）
- [ ] 及时打补丁（K8s 每年 3 个版本，别落后超过 2 个）
- [ ] 定期跑 CIS Benchmark：`kube-bench run`

### 工作负载级

- [ ] namespace 打上 PSA `restricted` 标签
- [ ] 所有 Pod 非 root、drop ALL capabilities、seccomp RuntimeDefault
- [ ] `readOnlyRootFilesystem: true`
- [ ] `automountServiceAccountToken: false`（除非需要）
- [ ] 每个应用一个专属 SA，权限最小化
- [ ] 每个 namespace 有 default-deny NetworkPolicy
- [ ] 所有 namespace 有 ResourceQuota + LimitRange
- [ ] 关键服务有 PDB
- [ ] 镜像来自可信仓库、有签名、扫描无高危漏洞
- [ ] 密钥来自外部密钥系统，不在 Git 里

### 流程级

- [ ] 生产变更走 GitOps（有 PR 审核和审计）
- [ ] 没人有生产的长期 `cluster-admin`（走临时提权审批）
- [ ] 有定期的权限审查（谁有什么权限）
- [ ] 有事故响应预案和演练

---

## 10. 动手实验

### 实验 1：RBAC 最小权限

```bash
kubectl create ns sec && kubectl config set-context --current --namespace=sec

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ServiceAccount
metadata: {name: reader, namespace: sec}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: pod-reader, namespace: sec}
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: reader-binding, namespace: sec}
subjects: [{kind: ServiceAccount, name: reader, namespace: sec}]
roleRef: {kind: Role, name: pod-reader, apiGroup: rbac.authorization.k8s.io}
EOF

SA=system:serviceaccount:sec:reader
kubectl auth can-i list pods --as=$SA -n sec          # yes
kubectl auth can-i delete pods --as=$SA -n sec        # no
kubectl auth can-i list secrets --as=$SA -n sec       # no
kubectl auth can-i list pods --as=$SA -n default      # no（Role 只在 sec 生效）
kubectl auth can-i --list --as=$SA -n sec
```

### 实验 2：在 Pod 里用 SA 访问 API

```bash
kubectl run api-client --image=nicolaka/netshoot --restart=Never \
  --overrides='{"spec":{"serviceAccountName":"reader"}}' -- sleep 3600
kubectl wait --for=condition=Ready pod/api-client --timeout=60s

kubectl exec -it api-client -- bash -c '
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
CACERT=/var/run/secrets/kubernetes.io/serviceaccount/ca.crt
NS=$(cat /var/run/secrets/kubernetes.io/serviceaccount/namespace)

echo "=== 列 Pod（有权限）==="
curl -s --cacert $CACERT -H "Authorization: Bearer $TOKEN" \
  https://kubernetes.default.svc/api/v1/namespaces/$NS/pods | head -c 200

echo -e "\n\n=== 列 Secret（无权限）==="
curl -s --cacert $CACERT -H "Authorization: Bearer $TOKEN" \
  https://kubernetes.default.svc/api/v1/namespaces/$NS/secrets | head -c 300
'
# Secret 请求返回 403 Forbidden ✅
kubectl delete pod api-client
```

### 实验 3：⭐ Pod Security Admission

```bash
kubectl label ns sec pod-security.kubernetes.io/enforce=restricted --overwrite

# 违规 Pod 被拒绝
kubectl run bad --image=nginx:alpine
# Error from server (Forbidden): pods "bad" is forbidden: violates PodSecurity "restricted:latest":
#   allowPrivilegeEscalation != false, unrestricted capabilities, runAsNonRoot != true,
#   seccompProfile type unset

# 合规 Pod 通过
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: good, namespace: sec}
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 65532
    seccompProfile: {type: RuntimeDefault}
  containers:
    - name: c
      image: gcr.io/distroless/static-debian12:nonroot
      command: ["/bin/sleep"]              # distroless static 没有 sleep，会失败但能创建
      args: ["3600"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities: {drop: ["ALL"]}
EOF
kubectl get pod good -n sec    # 对象创建成功 ✅（容器可能起不来，但准入通过了）
kubectl delete pod good --ignore-not-found
```

### 实验 4：ResourceQuota + LimitRange

```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ResourceQuota
metadata: {name: q, namespace: sec}
spec:
  hard:
    requests.cpu: "1"
    requests.memory: 1Gi
    limits.memory: 2Gi
    pods: "5"
---
apiVersion: v1
kind: LimitRange
metadata: {name: lr, namespace: sec}
spec:
  limits:
    - type: Container
      default: {cpu: 200m, memory: 256Mi}
      defaultRequest: {cpu: 100m, memory: 128Mi}
      max: {cpu: "1", memory: 1Gi}
EOF

kubectl label ns sec pod-security.kubernetes.io/enforce=baseline --overwrite

# 不写 resources，LimitRange 自动填
kubectl run auto --image=nginx:alpine -n sec
kubectl get pod auto -n sec -o jsonpath='{.spec.containers[0].resources}' | jq

# 超过 quota
kubectl run big --image=nginx:alpine -n sec \
  --overrides='{"spec":{"containers":[{"name":"big","image":"nginx:alpine","resources":{"requests":{"cpu":"2"}}}]}}'
# Error: exceeded quota

kubectl describe quota q -n sec
```

### 实验 5：审查危险权限

```bash
# 找出所有绑定了 cluster-admin 的主体
kubectl get clusterrolebindings -o json | \
  jq -r '.items[] | select(.roleRef.name=="cluster-admin") |
         "\(.metadata.name): \([.subjects[]? | "\(.kind)/\(.name)"] | join(", "))"'

# 找出能 exec 进 Pod 的 Role
kubectl get roles,clusterroles -A -o json | \
  jq -r '.items[] | select(.rules[]?.resources[]? == "pods/exec") |
         "\(.kind) \(.metadata.namespace // "cluster")/\(.metadata.name)"'

# 检查默认 SA 是否被过度授权
kubectl get rolebindings,clusterrolebindings -A -o json | \
  jq -r '.items[] | select(.subjects[]?.name == "default") |
         "\(.kind) \(.metadata.namespace // "-")/\(.metadata.name) → \(.roleRef.name)"'
```

### 清理

```bash
kubectl delete ns sec
kubectl config set-context --current --namespace=default
```

---

## 11. 本章检查清单

- [ ] K8s 有"用户"对象吗？人应该怎么认证？
- [ ] `system:masters` 组特殊在哪？
- [ ] 为什么绝大多数 Pod 应该设 `automountServiceAccountToken: false`？
- [ ] `RoleBinding` + `ClusterRole` 的组合是什么语义？
- [ ] 为什么 `create pods` 是危险权限？（这题很关键）
- [ ] RBAC 有 deny 规则吗？多个绑定的权限怎么合并？
- [ ] PSA 的三个级别和三种模式？生产改造应该怎么渐进落地？
- [ ] 满足 `restricted` 需要哪 5 个 securityContext 字段？
- [ ] Kyverno 能做什么 PSA 做不到的事？举 3 个例子
- [ ] Namespace 隔离了什么、没隔离什么？什么时候需要独立集群？
- [ ] 设了 ResourceQuota 的 CPU 项后，为什么必须配 LimitRange？
- [ ] 供应链安全的 6 个环节分别做什么？
- [ ] 审计日志里哪些事件应该告警？
- [ ] 完成实验 1、3、5

---

## 12. 阶段二小结

到这里你应该已经具备：

- ✅ 理解 K8s 的声明式 API 和控制器模式（能自己推导任何资源的行为）
- ✅ 能写出生产级的 Pod/Deployment/StatefulSet 定义并解释每个字段
- ✅ 掌握配置注入、存储、网络、调度、弹性伸缩
- ✅ 能搭建可观测性体系并用它排障
- ✅ 知道怎么把集群配置到安全基线

**自测**：不查文档，从零写出一个包含以下要素的完整清单：
Deployment（3 副本、探针、资源、securityContext、拓扑分布、优雅退出）+ Service + ConfigMap +
Secret 引用 + PDB + HPA + ServiceMonitor + NetworkPolicy。

写完对照第 7、9、10、12、13、14 章检查。能写出来就可以进入阶段三了。

---

## 13. 延伸阅读

- [RBAC 官方文档](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes 安全检查清单](https://kubernetes.io/docs/concepts/security/security-checklist/)
- [kube-bench (CIS Benchmark)](https://github.com/aquasecurity/kube-bench)
- [Kyverno 策略库](https://kyverno.io/policies/)
- [Falco](https://falco.org/)
- [SLSA](https://slsa.dev/) / [Sigstore](https://www.sigstore.dev/)

---

下一章：[15 - Helm：Kubernetes 的包管理器](./15-helm.md)
