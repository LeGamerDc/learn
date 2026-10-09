# 23 - 线程与借用

> 本章目标：把借用规则落到具体的并发原语上。
> 重点：`'static` 约束的来龙去脉、scoped thread 为什么能豁免、
> **以及 borrow checker 明确不管的那些并发问题**。
> 预计用时：2.5 小时。

---

## 1. `thread::spawn` 的三道门

```rust
pub fn spawn<F, T>(f: F) -> JoinHandle<T>
where
    F: FnOnce() -> T + Send + 'static,
    T: Send + 'static,
```

### 1.1 `'static` 的真正理由

**不是**"线程要永远运行"，而是：

> **`spawn` 返回之后，新线程和调用者是两条独立的控制流。
> 编译器无法证明新线程会在调用者的任何局部变量销毁之前结束。**

```rust
fn f() {
    let v = vec![1, 2, 3];
    std::thread::spawn(|| println!("{:?}", v));    // ❌ E0373
}                                                   // v 在这里销毁——线程可能还在跑
```

**实测报错**：

```
error[E0373]: closure may outlive the current function, but it borrows `v`,
              which is owned by the current function
help: to force the closure to take ownership of `v` (and any other referenced variables),
      use the `move` keyword
```

**注意**：`JoinHandle` 的存在**不改变**这一点——因为你可以不 join
（`drop(handle)` 之后线程会 detach 继续跑）。

### 1.2 三种通过 `'static` 的方式

```rust
// 1. move：把所有权交给线程
let v = vec![1, 2, 3];
std::thread::spawn(move || println!("{:?}", v));

// 2. clone 一份
let v2 = v.clone();
std::thread::spawn(move || println!("{:?}", v2));
println!("{:?}", v);

// 3. Arc 共享
let a = Arc::new(v);
let a2 = Arc::clone(&a);
std::thread::spawn(move || println!("{:?}", a2));
println!("{:?}", a);
```

---

## 2. scoped thread：借用的正门

```rust
fn f() {
    let v = vec![1, 2, 3];
    let mut sum = 0;
    std::thread::scope(|s| {
        s.spawn(|| println!("{:?}", v));       // ✅ 共享借用
        s.spawn(|| println!("len={}", v.len()));
    });                                         // ★ 这里保证所有线程已 join
    println!("{:?}", v);                        // ✅ v 还能用
    sum += 1;
}
```

### 2.1 它为什么安全

```rust
pub fn scope<'env, F, T>(f: F) -> T
where F: for<'scope> FnOnce(&'scope Scope<'scope, 'env>) -> T
```

第 10 章 §4 讲过：**`for<'scope>` 让调用方无法命名 `'scope`**，
所以闭包没法把 `&Scope` 泄漏出去；而 `scope` 函数在返回前会 join 所有未 join 的线程。

**关键实现细节**：`Scope` 内部有一个计数器和 `Drop`，
即使 `f` panic 了也会等待所有子线程——**这就是 1.0 之前 `thread::scoped`
被移除的那个问题的正确解法**（第 03 章 §8 的 "leakpocalypse"）。

### 2.2 scoped thread 里的可变借用

```rust
let mut a = vec![1, 2, 3];
let mut b = vec![4, 5, 6];
std::thread::scope(|s| {
    s.spawn(|| a.push(0));       // ✅ 独占借用 a
    s.spawn(|| b.push(0));       // ✅ 独占借用 b（不同 place）
});
```

```rust
let mut v = vec![1, 2, 3];
std::thread::scope(|s| {
    s.spawn(|| v.push(0));
    s.spawn(|| v.push(1));       // ❌ E0499：两个线程都要 &mut v
});
```

> ### ★ 这是本章最漂亮的一点
> **同一条借用规则，在 scoped thread 里自动变成了"并发安全"的检查。**
> 编译器不需要理解"线程"这个概念——它只是在做和第 05 章一模一样的借用检查。

### 2.3 分割数据并行处理

```rust
let mut data = vec![0u32; 1000];
let chunks: Vec<&mut [u32]> = data.chunks_mut(250).collect();   // ★ 第 18 章手法 8
std::thread::scope(|s| {
    for chunk in chunks {
        s.spawn(move || { for x in chunk.iter_mut() { *x += 1; } });
    }
});
```

**`chunks_mut` 在签名层面保证了不相交** → 每个线程拿到独立的 `&mut [u32]` → 编译通过。
**这就是数据并行的类型安全基础**，`rayon` 的 `par_chunks_mut` 是同一个原理。

---

## 3. `Arc<Mutex<T>>`：共享可变状态

```rust
use std::sync::{Arc, Mutex};

let counter = Arc::new(Mutex::new(0));
let mut handles = vec![];
for _ in 0..10 {
    let c = Arc::clone(&counter);
    handles.push(std::thread::spawn(move || {
        let mut n = c.lock().unwrap();
        *n += 1;
    }));                                     // ★ guard 在闭包结束时释放
}
for h in handles { h.join().unwrap(); }
println!("{}", *counter.lock().unwrap());    // 10
```

**为什么需要两层**：

| 层 | 解决什么 |
|---|---|
| `Arc` | **多个所有者**（每个线程都要持有）+ 原子引用计数 |
| `Mutex` | **共享可变**（`&Mutex<T>` 能拿到 `&mut T`）+ 同步 |

**只用一层不行**：
- `Arc<T>` → 只能读（`Arc` 的 `Deref` 给 `&T`）
- `Mutex<T>` → 没法让多个线程持有（不满足 `'static` 或者所有权只有一份）

> ### ⚠️ `Arc<Mutex<T>>` 常常是设计的最后手段
> **先问：能不能改成消息传递？** 见 §4。
> `Arc<Mutex<T>>` 的问题不是编译不过，是**锁竞争 + 死锁风险**——
> 而这两个 borrow checker 都不管。

---

## 4. Channel：把并发变成所有权转移

```rust
use std::sync::mpsc;

let (tx, rx) = mpsc::channel();
for i in 0..3 {
    let tx = tx.clone();
    std::thread::spawn(move || { tx.send(i * 10).unwrap(); });   // ★ 值被移动进 channel
}
drop(tx);                                    // 关掉最后一个发送端
for v in rx { println!("{}", v); }           // 接收直到所有 tx 都 drop
```

**核心洞察**：

> **`send(v)` 是一次所有权转移。** 值离开发送线程，进入接收线程。
> **任何时刻只有一个线程拥有它** → 从根本上不可能有数据竞争。

**这就是 Go 那句 "Don't communicate by sharing memory; share memory by communicating"
在 Rust 里的类型级实现**——Go 靠纪律（channel 里传指针照样能出竞争），
Rust 靠 `Send` + 移动语义强制执行。

**channel 的选择**：

| 场景 | 用什么 |
|---|---|
| 标准库，多生产者单消费者 | `std::sync::mpsc` |
| 需要多消费者 / 更快 | `crossbeam-channel` |
| async | `tokio::sync::mpsc` / `flume` |
| 单值一次性 | `std::sync::mpsc::sync_channel(0)` / `tokio::sync::oneshot` |

---

## 5. rayon：数据并行

```rust
use rayon::prelude::*;

let v: Vec<u64> = (0..1_000_000).collect();
let sum: u64 = v.par_iter().sum();                     // 并行求和
let mut data = vec![0u32; 1000];
data.par_chunks_mut(100).for_each(|c| { for x in c { *x += 1; } });
```

**rayon 为什么是安全的**：它的所有 API 都建立在
**"借用规则已经保证了不相交"** 这个前提上：

- `par_iter()` 要求 `&self` → 只读，任意并发 ✅
- `par_iter_mut()` 内部用 `split_at_mut` 递归分割 → 每个任务拿到不相交的 `&mut` ✅
- 闭包要求 `Send + Sync` → 捕获的东西必须线程安全 ✅

**它不需要任何运行时检查。** 又一次：**并发安全是借用规则的免费副产品。**

---

## 6. ★ borrow checker **不管**的三类并发问题

这一节和前面同样重要。**编译通过 ≠ 并发正确。**

### 6.1 死锁

```rust
let a = Mutex::new(1);
let b = Mutex::new(2);

// 线程 1
let _ga = a.lock().unwrap();
let _gb = b.lock().unwrap();

// 线程 2
let _gb = b.lock().unwrap();      // 💥 锁序不一致 → 死锁
let _ga = a.lock().unwrap();
```

**编译完全通过。** 借用检查不理解"锁"这个概念——`Mutex` 只是个普通类型。

**Rust 特有的死锁陷阱**：

```rust
// 1. 同一线程重复加锁（Rust 的 Mutex 不可重入！）
let g1 = m.lock().unwrap();
let g2 = m.lock().unwrap();      // 💥 自锁

// 2. 临时值活太久（第 12 章）
match m.lock().unwrap().len() {
    0 => { m.lock().unwrap().push(1); }    // 💥 scrutinee 的 guard 还活着
    _ => {}
}

// 3. 2021 edition 的 if let（第 11 章第 21 条）
if let Some(v) = *rw.read().unwrap() { v } else { *rw.write().unwrap() = ...; }  // 💥
```

**防御手段**：
- 统一锁序（给锁编号，永远按序加）
- 缩小临界区（第 18 章手法 3）
- `parking_lot::Mutex` 有 `try_lock_for`
- `tokio::sync::Mutex` 在 async 里（第 25 章）

### 6.2 竞态条件（race condition ≠ data race）

```rust
// TOCTOU：检查和使用之间状态变了
if map.lock().unwrap().contains_key(&k) {       // 检查
    // ← 另一个线程可能在这里删掉了 k
    let v = map.lock().unwrap()[&k];            // 💥 panic
}

// ✅ 一次操作里完成
if let Some(v) = map.lock().unwrap().get(&k) { }
```

**Rust 保证的是"无 data race"（无未同步的并发内存访问），
不是"无 race condition"（逻辑上的时序错误）。**

这两个术语的混淆非常普遍，务必分清：

| | data race | race condition |
|---|---|---|
| 定义 | 未同步的并发访问，至少一个写 | 结果依赖于事件时序 |
| 是 UB 吗 | ✅ 是 | ❌ 不是，只是逻辑错误 |
| Rust 保证 | ✅ 编译期排除 | ❌ 不管 |

### 6.3 内存序（memory ordering）

```rust
use std::sync::atomic::{AtomicBool, Ordering};
static FLAG: AtomicBool = AtomicBool::new(false);
FLAG.store(true, Ordering::Relaxed);      // ★ Relaxed 不保证和其它操作的顺序
```

用错 `Ordering` 会产生极难复现的 bug。**borrow checker 一点忙都帮不上。**

**建议**：不确定就用 `Ordering::SeqCst`（最强、最慢但最安全），
或者干脆用 `Mutex`。原子操作的内存序是一个独立的深水区。

---

## 7. 诊断速查

| 报错 | 含义 | 处方 |
|---|---|---|
| `E0373: closure may outlive the current function` | 闭包借用了局部变量，但要求 `'static` | 加 `move`；或用 `thread::scope` |
| `E0277: Rc<T> cannot be sent` | 类型不是 `Send` | 换 `Arc`；见第 22 章替换表 |
| `E0277: Cell<T> cannot be shared` | 类型不是 `Sync` | 换 `Mutex`/`Atomic` |
| `E0499` 在 scope 内 | 两个线程都要 `&mut` 同一处 | `chunks_mut`/`split_at_mut` 分割；或用 `Mutex` |
| `E0502` 在 scope 内 | 一个 `&` 一个 `&mut` | 同上 |
| `E0505: cannot move out of X because it is borrowed` | 在 scope 里 move 了被借的东西 | 调整顺序 |

---

## 8. 动手实验

### 实验 1：三种方式并行求和

```rust
// 目标：把 vec![1u64; 1_000_000] 分 4 份并行求和

// 方式 A：thread::spawn + Arc（分片用 chunks + to_vec）
// 方式 B：thread::scope + chunks（★ 零拷贝）
// 方式 C：Arc<Mutex<u64>> 累加（★ 故意做慢，体会锁竞争）
```

**任务**：三种都实现，用 `--release` 计时对比。
**预期**：B 最快，C 慢一个数量级（锁竞争）。

<details><summary>方式 B 参考</summary>

```rust
fn parallel_sum(v: &[u64]) -> u64 {
    let n = (v.len() + 3) / 4;
    let mut parts = vec![0u64; 4];
    std::thread::scope(|s| {
        for (chunk, out) in v.chunks(n).zip(parts.iter_mut()) {
            s.spawn(move || { *out = chunk.iter().sum(); });
        }
    });
    parts.iter().sum()
}
```

★ 注意 `parts.iter_mut()` 提供了不相交的 `&mut u64`，
所以每个线程写自己那份，**完全不需要锁**。

</details>

### 实验 2：亲手制造死锁并诊断

```rust
use std::sync::Mutex;
fn main() {
    let m = Mutex::new(vec![1, 2, 3]);
    match m.lock().unwrap().len() {
        0 => { m.lock().unwrap().push(1); }
        n => { println!("{}", n); m.lock().unwrap().push(1); }    // 💥
    }
    println!("done");
}
```

**实测**：

```
$ ./dl
3                       ← 打印了，说明进了 match 分支
<挂住>                   ← 3 秒后被 kill，exit=137

$ ./dl2                 # 改成先 let n = m.lock().unwrap().len();
3
done                    ← exit=0
```

然后：
1. 确认是死锁不是死循环（CPU 占用为 0）
2. 改成"先取出 `len` 再 match"，确认修好
3. **解释为什么 `match` 的 scrutinee 临时值活到整个 `match` 结束**（第 12 章 §4.2）

### 实验 3：scoped thread 的借用检查

```rust
fn main() {
    let mut v = vec![1, 2, 3];
    std::thread::scope(|s| {
        s.spawn(|| println!("{:?}", v));     // A
        s.spawn(|| v.push(4));               // B  ← 和 A 冲突吗？
    });
}
```

预测结果，然后编译验证。再试：两个都是 `println!` 呢？

### 实验 4：data race vs race condition

写两段代码：
1. 一段有 **data race** 的（在 Rust 里你会发现**写不出来**，除非用 `unsafe`）
2. 一段有 **race condition** 但编译完全通过的（TOCTOU）

**这个对比能让你永远记住两者的区别。**

---

## 9. 本章检查清单

- [ ] 知道 `spawn` 要求 `'static` 的真正理由（编译器不知道线程何时结束）
- [ ] 知道 `JoinHandle` 不改变这个要求（可以不 join）
- [ ] 能解释 `thread::scope` 为什么能豁免，以及 `for<'scope>` 的作用
- [ ] **知道 scoped thread 里的并发安全检查就是普通的借用检查**
- [ ] 知道 `chunks_mut` / `split_at_mut` 是数据并行的类型安全基础
- [ ] 能说出 `Arc<Mutex<T>>` 两层各自解决什么
- [ ] 知道 channel 的本质是所有权转移
- [ ] 知道 rayon 的安全性来自借用规则，不需要运行时检查
- [ ] **能区分 data race 和 race condition，知道 Rust 只保证前者**
- [ ] 知道 Rust 的 `Mutex` **不可重入**
- [ ] 知道三个 Rust 特有的死锁陷阱（重复加锁、临时值、2021 的 `if let`）

---

## 10. 常见坑

| 现象 | 原因 | 处方 |
|---|---|---|
| `closure may outlive` | 借用了局部变量 | `move`；或 `thread::scope` |
| 加了 `move` 之后外面不能用了 | 所有权转移了 | `clone`；或 `Arc`；或 `scope` |
| `Arc<T>` 不能改 | `Arc` 只给 `&T` | `Arc<Mutex<T>>` |
| 死锁 | 锁序 / 重入 / 临时值 | 统一锁序；缩小临界区；拆 scrutinee |
| `match m.lock()...` 挂住 | scrutinee 的 guard 活到 match 结束 | **永远**先 `let n = ...;` |
| 用 `Mutex` 性能很差 | 锁竞争 | 改成分片（每线程独立）+ 最后合并；或用 channel |
| 结果不确定但没有 data race | race condition | 把"检查 + 使用"合并成一次原子操作 |
| `Ordering::Relaxed` 导致诡异 bug | 内存序 | 不确定就 `SeqCst`；或用 `Mutex` |
| 线程 panic 后锁中毒 | `PoisonError` | 显式处理；或用 `parking_lot` |

---

下一章：[24 - async 与借用](24-async-borrowing.md)
