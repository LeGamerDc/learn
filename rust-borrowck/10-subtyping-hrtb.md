# 10 - 高阶生命周期（HRTB）与闭包推断

> 本章目标：搞懂 `for<'a>` 到底在说什么，以及为什么闭包的生命周期推断
> 是 Rust 里最容易卡住新手的地方之一。这一章解决"闭包里的引用怎么标注都不对"那类问题。
> 预计用时：2.5 小时。

---

## 1. 问题：有些约束无法用普通生命周期参数表达

先看一个具体需求：写一个函数，它接受一个闭包，这个闭包能处理**任意生命周期**的引用。

```rust
fn apply<F>(f: F)
where F: Fn(&str) -> usize     // ← 这里的 &str 是什么生命周期？
{
    let s1 = String::from("hello");
    f(&s1);                     // 传一个短命的
    f("static literal");        // 传一个 'static 的
}
```

**尝试用普通泛型参数**：

```rust
fn apply<'a, F>(f: F) where F: Fn(&'a str) -> usize { ... }
```

**这是错的**。因为 `'a` 是**调用方**在调用 `apply` 时确定的**一个具体值**，
而函数体里需要用**两个不同的**生命周期去调用 `f`。

我们需要表达的是：

> **"对于任意的 `'a`，`F` 都实现了 `Fn(&'a str) -> usize`。"**

这就是 **HRTB（Higher-Ranked Trait Bound，高阶 trait 约束）**：

```rust
fn apply<F>(f: F) where F: for<'a> Fn(&'a str) -> usize { ... }
```

`for<'a>` 读作"**对于所有的 `'a`**"，是一个**全称量词**。

---

## 2. 量词的位置决定一切

这是本章的核心。**同一个生命周期变量，写在不同位置，含义完全不同**：

```rust
// A：'a 由调用方选定（一个具体的生命周期）
fn a<'a, F: Fn(&'a str)>(f: F, s: &'a str) { f(s); }

// B：'a 对每次调用 f 都可以不同（全称量词在 F 上）
fn b<F: for<'a> Fn(&'a str)>(f: F) { f("x"); let s = String::new(); f(&s); }
```

用逻辑记号：

```
A:   ∃'a. ( F: Fn(&'a str) )       ← 存在一个 'a，调用方挑
B:   ∀'a. ( F: Fn(&'a str) )       ← 对所有 'a 都成立
```

**B 比 A 强**：满足 B 的闭包一定满足 A，反之不然。

### 2.1 类型层面的写法

`for<'a>` 也能写在类型上，产生**高阶函数指针类型**：

```rust
let f: for<'a> fn(&'a str) -> &'a str = |s| s;
let g: fn(&'static str) -> &'static str = f;      // ✅ 高阶的可以特化成具体的
// let h: for<'a> fn(&'a str) -> &'a str = g;     // ❌ 反过来不行
```

这和第 09 章的子类型是一致的：**`for<'a> fn(&'a T)` 是所有 `fn(&'x T)` 的子类型**
（更通用 = 更"子"）。

---

## 3. 你其实一直在用 HRTB（只是被省略了）

**`Fn`/`FnMut`/`FnOnce` 约束里的省略生命周期，默认就是高阶的。**

```rust
F: Fn(&str) -> usize
// 自动展开成
F: for<'a> Fn(&'a str) -> usize
```

**这是一条特殊的省略规则**，只对 `Fn` 系列 trait 的括号语法（parenthesized sugar）生效。
写成尖括号形式就没有这个待遇：

```rust
F: Fn<(&str,), Output = usize>       // 不稳定语法，且不自动高阶
```

**推论**：绝大部分时候你不需要手写 `for<'a>`——**除非你需要给那个生命周期起名字**。

什么时候需要起名字？

```rust
// 需要在返回类型里引用它
fn find<F>(f: F) where F: for<'a> Fn(&'a str) -> &'a str { }

// 需要加额外的约束
fn g<F, T>(f: F) where for<'a> F: Fn(&'a T) -> &'a T, T: 'static { }

// where 从句里的高阶约束
fn h<T>(x: T) where for<'a> &'a T: IntoIterator { }
```

---

## 4. 实战：`thread::scope` 的签名

第 06 章说过 scoped thread"用 HRTB 在类型层面证明了线程不会活过 scope"。现在能读懂了：

```rust
pub fn scope<'env, F, T>(f: F) -> T
where
    F: for<'scope> FnOnce(&'scope Scope<'scope, 'env>) -> T,
{ ... }
```

**逐段读**：

| 部分 | 含义 |
|---|---|
| `'env` | 外部环境的生命周期——被借用的数据活多久 |
| `for<'scope>` | ★ **`'scope` 由 `scope` 函数自己选，调用方无法指定** |
| `&'scope Scope<'scope, 'env>` | 传给闭包的 handle，它的生命周期就是 `'scope` |

**关键在 `for<'scope>`**：因为调用方不能选 `'scope`，所以闭包**没办法**把
`&'scope Scope` 存到外面去（它不知道 `'scope` 到底多长，只能假设最坏情况）。

于是：`s.spawn(...)` 产生的 `ScopedJoinHandle<'scope, T>` 也被困在 `'scope` 里，
而 `scope` 函数在返回前会 join 所有未 join 的线程。**编译器因此可以放心地允许借用**：

```rust
let v = vec![1, 2, 3];
std::thread::scope(|s| {
    s.spawn(|| println!("{:?}", v));       // ✅ 借用 v，不需要 'static
});
println!("{:?}", v);                        // ✅ 还能用
```

> ### 这是 HRTB 最漂亮的应用
> **用"调用方无法命名这个生命周期"来强制封闭一个作用域。**
> 同样的模式还出现在：`GhostCell`、`generativity` crate、
> `rayon::scope`、`crossbeam::scope`、以及 `qcell` 的品牌化（branded）类型。
>
> 术语叫 **invariant lifetime branding**（不变生命周期品牌化）——
> 因为 `Scope<'scope, 'env>` 对 `'scope` 是**不变的**（第 09 章），
> 所以两个不同的 scope 产生的 handle 类型互不兼容。

---

## 5. 闭包生命周期推断的三个经典坑

这是本章最实用的部分。**闭包的生命周期推断规则和函数不一样**，而且不太直观。

### 5.1 坑一：闭包返回引用时推断失败

```rust
let f = |s: &str| s;                 // ❌ 报错
```

**实测报错**：

```
error: lifetime may not live long enough
 --> src/main.rs
  |
  |     let f = |s: &str| s;
  |              -      - ^ returning this value requires that `'1` must outlive `'2`
  |              |      |
  |              |      return type of closure is &'2 str
  |              let's call the lifetime of this reference `'1`
```

**原因**：闭包的参数类型一旦被**显式标注**（`s: &str`），
编译器就为参数和返回值各自分配**独立的**生命周期变量，且**不自动建立联系**。
函数有省略规则（第 06 章规则 2）会自动把它们绑在一起，**闭包没有**。

**三种修法**：

```rust
// 1. 不标注类型，让编译器完全推断（最常用）
let f = |s| s;
let n = f("hello");                  // 推断出来了

// 2. 用函数而不是闭包
fn f(s: &str) -> &str { s }

// 3. 借助一个 helper 强制高阶签名
fn hrtb<F: for<'a> Fn(&'a str) -> &'a str>(f: F) -> F { f }
let f = hrtb(|s: &str| s);           // ✅
```

**第 3 种手法叫 "closure lifetime binder helper"**，在库代码里很常见。
Rust 也在推进直接标注的语法（`for<'a> |s: &'a str| -> &'a str { s }`，
不稳定特性 `closure_lifetime_binder`），但目前还没稳定。

### 5.2 坑二：闭包捕获的引用没法"高阶"

```rust
fn make_finder(data: &Vec<String>) -> impl Fn(&str) -> bool + '_ {
    move |needle| data.iter().any(|s| s == needle)
}
```

注意返回类型里的 `+ '_`——它说的是"这个闭包捕获了一个借用，
所以它不能活过那个借用"。**忘了写就报 E0700 / E0106。**

> **规律**：闭包捕获的东西的生命周期，会**出现在闭包的类型里**。
> `impl Fn(...)` 默认**不捕获任何生命周期**，需要显式写 `+ 'a` 或 `+ '_`。
>
> ⚠️ **2024 edition 改了这条规则**：RPIT（`-> impl Trait`）现在**默认捕获所有**
> 在作用域内的生命周期参数。所以上面的 `+ '_` 在 2024 edition 里可以省略。
> 想**排除**某个生命周期要用 `impl Fn(&str) -> bool + use<>`（精确捕获语法）。

### 5.3 坑三：`FnMut` 闭包和借用的交互

```rust
let mut v = vec![1, 2, 3];
let mut push = || v.push(4);        // 闭包独占借用 v（因为要改它）
// println!("{:?}", v);             // ❌ E0502：v 被闭包借着
push();
println!("{:?}", v);                // ✅ 闭包不再使用
```

**闭包的捕获就是一次借用**，它的活跃期从闭包创建开始，到**闭包最后一次被调用**为止。

**RFC 2229（2021 edition 起）的改进**：闭包按**字段粒度**捕获。

```rust
struct S { a: String, b: String }
fn f(s: &mut S) {
    let mut c = || s.a.push('x');   // 2021+：只捕获 s.a
    c();
    s.b.push('y');                  // ✅ 2021+ 通过；2018 edition 会报错
}
```

lab 的 17 号案例验证了这一点。**注意这是 edition 相关的行为**。

---

## 6. late-bound vs early-bound（进阶）

这个区分解释了几个诡异现象，值得知道。

**函数签名里的生命周期参数分两类**：

| | early-bound（早绑定） | late-bound（晚绑定） |
|---|---|---|
| 何时确定 | **函数被引用/单态化时** | **函数被调用时** |
| 出现在 | 有 `where 'a: 'b` 这类约束时；或用在关联类型里 | 只出现在参数类型里，无额外约束 |
| 能否 turbofish | ✅ `f::<'a>` | ❌ |
| 函数指针类型 | `fn(&'a str)`（具体） | `for<'a> fn(&'a str)`（高阶） |

```rust
fn late<'a>(x: &'a str) -> &'a str { x }         // late-bound
fn early<'a: 'a>(x: &'a str) -> &'a str { x }    // ★ 加个平凡约束就变成 early-bound

fn main() {
    let f: for<'x> fn(&'x str) -> &'x str = late;    // ✅ 高阶
    // let g: for<'x> fn(&'x str) -> &'x str = early; // ❌ early-bound 不是高阶的
    let g: fn(&'static str) -> &'static str = early;  // ✅ 只能特化
}
```

> **`<'a: 'a>` 这个看起来完全没用的约束，是把 late-bound 强制变成 early-bound 的标准技巧。**
> 你在标准库和一些库代码里会看到它。

**这解释了什么**：
- 为什么有时候把函数当值传给别人会报生命周期错误 → 它是 early-bound 的
- 为什么 `f::<'a>(x)` 有时候报"不能指定生命周期参数" → 它是 late-bound 的

---

## 7. HRTB 的已知限制

HRTB 是类型系统里比较薄弱的一块，有几个已知的坑：

### 7.1 `for<'a>` 里不能有 outlives 约束

```rust
fn f<F>(x: F) where for<'a> F: Fn(&'a str), for<'a> 'a: 'static { }   // ❌ 语法不支持
```

这类需求目前无解，通常要重新设计 API。

### 7.2 关联类型上的 HRTB 很难写

```rust
// 想说"对任意 'a，&'a T 能迭代出 &'a U"
fn f<T, U>(t: T)
where
    for<'a> &'a T: IntoIterator<Item = &'a U>,      // ✅ 可以写
{ }
```

这个可以写，但一旦加上更多层就会遇到编译器的限制（著名的
"implementation of `Trait` is not general enough" 错误）。

### 7.3 常见错误：`implementation of X is not general enough`

```
error: implementation of `Fn` is not general enough
```

**几乎总是意味着**：你提供的闭包/类型只对**某些**生命周期成立，但被要求对**所有**成立。

**排查清单**：
1. 闭包参数是不是显式标注了类型？→ 去掉标注试试
2. 闭包是不是捕获了带生命周期的东西？→ 那它就不可能是高阶的
3. 是不是在 async 上下文里？→ async 块的生命周期捕获更复杂，见第 24 章
4. 试试用 helper 函数强制签名（第 5.1 节手法 3）

---

## 8. 动手实验

### 实验 1：量词位置

```rust
// 判断这三个哪些能编译，哪些不能，为什么
fn a<'x, F: Fn(&'x str) -> usize>(f: F) {
    let s = String::from("local");
    f(&s);
}

fn b<F: for<'x> Fn(&'x str) -> usize>(f: F) {
    let s = String::from("local");
    f(&s);
    f("static");
}

fn c<F: Fn(&str) -> usize>(f: F) {
    let s = String::from("local");
    f(&s);
    f("static");
}
```

<details><summary>答案</summary>

- `a` ❌：`'x` 由调用方选定，函数体里传一个局部变量的引用，无法保证它满足 `'x`
- `b` ✅：显式高阶
- `c` ✅：`Fn(&str)` 的省略生命周期**自动是高阶的**，等价于 `b`

**结论：`c` 才是你 99% 情况下该写的形式。**

</details>

### 实验 2：闭包返回引用

```rust
fn main() {
    let f1 = |s: &str| s;                     // ?
    let f2 = |s| s;
    let _: &str = f2("x");                    // ?
    fn hrtb<F: for<'a> Fn(&'a str) -> &'a str>(f: F) -> F { f }
    let f3 = hrtb(|s: &str| s);               // ?
    println!("{}", f3("hello"));
}
```

编译，观察 `f1` 的完整错误信息。然后把 `f1` 的 `: &str` 去掉再试。

### 实验 3：late-bound vs early-bound

```rust
fn late<'a>(x: &'a str) -> &'a str { x }
fn early<'a: 'a>(x: &'a str) -> &'a str { x }

fn main() {
    let f: for<'x> fn(&'x str) -> &'x str = late;      // ?
    let g: for<'x> fn(&'x str) -> &'x str = early;     // ?
}
```

<details><summary>答案（实测 rustc 1.96.0）</summary>

- `late` → ✅
- `early` → ❌ **`error[E0308]: mismatched types`**（期望 `for<'x> fn(...)`，得到 `fn(&'a str) -> &'a str`）

一个**看起来完全无意义的 `<'a: 'a>` 约束**，改变了函数值的类型。

</details>

### 实验 4：scoped thread 的类型级证明

```rust
use std::thread;

fn main() {
    let v = vec![1, 2, 3];
    let mut escaped = None;
    thread::scope(|s| {
        s.spawn(|| println!("{:?}", v));
        // escaped = Some(s);        // ← 取消注释，看编译器怎么拦住你
    });
    println!("{:?}", v);
}
```

**任务**：解释错误信息里为什么会出现"lifetime may not live long enough"以及
它和 `for<'scope>` 的关系。

---

## 9. 本章检查清单

- [ ] 能说出 `for<'a>` 是全称量词，且知道量词位置决定含义
- [ ] 知道 `F: Fn(&str)` 的省略生命周期**自动是高阶的**
- [ ] 能读懂 `thread::scope` 的签名，解释 `for<'scope>` 起的作用
- [ ] 知道闭包**不享受**函数的生命周期省略规则（坑一）
- [ ] 知道 `impl Fn` 的生命周期捕获规则，及 2024 edition 的变更
- [ ] 知道 RFC 2229（2021+）让闭包按字段粒度捕获
- [ ] 能区分 late-bound 和 early-bound，知道 `<'a: 'a>` 这个技巧
- [ ] 看到 "implementation of X is not general enough" 知道该查什么

---

## 10. 常见坑

| 现象 | 根因 | 处方 |
|---|---|---|
| `let f = \|s: &str\| s;` 报错 | 闭包没有省略规则 | 去掉类型标注；或用 helper 函数 |
| "implementation of `Fn` is not general enough" | 闭包只对某些生命周期成立 | 去掉参数类型标注；检查闭包是否捕获了带生命周期的东西 |
| `impl Fn(...)` 返回值报生命周期错 | 捕获了借用但没在返回类型里声明 | 2021-：加 `+ '_`；2024+：默认已捕获，反而可能需要 `+ use<>` 排除 |
| 把函数当值传报生命周期错 | 它是 early-bound 的 | 检查签名里有没有 `where 'a: 'b` 这类约束 |
| `f::<'a>(x)` 报"不能指定生命周期" | 它是 late-bound 的 | 加平凡约束 `<'a: 'a>` 变成 early-bound |
| 闭包借了变量之后外面不能用 | 捕获就是借用，活到闭包最后一次调用 | 缩小闭包的作用域；或用 `move` + clone |
| 闭包捕获了整个结构体 | edition 2018 的行为 | 升级到 2021+（RFC 2229 按字段捕获） |
| HRTB 里想加 outlives 约束 | 语法不支持 | 重新设计 API |

---

**阶段 1 到此结束。** 你现在掌握了借用检查的全部核心机制。
接下来的第 11–14 章是**大量的实战案例**——把这些机制放到真实场景里，看它们怎么互相绊倒。

下一章：[11 - 反直觉合集](11-counterintuitive.md)
