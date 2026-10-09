# 08 - rustc borrowck 内部结构

> 本章目标：打开引擎盖。知道借用检查在编译器源码里的**具体位置**、
> **哪几个数据流分析在跑**、**每个错误是从哪段代码发出来的**。
> 这一章的价值不在于让你去改 rustc，而在于：当你遇到一个诡异错误时，
> 你能**自己去查**而不是在 StackOverflow 上碰运气。
> 预计用时：2.5 小时。

---

## 1. 借用检查在编译流水线里的位置

```
源码
 │  rustc_parse
 ▼
AST ──rustc_ast_lowering──► HIR
                             │  rustc_hir_typeck（类型推断、方法解析、trait 求解）
                             ▼
                            THIR
                             │  rustc_mir_build
                             ▼
                            MIR (built)
                             │
                             │  ★ query: mir_borrowck        ← 本章主角
                             │     ├─ MIR type check
                             │     ├─ region inference
                             │     └─ borrow check
                             ▼
                            MIR (analysis)
                             │  优化 pass
                             ▼
                            MIR (optimized) ──► LLVM IR ──► 机器码
```

**关键事实**：借用检查发生在**类型检查之后、优化之前**。
`mir_borrowck` 这一个 query 里同时跑着**两代引擎的组件**：
Polonius 负责第一阶段（贷款传播 / 可达性），NLL 的数据流负责第二阶段（active loans）。
`-Zpolonius=off` 只是跳过第一阶段，退回纯 NLL 的 region 求解。

推论：
- 类型错误会**先于**借用错误报出来（所以修完类型错误可能冒出一堆借用错误）
- 借用检查的结果**不影响生成的代码**——它是纯粹的验证 pass，
  通过之后 MIR 一个字节都不变。**所以借用检查是零运行时开销的**（第 03 章说的"零开销"就是这个意思）

---

## 2. 源码地图

代码在 [`compiler/rustc_borrowck/`](https://github.com/rust-lang/rust/tree/master/compiler/rustc_borrowck/src)。
主要模块（**2026-08 核实**）：

| 模块 | 职责 | 你什么时候会想读它 |
|---|---|---|
| `lib.rs` | 入口 `mir_borrowck` query；`MirBorrowckCtxt` 主循环 | 想知道整体流程 |
| `nll.rs` | NLL 检查的驱动：建约束、求解、报错 | 想知道 dump 是在哪里打的 |
| `type_check/` | **MIR 类型检查**——顺便产出所有 region 约束 | 想知道约束从哪来 |
| `region_infer/` | `RegionInferenceContext`：NLL 的约束求解（不动点迭代）。Polonius 阶段二仍复用它 | 想知道 region 点集怎么算的 |
| `dataflow.rs` | 三个数据流分析的组合 | ★ 最值得读的一个文件 |
| `borrow_set.rs` | `BorrowSet`：所有贷款的集合，`bw0`/`bw1` 的编号在这里分配 | 想理解 `Borrows` 段 |
| `places_conflict.rs` | ★ **判定两个 place 是否冲突** | 想知道 `s.a` 和 `s.b` 为什么不冲突 |
| `prefixes.rs` | place 的前缀遍历（`s.a.b` → `s.a` → `s`） | 同上 |
| `universal_regions.rs` | 从函数签名里提取"外部给定的" region | 想理解 `'?0/'?1/'?2` 那些 |
| `diagnostics/` | 所有错误信息的生成 | ★ 想知道某条报错的确切触发条件 |
| `polonius/` | ★ **当前默认引擎**：约束局部化 + 贷款可达性；子模块 `constraints` / `liveness_constraints` / `dump` / `legacy` | 第 07/15/16 章 |
| `consumers/` | **对外 API**，给 clippy / rust-analyzer / MIRAI 这类工具用 | 想自己写分析工具 |

> **一个高效的查法**：你拿到一个错误信息，比如
> `"cannot borrow X as mutable because it is also borrowed as immutable"`，
> 直接去 [`compiler/rustc_borrowck/messages.ftl`](https://github.com/rust-lang/rust/blob/master/compiler/rustc_borrowck/messages.ftl)
> 或 `diagnostics/` 里全文搜这句话，就能找到发出它的那段代码，
> 从而知道**触发条件的精确定义**。这比读文档快得多。

---

## 3. 三个数据流分析

`dataflow.rs` 里的 `Borrowck` 结构组合了三个子分析。**理解这三个，就理解了 borrowck 的全部输入。**

### 3.1 `Borrows`：哪些贷款在这个点"在作用域内"

**gen/kill 分析**（正向）：

| 事件 | 效果 |
|---|---|
| 执行 `_4 = &(*_1)` | **gen**：把贷款 `bw0` 加入集合 |
| 到达一个点 `P ∉ region(bw0)` | **kill**：把 `bw0` 移出集合 |
| 被借的 place 被赋新值（`_1 = ...`） | **kill**：贷款失效（"loan killed"） |

第 07 章那个 `loan_killed_at.facts` 文件就是这里产出的。

### 3.2 `MaybeUninitializedPlaces`（`uninits`）：哪些 place 可能未初始化

这是**移动分析**，回答 E0382（use of moved value）：

```rust
let s = String::from("x");
let t = s;              // s 变成"可能未初始化"
println!("{}", s);      // ❌ 读一个可能未初始化的 place
```

**它也负责部分移动**（第 04 章）——因为它按 place 而非变量追踪。
`MoveData` 结构记录了所有的 move path（`mp0`、`mp1`… 就是它，
第 07 章的 `path_is_var.facts` 里能看到）。

### 3.3 `EverInitializedPlaces`（`ever_inits`）：哪些 place 曾经被初始化过

用于判断"能否给一个 place 赋值"——特别是 `let x;` 后面延迟初始化的情况，
以及**是否需要在赋值前 drop 旧值**。

```rust
let x;
if cond { x = 1; }
println!("{}", x);      // ❌ E0381: used binding `x` isn't initialized
```

### 3.4 三者的分工

```
                      问题                          分析
   "这个借用还活着吗？"                    ──►  Borrows
   "这个值被移走了吗？"                    ──►  MaybeUninitializedPlaces
   "这个变量初始化了吗？赋值要不要先 drop？"  ──►  EverInitializedPlaces
```

**E0382（moved）和 E0502（borrow conflict）是两个不同分析报出来的**——
这就是为什么第 05 章说"看错误码就知道是移动还是重借用"。

---

## 4. `places_conflict`：两个 place 什么时候算冲突

这是第 05 章第 1.1 节那条规则的源码实现，值得单独讲。

**核心算法**（简化）：

```
conflict(borrowed_place, access_place):
    1. 逐层比较两个 place 的投影路径（projection）
    2. 如果在某一层上「确定不同」（比如 .a vs .b，或常量下标 [0] vs [1] 且是数组）
       → 不冲突
    3. 如果一个是另一个的前缀
       → 冲突（访问父级会影响子级，反之亦然）
    4. 遇到 Deref
       → ★ 看被解引用的引用类型：
          - 解引用 &T（共享）：如果访问是「只读」，不冲突
          - 解引用 &mut T：冲突（因为不知道指向哪）
          - 解引用裸指针：借用检查器直接放弃（那是 unsafe 的责任）
    5. 其他情况保守地认为冲突
```

**这解释了几个高频现象**：

| 现象 | 出自哪一步 |
|---|---|
| `s.a` 和 `s.b` 不冲突 | 第 2 步：字段名不同，确定不相交 |
| `t.0` 和 `t.1` 不冲突 | 第 2 步：元组字段同理 |
| `s` 和 `s.a` 冲突 | 第 3 步：前缀 |
| `v[0]` 和 `v[1]` 冲突（`Vec`） | `v[i]` 脱糖成 `*index_mut(&mut v, i)`，冲突发生在**整个 `v`** 上 |
| `a[0]` 和 `a[1]` 冲突（**固定长度数组也冲突！**） | 第 5 步：下标是运行时值，编译器保守处理 |
| 两个 `&mut` 指向的东西被认为可能相同 | 第 4 步：编译器不做指针别名分析 |

### 4.1 实测：哪些"分割"能过，哪些不能

很多资料（包括早期的 Rust 书）说"数组用常量下标可以分割借用"。**这是错的**，
下面是实测（`rustc 1.96.0`, edition 2024）：

```rust
struct S { a: i32, b: i32 }

pub fn p1() { let mut a=[1,2,3]; let [x,y,_] = &mut a; *x += *y; }                 // ✅
pub fn p2() { let mut a=[1,2,3]; let (l,r) = a.split_at_mut(1); l[0] += r[0]; }    // ✅
pub fn p3() { let mut t=(1,2);   let (x,y) = (&mut t.0, &mut t.1); *x += *y; }     // ✅
pub fn p4() { let mut a=[1,2,3]; let x=&mut a[0]; let y=&mut a[1]; *x += *y; }     // ❌ E0499
pub fn p5() { let mut v=vec![1,2,3];
              let [x,y] = v.get_disjoint_mut([0,1]).unwrap(); *x += *y; }          // ✅
pub fn p6() { let mut s=S{a:1,b:2}; let x=&mut s.a; let y=&mut s.b; *x += *y; }    // ✅
```

**只有 `p4` 失败**，报错是：

```
error[E0499]: cannot borrow `a[_]` as mutable more than once at a time
```

★ 注意报错里的 **`a[_]`**——下标被打成了 `_`。
这就是证据：**编译器根本没有记录下标是常量 0 还是 1，它把所有下标都视为"某个未知位置"。**

对比 `Vec` 版本的报错是 `cannot borrow \`v\``——连 `[_]` 都没有，
因为它冲突在整个 `v` 上（`IndexMut` 的 `&mut self`）。**两种失败的机制不同，但都失败。**

> ### 结论：分割借用只有两条合法途径
> 1. **模式解构 / 字段访问**——编译器在语法上就能看出不相交（`p1`/`p3`/`p6`）
> 2. **签名里声明了分割的 API**——`split_at_mut`、`get_disjoint_mut`、`iter_mut`、
>    `split_first_mut`、`chunks_mut`（`p2`/`p5`）
>
> **下标永远不行**，不管容器是数组、slice 还是 `Vec`，不管下标是不是常量。
> 记住这一条能省掉很多试错。

## 5. universal region 与 `Free Region Mapping`

第 07 章的 dump 里有这么一段：

```
| Free Region Mapping
| '?0 | Global | ['?0, '?2, '?1]
| '?1 | Local  | ['?2, '?1]
| '?2 | Local  | ['?2]
```

**universal region**（也叫 free region / placeholder region）是**函数签名里的生命周期**——
它们的值不由函数体决定，而是调用方给的。

对 `fn example(v: &mut Vec<i32>) -> i32`：
- `'?0` = `'static`（永远存在，是所有 region 的超集）
- `'?1` = 函数体本身的 region（`'fn`）
- `'?2` = `v` 参数上那个匿名生命周期

`Free Region Mapping` 表示的是它们之间的 **outlives 关系**：
`'?0` 的列表里有 `'?1` 和 `'?2`，表示 `'?0: '?1` 且 `'?0: '?2`（`'static` 长于一切）。

**为什么 `Inferred Region Values` 里 `'?0` 的集合里会出现 `'?1`、`'?2` 这种东西？**

因为 region 的值实际上是**两部分的并集**：

```
region 的值 = { CFG 上的程序点 }  ∪  { 它包含的 universal region }
```

第二部分表示"这个 region 延伸到函数外面去了"。这是 NLL 处理跨函数边界的方式——
它没法枚举调用方的程序点，就用 universal region 的符号来代表。

> **实用推论**：当你看到一个 region 的值里含有 universal region（如 `'?1`），
> 说明**这个借用要活到函数返回之后**。这通常是 problem case #3 那类错误的根源
> （第 07 章第 7 节）。

---

## 6. 调试工具箱

### 6.1 MIR 相关

```bash
# 人类可读的 MIR
rustc +nightly -Zunpretty=mir foo.rs

# 更详细（含 scope 信息）
rustc +nightly -Zunpretty=mir-cfg foo.rs > mir.dot && dot -Tpng mir.dot -o mir.png

# dump 特定 pass 的 MIR（nll = 借用检查阶段）
rustc +nightly -Zdump-mir=nll -Zdump-mir-dir=out foo.rs

# dump 所有 pass（会产生很多文件）
rustc +nightly -Zdump-mir=all -Zdump-mir-dir=out foo.rs

# 只 dump 某个函数
rustc +nightly -Zdump-mir='example' -Zdump-mir-dir=out foo.rs
```

**`-Zdump-mir=nll` 会产出三个文件**：

| 文件 | 内容 |
|---|---|
| `*.nll.0.mir` | region 推断结果 + 带标注的 MIR ★ 最有用 |
| `*.nll.0.regioncx.all.dot` | 完整的 region 约束图 |
| `*.nll.0.regioncx.scc.dot` | 强连通分量缩点后的约束图（更易读） |

```bash
dot -Tpng out/*regioncx.scc.dot -o scc.png
```

### 6.2 Polonius 事实导出

```bash
rustc +nightly -Znll-facts -Znll-facts-dir=facts foo.rs
ls facts/*/
```

产出的 `.facts` 文件就是 Polonius 的**输入关系**（第 15 章会逐个讲）：

```
cfg_edge.facts              控制流图的边
loan_issued_at.facts        贷款在哪个点产生，属于哪个 origin
loan_invalidated_at.facts   贷款在哪个点被"破坏"（有冲突访问）
loan_killed_at.facts        贷款在哪个点失效
subset_base.facts           origin 之间的子集关系
placeholder.facts           universal region 对应的占位贷款
var_used_at.facts           变量在哪些点被使用
path_moved_at_base.facts    move path 在哪里被移走
universal_region.facts      哪些 origin 是 universal 的
```

**实测样例**（第 07 章那段代码）：

```
$ cat facts/*/loan_issued_at.facts
"'?3"	"bw0"	"Mid(bb0[3])"
"'?5"	"bw1"	"Mid(bb1[8])"

$ cat facts/*/loan_invalidated_at.facts
"Start(bb0[3])"	"bw1"
"Start(bb1[8])"	"bw0"
"Start(bb1[8])"	"bw1"
"Start(bb1[9])"	"bw0"
```

> 注意点的表示变成了 `Start(bbN[i])` / `Mid(bbN[i])`——
> **Polonius 把每条语句拆成两个点**（执行前 / 执行中）。
> 这个细化是它能做到更高精度的技术前提之一，第 15 章详解。

### 6.3 编译器日志

```bash
# 看 region 推断的详细过程（输出非常多，配合 grep）
RUSTC_LOG=rustc_borrowck::region_infer=debug rustc +nightly foo.rs 2>&1 | head -100

# 看数据流分析
RUSTC_LOG=rustc_borrowck::dataflow=debug rustc +nightly foo.rs 2>&1 | head -50

# 看某个具体错误是哪里报的（配合 -Ztreat-err-as-bug 拿到 backtrace）
RUST_BACKTRACE=1 rustc +nightly -Ztreat-err-as-bug=1 foo.rs
```

**`-Ztreat-err-as-bug=1` 是个神器**：它让第一个错误直接 panic，
于是你拿到一个**完整的调用栈**，能精确看到这个错误是从 `diagnostics/` 的哪个函数发出来的。

### 6.4 `consumers` API：自己写分析工具

```rust
// 需要 #![feature(rustc_private)]
use rustc_borrowck::consumers::{get_body_with_borrowck_facts, ConsumerOptions};

let facts = get_body_with_borrowck_facts(tcx, def_id, ConsumerOptions::PoloniusInputFacts);
// facts.body            —— MIR
// facts.borrow_set      —— 所有贷款
// facts.region_inference_context  —— region 推断结果
// facts.input_facts     —— Polonius 输入事实
```

这是 [Flowistry](https://github.com/willcrichton/flowistry)、
[Aquascope](https://github.com/cognitive-engineering-lab/aquascope)（一个可视化教学工具，
值得一看）、以及各种形式化验证工具用的接口。

> **推荐**：如果本章的推演过程你觉得抽象，去玩一下 **Aquascope** 的在线演示——
> 它把每一个点上的"谁拥有什么、谁借了什么"画成了图。

---

## 7. 一个完整的排查演练

**场景**：你写了下面这段代码，报了一个你看不懂的错。

```rust
struct Graph { nodes: Vec<Node>, edges: Vec<Edge> }
struct Node { id: usize }
struct Edge { from: usize, to: usize }

impl Graph {
    fn node(&self, i: usize) -> &Node { &self.nodes[i] }
    fn add_edge(&mut self, from: &Node, to: &Node) {
        self.edges.push(Edge { from: from.id, to: to.id });
    }

    fn connect_first_two(&mut self) {
        let a = self.node(0);
        let b = self.node(1);
        self.add_edge(a, b);            // ❌ ?
    }
}
```

> ### ★ 先注意一个陷阱：把参数换成 `usize` 就编译过了
> ```rust
> fn add_edge(&mut self, from: usize, to: usize) { /* ... */ }
> // ...
> self.add_edge(a.id, b.id);           // ✅ 能过！
> ```
> **原因是两阶段借用**（第 05 章 §3）：`&mut self` 先"预留"，然后求值参数，最后才"激活"。
> `a.id` 是在预留期间读的，读一个 `usize` 就把 `a` 的借用用完了，激活时已经没有冲突。
>
> 换成 `&Node` 之后，`a` 要**活着进入调用**——它在激活点仍然存活，这才撞上。
> **这两行的差别就是本章要教的排查方法：错误不在"借了什么"，在"借用活到哪里"。**

**第 1 步：读错误的三个 span**（实测输出）

```
error[E0502]: cannot borrow `*self` as mutable because it is also borrowed as immutable
  --> g.rs:13:9
   |
11 |         let a = self.node(0);
   |                 ---- immutable borrow occurs here      ← 谁先借的
12 |         let b = self.node(1);
13 |         self.add_edge(a, b);
   |         ^^^^^--------^^^^^^
   |         |    |
   |         |    immutable borrow later used by call       ← ★ 谁把 region 撑大了
   |         mutable borrow occurs here                     ← 冲突点
```

**第 2 步：手工展开省略的生命周期**（第 06 章技巧）

```rust
fn node<'s>(&'s self, i: usize) -> &'s Node                    // 规则 3：绑到 self
fn add_edge<'s, 'n>(&'s mut self, from: &'n Node, to: &'n Node)
```

→ `a: &'s Node`，`'s` 是 `&self` 的 region。`a` 本身在最后一行被当参数传进去，
所以 `'s` 必须包含最后一行 → `&self` 的借用还活着 → 和 `&mut self` 冲突。

**第 3 步：dump 验证**

```bash
rustc +nightly -Zdump-mir=nll -Zdump-mir-dir=out --crate-type=lib g.rs
grep -A20 "Inferred Region" out/*connect_first_two*nll.0.mir
```

**第 4 步：判断类别**（第 03 章的流程图）

> 问：运行时真的有别名冲突吗？
> 答：**没有**。`a.id` 只是读了一个 `usize`，`add_edge` 只往 `edges` 里 push。
>
> 问：这个"不相交"能从签名推出来吗？
> 答：**不能**。`node(&self)` 借的是整个 `self`，签名里没有"我只碰 nodes"。

→ **签名表达力不足**。四种解法：

```rust
// 解法 1（最简单）：改成传值，让借用在参数求值期就结束（配合两阶段借用）
fn add_edge_by_id(&mut self, from: usize, to: usize) { self.edges.push(Edge{from,to}) }
fn connect_first_two(&mut self) {
    self.add_edge_by_id(self.node(0).id, self.node(1).id);   // usize 是 Copy
}

// 解法 2：直接访问字段，避开方法
fn connect_first_two(&mut self) {
    let a = &self.nodes[0];
    let b = &self.nodes[1];
    let (x, y) = (a.id, b.id);
    self.edges.push(Edge { from: x, to: y });    // 直接操作字段，place 不相交
}

// 解法 3：把 edges 拆成独立参数（自由函数）
fn add_edge_to(edges: &mut Vec<Edge>, from: usize, to: usize) { edges.push(Edge{from,to}) }

// 解法 4（第 17 章的未来）：view types
// fn node(&{nodes} self, i: usize) -> &Node      ← 还不存在的语法
```

**这四种解法覆盖了第 18 章"解法总表"里的四大类**，你会反复用到。

---

## 8. 动手实验

### 实验 1：分割借用的六种写法

把第 4.1 节的 `p1`..`p6` 全部编译一遍，确认只有 `p4` 失败。
然后**对比三种报错文本**：

```bash
rustc --edition 2024 --crate-type=lib --emit=metadata --out-dir out arr.rs
```

```rust
pub fn f1() { let mut a=[1,2,3];      let x=&mut a[0]; let y=&mut a[1]; *x += *y; }
pub fn f2() { let mut v=vec![1,2,3];  let x=&mut v[0]; let y=&mut v[1]; *x += *y; }
pub fn f3() { let mut a=[1,2,3]; let s=&mut a[..]; let x=&mut s[0]; let y=&mut s[1]; *x += *y; }
```

**实测报错**：
```
f1: cannot borrow `a[_]` as mutable more than once   ← 数组：place 是 a[_]，下标被抹掉
f2: cannot borrow `v` as mutable more than once      ← Vec：place 是整个 v（走 IndexMut）
f3: cannot borrow `s[_]` as mutable more than once   ← slice：同数组
```

然后 dump `f1` 和 `f2` 的 MIR，找出 `a[0]` 和 `v[0]` 脱糖后的差别
（一个是 `_x = &mut a[const 0]`，另一个是 `index_mut(&mut v, 0)` 的函数调用）。

### 实验 2：全套 dump 流程

拿第 7 节的 `Graph` 例子，走完整流程：
1. `-Zunpretty=mir` 看 MIR
2. `-Zdump-mir=nll` 看 region
3. `-Znll-facts` 看 Polonius 事实
4. `dot -Tpng *scc.dot` 看约束图
5. 用第 6.3 节的 `-Ztreat-err-as-bug=1` 拿到报错的调用栈

### 实验 3：找到一条错误信息的源码

去 [rustc_borrowck/messages.ftl](https://github.com/rust-lang/rust/blob/master/compiler/rustc_borrowck/messages.ftl)
搜 `cannot borrow`，找到 E0502 对应的模板，然后在 `diagnostics/` 目录里搜它的 key，
读那段代码，回答：**在什么精确条件下会选择 E0502 而不是 E0499？**

<details><summary>提示</summary>

E0499 = 两个都是 `&mut`（"more than once at a time"）
E0502 = 一个 `&mut` 一个 `&`（"as mutable because it is also borrowed as immutable"，或反过来）
E0503 = 直接使用一个被可变借用了的 place（"cannot use X because it was mutably borrowed"）
E0505 = 移动一个被借用的值（"cannot move out of X because it is borrowed"）
E0506 = 给一个被借用的 place 赋值（"cannot assign to X because it is borrowed"）

**这五个错误码的区别是"访问的类型"×"已有贷款的类型"的组合表**，附录 A 有完整版。

</details>

---

## 9. 本章检查清单

- [ ] 知道借用检查在流水线里的位置，以及"通过之后 MIR 不变"（零开销）
- [ ] 能说出 `rustc_borrowck` 的六个核心模块及职责
- [ ] 能说出三个数据流分析各自回答什么问题
- [ ] 知道 E0382 和 E0502 来自**不同**的分析
- [ ] 知道 `places_conflict` 的判定步骤，能解释数组 vs `Vec` 的差别
- [ ] 知道 universal region 是什么，以及为什么它会出现在 region 的"值"里
- [ ] 会用 `-Zunpretty=mir` / `-Zdump-mir=nll` / `-Znll-facts` / `RUSTC_LOG` / `-Ztreat-err-as-bug`
- [ ] 能走完第 7 节的四步排查流程

---

## 10. 常见坑

| 现象 | 解释 |
|---|---|
| dump 文件找不到 | `-Zdump-mir-dir` 目录要先 `mkdir`；且函数名要匹配（`-Zdump-mir=all` 最保险） |
| 借用检查失败时没有 nll dump | 有的，dump 在报错**之前**产出。检查目录 |
| MIR 里的变量编号和源码对不上 | 看 `debug x => _N;` 这些行，它们是映射表 |
| `-Znll-facts` 输出为空 | 某些简单函数确实没有贷款；换个有借用的例子 |
| 想改 rustc 试试 | `./x.py build` 一次要 30 分钟起。先用 `consumers` API 写外部工具 |
| 以为借用检查影响性能 | 不影响生成的代码。它是纯验证 pass，通过后 MIR 不变。（Polonius 会增加**编译时间**：官方在 top-10000 crate 上测得少数场景 2–3× 的借用检查耗时回归，见第 16 章） |
| 以为 `-Zpolonius=off` 会"关掉借用检查" | 只是退回上一代的 NLL 算法。检查照做，只是精度低一些 |
| 报错位置在宏展开里 | 用 `cargo expand` 先展开宏再看 |

---

**阶段 1 的"编译器视角"到此结束。** 第 09/10 章补上类型系统里和借用交织的两块：型变和 HRTB。

下一章：[09 - 型变（variance）](09-variance.md)
