# 09 - 型变（variance）：为什么有些替换合法有些不合法

> 本章目标：搞懂 Rust 里**唯一的子类型关系**（生命周期）如何在泛型容器里传播。
> 这是"我明明有个更长的生命周期，为什么不能用在需要更短的地方"这类问题的答案。
> 也是 `PhantomData` 和 `Cell` 那些奇怪限制的根源。
> 预计用时：2 小时。

---

## 1. Rust 里的子类型只有一种

**Rust 没有面向对象意义上的子类型。** `struct Dog` 不是 `struct Animal` 的子类型。
`impl Trait for T` 也不产生子类型关系。

**Rust 里唯一的子类型关系是生命周期之间的**：

> 如果 `'long` 包含 `'short`（即 `'long: 'short`），
> 那么 **`&'long T` 是 `&'short T` 的子类型**。

直觉：一个"活得更久的引用"可以用在"只需要活一小会儿的引用"的位置。
就像一个能开 10 年的合同可以拿去满足只需 1 年的要求。

```rust
fn takes_short<'s>(x: &'s str) {}

let long: &'static str = "hello";
takes_short(long);          // ✅ &'static str <: &'s str
```

**记号**：`A <: B` 读作 "A 是 B 的子类型"，意思是 **A 可以用在需要 B 的地方**。

```
'static <: 'a <: 'b        当 'static: 'a: 'b
&'static str <: &'a str
```

> ⚠️ **一个持续困扰人的方向问题**：
> **生命周期越长，类型越"小"（越靠近子类型）。**
> 这和"数量多的是超集"的直觉相反，因为子类型的方向是**可替换性**，不是集合大小。
>
> 记忆法：`'static` 是**最强的**引用，所以它是所有引用类型的**子类型**（最强 = 最特殊 = 子类型）。

---

## 2. 型变：子类型关系如何穿过泛型

现在问题来了：已知 `&'static str <: &'a str`，那么：

- `Vec<&'static str>` 和 `Vec<&'a str>` 是什么关系？
- `&mut Vec<&'static str>` 和 `&mut Vec<&'a str>` 呢？
- `Cell<&'static str>` 呢？
- `fn(&'static str)` 呢？

**型变（variance）就是回答"泛型参数的子类型关系如何传递给整体"的规则。**

三种可能：

| 型变 | 定义 | 记号 | 直觉 |
|---|---|---|---|
| **协变（covariant）** | `A <: B` ⟹ `F<A> <: F<B>` | `+` | 顺着传 |
| **逆变（contravariant）** | `A <: B` ⟹ `F<B> <: F<A>` | `-` | 反着传 |
| **不变（invariant）** | 没有任何关系 | `o` | 断了 |

---

## 3. 完整型变表（附实测验证）

| 类型 | 对 `'a` | 对 `T` | 对 `U` |
|---|---|---|---|
| `&'a T` | 协变 | **协变** | — |
| `&'a mut T` | 协变 | **不变** ★ | — |
| `*const T` | — | 协变 | — |
| `*mut T` | — | **不变** | — |
| `Box<T>` / `Vec<T>` / `[T; N]` / `Option<T>` | — | 协变 | — |
| `Cell<T>` / `RefCell<T>` / `UnsafeCell<T>` | — | **不变** ★ | — |
| `Mutex<T>` / `RwLock<T>` / `AtomicPtr<T>` | — | **不变** | — |
| `fn(T) -> U` | — | **逆变** ★ | 协变 |
| `PhantomData<T>` | — | 协变 | — |
| `dyn Trait + 'a` | 协变 | — | — |

**实测验证**（`rustc 1.96.0`，✅ = 编译通过，❌ = `error: lifetime may not live long enough`）：

```rust
use std::cell::{Cell, UnsafeCell};

pub fn a<'a>(x: &'static str) -> &'a str { x }                              // ✅ &'a T 对 'a 协变
pub fn b<'a>(x: &'a &'static str) -> &'a &'a str { x }                      // ✅ & 对 T 协变
pub fn c<'a>(x: &'static mut i32) -> &'a mut i32 { x }                      // ✅ &mut 对 'a 协变
pub fn d<'a,'b>(x: &'b mut Vec<&'static str>) -> &'b mut Vec<&'a str> { x } // ❌ &mut 对 T 不变
pub fn e<'a>(x: Vec<&'static str>) -> Vec<&'a str> { x }                    // ✅ Vec 对 T 协变
pub fn f<'a>(x: Box<&'static str>) -> Box<&'a str> { x }                    // ✅ Box 对 T 协变
pub fn g<'a>(x: Cell<&'static str>) -> Cell<&'a str> { x }                  // ❌ Cell 对 T 不变
pub fn h<'a>(x: UnsafeCell<&'static str>) -> UnsafeCell<&'a str> { x }      // ❌ UnsafeCell 不变
pub fn i<'a>(f: fn(&'a str)) -> fn(&'static str) { f }                      // ✅ fn 参数逆变
pub fn j<'a>(f: fn()->&'static str) -> fn()->&'a str { f }                  // ✅ fn 返回值协变
```

---

## 4. 逐个讲清楚"为什么"

### 4.1 `&'a T` 对 `T` 协变——安全，因为只读

```rust
fn shrink<'o, 'a>(r: &'o &'static str) -> &'o &'a str {
    r                              // ✅ 长的可以当短的用
}

// 反方向不行：
// fn grow<'o, 'a>(r: &'o &'a str) -> &'o &'static str { r }
//   error: lifetime may not live long enough
```

（这里两个生命周期都得手写：`&&'static str` 里有两个生命周期位置，
省略规则 2 只在**恰好一个**输入生命周期时才生效，否则报 E0106。）

通过 `r2` 只能**读**出一个 `&'a str`。而实际存的是 `&'static str`，
它满足 `&'a str` 的所有要求（活得更久没关系）。**读取不会破坏任何东西。**

### 4.2 `&'a mut T` 对 `T` 不变——★ 本章最重要的一条

**为什么不能协变？** 反证法：

```rust
fn evil<'a>(dst: &mut Vec<&'a str>, src: &'a str) {
    dst.push(src);
}

fn main() {
    let mut v: Vec<&'static str> = vec!["static"];
    {
        let local = String::from("temporary");
        // 假设 &mut Vec<&'static str> 可以当作 &mut Vec<&'a str> 用（协变）：
        evil(&mut v, &local);        // 往 v 里塞了一个只活到块末尾的引用！
    }                                // local 死了
    println!("{}", v[1]);            // 💥 use-after-free
}
```

**`&mut` 既能读也能写。**
- 读的方向要求**协变**（读出来的东西要能当短命的用）
- 写的方向要求**逆变**（写进去的东西必须满足长命的要求）
- 两者同时要求 → **只能不变**

> ### 一句话记忆
> **只读 → 协变；只写 → 逆变；可读可写 → 不变。**
>
> 这一条能推出表里所有的型变，包括 `Cell`（可读可写 → 不变）、
> `fn(T)`（只"写"参数 → 逆变）、`fn() -> T`（只"读"返回值 → 协变）。

### 4.3 `Cell<T>` / `UnsafeCell<T>` 对 `T` 不变——同样的理由

`Cell<T>` 提供 `get()` 和 `set()`，通过 `&self` 就能写。
所以哪怕你只有 `&Cell<T>`，也能写——因此必须不变。

```rust
let c: Cell<&'static str> = Cell::new("static");
let r: &Cell<&'a str> = &c;          // ❌ 如果允许……
r.set(&local_string);                //    就能把短命引用塞进去
// c.get() 之后就是悬垂的
```

**`UnsafeCell<T>` 的不变性是所有内部可变性类型不变性的根源**——
`Cell`/`RefCell`/`Mutex`/`RwLock` 都包着 `UnsafeCell`，因此都继承了不变性。

### 4.4 `fn(T)` 对 `T` 逆变——最反直觉的一条

```rust
fn takes_any_lifetime<'a>(f: fn(&'a str)) -> fn(&'static str) { f }   // ✅
```

**为什么？** 想想"什么函数可以用在需要 `fn(&'static str)` 的地方"：

调用方会传一个 `&'static str` 进去。所以被调函数只要能接受 `&'static str` 就行。
一个接受 `&'a str`（任意短命引用）的函数**更通用**，当然也能接受 `&'static str`。

> **一般规律**：参数要求**越宽松**的函数，越"通用"，越是子类型。
> 这和面向对象里的"里氏替换原则"（参数逆变、返回值协变）完全一致。

### 4.5 `Box<T>` / `Vec<T>` 协变——因为它们拥有数据

`Vec<&'static str>` 变成 `Vec<&'a str>` 之后，你可以往里 push `&'a str`。
但**这是一个新的、被移动过的 Vec**——原来那个已经不能用了（移动语义）。
所以不会有人从"原来那个 `Vec<&'static str>`"里读到短命引用。

**关键**：协变的前提是**所有权转移**。而 `&mut` 是**借用**，原所有者还在，所以不行。

---

## 5. 实战：型变咬人的三个场景

### 5.1 场景一：`&mut` 参数的隐藏刚性

```rust
struct Registry<'a> { items: Vec<&'a str> }

fn add_static(r: &mut Registry<'static>) { r.items.push("x"); }

fn main() {
    let mut r: Registry<'static> = Registry { items: vec![] };
    add_static(&mut r);                     // ✅

    let s = String::from("local");
    let mut r2: Registry = Registry { items: vec![&s] };
    // add_static(&mut r2);                 // ❌ Registry<'a> ≠ Registry<'static>
}
```

**诊断法**：报错说 "lifetime may not live long enough" 且涉及 `&mut` 时，
**先检查是不是型变问题**——把 `&mut X<'a>` 换成 `X<'a>`（按值）试试，如果能过就是型变。

### 5.2 场景二：`RefCell` 让结构体变得不变

```rust
struct Cache<'a> { data: RefCell<Vec<&'a str>> }
```

一旦字段里有 `RefCell`/`Cell`/`Mutex`，**整个结构体对 `'a` 就变成不变的**。
这意味着 `Cache<'static>` 不能用在需要 `Cache<'a>` 的地方。

**这是"为什么加了 `RefCell` 之后生命周期突然到处报错"的真实原因**，
很多人以为是 `RefCell` 本身的问题，其实是型变塌了。

### 5.3 场景三：`PhantomData` 与型变控制

写 `unsafe` 抽象时（第 26 章），你的结构体里可能只有裸指针：

```rust
struct MyVec<T> {
    ptr: *mut T,
    len: usize,
    cap: usize,
}
```

`*mut T` 对 `T` **不变**，但 `MyVec<T>` 语义上是**拥有** `T` 的，应该协变。
而且编译器不知道 `MyVec<T>` drop 时会 drop 里面的 `T`（dropck，第 04 章）。

**解法**：

```rust
use std::marker::PhantomData;

struct MyVec<T> {
    ptr: *mut T,
    len: usize,
    cap: usize,
    _marker: PhantomData<T>,     // ★ 告诉编译器：我拥有 T
}
```

`PhantomData<T>` 是零大小的，它唯一的作用就是**向编译器声明型变和 drop 关系**：

| 写法 | 型变（对 T） | dropck | 语义 |
|---|---|---|---|
| `PhantomData<T>` | 协变 | **拥有 T** | 我拥有一个 T |
| `PhantomData<&'a T>` | 协变 | 不拥有 | 我借用了一个 T |
| `PhantomData<&'a mut T>` | 对 T 不变 | 不拥有 | 我独占借用了 T |
| `PhantomData<*const T>` | 协变 | 不拥有 | 我有个只读裸指针 |
| `PhantomData<*mut T>` | **不变** | 不拥有 | 我有个可写裸指针 |
| `PhantomData<fn(T)>` | **逆变** | 不拥有 | 用来强制逆变 |
| `PhantomData<fn() -> T>` | 协变 | 不拥有 | 用来强制协变而不声明所有权 |
| `PhantomData<Cell<T>>` | **不变** | 不拥有 | 用来强制不变 |

> **`PhantomData` 是 Rust 里最纯粹的"类型即证明"的例子**——
> 一个占 0 字节、生成 0 条指令的东西，唯一的作用是给类型系统提供信息。

---

## 6. 怎么查一个类型的型变

**方法 1：推导规则**（结构化）

> 一个 struct/enum 对参数 `X` 的型变 = 它**所有字段**对 `X` 的型变的**"最小公倍数"**：
> - 全部协变 → 协变
> - 全部逆变 → 逆变
> - 混合，或有任何一个不变 → **不变**

**方法 2：用编译器问**（最可靠）

```rust
fn assert_covariant<'a, 'b: 'a>(x: MyType<'b>) -> MyType<'a> { x }
```

编译过 → 协变。报 `lifetime may not live long enough` → 不是协变。

**方法 3：查文档**——标准库类型的型变在 [Rustonomicon 的 Subtyping 章节](https://doc.rust-lang.org/nomicon/subtyping.html)有完整表。

---

## 7. 动手实验

### 实验 1：验证型变表

把第 3 节的 10 个函数原样敲进一个 `.rs`，编译，确认只有 `d`/`g`/`h` 三个失败。
然后逐个修改，比如把 `d` 的 `&'b mut Vec<...>` 改成 `Vec<...>`（按值），看是否通过。

### 实验 2：亲手制造 use-after-free（思想实验）

第 4.2 节的 `evil` 函数如果型变是协变的会怎样？
**在纸上**推演一遍，明确指出哪一行会读到已释放的内存。
（不要真的用 `unsafe` 去实现它——虽然那是个很好的 Miri 练习，第 26 章会做。）

### 实验 3：`PhantomData` 的型变控制

```rust
use std::marker::PhantomData;

struct A<T>(*mut T);
struct B<T>(*mut T, PhantomData<T>);
struct C<T>(*mut T, PhantomData<fn(T)>);

fn cov_a<'a>(x: A<&'static str>) -> A<&'a str> { x }     // ?
fn cov_b<'a>(x: B<&'static str>) -> B<&'a str> { x }     // ?
fn cov_c<'a>(x: C<&'static str>) -> C<&'a str> { x }     // ?
```

预测每个的结果，再编译验证。

<details><summary>提示</summary>

`A` 只有 `*mut T` → 不变 → ❌
`B` 有 `PhantomData<T>`（协变）+ `*mut T`（不变）→ **混合有不变 → 不变** → ❌
`C` 有 `PhantomData<fn(T)>`（逆变）+ `*mut T`（不变）→ 不变 → ❌

想让它协变，`*mut T` 得换成 `*const T` 或 `NonNull<T>`（`NonNull` 是协变的）。
**这就是为什么标准库里的 `Vec` 用 `NonNull<T>` 而不是 `*mut T`。**

</details>

---

## 8. 本章检查清单

- [ ] 知道 Rust 里唯一的子类型关系是生命周期，且**生命周期越长类型越"子"**
- [ ] 能说出协变/逆变/不变的定义
- [ ] 能背出核心型变表，尤其是 `&mut T` 对 `T` **不变**
- [ ] **能用"只读→协变，只写→逆变，可读可写→不变"推出整张表**
- [ ] 能用反证法解释为什么 `&mut T` 对 `T` 协变会导致 use-after-free
- [ ] 知道所有内部可变性类型的不变性都来自 `UnsafeCell`
- [ ] 知道结构体的型变 = 所有字段型变的"取最严"
- [ ] 知道 `PhantomData` 的七种常用写法及各自的型变/dropck 含义
- [ ] 会用 `fn assert_covariant<'a, 'b: 'a>(x: T<'b>) -> T<'a> { x }` 探测型变

---

## 9. 常见坑

| 现象 | 根因 | 处方 |
|---|---|---|
| `&mut X<'static>` 传不进要 `&mut X<'a>` 的地方 | `&mut` 对 T 不变 | 改成按值传；或让函数泛型化 `fn f<'a>(x: &mut X<'a>)` |
| 加了 `RefCell` 之后生命周期到处报错 | 内部可变性 → 不变 | 考虑把 `'a` 换成拥有的数据；或整体泛型化 |
| 自己写的 `unsafe` 容器不能协变 | 用了 `*mut T` | 换 `NonNull<T>` + `PhantomData<T>` |
| 自己写的容器 dropck 报错 | 少了 `PhantomData<T>` | 加上，声明所有权 |
| "lifetime may not live long enough" 但看不出哪里 | 常常是型变 | 用 `assert_covariant` 探测；或把 `&mut` 改成按值试试 |
| 以为 `impl Trait for A` 让 A 成为 Trait 的子类型 | Rust 没有这种子类型 | trait object 用 `dyn Trait`，是 unsize coercion 不是子类型 |

---

下一章：[10 - 子类型与 HRTB](10-subtyping-hrtb.md)——`for<'a>` 到底在说什么。
