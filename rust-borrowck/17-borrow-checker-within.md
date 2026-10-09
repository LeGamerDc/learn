# 17 - 未来：The Borrow Checker Within

> 本章目标：了解 Polonius Alpha 之后的路线图。这不是"畅想"——
> 它是 rust-lang 2026 的 **Flagship Goal**，有明确的设计原则和排期。
> 更重要的是：**它精确地划定了"哪些抱怨会被解决、哪些不会"**。
> ⚠️ 本章讲的**全部是提案**，语法可能变，没有任何一项已经实现。
> 预计用时：1.5 小时。

---

## 1. 这个项目要解决什么

第 14 章把"编译器拒绝"分成三类。Polonius Alpha 解决的是**精度**那一类。
剩下的**签名表达力**那三个痛点：

| 痛点 | 你每天遇到的形式 | 章节 |
|---|---|---|
| **方法借走整个 `self`** | 两个 getter 不能同时用；遍历一个字段时不能改另一个 | 05, 12 |
| **不能同时借两个元素** | `&mut v[0]` + `&mut v[1]` | 08, 11 |
| **写不了自引用结构** | 解析器想同时拥有 `String` 和指向它的 `&str` | 13 |

**官方对这三个痛点的诊断**（roadmap 原文大意）：

> 借用检查器有时会拒绝**在概念上完全符合 "mutation xor sharing" 纪律**的代码。这造成三个问题：
>
> 1. **用户困惑**：写了逻辑正确的代码却被拒，于是怀疑自己而不是意识到编译器不够精确
> 2. **低效的绕道**：不得不重构成自由函数、用索引代替引用、或加 `RefCell` 做运行时检查
> 3. **表达力缺口**：有些模式（比如 lending iterator）根本写不出来

---

## 2. 两条设计原则（★ 值得记住）

### 原则 1：Close the gap, don't change the discipline

> **"缩小差距，不改变纪律。"**
>
> 目标只针对那些**已经符合 "mutation xor sharing"、但当前无法表达**的模式。

**这是一个非常强的承诺**：第 03 章的公理**不会变**。
所有新特性都是"让你能把已经成立的事实告诉编译器"，而不是"放宽规则"。

**推论**：如果你的代码真的有别名冲突，**永远不要指望未来的 Rust 会接受它**。

### 原则 2：Explicit and concrete first

> **"先显式、先具体。"**
>
> 从内置引用和具体字段上的**显式标注**起步，之后再叠加推断和泛化。

**推论**：这些特性刚落地时会**很啰嗦**。别因此判断它没用——
生命周期省略规则也是 1.0 之后一点点加出来的（第 02 章准则 3）。

---

## 3. 四个特性及其排期

| 特性 | 时间 | 解决什么 |
|---|---|---|
| **Polonius Alpha** | 2026（进行中） | 条件借用、lending iterator ← 第 16 章 |
| **Full Polonius** | 未来 | 完整流敏感（链表类模式） |
| **Place-based lifetime syntax** | 未来 | 给生命周期"命名它借自哪里" |
| **View types** | 未来 | 在签名里声明"我访问哪些字段" |
| **Internal references** | 未来 | 结构体持有指向自己数据的引用 |

**当前状态**（2026-08 核实）：
- place-based syntax：**已有一个成形的表述，需要 bikeshedding**（语法名字的争论）
- view types：**需要建模**，在"strong update"上有开放的设计问题
- internal references：**已在一个简化的 Rust 变体上形式化**，需要移植到完整 Rust

**负责人**：Niko Matsakis（联系人），任务负责人包括 Amanda Stjerna、Rémy Rakic 等。

---

## 4. Place-based lifetimes：给生命周期起个真名字

### 4.1 想法

第 06/07 章说过：`'a` 在编译器内部是 origin，含义是"这个引用可能来自哪些贷款"。
**Place-based lifetime 就是把这个内部概念变成用户可写的语法**——
直接用**它借自的那个 place** 来命名生命周期。

### 4.2 提案语法

```rust
// 当前：'a 是一个抽象的名字，你得自己在脑子里追踪它绑到哪
fn get_default<'r, K: Hash + Eq + Copy, V: Default>(
    map: &'r mut HashMap<K, V>, key: K,
) -> &'r mut V { ... }

// 提案：直接说"借自参数 map"
fn get_default<K: Hash + Eq + Copy, V: Default>(
    map: &mut HashMap<K, V>, key: K,
) -> &'map mut V { ... }
//     ^^^^ "borrowed from the parameter map"
```

函数体内也能用：

```rust
struct WidgetFactory { manufacturer: String, model: String }

impl WidgetFactory {
    fn new_widget(&self, name: String) -> Widget {
        let name_suffix:  &'name str       = &name[3..];
        let model_prefix: &'self.model str = &self.model[..2];
        //                 ^^^^^^^^^^^^ 借自 self 的 model 字段
    }
}
```

### 4.3 为什么这是基础

**place-based lifetime 是后两个特性的前置**：
- view types 用它来写"我访问哪些字段"
- internal references 用它来写"这个字段引用同结构的哪个字段"

**它也让生命周期错误的诊断变得可读**：
今天你看到 `'1` 和 `'2`，将来能看到 `'map` 和 `'self.model`。

---

## 5. View types：本课程读者最关心的那个

### 5.1 它解决第 10/12 章那个痛点

```rust
// 今天：❌ E0499（lab/12）
struct S { counter: u32, widgets: Vec<Widget> }
impl S {
    fn increment_counter(&mut self) { self.counter += 1; }
}
fn f(s: &mut S) {
    for w in &s.widgets {          // 借了 s.widgets
        s.increment_counter();     // ❌ 借了整个 s
    }
}
```

**提案语法**：

```rust
impl WidgetFactory {
    fn increment_counter(&mut {counter} self) {
        //                    ^^^^^^^^^ ★ "我只访问 counter 字段"
        self.counter += 1;
    }
}
```

有了这个签名，编译器就能证明 `increment_counter` 不碰 `widgets`，
于是上面的循环合法。

### 5.2 这会改变什么

| 今天必须的绕道 | 有 view types 之后 |
|---|---|
| splitter 方法 `fn split(&mut self) -> (&mut A, &mut B)` | 不需要 |
| 把方法拆成自由函数，参数只取需要的字段 | 不需要 |
| 把相关字段打包成子结构体（纯粹为了借用检查） | 不需要 |
| 把值先拷出来再调方法 | 不需要 |
| 用 `RefCell` 把检查推到运行时 | 不需要 |

**第 18 章"解法总表"里的一大半手法，将来会变成历史。**

### 5.3 开放的设计问题："strong update"

roadmap 里提到 view types 在 "strong updates" 上还有开放问题。这是指：

```rust
// 如果一个字段是 Option<T>，方法把它从 None 改成 Some(x)，
// 类型系统要不要追踪这个"状态变化"？
fn init(&mut {data} self) { self.data = Some(compute()); }
// 调用之后，编译器应该知道 self.data 一定是 Some 吗？
```

**这本质上又回到了 typestate**（第 02 章！）——Rust 2012 年砍掉的那个东西。
**历史在这里绕了个圈**：当年砍掉 typestate 的理由之一是"和别名控制冲突"，
而现在有了成熟的别名控制之后，有限形式的 typestate 又变得可行了。

---

## 6. Internal references：自引用结构

### 6.1 提案语法

```rust
struct Message {
    text: String,
    headers: Vec<(&'self.text str, &'self.text str)>,
    body: &'self.text str,
}
```

**注意最关键的一点**：**这个结构体没有任何生命周期参数**。

对比今天你必须写的：

```rust
// 今天：要么带生命周期参数（传染性极强，第 06/21 章）
struct Message<'a> { text: String, headers: Vec<(&'a str, &'a str)>, body: &'a str }
// ↑ 而且这个还编译不过（自引用，lab/15）

// 要么存 range（第 13 章的标准替代）
struct Message {
    text: String,
    headers: Vec<(Range<usize>, Range<usize>)>,
    body: Range<usize>,
}
```

### 6.2 为什么它能跨线程

roadmap 里特意提到：这样的结构 **"can be safely sent across threads despite containing
internal references"**。

**原因**：`&'self.text str` 引用的是**结构体自己的一部分**，
所以整个结构体作为一个单元移动时，内部引用仍然有效（编译器会保证 fixup 或者禁止会破坏它的移动）。
它不借用**外部**任何东西，所以满足 `T: 'static`（第 06 章！）→ 可以 `Send`。

**这正好解决了第 13 章那个痛点**：自引用结构不能返回、不能移动。

### 6.3 和 `Pin` 的关系

**这不会取代 `Pin`**。两者解决不同的问题：

| | internal references | `Pin` |
|---|---|---|
| 谁用 | 用户写的数据结构 | 编译器生成的 `Future` / 手写的自引用 unsafe 代码 |
| 保证 | 类型系统知道引用指向哪个字段 | 值不会移动 |
| 移动 | **允许**（编译器保证正确） | **禁止** |

async 的状态机大概率仍然用 `Pin`（因为它的自引用是编译器生成的、形态更复杂）。

---

## 7. Full Polonius：剩下的流敏感

Polonius Alpha 是完整 Polonius 的子集（第 16 章）。剩下的部分主要针对
**链表类的模式**——那些需要"贷款沿着数据结构一层层转移"的形态。

**没有时间表。** 官方在 Alpha 稳定化博客里明确说：
"we don't currently have any concrete plans to continue active feature work on the
Polonius implementation after the stabilization"。

**读法**：Polonius 这条线在 Alpha 之后**暂停**，资源转向 place-based syntax / view types /
internal references——因为后三者解决的痛点更常见。

---

## 8. 这对你今天的决策意味着什么

### 8.1 该怎么写代码

| 情况 | 建议 |
|---|---|
| 遇到"方法借走整个 self" | **照常用第 18 章的手法绕**。view types 没有时间表，别等 |
| 想写自引用结构 | **照常用 range / index / `ouroboros`**。internal references 没有时间表 |
| 遇到条件借用（5 个 ★ 形态） | 这个**快了**（2026 底）。stable 上先绕，稳定后简化 |
| 设计公开 API 的签名 | 记住原则 1：**公理不会变**。按 "mutation xor sharing" 设计，不会白做 |

### 8.2 该怎么读这些提案

**警惕两种误读**：

1. ❌ **"以后 Rust 就不用管借用了"** —— 原则 1 明确说不改变纪律。
   你仍然要理解所有权、借用、生命周期。这些特性只是让你**说得更精确**。

2. ❌ **"现在学的东西要过时了"** —— 恰恰相反。
   place-based lifetime 是把 origin 这个**内部概念**暴露给用户，
   **你越理解第 06/07 章，就越容易用好它**。

### 8.3 一个有价值的判断练习

拿你项目里最难受的那段借用代码，问：

> **它属于哪一类？**
> - 真·别名冲突 → 永远要改设计
> - 条件借用（★ 骨架）→ 2026 底解决
> - 字段粒度 → view types，无时间表
> - 自引用 → internal references，无时间表
> - 索引不相交 → view types / place-based，无时间表

**这个分类能告诉你"该等还是该改"。**

---

## 9. 动手实验

### 实验 1：给你的绕道分类

翻一下你（或你熟悉的开源项目）的 Rust 代码，找出这些模式：

```bash
# 找 splitter 方法
rg 'fn \w+\(&mut self\) -> \(&mut '
# 找 RefCell（可能是借用检查的绕道）
rg 'RefCell<' --stats
# 找 range 代替引用的模式
rg 'Range<usize>'
# 找 ouroboros / self_cell
rg 'ouroboros|self_cell'
```

**对每一处问**：它是因为借用检查才这么写的吗？将来哪个特性能简化它？

### 实验 2：手写"未来版本"

把第 5.1 节那个例子用**今天的四种手法**分别写一遍，
然后写一遍**假想的 view types 版本**，对比行数和可读性。

<details><summary>参考答案</summary>

```rust
struct S { counter: u32, widgets: Vec<Widget> }

// 手法 1：把 counter 拷出来
fn f1(s: &mut S) {
    let mut c = s.counter;
    for _w in &s.widgets { c += 1; }
    s.counter = c;
}

// 手法 2：自由函数
fn inc(counter: &mut u32) { *counter += 1; }
fn f2(s: &mut S) {
    let S { counter, widgets } = s;          // ★ 解构，编译器知道不相交
    for _w in widgets.iter() { inc(counter); }
}

// 手法 3：splitter
impl S { fn split(&mut self) -> (&mut u32, &mut Vec<Widget>) { (&mut self.counter, &mut self.widgets) } }
fn f3(s: &mut S) { let (c, w) = s.split(); for _ in w.iter() { *c += 1; } }

// 手法 4：先收集
fn f4(s: &mut S) { let n = s.widgets.len() as u32; s.counter += n; }

// 假想的 view types 版本
// impl S { fn increment_counter(&mut {counter} self) { self.counter += 1; } }
// fn f5(s: &mut S) { for _w in &s.widgets { s.increment_counter(); } }
```

**注意手法 2 里的解构 `let S { counter, widgets } = s;`**——
这是今天最接近 view types 的写法，第 18 章会把它列为一个标准手法。

</details>

### 实验 3：跟踪进展

```bash
# 项目目标
open https://rust-lang.github.io/goals/2026/roadmap-borrow-checker-within.html
# view types 的 pre-RFC 讨论
open https://github.com/rust-lang/rfcs/issues/3269
# Niko 的设计博客
open https://smallcultfollowing.com/babysteps/blog/2024/06/02/the-borrow-checker-within/
```

---

## 10. 本章检查清单

- [ ] 知道这是 rust-lang 2026 的 Flagship Goal，不是民间畅想
- [ ] **能背出两条设计原则，尤其是"不改变纪律"**
- [ ] 知道四个特性的排期和当前状态
- [ ] 能说出 place-based lifetime 的提案语法（`'map`、`'self.model`）
- [ ] 能说出 view types 的提案语法（`&mut {counter} self`）及它解决什么
- [ ] 知道 internal references 的关键特点：**结构体不带生命周期参数**
- [ ] 知道 Full Polonius 在 Alpha 之后**暂停**
- [ ] **能给自己项目里的借用痛点分类，判断"该等还是该改"**

---

## 11. 常见坑

| 误解 | 事实 |
|---|---|
| "这些特性快了" | 只有 Polonius Alpha 有时间表（2026 底）。**其余三个都没有** |
| "有了 view types 就不用学借用了" | 原则 1：**不改变纪律**。它只是让你说得更精确 |
| "internal references 会取代 `Pin`" | 不会。两者解决不同问题 |
| "语法就长这样了" | 全是提案。place-based syntax 明确还在 bikeshedding 阶段 |
| "现在学的会过时" | 反过来：place-based lifetime 就是把 origin 暴露出来，理解越深越好用 |
| "Rust 团队终于要放宽借用规则了" | 从来没有过这个计划。公理是 2014 年定的，至今没变 |

---

**阶段 3 到此结束。** 你现在对 borrow checker 的过去、现在、未来都有了完整的图景。
接下来第 18–21 章是**纯工程手册**——今天就能用的解法。

下一章：[18 - 解法总表](18-solution-patterns.md)
