# 27 - 理论边界、横向对比，与"像 borrow checker 一样思考"

> 本章目标：收尾。三件事：
> **① borrow checker 的理论极限在哪**、
> **② 其它语言在这条路上走到了哪**、
> **③ 把整门课压缩成一套可以随身携带的思维习惯**。
> 预计用时：2 小时。

---

## 1. 理论边界：什么是**永远**做不到的

### 1.1 不可判定性

判定"一个程序在运行时是否违反 Aliasing XOR Mutability"**等价于停机问题**：

```rust
let i = f();                  // f 的返回值编译期不可知
let j = g();
let a = &mut v[i];
let b = &mut v[j];            // i == j 吗？
```

要回答就得算出 `f()` 和 `g()`。**所以任何静态检查器必然是不完备的**（第 03 章 §6）。

**推论**：无论 Polonius、view types 还是任何未来的特性，
**永远会有"运行时安全但编译器拒绝"的程序**。这不是工程缺陷，是数学事实。

### 1.2 三层不同的"做不到"

| 层次 | 例子 | 会被解决吗 |
|---|---|---|
| **① 分析精度不足** | 条件借用（第 14 章 5 个 ★ 案例） | ✅ Polonius 已解决 |
| **② 签名表达力不足** | 方法借走整个 self、自引用结构 | ⏳ view types / internal references（第 17 章，无时间表） |
| **③ 理论上不可判定** | 运行时才知道的索引是否相等 | ❌ **永远不会** |

**第 ③ 层的应对**：把不变量**移到运行时**（`split_at_mut` 里的 `assert!`、
`get_disjoint_mut` 返回 `Option`、`RefCell` 的计数器）或**移到类型里**
（用不同的类型表示不同的分区）。

### 1.3 borrow checker 的设计目标本来就是有限的

回顾第 03 章 §8——它**不**保证：不泄漏、不死锁、无竞态条件、不 panic、
无整数溢出、逻辑正确、`Drop` 一定执行。

> ### ★ 一个成熟的认识
> **borrow checker 是一个"单一目的"的工具：它证明程序没有别名可变冲突。**
> 它不是"正确性检查器"，也不打算是。
>
> 想要更强的保证，你需要**形式化验证工具**（见 §3），
> 而那是完全不同量级的投入。

---

## 2. 横向对比：其它语言走到哪了

### 2.1 全景表

| 语言 | 别名可变问题的解法 | 检查时机 | 状态（2026-08） |
|---|---|---|---|
| **C** | 不解决 | — | `restrict` 是手工承诺，无检查 |
| **C++** | RAII + 智能指针（约定） | — | 见 §2.2 |
| **Java / C#** | GC 解决释放，别名不管 | 部分运行时 | 成熟 |
| **Go** | 同上 + `-race`（运行时抽样） | 部分运行时 | 成熟 |
| **Swift** | ARC + exclusivity enforcement | 主要运行时 | 见 §2.3 |
| **Rust** | 类型系统全解 | **编译期** | NLL → Polonius（本课程） |
| **Cyclone** | 区域 + 唯一指针 | 编译期 | 研究项目，2006 年停止（Rust 的直接祖先） |
| **ATS** | 线性类型 + 依赖类型 | 编译期 | 学术，极陡峭 |
| **Mojo** | 借鉴 Rust 的所有权 + ASAP 释放 | 编译期 | 见 §2.4 |
| **Hylo（原 Val）** | 可变值语义（mutable value semantics） | 编译期 | 见 §2.5 |
| **Zig** | 显式分配器 + 无隐藏控制流 | — | 不解决别名问题，靠工具（GPA、ASan） |
| **Ada / SPARK** | 契约 + 定理证明 | 编译期（证明） | 成熟但小众；近年也加了借用检查 |

### 2.2 C++：委员会选了另一条路（★ 2026 的大新闻）

C++ 曾经有两个内存安全提案：

| 提案 | 思路 |
|---|---|
| **Safe C++（P3390）** | 直接引入 Rust 式的**借用检查器** + 生命周期标注，作为新方言 |
| **Profiles** | 一组可选的、渐进的"安全档案"（类型安全、边界安全、生命周期安全…），**面向现有代码** |

**2026 年的结果**（核实）：

- 安全与安全性工作组投票：**Profiles 19 票，Safe C++ 9 票，两者都要 11 票**
- **Safe C++ 在 ISO 内的工作已终止**
- **C++26 在 2026-03 定稿时，profiles 被排除在外**
- Stroustrup 的类型安全 profile（P3984）和 profiles 框架都改为**瞄准 C++29**，无最终日期承诺

> ### ★ 这对理解 Rust 的价值很有帮助
> C++ 社区的核心分歧是：
> **借用检查需要"重写代码"（新方言），而 C++ 的核心承诺是"现有代码继续能编译"。**
>
> Rust 之所以能做到，正是因为它从零开始，把所有权做成语言的**核心**而非**补丁**
> （第 02 章 §4.3：Cyclone 想保持 C 兼容，所以背了很多包袱）。
>
> **推论**：如果你在评估"要不要把 C++ 项目迁到 Rust"，
> 别指望 C++ 会在可预见的未来长出等价的编译期保证。

### 2.3 Swift：同一个方向，不同的时机

Swift 5 引入了 **exclusivity enforcement**（独占性检查）：

```swift
func modify(_ a: inout Int, _ b: inout Int) { }
var x = 0
modify(&x, &x)          // ❌ 违反独占性
```

**和 Rust 的对比**：

| | Swift | Rust |
|---|---|---|
| 规则 | 同一个 `inout` 访问期间不能有其它访问 | `&mut` 独占 |
| 检查 | 局部变量编译期；**类属性/全局变量运行时** | 全部编译期 |
| 默认内存管理 | ARC（引用计数） | 所有权 |
| 逃逸 | `withUnsafe*` 系列 | `unsafe` |

**Swift 后来又加了 `~Copyable`（非可复制类型）和 `borrowing`/`consuming` 参数修饰符**——
**方向和 Rust 高度一致**，只是 Swift 选择让它们是可选的、渐进的。

### 2.4 Mojo：Rust 的所有权 + Python 的语法

```mojo
fn process(borrowed data: List[Int]): ...      # ≈ &T
fn modify(inout data: List[Int]): ...          # ≈ &mut T
fn consume(owned data: List[Int]): ...         # ≈ T
```

**主要差别**：Mojo 用 **ASAP（As Soon As Possible）析构**——
值在最后一次使用后**立刻**销毁，而不是作用域末尾。

> ### ★ 这正好解决了第 04 章 §3.4 那个不对称性
> Rust：借用止于最后一次使用，但 **drop 在作用域末尾**。
> Mojo：两者统一在"最后一次使用"。
>
> **代价**：`Drop` 的时机变得不那么可预测（RAII guard 的语义会变），
> 且和 Rust 的"作用域即资源生命期"心智模型冲突。这是一个真实的设计权衡，
> 没有绝对的对错。

### 2.5 Hylo（原 Val）：可变值语义

Hylo 的思路更激进：**根本不暴露引用类型给用户**。
所有参数用 `let`/`inout`/`sink`/`set` 四种"传递约定"，
编译器保证不会有观察得到的别名。

**优点**：没有生命周期标注，心智负担小得多。
**代价**：某些数据结构（图、观察者）表达起来更难；生态还很早期。

---

## 3. 想要更强的保证：形式化验证

borrow checker 只证明"无别名冲突"。想证明"这个函数确实返回排序后的数组"？
那是形式化验证的领域。

| 工具 | 方法 | 特点 |
|---|---|---|
| **Kani** | 有界模型检验（MIR → Goto-C → CBMC） | ★ **唯一明确支持验证标准库的**（`verify-std`）；擅长 **unsafe 代码** |
| **Prusti** | 基于 Viper 的演绎验证 | 混合方案：safe Rust 高度自动化 + unsafe 半自动 |
| **Creusot** | 演绎验证 + prophecy | ★ **比 Prusti 支持更广的借用模式** |
| **Verus** | SMT 求解 | 系统软件验证，性能好 |
| **MIRAI** | 抽象解释 | Facebook 出品，静态分析 |
| **RustBelt** | Coq/Iris 里的语义模型（λRust） | ★ **证明了 Rust 类型系统本身是 sound 的**，以及标准库里 `unsafe` 抽象的正确性 |
| **a-mir-formality** | rustc 的形式化模型 | ★ **Polonius Alpha 稳定化的前置条件之一**（第 16 章） |

> ### RustBelt 的意义
> 它回答了一个基础问题：**"Rust 的类型系统真的 sound 吗？"**
> 更重要的是，它给出了一个框架，用来证明
> **"某个用了 `unsafe` 的库（如 `Rc`、`RefCell`、`Mutex`）确实提供了安全的 API"**。
>
> 你在第 19 章用的每一个内部可变性类型，它们的 soundness 都是被这套框架论证过的。

---

## 4. 像 borrow checker 一样思考（★ 本课程的收尾）

### 4.1 一条公理

> **Aliasing XOR Mutability**
> 对任意一份数据，在任意一个程序点上：要么多处可读，要么一处可写。

**整门课的其它内容，全部是这条公理的推论。**

### 4.2 三个思维习惯

#### 习惯 1：写代码前先画数据流

对每份重要的数据问三个问题：

1. **谁拥有它？**（谁负责 drop）
2. **它要活多久？**（比调用者短 / 一样长 / 永生）
3. **同一时刻有几处要碰它？几处要写？**

想清楚这三个，函数签名自然就出来了。想不清楚就直接写，一定会和编译器打架。

#### 习惯 2：把 `&mut` 念成"独占"

第 03 章说过，再说最后一遍。念成"独占"之后：
- "为什么 `&Cell<T>` 能改？"→ 规则是关于**独占**的，不是关于可变的
- "为什么 `&mut self` 期间不能读别的字段？"→ 你把**整个** self 独占出去了
- "为什么 `&mut T` 不能 `Copy`？"→ 复制一份就有两个了

#### 习惯 3：报错时先分类，再找解法

```
借用错误
   │
   ├─ ① 运行时真有别名冲突吗？
   │      是 ──► 编译器对。改设计（第 20/21 章）
   │      否 ──▼
   ├─ ② 内联展开成直接字段/元素访问能过吗？
   │      能 ──► 签名表达力不足。第 18 章手法 4–8
   │      否 ──▼
   ├─ ③ 匹配第 14 章的"骨架"吗？
   │      是 ──► 精度问题。nightly 上能过；stable 用第 18 章手法
   │      否 ──▼
   └─ ④ 回到 ①，八成真的有冲突
```

**新手在 ① 就卡住（不知道自己的代码有没有别名）。大师 30 秒走完全程。**

### 4.3 一张随身速查卡

```
┌─────────────────────────────────────────────────────────────┐
│  公理：Aliasing XOR Mutability                               │
│                                                              │
│  &T   共享，只读，Copy         │  region/origin = 一组贷款     │
│  &mut T 独占，可写，reborrow    │  借用止于最后一次使用          │
│  T    唯一所有者，负责 drop     │  drop 在作用域末尾  ★ 不对称   │
│                                                              │
│  借用粒度 = place（字段可拆，下标不可拆）                       │
│  借用检查只看签名，从不跨函数                                   │
│                                                              │
│  Send  = 所有权能跨线程                                        │
│  Sync  = &T 能跨线程（⟺ &T: Send）                            │
│  async = 作用域跨 await 的变量进入状态机  ★                     │
│                                                              │
│  解法优先级：                                                 │
│    1. 挪动最后一次使用 / 拷贝值 / 块收缩                        │
│    2. 解构 / splitter / 自由函数 / split_at_mut               │
│    3. mem::take / entry 风格 API                             │
│    4. 索引 / arena  ★ 最通用                                  │
│    5. RefCell / Mutex（编译期 → 运行时）                       │
│    6. unsafe 封装 + Miri                                     │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 三个"不要"

1. **不要为了让编译器闭嘴而用 `Rc<RefCell<T>>`**
   它把编译期错误换成了运行时 panic，且失去 `Send`。
   只在**真正需要共享所有权**时用。

2. **不要因为"觉得慢"而拒绝 `.clone()`**
   先让代码跑起来，然后**问自己为什么需要它**。
   如果答案是"不知道"，那才是问题。

3. **不要相信任何没标日期的 "Rust 做不到 X"**
   包括本课程。用 `lab/run.sh` 的方式**自己实测**。

---

## 5. 学完之后往哪走

| 方向 | 资源 |
|---|---|
| **实战链表** | [Learn Rust With Entirely Too Many Linked Lists](https://rust-unofficial.github.io/too-many-lists/) |
| **unsafe 深入** | [The Rustonomicon](https://doc.rust-lang.org/nomicon/) |
| **可视化理解借用** | [Aquascope](https://cognitive-engineering-lab.github.io/aquascope/) |
| **编译器内部** | [rustc dev guide](https://rustc-dev-guide.rust-lang.org/borrow-check.html) |
| **Polonius 跟进** | [rust-lang/polonius](https://github.com/rust-lang/polonius)、[项目目标 #118](https://github.com/rust-lang/rust-project-goals/issues/118) |
| **未来特性** | [The Borrow Checker Within](https://smallcultfollowing.com/babysteps/blog/2024/06/02/the-borrow-checker-within/) |
| **形式化** | [RustBelt](https://plv.mpi-sws.org/rustbelt/)、[Kani](https://model-checking.github.io/kani/) |
| **async 深入** | [Async Rust（O'Reilly）](https://www.oreilly.com/)、tokio 官方 tutorial |
| **设计模式** | [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/) |

**最好的下一步其实是**：**拿一个真实项目写它**。
本课程给了你完整的模型和手册，但"30 秒内分类一个借用错误"这个技能
只能通过重复获得。

---

## 6. 最后的动手实验

### 实验 1：给自己出一份考卷

不查资料，回答：

1. `'a` 是什么？（Polonius 的答案和 NLL 的答案）
2. 为什么 `&mut T` 对 `T` 是不变的？
3. `v.push(v.len())` 为什么能编译，`Vec::push(&mut v, v.len())` 为什么不能？
4. `let _ = m.lock()` 和 `let _g = m.lock()` 有什么区别？
5. `T: 'static` 是什么意思？`String` 满足吗？
6. 为什么 `MutexGuard` 不是 `Send`？这导致了什么 async 问题？
7. Polonius Alpha 解决了什么？没解决什么？
8. 判断一个 async 变量是否进入状态机的判据是什么？
9. `unsafe` 解锁了哪五件事？
10. 你能背出第 4.3 节那张速查卡吗？

**答不上来的题，回对应章节。**

### 实验 2：审计一个真实项目

挑一个你熟悉的 Rust 开源项目（或自己的），统计：

```bash
rg 'Rc<RefCell<|Arc<Mutex<' --stats           # 共享可变状态
rg '\.clone\(\)' --stats                       # 克隆
rg 'unsafe' --stats                            # unsafe
rg "<'[a-z]+>" --stats                         # 带生命周期参数的类型
rg 'fn \w+\(&mut self\) -> \(&mut ' --stats    # splitter 方法
```

**对每一类抽样 5 处，问**：
- 它是必要的吗？
- 它属于第 1.2 节的哪一层？
- 有没有第 18 章的更好手法？

### 实验 3：复测整个课程

```bash
cd lab
rustc +nightly --version          # 记下今天的版本
./run.sh
EDITION=2021 ./run.sh
```

**和课程里记录的结果对比。** 有差异的地方，就是 Rust 在你学完之后又变了的地方——
把它们记下来，那是你自己的第一手资料。

---

## 7. 结语

回到第 01 章那七段代码。现在你应该能：

- 说出它们的**统一根因**（别名 + 可变 + 有效期重叠）
- 说出 GC **解决不了**其中的哪四个
- 说出 Rust 用**哪个机制**挡住了每一个
- 说出这套机制的**理论边界**在哪
- 遇到编译器拒绝时，**30 秒内分类**并选出手法

**从"和编译器打架"到"用 borrow checker 的方式思考"，中间隔的就是这 28 章。**

最后一句话：

> **Borrow checker 不是在检查你的代码，
> 它是在要求你把数据的所有权结构说清楚。**
>
> 大部分借用错误的正确解法不是"绕过检查"，而是"重新设计数据结构"。
> 而当你真的重新设计之后，你会发现——**那个设计本来就更好**。

---

## 附录

- [A - 错误码急诊手册](A-error-codes.md)
- [B - 术语表](B-glossary.md)
- [C - 分级练习 40 题](C-exercises.md)
- [lab/ - 可复现的实验床](lab/)
