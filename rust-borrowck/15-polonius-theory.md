# 15 - Polonius 的完整形式化：八条规则

> 本章目标：把借用检查**完整地**写成 8 条 datalog 规则，然后**手工跑一次不动点**，
> 用真实的编译器 dump 逐字验证。
> 学完这章，你可以说自己**完全理解**了 Rust 借用检查的算法——不是比喻，是字面意义上的。
> 预计用时：3.5 小时（必须动手推）。

---

## 1. 为什么是 datalog

Niko Matsakis 2018 年重构 borrow checker 时选了 **Datalog** 作为表述语言。理由：

| 好处 | 说明 |
|---|---|
| **声明式** | 规则就是定义，没有"算法顺序"的干扰。你读规则 = 读语义 |
| **可形式化验证** | 规则可以喂给 Alloy / Coq 做性质证明 |
| **不动点语义天然** | Datalog 的求值就是最小不动点，和 region 推断的语义一致 |
| **可增量** | Datalog 引擎（如 rustc 用的 [datafrog](https://github.com/rust-lang/datafrog)）天然支持增量计算 |
| **可解释** | 能回答"这个错误是哪条规则推出来的"（对诊断信息很有价值） |

**Datalog 30 秒速成**（你只需要知道这些）：

```datalog
head(X, Y) :- body1(X, Z), body2(Z, Y), !body3(X).
 ↑            ↑                          ↑
 结论          前提（用逗号连接 = 逻辑与）   否定（!）

// 读作："如果 body1(X,Z) 且 body2(Z,Y) 且 不 body3(X)，那么 head(X,Y)"
// 大写字母是变量，小写是关系名
// 分号 ; 表示"或"
```

**求值方式**：从输入事实出发，反复应用所有规则，直到不再产生新事实（**不动点**）。

---

## 2. 输入关系：编译器喂给分析器的东西

这 8 个关系是 Polonius 的**全部输入**。它们由 rustc 的 MIR type check 阶段产出，
你可以用 `-Znll-facts` 直接 dump 出来（第 08 章）。

| 关系 | 签名 | 含义 |
|---|---|---|
| `cfg_edge` | `(P, Q)` | 控制流图上 P 的后继是 Q |
| `loan_issued_at` | `(Origin, Loan, P)` | 贷款 `Loan` 在点 P 产生，进入 origin `Origin` |
| `loan_killed_at` | `(Loan, P)` | 在点 P，被借路径的某个前缀被覆写 → 贷款失效 |
| `loan_invalidated_at` | `(P, Loan)` | ★ 点 P 上有一次访问会**破坏**贷款 `Loan` |
| `subset_base` | `(Origin1, Origin2, P)` | 在点 P 上，`Origin1 ⊆ Origin2`（非传递的基础事实） |
| `origin_live_on_entry` | `(Origin, P)` | origin 出现在点 P 的某个活跃变量的类型里 |
| `placeholder` | `(Origin, Loan)` | universal region 对应的"占位贷款" |
| `known_placeholder_subset` | `(Origin1, Origin2)` | 签名里显式声明的 `'a: 'b` |

> ### 关于 `placeholder`
> 函数签名里的生命周期（`'a`、`'static`、`&self` 的匿名生命周期）在函数体内是"外部给定"的。
> Polonius 给每个这样的 origin 分配一笔**假想的贷款**，
> 表示"这里可能借了函数外面的某个东西，我不知道是什么"。
>
> 这就是为什么 `errors` 里会出现"借用要活到函数返回之后"这类判断——
> 它是通过占位贷款传播出来的。

---

## 3. 八条规则（Naive 变体，官方原文）

以下是 [Polonius Book](https://rust-lang.github.io/polonius/rules/loans.html) 里
"naive" 变体的完整规则。**"naive" 的意思是"为了清晰而不优化"**——
它算出了比必需更多的东西（完整的传递子集、每个点上每个 origin 的贷款集）。

### 3.1 第一组：`subset`（origin 之间的子集关系）

```datalog
.decl subset(Origin1: origin, Origin2: origin, Point: point)

// R1：从非传递的输入事实起步
subset(Origin1, Origin2, Point) :-
  subset_base(Origin1, Origin2, Point).

// R2：在同一个点上求传递闭包
subset(Origin1, Origin3, Point) :-
  subset(Origin1, Origin2, Point),
  subset(Origin2, Origin3, Point).

// R3：沿 CFG 传播子集关系，但只在两端 origin 都活着时
subset(Origin1, Origin2, TargetPoint) :-
  subset(Origin1, Origin2, SourcePoint),
  cfg_edge(SourcePoint, TargetPoint),
  (origin_live_on_entry(Origin1, TargetPoint); placeholder(Origin1, _)),
  (origin_live_on_entry(Origin2, TargetPoint); placeholder(Origin2, _)).
```

**R3 是流敏感的关键之一**：子集关系**不会**无条件地传遍整个 CFG，
只在 origin 还活着的路径上传播。

### 3.2 第二组：`origin_contains_loan_on_entry`（每个 origin 装着哪些贷款）

```datalog
.decl origin_contains_loan_on_entry(Origin: origin, Loan: loan, Point: point)

// R4：贷款产生时，进入它的 origin
origin_contains_loan_on_entry(Origin, Loan, Point) :-
  loan_issued_at(Origin, Loan, Point).

// R5：在同一个点上，沿子集关系传播贷款
origin_contains_loan_on_entry(Origin2, Loan, Point) :-
  origin_contains_loan_on_entry(Origin1, Loan, Point),
  subset(Origin1, Origin2, Point).

// R6：沿 CFG 传播贷款，但要避开 kill 点，且 origin 要活着
origin_contains_loan_on_entry(Origin, Loan, TargetPoint) :-
  origin_contains_loan_on_entry(Origin, Loan, SourcePoint),
  !loan_killed_at(Loan, SourcePoint),
  cfg_edge(SourcePoint, TargetPoint),
  (origin_live_on_entry(Origin, TargetPoint); placeholder(Origin, _)).
```

> ### ★ R6 是整个分析的心脏
> 它同时体现了三件事：
> 1. **可达性**：贷款沿 CFG 边往下流
> 2. **kill**：被借的东西被覆写了，贷款就断在这里
> 3. **liveness**：origin 死了，贷款也不再传播
>
> 第 07 章说的"贷款活跃性 = 图上的可达性"，指的就是 R6 的传递闭包。

### 3.3 第三组：`loan_live_at` 与 `errors`

```datalog
.decl loan_live_at(Loan: loan, Point: point)

// R7：只要某个活着的 origin 装着这笔贷款，贷款就活着
loan_live_at(Loan, Point) :-
  origin_contains_loan_on_entry(Origin, Loan, Point),
  (origin_live_on_entry(Origin, Point); placeholder(Origin, _)).

.decl errors(Loan: loan, Point: point)

// R8：★ 最终判据
errors(Loan, Point) :-
  loan_invalidated_at(Loan, Point),
  loan_live_at(Loan, Point).
```

> ## R8 就是 Rust 借用检查的全部
>
> **"一笔贷款在某个点被破坏了，而它在那个点还活着" = 错误。**
>
> 前面 7 条规则全是为了精确计算 `loan_live_at`。
> 而 `loan_invalidated_at` 是编译器根据"访问类型 × 贷款类型"直接生成的输入事实
> （对应附录 A 那张 E0499/E0502/E0503/E0505/E0506 的组合表）。

---

## 4. 手工跑一次不动点（★ 本章核心）

我们用一个**最小的失败例子**，把 8 条规则从头跑到尾，最后和编译器的报错对照。

### 4.1 源码

```rust
pub fn f() {
    let mut v = 1;
    let r = &v;
    v = 2;           // ★ 这里应该报错
    let _ = *r;
}
```

### 4.2 MIR（实测 dump）

```
bb0[0]   StorageLive(_1)
bb0[1]   _1 = const 1_i32
bb0[2]   FakeRead(ForLet(None), _1)
bb0[3]   StorageLive(_2)
bb0[4]   _2 = &_1                      ← ★ 贷款在这里产生
bb0[5]   FakeRead(ForLet(None), _2)
bb0[6]   _1 = const 2_i32              ← ★ 冲突点
bb0[7]   PlaceMention((*_2))           ← _2 的最后一次使用
bb0[8]   _0 = const ()
bb0[9]   StorageDead(_2)
bb0[10]  StorageDead(_1)
bb0[11]  return
```

（`_1` = `v`，`_2` = `r`。每条语句拆成 `Start(bb0[i])` 和 `Mid(bb0[i])` 两个点。）

### 4.3 输入事实（实测 `-Znll-facts` 输出，逐字）

```
loan_issued_at:
  ('?2, bw0, Mid(bb0[4]))

subset_base:
  ('?2, '?3, Mid(bb0[4]))

loan_killed_at:
  (bw0, Mid(bb0[1]))
  (bw0, Mid(bb0[6]))          ← ★ v = 2 覆写了被借的路径
  (bw0, Mid(bb0[10]))

loan_invalidated_at:
  (Start(bb0[1]),  bw0)
  (Start(bb0[6]),  bw0)       ← ★
  (Start(bb0[10]), bw0)
  (Start(bb0[11]), bw0)

use_of_var_derefs_origin:
  (_2, '?3)

var_used_at:
  (_2, Mid(bb0[5]))
  (_2, Mid(bb0[7]))           ← ★ 最后一次使用

placeholder:      ('?0, bw1), ('?1, bw2)
universal_region: '?0, '?1
cfg_edge:         Start(bb0[i]) → Mid(bb0[i]) → Start(bb0[i+1]) → ...（线性）
```

### 4.4 先算 `origin_live_on_entry`

`_2` 的类型是 `&'?3 i32`，且 `use_of_var_derefs_origin(_2, '?3)`。
`_2` 在 `Mid(bb0[5])` 和 `Mid(bb0[7])` 被使用，定义于 `Mid(bb0[4])`。

**`_2` 活跃 ⟹ `'?3` 活跃**。逆向 liveness 分析（第 07 章）给出：

```
'?3 live on entry at:  Start(bb0[5]), Mid(bb0[5]), Start(bb0[6]), Mid(bb0[6]),
                       Start(bb0[7]), Mid(bb0[7])
```

（`Mid(bb0[7])` 之后 `_2` 再没被用过 → 不活跃。）

`'?2` 只在 `Mid(bb0[4])` 这一瞬存在（它是 `&_1` 这个右值的 origin）。

### 4.5 应用规则

**R1**（`subset_base` → `subset`）：

```
subset('?2, '?3, Mid(bb0[4]))
```

**R2**（传递闭包）：没有新的（只有一条边）。

**R3**（沿 CFG 传播 subset）：需要 `'?2` 在下一个点也活着，但 `'?2` 不活了 → 无新事实。

**R4**（贷款产生）：

```
origin_contains_loan_on_entry('?2, bw0, Mid(bb0[4]))
```

**R5**（沿 subset 传播）：在 `Mid(bb0[4])` 上 `'?2 ⊆ '?3`，所以

```
origin_contains_loan_on_entry('?3, bw0, Mid(bb0[4]))     ★ 新事实
```

**R6**（沿 CFG 传播，避开 kill，要求 origin 活着）：

从 `Mid(bb0[4])` 出发，逐条边推：

| Source | 有 kill 吗？ | Target | `'?3` 在 Target 活吗？ | 产生新事实？ |
|---|---|---|---|---|
| `Mid(bb0[4])` | 否 | `Start(bb0[5])` | ✅ | ✅ |
| `Start(bb0[5])` | 否 | `Mid(bb0[5])` | ✅ | ✅ |
| `Mid(bb0[5])` | 否 | `Start(bb0[6])` | ✅ | ✅ ★ |
| `Start(bb0[6])` | 否 | `Mid(bb0[6])` | ✅ | ✅ |
| `Mid(bb0[6])` | ★ **有！** `loan_killed_at(bw0, Mid(bb0[6]))` | — | — | ❌ **传播中断** |

**结果**：

```
origin_contains_loan_on_entry('?3, bw0, P)
    for P ∈ { Mid(bb0[4]), Start(bb0[5]), Mid(bb0[5]), Start(bb0[6]), Mid(bb0[6]) }
```

**R7**（贷款活跃性）：`'?3` 在上述点中除 `Mid(bb0[4])` 外都活跃，所以

```
loan_live_at(bw0, P)  for P ∈ { Start(bb0[5]), Mid(bb0[5]), Start(bb0[6]), Mid(bb0[6]) }
```

**R8**（错误）：把 `loan_invalidated_at` 的四条逐个对照 `loan_live_at`：

| 破坏点 | `loan_live_at(bw0, P)` ? | 结论 |
|---|---|---|
| `Start(bb0[1])` | ❌（贷款还没产生） | 无错误 |
| **`Start(bb0[6])`** | **✅** | ★ **errors(bw0, Start(bb0[6]))** |
| `Start(bb0[10])` | ❌（传播已在 `Mid(bb0[6])` 中断） | 无错误 |
| `Start(bb0[11])` | ❌ | 无错误 |

**推导出恰好一个错误，位置在 `Start(bb0[6])`。**

### 4.6 对照编译器

```
error[E0506]: cannot assign to `v` because it is borrowed
 --> tiny.rs:4:5
  |
3 |     let r = &v;
  |             -- `v` is borrowed here
4 |     v = 2;
  |     ^^^^^ `v` is assigned to here but it was already borrowed
5 |     let _ = *r;
  |             -- borrow later used here
```

**`bb0[6]` 正是源码第 4 行 `v = 2;`。完全对上。**

三个 span 也能一一对应：
- `` `v` is borrowed here `` → `loan_issued_at(_, bw0, Mid(bb0[4]))`
- `` is assigned to here `` → `loan_invalidated_at(Start(bb0[6]), bw0)`
- `` borrow later used here `` → **让 `'?3` 一直活到 `Mid(bb0[7])` 的那次使用**

> ### ★ 你刚刚手工执行了一遍 rustc 的借用检查
> 这不是简化模型，是**真正的算法**。所有借用错误都是这 8 条规则推出来的。

### 4.7 验证"改一行就没错"

把源码改成：

```rust
pub fn f() {
    let mut v = 1;
    let r = &v;
    let _ = *r;      // ★ 提前使用
    v = 2;
}
```

现在 `_2` 的最后一次使用提前了，`'?3` 在 `v = 2` 那个点**不再活跃** →
R6 不再把贷款传播到那里 → R7 不成立 → R8 的第二个前提失败 → **无错误**。

---

## 5. Naive 之外的三个变体

Polonius 引擎提供了几个不同精度/性能的变体：

| 变体 | 特点 | 用途 |
|---|---|---|
| **Naive** | 算完整的传递子集和每点贷款集 | 定义语义的参考实现，最慢 |
| **LocationInsensitive** | 忽略 subset 里的 CFG 点，不追踪子集 | **快速预筛**：它是 Naive 的近似，如果它说"没错误"，那肯定没错误 |
| **Opt** | 优化过的实现，语义等价于 Naive | 实际使用 |
| **DatafrogOpt** | 用 datafrog 引擎的优化版 | 早期 rustc 集成 |

**rustc 的实际做法**（性能优化的关键）：
1. 先跑 `LocationInsensitive`（快）
2. 如果它报告"无错误"，直接通过 ✅
3. 只有它报告可能有错误时，才跑精确的分析

**这是 Polonius 能在真实代码上跑得动的原因**——绝大部分函数在第 1 步就过了。

---

## 6. rustc 里的 Polonius Alpha ≠ 这套 datalog

⚠️ **重要区分**。上面讲的是 **Polonius 项目的 datalog 形式化**（`-Zpolonius=legacy` 用它生成事实）。
而 **2026-08 在 nightly 默认开启的 "Polonius Alpha" 是 rustc 内部的原生实现**，
它**不跑 datalog 引擎**。

**Alpha 的实际做法**（`rustc_borrowck::polonius` 模块文档原文）：

> "models flow-sensitive borrow-checking concerns as a graph containing both region and
> control flow information，loan propagation seen as a reachability problem"

具体是：

| 步骤 | 做法 |
|---|---|
| 1 | 把 NLL 的 typeck 约束**局部化**成 `(origin, point)` 节点之间的边 |
| 2 | 加上活跃性约束的边（origin 在两点都活 → 加一条沿 CFG 的边） |
| 3 | **不变型变**（第 09 章）产生**双向边**——贷款可以"逆着时间"往回流 |
| 4 | 从每笔贷款的产生节点做**图遍历**，记录可达性 = 贷款活跃性 |
| 5 | 再跑一遍 NLL 的数据流得到 "active loans"（在作用域内的贷款） |
| 6 | 检查非法访问 |

**为什么换实现**：datalog 引擎（datafrog）在大函数上会爆炸。
原生图遍历实现**可扩展性好得多**，这是它能进入稳定化流程的前提。

**语义关系**：Alpha 是完整 Polonius 的一个**子集**——
官方明确说"有些在原始 Polonius 表述下能编译的程序，在 Alpha 下编译不过"。

| | 完整 Polonius（datalog） | Polonius Alpha（rustc 原生） |
|---|---|---|
| 实现 | datafrog datalog 引擎 | 原生图可达性 |
| 精度 | 完整流敏感 | Alpha 子集 |
| 性能 | 大函数上会爆 | 可接受（少数场景 2–3× 回归） |
| 状态 | 参考实现 / `-Zpolonius=legacy` 的事实生成 | **nightly 默认，目标 2026 底稳定** |
| 后续 | — | **稳定化后不再继续功能开发** |

---

## 7. 动手实验

### 实验 1：完整复现第 4 节

```bash
mkdir -p /tmp/tiny && cd /tmp/tiny
cat > tiny.rs <<'RSEOF'
pub fn f() {
    let mut v = 1;
    let r = &v;
    v = 2;
    let _ = *r;
}
RSEOF

# 1) 拿 MIR（借用检查失败时 -Zunpretty=mir 不输出，所以用 dump）
mkdir -p out
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out \
      -Zdump-mir=nll -Zdump-mir-dir=out -Zpolonius=off tiny.rs 2>/dev/null
sed -n '/bb0: {/,/^    }/p' out/*nll.0.mir | sed 's|//.*||' | grep -vE '^\s*$' \
  | tail -n +2 | awk '{printf "bb0[%d]  %s\n", NR-1, $0}'

# 2) 拿全部输入事实
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out \
      -Znll-facts -Znll-facts-dir=facts tiny.rs 2>/dev/null
for f in facts/*/*.facts; do
  [ -s "$f" ] && { echo "--- $(basename $f .facts) ---"; cat "$f"; }
done
```

**任务**：不看第 4 节，自己把 R1–R8 跑一遍，推出错误位置，再对照编译器输出。

### 实验 2：把贷款"弄死"

把 `tiny.rs` 改成第 4.7 节的版本（提前使用 `*r`），重新 dump 事实。
**对比 `var_used_at` 的变化**，然后重新跑 R6/R7/R8，解释为什么不报错了。

### 实验 3：用规则解释 problem case #3

拿 `lab/cases/06-problem-case-3-match.rs`：

```bash
cd lab
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out \
      -Znll-facts -Znll-facts-dir=/tmp/pc3facts cases/06-problem-case-3-match.rs 2>/dev/null
ls /tmp/pc3facts/*/
```

**任务**：
1. 找出 `get_mut` 产生的那笔贷款
2. 找出 `insert` 处的 `loan_invalidated_at`
3. **用 R6 论证：为什么这笔贷款传播不到 `None` 分支**（提示：看 `origin_live_on_entry`）
4. 再用第 07 章 §9 的 NLL 模型论证：为什么 NLL 会把它算进去

### 实验 4：加一个循环

```rust
pub fn f(n: usize) {
    let mut v = 1;
    for _ in 0..n {
        let r = &v;
        let _ = *r;
        v = 2;
    }
}
```

dump 事实，观察 `cfg_edge` 里出现的**回边**。
**思考**：R6 沿回边传播时，为什么不会把上一轮的贷款带进下一轮？（答案在 `loan_killed_at`）

---

## 8. 本章检查清单

- [ ] 会读 datalog 规则（`:-`、`,`、`;`、`!`）
- [ ] 能列出 8 个输入关系及其含义
- [ ] **能默写 R8：`errors :- loan_invalidated_at ∧ loan_live_at`**
- [ ] 能解释 R6 同时体现的三件事（可达性 / kill / liveness）
- [ ] **能独立手工跑一遍第 4 节的不动点**
- [ ] 能把编译器报错的三个 span 映射回三个事实
- [ ] 知道 `LocationInsensitive` 变体的作用（快速预筛）
- [ ] **知道 rustc 的 Polonius Alpha 不跑 datalog，而是图可达性**
- [ ] 知道 Alpha 是完整 Polonius 的子集，且后续不再开发

---

## 9. 常见坑

| 误解 | 事实 |
|---|---|
| "Polonius 就是那套 datalog" | 那是**参考形式化**。rustc 的 Alpha 是原生图实现，更快但精度是子集 |
| "R8 只是众多规则之一" | R8 **就是**借用检查的定义。R1–R7 都在为它算 `loan_live_at` |
| "kill 和 invalidate 是一回事" | 完全不同：**kill** = 被借的路径被覆写，贷款作废；**invalidate** = 有一次访问与贷款冲突 |
| "origin 就是 region" | 在 Polonius 里 origin 装的是**贷款**，NLL 里 region 装的是**程序点** |
| "placeholder 是实现细节" | 它是"借用跨出函数边界"的建模方式，是理解 problem case #3 的关键 |
| "Naive 变体是给初学者的" | 它是**语义定义**。Opt 变体必须和它等价 |

---

下一章：[16 - Polonius Alpha 现状实测（2026-08）](16-polonius-alpha.md)
