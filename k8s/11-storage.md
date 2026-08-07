# 11 - 存储：Volume、PV、PVC 与 CSI

> 本章目标：搞清楚 K8s 里的"文件系统"——临时数据放哪、持久数据怎么存、Pod 漂移时数据怎么跟着走、
> 怎么扩容和迁移。这是有状态服务的地基。
> 预计用时：2.5 小时（含实验）。

---

## 1. 问题背景

回顾第 2 章：容器的可写层是 **ephemeral（临时）** 的——容器删除，数据就没了。而 K8s 里 Pod 被删除重建是**常态**（滚动更新、节点维护、驱逐、扩缩容）。

所以任何需要活过 Pod 生命周期的数据，都必须放在 **Volume** 里。

K8s 的存储抽象要解决三个问题：

1. **解耦**：应用不该知道底层是 AWS EBS 还是 Ceph 还是本地盘
2. **跟随**：Pod 漂移到另一个节点时，数据要能跟着挂过去
3. **生命周期**：谁创建存储、谁销毁、Pod 删了数据要不要留

---

## 2. Volume：Pod 级别的存储

Volume 挂在 **Pod** 上，Pod 内多个容器可以挂载同一个 Volume（这是容器间共享文件的唯一方式）。

### 2.1 常用 Volume 类型

| 类型 | 生命周期 | 用途 |
|---|---|---|
| **emptyDir** | 与 **Pod** 同生命周期（Pod 删除即销毁，容器重启不丢） | 临时文件、容器间共享、缓存 |
| **configMap / secret** | 跟随对象 | 配置注入（第 8 章） |
| **downwardAPI** | 跟随 Pod | 元数据注入（第 8 章） |
| **projected** | 跟随 Pod | 多来源合并 |
| **persistentVolumeClaim** ⭐ | **独立于 Pod** | 持久化数据 |
| **hostPath** | 节点上的目录 | ⚠️ 危险，仅限系统组件 |
| **local** | 节点本地盘（通过 PV） | 高性能本地存储，有节点亲和性 |
| **csi**（临时卷） | 跟随 Pod | 密钥挂载（Secrets Store CSI）等 |
| **image**（1.33+） | 跟随 Pod | 把 OCI 镜像当只读卷挂载（模型文件、静态资源） |

### 2.2 emptyDir

```yaml
volumes:
  - name: cache
    emptyDir:
      sizeLimit: 1Gi           # 超过会被驱逐（算 ephemeral-storage）
  - name: shm
    emptyDir:
      medium: Memory           # ⭐ 用 tmpfs（内存），速度快但计入容器内存 limit！
      sizeLimit: 256Mi
```

**要点**：
- 容器**重启**不丢（还是同一个 Pod），Pod **删除**才丢
- `medium: Memory` 的用量**计入 Pod 的内存 limit**——写 1GB 文件会导致 OOMKill
- 常见用途：`/tmp`（配合 `readOnlyRootFilesystem: true`）、sidecar 与主容器共享日志目录、`/dev/shm`（很多程序默认 64MB 不够）

### 2.3 hostPath：⚠️ 请不要用

```yaml
volumes:
  - name: docker-sock
    hostPath:
      path: /var/run/docker.sock
      type: Socket             # DirectoryOrCreate | Directory | FileOrCreate | File | Socket
```

**为什么危险**：
- **权限逃逸**：挂载 `/`、`/var/run/docker.sock`、`/etc/kubernetes` 等价于拿到节点 root
- **不可移植**：Pod 调度到另一个节点，那里没有这个目录（或内容不同）
- **无容量管理**：写满节点磁盘会导致整个节点上的所有 Pod 被驱逐

**合法用途只有系统组件**：日志采集（读 `/var/log/pods`）、node-exporter（读 `/proc`、`/sys`）、CNI/CSI 插件。

业务 Pod 想用本地盘 → 用 **local PV**（有节点亲和性、有容量管理）或 **generic ephemeral volume**。

---

## 3. PV / PVC / StorageClass：持久化三件套

### 3.1 概念与分工

```
   开发者                          集群管理员                 存储系统
      │                                │                         │
  ┌───▼────┐   绑定    ┌──────────┐    │    ┌─────────────┐      │
  │  PVC   │◄────────►│    PV    │◄───┼────│StorageClass │      │
  │"我要   │           │"这里有   │    │    │"用什么类型  │      │
  │ 10Gi   │           │ 10Gi 的  │    │    │ 的存储、    │──────┘
  │ 读写卷"│           │ 实际存储"│    │    │ 怎么创建"   │  动态创建
  └────────┘           └──────────┘    │    └─────────────┘
   命名空间级            集群级          │      集群级
```

| 对象 | 谁创建 | 作用 | 类比 |
|---|---|---|---|
| **PersistentVolume (PV)** | 管理员，或由 StorageClass 动态创建 | 一块真实存储的抽象 | 一块硬盘 |
| **PersistentVolumeClaim (PVC)** | 应用开发者 | "我需要一块多大、什么访问模式的存储" | 申请单 |
| **StorageClass (SC)** | 管理员 | "这类存储怎么动态创建" | 硬盘型号目录 |

**为什么要分成 PVC 和 PV 两个对象？** 因为它们属于不同角色：开发者写 PVC（跟着应用走，进 Git），管理员管 PV 和 SC（跟着集群走）。开发者不需要知道底层是 EBS 还是 Ceph。

### 3.2 动态供给（现代的标准做法）

现在几乎不用手工创建 PV 了：

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: hello-data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard        # 不写则用默认 SC
  resources:
    requests:
      storage: 10Gi
```

```bash
kubectl apply -f pvc.yaml
kubectl get pvc,pv
# PVC 状态 Bound，PV 由 CSI driver 自动创建
```

流程：

```
① 创建 PVC（Pending）
② PV 控制器看到 PVC，找它的 StorageClass
③ SC 指定的 CSI provisioner 去后端创建一块真实存储（如调 AWS API 创建 EBS 卷）
④ 创建对应的 PV 对象，与 PVC 绑定（Bound）
⑤ Pod 调度到某节点
⑥ CSI attach：把卷挂到节点（云盘要 attach 到 EC2）
⑦ CSI mount：格式化（首次）并挂载到节点目录
⑧ kubelet 把节点目录 bind mount 进容器
```

### 3.3 StorageClass

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"   # 默认 SC
provisioner: ebs.csi.aws.com
parameters:                        # ⭐ 每个 provisioner 的参数不同
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
  csi.storage.k8s.io/fstype: ext4
reclaimPolicy: Delete              # ⭐ Delete | Retain
allowVolumeExpansion: true         # ⭐ 允许扩容（一定要开！）
volumeBindingMode: WaitForFirstConsumer   # ⭐ 见下
mountOptions:
  - noatime
```

**三个关键参数**：

**① `reclaimPolicy`（PVC 删除后 PV 怎么办）**

| 值 | 行为 |
|---|---|
| `Delete`（动态供给默认） | 删 PVC → 删 PV → **删除底层真实存储（数据永久丢失）** |
| `Retain` | 删 PVC → PV 变 `Released` 状态，**数据保留**，需要管理员手工处理 |

⚠️ **生产数据库一定要用 `Retain`**。误删一个 PVC 就丢掉全部数据的事故非常常见。

**② `volumeBindingMode`**

| 值 | 行为 |
|---|---|
| `Immediate` | PVC 一创建就立刻创建并绑定 PV |
| `WaitForFirstConsumer` ⭐ | 等到有 Pod 使用这个 PVC 时才创建 PV |

**为什么 `WaitForFirstConsumer` 几乎总是更好**：云盘是**有可用区的**。如果 PV 先在 zone-a 创建了，而调度器后来把 Pod 调度到 zone-b 的节点，就会永久卡住（`volume node affinity conflict`）。等 Pod 调度完再创建卷，就能创建在正确的可用区。

**③ `allowVolumeExpansion: true`**——不开的话以后想扩容只能迁移数据，非常痛苦。

```bash
kubectl get sc
kubectl describe sc standard
```

### 3.4 访问模式（AccessModes）

| 模式 | 简写 | 含义 | 支持的存储 |
|---|---|---|---|
| `ReadWriteOnce` | RWO | **单节点**读写（该节点上可以有多个 Pod） | 块存储：EBS、云盘、Ceph RBD、local |
| `ReadOnlyMany` | ROX | 多节点只读 | 文件存储、对象存储 |
| `ReadWriteMany` | RWX | **多节点**读写 | 文件存储：NFS、EFS、CephFS、Longhorn |
| `ReadWriteOncePod` | RWOP | **单个 Pod**独占读写（1.29 GA） | CSI driver 支持即可 |

⚠️ **最常见的误解**：`ReadWriteOnce` 不是"只能一个 Pod 用"，而是"只能一个**节点**挂载"。同节点上的多个 Pod 可以同时用同一个 RWO 卷。要真正独占用 `ReadWriteOncePod`。

**这决定了你的架构**：
- 用 RWO 云盘 + Deployment 多副本 → 副本被调度到不同节点时会挂载失败（Pod 卡 `ContainerCreating`）
- 需要多副本共享同一份数据 → 必须用 RWX（NFS/EFS/CephFS），但性能和一致性要仔细评估
- **更好的架构**：不要多个副本共享文件系统。用对象存储（S3）或数据库来共享状态

### 3.5 PV 的完整定义（手工创建时）

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-manual-001
spec:
  capacity: {storage: 10Gi}
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  volumeMode: Filesystem            # 或 Block（裸块设备，数据库可能要）
  nodeAffinity:                     # local PV 必须有
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - {key: kubernetes.io/hostname, operator: In, values: [learn-worker]}
  local:
    path: /mnt/disks/ssd1
  # 或者其他后端：
  # nfs: {server: 10.0.0.5, path: /exports/data}
  # csi: {driver: ebs.csi.aws.com, volumeHandle: vol-abc123}
```

**PV 的状态**：

| 状态 | 含义 |
|---|---|
| `Available` | 空闲，可被绑定 |
| `Bound` | 已绑定到某个 PVC |
| `Released` | PVC 被删了，但 PV 还没被回收（`Retain` 策略下停在这里） |
| `Failed` | 自动回收失败 |

⚠️ `Released` 状态的 PV **不能直接被新 PVC 绑定**（它还记着旧 PVC 的 UID）。要复用得手工编辑，清掉 `spec.claimRef`：

```bash
kubectl patch pv pv-xxx -p '{"spec":{"claimRef":null}}'
```

---

## 4. 在 Pod 里使用

```yaml
spec:
  securityContext:
    fsGroup: 65532                      # ⭐ 见 §5
    fsGroupChangePolicy: OnRootMismatch
  containers:
    - name: server
      volumeMounts:
        - name: data
          mountPath: /var/lib/app
          # subPath: app1               # 卷内的子目录（多个应用共享一个卷时用）
          readOnly: false
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: hello-data
```

### 4.1 StatefulSet 的 volumeClaimTemplates（第 9 章回顾）

```yaml
volumeClaimTemplates:
  - metadata: {name: data}
    spec:
      accessModes: [ReadWriteOnce]
      storageClassName: fast-ssd
      resources: {requests: {storage: 100Gi}}
```

每个 Pod 自动获得一个专属 PVC：`data-db-0`、`data-db-1`……Pod 重建后**挂回同一个 PVC**。

### 4.2 Generic Ephemeral Volume（1.23 GA）

需要"每个 Pod 一块独立的临时盘，但要比 emptyDir 大/快"时：

```yaml
volumes:
  - name: scratch
    ephemeral:
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          storageClassName: fast-ssd
          resources: {requests: {storage: 100Gi}}
```

PVC 随 Pod 创建、随 Pod 删除。适合大数据处理的中间结果、构建缓存。

---

## 5. fsGroup：有状态服务最常见的启动失败原因

第 4 章讲过 bind mount 的权限问题，K8s 里是这样的：

新创建的卷通常属于 `root:root`，权限 `755`。你的容器以 UID 65532 运行 → **写不进去** → `Permission denied` → CrashLoopBackOff。

```yaml
spec:
  securityContext:
    runAsUser: 65532
    runAsGroup: 65532
    fsGroup: 65532                     # ⭐ kubelet 会把卷的属组改成 65532，并加 setgid
    fsGroupChangePolicy: OnRootMismatch # 只在根目录属主不匹配时才递归 chown
```

**`fsGroupChangePolicy` 很重要**：默认 `Always` 会在每次 Pod 启动时**递归 chown 整个卷**。一个有几百万文件的卷（比如 Elasticsearch 数据目录）会导致启动耗时几十分钟。`OnRootMismatch` 只检查根目录，通常就够了。

**注意**：`fsGroup` 只对支持它的卷类型生效（块存储 + 文件系统）。NFS 等某些卷类型不生效，那时只能：

```yaml
initContainers:
  - name: fix-perms
    image: busybox:1.37
    command: ['sh','-c','chown -R 65532:65532 /data']
    securityContext: {runAsUser: 0}
    volumeMounts: [{name: data, mountPath: /data}]
```

---

## 6. 扩容

```bash
# ① 确认 SC 支持
kubectl get sc standard -o jsonpath='{.allowVolumeExpansion}'   # true

# ② 直接改 PVC 的 size
kubectl patch pvc hello-data -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
# 或 kubectl edit pvc hello-data

# ③ 观察
kubectl get pvc hello-data -w
kubectl describe pvc hello-data
# Conditions:
#   FileSystemResizePending  ← 需要重启 Pod 才能扩展文件系统（老的 CSI driver）
```

**要点**：
- **只能扩大，不能缩小**
- 大多数现代 CSI driver 支持**在线扩容**（不用重启 Pod）
- 老的 driver 需要重启 Pod 才能完成文件系统扩展
- **StatefulSet 的 `volumeClaimTemplates` 不可变**：想给所有副本扩容，要逐个 `kubectl edit pvc`，然后（如需要）滚动重启

StatefulSet 批量扩容脚本：

```bash
for i in 0 1 2; do
  kubectl patch pvc data-db-$i -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'
done
kubectl rollout restart statefulset db     # 如果 driver 需要重启
```

---

## 7. 快照与备份

### 7.1 VolumeSnapshot（CSI 快照）

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata: {name: csi-snapclass}
driver: ebs.csi.aws.com
deletionPolicy: Retain
---
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata: {name: hello-data-snap-20260729}
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: hello-data
---
# 从快照恢复：创建一个新 PVC
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: hello-data-restored}
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard
  resources: {requests: {storage: 10Gi}}
  dataSource:
    name: hello-data-snap-20260729
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
```

⚠️ **快照不等于一致的备份**。对运行中的数据库做卷快照，拿到的是"崩溃一致"状态（相当于突然断电）。数据库能恢复但可能要重放日志。**真正的数据库备份要用数据库自己的工具**（`pg_dump`、`pg_basebackup`、WAL 归档），或者先 `fsfreeze`。

### 7.2 Velero：集群级备份

```bash
velero install --provider aws --bucket my-backup --secret-file ./credentials

# 备份整个 namespace（K8s 对象 + PV 数据）
velero backup create prod-backup --include-namespaces prod

# 定时备份
velero schedule create daily --schedule="0 2 * * *" --include-namespaces prod --ttl 720h

# 恢复
velero restore create --from-backup prod-backup
```

Velero 备份两部分：**K8s 对象定义**（存成 tar 传到对象存储）+ **PV 数据**（用 CSI 快照或 restic/kopia 做文件级备份）。

第 21、23 章会讲完整的灾备策略。

---

## 8. 存储选型

| 场景 | 推荐 |
|---|---|
| 云上，单节点读写 | 云盘 CSI（EBS gp3 / 阿里云 ESSD / GCP PD） |
| 云上，多节点共享 | EFS / Filestore / NAS（注意：性能和延迟远不如块存储） |
| 自建，需要 RWX | Ceph（Rook）、Longhorn、NFS（简单但有单点） |
| 自建，高性能 RWO | Local PV（配合应用层复制）、OpenEBS、Longhorn |
| 大文件 / 非结构化数据 | **对象存储（S3/MinIO）** —— 应用直接用 SDK，不要挂文件系统 |
| 数据库 | **强烈建议用云托管服务**，或用成熟 Operator + 高性能块存储 |

**一条重要建议**：**能不用 PVC 就不用**。

云原生应用应该尽量做到无状态：
- 数据 → 数据库（托管服务）
- 文件 → 对象存储（S3 SDK）
- 缓存 → Redis
- 会话 → Redis/JWT

PVC 会给你带来：调度约束（卷绑在可用区）、备份复杂度、扩容麻烦、迁移困难、跨集群灾备难。**每一个 PVC 都是一份长期运维负担。**

---

## 9. 动手实验

### 实验 1：kind 的默认 StorageClass

```bash
kubectl get sc
# NAME                 PROVISIONER             RECLAIMPOLICY  VOLUMEBINDINGMODE
# standard (default)   rancher.io/local-path   Delete         WaitForFirstConsumer
kubectl describe sc standard
```

kind 用 `local-path-provisioner`，实际上就是在节点上创建目录。

### 实验 2：PVC 完整生命周期

```bash
kubectl create ns storage && kubectl config set-context --current --namespace=storage

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: demo-pvc}
spec:
  accessModes: [ReadWriteOnce]
  resources: {requests: {storage: 1Gi}}
EOF

kubectl get pvc,pv
# ⭐ PVC 是 Pending，PV 还没创建！因为 volumeBindingMode: WaitForFirstConsumer

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: writer}
spec:
  containers:
    - name: c
      image: busybox:1.37
      command: ['sh','-c','echo "written at $(date) by $HOSTNAME" >> /data/log.txt; cat /data/log.txt; sleep 3600']
      volumeMounts: [{name: d, mountPath: /data}]
  volumes:
    - name: d
      persistentVolumeClaim: {claimName: demo-pvc}
EOF

kubectl wait --for=condition=Ready pod/writer --timeout=60s
kubectl get pvc,pv          # ⭐ 现在 Bound 了
kubectl logs writer
```

### 实验 3：⭐ 数据在 Pod 重建后保留

```bash
kubectl delete pod writer
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: reader}
spec:
  containers:
    - name: c
      image: busybox:1.37
      command: ['sh','-c','echo "read by $HOSTNAME:"; cat /data/log.txt; sleep 3600']
      volumeMounts: [{name: d, mountPath: /data}]
  volumes:
    - name: d
      persistentVolumeClaim: {claimName: demo-pvc}
EOF
kubectl wait --for=condition=Ready pod/reader --timeout=60s
kubectl logs reader          # ⭐ 之前写的内容还在！
```

### 实验 4：emptyDir 的生命周期

```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: ed}
spec:
  containers:
    - name: c
      image: busybox:1.37
      command: ['sh','-c','echo "data-$(date +%s)" > /cache/f; cat /cache/f; sleep 3600']
      volumeMounts: [{name: cache, mountPath: /cache}]
  volumes:
    - {name: cache, emptyDir: {}}
EOF
kubectl wait --for=condition=Ready pod/ed --timeout=60s
kubectl exec ed -- cat /cache/f

# 杀掉容器（不删 Pod）—— 数据还在
kubectl exec ed -- sh -c 'kill 1' 2>/dev/null; sleep 8
kubectl get pod ed          # RESTARTS 变成 1
kubectl exec ed -- cat /cache/f    # ⭐ 数据还在（同一个 Pod）

# 删除 Pod 重建 —— 数据没了
kubectl delete pod ed
```

### 实验 5：fsGroup 权限

```bash
# 不设 fsGroup，非 root 用户写入
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: noperm}
spec:
  securityContext: {runAsUser: 65532, runAsGroup: 65532}
  restartPolicy: Never
  containers:
    - name: c
      image: busybox:1.37
      command: ['sh','-c','id; ls -ld /data; touch /data/test && echo "WRITE OK" || echo "WRITE FAILED"']
      volumeMounts: [{name: d, mountPath: /data}]
  volumes:
    - {name: d, persistentVolumeClaim: {claimName: demo-pvc}}
EOF
sleep 8; kubectl logs noperm

# 加上 fsGroup
kubectl delete pod noperm
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: withperm}
spec:
  securityContext: {runAsUser: 65532, runAsGroup: 65532, fsGroup: 65532, fsGroupChangePolicy: OnRootMismatch}
  restartPolicy: Never
  containers:
    - name: c
      image: busybox:1.37
      command: ['sh','-c','id; ls -ld /data; touch /data/test && echo "WRITE OK" || echo "WRITE FAILED"']
      volumeMounts: [{name: d, mountPath: /data}]
  volumes:
    - {name: d, persistentVolumeClaim: {claimName: demo-pvc}}
EOF
sleep 8; kubectl logs withperm       # WRITE OK ✅
```

### 实验 6：ReadWriteOnce 的真实含义

```bash
# 在同一个节点上起两个 Pod 用同一个 RWO PVC —— 可以！
NODE=$(kubectl get pod reader -o jsonpath='{.spec.nodeName}')
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata: {name: same-node}
spec:
  nodeName: $NODE
  containers:
    - name: c
      image: busybox:1.37
      command: ['sh','-c','cat /data/log.txt; sleep 3600']
      volumeMounts: [{name: d, mountPath: /data}]
  volumes:
    - {name: d, persistentVolumeClaim: {claimName: demo-pvc}}
EOF
kubectl wait --for=condition=Ready pod/same-node --timeout=60s   # ✅ 成功
kubectl get pods -o wide
```

（在真实的云盘上，调度到**不同节点**的第二个 Pod 会一直卡在 `ContainerCreating`，报 `Multi-Attach error`。kind 的 local-path 不会复现这个，但真实环境务必记住。）

### 实验 7：reclaimPolicy 的后果

```bash
kubectl get pv    # 记下 PV 名字和 RECLAIM POLICY（Delete）
PVNAME=$(kubectl get pvc demo-pvc -o jsonpath='{.spec.volumeName}')

kubectl delete pod reader same-node writer noperm withperm --ignore-not-found
kubectl delete pvc demo-pvc
kubectl get pv $PVNAME 2>&1     # ⭐ PV 也被删了，数据永久丢失

# 对比 Retain：先建一个 Retain 的 SC
kubectl apply -f - <<'EOF'
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata: {name: retain-sc}
provisioner: rancher.io/local-path
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
EOF
```

### 实验 8：StatefulSet 的存储（第 9 章实验 6/7 的延续）

回顾第 9 章：删除 `web-1` 后重建，数据还在；缩容后 PVC 保留。这就是 `volumeClaimTemplates` + PVC 独立生命周期的效果。

### 清理

```bash
kubectl delete ns storage
kubectl config set-context --current --namespace=default
```

---

## 10. 存储排障速查

| 现象 | 原因与排查 |
|---|---|
| PVC 一直 `Pending` | ① `volumeBindingMode: WaitForFirstConsumer` 且还没有 Pod 用它 → 正常<br>② 没有匹配的 SC → `kubectl get sc`，检查 `storageClassName`<br>③ CSI driver 没装或挂了 → `kubectl get pods -n kube-system \| grep csi`<br>④ 后端配额不足 → `kubectl describe pvc` 看 Events |
| Pod 卡 `ContainerCreating`，事件里有 `FailedAttachVolume` | 云盘 attach 失败：可能是卷还挂在另一个节点上（旧 Pod 没完全删除），或节点已达 attach 上限 |
| `Multi-Attach error` | RWO 卷被调度到两个不同节点的 Pod 使用。改用 RWX，或用 StatefulSet，或加 Pod 反亲和确保同节点 |
| `volume node affinity conflict` | PV 在 zone-a，Pod 被调度到 zone-b。用 `WaitForFirstConsumer` 避免 |
| 容器启动报 `Permission denied` | 缺 `fsGroup`，或卷类型不支持 fsGroup → 用 initContainer chown |
| Pod 被驱逐，事件说 `ephemeral-storage` 超限 | 容器写了太多本地文件（日志、临时文件）→ 设 `sizeLimit`，日志写 stdout |
| 扩容 PVC 后容量没变 | ① SC 的 `allowVolumeExpansion` 为 false<br>② 需要重启 Pod 完成文件系统扩展 → `kubectl describe pvc` 看 `FileSystemResizePending` |
| 删了 PVC 数据就没了 | `reclaimPolicy: Delete`。生产数据一律用 `Retain` |
| PV 是 `Released` 状态无法复用 | 清掉 `spec.claimRef` |
| 节点磁盘满，大量 Pod 被驱逐 | 检查镜像缓存、容器日志、emptyDir。设置 kubelet 的 GC 阈值和 `ephemeral-storage` 限制 |

---

## 11. 本章检查清单

- [ ] emptyDir 的生命周期是什么？容器重启会丢吗？Pod 删除呢？
- [ ] `emptyDir: {medium: Memory}` 有什么隐藏风险？
- [ ] 为什么 hostPath 危险？哪些场景可以用？
- [ ] PV、PVC、StorageClass 三者的分工是什么？为什么要分开？
- [ ] 描述动态供给的完整流程（8 步）
- [ ] `volumeBindingMode: WaitForFirstConsumer` 解决什么问题？
- [ ] `reclaimPolicy` 两种值的后果？生产数据库该用哪个？
- [ ] `ReadWriteOnce` 到底限制的是什么？（这题答错的人很多）
- [ ] 需要多个副本共享文件时，有哪些方案？为什么这是个架构信号？
- [ ] `fsGroup` 解决什么问题？`fsGroupChangePolicy` 为什么重要？
- [ ] PVC 能缩容吗？StatefulSet 怎么批量扩容？
- [ ] 卷快照等于数据库备份吗？为什么？
- [ ] 为什么说"每个 PVC 都是一份长期运维负担"？
- [ ] 完成实验 2、3、5

---

## 12. 延伸阅读

- [Volumes](https://kubernetes.io/docs/concepts/storage/volumes/)
- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [CSI 规范](https://github.com/container-storage-interface/spec)
- [Velero](https://velero.io/docs/)
- [Rook/Ceph](https://rook.io/) / [Longhorn](https://longhorn.io/)

---

下一章：[12 - 调度、资源与弹性伸缩](./12-scheduling-scaling.md)
