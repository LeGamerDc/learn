# 07 - 借用检查的计算模型：贷款、origin 与可达性

> 本章目标：把第 06 章的概念变成**可以手算的算法**。
> 我们讲的是**当前的模型（Polonius）**：借用检查 = **在一张 (region, point) 图上做可达性搜索**。
> 上一代的 NLL 模型放在第 9 节作为历史对照——你需要认识它，因为 stable 工具链
> 在 Polonius 稳定化之前仍然跑它，而且网上 90% 的资料讲的是它。
> 预计用时：3.5 小时（必须动手）。

> ### ⚠️ 本章的版本前提
> - **nightly（2026-08-04 起）**：Polonius Alpha **默认开启**。本章正文讲的是它。
> - **stable 1.96/1.97**：仍是 NLL。目标是 **2026 年底前**稳定化 Polonius Alpha。
> - 所有实验用 `rustc +nightly`。加 `-Zpolonius=off` 可以随时退回 NLL 做对照。

---

## 1. 借用检查的流水线

```
   源码
    │  解析 + 类型检查
    ▼
   HIR ──► THIR ──► MIR（控制流图形式的中间表示）
                     │
                     │  ① MIR type check：给每个引用类型分配 region 变量，
                     │     并收集所有 outlives 约束
                     ▼
              ┌─────────────────────────────────────────┐
              │ ② liveness 分析                          │
              │    每个变量 / 每个 region 在哪些点上还有用  │
              └────────────────┬────────────────────────┘
                               ▼
              ┌─────────────────────────────────────────┐
              │ ③ ★ 贷款传播（Polonius 的核心）           │
              │    把约束"局部化"成 (region, point) 图，   │
              │    从每个贷款的产生点做可达性搜索，          │
              │    得出「哪些贷款在哪些点上活着」            │
              └────────────────┬────────────────────────┘
                               ▼
              ┌─────────────────────────────────────────┐
              │ ④ 冲突检测                                │
              │    每次访问，检查有没有活跃且冲突的贷款      │
              └────────────────┬────────────────────────┘
                               ▼
                         E0499/E0502/...
```

**关键事实**：借用检查发生在**类型检查之后、优化之前**，且**通过之后 MIR 一个字节都不变**。
借用检查是纯验证 pass——**这就是"零成本"的确切含义**。

---

## 2. MIR：一切分析的舞台

### 2.1 先看一眼

```rust
pub fn example(v: &mut Vec<i32>) -> i32 {
    let first = &v[0];
    v.push(4);
    *first
}
```

```bash
rustc +nightly --edition 2024 --crate-type=lib -Zunpretty=mir bad.rs
```

**真实输出**（删掉注释，本课程实测）：

```
fn example(_1: &mut Vec<i32>) -> i32 {
    let mut _0: i32;                      // 返回值
    let _2: &i32;                         // first
    let _3: &i32;                         // index() 的返回值
    let mut _4: &Vec<i32>;                // 传给 index 的 &v
    let _5: ();                           // push 的返回值
    let mut _6: &mut Vec<i32>;            // 传给 push 的 &mut v

    bb0: {
        StorageLive(_2);                                    // bb0[0]
        StorageLive(_3);                                    // bb0[1]
        StorageLive(_4);                                    // bb0[2]
        _4 = &(*_1);                                        // bb0[3]  ★ 贷款 bw0 在这里产生
        _3 = <Vec<i32> as Index<usize>>::index(move _4, const 0_usize)
             -> [return: bb1, unwind: bb3];                 // bb0[4]  （终结符）
    }

    bb1: {
        StorageDead(_4);                                    // bb1[0]
        _2 = &(*_3);                                        // bb1[1]
        FakeRead(ForLet(None), _2);                         // bb1[2]
        StorageLive(_5);                                    // bb1[3]
        StorageLive(_6);                                    // bb1[4]
        _6 = &mut (*_1);                                    // bb1[5]  ★ 贷款 bw1 在这里产生
        _5 = Vec::<i32>::push(move _6, const 4_i32)
             -> [return: bb2, unwind: bb3];                 // bb1[6]
    }

    bb2: {
        StorageDead(_6);                                    // bb2[0]
        StorageDead(_5);                                    // bb2[1]
        _0 = copy (*_2);                                    // bb2[2]  ★ first 的最后一次使用
        StorageDead(_3);                                    // bb2[3]
        StorageDead(_2);                                    // bb2[4]
        return;                                             // bb2[5]
    }

    bb3 (cleanup): { resume; }
}
```

### 2.2 需要认识的 MIR 元素

| 元素 | 含义 |
|---|---|
| `_0`, `_1`, `_2`… | **局部变量（local）**。`_0` 永远是返回值，`_1.._n` 是参数 |
| `bbN` | **基本块**：一串顺序语句 + 一个终结符 |
| `bbN[i]` | **位置（location）**：第 N 块第 i 条语句 |
| `Start(bbN[i])` / `Mid(bbN[i])` | ★ **程序点（point）**。Polonius 把每条语句拆成两个点：执行**前**和执行**中** |
| `StorageLive/Dead` | 栈空间生命期标记（不是 drop） |
| `_4 = &(*_1)` | 一次**借用**，产生一笔**贷款（loan）** |
| `-> [return: bb1, unwind: bb3]` | 终结符：正常路径 / panic 展开路径 |
| `FakeRead` | 编译器插入的假读，让 `let`/`match` 的借用检查符合直觉 |
| `move _4` / `copy (*_2)` | 显式区分移动和复制 |

> ### ★ `Start` / `Mid` 是 Polonius 的技术前提之一
> NLL 里一条语句就是一个点。Polonius 把它拆成两个：
> - **`Start(P)`**：语句 P **执行之前**
> - **`Mid(P)`**：语句 P **执行之中**（效果已经发生）
>
> 为什么需要？因为 `_4 = &(*_1)` 这条语句里，"贷款产生"和"贷款可用"是两个时刻。
> 这个半步的精度差，正是"条件借用"能被正确处理的原因之一。

### 2.3 CFG

```
        bb0
         │  index() 正常返回
         ▼
        bb1 ──unwind──┐
         │            │
         │ push() 返回 │
         ▼            ▼
        bb2          bb3 (cleanup)
         │            │
      return        resume
```

**注意 unwind 边**：因为 `index()` 可能 panic，CFG 上有一条通往清理块的边。
**借用检查必须考虑这条边**——偶尔会导致"看起来不可能到达的地方也算冲突"。

---

## 3. 核心概念：loan 与 origin

这是 Polonius 模型的两个基本对象。**请把它们和第 06 章的"region 是点集"区分开**——
那是上一代的说法。

### 3.1 loan（贷款）

> **每一次 `&` 或 `&mut` 操作，产生一笔贷款。**

贷款记录三件事：**在哪个点产生**、**借了哪个 place**、**是共享还是独占**。

编译器给它们编号 `bw0`、`bw1`、…（`bw` = borrow）。

```
bw0: 在 Mid(bb0[3]) 产生，借了 place `*_1`，共享
bw1: 在 Mid(bb1[5]) 产生，借了 place `*_1`，独占
```

### 3.2 origin（起源）

> **`'a` 不再是"一段有效区间"，而是"这个引用可能来自哪些贷款"的集合。**

```rust
let r = if cond { &a } else { &b };
// r 的类型是 &'x i32
// 'x 这个 origin = { 借 a 的那笔贷款, 借 b 的那笔贷款 }
```

**这是第 06 章那次认知翻转的"第二级"**：

| 时代 | `'a` 是什么 | 回答的问题 |
|---|---|---|
| 1.0（词法） | 一个**词法作用域** | 这个借用管到哪个 `}` |
| NLL（2018） | CFG 上的**一组程序点** | 这个引用**在哪些点有效** |
| **Polonius（现在）** | 一组**贷款** | 这个引用**可能指向谁借来的东西** |

> **为什么这个转变提高了精度？**
>
> 点集模型只能说"这个 region 覆盖了 `None` 分支"，于是 `None` 分支里的所有操作都受限。
> 贷款模型可以说"在 `None` 分支的这个点上，`bw0` 这笔贷款**已经死了**"——
> 因为从这个点出发，永远到不了任何使用 `bw0` 的地方。
>
> **精度的来源：把"区域有多大"换成"每一笔贷款在每一个点上是死是活"。**

编译器给 origin 编号 `'?0`、`'?1`、…（和 NLL 共用编号空间）。

---

## 4. Polonius 的算法：图上的可达性

rustc 里 Polonius Alpha 的实现思路（`rustc_borrowck::polonius` 模块的原话是
"models flow-sensitive borrow-checking concerns as a graph containing both region and
control flow information"）：

### 4.1 建图

**节点** = `(origin, point)` 二元组。也就是说，同一个 origin 在不同程序点上是**不同的节点**。

```
('?3, Mid(bb0[3]))   ('?3, Start(bb0[4]))   ('?3, Mid(bb0[4]))  ...
('?5, Mid(bb1[5]))   ('?5, Start(bb1[6]))   ...
```

**边**来自两个地方：

| 边的来源 | 形状 | 含义 |
|---|---|---|
| **类型检查约束**（localized） | `('a, P) → ('b, P)` | 在**同一个点** P 上，贷款可以从 origin `'a` 流到 `'b`（因为存在 `'a: 'b` 的 outlives 约束） |
| **活跃性约束** | `('a, P) → ('a, Q)` | `Q` 是 `P` 的后继，且 `'a` 在两处都活着 → 贷款可以**沿 CFG 往后流** |

★ **有些边是双向的**：当型变关系是**不变**（第 09 章）时，
约束是 `'a: 'b` **且** `'b: 'a`，于是加两条边。这意味着
**贷款可以"逆着时间"往回流**——这是 rustc 文档里明确写的
("loans can flow back in time through bidirectional edges")。

### 4.2 传播

> **一笔贷款 `L` 在点 `P` 活着 ⟺ 从 `L` 的产生节点出发，能在图上到达某个 `(_, P)` 节点。**

搜索过程中要尊重 **kill**：

| kill 的来源 | 例子 |
|---|---|
| 被借的 place 被重新赋值 | `let r = &x; x = 5;` → `r` 的贷款在 `x = 5` 处被 kill |
| origin 在某个点不再活跃 | 引用之后再没被用过 |
| 被借的 place 被移走 | — |

### 4.3 检查

第一步算出"活跃贷款"之后，**再跑一遍常规的 NLL 数据流**得到"在作用域内的贷款（active loans）"，
然后逐个访问点检查：

```
在点 P 对 place X 做访问 A（读 / 写 / 独占借用 / 共享借用 / 移动 / 丢弃）
    ↓
遍历所有在 P 处活跃的贷款 L
    ↓
若 L 借的 place 与 X 冲突（places_conflict，见第 08 章）
   且 (L 的种类, A) 的组合违反 Aliasing XOR Mutability
    ↓
报错
```

---

## 5. 实测：把算法的输入全部 dump 出来

```bash
mkdir -p /tmp/mirlab && cd /tmp/mirlab
cat > bad.rs <<'RSEOF'
pub fn example(v: &mut Vec<i32>) -> i32 {
    let first = &v[0];
    v.push(4);
    *first
}
RSEOF
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata \
      -Znll-facts -Znll-facts-dir=facts bad.rs
ls facts/*/
```

**真实输出**（本课程实测，`rustc 1.100.0-nightly (8fa1c96cf 2026-08-17)`）：

```
$ cat facts/*/loan_issued_at.facts
"'?3"	"bw0"	"Mid(bb0[3])"        ← 贷款 bw0 在 Mid(bb0[3]) 产生，属于 origin '?3
"'?5"	"bw1"	"Mid(bb1[8])"        ← 贷款 bw1 在 Mid(bb1[8]) 产生，属于 origin '?5

$ cat facts/*/loan_invalidated_at.facts
"Start(bb0[3])"	"bw1"
"Start(bb1[8])"	"bw0"                ← ★ bw0 在 Start(bb1[8]) 被"破坏"了
"Start(bb1[8])"	"bw1"
"Start(bb1[9])"	"bw0"

$ cat facts/*/subset_base.facts
"'?6"	"'?3"	"Mid(bb0[3])"        ← 在 Mid(bb0[3]) 处，'?6 ⊆ '?3
"'?3"	"'?9"	"Mid(bb0[3])"
"'?11"	"'?8"	"Mid(bb0[4])"
"'?9"	"'?11"	"Mid(bb0[4])"

$ cat facts/*/cfg_edge.facts | head -4
"Start(bb0[0])"	"Mid(bb0[0])"
"Mid(bb0[0])"	"Start(bb0[1])"
"Start(bb0[1])"	"Mid(bb0[1])"
"Mid(bb0[1])"	"Start(bb0[2])"
```

### 5.1 完整的输入关系表

`-Znll-facts` 会产出 18 个文件，它们**就是 Polonius 的全部输入**：

| 文件 | 关系 | 含义 |
|---|---|---|
| `cfg_edge` | `cfg_edge(P, Q)` | CFG 上 P 的后继是 Q |
| `loan_issued_at` | `loan_issued_at(O, L, P)` | 贷款 L 在点 P 产生，进入 origin O |
| `loan_killed_at` | `loan_killed_at(L, P)` | 贷款 L 在点 P 失效（被借的 place 被覆盖） |
| `loan_invalidated_at` | `loan_invalidated_at(P, L)` | ★ 点 P 有一次访问会**破坏**贷款 L |
| `subset_base` | `subset_base(O1, O2, P)` | 在点 P，`O1 ⊆ O2` |
| `universal_region` | `universal_region(O)` | O 是函数签名给定的 origin |
| `placeholder` | `placeholder(O, L)` | universal region O 对应的"占位贷款" |
| `var_used_at` / `var_defined_at` / `var_dropped_at` | | 变量的使用 / 定义 / 丢弃点 |
| `use_of_var_derefs_origin` | `(V, O)` | 使用变量 V 会解引用 origin O |
| `drop_of_var_derefs_origin` | `(V, O)` | drop 变量 V 会解引用 origin O ← **dropck 靠这个** |
| `path_is_var` / `child_path` | | move path 的结构 |
| `path_assigned_at_base` / `path_accessed_at_base` / `path_moved_at_base` | | 移动分析的输入 |
| `known_placeholder_subset` | | 签名里显式写的 `'a: 'b` |

> **`loan_invalidated_at` 是理解错误信息的钥匙。**
> 它记录的是"这里有一次访问，如果那笔贷款还活着，就是错误"。
> 借用检查的最后一步就是：
>
> ```
> errors(L, P)  :-  loan_invalidated_at(P, L),  loan_live_at(L, P).
> ```
>
> 也就是：**被破坏 且 还活着 = 报错**。第 15 章会把完整的 datalog 规则写出来。

### 5.2 对照实验：改一行，看贷款的死活翻转

```rust
pub fn example(v: &mut Vec<i32>) -> i32 {
    let first = &v[0];
    let x = *first;        // ★ 提前把值拷出来
    v.push(4);
    x
}
```

现在 `bw0`（`first` 的贷款）在 `v.push(4)` 那个点上**已经死了**——
从那个点出发，图上到不了任何使用 `bw0` 的节点（`*first` 已经在前面执行完了）。

```
loan_invalidated_at(Start(bb1[8]), bw0)   ← push 仍然会"破坏"它
loan_live_at(bw0, Start(bb1[8]))          ← 但它已经不活了
    ↓
errors 规则的两个前提不同时成立  →  ✅ 编译通过
```

**这就是 NLL 和 Polonius 共有的核心洞察**（NLL 也能处理这个例子）。
差别在下一节。

---

## 6. Polonius 比 NLL 强在哪：条件借用

现在看 Polonius Alpha **真正带来的**东西。lab 里的 5 个 ★ 案例都是这一类。

```rust
// lab/08-conditional-reborrow.rs
pub fn f(a: &mut u8) -> &mut u8 {
    let b = &mut *a;
    if *b > 0 { b } else { a }
}
```

**实测**：`-Zpolonius=off` → `E0499`；默认（Polonius）→ ✅

**Polonius 的推理**：

```
bw0 = 贷款「b = &mut *a」，在 Mid(第2行) 产生
返回值的 origin 'ret = { bw0 }  ∪  { a 自己的占位贷款 }

在 else 分支的那个点上：
    从 bw0 的产生节点出发，能到达 else 分支吗？
        → then 分支返回 b（用了 bw0）
        → else 分支返回 a（没用 bw0）
    → 在 else 分支的点上，bw0 **不可达** → 不活跃
    ↓
    else 分支里使用 a（等价于访问 *a）不会和 bw0 冲突
    ↓
    ✅
```

**NLL 的推理**（第 9 节详解）：

```
'0 = bw0 的 region（一个点集）
返回值要求 '0 ⊇ 'ret，而 'ret 是 universal region
→ '0 被撑大到覆盖整个函数，包括 else 分支
→ else 分支里 `a` 的使用与 '0 冲突
→ ❌ E0499
```

> ### ★ 一句话总结两代的差别
>
> **NLL 问："这个 region 有多大？"** → region 是一个**扁平点集**，
> 一旦某条路径要求它很大，**所有**路径都被撑大 → 流不敏感。
>
> **Polonius 问："每一笔贷款在每一个点上是死是活？"** → 通过**图可达性**回答，
> 天然区分路径 → 流敏感。

---

## 7. Polonius Alpha **不能**做到的（边界）

必须说清楚，否则你会有错误预期。**实测**（lab 完整数据）：

| 形态 | NLL | Polonius Alpha | 为什么 Alpha 也不行 |
|---|---|---|---|
| 条件返回借用 | ❌ | ✅ | — |
| `HashMap` get-or-insert | ❌ | ✅ | — |
| lending iterator + 条件返回 | ❌ | ✅ | — |
| 循环里的条件返回 | ❌ | ✅ | — |
| **经方法访问不相交字段** | ❌ | ❌ | **签名表达力不足**，不是分析精度问题。需要 view types（第 17 章） |
| **自引用结构** | ❌ | ❌ | 需要"内部引用"这个全新的类型系统特性（第 17 章） |
| **`&mut v[0]` + `&mut v[1]`** | ❌ | ❌ | `IndexMut` 借走整个 `v`，签名里没有"不相交"的信息 |
| **返回局部变量引用** | ❌ | ❌ | 这是**真正的**悬垂，永远不该通过 |

> ### ★ 分清两类"编译器拒绝"
>
> **分析精度不足**（Polonius 在解决）：签名里有足够信息，但算法算不出来。
> **签名表达力不足**（Polonius 解决不了）：签名里根本没有那个信息。
>
> 后者需要**新的类型系统特性**（view types、place-based lifetimes），
> 那是第 17 章 "The Borrow Checker Within" 的内容，没有稳定化时间表。
>
> **判断法**：把函数内联展开成直接的字段访问，如果就能过 → 签名表达力问题。

**另外，Polonius Alpha 也不是完整的 Polonius**：
官方明确说明 Alpha 是"完整流敏感"的一个子集，且
**Alpha 稳定化之后不再继续 Polonius 的功能开发**。第 16 章有详细现状。

---

## 8. 手工推演一个完整例子

**题目**：判断下面这段在 Polonius 下能否通过。**先自己推，再验证。**

```rust
use std::collections::HashMap;
fn f<'r>(map: &'r mut HashMap<u32, String>, k: u32) -> &'r mut String {
    match map.get_mut(&k) {
        Some(v) => v,
        None => {
            map.insert(k, String::new());
            map.get_mut(&k).unwrap()
        }
    }
}
```

**推演**：

1. **贷款**
   - `bw0`：`map.get_mut(&k)` 的 `&mut *map`，在 `match` 的 scrutinee 求值处产生
   - `bw1`：`map.insert(...)` 的 `&mut *map`，在 `None` 分支产生
   - `bw2`：第二个 `map.get_mut(&k)` 的 `&mut *map`

2. **`bw0` 在 `None` 分支的 `map.insert` 那个点上活着吗？**
   - 问：从 `bw0` 的产生节点出发，沿图能到达 `None` 分支里 insert 那个点吗？
   - `bw0` 的使用点只有 `Some(v) => v`（把 `v` 返回出去）
   - 从 `Some` 分支出去之后就 return 了，**回不到 `None` 分支**
   - CFG 上：scrutinee → 判别 → 分两支，两支不互相到达
   - → **`bw0` 在 `None` 分支不可达 → 不活跃**

3. **`loan_invalidated_at(insert 处, bw0)`** 成立（insert 需要 `&mut *map`）
   但 **`loan_live_at(bw0, insert 处)`** 不成立
   → `errors` 规则的两个前提不同时满足 → **不报错**

4. `bw1`、`bw2` 同理，只在 `None` 分支内部，且不互相冲突

**结论：✅ 通过。**

**验证**：

```bash
cd lab
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out \
      cases/06-problem-case-3-match.rs                 # ✅ 无输出
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out \
      -Zpolonius=off cases/06-problem-case-3-match.rs  # ❌ E0499 ×2
```

---

## 9. 附录：上一代的 NLL 模型（历史参考）

**你为什么还需要认识它**：
1. stable 工具链在 Polonius 稳定化前仍然跑 NLL
2. 网上 90% 的资料、书籍、博客讲的是 NLL
3. `-Zdump-mir=nll` 的输出格式仍然是 NLL 的（region 点集）
4. Polonius Alpha 的第二阶段（"active loans"）仍然复用 NLL 的数据流

### 9.1 NLL 的模型

> **region `'a` = CFG 上的一组程序点。**

三类约束：

| 约束 | 规则 |
|---|---|
| **liveness** | 变量 `x: &'a T` 在点 P 活跃 ⟹ `P ∈ 'a` |
| **subtyping** | 赋值 `_a = _b`，`_b: &'x T`、`_a: &'y T` ⟹ `'y ⊆ 'x` |
| **CFG 传播** | region 从约束点沿 CFG 反向传播，直到不再 live |

**求解**：不动点迭代，得到满足所有约束的**最小点集**。

**检查**：在点 P 对 place X 访问时，若存在贷款 L 满足 `P ∈ region(L)` 且 place 冲突 → 报错。

### 9.2 实测 NLL 的输出

```bash
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata \
      -Zdump-mir=nll -Zdump-mir-dir=out -Zpolonius=off bad.rs
head -40 out/*nll.0.mir
```

**真实输出**：

```
| Inferred Region Values
| '?0 | U0 | {bb0[0..=4], bb1[0..=6], bb2[0..=5], bb3[0], '?0, '?1, '?2}
| '?3 | U0 | {bb0[3..=4], bb1[0..=6], bb2[0..=2]}          ← ★ bw0 的 region
| '?5 | U0 | {bb1[5..=6]}                                   ← ★ bw1 的 region
| Borrows
| bw0: issued at bb0[3] in '?3
| bw1: issued at bb1[5] in '?5
```

**读法**：`bw1` 在 `bb1[5]` 产生，而 `bb1[5] ∈ '?3`（`bw0` 的 region）→ 冲突 → E0502。

把代码改成 `let x = *first;` 提前拷贝之后：

```
| '?3 | U0 | {bb0[3..=4], bb1[0..=4]}      ← 缩小了
| bw1: issued at bb1[8] in '?5
```

`bb1[8] ∉ '?3` → 无冲突 → ✅。

### 9.3 NLL 为什么精度不够

**region 是一个扁平的点集，无法表达"这个借用只在某些路径上有效"。**

回到 problem case #3：

1. `Some(v) => v` 要把借用返回，返回值类型 `&'r mut V`
2. subtyping 约束：`'r ⊆ '?N`（`'?N` 是 `bw0` 的 region）
3. `'r` 是 universal region，**包含函数的所有点**
4. → `'?N` 被撑大到覆盖整个函数，**包括 `None` 分支**
5. → `None` 分支里的 `map.insert` 与 `bw0` 冲突 → E0499

**问题出在第 3→4 步**：一条路径的需求，污染了所有路径。

> **这就是"流不敏感"的确切含义**，也是 Polonius 用"每笔贷款独立做可达性"取代它的原因。

### 9.4 两代模型对照表

| | NLL（2018–） | Polonius Alpha（2026–） |
|---|---|---|
| `'a` 是什么 | 程序点的集合 | **贷款的集合（origin）** |
| 核心问题 | region 有多大 | **每笔贷款在每个点是死是活** |
| 算法 | 约束求解 + 不动点迭代 | **(origin, point) 图上的可达性搜索** |
| 程序点粒度 | `bbN[i]` | **`Start(bbN[i])` / `Mid(bbN[i])`** |
| 流敏感 | ❌ | ✅（对贷款传播而言） |
| 条件借用 | ❌ | ✅ |
| 字段粒度 | 整个 self | 整个 self（**没变**） |
| 稳定状态 | stable | nightly 默认，目标 2026 底稳定 |

---

## 10. 动手实验

### 实验 1：跑通全套 dump（Polonius 视角）

```bash
mkdir -p /tmp/mirlab && cd /tmp/mirlab
cat > bad.rs <<'RSEOF'
pub fn example(v: &mut Vec<i32>) -> i32 {
    let first = &v[0];
    v.push(4);
    *first
}
RSEOF

# 1) MIR
rustc +nightly --edition 2024 --crate-type=lib -Zunpretty=mir bad.rs

# 2) Polonius 的输入事实
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata \
      -Znll-facts -Znll-facts-dir=facts bad.rs
for f in facts/*/*.facts; do echo "### $(basename $f)"; cat "$f"; done

# 3) 上一代 NLL 的 region 点集（对照）
mkdir -p out
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out \
      -Zdump-mir=nll -Zdump-mir-dir=out -Zpolonius=off bad.rs
head -40 out/*nll.0.mir
```

**任务**：
1. 从 `loan_issued_at.facts` 找出所有贷款及其产生点
2. 从 `loan_invalidated_at.facts` 找出哪些点会破坏哪些贷款
3. 手工判断：每个 `(P, L)` 对里，`L` 在 `P` 处活着吗？
4. 用 `errors(L,P) :- loan_invalidated_at(P,L), loan_live_at(L,P)` 推出最终结论
5. 和编译器的实际报错对照

### 实验 2：亲手把贷款"弄死"

把 `bad.rs` 改成第 5.2 节的版本（提前拷贝），重跑，对比事实文件的差别。

再试这几个变体，每次预测结果再验证：

```rust
pub fn a(v: &mut Vec<i32>) -> i32 { let f = &v[0]; let x = *f; v.push(4); x }
pub fn b(v: &mut Vec<i32>) -> i32 { let x = { let f = &v[0]; *f }; v.push(4); x }
pub fn c(v: &mut Vec<i32>) -> i32 { let x = v[0]; v.push(4); x }
pub fn d(v: &mut Vec<i32>) -> i32 { let f = &v[0]; if v.len() > 5 { *f } else { v.push(4); 0 } }
```

**`d` 特别值得试**——它是条件借用的形态。预测 NLL 和 Polonius 分别怎么判。

### 实验 3：NLL vs Polonius 的完整差集

```bash
cd lab && ./run.sh
```

把所有 `★ Polonius 新增接受` 的案例挑出来，**对每一个手工推演一遍第 6 节的过程**：
"从这笔贷款的产生点出发，在哪些点上可达？"

---

## 11. 本章检查清单

- [ ] 能说出借用检查的四个阶段，且知道它**不改变生成的代码**
- [ ] 能读懂 MIR：`_N`、`bbN[i]`、`StorageLive/Dead`、终结符、`FakeRead`
- [ ] 知道 Polonius 的程序点是 **`Start(P)` / `Mid(P)`** 两个半步
- [ ] **能说出 loan 和 origin 的定义，且知道 `'a` 现在是"贷款的集合"**
- [ ] 能说出图的节点是 `(origin, point)`，边来自类型约束和活跃性约束
- [ ] **知道贷款活跃性 = 图上的可达性**
- [ ] 知道最终规则：`errors :- loan_invalidated_at ∧ loan_live_at`
- [ ] 会用 `-Znll-facts` dump 全部输入事实，并读懂主要的几个
- [ ] 能分清"分析精度不足"和"签名表达力不足"两类拒绝
- [ ] 知道上一代 NLL 的模型（region = 点集）及其流不敏感的根因

---

## 12. 常见坑

| 现象 | 解释 |
|---|---|
| stable 上编译不过，nightly 上过了 | 大概率就是这 5 类 Polonius 新增案例之一。用 `-Zpolonius=off` 确认 |
| 网上说"这段代码 Rust 编译不过" | 复核。很多结论写于 NLL 时代，2026-08 之后已经变了。用 `lab/run.sh` 实测 |
| 错误信息指向的位置很奇怪 | 检查在 MIR 上做，span 是反查回来的。看三个 span 的组合 |
| "我明明没用那个变量了" | 检查有没有 `Drop` 实现——drop 也算一次使用（第 04 章 dropck） |
| "这条路径根本不会执行" | 借用检查不做路径可行性分析（不可判定）。`if false` 里的代码也检查 |
| 加个 `{}` 块就好了 | 你缩小了某个作用域。在 NLL/Polonius 时代这通常意味着涉及 `Drop` 类型 |
| 循环里的借用特别难搞 | 循环让 CFG 有回边，可达性会绕回去。Polonius 改善了很多，但循环仍是最难的形态 |
| 期待 Polonius 解决字段粒度问题 | 它不解决。那是签名表达力问题，见第 17 章 |

---

下一章：[08 - rustc borrowck 内部结构](08-borrowck-internals.md)——打开引擎盖。
