# 19 - 内部可变性：类型系统里唯一的合法裂缝

> 本章目标：搞清楚 `Cell` / `RefCell` / `Mutex` 到底"合法"在哪里，
> 以及它们各自的**精确代价**。
> 核心洞察：**它们全都建立在同一个语言原语 `UnsafeCell` 上，而这个原语是编译器认识的。**
> 预计用时：2.5 小时。

---

## 1. 问题：`&T` 的承诺是什么

第 03 章的公理说"共享的不可变"。编译器**利用**这个承诺做优化：

```rust
fn f(x: &i32, g: impl Fn()) -> i32 {
    let a = *x;
    g();              // 可能做任何事
    let b = *x;
    a + b             // ★ 编译器可以优化成 2 * a，因为 *x 不可能变
}
```

在 LLVM IR 层面，Rust 给 `&T` 打上 **`noalias` + `readonly`** 标记
（`&mut T` 打 `noalias`）。这是 Rust 能在某些场景快过 C 的原因之一——
C 里要拿到同样的保证得手写 `restrict`。

**所以问题变成**：如果我需要通过 `&T` 修改数据（缓存、引用计数、观察者模式），
怎么办？直接改就是 **UB**——编译器已经基于"不会变"生成了代码。

---

## 2. `UnsafeCell`：编译器认识的唯一豁免

```rust
#[lang = "unsafe_cell"]              // ★ 语言项，编译器特殊对待
#[repr(transparent)]
pub struct UnsafeCell<T: ?Sized> { value: T }

impl<T: ?Sized> UnsafeCell<T> {
    pub const fn get(&self) -> *mut T { ... }        // ★ 从 &self 拿到 *mut T
}
```

**`UnsafeCell` 的全部魔力**：它告诉编译器
**"这块内存后面的东西可能通过共享引用被修改，不要做 `readonly` 假设"**。

```
&T            → LLVM: noalias readonly     （可以激进优化）
&UnsafeCell<T> → LLVM: 只有 noalias 的部分被移除对该字段的 readonly 假设
&mut T        → LLVM: noalias
```

> ### ★ 记住这一条
> **`UnsafeCell` 是安全 Rust 里唯一能合法地"通过 `&` 修改数据"的途径。**
> **所有**内部可变性类型——`Cell`、`RefCell`、`Mutex`、`RwLock`、`OnceCell`、
> 所有 `Atomic*`——内部都是 `UnsafeCell`。
>
> **反过来**：如果你自己用裸指针从 `&T` 强转出 `*mut T` 去改，
> 即使编译通过、即使跑起来对，**那也是 UB**。第 26 章会用 Miri 抓出来。

**副作用（第 09 章）**：`UnsafeCell<T>` 对 `T` **不变（invariant）**。
这个不变性传染给了所有内部可变性类型——这就是"加了 `RefCell` 之后远处的生命周期报错"的根源。

---

## 3. 内部可变性全家族

### 3.1 全景表

| 类型 | 检查时机 | 开销 | `Send` | `Sync` | 能拿到 `&mut T` 吗 |
|---|---|---|---|---|---|
| `Cell<T>` | **无检查** | 零 | 若 `T: Send` | ❌ | ❌（只能整体换） |
| `RefCell<T>` | **运行时**，违反 panic | 一个计数器 | 若 `T: Send` | ❌ | ✅ `RefMut<T>` |
| `OnceCell<T>` | 只能写一次 | 一个标志 | 若 `T: Send` | ❌ | ❌ |
| `LazyCell<T, F>` | 首次访问时初始化 | 同上 | — | ❌ | ❌ |
| `Mutex<T>` | **运行时**，阻塞 | 系统锁 | 若 `T: Send` | ✅ 若 `T: Send` | ✅ `MutexGuard` |
| `RwLock<T>` | 运行时，阻塞 | 读写锁 | 若 `T: Send` | ✅ 若 `T: Send+Sync` | ✅ |
| `OnceLock<T>` | 只能写一次，线程安全 | 原子标志 | 若 `T: Send` | ✅ 若 `T: Send+Sync` | ❌ |
| `LazyLock<T, F>` | 首次访问时初始化，线程安全 | 同上 | — | ✅ | ❌ |
| `AtomicUsize` 等 | 无（硬件保证） | 原子指令 | ✅ | ✅ | ❌ |
| `UnsafeCell<T>` | **无**，你负责 | 零 | 若 `T: Send` | ❌ | `*mut T` |

**核心区分**：**左边一半（`Cell` 系）不是 `Sync`，右边一半（`Mutex` 系）是。**
`Sync` 的差别就是"能不能把 `&T` 给另一个线程"（第 22 章）。

### 3.2 `Cell<T>`：最便宜的那个

**关键设计**：`Cell` **从不交出内部数据的引用**，只做整体的读/写/替换。
没有引用泄漏 → 不需要任何检查 → **零开销**。

```rust
use std::cell::Cell;
let c = Cell::new(5);
c.set(6);                       // 写
let v = c.get();                // 读（需要 T: Copy）
let old = c.replace(7);         // 换，返回旧值
let old = c.take();             // 换成 Default，返回旧值（需要 T: Default）
let inner = c.into_inner();     // 消耗 Cell，拿出 T
```

**适用**：小的 `Copy` 类型——计数器、标志位、缓存的 `Option<u32>`。

```rust
struct Node {
    value: i32,
    visit_count: Cell<u32>,      // ★ 逻辑上不可变的方法里也能计数
}
impl Node {
    fn value(&self) -> i32 {                       // 注意是 &self
        self.visit_count.set(self.visit_count.get() + 1);
        self.value
    }
}
```

### 3.3 `RefCell<T>`：把借用检查搬到运行时

```rust
use std::cell::RefCell;
let c = RefCell::new(vec![1, 2, 3]);

let r: Ref<Vec<i32>> = c.borrow();          // 共享借用，计数 +1
let m: RefMut<Vec<i32>> = c.borrow_mut();   // 💥 panic: already borrowed

// 不 panic 的版本
if let Ok(r) = c.try_borrow() { }
if let Ok(m) = c.try_borrow_mut() { }
```

**内部实现**（简化）：

```rust
pub struct RefCell<T: ?Sized> {
    borrow: Cell<isize>,        // >0: 有 n 个共享借用；-1: 有一个独占借用；0: 无
    value: UnsafeCell<T>,
}
```

`Ref` / `RefMut` 的 `Drop` 负责把计数减回去。**所以 `RefCell` 的借用规则
和编译期完全一样，只是检查时机不同。**

**⚠️ 三个高频 bug**：

```rust
// bug 1：借用范围太大
let c = RefCell::new(vec![1]);
let len = c.borrow().len();
c.borrow_mut().push(len);            // ✅ 第一个 borrow 是临时值，语句末尾就 drop 了

let b = c.borrow();                  // ← 有名字，活到作用域末尾
c.borrow_mut().push(b.len());        // 💥 panic

// bug 2：递归/重入
fn visit(node: &RefCell<Node>) {
    let n = node.borrow();
    for child in &n.children { visit(child); }    // 如果 child 就是 node → 💥
}

// bug 3：在 Drop 里 borrow
impl Drop for Foo {
    fn drop(&mut self) { self.cell.borrow_mut(); }  // 如果 drop 发生在借用期间 → 💥
}
```

### 3.4 `OnceCell` / `LazyCell` / `OnceLock` / `LazyLock`

**"只写一次"的内部可变性**——最安全的一种，因为不会有借用冲突。

```rust
use std::cell::{OnceCell, LazyCell};
use std::sync::{OnceLock, LazyLock};

// 单线程
let o: OnceCell<u32> = OnceCell::new();
o.set(1).unwrap();
let v = o.get();                            // Option<&u32>
let v = o.get_or_init(|| expensive());      // ★ 最常用

let l: LazyCell<u32> = LazyCell::new(|| expensive());
let v = *l;                                 // 首次解引用时才计算

// 多线程（★ 全局单例的标准做法）
static CONFIG: OnceLock<Config> = OnceLock::new();
fn config() -> &'static Config { CONFIG.get_or_init(|| load_config()) }

static REGEX: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\d+").unwrap());
```

> **`LazyLock` 在 1.80 稳定，取代了 `lazy_static!` 和 `once_cell::sync::Lazy`。**
> 新代码应该用标准库的。（本课程实测：`OnceCell`/`LazyCell`/`OnceLock`/`LazyLock`
> 在 stable 1.96 上全部可用。）

### 3.5 `Mutex` / `RwLock`：`RefCell` 的线程安全版

```rust
use std::sync::Mutex;
let m = Mutex::new(vec![1]);
{
    let mut g = m.lock().unwrap();     // 阻塞直到拿到锁
    g.push(2);
}                                       // 锁在这里释放
```

**Rust 的锁和其它语言的重要区别**：

| | Java/Go/C++ | Rust |
|---|---|---|
| 锁保护什么 | **代码段**（约定） | **数据**（类型强制） |
| 忘了加锁 | 编译通过，运行时数据竞争 | **不可能**——不 `lock()` 拿不到数据 |
| 忘了解锁 | 死锁 | **不可能**——`Drop` 自动解 |
| 加错了锁 | 可能 | **不可能**——数据只属于一个锁 |

```go
// Go：mu 和 data 的关联全靠纪律和注释
var mu sync.Mutex
var data []int          // 注释说：访问前必须持有 mu
```

```rust
// Rust：类型上就绑定了
let data = Mutex::new(Vec::<i32>::new());     // 拿不到锁就碰不到 data
```

**`unwrap()` 是干什么的**：`lock()` 返回 `Result`，因为持锁的线程 panic 会让锁"中毒
（poisoned）"。**中毒是一个信号**：被保护的数据可能处于不一致状态。
生产代码应该显式处理，或用 `parking_lot`（不做中毒检查，更快）。

### 3.6 原子类型

```rust
use std::sync::atomic::{AtomicUsize, Ordering};
static COUNTER: AtomicUsize = AtomicUsize::new(0);
COUNTER.fetch_add(1, Ordering::Relaxed);
```

**最便宜的线程安全内部可变性**，但只支持机器字大小的整数/指针，
且内存序（`Ordering`）本身是个大坑（超出本课程范围）。

---

## 4. 决策表：该用哪个

```
需要通过 &self 修改数据
   │
   ├─ 跨线程吗？
   │    │
   │    ├─ 不跨（单线程 / 都在一个 task 内）
   │    │     ├─ 只写一次（配置、懒初始化） ──► OnceCell / LazyCell
   │    │     ├─ 小的 Copy 类型（计数器/标志）──► Cell         ★ 零开销
   │    │     └─ 需要 &mut 内部数据          ──► RefCell       ⚠️ 运行时 panic
   │    │
   │    └─ 跨线程
   │          ├─ 只写一次（全局单例）        ──► OnceLock / LazyLock  ★ 首选
   │          ├─ 整数/指针的简单操作          ──► Atomic*      ★ 最快
   │          ├─ 读多写少                    ──► RwLock
   │          └─ 一般情况                    ──► Mutex        ★ 默认选它
   │
   └─ 其实不需要？──► 回到第 18 章手法 1–11
```

> ### ★ 选择建议
> **`Mutex` 是跨线程场景的默认选择。** 不要一上来就用 `RwLock`——
> 它在写少读多且临界区长时才划算，否则原子操作的开销和写者饥饿会让它更慢。
>
> **`RefCell` 是单线程场景的最后选择**，不是第一选择。

---

## 5. 代价清单（★ 必须清楚）

用内部可变性之前，确认你接受这四条：

### 代价 1：编译期错误变成运行时 panic

```rust
// 编译期版本：改代码
let a = &mut v[0]; let b = &mut v[1];      // ❌ E0499，你必须改

// 运行时版本：上线后炸
let a = c.borrow_mut(); let b = c.borrow_mut();   // ✅ 编译通过，💥 运行时
```

**这是最大的代价。** 你把一个"100% 在开发期发现"的问题变成了
"可能在生产环境的某个罕见路径上发现"的问题。

### 代价 2：型变塌了（第 09 章）

```rust
struct A<'a> { data: Vec<&'a str> }             // 对 'a 协变 ✅
struct B<'a> { data: RefCell<Vec<&'a str>> }    // 对 'a 不变 ❌
```

**症状**：加了 `RefCell` 之后，**完全不相关的地方**冒出 `lifetime may not live long enough`。

### 代价 3：`Sync` 没了

```rust
fn is_sync<T: Sync>() {}
is_sync::<Cell<i32>>();     // ❌ error[E0277]: `Cell<i32>` cannot be shared between threads safely
```

一旦结构体里有 `Cell`/`RefCell`，**整个结构体不再是 `Sync`**，
于是不能 `&` 跨线程、不能放进多线程 executor 的 Future 里（第 25 章）。

### 代价 4：性能

| | 开销 |
|---|---|
| `Cell` | 零 |
| `RefCell` | 一次计数器读写 + 分支（可预测，很便宜） |
| `Atomic` | 一条原子指令（不算便宜，尤其是竞争时） |
| `Mutex` | 无竞争时约几十纳秒；有竞争时涉及系统调用 |
| `RwLock` | 比 `Mutex` 贵（要维护读者计数） |

**注意**：`RefCell` 的开销其实很小。它的问题**不是性能，是 panic 风险**。

---

## 6. 正当用途（这些场景内部可变性是**对的**）

### 6.1 memoization（逻辑不可变，内部缓存）

```rust
use std::cell::RefCell;
use std::collections::HashMap;

struct Solver { cache: RefCell<HashMap<u64, u64>> }
impl Solver {
    fn fib(&self, n: u64) -> u64 {              // ★ &self，语义上是纯函数
        if let Some(&v) = self.cache.borrow().get(&n) { return v; }
        let v = if n < 2 { n } else { self.fib(n - 1) + self.fib(n - 2) };
        self.cache.borrow_mut().insert(n, v);
        v
    }
}
```

**这段是安全的**（两个 edition 下实测都正常）——因为 `borrow()` 的临时 `Ref`
在 `if let` 语句结束时就没了，递归调用发生在**之后**。

**但把 `borrow_mut()` 挪进 `else` 分支就完全不同了**：

```rust
fn get(&self, n: u64) -> u64 {
    if let Some(&v) = self.cache.borrow().get(&n) { v } else {
        let v = n * 2;
        self.cache.borrow_mut().insert(n, v);   // ★ 2021：Ref 还活着 → 💥
        v
    }
}
```

**实测**（同一份代码，同一个编译器）：

```
edition 2021: thread 'main' panicked at memo.rs:7:24:
              RefCell already borrowed          ← 进程退出，无输出
edition 2024: 42
```

> ### ★ 这是本课程"临时值作用域"那条知识的真实价值
> 一个看起来完全正常的缓存函数，**在 2021 edition 下必然 panic，在 2024 下完全正常**。
> 而且这个 panic 只在**缓存未命中**的路径上发生——在测试里很容易漏掉。
>
> **如果你的项目还在 2021 edition，全局搜一下 `if let ... borrow()` 这个模式。**

**2021 下的正确写法**：

```rust
let cached = self.cache.borrow().get(&n).copied();      // 显式结束借用
if let Some(v) = cached { return v; }
```

### 6.2 全局配置 / 单例

```rust
static CONFIG: OnceLock<Config> = OnceLock::new();
pub fn config() -> &'static Config { CONFIG.get_or_init(load_config) }
```

### 6.3 观察者 / 回调注册

```rust
struct EventBus { handlers: RefCell<Vec<Box<dyn Fn(&Event)>>> }
impl EventBus {
    fn subscribe(&self, f: impl Fn(&Event) + 'static) {   // ★ &self，方便调用方
        self.handlers.borrow_mut().push(Box::new(f));
    }
}
```

⚠️ 这里有经典的重入 bug：如果某个 handler 在被调用时又调 `subscribe` → 💥。
**解法**：`emit` 时先 `let hs = self.handlers.borrow(); ` 改成先克隆一份，或用 `try_borrow_mut`。

### 6.4 单线程图结构

```rust
use std::rc::{Rc, Weak};
use std::cell::RefCell;
struct Node {
    value: i32,
    parent: RefCell<Weak<Node>>,
    children: RefCell<Vec<Rc<Node>>>,
}
```

**但先考虑第 18 章手法 11/12（索引 / arena）**——通常更好。

---

## 7. 动手实验

### 实验 1：亲手触发每一种 panic

```rust
use std::cell::RefCell;

fn main() {
    let c = RefCell::new(vec![1]);

    // A：双重可变借用
    // let a = c.borrow_mut(); let b = c.borrow_mut();

    // B：共享 + 可变
    // let a = c.borrow(); let b = c.borrow_mut();

    // C：临时值活太久（在 2021 edition 下试）
    // if let Some(x) = c.borrow().first() { c.borrow_mut().push(*x); }

    // D：递归重入
    // fn f(c: &RefCell<i32>) { let g = c.borrow(); f(c); }

    // 每次只取消注释一个，观察 panic 信息
}
```

### 实验 2：`Sync` 的传染

```rust
use std::cell::RefCell;
fn is_sync<T: Sync>() {}

struct A { data: Vec<i32> }
struct B { data: RefCell<Vec<i32>> }
struct C { data: std::sync::Mutex<Vec<i32>> }

fn main() {
    is_sync::<A>();     // ?
    is_sync::<B>();     // ?
    is_sync::<C>();     // ?
}
```

### 实验 3：`Mutex` vs Go 的 `sync.Mutex`

用 Go 写一个"忘了加锁"的 bug：

```go
var mu sync.Mutex
var counter int
func inc() { counter++ }        // 忘了 mu.Lock()
```

**然后试着在 Rust 里犯同样的错**。你会发现**做不到**——
`Mutex::new(0)` 之后，不 `lock()` 根本拿不到那个 `0`。

### 实验 4：`Cell` 的零开销

```rust
use std::cell::Cell;
pub fn with_cell(c: &Cell<u32>) { c.set(c.get() + 1); }
pub fn with_plain(c: &mut u32) { *c += 1; }
```

```bash
rustc --edition 2024 -O --crate-type=lib --emit=asm -o cell.s cell.rs
```

（`#[no_mangle]` 在 edition 2024 里要写成 `#[unsafe(no_mangle)]`。）

**实测结果**（aarch64，`rustc 1.96.0 -O`）：

```asm
_with_cell:                 _with_plain:
    ldr  w8, [x0]               ldr  w8, [x0]
    add  w8, w8, #1             add  w8, w8, #1
    str  w8, [x0]               str  w8, [x0]
    ret                         ret
```

**逐条指令完全相同。`Cell` 确实是零开销。**

---

## 8. 本章检查清单

- [ ] 知道 `&T` 在 LLVM 层面意味着 `noalias readonly`
- [ ] **知道 `UnsafeCell` 是唯一的合法豁免，且是语言项**
- [ ] 知道所有内部可变性类型内部都是 `UnsafeCell`
- [ ] 知道 `UnsafeCell<T>` 对 `T` 不变，以及这个不变性的传染后果
- [ ] 能说出 `Cell` 为什么零开销（不泄漏引用）
- [ ] 知道 `RefCell` 的内部实现（一个计数器 + `UnsafeCell`）
- [ ] 能背出决策表：单线程 vs 跨线程 × 只写一次 / Copy / 一般
- [ ] **知道内部可变性的四项代价，尤其是"编译期→运行时"和"型变塌了"**
- [ ] 知道 Rust 的锁保护的是**数据**不是代码段
- [ ] 知道 `LazyLock`（1.80+）取代了 `lazy_static!`

---

## 9. 常见坑

| 现象 | 原因 | 处方 |
|---|---|---|
| `RefCell already borrowed` / `already mutably borrowed` | `RefCell` 借用重叠 | 缩小 `borrow()` 范围；把结果 `.copied()`/`.cloned()` 出来 |
| 递归里 `RefCell` panic | 重入 | 用 `try_borrow_mut`；或重构成非递归 |
| `if let c.borrow()...` 里 panic（2021） | 临时值活到整个 `if let` | 升 edition 2024；或拆成独立语句 |
| 加了 `RefCell` 后远处报生命周期错 | 型变塌了 | 见第 09 章；考虑让结构体拥有数据 |
| Future 不是 `Send` | 结构体里有 `Rc`/`RefCell`/`Cell` | 换 `Arc`/`Mutex`；或确保不跨 `await` |
| `Mutex` 死锁 | 同一线程重复 lock；或锁序不一致 | Rust 的 `Mutex` **不可重入**；统一锁序 |
| `lock().unwrap()` panic | 锁中毒（持锁线程 panic 过） | 显式处理 `PoisonError`；或用 `parking_lot` |
| 用 `RwLock` 反而更慢 | 读写锁开销 + 写者饥饿 | 默认用 `Mutex`，profile 之后再换 |
| 从 `&T` 强转 `*mut T` 去改 | **UB**，即使跑起来对 | 必须用 `UnsafeCell`。用 Miri 验证（第 26 章） |

---

下一章：[20 - 图 / 树 / 链表到底怎么写](20-data-structures.md)
