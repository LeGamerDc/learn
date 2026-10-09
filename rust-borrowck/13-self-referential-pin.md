# 13 - 自引用结构与 `Pin`

> 本章目标：搞清楚"为什么 Rust 写不出双向链表"这个经典问题的**真正**答案，
> 以及 `Pin` 到底解决了什么、没解决什么。
> 这一章是理解 async（第 24 章）的前置——`Future` 就是一个自引用结构。
> 预计用时：2.5 小时。

---

## 1. 问题的根源：移动会让引用失效

```rust
struct SelfRef {
    data: String,
    view: *const str,     // 指向 data 内部
}
```

假设我们构造了这样一个值，`view` 指向 `data` 的堆缓冲区。然后：

```rust
let a = make_self_ref();
let b = a;                // 移动！
```

**移动 = memcpy**（第 04 章）。`b` 是 `a` 的按位副本，**`b.view` 仍然指向 `a` 原来的位置**。
如果 `view` 指向的是 `data` 的**堆缓冲区**，那没问题（堆地址没变）；
但如果指向的是**栈上的字段本身**，`b.view` 就悬垂了。

> ### 核心冲突
> **Rust 的移动是"编译器可以随便 memcpy"**（没有 C++ 的移动构造函数钩子）。
> 而自引用结构要求"我知道自己在哪"。**两者天然矛盾。**
>
> 这也解释了为什么 C++ 能写自引用（移动构造函数里可以 fixup 指针），Rust 不行。

---

## 2. 实测：你能走到哪一步

用安全 Rust 试试，实测结果很有教育意义：

```rust
pub struct B<'a> { data: String, view: Option<&'a str> }

// 1. 构造时就自引用
pub fn a1() {
    let d = String::from("hello");
    let _s = B { view: Some(&d), data: d };     // ❌ E0505: cannot move out of `d` because it is borrowed
}

// 2. 构造后再自引用 —— ✅ 居然可以！
pub fn ok() {
    let mut b = B { data: "hi".into(), view: None };
    b.view = Some(&b.data);                      // ✅
    println!("{:?}", b.view);                    // ✅
}

// 3. 但不能移动它
pub fn mv() {
    let mut b = B { data: "hi".into(), view: None };
    b.view = Some(&b.data);
    let _c = b;                                  // ❌ E0505: cannot move out of `b` because it is borrowed
}

// 4. 也不能返回它
pub fn ret<'a>() -> B<'a> {
    let mut b = B { data: "hi".into(), view: None };
    b.view = Some(&b.data);
    b                                            // ❌ E0505 + E0515
}

// 5. 自引用期间不能改被引用的字段
pub fn push_then_read() {
    let mut b = B { data: "hi".into(), view: None };
    b.view = Some(&b.data);
    b.data.push('x');                            // ❌ E0502
    println!("{:?}", b.view);
}

// 6. 但如果之后不读 view，借用就死了 —— ✅
pub fn push_only() {
    let mut b = B { data: "hi".into(), view: None };
    b.view = Some(&b.data);
    b.data.push('x');                            // ✅ view 之后没被读，借用已死
}
```

> ### ★ 这组实验的结论
> **安全 Rust 里可以有自引用结构，但它是"钉死"的**——
> 一旦自引用建立，这个值就**不能移动、不能返回、不能放进容器**。
>
> 这几乎让它毫无用处：一个不能返回的结构，你没法把它从构造函数里传出来。

**这就是 `Pin` 要解决的问题**：提供一种类型层面的机制，
让"这个值已经被钉住，不会再移动"成为一个**可以传递的承诺**。

---

## 3. 为什么"链表"这个例子经常被误解

流传很广的说法："Rust 写不了链表"。**这是错的**，需要拆开说：

| 结构 | 能写吗 | 怎么写 |
|---|---|---|
| **单向链表** | ✅ 容易 | `struct Node { val: T, next: Option<Box<Node>> }` |
| **双向链表** | ✅ 但麻烦 | `Rc<RefCell<Node>>` + `Weak` 反向指针；或 `unsafe` + `NonNull`（标准库 `LinkedList` 就是这么写的） |
| **树 + 父指针** | ✅ | 同上，或 arena + index |
| **图** | ✅ | arena + index（`petgraph` 的做法） |
| **字段指向自己另一个字段** | ❌ 安全 Rust 做不到 | `Pin` + `unsafe`；或 `ouroboros` / `self_cell` 这类宏 crate |

**真正做不到的只有最后一行**：一个值的**内部指针指向它自己的另一部分**。

> **必读推荐**：[Learn Rust With Entirely Too Many Linked Lists](https://rust-unofficial.github.io/too-many-lists/)
> ——它把链表的六种写法从头到尾实现了一遍，是理解所有权最好的实战材料。

---

## 4. `Pin` 是什么

### 4.1 一句话

> **`Pin<P<T>>` 是一个指针包装器，它保证：
> 只要 `T: !Unpin`，被指向的 `T` 在被 drop 之前不会被移动。**

注意几点：
- `Pin` 包装的是**指针**（`Pin<&mut T>`、`Pin<Box<T>>`、`Pin<Rc<T>>`），不是值本身
- 它是一个**纯类型层面的东西**：运行时没有任何开销，`Pin<Box<T>>` 和 `Box<T>` 的布局一样
- 它保证的方式是**不给你 `&mut T`**——拿不到 `&mut T` 就用不了 `mem::swap`/`mem::replace`

### 4.2 `Unpin`：99% 的类型都是

```rust
pub auto trait Unpin {}
```

`Unpin` 是一个 **auto trait**（和 `Send`/`Sync` 一样自动实现）。含义是：

> **"我不在乎被移动"** —— 对我来说 `Pin` 没有任何约束力。

**几乎所有类型都是 `Unpin`**：`i32`、`String`、`Vec<T>`、你写的绝大部分 struct。

```rust
fn assert_unpin<T: Unpin>() {}
assert_unpin::<String>();      // ✅
assert_unpin::<Vec<i32>>();    // ✅
```

**不是 `Unpin` 的**：
- `async` 块 / `async fn` 产生的 `Future`（编译器生成的自引用状态机）
- 手动包了 `PhantomPinned` 的类型
- 包含以上两者的类型

**推论**：对于 `T: Unpin`，`Pin<&mut T>` 和 `&mut T` 完全等价——
`Pin::new` 和 `Pin::get_mut` 都是安全的。**`Pin` 只对 `!Unpin` 类型有约束力。**

### 4.3 API 速查

```rust
// 构造（安全的，只对 Unpin 类型）
Pin::new(&mut x)                   // T: Unpin
Box::pin(value)                    // 任何 T，因为堆上的地址不会因 Pin 移动而变
Box::into_pin(boxed)

// 构造（unsafe，对 !Unpin 类型）
unsafe { Pin::new_unchecked(&mut x) }    // ★ 你保证 x 之后不会被移动

// 使用
p.as_ref()                         // Pin<&T>
p.as_mut()                         // Pin<&mut T>（重借用）
Pin::get_ref(p)                    // &T，安全（读不会移动）
Pin::get_mut(p)                    // &mut T，仅 T: Unpin
unsafe { Pin::get_unchecked_mut(p) }     // &mut T，你保证不移动它
unsafe { p.map_unchecked_mut(|s| &mut s.field) }   // ★ pin projection
```

### 4.4 `Pin` 的核心不变量

> **一旦一个 `!Unpin` 的值被 `Pin` 住，它必须保持在同一个地址上，直到它被 drop。
> 而且它的 `Drop::drop` 一定会被调用（在内存被复用之前）。**

第二句叫 **"Drop guarantee"**，它是 `Pin` 契约里容易被忽略但很关键的一半：
你不能 `mem::forget` 一个 pinned 的值然后复用它的内存。

---

## 5. `Pin` 为什么长这么怪

新手看 `Pin` 的第一反应是"这 API 也太别扭了"。它的设计有明确的约束：

**约束 1：不能改语言**。`Pin` 是 2019 年为了 async/await 加的，
必须是一个**纯库特性**（第 02 章准则 2："能做成库的就不会做进语言"）。

**约束 2：不能破坏现有代码**。所以引入 `Unpin` 作为 auto trait，
让所有现有类型自动豁免。

**约束 3：`&mut T` 已经存在且能 `swap`**。所以唯一的办法是**不给出 `&mut T`**。

结果就是：`Pin<P<T>>` 是一个"阉割版的指针"——能读，能通过 unsafe 投影，
但不能直接拿出 `&mut T`。

> ### 一个有用的类比
> `Pin<&mut T>` ≈ **"一个 `&mut T`，但被贴了封条"**。
> 封条上写着"不许把里面的东西搬走"。`Unpin` 类型的封条是假的（随便撕）。

---

## 6. Pin projection：从 `Pin<&mut Struct>` 到 `Pin<&mut Field>`

写自定义 `Future`（第 24 章）时必然遇到的问题：

```rust
struct MyFuture {
    inner: SomeFuture,       // 需要 Pin<&mut SomeFuture> 才能 poll
    counter: u32,            // 普通字段
}
```

从 `Pin<&mut MyFuture>` 怎么拿到 `Pin<&mut SomeFuture>`？

**规则**：你必须为**每个字段**做二选一：

| 选择 | 含义 | 怎么拿 |
|---|---|---|
| **structurally pinned**（结构性钉住） | 这个字段也被钉住 | `unsafe { p.map_unchecked_mut(|s| &mut s.inner) }` → `Pin<&mut Inner>` |
| **not structurally pinned** | 这个字段不受钉住约束 | `unsafe { p.get_unchecked_mut() }.counter` → `&mut u32` |

**手写投影的四条义务**（做错就是 unsound）：

1. 结构体的 `Drop` 实现（如果有）不能移动被钉住的字段
2. 不能提供任何返回被钉住字段的 `&mut` 的安全 API
3. 结构体不能实现 `Unpin`，除非所有结构性钉住的字段都是 `Unpin`
4. 不能在结构性钉住的字段上用 `mem::replace`/`swap`

**实践中不要手写**。用 [`pin-project-lite`](https://docs.rs/pin-project-lite)（无依赖、编译快）
或 [`pin-project`](https://docs.rs/pin-project)（功能全）：

```rust
use pin_project_lite::pin_project;

pin_project! {
    struct MyFuture {
        #[pin] inner: SomeFuture,     // 结构性钉住
        counter: u32,                 // 不钉
    }
}

impl Future for MyFuture {
    type Output = ();
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        let this = self.project();
        *this.counter += 1;                    // &mut u32
        this.inner.poll(cx)                    // Pin<&mut SomeFuture>
    }
}
```

---

## 7. `Pin` 和 async 的关系（第 24 章预告）

```rust
async fn f() {
    let s = String::from("hello");
    let r = &s;                    // ★ 引用一个局部变量
    something().await;             // 在这里挂起
    println!("{}", r);             // 恢复后还要用 r
}
```

编译器把它变成一个状态机：

```rust
enum FState {
    Start,
    AfterAwait {
        s: String,
        r: *const String,     // ★ 指向同一个结构体里的 s！自引用！
    },
    Done,
}
```

**`await` 点跨越的每一个局部引用，都会变成状态机结构体里的一个自引用指针。**

所以：
- 编译器生成的 `Future` 是 `!Unpin` 的
- `Future::poll` 的签名必须是 `fn poll(self: Pin<&mut Self>, ...)`
- 你必须先 `Box::pin(fut)` 或用 `pin!` 宏才能 poll 一个 `async` 块

```rust
let fut = async { ... };
// fut.poll(cx);                   // ❌ 需要 Pin<&mut Self>
let mut fut = Box::pin(fut);       // ✅ 堆上钉住
// 或者栈上钉住（1.68+ 稳定）
let mut fut = std::pin::pin!(async { ... });
```

> ### 因果链回顾（第 02 章）
> **2014 年砍掉绿色线程和运行时** → async 必须是无栈的库特性 →
> Future 是编译器生成的状态机 → 跨 `await` 的引用变成自引用 →
> **需要 `Pin`**。
>
> 如果 Rust 保留了绿色线程（有独立栈），`Pin` 就不需要存在。

---

## 8. 安全的替代方案（推荐优先级）

**先问：你真的需要自引用吗？** 90% 的情况有更好的方案。

| 方案 | 适用 | 代价 |
|---|---|---|
| **1. 索引代替引用** | 大多数情况 ★★★★★ | 需要携带容器；边界检查 |
| **2. 拆成两个结构** | 数据 + 视图能分开时 | 需要调整 API |
| **3. 存 offset/range 而非引用** | 解析器（存 `Range<usize>` 而非 `&str`） | 用的时候要切片 |
| **4. `Rc` / `Arc`** | 真正的共享所有权 | 引用计数开销；环要用 `Weak` |
| **5. `ouroboros` / `self_cell` crate** | 确实需要"拥有 + 借用自己"的结构 | 宏；API 受限 |
| **6. `Pin` + `unsafe`** | 写运行时/库 | 要自己保证四条义务 |

**方案 3 的例子（最常用的自引用替代）**：

```rust
// ❌ 想要的自引用
struct Parser<'a> { source: String, tokens: Vec<&'a str> }

// ✅ 存 range
struct Parser {
    source: String,
    tokens: Vec<std::ops::Range<usize>>,
}
impl Parser {
    fn token(&self, i: usize) -> &str { &self.source[self.tokens[i].clone()] }
}
```

**这个模式（存索引/范围而非引用）是整个课程里最通用的解法**，第 18/20 章会反复用到。

---

## 9. 动手实验

### 实验 1：自引用的六个阶段

把第 2 节的六个函数敲进一个文件，编译，确认哪三个失败、错误码分别是什么。
**重点体会 `push_then_read` 和 `push_only` 的差别**——同一份自引用结构，
只因为后面读不读 `view`，结果就不同。

### 实验 2：`Unpin` 探测

```rust
fn assert_unpin<T: Unpin>() {}

fn main() {
    assert_unpin::<i32>();
    assert_unpin::<String>();
    assert_unpin::<Vec<String>>();
    // assert_unpin::<std::marker::PhantomPinned>();    // ← 取消注释
}

async fn dummy() {}
// fn check() { assert_unpin::<impl Future>(); }        // 想办法验证 async 块不是 Unpin
```

### 实验 3：亲手 pin 一个 Future

```rust
use std::future::Future;
use std::task::{Context, Poll, Waker};

fn main() {
    let fut = async { 42 };
    // let mut f = fut;
    // let p = std::pin::Pin::new(&mut f);        // ← 取消注释，看错误
    let mut f = Box::pin(fut);                     // ✅
    let waker = Waker::noop();
    let mut cx = Context::from_waker(&waker);
    match f.as_mut().poll(&mut cx) {
        Poll::Ready(v) => println!("ready: {}", v),
        Poll::Pending => println!("pending"),
    }
}
```

**任务**：看 `Pin::new` 那行的错误信息，理解为什么 async 块不是 `Unpin`。

### 实验 4：把自引用改写成 range

把下面这个（编译不过的）结构改写成用 `Range<usize>` 的版本：

```rust
struct Doc<'a> {
    text: String,
    title: &'a str,       // 指向 text 的一部分
    body: &'a str,
}
```

---

## 10. 本章检查清单

- [ ] 能解释为什么"移动 = memcpy"和自引用天然矛盾
- [ ] 知道安全 Rust **可以**创建自引用结构，但它不能移动/返回
- [ ] 知道"Rust 写不了链表"是错的，且知道各种链表的正确写法
- [ ] 能用一句话说清 `Pin` 的保证
- [ ] 知道 `Unpin` 是 auto trait，且 99% 的类型都是
- [ ] 知道对 `T: Unpin`，`Pin<&mut T>` 和 `&mut T` 等价
- [ ] 知道 `Pin` 是**纯类型层面**的，零运行时开销
- [ ] 知道 pin projection 的两种选择及四条义务，且知道该用 `pin-project-lite`
- [ ] **能说出从"砍掉绿色线程"到"需要 Pin"的完整因果链**
- [ ] 知道"存 range 而非引用"这个通用替代方案

---

## 11. 常见坑

| 现象 | 错误码 | 处方 |
|---|---|---|
| 构造时自引用 | E0505 | 分两步：先构造 `None`，再赋值 |
| 自引用结构不能返回 | E0505 + E0515 | 用 `Pin<Box<T>>`；或改成存 range |
| 自引用期间改被引用字段 | E0502 | 那就是真的冲突，改设计 |
| `Pin::new` 对 async 块报错 | E0277（`!Unpin`） | 用 `Box::pin` 或 `std::pin::pin!` |
| 手写 pin projection 后 unsound | 无（UB） | 用 `pin-project-lite` |
| 给 `!Unpin` 结构实现了 `Drop` 且移动了字段 | 无（UB） | 检查 pin projection 的四条义务 |
| 以为 `Pin` 有运行时开销 | — | 没有。`Pin<Box<T>>` 就是 `Box<T>` |
| 以为 `Pin` 能钉住栈上的值 | — | 需要 `pin!` 宏或 `unsafe { Pin::new_unchecked }`，且之后你不能再碰原变量 |

---

下一章：[14 - 著名难题：从 NLL problem cases 到 Polonius](14-nll-problem-cases.md)
