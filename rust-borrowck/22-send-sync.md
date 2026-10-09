# 22 - `Send` / `Sync` 的本质：无畏并发是推论，不是新机制

> 本章目标：证明一件事——**Rust 没有为并发安全设计任何新东西**。
> `Send`/`Sync` 只是把第 03 章那条公理从"内存"推广到"线程"的直接结果。
> 学完这章，你看到任何 `Send`/`Sync` 报错都能立刻推出原因。
> 预计用时：2 小时。

---

## 1. 从公理推导

**数据竞争的标准定义**：

> 两个线程**并发**访问同一内存位置，**至少一个是写**，且**没有同步**。

拆开看：

```
数据竞争 = 别名（两个线程都能访问同一处）
         + 可变（至少一个在写）
         + 无同步
```

**和公理对照**（第 03 章）：

```
Aliasing XOR Mutability 被违反 = 别名 + 可变
```

**它们是同一件事。** 所以：

> ### **只要借用规则在跨线程时仍然成立，就不可能有数据竞争。**

问题只剩一个：**借用规则本来是"在同一个程序点上"检查的，跨线程时"程序点"怎么定义？**

答案：**不定义**。Rust 换了个更保守的做法——
**限制哪些类型可以跨线程移动 / 共享**。这就是 `Send` 和 `Sync`。

---

## 2. 两个定义

```rust
pub unsafe auto trait Send { }
pub unsafe auto trait Sync { }
```

| trait | 定义 | 一句话 |
|---|---|---|
| **`Send`** | 类型的值可以**安全地移动**到另一个线程 | "换个线程用是安全的" |
| **`Sync`** | 类型可以被**多个线程同时通过 `&T` 访问** | "共享引用发给别人是安全的" |

**它们之间的精确关系**（标准库里的实际定义）：

```rust
// T: Sync  ⟺  &T: Send
unsafe impl<T: Sync + ?Sized> Send for &T {}
```

> ### ★ 记住这一条就够了
> **`Sync` 就是 "`&T` 是 `Send` 的"。**
>
> 所以：
> - `Send` 管的是**所有权转移**
> - `Sync` 管的是**共享引用转移**
> - `&mut T: Send` ⟺ `T: Send`（独占引用转移等价于所有权转移）

### 2.1 `auto trait`：自动推导

`Send`/`Sync` 是 **auto trait**：**编译器自动为"所有字段都满足"的类型实现它们**。

```rust
struct A { x: i32, y: String }          // 自动 Send + Sync
struct B { x: i32, y: Rc<i32> }         // 自动 !Send + !Sync（因为 Rc 是）
```

**你不需要写任何东西**。这就是"零成本"的一部分——
并发安全检查完全由类型系统自动完成。

**手动 opt-out**（不稳定特性 `negative_impls`）或者塞一个 `PhantomData`：

```rust
struct NotSync { data: i32, _marker: PhantomData<Cell<()>> }   // ★ 常用技巧
```

---

## 3. 谁不是 `Send` / `Sync`，以及为什么

**这张表是本章的核心。每一行都能从公理推出来。**

| 类型 | `Send` | `Sync` | 为什么 |
|---|---|---|---|
| `i32`、`String`、`Vec<T>`（T: Send） | ✅ | ✅ | 无共享状态 |
| `&T` | 若 `T: Sync` | 若 `T: Sync` | 定义 |
| `&mut T` | 若 `T: Send` | 若 `T: Sync` | 独占引用 ≈ 所有权 |
| **`Rc<T>`** | ❌ | ❌ | **引用计数是非原子的**——两个线程同时 clone 会丢计数 → double free |
| `Arc<T>` | 若 `T: Send+Sync` | 若 `T: Send+Sync` | 原子计数 ✅；但内部 `T` 会被共享，所以要 `Sync` |
| **`Cell<T>`** | 若 `T: Send` | **❌** | 通过 `&Cell` 就能写 → 两个线程同时写 = 数据竞争 |
| **`RefCell<T>`** | 若 `T: Send` | **❌** | 借用计数是非原子的 |
| `Mutex<T>` | 若 `T: Send` | **✅** 若 `T: Send` | 锁提供了同步 |
| `RwLock<T>` | 若 `T: Send` | ✅ 若 `T: Send+Sync` | 读锁允许多个并发读 → 需要 `T: Sync` |
| **`MutexGuard<'_, T>`** | **❌** | 若 `T: Sync` | ★ **必须在加锁的线程解锁**（POSIX 要求） |
| `RwLockReadGuard` | ❌ | 若 `T: Sync` | 同上 |
| `*const T` / `*mut T` | ❌ | ❌ | 编译器无法知道它指向什么 |
| `Atomic*` | ✅ | ✅ | 硬件保证 |
| `OnceLock<T>` / `LazyLock<T>` | 若 `T: Send` | ✅ 若 `T: Send+Sync` | 内部用原子 |

### 3.1 逐个推导

**`Rc<T>` 为什么不是 `Send`**：

```rust
// 假设 Rc 是 Send。两个线程各持一个 Rc<Data>：
线程 A: rc.clone()  →  读 count=1, 写 count=2
线程 B: drop(rc)    →  读 count=1, 写 count=0
// 交错执行后 count 可能是 0 而数据还在用，或者是 2 而只剩一个持有者
// → double free 或 内存泄漏
```

**`Cell<T>` 为什么不是 `Sync`**：

```rust
// 假设 Cell 是 Sync。两个线程各有 &Cell<i64>：
线程 A: c.set(0x1111_1111_1111_1111)
线程 B: c.set(0x2222_2222_2222_2222)
// 非原子写，可能撕裂成 0x1111_1111_2222_2222
// 如果 T 是个带指针的类型，撕裂就是内存不安全
```

**`MutexGuard` 为什么不是 `Send`**（★ 最容易忽略的一个）：

```rust
let g = m.lock().unwrap();          // 线程 A 加锁
thread::spawn(move || drop(g));     // ❌ 线程 B 解锁
```

POSIX 的 `pthread_mutex_unlock` **要求由加锁的线程调用**，否则是 UB。
所以 `MutexGuard` 必须 `!Send`。

> ### ★ 这一条直接导致了第 25 章那个最著名的异步坑
> `MutexGuard` `!Send` → 跨 `await` 持有它的 `Future` 也 `!Send` →
> 不能交给多线程 executor（`tokio::spawn`）。

---

## 4. 编译器怎么用它们

### 4.1 `thread::spawn` 的签名

```rust
pub fn spawn<F, T>(f: F) -> JoinHandle<T>
where
    F: FnOnce() -> T + Send + 'static,
    T: Send + 'static,
```

**三个约束各管什么**：

| 约束 | 防止什么 |
|---|---|
| `F: Send` | 闭包（含它捕获的所有东西）能不能移到新线程 |
| `F: 'static` | 闭包不能借用调用者栈上的东西（编译器不知道线程何时结束） |
| `T: Send` | 返回值能不能移回来 |

### 4.2 报错长什么样

```rust
use std::rc::Rc;
let r = Rc::new(1);
std::thread::spawn(move || println!("{}", r));
```

**实测**：

```
error[E0277]: `Rc<i32>` cannot be sent between threads safely
  |
  |  std::thread::spawn(move || println!("{}", r));
  |  ------------------ -------^^^^^^^^^^^^^^^^^^
  |  |                  |
  |  |                  `Rc<i32>` cannot be sent between threads safely
  |  |                  within this `{closure@...}`
  |  required by a bound introduced by this call
  |
  = help: within `{closure@...}`, the trait `Send` is not implemented for `Rc<i32>`
note: required because it's used within this closure
```

**读法**：
1. 哪个类型不满足 → `Rc<i32>`
2. 它在哪里 → `within this closure`（闭包捕获了它）
3. 谁要求的 → `required by a bound introduced by this call`（`spawn`）

**排查三步**：
- 找出报告的那个 `!Send` 类型
- 在自己的代码里找它从哪来（通常是某个字段或捕获的变量）
- 换成对应的线程安全版本（见 §5）

---

## 5. 替换表

| 单线程 | 跨线程 | 代价 |
|---|---|---|
| `Rc<T>` | `Arc<T>` | 原子计数 |
| `Cell<T>` | `Atomic*`（若是整数）/ `Mutex<T>` | 原子指令 / 锁 |
| `RefCell<T>` | `Mutex<T>` / `RwLock<T>` | 锁 |
| `Rc<RefCell<T>>` | `Arc<Mutex<T>>` | 两者 |
| `OnceCell<T>` | `OnceLock<T>` | 原子 |
| `LazyCell<T>` | `LazyLock<T>` | 原子 |
| `*mut T` | 包一层 `unsafe impl Send`（见 §6） | 你负责 |

---

## 6. `unsafe impl Send/Sync`：什么时候、怎么写

**只有一种正当场景**：你写了一个 `unsafe` 抽象，内部有裸指针，
但你能证明它满足并发安全的语义。

```rust
pub struct MyBuffer {
    ptr: NonNull<u8>,        // ← 裸指针让它自动变成 !Send + !Sync
    len: usize,
}

// SAFETY: MyBuffer 拥有它指向的内存（不与任何其它对象共享），
// 移动 MyBuffer 会连同所有权一起移动，因此可以安全地跨线程发送。
unsafe impl Send for MyBuffer {}

// SAFETY: MyBuffer 的所有 &self 方法都只做读取，
// 内部没有任何内部可变性，因此多线程同时持有 &MyBuffer 是安全的。
unsafe impl Sync for MyBuffer {}
```

**四条规矩**：

1. **每个 `unsafe impl` 都必须有 `// SAFETY:` 注释**说明为什么成立
2. **`Send` 和 `Sync` 要分别论证**——它们不是一回事
3. **想清楚泛型参数**：`unsafe impl<T> Send for MyBox<T> {}` 通常是错的，
   应该是 `unsafe impl<T: Send> Send for MyBox<T> {}`
4. **用 Miri 和并发测试验证**（第 26 章）；`loom` crate 可以穷举线程交错

> ### ⚠️ 最常见的 unsound 模式
> ```rust
> unsafe impl<T> Send for MyContainer<T> {}       // ❌ 忘了 T: Send
> ```
> 这样 `MyContainer<Rc<i32>>` 就变成 `Send` 了 → 用户可以用安全代码触发 UB。
> **这是一个 soundness bug**，属于最严重的问题类别。

---

## 7. 一个哲学总结

回顾一下这条推理链：

```
Aliasing XOR Mutability（第 03 章公理）
        │
        ├─ 在单线程内 ──► 借用检查（第 04–07 章）
        │
        └─ 跨线程    ──► 数据竞争 = 别名 + 可变（同一件事！）
                              │
                              └─► 只需限制"哪些类型能跨线程"
                                       │
                                       ├─ Send：所有权能不能转移
                                       └─ Sync：&T 能不能转移（= &T: Send）
                                              │
                                              └─► auto trait：编译器自动推导
```

**没有新机制。没有额外的运行时检查。没有性能开销。**

> ### "Fearless Concurrency" 的确切含义
> 不是"Rust 有很棒的并发库"，而是：
>
> **"如果你的并发代码能编译，它就没有数据竞争。"**
>
> 而这个保证的成本是**零**——它完全来自你为了内存安全已经付过的那笔学费。
>
> **对比**：Go 有优秀的并发原语（goroutine、channel、select），
> 但 Go **无法**在编译期保证无数据竞争——它只能给你 `-race`（运行时抽样，会漏）。
> 这不是 Go 团队不努力，是**没有别名控制就做不到**。

---

## 8. 动手实验

### 实验 1：Send/Sync 探测器

```rust
fn is_send<T: Send>() {}
fn is_sync<T: Sync>() {}

use std::cell::{Cell, RefCell};
use std::rc::Rc;
use std::sync::{Arc, Mutex, RwLock, MutexGuard};

fn main() {
    // 逐行取消注释，记录哪些失败
    is_send::<i32>();
    is_send::<String>();
    is_send::<Rc<i32>>();               // ?
    is_send::<Arc<i32>>();              // ?
    is_send::<Cell<i32>>();             // ?
    is_send::<RefCell<i32>>();          // ?
    is_send::<*mut i32>();              // ?

    is_sync::<i32>();
    is_sync::<Cell<i32>>();             // ?
    is_sync::<RefCell<i32>>();          // ?
    is_sync::<Mutex<i32>>();            // ?
    is_sync::<Rc<i32>>();               // ?
    is_sync::<Arc<Cell<i32>>>();        // ? ★ 想清楚为什么
}
```

<details><summary>答案与关键推理</summary>

失败的：`Rc<i32>`（都不是）、`Cell<i32>`（不 `Sync`）、`RefCell<i32>`（不 `Sync`）、
`*mut i32`（都不是）。

★ **`Arc<Cell<i32>>`**：`Arc<T>: Sync` 需要 `T: Send + Sync`。
`Cell<i32>` 不是 `Sync` → `Arc<Cell<i32>>` 不是 `Sync`。
**这说明 `Arc` 不会"修好"内部类型的线程安全性**——它只解决引用计数的原子性。
想共享可变状态，必须是 `Arc<Mutex<T>>`。

</details>

### 实验 2：从公理推 `!Send`

不看第 3 节，自己论证：

1. 如果 `Rc<T>` 是 `Send`，构造一个具体的 double free 场景
2. 如果 `Cell<i64>` 是 `Sync`，构造一个撕裂写场景
3. 如果 `MutexGuard` 是 `Send`，会违反什么

### 实验 3：诊断 `Send` 报错

```rust
use std::rc::Rc;
struct Task { id: u32, cache: Rc<Vec<u8>> }

fn main() {
    let t = Task { id: 1, cache: Rc::new(vec![]) };
    std::thread::spawn(move || println!("{}", t.id));               // ✅ 居然能过！
    let t2 = Task { id: 2, cache: Rc::new(vec![]) };
    std::thread::spawn(move || println!("{}", t2.cache.len()));     // ❌ 这个才报错
}
```

> ### ★ 为什么第一个能过
> **RFC 2229（edition 2021 起）：`move` 闭包按"用到的字段"捕获，不是整个结构体。**
> 第一个闭包只提到 `t.id`，捕获的就只有一个 `u32` —— `Rc` 压根没进闭包。
> 把 edition 退回 2018 再编译，它就报 `Rc<Vec<u8>> cannot be sent between threads safely`。
>
> **推论**：`Send` 报错看的是**闭包真正捕获了什么**，不是变量声明成了什么。
> 排查时先问"这个闭包到底捕获了哪几个字段"（第 12 章 场景三）。

**任务**：
1. 抄下第二个的完整报错
2. 指出是**哪个字段**导致的
3. 用 `--edition 2018` 重编译，看第一个也开始报错
3. 用两种方式修好（换 `Arc`；或让闭包只捕获 `t.id`）

### 实验 4：`unsafe impl` 的 soundness

```rust
use std::marker::PhantomData;
struct Wrapper<T> { ptr: *mut T, _m: PhantomData<T> }

unsafe impl<T> Send for Wrapper<T> {}       // ★ 这个 impl 是 unsound 的
```

**任务**：写一段**只用安全代码**的程序，利用这个 unsound 的 impl 触发数据竞争。
（提示：`Wrapper<Rc<i32>>`。）然后修正这个 impl。

---

## 9. 本章检查清单

- [ ] **能从公理推出"数据竞争 = 违反 Aliasing XOR Mutability"**
- [ ] 能说出 `Send` 和 `Sync` 的定义
- [ ] **能默写 `T: Sync ⟺ &T: Send`**
- [ ] 知道它们是 auto trait，编译器自动推导
- [ ] 能解释 `Rc` 为什么 `!Send`、`Cell` 为什么 `!Sync`、`MutexGuard` 为什么 `!Send`
- [ ] 知道 `Arc<T>: Sync` 需要 `T: Send + Sync`（`Arc<Cell<T>>` 不是 `Sync`）
- [ ] 能读懂 `E0277: cannot be sent between threads safely` 的三段信息
- [ ] 会用替换表
- [ ] 知道 `unsafe impl Send/Sync` 的四条规矩，尤其是**别忘了泛型 bound**
- [ ] **能用一句话解释 "fearless concurrency" 的确切含义**

---

## 10. 常见坑

| 现象 | 原因 | 处方 |
|---|---|---|
| `Rc<T> cannot be sent` | 用了单线程引用计数 | 换 `Arc<T>` |
| `Cell/RefCell cannot be shared` | 它们不是 `Sync` | 换 `Mutex`/`RwLock`/`Atomic` |
| 用了 `Arc` 还是不能共享可变 | `Arc<T>` 只让计数原子，`T` 本身还是不可变 | `Arc<Mutex<T>>` |
| `Arc<Cell<T>>` 报 `!Sync` | `Arc<T>: Sync` 需要 `T: Sync` | 同上 |
| `MutexGuard` 不能跨线程 / 跨 await | 它是 `!Send`（POSIX 要求） | 收缩 guard 的作用域（第 25 章） |
| 自己的类型莫名 `!Send` | 某个字段是 `!Send`（常见：`Rc`、`*mut`、`RefCell`） | 用 `is_send::<T>()` 二分定位 |
| `unsafe impl<T> Send` 忘了 bound | **soundness bug** | 写成 `unsafe impl<T: Send> Send` |
| 以为 `Send` 保证了线程安全 | 只保证**无数据竞争**。死锁、竞态条件不管（第 23 章） | — |

---

下一章：[23 - 线程与借用](23-concurrency.md)
