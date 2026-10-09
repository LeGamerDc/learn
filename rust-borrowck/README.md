# 从零到精通：Rust Borrow Checker 系统课程

> 面向对象：有 Go 服务端开发经验、**零 Rust 基础**的工程师。
> 学完之后你应该能够：看到一个借用错误立刻知道**编译器在算什么**、**为什么这么算**、
> **哪些是它的真实限制、哪些是你的设计问题**，并且能在 async / 并发 / unsafe 场景里
> 自如地设计所有权结构，而不是靠 `clone()` 和 `Rc<RefCell<T>>` 硬凑。
>
> 换句话说：不是"学会怎么让编译器闭嘴"，是"学会用 borrow checker 的方式思考"。
>
> ### ★ 本课程以 **Polonius** 为主线
> 借用检查在 2026-08-04 完成了 NLL 之后的第一次换代：**Polonius Alpha 在 nightly 默认开启**，
> 目标 2026 年底稳定化。本课程正文讲的是**这一代的模型**（贷款 / origin / 图可达性），
> 上一代的 NLL（region = 点集）作为**历史参考**放在第 07 章附录和各章的对照框里。
>
> 这么安排的理由很实际：网上 90% 的 Rust 借用检查资料写于 2018–2025 年，讲的是 NLL，
> 其中一部分结论（"这段代码 Rust 编译不过"）**今天已经不成立了**。
> 你需要学的是新模型，同时能认出旧资料在讲什么。

本课程编写于 **2026 年 8 月**，基线版本：

| 组件 | 版本基线 | 说明 |
|---|---|---|
| Rust stable | 本机 **1.96.0**（2026-05-25）；`rustup check` 显示最新为 **1.97.1**（2026-07-14） | stable 上仍是 NLL |
| Rust nightly | **1.100.0-nightly (8fa1c96cf 2026-08-17)** | 本课程所有 MIR / Polonius 实验都在它上面实测 |
| Edition | **2024** | 2024 edition 改了 `if let` 和尾表达式的临时值作用域，直接影响借用检查，见第 12 章 |
| **Polonius Alpha** | **2026-08-04 起在 nightly 默认开启** | `-Zpolonius=off` 可关；目标"2026 年底前稳定化"，见第 16 章 |
| Miri | 默认 Stacked Borrows，`-Zmiri-tree-borrows` 切 Tree Borrows | 见第 26 章 |

> ⚠️ **本课程写在一个特殊的时间点。** 2018 年 NLL 落地之后，borrow checker 的核心算法
> 稳定了整整八年。2026-08-04，Polonius Alpha 在 nightly 默认开启，这是八年来第一次换代。
> 课程里每个边界案例都标注了 **NLL** 和 **Polonius Alpha** 两栏结果，全部在
> `rustc 1.100.0-nightly` 上实测过（见 [lab/](lab/)）。
>
> **在 stable 上验证课程里的 ✅ 时，请务必用 `rustc +nightly`**——
> 有 5 类案例在 stable（NLL）上仍然编译失败。

---

## 0. 先说结论：一张图看懂整个系统

这门课要讲的东西，本质上是**同一个约束在五个层面上的投影**：

```
                        ┌────────────────────────────────────┐
                        │   设计公理（第 03 章）              │
                        │   Aliasing XOR Mutability          │
                        │   「共享的不可变，可变的不共享」      │
                        └──────────────┬─────────────────────┘
                                       │ 落到类型系统
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
          ┌─────────────────┐ ┌────────────────┐ ┌────────────────┐
          │ 所有权 Ownership│ │ 借用 Borrowing │ │ 生命周期 Origin│
          │  (第 04 章)     │ │  (第 05 章)    │ │  (第 06 章)    │
          │  谁负责 drop    │ │ &T 可多 / &mut │ │ 'a =「这个引用 │
          │  移动 = 转移职责 │ │ T 独占         │ │  可能来自哪些   │
          │                 │ │                │ │  贷款」的集合   │
          └────────┬────────┘ └───────┬────────┘ └───────┬────────┘
                   └──────────────────┼──────────────────┘
                                      │ 编译器怎么算
                    ┌─────────────────▼──────────────────┐
                    │  MIR + 控制流图 + 贷款可达性分析      │
                    │  Polonius (第 07/08/15/16 章)       │
                    │  ├ loan：每次借用产生一笔「贷款」     │
                    │  ├ origin：'a = 一组可能的贷款       │
                    │  └ 活跃性 = (origin,point) 图上可达  │
                    │  〔上一代 NLL：region = 点集，见 07§9〕│
                    └─────────────────┬──────────────────┘
                                      │ 推广到线程
                    ┌─────────────────▼──────────────────┐
                    │  Send / Sync (第 22 章)             │
                    │  「无畏并发」不是新机制，是同一条规则  │
                    │  从「内存」推广到「时间」的直接推论     │
                    └─────────────────┬──────────────────┘
                                      │ 推广到 async
                    ┌─────────────────▼──────────────────┐
                    │  Future = 自引用状态机 (第 24 章)    │
                    │  Pin、'static、Send 传染             │
                    └────────────────────────────────────┘
```

**一句话版本**：Rust 把 C++ 里"你自己心里要记住"的别名规则，变成了编译器检查的类型规则。
所有让你痛苦的地方，都是这条规则的**精度不够**（编译器保守）或者**你的设计确实违反了它**（编译器是对的）——
这门课的核心技能，就是**一眼分辨这两种情况**。

---

## 1. 为什么 Go 开发者学这个特别容易翻车

你带着一整套 Go 的直觉过来，其中一部分会**主动坑你**：

| Go 里的习惯 | 在 Rust 里会发生什么 | 讲解章节 |
|---|---|---|
| 到处传指针，反正有 GC | 每个引用都要能证明"被指向的东西还活着" | 04, 06 |
| `append` 可能复制底层数组，你已经习惯了 | Rust 直接禁止你在持有元素引用时 `push` | 05, 11 |
| 结构体方法里随便读写各个字段 | `&mut self` 借的是**整个** self，字段级并发访问要拆 | 12, 21 |
| `go func(){ ... }()` 捕获外层变量 | 闭包捕获要么移动要么借用，`spawn` 还要求 `'static` | 22, 23 |
| `sync.Mutex` + `defer mu.Unlock()` | `MutexGuard` 的生命周期就是锁的持有时间——跨 `await` 会炸 | 19, 25 |
| 循环引用？GC 会处理 | 引用计数环会泄漏，你得自己用 `Weak` 或 arena | 20 |
| `interface{}` / `any` 到处塞 | trait object 带生命周期参数，默认 `'static` 的坑 | 10, 21 |

好消息是，你的另一部分 Go 经验是**直接可迁移的**：
- **逃逸分析**：Go 编译器判断"这个变量能不能放栈上"，用的分析和 borrow checker 的 liveness 是同一族。
- **`-race` 检测器**：Go 在运行时抓数据竞争，Rust 在编译期抓，抓的是**同一类 bug**。
- **slice 别名 bug**：`s2 := s1[:2]` 之后改 `s2` 影响 `s1`——你被这个坑过的经验，就是理解 `&mut` 排他性的最好入口。

---

## 2. 课程结构（28 章 + 3 附录 + lab）

### 阶段 0：地基（第 00–03 章，约 5 小时）

| 章节 | 主题 | 你会得到什么 |
|---|---|---|
| [00](00-rust-in-30min.md) | Rust 语法速通（Go 对照版） | 能读懂本课程后面所有代码，不多不少 |
| [01](01-memory-safety-history.md) | 内存安全的历史债 | 理解 borrow checker 到底在**防什么**——UAF、double free、迭代器失效、数据竞争的统一根因 |
| [02](02-rust-design-history.md) | Rust 设计史：从 GC 到所有权 | 为什么 Rust 砍掉了 `@T`、typestate、绿色线程；1.0 → NLL → Polonius 的三次换代 |
| [03](03-philosophy.md) | 设计哲学 | Aliasing XOR Mutability、局部推理、**为什么宁可拒绝正确程序**（soundness > completeness） |

### 阶段 1：核心机制（第 04–10 章，约 12 小时）

| 章节 | 主题 | 你会得到什么 |
|---|---|---|
| [04](04-ownership.md) | 所有权与移动 | `Drop` 的真实语义、部分移动、`Copy` 的边界、drop 顺序 |
| [05](05-borrowing.md) | 借用、重借用、两阶段借用 | 为什么 `v.push(v.len())` 能编译而 `v.push(v[0])` 不行 |
| [06](06-lifetimes.md) | 生命周期**不是**"活多久" | 把 `'a` 理解成**一个集合**（Polonius：贷款集 / NLL：点集），这是本课程最重要的一次认知翻转 |
| [07](07-borrowck-model.md) | **借用检查的计算模型（Polonius）** | loan / origin / (region,point) 图可达性；手工推演编译器的计算过程；附录含上一代 NLL 模型 |
| [08](08-borrowck-internals.md) | rustc 里 borrowck 真实的样子 | 读 MIR dump、`-Znll-facts`、loan / place / dataflow、亲手定位一个错误的来源 |
| [09](09-variance.md) | 型变 | 为什么 `&'a mut T` 对 `T` 不变、`PhantomData` 怎么用 |
| [10](10-subtyping-hrtb.md) | 子类型与 HRTB | `for<'a>`、闭包生命周期推断的经典坑 |

### 阶段 2：反直觉与 corner case（第 11–14 章，约 10 小时）

| 章节 | 主题 |
|---|---|
| [11](11-counterintuitive.md) | **反直觉合集**：25 个最小复现 + 根因 + 处方（全部实测） |
| [12](12-corner-cases.md) | 场景化 corner case：字段分割借用、match 守卫、临时值 drop、2024 edition 的作用域变更 |
| [13](13-self-referential-pin.md) | 自引用结构与 `Pin`：为什么天真的链表写不出来 |
| [14](14-nll-problem-cases.md) | **著名难题实测**：RFC 2094 的四个 problem case 今天各是什么状态；lending iterator + GAT；哪些"Rust 做不到"已经过时 |

### 阶段 3：Polonius（第 15–17 章，约 8 小时）

| 章节 | 主题 |
|---|---|
| [15](15-polonius-theory.md) | Polonius 的完整 datalog 形式化：逐条规则 + 手工跑一次不动点 |
| [16](16-polonius-alpha.md) | **2026-08 现状实测**：`-Zpolonius` 开关、Alpha 与完整 Polonius 的差距、性能、稳定化路线、迁移建议 |
| [17](17-borrow-checker-within.md) | 未来：view types、place-based lifetimes、内部引用 |

### 阶段 4：解决思路（第 18–21 章，约 10 小时）

| 章节 | 主题 |
|---|---|
| [18](18-solution-patterns.md) | **解法总表**：12 种把借用冲突解开的标准手法，及各自的代价 |
| [19](19-interior-mutability.md) | 内部可变性：`UnsafeCell` 是类型系统里唯一的合法裂缝 |
| [20](20-data-structures.md) | 图 / 树 / 双链表到底怎么写：arena + index、`Rc`/`Weak`、`unsafe` |
| [21](21-api-design.md) | 用生命周期设计 API：借用 vs 拥有、`Cow`、公开签名里出现 `'a` 的长期成本 |

### 阶段 5：并发与异步（第 22–25 章，约 10 小时）

| 章节 | 主题 |
|---|---|
| [22](22-send-sync.md) | `Send`/`Sync` 的本质：无畏并发是 borrow checker 的**推论**，不是新机制 |
| [23](23-concurrency.md) | 线程与借用：scoped threads、`Arc<Mutex<T>>`、rayon、数据竞争 vs 竞态条件 |
| [24](24-async-borrowing.md) | async 与借用：Future 是自引用状态机、跨 `await` 持有借用、`Send` bound 传染 |
| [25](25-async-pitfalls.md) | 异步经典陷阱：`MutexGuard` 跨 await、`spawn` 的 `'static`、取消安全性 |

### 阶段 6：越界与精通（第 26–27 章，约 6 小时）

| 章节 | 主题 |
|---|---|
| [26](26-unsafe-aliasing.md) | `unsafe` **不关闭** borrow checker：Stacked / Tree Borrows、Miri 实操 |
| [27](27-limits-and-comparison.md) | 理论边界；与 Cyclone / C++ / Swift / Mojo 的横向对比；"像 borrow checker 一样思考" |

### 附录

| 文件 | 内容 |
|---|---|
| [A](A-error-codes.md) | **错误码急诊手册**：一分钟分诊表 + 32 个错误码条目 → 病因 → 处方；含 edition 差异速查 |
| [B](B-glossary.md) | 术语表（中英对照，含 rustc 内部术语） |
| [C](C-exercises.md) | 分级练习 40 题 + 详解（含 5 道"最容易反直觉"的重点题） |
| [lab/](lab/) | **28 个案例 × (NLL / Polonius Alpha) 的可复现对照表**，`./run.sh` 一键重跑 |

---

## 3. 怎么用这门课

**如果你只有一个下午**：读 03（哲学）→ 06（生命周期到底是什么）→ 11（反直觉合集）→ 18（解法总表）。
这四章能让你从"和编译器打架"变成"知道编译器在想什么"。

**如果你在真实项目里被卡住了**：直接查附录 A，按错误码找到章节。

**如果你要系统学**：按顺序。第 06 章是分水岭——那一章的认知翻转没完成的话，后面全是死记硬背。

**每章的固定结构**（沿用你熟悉的格式）：

```
本章目标 → 问题背景 → 原理 → 手册/速查 → 动手实验 → 检查清单 → 常见坑
```

---

## 4. 环境准备

```bash
# 1) 安装 rustup（如果还没有）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 2) 本课程需要 stable + nightly 两个工具链
rustup toolchain install stable
rustup toolchain install nightly

# 3) 第 08 / 15 / 16 章要看 MIR 和 Polonius，需要 nightly 的这些组件
rustup component add --toolchain nightly rust-src
rustup component add --toolchain nightly miri     # 第 26 章

# 4) 验证
rustc --version                 # 本课程基线 1.96.0（最新 stable 为 1.97.1）
rustc +nightly --version        # 需要 2026-08-04 之后的 nightly（本课程用 1.100.0-nightly）

# 5) 确认 Polonius 在你的 nightly 上是默认开启的（2026-08-04 之后的 nightly）
rustc +nightly -Z help 2>&1 | grep polonius
```

**实验工程**：

```bash
cd lab
./run.sh               # 28 个案例 × (Polonius Alpha | NLL) 的完整对照表
EDITION=2021 ./run.sh  # 对比 edition 差异（19/20 号案例会变）
```

**实测汇总**（`rustc 1.100.0-nightly`，完整表见 [lab/README.md](lab/README.md)）：

```
两者都接受: 14   ★ Polonius 新增接受: 5   两者都拒绝: 9
```

那 **5 个 ★ 案例就是这次换代的全部实质内容**：
条件返回借用、`HashMap` get-or-insert（match 版 / loop 版）、条件重借用、lending iterator + 条件返回。

> `lab/` 里的每个例子都标了三个状态：`✅ 两者都接受` / `★ NLL 拒绝但 Polonius 接受` / `❌ 两者都拒绝`。
> 这个三态标注是本课程和其他 Rust 教程最大的区别——在 2026 年，"这段代码能不能过"
> 已经**不再是一个二值问题**了。

---

## 5. 本课程的实测承诺

这门课的每一个"能编译 / 不能编译"的断言，都在本机跑过。具体包括：

| 类别 | 做了什么 |
|---|---|
| **三态对照** | 28 个边界案例，每个都在 **NLL** 和 **Polonius Alpha** 两个引擎下实测（[lab/](lab/)） |
| **错误码** | 附录 A 的 32 个错误码条目，全部由实际编译采集，**不是凭记忆写的** |
| **edition 差异** | `if let` 死锁、尾表达式 drop 顺序、闭包捕获、RPIT 捕获——都在 2021/2024 下分别跑过 |
| **编译器内部** | 第 07/08/15 章的 MIR dump、region 点集、Polonius 事实文件，全是真实输出 |
| **Miri** | 第 26 章的 UB 案例，包括一个 **Stacked Borrows 判 UB 但 Tree Borrows 通过**的例子 |
| **性能** | 第 16 章的 Polonius 编译开销，是在 12800 行合成载荷上用 `-Ztime-passes` 实测的 |
| **全量回归** | 全书 513 个 `rust` 代码块由脚本逐个送进 `rustc` 编译，与块内自称的结论逐条比对 |
| **推翻的旧说法** | 5 条流传很广的结论被实测证伪（见下） |

**被实测证伪的五条常见说法**：

1. ❌ "固定长度数组用常量下标可以分割借用" → **不能**，报错是 `cannot borrow \`a[_]\``（下标被抹掉）
2. ❌ "NLL problem case #4 编译不过" → **今天在 NLL 上已经能过**（NLL 这些年一直在改进）
3. ❌ "async 里变量在 await 前用完就不影响 `Send`" → **不对**，判据是**作用域**而非最后一次使用
4. ❌ "`let _ = mutex.lock()` 会静默地立刻解锁" → **编译器现在拦得住**（`let_underscore_lock`
   是 deny-by-default 硬错误）；但它**只认标准库同步锁**，`RefCell` / 自定义 guard 照样中招（第 11 章）
5. ❌ "`self.method_taking_&mut(a.field)` 会和先前的 `&self` 冲突" → **不会**，
   两阶段借用让参数在"预留期"求值；只有把**引用本身**传进去才冲突（第 08 章 §7）

> ### ⚠️ 写"最小复现"时最常犯的错
> **借用不被使用，就没有活跃区间，也就不报错。**
> ```rust
> let a = &mut v[0];
> let b = &mut v[1];   // 只有这两行 → 编译通过！
> *a += *b;            // 加上这行 → 才是 E0499
> ```
> 本课程所有 ❌ 示例都带着对借用的后续使用。网上流传的很多复现漏了这一行，
> 粘进编译器发现不报错，就以为规则变了——其实是复现写错了。

> **复测方法**：每章的"动手实验"里都给了完整命令。
> 如果你的结果和课程不一致，**以你的实测为准**——并且那说明 Rust 又变了。

---

## 6. 一个诚实的预期管理

这门课不会让你"再也不遇到借用错误"。真正的大师也天天遇到。区别在于：

| 新手 | 大师 |
|---|---|
| 看到红色报错 → 焦虑 → 随机试 `clone()` / `&` / `.to_owned()` | 看到报错 → 读第二行的 `note:` → 30 秒内定位是**哪两个借用**打架 |
| 认为编译器在刁难自己 | 知道 90% 情况编译器是对的（你的设计里确实有别名问题），10% 是编译器精度不够 |
| 用 `Rc<RefCell<T>>` 解决一切 | 知道那是把编译期检查换成运行时 panic，只在真正需要共享可变时才用 |
| 生命周期标注靠试 | 能在写函数签名之前就想清楚"数据从哪来、活多久、谁拥有" |
| 遇到 async 借用问题就重写成 `Arc<Mutex<>>` + `clone` | 知道跨 `await` 持有的是什么、为什么状态机需要 `Pin` |

**核心心法（第 03 章会展开）**：
> Borrow checker 不是在检查你的代码，它是在**要求你把数据的所有权结构说清楚**。
> 大部分借用错误的正确解法不是"绕过检查"，而是"重新设计数据结构"。

---

## 7. 本课程的写作基线（复现信息）

```
rustc (stable) : 1.96.0 (ac68faa20 2026-05-25)   ← 本机；rustup 显示最新为 1.97.1
rustc (nightly): 1.100.0-nightly (8fa1c96cf 2026-08-17)
edition        : 2024（部分实验对比 2021）
平台           : macOS / aarch64
Polonius       : nightly 默认开启（2026-08-04 起）
Miri           : miri 0.1.0 (8fa1c96cfd 2026-08-17)
```

准备好了就从 [00-rust-in-30min.md](00-rust-in-30min.md) 开始。
