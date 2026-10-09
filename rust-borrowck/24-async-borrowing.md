# 24 - async 与借用：Future 是一个自引用状态机

> 本章目标：把第 13 章（自引用/`Pin`）、第 22 章（`Send`/`Sync`）、
> 第 06 章（`'static`）三条线合起来，解释 async 里所有借用相关的行为。
> 核心洞察：**`async` 没有引入任何新的借用规则。所有痛苦都来自
> "Future 是一个编译器生成的、可能自引用的、需要满足 `Send + 'static` 的结构体"。**
> 预计用时：3 小时。

---

## 1. 先建立正确的心智模型

### 1.1 `async fn` 到底生成了什么

```rust
async fn work(v: &Vec<i32>) -> usize {
    let first = &v[0];              // 借用
    yield_now().await;              // ★ 挂起点
    *first as usize + v.len()       // 恢复后继续用 first
}
```

**编译器大致生成**（示意，真实的更复杂）：

```rust
enum WorkFuture<'a> {
    Start { v: &'a Vec<i32> },
    Suspended {
        v: &'a Vec<i32>,
        first: *const i32,          // ★★★ 指向 v 内部——但它是从 v 派生的
        inner: YieldNowFuture,
    },
    Done,
}

impl<'a> Future for WorkFuture<'a> {
    type Output = usize;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<usize> { ... }
}
```

**四个必须记住的事实**：

| 事实 | 后果 |
|---|---|
| **1. `async fn` 返回一个匿名结构体**，函数体一行都没执行 | 不 `.await` 就什么都不发生 |
| **2. 所有跨 `await` 存活的局部变量，都变成这个结构体的字段** | 它们的类型决定了 Future 的 `Send`/`Sync`/`'static` |
| **3. 指向这些字段的引用变成自引用指针** | Future 是 `!Unpin`，需要 `Pin`（第 13 章） |
| **4. 参数里的生命周期出现在 Future 类型上** | `async fn work(v: &Vec<i32>)` 的返回类型带 `'a` |

> ### ★ 一条能解释 90% async 借用问题的推论
> **"作用域是否跨越 `.await`"是关键判据。**
>
> ⚠️ **注意是"作用域"，不是"最后一次使用"**（这一点实测过，见第 8 节实验 2）：
>
> ```rust
> async fn a() { let r = Rc::new(1); println!("{}", r); yield_now().await; }
> //             ↑ 最后一次使用在 await 之前，但 r 要到函数末尾才 drop
> //             → 仍然进入状态机 → Future 是 !Send  ★
>
> async fn c() { { let r = Rc::new(1); println!("{}", r); } yield_now().await; }
> //             ↑ 块结束时 r 已 drop → 不进入状态机 → Send ✅
> ```
>
> 这是第 04 章那条"借用止于最后一次使用，**drop 在作用域末尾**"的不对称性
> 在 async 里最咬人的后果。

### 1.2 三个约束的来源

```rust
tokio::spawn(fut)      where fut: Future + Send + 'static
```

| 约束 | 为什么 | 违反时的症状 |
|---|---|---|
| `Send` | 多线程 executor 会在线程间搬运 task | `future cannot be sent between threads safely` |
| `'static` | executor 不知道 task 何时结束 | `borrowed value does not live long enough` |
| `Pin`（poll 时） | 状态机可能自引用 | `cannot be unpinned` |

**注意**：单线程 executor（`tokio::task::spawn_local`、
`LocalSet`、`actix` 的部分 API）**不要求 `Send`**。

---

## 2. 借用跨 `await`：本身完全合法

```rust
async fn ok(v: &mut Vec<i32>) {
    let first = &v[0];
    yield_now().await;              // ✅ 借用跨 await 完全没问题
    println!("{}", first);
}
```

**实测：编译通过。** 借用检查在 async 里和普通函数**一模一样**——
`await` 只是一个普通的挂起点，不改变借用规则。

**真正的问题在于**：这个借用变成了 Future 结构体的字段，
于是 Future 的 `Send`/`'static` 属性受它影响。

---

## 3. `Send` 传染：最常见的 async 痛点

### 3.1 最小复现

```rust
use std::sync::Mutex;
fn assert_send<T: Send>(_: T) {}
async fn yield_now() {}

// ❌ MutexGuard 跨 await
async fn bad(m: &Mutex<i32>) {
    let g = m.lock().unwrap();
    yield_now().await;
    println!("{}", *g);
}

// ✅ guard 在 await 之前就结束
async fn good(m: &Mutex<i32>) {
    let v = { *m.lock().unwrap() };     // ★ 块限定作用域
    yield_now().await;
    println!("{}", v);
}
```

**实测报错**（lab/26）：

```
error: future cannot be sent between threads safely
  |
  |  assert_send(bad(m));
  |              ^^^^^^ future returned by `bad` is not `Send`
  |
  = help: within `impl Future<Output = ()>`, the trait `Send` is not implemented
          for `std::sync::MutexGuard<'_, i32>`
note: future is not `Send` as this value is used across an await
  |
  |  async fn bad(m: &Mutex<i32>) { let g = m.lock().unwrap(); yield_now().await; ... }
  |                                     -                                  ^^^^^ await occurs here,
  |                                     |                                        with `g` maybe used later
  |                                     has type `MutexGuard<'_, i32>` which is not `Send`
```

> ★ **注意这个错误没有错误码**（是裸的 `error:`），且诊断信息非常好——
> 它直接告诉你**哪个变量、什么类型、哪个 await**。

### 3.2 为什么 `MutexGuard` 是 `!Send`

第 22 章 §3.1：POSIX 要求 `pthread_mutex_unlock` 由加锁的线程调用。
而多线程 executor 可能在 `await` 之后把 task 调度到**另一个线程**上继续，
那时 guard 的 `Drop` 就在错误的线程执行了。

**这不是 Rust 保守——这是真实的 UB 风险。**

### 3.3 `!Send` 类型清单（async 里最常见的）

| 类型 | 替代方案 |
|---|---|
| `std::sync::MutexGuard` | 收缩作用域；或用 `tokio::sync::Mutex`（它的 guard 是 `Send`） |
| `std::sync::RwLockReadGuard/WriteGuard` | 同上 |
| `Rc<T>` | `Arc<T>` |
| `RefCell<T>` 的 `Ref`/`RefMut` | `tokio::sync::Mutex`；或不跨 await |
| `Cell<T>` / `RefCell<T>` 本身 | 它们是 `Send` 的（只是不 `Sync`），跨 await 没问题，但不能被 `&` 共享 |
| `*const T` / `*mut T` | 包装 + `unsafe impl Send` |
| 任何含以上字段的结构体 | 逐个替换 |

### 3.4 `std::sync::Mutex` vs `tokio::sync::Mutex`

| | `std::sync::Mutex` | `tokio::sync::Mutex` |
|---|---|---|
| `lock()` | 阻塞线程 | `.await`，让出 task |
| guard 是 `Send` | ❌ | ✅ |
| 能跨 `await` 持有 | ❌ | ✅ |
| 开销 | 低 | 高（要维护等待队列） |
| **推荐** | ★ **默认用它**，把临界区收缩到 await 之外 | 只在**必须**跨 await 持锁时用 |

> ### ★ tokio 官方的建议（很多人搞反了）
> **默认用 `std::sync::Mutex`。** 因为：
> 1. 大部分临界区很短（改个计数器、读个字段），不需要跨 await
> 2. `std` 版更快
> 3. 编译器会在你不小心跨 await 时**报错**——这是好事，它逼你收缩临界区
>
> 只有当你**确实需要在持锁期间做 IO** 时，才换 `tokio::sync::Mutex`。
> 而"持锁做 IO"本身往往是设计问题。

---

## 4. `'static` 传染：`spawn` 的约束

```rust
async fn process(data: &[u8]) -> usize { data.len() }

fn caller() {
    let v = vec![1u8, 2, 3];
    tokio::spawn(process(&v));       // ❌ `v` does not live long enough
}
```

**根因**：`process(&v)` 返回的 Future 类型里含 `&'a [u8]`，不满足 `'static`。

**四种解法**：

```rust
// 1. 把数据移进去（最常用）
async fn process(data: Vec<u8>) -> usize { data.len() }
tokio::spawn(process(v));

// 2. Arc 共享
let a: Arc<[u8]> = v.into();
tokio::spawn({ let a = a.clone(); async move { process(&a).await } });

// 3. 不 spawn，直接 await（在当前 task 里跑，不需要 'static）
let n = process(&v).await;

// 4. 用 scoped task（tokio 没有；`async_scoped`、`moro` 等 crate 提供，
//    但都需要 unsafe 或有限制。这是 async Rust 的一个已知缺口）
```

> ### ★ async scoped task 是 async Rust 最大的缺口之一
> 同步世界有 `thread::scope`（第 23 章），async 世界**没有等价物**。
> 原因：`thread::scope` 靠"函数返回前一定 join"来保证安全，
> 但 async task 可以被**取消**（drop Future），没法保证 join。见 §6。

---

## 5. `Pin`：为什么 `poll` 长那样

```rust
pub trait Future {
    type Output;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
    //      ^^^^^^^^^^^^^^^^^^^ 不是 &mut self
}
```

**因果链**（第 02 章 + 第 13 章）：

```
2014 砍掉绿色线程和运行时
    ↓
async 必须无栈（状态机而非独立栈）
    ↓
跨 await 的局部引用变成状态机的自引用字段
    ↓
移动状态机会让自引用悬垂
    ↓
必须禁止移动 → Pin
```

**实用后果**：

```rust
let fut = async { 42 };
// fut.poll(cx);                       // ❌ E0277: cannot be unpinned
let mut fut = Box::pin(fut);           // ✅ 堆上钉住
let mut fut = std::pin::pin!(async {}); // ✅ 栈上钉住（1.68+）
```

**99% 的应用代码不需要碰 `Pin`**——`.await` 帮你处理了。
只有**手写 `Future`** 时才需要（用 `pin-project-lite`，第 13 章 §6）。

---

## 6. 取消（cancellation）与 `Drop`

**async Rust 最容易被忽略的一块**，且和第 03 章 §8 那条"Rust 不保证 `Drop` 一定执行"直接相关。

### 6.1 取消 = drop 一个 Future

```rust
tokio::select! {
    _ = long_task() => {},
    _ = tokio::time::sleep(Duration::from_secs(1)) => {},   // 超时
}
// ★ 没被选中的那个 Future 被 drop 了——它停在某个 await 点上，永远不会恢复
```

**后果**：

```rust
async fn transfer(db: &Db) {
    db.begin().await;
    db.debit(a, 100).await;
    // ← 如果在这里被取消，钱扣了但没转！
    db.credit(b, 100).await;
    db.commit().await;
}
```

### 6.2 "取消安全（cancellation safety）"

一个 async 函数是**取消安全**的，如果在任意 `await` 点被 drop 都不会留下不一致状态。

**判断方法**：想象在**每一个** `.await` 处被砍断，问"状态还一致吗"。

**保证取消安全的手段**：

| 手段 | 说明 |
|---|---|
| **把不可分割的操作放在一个 await 里** | 比如用数据库事务的原子 API |
| **用 RAII guard 做补偿** | `Drop` 里回滚（★ 但注意 async drop 还不稳定，`Drop::drop` 不能 `.await`） |
| **`tokio::spawn` 隔离** | spawn 出去的 task 不会因为父 task 被取消而取消 |
| **查文档** | tokio 的 API 文档明确标注了哪些是 cancel-safe（`select!` 里只能用 cancel-safe 的） |

### 6.3 `Drop` 在 async 里的限制

```rust
impl Drop for Conn {
    fn drop(&mut self) {
        // self.close().await;      // ❌ 不能在 Drop 里 .await
        // 只能做同步清理，或者 spawn 一个 task（但那个 task 可能来不及跑）
    }
}
```

**async drop（`AsyncDrop`）目前仍不稳定。** 这是 async Rust 的另一个已知缺口。
**现状的最佳实践**：提供显式的 `async fn close(self)`，
并在 `Drop` 里做尽力而为的同步清理 + 打日志。

---

## 7. 诊断流程

```
async 代码编译不过
   │
   ├─ 报错含 "future cannot be sent between threads safely"
   │     └─► 找 note 里的 "this value is used across an await"
   │         → 那个变量的类型是 !Send
   │         → 收缩它的作用域到 await 之前（★ 首选）
   │         → 或换成 Send 的等价物（Rc→Arc, std Mutex→tokio Mutex）
   │         → 或改用 spawn_local（单线程 executor）
   │
   ├─ 报错含 "does not live long enough" + spawn
   │     └─► Future 借用了局部数据，不满足 'static
   │         → 把数据 move 进 async 块
   │         → 或用 Arc
   │         → 或不 spawn，直接 await
   │
   ├─ 报错含 "cannot be unpinned" / "Unpin is not implemented"
   │     └─► 手动 poll 了一个 async 块
   │         → Box::pin 或 std::pin::pin!
   │
   ├─ 报错含 "implementation of `Fn` is not general enough"
   │     └─► 闭包 + 生命周期，见第 10 章 §7.3
   │
   └─ 普通的 E0499/E0502/E0505
         └─► 和同步代码一样处理。async 没有改变借用规则
```

---

## 8. 动手实验

**注**：本节实验不需要 tokio，用 `Waker::noop` 就能手动 poll。

### 实验 1：`Send` 传染的最小复现

```rust
use std::sync::Mutex;
fn assert_send<T: Send>(_: T) {}
async fn yield_now() {}

async fn bad(m: &Mutex<i32>)  { let g = m.lock().unwrap(); yield_now().await; println!("{}", *g); }
async fn good(m: &Mutex<i32>) { let v = { *m.lock().unwrap() }; yield_now().await; println!("{}", v); }

fn main() {
    static M: Mutex<i32> = Mutex::new(0);
    // assert_send(bad(&M));      // ← 取消注释，抄下完整报错
    assert_send(good(&M));
}
```

**任务**：抄下 `bad` 的完整报错，**指出报错里的三段信息**：
哪个类型、哪个变量、哪个 await。

### 实验 2：跨 await 的判据

预测下面每个 Future 是不是 `Send`：

```rust
use std::rc::Rc;
async fn yield_now() {}

async fn a() { let r = Rc::new(1); println!("{}", r); yield_now().await; }          // ?
async fn b() { let r = Rc::new(1); yield_now().await; println!("{}", r); }          // ?
async fn c() { { let r = Rc::new(1); println!("{}", r); } yield_now().await; }      // ?
async fn d() { let r = Rc::new(1); drop(r); yield_now().await; }                     // ?
```

<details><summary>答案（★ 实测结果和直觉不同）</summary>

**实测**（`rustc 1.96.0`，edition 2024）：

```
a: error: future cannot be sent between threads safely     ← ★ 意外！
b: error: future cannot be sent between threads safely
c: ✅
d: ✅
```

- `a` **❌ !Send**（★ 反直觉）：`r` 虽然在 await **之前**最后一次使用，
  但它**仍在作用域内**——要到 async 块结束时才 drop，也就是 await **之后**。
  所以它进入了状态机。
- `b` ❌ !Send：显然跨越了
- `c` ✅ Send：块 `{}` 结束时 `r` 已 drop
- `d` ✅ Send：显式 `drop(r)`

> ### ★★★ 这是本章最重要的一条实测结论
> **判据不是"最后一次使用在 await 之前"，而是"作用域是否跨越 await"。**
>
> 这和 NLL 的借用规则**不一样**！NLL 让借用止于最后一次使用（第 04 章），
> 但**变量本身要到作用域末尾才 drop**——而 Future 的状态机是按
> **drop 时机**（作用域）来决定字段的，不是按最后一次使用。
>
> 这正是第 04 章 §3.4 那条"借用止于最后一次使用，drop 在作用域末尾"
> 不对称性在 async 里的直接后果。

**处方**（记住这两个）：

```rust
// 1. 用块限定作用域 ★ 首选
async fn ok1() { { let r = Rc::new(1); println!("{}", r); } yield_now().await; }

// 2. 显式 drop
async fn ok2() { let r = Rc::new(1); println!("{}", r); drop(r); yield_now().await; }
```

</details>

### 实验 3：手动 poll 一个 Future

```rust
use std::future::Future;
use std::task::{Context, Poll, Waker};

fn main() {
    let fut = async {
        let s = String::from("hello");
        let r = &s;                       // ★ 跨 await 的自引用
        yield_once().await;
        r.len()
    };
    // let p = std::pin::Pin::new(&mut fut);      // ← 取消注释看错误
    let mut fut = Box::pin(fut);
    let waker = Waker::noop();
    let mut cx = Context::from_waker(&waker);
    loop {
        match fut.as_mut().poll(&mut cx) {
            Poll::Ready(v) => { println!("ready: {}", v); break }
            Poll::Pending => println!("pending, poll again"),
        }
    }
}

async fn yield_once() {
    struct Y(bool);
    impl Future for Y {
        type Output = ();
        fn poll(mut self: std::pin::Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
            if self.0 { Poll::Ready(()) } else { self.0 = true; cx.waker().wake_by_ref(); Poll::Pending }
        }
    }
    Y(false).await
}
```

**任务**：跑通它，观察 `Pending` 打印了几次。然后取消 `Pin::new` 那行，看错误。

### 实验 4：取消安全性

```rust
async fn transfer(log: &mut Vec<&'static str>) {
    log.push("begin");
    yield_now().await;
    log.push("debit");
    yield_now().await;
    log.push("credit");
    log.push("commit");
}
```

用实验 3 的手动 poll 循环跑它，但**只 poll 两次就丢弃 Future**。
观察 `log` 的内容——**这就是取消发生时的状态**。

---

## 9. 本章检查清单

- [ ] 知道 `async fn` 返回一个匿名结构体，不 `.await` 什么都不发生
- [ ] **能背出核心判据：变量是否"跨越 await"决定它是否进入状态机**
- [ ] 知道跨 await 持有借用**本身完全合法**，问题在 `Send`/`'static`
- [ ] 知道 `MutexGuard` 为什么 `!Send`（POSIX 要求）
- [ ] **知道 tokio 官方推荐默认用 `std::sync::Mutex`**
- [ ] 能读懂 `future cannot be sent between threads safely` 的三段信息
- [ ] 知道 `spawn` 要求 `'static` 的理由和四种解法
- [ ] **能说出从"砍掉绿色线程"到"需要 Pin"的完整因果链**
- [ ] 知道取消 = drop Future，以及什么是取消安全
- [ ] 知道 `Drop` 里不能 `.await`，async drop 尚未稳定
- [ ] 知道 async scoped task 是个已知缺口

---

## 10. 常见坑

| 现象 | 原因 | 处方 |
|---|---|---|
| `future cannot be sent` | 某个 `!Send` 值跨了 await | 收缩作用域；换 `Arc`/`tokio::sync::Mutex`；或 `spawn_local` |
| `spawn` 报生命周期错 | Future 借用了局部数据 | move 进去；或 `Arc`；或直接 await |
| `cannot be unpinned` | 手动 poll 了 async 块 | `Box::pin` / `pin!` |
| 明明 await 之前就用完了还说跨 await | ★ **判据是"作用域"不是"最后一次使用"**——变量到作用域末尾才 drop | 用块 `{}` 限定；或显式 `drop(x)` |
| `select!` 之后状态不一致 | 取消安全性 | 检查每个 await 点；用 cancel-safe 的 API |
| `Drop` 里想 `.await` | 不支持 | 提供显式 `async fn close(self)` |
| 用了 `tokio::sync::Mutex` 反而更慢 | 它比 `std` 版重 | 默认 `std`，只在必须跨 await 持锁时换 |
| async trait 报 `Send` 相关错误 | `async fn` in trait 无法指定 auto trait bound | 改写成 `-> impl Future<Output=T> + Send`（第 21 章） |
| 忘了 `.await` | Future 什么都不做 | `#[must_use]` 会警告；打开 `unused_must_use` |

---

下一章：[25 - 异步经典陷阱](25-async-pitfalls.md)
