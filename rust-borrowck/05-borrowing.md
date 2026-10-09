# 05 - 借用、重借用、两阶段借用

> 本章目标：搞清楚"借用"到底是什么类型层面的操作。
> 三个重点：**重借用（reborrow）——为什么 `&mut` 不是 `Copy` 你却能反复用它**、
> **两阶段借用的精确边界**、**借用的粒度是 place 不是变量**。
> 预计用时：2.5 小时。

---

## 1. 三条规则的精确版

第 00 章给了口语版，现在给精确版：

> 在程序的**任意一个点**上，对**任意一个 place**（内存位置）：
>
> 1. 可以存在**任意多个**活跃的共享借用 `&T`，此时**没有**任何写访问（包括所有者自己）
> 2. 或者存在**恰好一个**活跃的独占借用 `&mut T`，此时**没有**任何其他访问（包括所有者自己的读）
> 3. 或者没有任何活跃借用，所有者自由读写
>
> "活跃"的定义由 NLL 给出：**从借用创建，到该借用（或从它派生出的任何借用）的最后一次使用**。

三个词需要展开：**place**、**活跃**、**派生**。

### 1.1 place：借用的粒度

**place（位置）** 是 rustc 内部的术语，指一个可以被读写的内存位置的**路径表达式**：

```rust
x                    // 一个局部变量
x.field              // 字段
x.field.inner        // 嵌套字段
*x                   // 解引用
x[i]                 // 索引（★ 特殊，见下）
(*x).field
```

**借用检查是按 place 做的，不是按变量做的。** 这解释了为什么下面这段能过：

```rust
struct S { a: Vec<i32>, b: Vec<i32> }
fn f(s: &mut S) {
    let ra = &s.a;              // 借用 place `(*s).a`
    s.b.push(1);                // 写 place `(*s).b`
    println!("{}", ra.len());   // ✅ 两个 place 不相交
}
```

**两个 place 冲突的判定**：一个是另一个的**前缀**，或者相等。
- `s.a` 和 `s.b` → 不相交 ✅
- `s` 和 `s.a` → `s` 是 `s.a` 的前缀 → 冲突 ❌
- `*p` 和 `*q`（两个不同引用）→ 编译器**假设可能相同**（它不做指针别名分析）→ 冲突

⚠️ **`x[i]` 是个例外**：索引不是内置 place（除了数组和 slice 的常量索引场景），
`v[i]` 会脱糖成 `*Index::index(&v, i)` 或 `*IndexMut::index_mut(&mut v, i)`——
**一个借了整个 `v` 的方法调用**。所以：

```rust
let a = &mut v[0];
let b = &mut v[1];       // ❌ E0499：两次都借了整个 v
*a += *b;                // ← 这行不能省，见下面的警告
```

这是 lab 里 13 号案例。**记住：`v[i]` 借的是整个 `v`。**

> ### ⚠️ 少了最后一行，这段就编译过了
> 本课程所有"❌"示例都带着**对借用的后续使用**，这不是凑数。
> 借用不被使用 → 活跃区间为空 → 和谁都不冲突。
> 你在网上看到的很多"最小复现"漏掉了这一行，粘进编译器发现不报错，
> 就以为规则变了——其实是**复现写错了**。
>
> **推论**：调试借用错误时，先找"最后一次使用"，而不是"在哪里借的"。

### 1.2 活跃：NLL 的定义

```rust
let mut x = 5;
let r = &x;              // 借用开始
println!("{}", r);       // 最后一次使用 → 借用结束
x = 6;                   // ✅ 此刻没有活跃借用
```

**"活跃"是 CFG 上的概念，不是词法的。** 第 07 章会精确定义：
一个借用在点 P 活跃，当且仅当**从 P 出发存在一条路径能到达该借用的某次使用**。

注意最后这句话的"存在一条路径"——这是**流不敏感**的近似，也正是 Polonius 要改进的地方（第 15 章）。

### 1.3 派生：借用链

```rust
let mut v = vec![1, 2, 3];
let r1 = &mut v;             // 借用 v
let r2 = &mut r1[0];         // 从 r1 派生
*r2 = 10;                    // 用 r2 → r1 的借用也必须还活着
// v.push(4);                // ❌ v 仍被借用（通过 r1 → r2 这条链）
println!("{:?}", v);         // ✅ r2/r1 都不用了
```

**从借用派生出的借用，会让原借用的活跃期延长到派生借用的最后一次使用。**
这是"借用链"，第 07 章会看到它在 region 约束里的形式。

---

## 2. 重借用（reborrow）：本章最重要的机制

### 2.1 一个必须解释的悖论

`&mut T` **不是 `Copy`**（第 04 章说过）。那这段代码为什么能编译？

```rust
fn takes(r: &mut i32) { *r += 1; }

fn main() {
    let mut x = 5;
    let r = &mut x;
    takes(r);            // r 被传进去了……
    takes(r);            // ……为什么还能再传一次？
    println!("{}", x);
}
```

如果 `r` 在第一次调用时被**移动**进 `takes`，第二次就该报 E0382。

**答案：这里发生的不是移动，是重借用（reborrow）。** 编译器把它脱糖成：

```rust
takes(&mut *r);          // ← 从 *r 这个 place 新建一个借用
takes(&mut *r);
```

**重借用的语义**：
- 创建一个**新的**借用，指向 `*r`
- 在新借用活跃期间，`r` 本身被**冻结**（不能用）
- 新借用结束后，`r` 恢复可用

```
r:        ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●
             ↓冻结          ↑恢复  ↓冻结  ↑恢复
新借用1:     ●━━━━━━━━━━━━━●
新借用2:                          ●━━━━━━━━●
```

### 2.2 重借用什么时候自动发生

**隐式重借用发生在"强制转换点（coercion site）"**，主要是：

```rust
fn takes(r: &mut i32);
takes(r);                    // ✅ 函数参数位置 → 自动 &mut *r

let s: &mut i32 = r;         // ✅ 有类型标注的 let → 自动重借用

r.method();                  // ✅ 方法调用的 self 位置

for x in &mut *v { }         // 需要显式写（for 的迭代表达式不是强制点）
```

**不会自动重借用的地方**（这些会真正移动）：

```rust
let s = r;                   // ❌ 无类型标注 → 移动！r 之后不可用
let v = vec![r];             // ❌ 放进容器 → 移动
let c = move || *r += 1;     // ❌ move 闭包 → 移动
fn generic<T>(t: T);  generic(r);   // ❌ 泛型参数 → 移动（不是强制点）
```

> ### 这是 Rust 里最隐蔽的坑之一
>
> ```rust
> let mut x = 5;
> let r = &mut x;
> let s = r;               // 移动（没有类型标注）
> // *r += 1;              // ❌ E0382: use of moved value
>
> let r2 = &mut x;
> let s2: &mut i32 = r2;   // 重借用（有类型标注）
> // *r2 += 1;             // ❌ E0503：不是移动，是 *r2 被 s2 借着（实测）
> *s2 += 1;
> *r2 += 1;                // ✅ s2 用完了，r2 恢复
> ```
>
> **同样的代码，加不加类型标注，语义完全不同，错误码也不同。**
> 遇到 `&mut` 相关的诡异错误，先问"这里是移动还是重借用"。

### 2.3 手动重借用：`&mut *`

需要时可以显式写：

```rust
fn consume(r: &mut i32) { }

let mut x = 5;
let r = &mut x;
consume(&mut *r);        // 显式重借用，r 之后还能用
*r += 1;                 // ✅
```

**什么时候必须手写**：泛型参数位置、闭包捕获、放进容器时。

```rust
fn generic<T: Debug>(t: T) { println!("{:?}", t); }

let r = &mut x;
generic(&mut *r);        // ✅ 显式重借用
*r += 1;                 // ✅ 还能用
// generic(r); *r += 1;  // ❌ r 被移动了
```

### 2.4 共享引用为什么不需要这套

`&T` **是 `Copy`**，所以传参就是复制一份，原来的照样能用。
**只有 `&mut` 需要重借用机制**——因为它必须维持"任意时刻只有一个"这个不变量。

> **一句话总结**：`&T` 靠 `Copy` 复用，`&mut T` 靠 reborrow 复用。
> 前者可以有多份同时活着，后者的多份是**嵌套**（栈式）的，任意时刻只有栈顶那个能用。
>
> 这个"栈式嵌套"的直觉，正是第 26 章 **Stacked Borrows** 模型的来源。

---

## 3. 两阶段借用（two-phase borrows）

### 3.1 问题

```rust
let mut v = vec![1, 2, 3];
v.push(v.len());
```

脱糖后：

```rust
Vec::push(&mut v, Vec::len(&v));
//        ^^^^^^^ 独占借用      ^^^^ 共享借用     ← 冲突？
```

按第 1 节的规则，这该报错。但它是安全的，而且太常见了（`v.push(v.len())`、
`map.insert(k, map.len())`、`self.items.push(self.next_id())`）。

### 3.2 解法：把 `&mut` 拆成两个阶段

**RFC 2025 / NLL 引入**：由 **autoref**（自动取引用）产生的 `&mut` 借用分两阶段：

| 阶段 | 时机 | 行为 |
|---|---|---|
| **保留（reserved）** | 从 `&mut` 创建到实际使用之前 | 表现得像**共享借用**：允许其他 `&`，但禁止其他 `&mut` 和直接写 |
| **激活（activated）** | 第一次通过它读写时 | 变成真正的独占借用 |

所以 `v.push(v.len())` 的时序是：

```
1. 为 push 的 self 参数创建 &mut v          → 进入「保留」阶段
2. 求值实参 v.len()，需要 &v                → 保留阶段允许 ✅
3. 进入 push 函数体，通过 &mut v 写         → 「激活」，此时 &v 已经结束 ✅
```

### 3.3 精确边界（高频考点）

**两阶段借用只对 autoref 生效**——也就是**方法调用语法**自动插入的那个 `&mut`。

```rust
let mut v = vec![1, 2, 3];

v.push(v.len());                 // ✅ autoref → 两阶段
Vec::push(&mut v, v.len());      // ❌ E0502：显式 &mut，没有两阶段
(&mut v).push(v.len());          // ❌ E0502：同上
```

lab 的 `03` / `04` 号案例就是这一对。**语义完全相同，写法不同，结果不同。**

**另外这些也不享受两阶段**：

```rust
let mut v = vec![1, 2, 3];
let r = &mut v;                  // 显式 let 绑定 → 立刻是完整的独占借用
// println!("{}", v.len());      // ❌ E0502
r.push(1);
```

### 3.4 为什么不干脆全都两阶段

因为两阶段借用**削弱了 `noalias` 优化**，且规则复杂。它是一个**专门为 autoref 这个高频场景
打的补丁**，而不是一条通用规则。设计者的原话大意是："这是权宜之计，Polonius 之后可能重新审视。"

**记忆法**：
> 两阶段借用 = "**方法调用的参数求值期间，`self` 的独占借用还没生效**"

---

## 4. 借用的分割：什么能拆，什么不能

这是**日常最高频的冲突来源**，第 12 章会展开更多场景，这里先建立分类。

### 4.1 ✅ 能拆的：直接字段访问

```rust
struct S { a: Vec<i32>, b: String }

fn f(s: &mut S) {
    let ra = &mut s.a;
    let rb = &mut s.b;         // ✅ 不同 place
    ra.push(1);
    rb.push('x');
}
```

### 4.2 ❌ 不能拆的：经过方法

```rust
impl S {
    fn a(&mut self) -> &mut Vec<i32> { &mut self.a }
    fn b(&mut self) -> &mut String   { &mut self.b }
}

fn f(s: &mut S) {
    let ra = s.a();
    let rb = s.b();            // ❌ E0499：两次都借了整个 *s
    ra.push(1);
}
```

**根因（第 03 章的局部推理）**：`fn a(&mut self) -> &mut Vec<i32>` 这个签名说的是
"我借走整个 `self`，还你一个 `&mut Vec<i32>`"。**签名里没有"我只碰 `self.a`"这个信息**，
而 borrow checker 只看签名。

这正是 lab 的 12 号案例，也是 Polonius Alpha **依然拒绝**的形态——
它需要的是 **view types**（第 17 章），一种能在签名里写"我只访问哪些字段"的语法。

**今天的解法**（第 18 章会系统讲）：

```rust
// 手法 1：返回元组，一次性拆开
impl S {
    fn split(&mut self) -> (&mut Vec<i32>, &mut String) { (&mut self.a, &mut self.b) }
}

// 手法 2：改成自由函数，参数只取需要的字段
fn process(a: &mut Vec<i32>, b: &mut String) { ... }
process(&mut s.a, &mut s.b);

// 手法 3：把相关字段打包成子结构体
struct S { inner: Inner, other: String }
```

### 4.3 ❌ 不能拆的：索引

```rust
let a = &mut v[0];
let b = &mut v[1];         // ❌ E0499
*a += *b;
```

同样的根因：`IndexMut::index_mut(&mut self, i)` 借走整个 `self`。

**解法**：使用签名里就声明了"分割"的 API。

```rust
let (l, r) = v.split_at_mut(1);      // ✅ 签名：(&mut [T], &mut [T])
let [a, b] = v.get_disjoint_mut([0, 1]).unwrap();   // ✅ 1.86+ 稳定的 API
let mut it = v.iter_mut();
let a = it.next().unwrap();
let b = it.next().unwrap();           // ✅ IterMut 内部保证了不相交
```

> **注意**：`slice::get_disjoint_mut`（原名 `get_many_mut`）在 Rust 1.86 稳定。
> 如果你的工具链更老，用 `split_at_mut`。

### 4.4 ✅ 能拆的：切片模式与解构

```rust
let v = &mut [1, 2, 3][..];
if let [a, b, c] = v {      // ✅ 切片模式，编译器知道三个元素不相交
    *a += *b + *c;
}

let (x, y) = &mut tuple;     // ✅ 元组解构
let S { a, b } = s;          // ✅ 结构体解构
```

**解构是"编译器知道不相交"的最强信号**。能用解构就别用字段访问。

---

## 5. `Deref` / `DerefMut` 与自动解引用

### 5.1 自动解引用怎么影响借用

```rust
let s = String::from("hi");
let n = s.len();             // String 没有 len 方法！
```

`str::len` 是 `str` 的方法。编译器做了 **deref coercion**：
`&String` → `&str`（通过 `impl Deref for String { type Target = str }`）。

**对借用检查的影响**：`s.len()` 实际上是 `str::len(&*s)`，
所以它借用的是 `*s`（经过 `Deref::deref(&s)`），链条是 `s → &s → &str`。
**整个 `s` 被共享借用了。**

### 5.2 `DerefMut` 的传染性

```rust
let mut v: Vec<i32> = vec![1, 2, 3];
v.sort();                    // sort 是 [T] 的方法，需要 &mut [T]
                             // → DerefMut → 借走整个 &mut v
```

**推论**：任何通过 `DerefMut` 到达的方法，都会独占借用整个智能指针。

```rust
let b: Box<Vec<i32>> = Box::new(vec![1]);
// 对 b 调用任何 Vec 的 &mut 方法，都会独占借走整个 b
```

### 5.3 一个高频困惑：`RefCell` 为什么"绕过"了规则

```rust
use std::cell::RefCell;
let c = RefCell::new(5);
let a = c.borrow();          // c 只是被 &self 借用（共享）
let b = c.borrow_mut();      // ❌ 编译通过，运行时 panic!
```

**编译器为什么不拦？** 因为 `RefCell::borrow_mut` 的签名是 `fn borrow_mut(&self) -> RefMut<T>`——
**参数是 `&self` 不是 `&mut self`**。从借用检查的角度，这只是两个共享借用，完全合法。

`RefCell` 是把**编译期检查搬到了运行时**：它内部有个计数器，`borrow_mut` 时检查，
冲突就 panic。第 19 章会讲它内部的 `UnsafeCell` 如何合法地做到这件事。

> **判断法则**：看到 `fn xxx(&self) -> 某种可写的东西`，就说明这个类型用了内部可变性，
> **借用检查在这里被有意地转移到运行时了**。

---

## 6. 借用与迭代器

```rust
let mut v = vec![1, 2, 3];

for x in &v      { }        // x: &i32       ── v 被共享借用
for x in &mut v  { }        // x: &mut i32   ── v 被独占借用
for x in v       { }        // x: i32        ── v 被移动消耗

// 等价写法
for x in v.iter()      { }
for x in v.iter_mut()  { }
for x in v.into_iter() { }
```

**迭代期间的借用覆盖整个循环体**，所以：

```rust
for x in &v {
    v.push(*x);             // ❌ E0502：迭代借用还活着
}
```

**标准解法**：

```rust
// 1. 先收集再改
let to_add: Vec<_> = v.iter().map(|x| x * 2).collect();
v.extend(to_add);

// 2. 用索引（放弃借用，接受边界检查开销）
for i in 0..v.len() { v[i] *= 2; }

// 3. retain / drain / iter_mut，用标准库提供的"安全的边迭代边改"API
v.retain(|x| *x > 1);
for x in v.iter_mut() { *x *= 2; }      // ✅ 改元素值可以，改结构不行
```

**关键区分**：
- **改元素的值** → `iter_mut()` 就行
- **改容器的结构**（push/remove/清空） → 必须先结束迭代借用

---

## 7. 动手实验

### 实验 1：重借用 vs 移动

```rust
fn takes(r: &mut i32) { *r += 1; }
fn generic<T: std::fmt::Debug>(t: T) { println!("{:?}", t); }

fn main() {
    let mut x = 5;

    // A：函数参数位置 → 重借用
    let r = &mut x;
    takes(r); takes(r);
    println!("A ok");

    // B：无标注 let → 移动。取消注释看错误
    let r = &mut x;
    let _s = r;
    // *r += 1;                    // ← 取消注释：什么错误码？

    // C：有标注 let → 重借用。取消注释看错误
    let r = &mut x;
    let s: &mut i32 = r;
    // *r += 1;                    // ← 取消注释：什么错误码？（和 B 不同！）
    *s += 1;

    // D：泛型参数位置 → 移动
    let r = &mut x;
    generic(r);
    // *r += 1;                    // ← 取消注释：什么错误码？

    // E：手动重借用救 D
    let r = &mut x;
    generic(&mut *r);
    *r += 1;                       // ✅
    println!("{}", x);
}
```

<details><summary>答案</summary>

**实测输出**（`rustc 1.96.0`）：

```
error[E0382]: use of moved value: `r`                         ← B
error[E0503]: cannot use `*r` because it was mutably borrowed ← C
error[E0382]: use of moved value: `r`                         ← D
```

- B：真的**移动**了
- C：**没有移动**，是 `*r` 正被 `s` 借着 → `E0503`
- D：泛型参数不是强制点，所以移动
- E：显式 `&mut *r` → 通过

> ### 记住这个判据
> **`E0382`（moved）说明发生了移动；`E0503`/`E0502` 说明发生了重借用。**
> 看到 `&mut` 的诡异错误，先看错误码，立刻就知道是哪一类。

</details>

### 实验 2：两阶段借用的边界

```bash
cd lab
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out cases/03-two-phase-borrow.rs   # ✅
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out cases/04-two-phase-limit.rs    # ❌ E0502
```

然后自己试这四种写法，预测结果再验证：

```rust
let mut v = vec![1,2,3];
v.push(v.len());                  // ?
Vec::push(&mut v, v.len());       // ?
(&mut v).push(v.len());           // ?
let n = v.len(); v.push(n);       // ?
```

### 实验 3：借用分割

```rust
struct Server { conns: Vec<String>, log: Vec<String> }

impl Server {
    // 目标：同时可变借用 conns 和 log
    // 试试下面四种写法，哪些能过？
    fn v1(&mut self) { let c = &mut self.conns; let l = &mut self.log; c.push("x".into()); l.push("y".into()); }
    fn conns_mut(&mut self) -> &mut Vec<String> { &mut self.conns }
    fn log_mut(&mut self) -> &mut Vec<String> { &mut self.log }
    fn v2(&mut self) { let c = self.conns_mut(); let l = self.log_mut(); c.push("x".into()); l.push("y".into()); }
    fn v3(&mut self) -> (&mut Vec<String>, &mut Vec<String>) { (&mut self.conns, &mut self.log) }
    fn v4(&mut self) { let (c, l) = self.v3(); c.push("x".into()); l.push("y".into()); }
}
```

<details><summary>答案</summary>

- `v1` ✅：直接字段访问，两个 place 不相交
- `v2` ❌ E0499：两个方法都借走整个 `*self`
- `v3` ✅：一次性借出两个不相交的字段，返回类型里两个 `&mut` 的生命周期都绑到同一个 `&mut self`，
  编译器接受，因为它们来自**同一次**借用的**不同 place**
- `v4` ✅：用 `v3` 就能解决 `v2` 的问题——**这就是第 18 章的"splitter 方法"手法**

</details>

---

## 8. 本章检查清单

- [ ] 知道 borrow check 的粒度是 **place**，且两个 place 冲突的判定是"前缀或相等"
- [ ] 知道 `v[i]` 借的是整个 `v`
- [ ] **能解释重借用，并说出哪些位置自动重借用、哪些是移动**
- [ ] 能用错误码（E0382 vs E0502）区分"移动了"和"被冻结了"
- [ ] 知道两阶段借用只对 autoref 生效
- [ ] 能列出四种"能拆"和三种"不能拆"的借用分割场景
- [ ] 知道 `DerefMut` 会独占借走整个智能指针
- [ ] 知道 `RefCell` 不是"绕过"检查，而是签名用了 `&self` + 运行时计数

---

## 9. 常见坑

| 现象 | 错误码 | 根因 | 处方 |
|---|---|---|---|
| `let s = r;` 之后 `r` 不能用 | E0382 | 无标注 let 是移动不是重借用 | 加类型标注，或写 `&mut *r` |
| `let s: &mut T = r;` 之后 `r` 不能用 | **E0503** | 重借用期间 `*r` 被 `s` 借着 | 等 `s` 用完；或缩小 `s` 的作用域 |
| `generic(r)` 之后 `r` 不能用 | E0382 | 泛型参数不是强制点 | 写 `generic(&mut *r)` |
| `Vec::push(&mut v, v.len())` | E0502 | 显式 `&mut` 不享受两阶段 | 写成方法调用 `v.push(v.len())` |
| 两个 getter 方法同时用 | E0499 | 每个都借走整个 `self` | splitter 方法返回元组；或直接访问字段；或拆自由函数 |
| `&mut v[0]` 和 `&mut v[1]` | E0499 | `IndexMut` 借走整个 `v` | `split_at_mut` / `get_disjoint_mut` / `iter_mut` |
| 循环里改容器 | E0502 | 迭代借用覆盖整个循环体 | 先 collect；或用索引；或 `retain`/`drain` |
| `RefCell` 运行时 panic | 无（`already borrowed`） | 编译期检查被搬到了运行时 | 缩小 `borrow()` 的作用域；或重新设计 |
| 方法调用后整个结构体被借走 | E0502/E0499 | `&mut self` 的粒度就是整个 self | 见第 12/18 章 |

---

下一章：[06 - 生命周期不是"活多久"](06-lifetimes.md)——**本课程的分水岭**。
