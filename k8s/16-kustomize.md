# 16 - Kustomize 与配置管理选型

> 本章目标：掌握另一条配置管理路线——**无模板的叠加**，并学会在 Helm / Kustomize / 两者组合之间做选择。
> 预计用时：1.5 小时。

---

## 1. 另一条路线

Helm 的思路是"模板 + 变量"，问题是：**模板不是合法的 YAML**。

```gotemplate
{{- if .Values.autoscaling.enabled }}
replicas: {{ .Values.replicaCount }}
{{- end }}
```

这段文本没法用 YAML 工具解析、编辑器不能校验、`kubectl explain` 帮不上忙。复杂 chart 的模板可读性会急剧下降。

**Kustomize 的思路**：所有文件都是**合法的、完整的 YAML**，环境差异通过"打补丁"表达。

```
base/                    ← 完整可用的 YAML
  deployment.yaml
  service.yaml
overlays/
  dev/                   ← 只写"和 base 的差异"
    kustomization.yaml
    patch-replicas.yaml
  prod/
    kustomization.yaml
    patch-resources.yaml
```

Kustomize **内置在 kubectl 里**（`kubectl apply -k`），也有独立 CLI。

---

## 2. base / overlay 模型

### 2.1 base

```yaml
# base/deployment.yaml —— 完整的、能直接 apply 的 YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
spec:
  replicas: 2
  selector:
    matchLabels: {app: hello}
  template:
    metadata:
      labels: {app: hello}
    spec:
      terminationGracePeriodSeconds: 45
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: server
          image: hello           # ⭐ 不写 tag，由 overlay 用 images 指定
          ports: [{name: http, containerPort: 8080}]
          readinessProbe:
            httpGet: {path: /readyz, port: http}
            periodSeconds: 5
          livenessProbe:
            httpGet: {path: /healthz, port: http}
            periodSeconds: 10
          lifecycle:
            preStop: {sleep: {seconds: 5}}
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {memory: 512Mi}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: ["ALL"]}
          volumeMounts: [{name: tmp, mountPath: /tmp}]
      volumes:
        - name: tmp
          emptyDir: {medium: Memory, sizeLimit: 64Mi}
```

```yaml
# base/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: hello
spec:
  selector: {app: hello}
  ports: [{name: http, port: 80, targetPort: http}]
```

```yaml
# base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
commonLabels:
  app.kubernetes.io/name: hello
  app.kubernetes.io/managed-by: kustomize
```

```bash
kubectl kustomize base/          # 渲染看看
kubectl apply -k base/           # 直接部署
```

### 2.2 overlay

```yaml
# overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: prod
namePrefix: prod-
nameSuffix: ""

resources:
  - ../../base
  - hpa.yaml                     # overlay 独有的资源
  - pdb.yaml

labels:                          # 新写法（commonLabels 已弃用）
  - pairs:
      environment: production
      team: backend
    includeSelectors: false      # ⚠️ 不要加到 selector 里（selector 不可变）

commonAnnotations:
  owner: backend-team

# ⭐ 统一改镜像 tag —— CI 里最常用的一条
images:
  - name: hello
    newName: ghcr.io/yourorg/hello
    newTag: v1.2.3
    # digest: sha256:abc...      # 或用 digest

replicas:
  - name: hello
    count: 6

patches:
  - path: patch-resources.yaml
    target: {kind: Deployment, name: hello}
  - path: patch-env.yaml

configMapGenerator:
  - name: hello-config
    literals:
      - LOG_LEVEL=warn
      - GREETING=hello from prod
    # files:
    #   - app.yaml=configs/app-prod.yaml

secretGenerator:
  - name: hello-secret
    envs: [secrets.env]          # ⚠️ 明文文件，实际生产用 External Secrets

generatorOptions:
  disableNameSuffixHash: false   # ⭐ 保持 false！见 §4
```

### 2.3 两种补丁写法

**① Strategic Merge Patch（推荐，直观）**

```yaml
# overlays/prod/patch-resources.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello                    # 用 name+kind 定位目标
spec:
  template:
    spec:
      containers:
        - name: server           # ⭐ 靠 name 匹配数组元素（merge key）
          resources:
            requests: {cpu: 500m, memory: 512Mi}
            limits: {memory: 2Gi}
          env:
            - name: LOG_LEVEL
              value: warn
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels: {app: hello}
```

**② JSON 6902 Patch（精确操作，能删除）**

```yaml
patches:
  - target:
      kind: Deployment
      name: hello
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 6
      - op: add
        path: /spec/template/spec/containers/0/env/-
        value: {name: EXTRA, value: "1"}
      - op: remove
        path: /spec/template/spec/containers/0/livenessProbe
```

**选择**：
- 加字段、改字段 → Strategic Merge（可读性好）
- 删字段、精确操作数组下标 → JSON 6902

⚠️ **数组的合并语义**：Strategic Merge 对 `containers` 这类有 `patchMergeKey` 的数组是按 key 合并，
对 `env`、`args`、`command` 这类**没有明确 merge key 的数组是整体替换**。不确定就 `kubectl kustomize` 渲染出来看。

```bash
kubectl kustomize overlays/prod/
kubectl apply -k overlays/prod/
kubectl diff -k overlays/prod/        # ⭐ 部署前看差异
```

---

## 3. Components：可复用的功能片段

overlay 是"环境"维度，**Component 是"功能"维度**——多个环境可以按需组合同一组功能。

```yaml
# components/monitoring/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component
resources:
  - servicemonitor.yaml
patches:
  - target: {kind: Deployment}
    patch: |-
      - op: add
        path: /spec/template/spec/containers/0/ports/-
        value: {name: metrics, containerPort: 9090}
```

```yaml
# overlays/prod/kustomization.yaml
components:
  - ../../components/monitoring
  - ../../components/istio-injection
  - ../../components/high-availability
```

这解决了 overlay 的组合爆炸问题（`prod × 带监控 × 高可用` 不需要单独建目录）。

---

## 4. 生成器与名字哈希（⭐ Kustomize 的杀手锏）

```yaml
configMapGenerator:
  - name: hello-config
    literals: [LOG_LEVEL=debug]
```

渲染结果：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hello-config-9f6b8cc4m2      # ⭐ 名字带内容哈希
---
# 引用它的地方自动改名
        envFrom:
          - configMapRef:
              name: hello-config-9f6b8cc4m2
```

**这就自动解决了第 8 章的问题**：ConfigMap 内容变 → 哈希变 → 名字变 → Deployment 的 template 变 → **自动触发滚动更新**。

Helm 需要手写 `checksum/config` annotation 才能做到，Kustomize 是内建的。

⚠️ 除非有特殊理由，**不要设 `disableNameSuffixHash: true`**——那样就失去了这个能力。

⚠️ 副作用：ConfigMap 会越积越多（每个版本一个）。需要定期清理，或者依赖 GitOps 工具的 prune（第 18 章 Argo CD 会自动删除不再被引用的资源）。

---

## 5. Helm vs Kustomize

| 维度 | Helm | Kustomize |
|---|---|---|
| **范式** | 模板 + 变量 | 完整 YAML + 补丁 |
| **文件是合法 YAML** | ❌ | ✅ |
| **学习曲线** | 中（要学模板语法） | 低（但补丁语义有坑） |
| **表达能力** | 强（循环、条件、函数） | 弱（无循环无条件） |
| **打包分发** | ✅ 仓库、版本、依赖 | ❌ 只能靠 git ref / OCI |
| **给第三方用** | ✅ 参数化接口清晰 | ❌ 用户要读懂你的结构才能改 |
| **release 管理** | ✅ 历史、回滚、状态 | ❌ 无（靠 kubectl / GitOps 工具） |
| **配置变更触发滚动更新** | 手写 checksum | ✅ 内建名字哈希 |
| **安装** | 单独安装 | ✅ 内置于 kubectl |
| **调试** | `helm template` | `kubectl kustomize` |
| **多环境** | 多个 values 文件 | base + overlay |
| **谁在用** | 几乎所有开源软件的分发格式 | 大量企业内部服务、Argo CD 生态 |

### 选择建议

| 场景 | 推荐 |
|---|---|
| **安装第三方软件**（Prometheus、cert-manager、Argo CD） | **Helm**（人家就是这么发布的） |
| **自己团队的几十个微服务** | **Kustomize** 或 **统一 Helm chart + 每服务只有 values** |
| **要发布给外部用户的软件** | **Helm**（参数化接口 + 版本 + 仓库） |
| **配置差异主要是"改几个字段"** | Kustomize |
| **配置差异涉及"要不要这个资源、循环生成 N 个" ** | Helm |
| **已经在用 Argo CD** | 两者都原生支持，看团队偏好 |

**我的实际建议**：
- 第三方组件用 Helm（别自己造轮子）
- 自研服务，如果服务数量少（< 10）用 Helm，多了用"通用 chart + values"或 Kustomize
- **不要在同一个仓库里混用两套心智模型**，除非用下面的组合方式

---

## 6. 组合使用：Helm 渲染 + Kustomize 打补丁

有时第三方 chart 没有暴露你需要的参数（比如给某个 Deployment 加个 sidecar、改个不支持的字段）。这时可以：

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
helmGlobals:
  chartHome: ./charts
helmCharts:
  - name: kube-prometheus-stack
    repo: https://prometheus-community.github.io/helm-charts
    version: 68.x.x
    releaseName: monitoring
    namespace: monitoring
    valuesFile: values-prod.yaml
patches:
  - path: patch-prometheus-retention.yaml
    target: {kind: Prometheus, name: monitoring-kube-prometheus-prometheus}
```

```bash
kubectl kustomize --enable-helm .
```

**流程**：Kustomize 先调 `helm template` 渲染 chart，再对渲染结果打补丁。

Argo CD 也支持这个组合（第 18 章）。

⚠️ 代价：失去了 Helm 的 release 管理（history、rollback），因为最终是 `kubectl apply`。在 GitOps 下这不是问题（回滚 = git revert）。

---

## 7. 动手实验

### 实验 1：搭建 base + overlay

```bash
mkdir -p ~/lab/kustomize/{base,overlays/dev,overlays/prod}
cd ~/lab/kustomize
```

按 §2 创建 `base/deployment.yaml`、`base/service.yaml`、`base/kustomization.yaml`。

```yaml
# overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: k-dev
namePrefix: dev-
resources: [../../base]
images:
  - name: hello
    newTag: v0.1.0
replicas:
  - {name: hello, count: 1}
configMapGenerator:
  - name: hello-config
    literals: [LOG_LEVEL=debug, GREETING=DEV]
patches:
  - target: {kind: Deployment}
    patch: |-
      - op: add
        path: /spec/template/spec/containers/0/envFrom
        value: [{configMapRef: {name: hello-config}}]
      - op: replace
        path: /spec/template/spec/containers/0/imagePullPolicy
        value: IfNotPresent
```

```yaml
# overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: k-prod
namePrefix: prod-
resources: [../../base]
images:
  - name: hello
    newTag: v0.1.0
replicas:
  - {name: hello, count: 4}
configMapGenerator:
  - name: hello-config
    literals: [LOG_LEVEL=warn, GREETING=PROD]
labels:
  - pairs: {environment: production}
    includeSelectors: false
patches:
  - target: {kind: Deployment}
    patch: |-
      - op: add
        path: /spec/template/spec/containers/0/envFrom
        value: [{configMapRef: {name: hello-config}}]
      - op: replace
        path: /spec/template/spec/containers/0/imagePullPolicy
        value: IfNotPresent
      - op: replace
        path: /spec/template/spec/containers/0/resources/requests/cpu
        value: 300m
```

```bash
# 渲染对比
diff <(kubectl kustomize overlays/dev) <(kubectl kustomize overlays/prod)

# 部署
kubectl create ns k-dev; kubectl create ns k-prod
kubectl apply -k overlays/dev
kubectl apply -k overlays/prod
kubectl get all -n k-dev
kubectl get all -n k-prod
```

### 实验 2：⭐ 名字哈希自动触发滚动更新

```bash
kubectl -n k-prod get cm
# prod-hello-config-<hash>
kubectl -n k-prod get rs

# 改 ConfigMap 内容
sed -i '' 's/GREETING=PROD/GREETING=PROD-v2/' overlays/prod/kustomization.yaml
kubectl diff -k overlays/prod | head -30      # ⭐ 看到 ConfigMap 名字变了，Deployment 也变了
kubectl apply -k overlays/prod

kubectl -n k-prod get cm                       # 新的哈希名（旧的还在）
kubectl -n k-prod get rs                       # ⭐ 新的 ReplicaSet —— 自动滚动更新了！
kubectl -n k-prod rollout status deploy/prod-hello
```

**对比 Helm**：Helm 需要手写 `checksum/config` 才能做到，Kustomize 是免费的。

### 实验 3：Component

```bash
mkdir -p ~/lab/kustomize/components/debug
cat > ~/lab/kustomize/components/debug/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component
patches:
  - target: {kind: Deployment}
    patch: |-
      - op: add
        path: /spec/template/spec/containers/0/env
        value:
          - {name: DEBUG, value: "true"}
          - {name: PPROF_ENABLED, value: "true"}
EOF

# 在 dev overlay 里启用
echo 'components: [../../components/debug]' >> overlays/dev/kustomization.yaml
kubectl kustomize overlays/dev | grep -A4 "env:"
```

### 实验 4：Helm + Kustomize 组合

```bash
mkdir -p ~/lab/kustomize/helm-combo && cd ~/lab/kustomize/helm-combo
cat > kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: combo
helmCharts:
  - name: podinfo
    repo: https://stefanprodan.github.io/podinfo
    version: 6.x.x
    releaseName: demo
patches:
  - target: {kind: Deployment}
    patch: |-
      - op: add
        path: /spec/template/metadata/annotations
        value: {patched-by: kustomize}
EOF

kubectl kustomize --enable-helm . | grep -B2 -A2 "patched-by"
```

### 清理

```bash
kubectl delete ns k-dev k-prod --ignore-not-found
```

---

## 8. 本章检查清单

- [ ] Kustomize 和 Helm 的根本范式区别是什么？
- [ ] base 和 overlay 各自放什么？
- [ ] Strategic Merge Patch 和 JSON 6902 Patch 分别适合什么场景？
- [ ] `containers` 数组和 `env` 数组的合并语义有什么不同？
- [ ] Component 解决 overlay 的什么问题？
- [ ] `configMapGenerator` 的名字哈希解决了什么问题？为什么不要关掉它？
- [ ] `labels` 的 `includeSelectors: false` 为什么重要？
- [ ] 什么场景该用 Helm、什么场景该用 Kustomize？
- [ ] Helm + Kustomize 组合的流程是什么？代价是什么？
- [ ] 完成实验 1、2

---

## 9. 延伸阅读

- [Kustomize 官方文档](https://kubectl.docs.kubernetes.io/references/kustomize/)
- [Kustomize 示例](https://github.com/kubernetes-sigs/kustomize/tree/master/examples)
- [SIG CLI 的 Kustomize 指南](https://kubectl.docs.kubernetes.io/guides/)

---

下一章：[17 - Jenkins 与持续集成](./17-jenkins-ci.md)
