# 17 - Jenkins 与持续集成

> 本章目标：搞懂 CI 到底在做什么、Jenkins 怎么工作、怎么在 K8s 上跑动态构建 agent、
> 怎么把 Go 服务构建成镜像推到仓库，并把结果交接给 CD（第 18 章）。
> 预计用时：3 小时（含实验）。

---

## 1. CI 到底在解决什么

**持续集成（Continuous Integration）的原意**：让每个人的改动**频繁地**合并到主干，并**自动验证**没有破坏东西。

没有 CI 的世界：
- 三个人各开一个分支写两周，合并时冲突几百个文件（"合并地狱"）
- "我本地测试是过的"——但没人知道在干净环境下是否能编译
- 发布前一天才发现两个功能互相冲突
- 构建过程只有某个人的机器上能跑（"卡车因子 = 1"）

CI 提供的保障：

| 能力 | 价值 |
|---|---|
| 每次提交自动编译 | 立刻知道有没有编译错误 |
| 自动跑测试 | 立刻知道有没有破坏已有功能 |
| 统一的构建环境 | 消除"在我机器上是好的" |
| 产出**不可变构件**（镜像） | 测试的和上线的是同一个二进制 |
| 质量门禁（lint、覆盖率、安全扫描） | 把标准自动化，不靠人自觉 |

**CI 的产出永远是一个"构件"**——对我们来说就是一个打了不可变 tag 的容器镜像。

### 1.1 CI 与 CD 的边界

```
┌────────────────────── CI（本章）──────────────────────┐
│  代码提交 → 编译 → 单测 → lint → 构建镜像 → 扫描 → 推仓库  │
│                                                       │
│  产出：ghcr.io/org/hello:v1.2.3@sha256:abc...          │
└───────────────────────────┬───────────────────────────┘
                            │ 更新配置仓库里的 image tag
                            ▼
┌────────────────────── CD（第 18 章）──────────────────┐
│  Argo CD 检测到 Git 变化 → 渲染 → apply → 健康检查        │
└───────────────────────────────────────────────────────┘
```

**关键设计决策：CI 不直接部署。** CI 只做两件事：产出镜像，然后**修改配置仓库里的一行 tag**。理由见第 18 章。

---

## 2. Jenkins 架构

Jenkins（2011 年从 Hudson 分叉）是最老牌的 CI 工具，2026 年仍在大量企业使用。当前 LTS 是 **2.555.x**，需要 **Java 21+**（Java 17 支持已在 2.555.1 移除）。

```
┌─────────────────────────────────────────────────────┐
│  Jenkins Controller（控制器，旧称 master）             │
│  · Web UI / REST API                                 │
│  · 任务调度与队列                                      │
│  · 插件系统（1800+ 插件）                              │
│  · 构建历史与产物                                      │
│  · $JENKINS_HOME（配置、任务、凭据都在这里）             │
│  ⚠️ 不应该在这里执行构建！                              │
└──────────────────┬──────────────────────────────────┘
                   │ 分派任务
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐   ┌────────┐   ┌────────────────┐
│ Agent  │   │ Agent  │   │ K8s Pod Agent  │ ⭐ 本章重点
│(静态VM)│   │(Docker)│   │(按需创建/销毁)   │
└────────┘   └────────┘   └────────────────┘
```

**核心概念**：

| 概念 | 说明 |
|---|---|
| **Controller** | 大脑。**绝不要在上面跑构建**（安全 + 稳定性） |
| **Agent / Node** | 干活的机器 |
| **Executor** | agent 上的并发槽位（一个 executor 同时只跑一个构建） |
| **Job / Pipeline** | 一个可执行的任务定义 |
| **Stage / Step** | Pipeline 的阶段和步骤 |
| **Workspace** | agent 上的工作目录 |

### 2.1 为什么要在 K8s 上跑 Jenkins agent

传统方式：养一批固定的构建机。问题：
- 空闲时浪费（构建高峰在白天，晚上机器闲着）
- 高峰时排队
- 环境冲突（项目 A 要 Go 1.21，项目 B 要 Go 1.26）
- 环境漂移（有人手工在构建机上装了东西，后来没人知道）

**Kubernetes 插件**：每个构建**动态创建一个 Pod** 作为 agent，构建完就销毁。

- ✅ 弹性：0 构建时 0 成本
- ✅ 隔离：每个构建一个全新环境
- ✅ 环境即代码：Pod 模板写在 Jenkinsfile 里
- ✅ 复用集群资源

---

## 3. 在 K8s 上部署 Jenkins

```bash
kubectl create namespace jenkins

helm repo add jenkins https://charts.jenkins.io
helm repo update
```

`jenkins-values.yaml`：

```yaml
controller:
  image:
    tag: "2.555.3-lts-jdk21"
  adminUser: admin
  adminPassword: "change-me-in-production"    # 生产用 existingSecret

  # ⭐ controller 上不跑构建
  numExecutors: 0

  resources:
    requests: {cpu: 500m, memory: 1Gi}
    limits: {memory: 4Gi}

  javaOpts: "-Xmx3g -XX:+UseG1GC"

  # ⭐ JCasC：配置即代码，避免 UI 点点点导致的不可复现
  installPlugins:
    - kubernetes:latest
    - workflow-aggregator:latest
    - git:latest
    - configuration-as-code:latest
    - credentials-binding:latest
    - pipeline-stage-view:latest
    - github-branch-source:latest
    - job-dsl:latest

  JCasC:
    defaultConfig: true
    configScripts:
      welcome: |
        jenkins:
          systemMessage: "Managed by JCasC. Do not edit via UI."
          numExecutors: 0
          quietPeriod: 0
      security: |
        jenkins:
          authorizationStrategy:
            globalMatrix:
              permissions:
                - "Overall/Administer:admin"
                - "Overall/Read:authenticated"
          securityRealm:
            local:
              allowsSignup: false
      clouds: |
        jenkins:
          clouds:
            - kubernetes:
                name: "kubernetes"
                serverUrl: "https://kubernetes.default"
                namespace: "jenkins"
                jenkinsUrl: "http://jenkins.jenkins.svc.cluster.local:8080"
                jenkinsTunnel: "jenkins-agent.jenkins.svc.cluster.local:50000"
                containerCapStr: "20"          # 最多同时 20 个 agent Pod
                podRetention: "never"
                retentionTimeout: 5
                connectTimeout: 300

persistence:
  enabled: true
  storageClass: standard
  size: 20Gi

agent:
  enabled: true
  podName: "jenkins-agent"
  resources:
    requests: {cpu: 200m, memory: 512Mi}
    limits: {memory: 2Gi}

serviceAccount:
  create: true
  name: jenkins

rbac:
  create: true
  readSecrets: false
```

```bash
helm upgrade --install jenkins jenkins/jenkins -n jenkins -f jenkins-values.yaml --wait --timeout 10m

kubectl -n jenkins get pods
kubectl -n jenkins exec svc/jenkins -c jenkins -- \
  cat /run/secrets/additional/chart-admin-password 2>/dev/null || echo "用 values 里设的密码"

kubectl -n jenkins port-forward svc/jenkins 8080:8080
# 浏览器 localhost:8080
```

**Jenkins 需要的 RBAC**（Helm chart 会创建）：在 `jenkins` namespace 里能 create/delete/watch Pod、读 Pod 日志、exec 进 Pod。

---

## 4. Pipeline as Code：Jenkinsfile

Jenkins 有两种 Pipeline 语法：

| | Declarative（推荐） | Scripted |
|---|---|---|
| 语法 | 结构化的 `pipeline { }` DSL | 完整的 Groovy 脚本 |
| 可读性 | 好 | 差 |
| 校验 | 语法错误早期发现 | 运行时才发现 |
| 灵活性 | 够用（可用 `script {}` 逃生） | 无限 |

**一律用 Declarative**，需要复杂逻辑时在 `script { }` 块里写。

### 4.1 一个生产级的 Go 服务 Jenkinsfile

```groovy
// Jenkinsfile —— 放在应用代码仓根目录
pipeline {
  agent {
    kubernetes {
      // ⭐ agent 就是一个 Pod 定义 —— 你第 7 章学的所有东西都能用
      yaml '''
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsUser: 1000
    fsGroup: 1000
  containers:
    - name: golang
      image: golang:1.26-alpine
      command: ["cat"]          # ⭐ 让容器保持运行，Jenkins 用 exec 进去执行步骤
      tty: true
      env:
        - {name: GOCACHE, value: /workspace/.cache/go-build}
        - {name: GOMODCACHE, value: /workspace/.cache/go-mod}
        - {name: CGO_ENABLED, value: "0"}
      resources:
        requests: {cpu: "1", memory: 2Gi}
        limits: {memory: 4Gi}
      volumeMounts:
        - {name: cache, mountPath: /workspace/.cache}

    # ⭐ BuildKit：在集群里构建镜像，无需 docker.sock
    #    （Kaniko 已于 2025-06 归档，不要再用）
    - name: buildkit
      image: moby/buildkit:v0.28.0-rootless
      command: ["buildkitd", "--addr", "unix:///run/user/1000/buildkit/buildkitd.sock",
                "--oci-worker-no-process-sandbox"]
      securityContext:
        runAsUser: 1000
        runAsGroup: 1000
        seccompProfile: {type: Unconfined}
        appArmorProfile: {type: Unconfined}
      resources:
        requests: {cpu: "1", memory: 2Gi}
        limits: {memory: 6Gi}
      volumeMounts:
        - {name: buildkit-cache, mountPath: /home/user/.local/share/buildkit}

    - name: tools
      image: alpine/k8s:1.36.0        # 内置 kubectl / helm / yq / git
      command: ["cat"]
      tty: true

  volumes:
    - name: cache
      emptyDir: {}
    - name: buildkit-cache
      emptyDir: {}
'''
      defaultContainer 'golang'
    }
  }

  options {
    timeout(time: 30, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '10'))
    disableConcurrentBuilds(abortPrevious: true)
    timestamps()
    ansiColor('xterm')
  }

  environment {
    REGISTRY    = 'ghcr.io/yourorg'
    IMAGE_NAME  = 'hello'
    GIT_SHA     = "${env.GIT_COMMIT?.take(7) ?: 'unknown'}"
    // ⭐ 不可变 tag：语义版本 + git sha
    IMAGE_TAG   = "${env.BRANCH_NAME == 'main' ? env.BUILD_NUMBER + '-' + GIT_SHA : 'pr-' + env.CHANGE_ID + '-' + GIT_SHA}"
    FULL_IMAGE  = "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh 'git log -1 --oneline'
      }
    }

    stage('Verify') {
      // ⭐ 并行执行独立的检查，缩短反馈时间
      parallel {
        stage('Lint') {
          steps {
            sh '''
              go vet ./...
              go run honnef.co/go/tools/cmd/staticcheck@latest ./...
            '''
          }
        }
        stage('Unit Test') {
          steps {
            sh '''
              go test -race -coverprofile=coverage.out -covermode=atomic ./...
              go tool cover -func=coverage.out | tail -1
            '''
          }
          post {
            always {
              // 需要 junit 插件 + gotestsum
              archiveArtifacts artifacts: 'coverage.out', allowEmptyArchive: true
            }
          }
        }
        stage('Vulnerability Scan') {
          steps {
            sh 'go run golang.org/x/vuln/cmd/govulncheck@latest ./... || true'
          }
        }
      }
    }

    stage('Build Image') {
      steps {
        container('buildkit') {
          // ⭐ 凭据注入：绝不把密码写在 Jenkinsfile 里
          withCredentials([usernamePassword(
              credentialsId: 'registry-creds',
              usernameVariable: 'REG_USER',
              passwordVariable: 'REG_PASS')]) {
            sh '''
              mkdir -p ~/.docker
              AUTH=$(printf "%s:%s" "$REG_USER" "$REG_PASS" | base64 | tr -d '\\n')
              cat > ~/.docker/config.json <<EOF
{"auths":{"ghcr.io":{"auth":"$AUTH"}}}
EOF
              buildctl-daemonless.sh build \
                --frontend dockerfile.v0 \
                --local context=. \
                --local dockerfile=. \
                --opt build-arg:VERSION=${IMAGE_TAG} \
                --opt build-arg:COMMIT=${GIT_SHA} \
                --opt platform=linux/amd64,linux/arm64 \
                --output type=image,name=${FULL_IMAGE},push=true \
                --export-cache type=registry,ref=${REGISTRY}/${IMAGE_NAME}:buildcache,mode=max \
                --import-cache type=registry,ref=${REGISTRY}/${IMAGE_NAME}:buildcache
            '''
          }
        }
      }
    }

    stage('Scan Image') {
      steps {
        container('tools') {
          sh '''
            wget -qO- https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /tmp
            /tmp/trivy image --severity HIGH,CRITICAL --exit-code 1 \
              --ignore-unfixed ${FULL_IMAGE}
          '''
        }
      }
    }

    // ⭐⭐ 关键交接点：CI 的最后一步不是部署，而是改配置仓库
    stage('Update Config Repo') {
      when { branch 'main' }
      steps {
        container('tools') {
          withCredentials([sshUserPrivateKey(
              credentialsId: 'config-repo-ssh', keyFileVariable: 'SSH_KEY')]) {
            sh '''
              export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"
              rm -rf /tmp/config && git clone git@github.com:yourorg/k8s-config.git /tmp/config
              cd /tmp/config

              # 用 yq 精确修改 image tag
              yq -i ".image.tag = \\"${IMAGE_TAG}\\"" apps/hello/values-staging.yaml

              git config user.email "ci@yourorg.com"
              git config user.name  "Jenkins CI"
              git add -A
              git commit -m "chore(hello): bump staging image to ${IMAGE_TAG}

Source: ${GIT_URL}@${GIT_COMMIT}
Build:  ${BUILD_URL}" || echo "no changes"
              git push origin main
            '''
          }
        }
        echo "✅ 已提交到配置仓库，Argo CD 将自动同步到 staging"
      }
    }
  }

  post {
    success {
      echo "✅ ${FULL_IMAGE}"
    }
    failure {
      // 接飞书/钉钉/Slack
      echo "❌ 构建失败：${env.BUILD_URL}"
    }
    always {
      cleanWs()
    }
  }
}
```

### 4.2 Jenkinsfile 的关键点解释

**① `command: ["cat"]` + `tty: true`**
Jenkins 需要容器一直活着好往里 `exec` 执行步骤。`cat` 在 tty 下会一直等输入不退出。这是 Jenkins K8s 插件的惯用法。

**② `container('name') { }`**
切换到 Pod 里的哪个容器执行。`defaultContainer` 设置默认值。

**③ 为什么不用 `docker build`**
在 K8s Pod 里跑 `docker build` 需要挂载宿主机的 `/var/run/docker.sock` —— **这等于把整个节点的 root 权限给了每个构建任务**（第 14 章）。任何人改一行 Jenkinsfile 就能接管节点。

安全的替代方案：

| 方案 | 状态 |
|---|---|
| **BuildKit rootless** ⭐ | 推荐。功能最全（多架构、缓存、secret 挂载） |
| **Buildah** | Red Hat 系，也很好 |
| ~~Kaniko~~ | ⚠️ **已于 2025-06 归档**，不要在新项目使用 |
| Docker-in-Docker (dind) | 需要特权容器，安全性差 |
| 外部构建服务（Depot、云 Build 服务） | 托管方案 |

**④ 不可变 tag**
`IMAGE_TAG` 包含 build number 和 git sha，**永不复用**。这样任何时候都能从镜像 tag 反查到确切的源码。

**⑤ 缓存**
`--export-cache`/`--import-cache` 把 BuildKit 的层缓存推到 registry，跨构建复用。Go 的模块和编译缓存放 emptyDir（同一个 Pod 内跨 stage 复用）。想跨构建复用，改成 PVC。

---

## 5. 凭据管理

**绝对不要**把密码写进 Jenkinsfile 或环境变量默认值。

```groovy
withCredentials([
  string(credentialsId: 'slack-token', variable: 'SLACK_TOKEN'),
  usernamePassword(credentialsId: 'registry-creds',
                   usernameVariable: 'USER', passwordVariable: 'PASS'),
  sshUserPrivateKey(credentialsId: 'deploy-key', keyFileVariable: 'KEY'),
  file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG'),
]) {
  sh 'echo "使用 $USER"'    // Jenkins 会自动把日志里的密码值替换成 ****
}
```

**凭据来源**：
- Jenkins 内置凭据存储（加密在 `$JENKINS_HOME`）
- **HashiCorp Vault 插件**（推荐生产用）
- **Kubernetes Credentials Provider 插件**：直接用 K8s Secret 作为 Jenkins 凭据
- 云厂商的 Secrets Manager 插件

**安全要点**：
- Jenkins 的凭据一旦泄漏影响面极大 → 严格限制谁能改 Jenkinsfile、谁能进 Jenkins UI
- 开启 **Script Security**，Groovy 脚本要审批才能用危险 API
- **用 GitOps 后，Jenkins 完全不需要集群的部署权限**——这是最大的安全改进

---

## 6. 多分支流水线与共享库

### 6.1 Multibranch Pipeline

自动为仓库的每个分支/PR 创建流水线：

```groovy
// Job DSL 或在 UI 里配置
multibranchPipelineJob('hello') {
  branchSources {
    github {
      id('hello')
      repoOwner('yourorg')
      repository('hello')
      credentialsId('github-token')
      buildOriginBranch(true)
      buildOriginPRMerge(true)
    }
  }
  orphanedItemStrategy { discardOldItems { numToKeep(10) } }
}
```

配合 Jenkinsfile 里的 `when { branch 'main' }` 实现分支差异化行为。

### 6.2 Shared Library（消除重复）

50 个微服务的 Jenkinsfile 90% 相同。抽成共享库：

```groovy
// 共享库仓库：vars/goService.groovy
def call(Map config) {
  pipeline {
    agent { kubernetes { yaml libraryResource('pods/go-builder.yaml') } }
    stages {
      stage('Test')  { steps { sh 'go test ./...' } }
      stage('Build') { steps { buildImage(config.image) } }
      stage('Deploy'){ steps { bumpConfigRepo(config.app, env.IMAGE_TAG) } }
    }
  }
}
```

各服务的 Jenkinsfile 就只剩：

```groovy
@Library('platform-lib@v2') _
goService(app: 'hello', image: 'ghcr.io/yourorg/hello')
```

**这是平台工程的典型做法**（第 21 章）：把最佳实践固化成库，业务团队零成本获得。

---

## 7. Jenkins vs 其他 CI

| 工具 | 优势 | 劣势 | 适用 |
|---|---|---|---|
| **Jenkins** | 插件生态无敌、完全自主可控、能对接任何遗留系统、私有部署 | 运维负担重、UI 老旧、插件质量参差、Groovy 学习成本、安全需要认真配置 | 企业内网、复杂遗留环境、需要深度定制 |
| **GitHub Actions** | 与 GitHub 深度集成、YAML 简单、Marketplace 丰富、托管免运维 | 绑定 GitHub、自托管 runner 要自己管、大规模成本高 | 代码在 GitHub 上的团队 ⭐ |
| **GitLab CI** | 与 GitLab 一体、YAML 简洁、内置容器仓库和环境管理 | 绑定 GitLab | 用 GitLab 的团队 ⭐ |
| **Tekton** | K8s 原生（CRD）、可组合、无状态 | 很底层，要自己搭 UI 和流程 | 做平台的团队 |
| **Argo Workflows** | K8s 原生、DAG 强大、和 Argo CD 同生态 | 更偏批处理/ML 流水线 | 已用 Argo 生态 |
| **Drone / Woodpecker** | 轻量、容器原生 | 生态小 | 小团队 |

**选型建议**：
- 新项目、代码在 GitHub/GitLab → **直接用 Actions/GitLab CI**，别自建 Jenkins
- 已有 Jenkins 且运转正常 → 不用急着换，把 agent 迁到 K8s + 上 GitOps 就能获得大部分收益
- 内网、有合规要求、需要对接一堆遗留系统 → Jenkins 仍是好选择

**注意：本章的核心思想（不可变构件、CI/CD 分离、凭据管理、in-cluster 构建）与工具无关。** 换成 GitHub Actions 也是同样的流程：

```yaml
# 等价的 GitHub Actions（对照理解）
name: ci
on: {push: {branches: [main]}}
jobs:
  build:
    runs-on: ubuntu-latest
    permissions: {contents: read, packages: write, id-token: write}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: {go-version: '1.26'}
      - run: go test -race ./...
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with: {registry: ghcr.io, username: ${{github.actor}}, password: ${{secrets.GITHUB_TOKEN}}}
      - uses: docker/build-push-action@v6
        with:
          push: true
          platforms: linux/amd64,linux/arm64
          tags: ghcr.io/${{github.repository}}:${{github.run_number}}-${{github.sha}}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      # 同样的交接：改配置仓库
      - run: |
          git clone https://x:${{secrets.CONFIG_REPO_TOKEN}}@github.com/org/k8s-config /tmp/c
          cd /tmp/c && yq -i '.image.tag = "${{github.run_number}}-${{github.sha}}"' apps/hello/values-staging.yaml
          git -c user.email=ci@org -c user.name=CI commit -am "bump hello" && git push
```

---

## 8. CI 实践清单

### 流水线设计

- [ ] 每次提交都跑（不只是 main 分支）
- [ ] 快的检查放前面、能并行的并行（**目标：PR 反馈 < 10 分钟**）
- [ ] 构建产出**不可变 tag** 的镜像，绝不用 `latest`
- [ ] 同一个镜像流转到所有环境（不要为每个环境重新构建）
- [ ] 有质量门禁：编译、单测、lint、漏洞扫描、镜像扫描
- [ ] 构建可复现（锁依赖版本、固定基础镜像、`-trimpath`）
- [ ] 流水线定义在代码仓（Jenkinsfile），随代码演进

### 安全

- [ ] **不挂载 docker.sock**，用 BuildKit/Buildah
- [ ] 凭据用 `withCredentials`，不在日志里出现
- [ ] agent 用最小权限的 SA，构建 Pod 不用 `privileged`
- [ ] Controller 上 `numExecutors: 0`
- [ ] **CI 没有生产集群的写权限**（用 GitOps）
- [ ] 第三方 Action/插件固定版本（供应链）

### 效率

- [ ] 依赖缓存（Go module + build cache）
- [ ] 镜像层缓存（registry cache）
- [ ] 构建 agent 按需创建
- [ ] 测试并行分片
- [ ] 用 `disableConcurrentBuilds(abortPrevious: true)` 避免同一分支的过时构建浪费资源

---

## 9. 动手实验

### 实验 1：部署 Jenkins

```bash
kubectl create ns jenkins
helm repo add jenkins https://charts.jenkins.io && helm repo update

cat > /tmp/jenkins-values.yaml <<'EOF'
controller:
  adminUser: admin
  adminPassword: admin123
  numExecutors: 0
  resources:
    requests: {cpu: 300m, memory: 1Gi}
    limits: {memory: 3Gi}
  installPlugins:
    - kubernetes:latest
    - workflow-aggregator:latest
    - git:latest
    - configuration-as-code:latest
    - credentials-binding:latest
  serviceType: ClusterIP
persistence:
  enabled: true
  size: 8Gi
agent:
  enabled: true
EOF

helm upgrade --install jenkins jenkins/jenkins -n jenkins -f /tmp/jenkins-values.yaml --wait --timeout 15m
kubectl -n jenkins get pods
kubectl -n jenkins port-forward svc/jenkins 8080:8080 &
# 浏览器 localhost:8080，admin/admin123
```

### 实验 2：第一个 K8s agent 流水线

在 Jenkins UI 里 New Item → Pipeline，粘贴：

```groovy
pipeline {
  agent {
    kubernetes {
      yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: golang
      image: golang:1.26-alpine
      command: ["cat"]
      tty: true
      resources:
        requests: {cpu: 500m, memory: 512Mi}
        limits: {memory: 2Gi}
'''
      defaultContainer 'golang'
    }
  }
  stages {
    stage('Info') {
      steps {
        sh 'go version; uname -a; hostname; nproc'
      }
    }
    stage('Build a Go program') {
      steps {
        sh '''
          mkdir -p /tmp/app && cd /tmp/app
          cat > main.go <<'GOEOF'
package main
import "fmt"
func main() { fmt.Println("built in a k8s pod agent!") }
GOEOF
          go mod init demo
          go build -o app .
          ./app
        '''
      }
    }
  }
}
```

点 Build Now，**同时在另一个终端观察 agent Pod 被动态创建和销毁**：

```bash
kubectl -n jenkins get pods -w
# 会看到一个 jenkins-agent-xxxx Pod 出现，构建完消失 ⭐
```

### 实验 3：用 BuildKit 构建并推到本地仓库

先确保第 0 章的本地 registry 在跑（`kind-registry`）。

```groovy
pipeline {
  agent {
    kubernetes {
      yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: buildkit
      image: moby/buildkit:v0.28.0-rootless
      command: ["buildkitd", "--addr", "unix:///run/user/1000/buildkit/buildkitd.sock",
                "--oci-worker-no-process-sandbox"]
      securityContext:
        runAsUser: 1000
        runAsGroup: 1000
        seccompProfile: {type: Unconfined}
        appArmorProfile: {type: Unconfined}
      resources:
        requests: {cpu: 500m, memory: 1Gi}
        limits: {memory: 4Gi}
'''
    }
  }
  stages {
    stage('Build') {
      steps {
        container('buildkit') {
          sh '''
            mkdir -p /tmp/ctx && cd /tmp/ctx
            cat > Dockerfile <<'EOF'
FROM alpine:3.22
RUN echo "built by buildkit in jenkins" > /msg
CMD ["cat", "/msg"]
EOF
            buildctl-daemonless.sh build \
              --frontend dockerfile.v0 \
              --local context=/tmp/ctx \
              --local dockerfile=/tmp/ctx \
              --output type=image,name=kind-registry:5000/demo:jenkins-${BUILD_NUMBER},push=true,registry.insecure=true
          '''
        }
      }
    }
  }
}
```

验证：

```bash
kubectl run verify --rm -it --restart=Never \
  --image=localhost:5001/demo:jenkins-1 --image-pull-policy=Always
# 输出：built by buildkit in jenkins ✅
```

### 实验 4：凭据注入与日志遮蔽

在 Jenkins 里 Manage Jenkins → Credentials 添加一个 Secret text，ID 为 `my-secret`，值为 `super-secret-value`。

```groovy
pipeline {
  agent { kubernetes { yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: sh
      image: alpine:3.22
      command: ["cat"]
      tty: true
''' } }
  stages {
    stage('Use secret') {
      steps {
        container('sh') {
          withCredentials([string(credentialsId: 'my-secret', variable: 'TOKEN')]) {
            sh 'echo "token is $TOKEN"'
            // ⭐ 构建日志里显示：token is ****
          }
        }
      }
    }
  }
}
```

### 实验 5：并行阶段

```groovy
stage('Verify') {
  parallel {
    stage('lint')  { steps { sh 'sleep 10; echo lint ok' } }
    stage('test')  { steps { sh 'sleep 15; echo test ok' } }
    stage('scan')  { steps { sh 'sleep 8;  echo scan ok' } }
  }
}
// 总耗时 ≈ 15 秒而不是 33 秒
```

### 清理

```bash
helm uninstall jenkins -n jenkins
kubectl delete ns jenkins
```

---

## 10. 本章检查清单

- [ ] CI 解决什么问题？它的产出是什么？
- [ ] 为什么 CI 不应该直接部署到生产？
- [ ] Jenkins 的 Controller / Agent / Executor 分别是什么？
- [ ] 为什么要在 K8s 上跑动态 agent？（说出 4 个好处）
- [ ] `command: ["cat"]` + `tty: true` 是干什么的？
- [ ] 为什么不能挂载 `/var/run/docker.sock`？替代方案有哪些？
- [ ] Kaniko 现在的状态是什么？
- [ ] 镜像 tag 为什么要不可变？该怎么构造？
- [ ] Jenkins 的凭据怎么用？日志遮蔽是怎么工作的？
- [ ] Shared Library 解决什么问题？
- [ ] CI 反馈时间应该控制在多少？怎么优化？
- [ ] 什么情况下你会选 GitHub Actions 而不是 Jenkins？
- [ ] 完成实验 1、2、3

---

## 11. 延伸阅读

- [Jenkins Pipeline 语法](https://www.jenkins.io/doc/book/pipeline/syntax/)
- [Kubernetes Plugin](https://plugins.jenkins.io/kubernetes/)
- [Configuration as Code](https://www.jenkins.io/projects/jcasc/)
- [BuildKit](https://github.com/moby/buildkit) / [Buildah](https://buildah.io/)
- [Jenkins 安全最佳实践](https://www.jenkins.io/doc/book/security/)

---

下一章：[18 - Argo CD 与 GitOps](./18-argocd-gitops.md)
