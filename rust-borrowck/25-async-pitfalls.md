# 25 - 异步经典陷阱

> 本章目标：把 async Rust 里所有和借用/所有权相关的高频陷阱集中起来，
> 每个给出**最小复现 + 根因 + 处方**。这是第 11/12 章的 async 版本。
> 所有例子实测于 `rustc 1.96.0` / `1.100.0-nightly`，edition 2024。
> 预计用时：2.5 小时。

---

## 目录

| # | 陷阱 | 类别 |
|---|---|---|
| 1 | `MutexGuard` 跨 `await` → Future 不是 `Send` | Send |
| 2 | **变量"用完了"但作用域没结束，仍然算跨 await** | Send ★ |
| 3 | `tokio::sync::Mutex` 用过头 | 性能 |
| 4 | `spawn` 的 `'static` | 生命周期 |
| 5 | async 递归必须 boxing | 类型 |
| 6 | 公开 trait 里的 `async fn` 无法指定 `Send` | trait |
| 7 | `async fn` in trait 不能直接 `dyn` | trait |
| 8 | `select!` 的取消安全性 | 取消 |
| 9 | `Drop` 里不能 `.await` | 取消 |
| 10 | 在 async 里做阻塞操作 | 运行时 |
| 11 | 循环里跨 await 持有 `&mut` | 借用 |
| 12 | `join_all` / `FuturesUnordered` 与借用 | 借用 |
| 13 | async 里没有 scoped task | 缺口 |
| 14 | 忘了 `.await` | 基础 |

---

## 1. `MutexGuard` 跨 `await`

```rust
use std::sync::Mutex;
async fn bad(m: &Mutex<i32>) {
    let g = m.lock().unwrap();
    yield_now().await;                  // ❌
    println!("{}", *g);
}
```

**报错**（无错误码，诊断很好）：

```
error: future cannot be sent between threads safely
  = help: the trait `Send` is not implemented for `std::sync::MutexGuard<'_, i32>`
note: future is not `Send` as this value is used across an await
  |  has type `MutexGuard<'_, i32>` which is not `Send`
```

**根因**：`MutexGuard` 是 `!Send`（POSIX 要求由加锁线程解锁，第 22 章 §3.1）。
多线程 executor 可能在 await 后把 task 换到别的线程。

**处方**（按优先级）：

```rust
// 1. ★ 收缩临界区到 await 之外（90% 的情况）
async fn ok(m: &Mutex<i32>) {
    let v = { *m.lock().unwrap() };     // 块结束，guard 释放
    yield_now().await;
    println!("{}", v);
}

// 2. 换 tokio::sync::Mutex（它的 guard 是 Send）—— 只在必须跨 await 持锁时
async fn ok2(m: &tokio::sync::Mutex<i32>) {
    let g = m.lock().await;
    yield_now().await;                  // ✅
    println!("{}", *g);
}

// 3. 用单线程 executor（spawn_local / LocalSet）—— 不要求 Send
```

---

## 2. ★ 变量"用完了"但作用域没结束，仍然算跨 await

**这是本章最反直觉、也最容易踩的一条。**

```rust
use std::rc::Rc;
async fn a() {
    let r = Rc::new(1);
    println!("{}", r);        // ← 最后一次使用，在 await 之前
    yield_now().await;
}                             // ← 但 r 到这里才 drop
```

**实测：`a()` 的 Future 不是 `Send`。**

**根因**：Future 状态机的字段是按**变量作用域**决定的，不是按**最后一次使用**。
`r` 在 await 点仍然"存活"（还没 drop），所以它进入了状态机。

> ### ★ 和借用规则的不一致
> - **借用**：止于最后一次使用（NLL/Polonius，第 04/07 章）
> - **变量本身**：活到作用域末尾才 drop（第 04 章 §3.4）
> - **Future 的字段**：按后者决定
>
> 所以"我明明用完了"这个直觉在 async 里**不成立**。

**处方**：

```rust
// 1. ★ 块限定作用域
async fn ok1() { { let r = Rc::new(1); println!("{}", r); } yield_now().await; }

// 2. 显式 drop
async fn ok2() { let r = Rc::new(1); println!("{}", r); drop(r); yield_now().await; }

// 3. 抽成子函数（子函数返回时局部变量已 drop）
async fn ok3() { helper(); yield_now().await; }
fn helper() { let r = Rc::new(1); println!("{}", r); }
```

**⚠️ 特别注意 `if`/`match` 的临时值**：

```rust
async fn tricky(m: &Mutex<Vec<i32>>) {
    if m.lock().unwrap().is_empty() {    // ★ guard 是 scrutinee 的临时值
        yield_now().await;               // 在 2021 edition 下 guard 还活着 → !Send
    }
}
// ✅ 拆开
async fn ok(m: &Mutex<Vec<i32>>) {
    let empty = m.lock().unwrap().is_empty();
    if empty { yield_now().await; }
}
```

---

## 3. `tokio::sync::Mutex` 用过头

**tokio 官方文档的明确建议**：**默认用 `std::sync::Mutex`。**

| | `std::sync::Mutex` | `tokio::sync::Mutex` |
|---|---|---|
| 开销 | 低（无竞争时几十纳秒） | 高（维护等待队列 + waker） |
| guard `Send` | ❌ | ✅ |
| `lock()` | 阻塞线程 | `.await` 让出 task |
| 适合 | ★ 短临界区（改字段、读值） | 持锁期间要做 IO |

**为什么 `std` 版的"编译错误"是好事**：它逼你把临界区收缩到 await 之外，
而**持锁做 IO 本身通常就是设计问题**（会阻塞所有等这把锁的 task）。

**反模式**：

```rust
// ❌ 持锁期间做网络请求 —— 所有其它 task 都被卡住
let mut cache = cache.lock().await;
let data = http_get(url).await;
cache.insert(url, data);

// ✅ 先做 IO，再短暂加锁
let data = http_get(url).await;
cache.lock().await.insert(url, data);
```

---

## 4. `spawn` 的 `'static`

```rust
async fn process(data: &[u8]) -> usize { data.len() }

fn caller() {
    let v = vec![1u8, 2, 3];
    tokio::spawn(process(&v));       // ❌ `v` does not live long enough
}
```

**处方**：

```rust
tokio::spawn(async move { process_owned(v).await });      // 1. move
let a = Arc::new(v); let a2 = a.clone();
tokio::spawn(async move { process(&a2).await });          // 2. Arc
let n = process(&v).await;                                 // 3. 不 spawn
```

---

## 5. async 递归必须 boxing

```rust
async fn rec(n: u32) { if n > 0 { rec(n - 1).await; } }
```

**实测报错**：

```
error[E0733]: recursion in an async fn requires boxing
 --> arec.rs:2:1
  |
2 | pub async fn rec_bad(n: u32) { if n>0 { rec_bad(n-1).await; } }
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^            ------------------ recursive call here
```

**根因**：状态机结构体会包含自己 → 无限大小。

**处方**：

```rust
// 1. Box::pin 递归调用（最简单）
pub async fn rec(n: u32) { if n > 0 { Box::pin(rec(n - 1)).await; } }

// 2. 返回 Pin<Box<dyn Future>>
fn rec2(n: u32) -> Pin<Box<dyn Future<Output = ()> + Send>> {
    Box::pin(async move { if n > 0 { rec2(n - 1).await; } })
}

// 3. 改成迭代（★ 最好，也避免栈/堆爆炸）
```

---

## 6. 公开 trait 里的 `async fn` 无法指定 `Send`

```rust
pub trait Svc { async fn call(&self) -> u32; }
```

**实测警告**：

```
warning: use of `async fn` in public traits is discouraged
         as auto trait bounds cannot be specified
```

**根因**：`async fn` 返回的是匿名 Future 类型，你没法在 trait 定义里
给它加 `+ Send`。于是下游用户没法把实现了这个 trait 的对象 `tokio::spawn`。

**处方**：

```rust
// ★ 公开库的推荐写法
pub trait Svc {
    fn call(&self) -> impl Future<Output = u32> + Send;
}

// 或用 trait-variant crate 自动生成两个版本（Send / 非 Send）
```

**私有 trait / 内部代码用 `async fn` 完全没问题。**

---

## 7. `async fn` in trait 不能直接 `dyn`

```rust
pub trait Svc { async fn call(&self) -> u32; }
// let s: Box<dyn Svc> = ...;         // ❌ 不是 dyn-compatible（旧称 object-safe）
```

**根因**：返回类型是每个 impl 各自的匿名类型，vtable 里放不下。

**处方**：

```rust
// 1. 手动 box（最直接）
pub trait Svc {
    fn call(&self) -> Pin<Box<dyn Future<Output = u32> + Send + '_>>;
}

// 2. async-trait 宏（自动做上面这件事）
#[async_trait::async_trait]
pub trait Svc { async fn call(&self) -> u32; }

// 3. 避免 dyn：用泛型 + 枚举分发
enum AnySvc { A(SvcA), B(SvcB) }
```

**注意 `+ '_`**：如果 `call` 借用了 `&self`，返回的 Future 也借用了它，
所以 trait object 上要写生命周期（第 21 章 §5.1）。

---

## 8. `select!` 的取消安全性

```rust
tokio::select! {
    res = read_exact(&mut socket, &mut buf) => { ... }     // ⚠️ 不是 cancel-safe！
    _ = shutdown.recv() => { return; }
}
```

**问题**：如果 `shutdown` 先完成，`read_exact` 的 Future 被 **drop**——
它可能已经读了一半数据到 `buf` 里，**那部分数据永久丢失**。

**规则**：`select!` 的每个分支必须是 **cancel-safe** 的。

**tokio 文档里标注了哪些是 cancel-safe**：

| cancel-safe ✅ | **不是** cancel-safe ❌ |
|---|---|
| `mpsc::Receiver::recv` | `AsyncReadExt::read_exact` |
| `oneshot::Receiver` | `AsyncWriteExt::write_all` |
| `tokio::time::sleep` | 大部分"读满 N 字节"类 API |
| `AsyncReadExt::read`（单次） | 自己写的多步 async 函数（默认假设不安全） |

**处方**：

```rust
// 1. 把不安全的操作 spawn 出去，select 它的 JoinHandle（★ 通用手法）
let h = tokio::spawn(async move { read_exact(&mut socket, &mut buf).await });
tokio::select! {
    res = h => { ... }
    _ = shutdown.recv() => { /* h 会继续跑完，或显式 h.abort() */ }
}

// 2. 用 &mut fut 让 Future 在循环外保持存活（select 只 poll 不消耗）
let mut fut = std::pin::pin!(read_exact(&mut socket, &mut buf));
loop {
    tokio::select! {
        res = &mut fut => break res,       // ★ &mut，不消耗
        _ = tick.tick() => { log("still reading"); }
    }
}
```

### 8.1 怎么判断自己的函数是否 cancel-safe

> **在每一个 `.await` 处画一刀，问："如果这里被砍断，状态还一致吗？"**

```rust
async fn transfer(db: &Db) {
    db.begin().await;
    db.debit(a, 100).await;
    // ← 砍在这里：钱扣了，没转 ❌
    db.credit(b, 100).await;
    db.commit().await;
}
```

---

## 9. `Drop` 里不能 `.await`

```rust
impl Drop for Conn {
    fn drop(&mut self) {
        // self.close().await;                 // ❌ Drop::drop 不是 async
        // tokio::spawn(self.close());         // ⚠️ 可能来不及跑（进程退出时）
    }
}
```

**现状**：`AsyncDrop` **尚未稳定**。这是 async Rust 的已知缺口。

**当前最佳实践**：

```rust
impl Conn {
    pub async fn close(mut self) -> Result<()> { ... }   // ★ 显式的异步关闭
}
impl Drop for Conn {
    fn drop(&mut self) {
        if !self.closed {
            tracing::warn!("Conn dropped without close()");     // 尽力而为
            // 同步的兜底清理（关 fd 之类）
        }
    }
}
```

---

## 10. 在 async 里做阻塞操作

```rust
async fn bad() {
    std::thread::sleep(Duration::from_secs(1));      // ❌ 阻塞整个 executor 线程
    let data = std::fs::read("big.txt").unwrap();    // ❌ 同上
    heavy_cpu_work();                                 // ❌ 同上
}
```

**这不是借用问题，但它是 async Rust 最常见的生产事故。**
一个 executor 线程被阻塞 → 该线程上排队的所有 task 全部卡住。

**处方**：

```rust
tokio::time::sleep(d).await;                              // 异步 sleep
let data = tokio::fs::read("big.txt").await?;             // 异步 IO
let r = tokio::task::spawn_blocking(|| heavy_cpu_work()).await?;   // ★ 隔离到阻塞线程池
```

**`spawn_blocking` 的闭包要求 `Send + 'static`** —— 又回到了第 22/23 章的规则。

---

## 11. 循环里跨 await 持有 `&mut`

```rust
pub async fn ok(v: &mut Vec<i32>) {
    for i in 0..3 {
        v.push(i);
        yield_now().await;          // ✅ 编译通过
    }
}
```

**实测通过**——因为每轮的 `&mut v` 借用在 `push` 后就结束了。

**但下面这个不行**：

```rust
pub async fn bad(v: &mut Vec<i32>) {
    let first = &mut v[0];
    for _ in 0..3 {
        yield_now().await;
        *first += 1;
        v.push(0);                  // ❌ first 还借着 v
    }
}
```

**根因和同步代码完全一样**（第 05 章）。**async 没有改变借用规则。**

---

## 12. `join_all` / `FuturesUnordered` 与借用

```rust
// ❌ 多个 Future 同时可变借用同一个东西
let futs: Vec<_> = (0..3).map(|i| async { v.push(i) }).collect();   // E0499
futures::future::join_all(futs).await;

// ✅ 分割数据
let chunks: Vec<&mut [i32]> = v.chunks_mut(10).collect();
let futs: Vec<_> = chunks.into_iter().map(|c| async move { process(c).await }).collect();
join_all(futs).await;

// ✅ 或用共享
let v = Arc::new(Mutex::new(vec![]));
let futs: Vec<_> = (0..3).map(|i| { let v = v.clone(); async move { v.lock().await.push(i) } }).collect();
```

**规律**：并发的 Future 之间的借用检查，和 `thread::scope` 里的完全一样（第 23 章 §2.2）——
**同一条借用规则**。

---

## 13. async 里没有 scoped task

同步世界有 `thread::scope`（第 23 章 §2），async 世界**没有稳定的等价物**。

**原因**：`thread::scope` 的安全性依赖"函数返回前一定 join"，
即使 panic 也靠 `Drop` 保证。但 **async task 可以被取消**（Future 被 drop），
而 Rust **不保证 `Drop` 一定执行**（第 03 章 §8 的 leakpocalypse）——
所以没法做出同样的保证。

**现有方案**（都有取舍）：

| 方案 | 说明 |
|---|---|
| `tokio::task::JoinSet` | 能等待一组 task，但仍要求 `'static` |
| `futures::stream::FuturesUnordered` | 在**当前 task 内**并发，不需要 `'static` ★ 常被忽略的好办法 |
| `async_scoped` / `moro` crate | 提供 scoped API，但需要 unsafe 或有使用限制 |
| 改用 `Arc` | 最省事 |

```rust
// ★ FuturesUnordered：在当前 task 内并发，可以借用局部数据
use futures::stream::{FuturesUnordered, StreamExt};
let v = vec![1, 2, 3];
let mut set = FuturesUnordered::new();
for x in &v { set.push(async move { process(x).await }); }    // ✅ 借用 v，不需要 'static
while let Some(r) = set.next().await { println!("{:?}", r); }
```

**注意**：`FuturesUnordered` 是**并发不并行**——所有 Future 在同一个 task、
同一个线程上交替执行。想要并行必须 `spawn`，而 `spawn` 要 `'static`。

---

## 14. 忘了 `.await`

```rust
async fn f() { do_something(); }        // ⚠️ 什么都没发生
```

**Future 是惰性的**——不 poll 就不执行。

**防御**：`Future` 有 `#[must_use]`，所以会有警告：

```
warning: unused implementer of `Future` that must be used
  = note: futures do nothing unless you `.await` or poll them
```

**把它变成错误**：

```toml
# Cargo.toml
[lints.rust]
unused_must_use = "deny"
```

---

## 15. 诊断速查表

| 报错 / 症状 | 陷阱 # | 处方 |
|---|---|---|
| `future cannot be sent between threads safely` | 1, 2 | 收缩作用域（`{}` / `drop`）；换 `Arc`/`tokio::Mutex` |
| `does not live long enough` + `spawn` | 4 | move / `Arc` / 不 spawn / `FuturesUnordered` |
| `E0733: recursion in an async fn requires boxing` | 5 | `Box::pin` 递归调用 |
| `warning: use of async fn in public traits` | 6 | 改成 `-> impl Future + Send` |
| `the trait is not dyn compatible` | 7 | `Pin<Box<dyn Future>>` 或 `async-trait` |
| 数据丢失 / 状态不一致（无编译错误） | 8 | 检查 cancel safety |
| 资源没关（无编译错误） | 9 | 显式 `async fn close(self)` |
| 延迟毛刺 / 吞吐骤降 | 10 | 查有没有阻塞调用；用 `spawn_blocking` |
| `E0499` / `E0502` 在 async 里 | 11, 12 | 和同步代码一样处理 |
| `cannot be unpinned` | — | `Box::pin` / `pin!` |
| 代码"没执行" | 14 | 忘了 `.await` |

---

## 16. 动手实验

### 实验 1：作用域 vs 最后一次使用（★ 必做）

```rust
use std::rc::Rc;
fn assert_send<T: Send>(_: T) {}
async fn y() {}

async fn a() { let r = Rc::new(1); println!("{}", r); y().await; }
async fn b() { { let r = Rc::new(1); println!("{}", r); } y().await; }
async fn c() { let r = Rc::new(1); println!("{}", r); drop(r); y().await; }

fn main() {
    // assert_send(a());    // ← 取消注释
    assert_send(b());
    assert_send(c());
}
```

**实测**：`a` 失败，`b`/`c` 通过。**把这个结果刻在脑子里。**

### 实验 2：cancel safety 的实证

用第 24 章实验 3 的手动 poll 循环，poll 两次就丢弃：

```rust
async fn transfer(log: &mut Vec<&'static str>) {
    log.push("begin");   y().await;
    log.push("debit");   y().await;
    log.push("credit");  log.push("commit");
}
```

**观察 `log` 停在哪里。** 这就是取消发生时的真实状态。

### 实验 3：async trait 的四种写法

把同一个 trait 用四种方式写：
1. `async fn`（有警告）
2. `-> impl Future + Send`
3. `-> Pin<Box<dyn Future + Send + '_>>`
4. `#[async_trait]`

对比：能不能 `dyn`？能不能 `spawn`？代码多长？有没有堆分配？

### 实验 4：找出阻塞调用

在你的 async 项目里搜：

```bash
rg 'std::thread::sleep|std::fs::|std::net::|\.lock\(\)\.unwrap\(\)' --type rust
```

**逐个判断**：这个调用会阻塞多久？在 executor 线程上跑合适吗？

---

## 17. 本章检查清单

- [ ] **知道判据是"作用域跨越 await"而非"最后一次使用"**（陷阱 2）
- [ ] 知道 `MutexGuard` 跨 await 的根因和三种处方
- [ ] **知道 tokio 官方推荐默认用 `std::sync::Mutex`**
- [ ] 知道 async 递归要 `Box::pin`（E0733）
- [ ] 知道公开 trait 里 `async fn` 的 `Send` 问题及替代写法
- [ ] **能判断一个 async 函数是否 cancel-safe**（每个 await 点画一刀）
- [ ] 知道 `select!` 里只能放 cancel-safe 的 Future，及两种绕法
- [ ] 知道 `Drop` 里不能 `.await`，以及当前的最佳实践
- [ ] 知道阻塞调用会卡住整个 executor 线程，要用 `spawn_blocking`
- [ ] 知道 async 没有 scoped task，以及 `FuturesUnordered` 这个替代
- [ ] 知道并发的 Future 之间的借用检查和 `thread::scope` 完全一样

---

**阶段 5 到此结束。** 你现在能处理 Rust 里最复杂的借用场景了。
最后两章讲边界：`unsafe` 之下发生了什么，以及这套系统的理论极限。

下一章：[26 - `unsafe` 不关闭 borrow checker](26-unsafe-aliasing.md)
