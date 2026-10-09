# 14 - 著名难题：从 NLL problem cases 到今天

> 本章目标：把社区多年来反复讨论的那些"Rust 编译不过"的经典例子**逐个实测一遍**，
> 给出 2026-08 的真实状态。你会发现其中一大半**已经不再是问题了**——
> 而这正是本章最大的价值：**清理你从旧资料里读来的过时结论**。
> 预计用时：2.5 小时。

---

## 1. RFC 2094 的四个 problem case（1.0 时代的痛点）

2017 年的 NLL RFC 列了四个"当时编译不过、但显然应该能过"的例子。
**全部实测**（`rustc 1.96.0` = NLL，`1.100.0-nightly` = Polonius Alpha，edition 2024）：

### Problem case #1：引用赋给变量后

```rust
fn capitalize(_d: &mut [char]) {}

pub fn pc1() {
    let mut data = vec!['a', 'b', 'c'];
    capitalize(&mut data[..]);
    data.push('d');
}
```

| 1.0（词法） | NLL | Polonius Alpha |
|---|---|---|
| ❌ | ✅ | ✅ |

**NLL 解决的**：借用在 `capitalize` 调用结束后就死了，不必等到作用域末尾。

### Problem case #2：条件控制流

```rust
fn process(_v: &mut i32) {}

pub fn pc2(map: &mut HashMap<u32, i32>, key: u32) {
    match map.get_mut(&key) {
        Some(v) => process(v),
        None => { map.insert(key, 0); }
    }
}
```

| 1.0 | NLL | Polonius Alpha |
|---|---|---|
| ❌ | ✅ | ✅ |

**NLL 解决的**：`Some` 分支的借用在 `process(v)` 之后就死了，
`None` 分支上根本没有活跃借用。

### Problem case #3：条件控制流**跨函数**（★ 留给 Polonius 的那个）

```rust
pub fn pc3<'r, K: Hash + Eq + Copy, V: Default>(map: &'r mut HashMap<K, V>, key: K) -> &'r mut V {
    match map.get_mut(&key) {
        Some(v) => v,
        None => { map.insert(key, V::default()); map.get_mut(&key).unwrap() }
    }
}
```

| 1.0 | NLL | Polonius Alpha |
|---|---|---|
| ❌ | ❌ **E0499 ×2** | ✅ |

**这是唯一一个 NLL 没解决的**，也是 Polonius 项目立项的直接动因。

**和 #2 的差别只有一处：`-> &'r mut V`（借用要跨出函数）。**
第 12 章 §1.1 详细分析了这个分水岭。

### Problem case #4：修改 `&mut` 引用本身

```rust
pub struct List<T> { pub value: T, pub next: Option<Box<List<T>>> }

pub fn pc4<T>(mut list: &mut List<T>) -> Vec<&mut T> {
    let mut r = vec![];
    loop {
        r.push(&mut list.value);
        if let Some(n) = list.next.as_mut() { list = n; } else { return r; }
    }
}
```

| 1.0 | NLL（RFC 写作时预期） | **NLL（2026 实测）** | Polonius Alpha |
|---|---|---|---|
| ❌ | 部分解决 | ✅ | ✅ |

> ### ★ 一个重要的方法论提醒
> **RFC 2094 里说 #4"NLL 只能部分解决"，但今天实测它完全通过。**
>
> 原因是：**NLL 这些年一直在改进**。2018 年上线之后，rustc 团队持续修补它的
> region 推断，很多当年的限制早就没了。
>
> **所以：任何"Rust 编译不过 X"的结论，都必须标注年份并复核。**
> 本课程的所有结论都在 2026-08 实测过，且给了 `lab/run.sh` 让你自己复现。

---

## 2. 2026-08 的完整实测表

这是 `lab/run.sh` 的输出（28 个案例）。**★ 标记的 5 个就是这次换代的全部实质内容**：

| 案例 | NLL | Polonius Alpha | 类别 |
|---|---|---|---|
| 01 迭代器失效 | ❌ E0502 | ❌ E0502 | 真·别名冲突 |
| 02 NLL 基本功 | ✅ | ✅ | — |
| 03 两阶段借用 | ✅ | ✅ | — |
| 04 两阶段借用边界 | ❌ E0502 | ❌ E0502 | 规则边界 |
| **05 problem case #1（match 一支借一支改）** | ❌ E0502 | **✅** | ★ 精度 |
| **06 problem case #3（match 版）** | ❌ E0499 | **✅** | ★ 精度 |
| **07 problem case #3（loop 版）** | ❌ E0499 | **✅** | ★ 精度 |
| **08 条件重借用** | ❌ E0499 | **✅** | ★ 精度 |
| 09 lending iterator（基础） | ✅ | ✅ | — |
| **10 lending iterator + 条件返回** | ❌ E0499 | **✅** | ★ 精度 |
| 11 字段分割（直接访问） | ✅ | ✅ | — |
| 12 **字段分割（经方法）** | ❌ E0502 | ❌ E0502 | **表达力** |
| 13 **`&mut v[0]` + `&mut v[1]`** | ❌ E0499 | ❌ E0499 | **表达力** |
| 14 `split_at_mut` | ✅ | ✅ | — |
| 15 **自引用结构** | ❌ E0505 | ❌ E0505 | **表达力** |
| 16 返回局部变量引用 | ❌ E0515 | ❌ E0515 | 真·悬垂 |
| 17 闭包不相交捕获 | ✅ | ✅ | — |
| 18–21 临时值 / edition / await | ✅ | ✅ | — |
| 22 `spawn` 的 `'static` | ❌ E0373 | ❌ E0373 | 真·约束 |
| 23 scoped thread | ✅ | ✅ | — |
| 24 `Rc` 不是 `Send` | ❌ E0277 | ❌ E0277 | 真·约束 |
| 25 `let _ = x` 不捕获 | ✅ | ✅ | 反直觉 |
| 26 `MutexGuard` 跨 await | ❌（无编号） | ❌ | 真·约束 |
| 27 guard 在 await 前 drop | ✅ | ✅ | — |
| 28 链表收集 `&mut` | ✅ | ✅ | — |

**汇总：两者都接受 14，★ Polonius 新增 5，两者都拒绝 9。**

---

## 3. 五个 ★ 案例的共同形状

把这 5 个放在一起看，它们其实是**同一个模式的变体**：

```
在一条控制流路径上产生一个借用
    ↓
在某些路径上使用它（甚至返回出去）
    ↓
在另一些路径上根本不用它，但要访问被借的东西
```

**最小骨架**：

```rust
fn skeleton(x: &mut T) -> &mut U {
    let borrow = x.something_mut();       // 产生借用
    if cond(&borrow) {
        borrow                             // 路径 A：用它
    } else {
        x.other_mut()                      // 路径 B：不用它，但要重新借 x
    }
}
```

**记住这个骨架**。以后在自己的代码里看到它，你就知道：
- 在 stable 上会失败
- 在 nightly 上能过
- 稳定化之后可以直接写

**五个变体**：

| 案例 | 变体形式 |
|---|---|
| 05 | `match v.first() { Some(x) => x, None => { v.push(..); v.first().unwrap() } }` |
| 06 | 同上，容器换成 `HashMap`，借用是 `&mut` |
| 07 | 把 `match` 放进 `loop` |
| 08 | 最纯粹的形式：`let b = &mut *a; if c { b } else { a }` |
| 10 | lending iterator 上的 `loop { match it.next() { Some(w) if p(w) => return Some(w), ... } }` |

---

## 4. 九个"两者都拒绝"的案例：两种完全不同的原因

**这是本章最重要的一张分类表**——它决定了你该等编译器改进，还是该改代码。

### 4.1 真·别名冲突（编译器是对的，去改设计）

| 案例 | 为什么是真冲突 |
|---|---|
| 01 迭代器失效 | `push` 可能重分配，迭代器持有的指针会悬垂。**运行时真的会出事** |
| 16 返回局部变量引用 | 栈帧销毁，引用必然悬垂 |
| 22 `spawn` 的 `'static` | 编译器无法知道线程何时结束 |
| 24 `Rc` 不是 `Send` | 非原子计数，跨线程就是数据竞争 |
| 26 `MutexGuard` 跨 await | guard 是 `!Send`，Future 也就 `!Send` |

**这五个永远不会被"修好"**，因为它们不是编译器的问题。

### 4.2 签名表达力不足（需要新的语言特性，第 17 章）

| 案例 | 缺什么 | 未来方案 |
|---|---|---|
| 12 字段分割（经方法） | 签名无法说"我只访问 `self.a`" | **view types** |
| 13 `&mut v[0]` + `&mut v[1]` | `IndexMut` 签名无法说"我只碰第 i 个" | view types / place-based lifetimes |
| 15 自引用结构 | 类型系统无法表达"字段引用同结构的另一字段" | **internal references** |

**这三个是 "The Borrow Checker Within" 的目标**，**没有稳定化时间表**。

### 4.3 规则边界（不是 bug，是权衡）

| 案例 | 说明 |
|---|---|
| 04 两阶段借用边界 | 两阶段借用只对 autoref 生效，这是刻意的范围限制 |

### 4.4 判断流程

```
编译器拒绝了我的代码
   │
   ├─ 运行时真的有两条路径访问同一份数据且至少一条在写？
   │     ├─ 有  ──────────────────────► 4.1 类：改设计
   │     └─ 没有
   │           │
   │           ├─ 把函数手工内联展开成直接的字段/元素访问，能过吗？
   │           │     ├─ 能  ──────────► 4.2 类：签名表达力不足
   │           │     │                   → 用 splitter / 索引 / unsafe 封装（第 18 章）
   │           │     └─ 不能
   │           │           │
   │           │           └─ 匹配第 3 节的"骨架"吗？
   │           │                 ├─ 匹配 ──► ★ 精度问题
   │           │                 │            → nightly 上能过；stable 上用第 18 章手法
   │           │                 └─ 不匹配 ──► 回到 4.1 再想想，八成真的有冲突
```

---

## 5. lending iterator：从"不可能"到"可以"

这是一个值得单独讲的案例，因为它跨越了三个特性。

### 5.1 需求

写一个迭代器，每次返回一个**借用了迭代器自身**的元素（比如可变的滑动窗口）。

```rust
// 用标准 Iterator 是不可能的：
trait Iterator { type Item; fn next(&mut self) -> Option<Self::Item>; }
//               ^^^^^^^^^ Item 不能引用 &mut self
```

**为什么不可能**：`Item` 是关联类型，在 `impl` 时就固定了，
无法引用 `next` 的 `&mut self` 的生命周期。

### 5.2 GAT（泛型关联类型，1.65 稳定）解决了签名问题

```rust
pub trait LendingIterator {
    type Item<'a> where Self: 'a;                     // ★ 关联类型带生命周期参数
    fn next(&mut self) -> Option<Self::Item<'_>>;
}
```

**GAT 在 2022-11（Rust 1.65）稳定**，这是等了 6 年的特性。

### 5.3 实现（实测 ✅ 在 NLL 上就能过）

```rust
pub struct Windows { v: Vec<i32>, i: usize }

impl LendingIterator for Windows {
    type Item<'a> = &'a mut [i32] where Self: 'a;
    fn next(&mut self) -> Option<&mut [i32]> {
        if self.i + 2 > self.v.len() { return None }
        let s = &mut self.v[self.i..self.i + 2];
        self.i += 1;
        Some(s)
    }
}

pub fn drive(it: &mut Windows) {
    while let Some(w) = it.next() { w[0] += 1; }       // ✅ NLL 就能过
}
```

### 5.4 但条件返回还是要 Polonius（lab/10）

```rust
pub fn find_mut(it: &mut Windows) -> Option<&mut [i32]> {
    loop {
        match it.next() {
            Some(w) => { if w[0] > 0 { return Some(w); } }    // ★ 条件返回
            None => return None,
        }
    }
}
```

**实测**：NLL ❌ E0499 / Polonius Alpha ✅

**这就是第 3 节骨架的 lending iterator 版本。**

### 5.5 lending iterator 的剩余问题

即使有了 GAT 和 Polonius，lending iterator 仍然**不能用 `for` 循环**，
也不能用 `Iterator` 的任何适配器（`map`/`filter`/`collect`）。
因为那些都要求 `Item` 不借用迭代器。

**这需要的是**"泛型上的 lifetime-generic 抽象"，属于更远的未来。
现状：用 `while let` 手写循环。

---

## 6. 其它几个流传很广但已过时的"Rust 做不到"

| 说法 | 年份 | 2026-08 现状 |
|---|---|---|
| "Rust 写不了 lending iterator" | ≤2022 | ❌ 过时。GAT 1.65 稳定 |
| "Rust 没有 async trait" | ≤2023 | ❌ 过时。**AFIT/RPITIT 在 1.75 稳定**（`async fn` 可以直接写在 trait 里，但 trait object 仍需 `async-trait` 宏） |
| "`impl Trait` 不能出现在 trait 方法返回值" | ≤2023 | ❌ 过时。RPITIT 1.75 稳定 |
| "`let-else` 不存在" | ≤2022 | ❌ 过时。1.65 稳定 |
| "闭包捕获整个结构体" | ≤2021 | ❌ 过时。RFC 2229，2021 edition |
| "`if let` 的 `else` 里会持锁" | ≤2024 | ❌ 过时（在 2024 edition 里）。**但 2021 edition 项目仍然会** |
| "NLL problem case #3 编译不过" | ≤2026-08 | ⚠️ **stable 上仍然是**，nightly 已经可以 |
| "不能同时可变借用 `v[0]` 和 `v[1]`" | 一直 | ✅ **仍然成立**。用 `split_at_mut` / `get_disjoint_mut` |
| "不能写自引用结构" | 一直 | ✅ **仍然成立**（安全 Rust 里） |
| "方法会借走整个 self" | 一直 | ✅ **仍然成立**。等 view types |

> ### 使用本表的方法
> 你在网上看到"Rust 做不到 X"时，先查这张表，再用 `lab/run.sh` 的方式自己实测。
> **Rust 生态的一个特点是：文档和博客的半衰期很短。**

---

## 7. 动手实验

### 实验 1：复现 RFC 2094 的四个 case

```bash
cd /tmp && cat > rfc.rs <<'RSEOF'
use std::collections::HashMap; use std::hash::Hash;
fn capitalize(_d: &mut [char]) {}
pub fn pc1() { let mut d = vec!['a','b']; capitalize(&mut d[..]); d.push('c'); }
fn process(_v: &mut i32) {}
pub fn pc2(m: &mut HashMap<u32,i32>, k: u32) {
    match m.get_mut(&k) { Some(v)=>process(v), None=>{ m.insert(k,0); } }
}
pub fn pc3<'r,K:Hash+Eq+Copy,V:Default>(m:&'r mut HashMap<K,V>, k:K) -> &'r mut V {
    match m.get_mut(&k) { Some(v)=>v, None=>{ m.insert(k,V::default()); m.get_mut(&k).unwrap() } }
}
pub struct List<T>{ pub value:T, pub next:Option<Box<List<T>>> }
pub fn pc4<T>(mut l:&mut List<T>) -> Vec<&mut T> {
    let mut r=vec![]; loop { r.push(&mut l.value); if let Some(n)=l.next.as_mut(){ l=n; } else { return r; } }
}
RSEOF
echo "--- NLL ---";      rustc          --edition 2024 --crate-type=lib --emit=metadata --out-dir /tmp/o rfc.rs 2>&1 | grep "^error\["
echo "--- Polonius ---"; rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir /tmp/o rfc.rs 2>&1 | grep "^error\["
```

**预期**：NLL 只有 `pc3` 报两个 E0499；Polonius 全过。

### 实验 2：把骨架套到自己的代码上

回想（或翻一下）你写 Rust 时被卡住的一次。**它匹配第 3 节的骨架吗？**
如果匹配，在 nightly 上试一遍。

### 实验 3：给九个"都拒绝"的案例分类

不看第 4 节的答案，自己给 lab 里 9 个"两者都拒绝"的案例分类：
真·冲突 / 表达力不足 / 规则边界。然后对照。

**分错的那些，回去重读对应章节。**

---

## 8. 本章检查清单

- [ ] 知道 RFC 2094 的四个 problem case 各自的现状
- [ ] 知道 **#3 是唯一留给 Polonius 的**，且知道它和 #2 的分水岭是"借用是否跨出函数"
- [ ] 知道 **#4 今天在 NLL 上已经能过**——说明"NLL 做不到 X"的旧结论要复核
- [ ] **能背出第 3 节的"骨架"**，一眼认出精度问题
- [ ] 能把编译器的拒绝分成三类：真·冲突 / 表达力不足 / 规则边界
- [ ] 能走完第 4.4 节的判断流程
- [ ] 知道 lending iterator 需要 GAT（1.65）+ Polonius（条件返回形态）
- [ ] 知道第 6 节表里哪些"Rust 做不到"已经过时

---

## 9. 常见坑

| 误解 | 事实 |
|---|---|
| "Polonius 会解决所有借用问题" | 只解决"条件控制流"这一类。字段粒度、自引用、索引不相交完全没动 |
| "NLL 就是 2018 年的样子" | 它一直在改进。problem case #4 就是例子 |
| "看到 E0499 就是 Polonius 能解决的" | 不一定。`&mut v[0]` + `&mut v[1]` 也是 E0499，但 Polonius 不救 |
| "在 nightly 上能过就可以用了" | ⚠️ **稳定化前不要在生产代码里依赖**。目标是 2026 年底 |
| "GAT 稳定了 lending iterator 就完美了" | 还不能用 `for` 和迭代器适配器 |
| "async trait 还需要 `async-trait` 宏" | 1.75 起原生支持；只有需要 `dyn` 时才要宏 |

---

**阶段 2 到此结束。** 你现在能准确判断任何一个借用错误的类别了。
接下来第 15–17 章深入 Polonius 的形式化和未来。

下一章：[15 - Polonius 的完整形式化](15-polonius-theory.md)
