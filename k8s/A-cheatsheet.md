# 附录 A - 命令与 YAML 速查

> 打印出来贴在显示器旁边的那种。

---

## 1. kubectl 基础

### 1.1 上下文与命名空间

```bash
kubectl config get-contexts
kubectl config current-context
kubectl config use-context kind-learn
kubectl config set-context --current --namespace=prod
kubectl config view --minify                  # 当前上下文的完整配置

# 用 kubectx/kubens 更快
kubectx                  # 列出并切换集群
kubens prod              # 切换 namespace
```

**推荐的 alias**（放 `~/.zshrc`）：

```bash
alias k=kubectl
alias kg='kubectl get'
alias kd='kubectl describe'
alias kl='kubectl logs'
alias kex='kubectl exec -it'
alias kaf='kubectl apply -f'
alias kdel='kubectl delete'
alias kgp='kubectl get pods -o wide'
alias kgpa='kubectl get pods -A -o wide'
alias kge='kubectl get events --sort-by=.lastTimestamp'
alias kdbg='kubectl debug -it --image=nicolaka/netshoot'
source <(kubectl completion zsh); compdef __start_kubectl k
```

### 1.2 查询

```bash
kubectl get pods                              # 当前 namespace
kubectl get pods -A                           # 所有 namespace
kubectl get pods -o wide                      # 带 IP 和节点
kubectl get pods -o yaml                      # 完整对象
kubectl get pods -o json | jq '.items[].metadata.name'
kubectl get pods -w                           # watch
kubectl get pods --show-labels
kubectl get all                               # 常见资源（不含 configmap/secret/pvc 等）

# 标签选择
kubectl get pods -l app=hello
kubectl get pods -l 'env in (prod,staging)'
kubectl get pods -l '!canary'
kubectl get pods -l 'app=hello,version!=v1'

# 字段选择
kubectl get pods --field-selector status.phase=Running
kubectl get pods --field-selector spec.nodeName=learn-worker
kubectl get events --field-selector type=Warning

# 排序
kubectl get pods --sort-by=.status.startTime
kubectl get pods --sort-by=.metadata.creationTimestamp
kubectl get events --sort-by=.lastTimestamp

# 自定义列 ⭐
kubectl get pods -o custom-columns='NAME:.metadata.name,NODE:.spec.nodeName,IP:.status.podIP,STATUS:.status.phase'
kubectl get pods -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[*].image'
kubectl get nodes -o custom-columns='NAME:.metadata.name,CPU:.status.allocatable.cpu,MEM:.status.allocatable.memory'

# jsonpath
kubectl get pod hello -o jsonpath='{.status.podIP}'
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.nodeName}{"\n"}{end}'
kubectl get deploy hello -o jsonpath='{.spec.template.spec.containers[0].image}'

# 资源类型
kubectl api-resources                         # 所有类型 + 简称
kubectl api-resources --namespaced=false      # 集群级资源
kubectl api-versions
kubectl explain deployment.spec.strategy --recursive    # ⭐ 字段文档
```

### 1.3 创建与修改

```bash
kubectl apply -f manifest.yaml
kubectl apply -f ./dir/                       # 整个目录
kubectl apply -k ./overlays/prod/             # kustomize
kubectl apply --server-side -f m.yaml         # SSA
kubectl apply --dry-run=server -f m.yaml      # 服务端校验不落盘
kubectl diff -f manifest.yaml                 # ⭐ 应用前看差异

kubectl create deployment x --image=nginx --replicas=3
kubectl create ns prod
kubectl create configmap cm --from-literal=K=V --from-file=./f.yaml
kubectl create secret generic s --from-literal=pw=x
kubectl create job j --from=cronjob/nightly    # 手工触发 CronJob

kubectl edit deploy hello                     # 用 $EDITOR 编辑
kubectl patch deploy hello -p '{"spec":{"replicas":5}}'
kubectl patch deploy hello --type=json -p='[{"op":"replace","path":"/spec/replicas","value":5}]'
kubectl set image deploy/hello server=hello:v2
kubectl set env deploy/hello LOG_LEVEL=debug
kubectl set env deploy/hello --from=configmap/cm
kubectl set resources deploy/hello --limits=memory=1Gi --requests=cpu=200m
kubectl scale deploy/hello --replicas=5
kubectl label pod hello tier=frontend --overwrite
kubectl annotate deploy hello kubernetes.io/change-cause="v2"

kubectl delete -f manifest.yaml
kubectl delete pod hello --grace-period=0 --force    # ⚠️ 强删
kubectl delete pods --all -n test
```

### 1.4 生成模板（不记得字段时）

```bash
kubectl run tmp --image=nginx --dry-run=client -o yaml
kubectl create deployment x --image=nginx --dry-run=client -o yaml
kubectl create job j --image=busybox --dry-run=client -o yaml -- sh -c 'echo hi'
kubectl create cronjob c --image=busybox --schedule="*/5 * * * *" --dry-run=client -o yaml -- date
kubectl expose deploy hello --port=80 --target-port=8080 --dry-run=client -o yaml
kubectl create configmap cm --from-literal=a=b --dry-run=client -o yaml
kubectl create role r --verb=get,list --resource=pods --dry-run=client -o yaml
kubectl create rolebinding rb --role=r --user=alice --dry-run=client -o yaml
```

### 1.5 日志与调试

```bash
kubectl logs <pod>
kubectl logs <pod> -c <container>
kubectl logs <pod> --previous                 # ⭐ 崩溃前
kubectl logs <pod> -f --tail=100 --timestamps
kubectl logs <pod> --since=10m
kubectl logs -l app=hello --all-containers --max-log-requests=20
kubectl logs deploy/hello
stern hello -n prod --since 5m                # ⭐ 更好用

kubectl exec -it <pod> -- sh
kubectl exec <pod> -c server -- env
kubectl debug -it <pod> --image=nicolaka/netshoot --target=server    # ⭐ distroless
kubectl debug <pod> --copy-to=dbg --set-image=server=busybox -it -- sh
kubectl debug node/<node> -it --image=busybox

kubectl port-forward pod/<pod> 8080:8080
kubectl port-forward svc/<svc> 8080:80
kubectl port-forward deploy/<deploy> 9090:9090

kubectl cp <pod>:/path/f ./f
kubectl cp ./f <pod>:/tmp/f

kubectl top nodes
kubectl top pods -A --sort-by=memory
kubectl top pod <pod> --containers

kubectl get events --sort-by=.lastTimestamp -A | tail -30
kubectl describe pod <pod>                    # ⭐ Events 在最下面
```

### 1.6 滚动更新

```bash
kubectl rollout status deploy/hello --timeout=300s     # ⭐ CI 里用
kubectl rollout history deploy/hello
kubectl rollout history deploy/hello --revision=3
kubectl rollout undo deploy/hello
kubectl rollout undo deploy/hello --to-revision=2
kubectl rollout restart deploy/hello                   # ⭐ 重启所有 Pod
kubectl rollout pause deploy/hello
kubectl rollout resume deploy/hello
```

### 1.7 节点操作

```bash
kubectl get nodes -o wide
kubectl get nodes --show-labels
kubectl get nodes -L topology.kubernetes.io/zone
kubectl describe node <node>
kubectl label node <node> node-pool=general
kubectl taint node <node> key=value:NoSchedule
kubectl taint node <node> key=value:NoSchedule-        # 去掉（末尾 -）

kubectl cordon <node>                                  # 不再调度新 Pod
kubectl uncordon <node>
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data --timeout=300s
```

### 1.8 权限

```bash
kubectl auth whoami
kubectl auth can-i create deploy -n prod
kubectl auth can-i '*' '*'
kubectl auth can-i list secrets --as=system:serviceaccount:prod:hello -n prod
kubectl auth can-i --list --as=alice -n prod
```

### 1.9 直接访问 API

```bash
kubectl proxy --port=8001
curl localhost:8001/api/v1/namespaces/default/pods

kubectl get --raw /healthz
kubectl get --raw /readyz?verbose
kubectl get --raw /metrics | head
kubectl get --raw /api/v1/nodes | jq -r '.items[].metadata.name'
```

---

## 2. YAML 骨架速查

### 2.1 Deployment（生产模板）

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
  labels:
    app.kubernetes.io/name: hello
spec:
  replicas: 3
  minReadySeconds: 10
  revisionHistoryLimit: 10
  progressDeadlineSeconds: 600
  strategy:
    type: RollingUpdate
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
  selector:
    matchLabels: {app.kubernetes.io/name: hello}
  template:
    metadata:
      labels: {app.kubernetes.io/name: hello}
      annotations:
        checksum/config: "<sha256>"
    spec:
      terminationGracePeriodSeconds: 45
      automountServiceAccountToken: false
      serviceAccountName: hello
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        fsGroup: 65532
        seccompProfile: {type: RuntimeDefault}
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector: {matchLabels: {app.kubernetes.io/name: hello}}
          matchLabelKeys: [pod-template-hash]
      containers:
        - name: server
          image: ghcr.io/org/hello:v1.2.3
          imagePullPolicy: IfNotPresent
          ports:
            - {name: http, containerPort: 8080}
            - {name: metrics, containerPort: 9090}
          env:
            - {name: LOG_LEVEL, value: "info"}
            - name: POD_NAME
              valueFrom: {fieldRef: {fieldPath: metadata.name}}
            - name: DB_PASSWORD
              valueFrom: {secretKeyRef: {name: db, key: password}}
          envFrom:
            - configMapRef: {name: hello-config}
          startupProbe:
            httpGet: {path: /healthz, port: http}
            periodSeconds: 5
            failureThreshold: 30
          livenessProbe:
            httpGet: {path: /healthz, port: http}
            periodSeconds: 10
            timeoutSeconds: 3
          readinessProbe:
            httpGet: {path: /readyz, port: http}
            periodSeconds: 5
            timeoutSeconds: 2
          lifecycle:
            preStop: {sleep: {seconds: 5}}
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {memory: 512Mi}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: ["ALL"]}
          volumeMounts:
            - {name: tmp, mountPath: /tmp}
            - {name: config, mountPath: /etc/app, readOnly: true}
      volumes:
        - name: tmp
          emptyDir: {medium: Memory, sizeLimit: 64Mi}
        - name: config
          configMap: {name: hello-config}
```

### 2.2 Service

```yaml
apiVersion: v1
kind: Service
metadata: {name: hello}
spec:
  type: ClusterIP                 # ClusterIP | NodePort | LoadBalancer | ExternalName
  selector: {app.kubernetes.io/name: hello}
  ports:
    - {name: http, port: 80, targetPort: http, protocol: TCP}
  # clusterIP: None               # headless
  # externalTrafficPolicy: Local  # 保留客户端 IP
  # sessionAffinity: ClientIP
```

### 2.3 StatefulSet

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata: {name: db}
spec:
  serviceName: db-headless
  replicas: 3
  podManagementPolicy: OrderedReady        # 或 Parallel
  updateStrategy:
    type: RollingUpdate
    rollingUpdate: {partition: 0}
  persistentVolumeClaimRetentionPolicy:
    whenDeleted: Retain
    whenScaled: Retain
  selector: {matchLabels: {app: db}}
  template: {...}
  volumeClaimTemplates:
    - metadata: {name: data}
      spec:
        accessModes: [ReadWriteOnce]
        storageClassName: fast-ssd
        resources: {requests: {storage: 100Gi}}
```

### 2.4 其他常用对象

```yaml
# ConfigMap
apiVersion: v1
kind: ConfigMap
metadata: {name: cfg}
immutable: false
data:
  KEY: value
  app.yaml: |
    server: {port: 8080}
---
# Secret
apiVersion: v1
kind: Secret
metadata: {name: sec}
type: Opaque
stringData: {password: s3cr3t}
---
# PVC
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: data}
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard
  resources: {requests: {storage: 10Gi}}
---
# PDB
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: hello}
spec:
  maxUnavailable: 1
  selector: {matchLabels: {app.kubernetes.io/name: hello}}
  unhealthyPodEvictionPolicy: AlwaysAllow
---
# HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {name: hello}
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: hello}
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource: {name: cpu, target: {type: Utilization, averageUtilization: 70}}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies: [{type: Percent, value: 25, periodSeconds: 60}]
---
# Job
apiVersion: batch/v1
kind: Job
metadata: {name: migrate}
spec:
  backoffLimit: 3
  activeDeadlineSeconds: 600
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: OnFailure
      containers: [{name: m, image: app:v1, command: ["/migrate"]}]
---
# CronJob
apiVersion: batch/v1
kind: CronJob
metadata: {name: nightly}
spec:
  schedule: "0 2 * * *"
  timeZone: "Asia/Shanghai"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  jobTemplate: {spec: {...}}
---
# NetworkPolicy（default deny + 放行 DNS）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: default-deny}
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
  egress:
    - to:
        - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}
          podSelector: {matchLabels: {k8s-app: kube-dns}}
      ports: [{protocol: UDP, port: 53}, {protocol: TCP, port: 53}]
---
# ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata: {name: hello, labels: {release: monitoring}}
spec:
  selector: {matchLabels: {app.kubernetes.io/name: hello}}
  endpoints: [{port: metrics, interval: 30s}]
---
# Gateway API HTTPRoute
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata: {name: hello}
spec:
  parentRefs: [{name: main-gateway, namespace: infra}]
  hostnames: ["hello.example.com"]
  rules:
    - matches: [{path: {type: PathPrefix, value: /}}]
      backendRefs:
        - {name: hello, port: 80, weight: 90}
        - {name: hello-canary, port: 80, weight: 10}
```

---

## 3. Docker / 镜像

```bash
docker build -t app:v1 .
docker build --build-arg VERSION=v1 --no-cache -t app:v1 .
docker buildx build --platform linux/amd64,linux/arm64 -t app:v1 --push .
docker buildx imagetools inspect app:v1

docker run -d --name x -p 8080:80 -e K=V -v vol:/data --memory=512m --cpus=1 app:v1
docker run --rm -it --network=container:x nicolaka/netshoot
docker exec -it x sh
docker logs -f --tail=100 x
docker stats
docker inspect x -f '{{.State.Pid}}'
docker stop -t 30 x

docker images; docker system df; docker system prune -a --volumes
docker history --no-trunc app:v1
docker save app:v1 | gzip > app.tgz

trivy image --severity HIGH,CRITICAL app:v1
cosign sign --key k.key ghcr.io/org/app:v1
```

---

## 4. Helm（v4）

```bash
helm create c; helm lint ./c
helm template rel ./c -f values-prod.yaml            # ⭐ 本地渲染
helm install rel ./c -n ns --create-namespace -f v.yaml
helm upgrade --install rel ./c -n ns -f v.yaml \
  --set image.tag=v1.2.3 --wait --timeout 10m --rollback-on-failure
helm diff upgrade rel ./c -f v.yaml                  # 需要 helm-diff 插件

helm list -A
helm status rel -n ns
helm get manifest rel -n ns                          # ⭐ 实际部署的 YAML
helm get values rel -n ns --all
helm history rel -n ns
helm rollback rel 3 -n ns
helm uninstall rel -n ns

helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm search repo postgres
helm show values bitnami/postgresql                  # ⭐ 看有哪些参数
helm pull bitnami/postgresql --untar

helm package ./c
helm registry login ghcr.io                          # ⚠️ v4.1+ 不写 https://
helm push c-0.1.0.tgz oci://ghcr.io/org/charts
helm dependency update ./c
```

**Helm 4 变化**：`--atomic` → `--rollback-on-failure`；`--force` → `--force-replace`；
post-renderer 必须是插件；`--wait` 需要 `watch` 权限。

---

## 5. Kustomize

```bash
kubectl kustomize ./overlays/prod              # 渲染
kubectl apply -k ./overlays/prod
kubectl diff -k ./overlays/prod
kubectl delete -k ./overlays/prod
kustomize build --enable-helm .                # Helm + Kustomize 组合
```

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: prod
namePrefix: prod-
resources: [../../base, hpa.yaml]
images:
  - {name: app, newName: ghcr.io/org/app, newTag: v1.2.3}
replicas:
  - {name: app, count: 6}
labels:
  - pairs: {env: prod}
    includeSelectors: false
configMapGenerator:
  - name: cfg
    literals: [LOG_LEVEL=warn]
patches:
  - path: patch.yaml
    target: {kind: Deployment, name: app}
components: [../../components/monitoring]
```

---

## 6. Argo CD

```bash
argocd login <host> --username admin --password <pw> --insecure
argocd app list
argocd app create x --repo <url> --path <p> --dest-server https://kubernetes.default.svc \
  --dest-namespace ns --sync-policy automated --auto-prune --self-heal \
  --sync-option CreateNamespace=true
argocd app get x
argocd app diff x                              # ⭐
argocd app sync x
argocd app sync x --prune --force
argocd app wait x --health --timeout 600
argocd app history x
argocd app rollback x <id>
argocd app delete x --cascade
argocd app set x --helm-set image.tag=v2

argocd cluster add <ctx> --name prod --label env=production
argocd cluster list
argocd repo add <url> --ssh-private-key-path ~/.ssh/id_ed25519
argocd proj list

kubectl -n argocd logs deploy/argocd-application-controller --tail=100
kubectl -n argocd logs deploy/argocd-repo-server --tail=100
```

---

## 7. Argo Rollouts

```bash
kubectl argo rollouts get rollout hello --watch      # ⭐ 最常用
kubectl argo rollouts set image hello server=app:v2
kubectl argo rollouts promote hello
kubectl argo rollouts promote hello --full
kubectl argo rollouts abort hello                   # ⭐ 中止并回滚
kubectl argo rollouts undo hello
kubectl argo rollouts pause hello
kubectl argo rollouts status hello
kubectl argo rollouts dashboard                     # localhost:3100
kubectl get analysisrun; kubectl describe analysisrun <n>
```

---

## 8. 常用 PromQL

```promql
# QPS
sum(rate(http_requests_total[5m])) by (service)

# 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
  / sum(rate(http_requests_total[5m])) by (service)

# P99 延迟
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))

# 内存使用 vs limit
sum(container_memory_working_set_bytes{container!=""}) by (pod)
  / sum(kube_pod_container_resource_limits{resource="memory"}) by (pod)

# CPU 节流率
sum(rate(container_cpu_cfs_throttled_periods_total[5m])) by (pod)
  / sum(rate(container_cpu_cfs_periods_total[5m])) by (pod)

# 重启次数
sum(increase(kube_pod_container_status_restarts_total[1h])) by (namespace, pod)

# 副本不足
kube_deployment_status_replicas_available < kube_deployment_spec_replicas

# 集群分配率
sum(kube_pod_container_resource_requests{resource="cpu"})
  / sum(kube_node_status_allocatable{resource="cpu"})

# 集群利用率
sum(rate(container_cpu_usage_seconds_total{container!=""}[5m]))
  / sum(kube_node_status_allocatable{resource="cpu"})

# PVC 使用率
kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes

# apiserver 压力来源
topk(10, sum(rate(apiserver_request_total[5m])) by (client, resource, verb))

# 高基数指标排查
topk(20, count by (__name__)({__name__=~".+"}))
```

---

## 9. 排障一条龙

```bash
# ① 全局扫一眼
kubectl get nodes
kubectl get pods -A | grep -Ev "Running|Completed"
kubectl get events -A --sort-by=.lastTimestamp | tail -20
kubectl top nodes

# ② 定位到具体 Pod
kubectl describe pod <pod>              # ⭐ Events
kubectl logs <pod> --previous
kubectl get pod <pod> -o yaml | grep -A10 "state:\|conditions:"

# ③ 网络
kubectl get endpointslices -l kubernetes.io/service-name=<svc>
kubectl run -it --rm t --image=nicolaka/netshoot --restart=Never -- bash
  # nslookup <svc> / curl <pod-ip>:<port> / ss -tlnp / dig / tcpdump

# ④ 资源
kubectl exec <pod> -- cat /sys/fs/cgroup/memory.max
kubectl exec <pod> -- cat /sys/fs/cgroup/cpu.stat
kubectl top pod <pod> --containers

# ⑤ 节点
kubectl describe node <node> | grep -A15 Conditions
docker exec <node> journalctl -u kubelet -n 100 --no-pager
docker exec <node> crictl ps -a
docker exec <node> df -h
```

---

## 10. kind 集群

```bash
kind create cluster --config kind.yaml --name learn
kind get clusters
kind get nodes --name learn
kind load docker-image app:v1 --name learn        # ⭐ 把本地镜像塞进集群
kind delete cluster --name learn
kind export logs ./logs --name learn              # 导出所有日志用于排查

docker exec learn-worker crictl ps
docker exec learn-worker crictl images
docker exec learn-worker crictl logs <container-id>
```

---

## 11. 退出码速查

| 码 | 含义 |
|---|---|
| 0 | 正常退出 |
| 1 | 通用错误 |
| 2 | shell 用法错误 |
| 126 | 命令不可执行（权限） |
| 127 | **命令不存在**（distroless 里写了 sh） |
| 128+n | 被信号 n 终止 |
| **137** | 128+9 = **SIGKILL**（OOMKilled 或宽限期超时） |
| 139 | 128+11 = SIGSEGV |
| **143** | 128+15 = SIGTERM（正常终止） |

---

## 12. Pod 状态速查

| 状态 | 含义 | 去哪查 |
|---|---|---|
| `Pending` | 未调度或未启动 | `describe pod` 的 Events |
| `ContainerCreating` | 正在拉镜像/挂卷/配网 | 同上 |
| `Running` | 至少一个容器在跑（**不等于可用**） | 看 Ready 列 |
| `0/1 Ready` | readiness 失败 | `describe` 的 Readiness 事件 |
| `CrashLoopBackOff` | 反复崩溃，正在退避 | `logs --previous` |
| `ImagePullBackOff` | 拉不到镜像 | Events |
| `ErrImageNeverPull` | `imagePullPolicy: Never` 但本地没有 | — |
| `CreateContainerConfigError` | ConfigMap/Secret 不存在 | Events |
| `CreateContainerError` | 命令/入口有问题 | Events |
| `Init:0/2` | init 容器在跑 | `logs -c <init>` |
| `Init:Error` | init 容器失败 | 同上 |
| `Completed` | 正常退出（Job） | — |
| `Error` | 非零退出 | `logs` |
| `Evicted` | 被节点驱逐 | `describe` 的 Message |
| `Terminating` | 正在删除 | finalizer / 宽限期 |
| `OOMKilled` | 内存超限 | `describe` 的 Last State |
| `NodeLost` / `Unknown` | 节点失联 | 看节点 |

---

[← 返回课程总览](./README.md) · [附录 B - 术语表](./B-glossary.md)
