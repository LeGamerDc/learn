# 18 - 解法总表：16 种手法及其代价

> 本章目标：给你一张**今天就能用**的手册。每种手法配：适用场景、代码、**代价**、什么时候**不该**用。
> 这是本课程最实用的一章，建议打印出来放手边。
> 所有代码均实测编译通过（`rustc 1.96.0`，edition 2024）。
> 预计用时：3 小时。

---

## 0. 先走判断流程

**不要先找手法，先分类。** 90% 的时间浪费在给错误的问题找解法。

```
借用错误
   │
   ├─ ① 运行时真的有两条路径访问同一份数据且至少一条在写？
   │      └─ 是 ──► 编译器是对的。回到设计（不是本章内容，见第 21 章）
   │
   ├─ ② 冲突的两个操作能不能"错开时间"？
   │      └─ 能 ──► 手法 1–3（缩小 region）★ 最便宜
   │
   ├─ ③ 冲突的两个操作访问的是不相交的 place，但签名没说清？
   │      └─ 是 ──► 手法 4–8（表达不相交）★ 首选
   │
   ├─ ④ 需要"暂时把值搬出来"？
   │      └─ 是 ──► 手法 9–10（mem::take 家族）
   │
   ├─ ⑤ 数据结构本身需要共享 / 图状 / 自引用？
   │      └─ 是 ──► 手法 11–14（换数据结构）
   │
   └─ ⑥ 上面都不行？
          └─ 手法 15–16（运行时检查 / unsafe 封装）★ 最后手段
```

---

## 第一组：缩小 region（最便宜，优先尝试）

### 手法 1：把"最后一次使用"提前

**原理**：借用的 region 由最后一次使用决定（第 07 章）。挪动它就缩小了 region。

```rust
// ❌
let first = &v[0];
v.push(4);
println!("{}", first);

// ✅ 把使用提到冲突之前
let first = &v[0];
println!("{}", first);
v.push(4);

// ✅ 或者把值拷出来，借用当场结束
let first = v[0];          // i32 是 Copy
v.push(4);
println!("{}", first);
```

**代价**：几乎为零。**这是第一个该试的手法。**

**诊断信号**：错误信息里的 `` borrow later used here `` 指向的那一行，就是你要挪的那行。

### 手法 2：拷贝需要的部分

```rust
// ❌ 持有 &Widget 的同时要 &mut self
let w = &s.widgets[0];
s.log.push(w.name.clone());          // 其实这个能过（不同字段）

// 但如果经过方法就不行了，那就先把需要的值取出来
let name = s.get_widget(0).name.clone();     // 借用在这一句结束
s.log_mut().push(name);
```

**代价**：一次 clone / copy。
**什么时候不该用**：热路径上克隆大对象。此时改用手法 4–8。

> **再次强调（第 04 章）**：`.clone()` 不是罪。**不知道为什么要 clone 才是问题。**

### 手法 3：用块 `{}` 收缩 `Drop` 类型的作用域

**只对有 `Drop` 实现的类型有效**（`MutexGuard`、`RefMut`、`File`、`Transaction`…）。
普通借用 NLL 已经帮你缩了，加块没用。

```rust
// ❌ 锁持有到函数末尾
let guard = m.lock().unwrap();
let n = guard.len();
expensive_computation();             // 还持着锁！
println!("{}", n);

// ✅
let n = { m.lock().unwrap().len() };  // 或 let n = m.lock().unwrap().len();
expensive_computation();
println!("{}", n);

// ✅ 或显式 drop
let guard = m.lock().unwrap();
let n = guard.len();
drop(guard);
expensive_computation();
```

**代价**：零。
**⚠️ 注意**：`let _ = m.lock()` **不是**这个手法（第 11 章第 1 条），那是 bug。

---

## 第二组：表达"不相交"（★ 最常用）

### 手法 4：解构（★★★★★ 本组首选）

**原理**：模式解构让编译器在**语法层面**看到不相交。

```rust
struct App { widgets: Vec<Widget>, log: Vec<String>, counter: u32 }

// ❌ 经过方法
fn bad(a: &mut App) { for w in &a.widgets { a.log.push(w.name.clone()); a.counter += 1; } }
//                                          ^^^^^ 如果 log/counter 是通过方法访问就会失败

// ✅ 解构：一次性把字段全部借出来
fn good(a: &mut App) {
    let App { widgets, log, counter } = a;
    for w in widgets.iter() {
        log.push(w.name.clone());
        *counter += 1;
    }
}
```

**代价**：零运行时开销，只是写法变了。
**局限**：只能在你能看到字段的地方用（同 crate / `pub` 字段）。

> ### ★ 这是今天最接近 view types（第 17 章）的写法
> 解构一次，之后每个字段都是独立的 `&mut`，编译器完全知道它们不相交。
> **遇到"方法借走整个 self"时，第一个想到它。**

### 手法 5：splitter 方法

**适用**：字段是私有的，但你想让调用方能同时用。

```rust
impl App {
    pub fn split(&mut self) -> (&mut Vec<Widget>, &mut Vec<String>) {
        (&mut self.widgets, &mut self.log)
    }
}

fn use_it(a: &mut App) {
    let (w, l) = a.split();
    for x in w.iter() { l.push(x.name.clone()); }
}
```

**代价**：API 表面变大；每加一个字段组合就要加一个方法（组合爆炸）。
**什么时候不该用**：字段超过 3–4 个时会失控。此时用手法 6 或 7。

### 手法 6：拆成自由函数，参数只取需要的字段

```rust
fn log_all(widgets: &[Widget], log: &mut Vec<String>) {
    for x in widgets { log.push(x.name.clone()); }
}

fn use_it(a: &mut App) { log_all(&a.widgets, &mut a.log); }
```

**代价**：失去方法语法；参数列表变长。
**优点**：**签名精确地说明了它碰什么**——这正是 view types 想在语言层面做的事。
**推荐**：内部逻辑函数用这个，公开 API 保留方法。

### 手法 7：重组结构体

```rust
// ❌ 平铺
struct App { widgets: Vec<Widget>, log: Vec<String>, counter: u32, config: Config }

// ✅ 按"一起被访问"分组
struct App { data: Data, obs: Observability }
struct Data { widgets: Vec<Widget>, config: Config }
struct Observability { log: Vec<String>, counter: u32 }

impl App {
    fn process(&mut self) { self.data.process(&mut self.obs); }   // ✅ 两个字段不相交
}
```

**代价**：结构调整成本；多一层间接（`a.obs.log` 而非 `a.log`）。
**优点**：**通常也是更好的设计**——"一起被访问的数据应该放在一起"是个独立于 Rust 的好原则。

> ### 一个有价值的观察
> **借用检查器经常在逼你做正确的模块划分。**
> 如果你发现一个结构体的字段总是需要各种奇怪的组合借出来，
> 很可能它承担了太多职责。

### 手法 8：用签名声明分割的标准库 API

```rust
// 切片
let (l, r) = v.split_at_mut(mid);
let [a, b] = v.get_disjoint_mut([0, 1]).unwrap();       // 1.86+
let (first, rest) = v.split_first_mut().unwrap();
for chunk in v.chunks_mut(3) { }
let mut it = v.iter_mut();
let (a, b) = (it.next().unwrap(), it.next().unwrap());

// HashMap
let [a, b] = m.get_disjoint_mut([&k1, &k2]);            // 1.86+
```

**代价**：零（这些函数内部用 `unsafe` 一次性证明了不相交，你免费享用）。
**记住**：**下标永远不行**（第 11 章第 9 条）。想按下标分割就用这些 API。

---

## 第三组：把值搬出来

### 手法 9：`mem::take` / `mem::replace` / `mem::swap`

**原理**：在只有 `&mut` 的情况下合法地把值搬出来——**同时放一个替代品进去**，
保证那个位置始终是有效值。

```rust
// ❌ 只有 &mut self，但 into_iter 需要所有权
impl App {
    fn filter(&mut self) {
        self.widgets = self.widgets.into_iter().filter(|w| !w.name.is_empty()).collect();
        //             ^^^^^^^^^^^^ E0507
    }
}

// ✅
impl App {
    fn filter(&mut self) {
        let old = std::mem::take(&mut self.widgets);     // 留一个空 Vec
        self.widgets = old.into_iter().filter(|w| !w.name.is_empty()).collect();
    }
}
```

**三兄弟**：

```rust
mem::replace(dest, src) -> T      // 放 src 进去，把旧值拿出来
mem::take(dest) -> T              // = replace(dest, T::default())，需要 T: Default
mem::swap(a, b)                   // 交换两处
```

**代价**：中间状态里那个位置是"默认值"。**如果中途 panic，值就丢了**——
这在需要异常安全的代码里要小心。

**变体：`Option::take`**

```rust
struct Node { next: Option<Box<Node>> }
let next = node.next.take();      // 拿走，留 None
```

字段本身语义上就是"可能没有"时，用 `Option<T>` + `take()` 比 `mem::take` 更清晰。

### 手法 10：把"查找 + 修改"打包成一次操作

**原理**：两次借用打不过，就合并成一次。

```rust
// ❌（stable 上）借用要跨出函数
fn get_or_insert(m: &mut HashMap<u32, Vec<u32>>, k: u32) -> &mut Vec<u32> {
    match m.get_mut(&k) { Some(v) => v, None => { m.insert(k, vec![]); m.get_mut(&k).unwrap() } }
}

// ✅ entry API：一次哈希，一次借用
fn ok(m: &mut HashMap<u32, Vec<u32>>, k: u32) -> &mut Vec<u32> {
    m.entry(k).or_default()
}
```

**这是 API 设计手法**（第 21 章展开）：给自己的容器也提供 `entry` 风格的 API。

```rust
// 通用形式：回调（控制反转）
impl App {
    pub fn with_widget<R>(
        &mut self, i: usize,
        f: impl FnOnce(&mut Widget, &mut Vec<String>) -> R,
    ) -> Option<R> {
        let w = self.widgets.get_mut(i)?;
        Some(f(w, &mut self.log))
    }
}
```

**代价**：调用方要写闭包；不能从闭包里 `return`/`?` 到外层函数。

---

## 第四组：换数据结构

### 手法 11：索引 / ID 代替引用（★★★★★ 最通用的解法）

**原理**：引用带生命周期，索引不带。**用一个 `usize` 代替 `&T`，所有借用问题消失。**

```rust
// ❌ 想同时持有多个节点的引用
struct Graph { nodes: Vec<Node> }
struct Node { neighbors: Vec<&Node> }        // 编译不过

// ✅ 索引
struct Graph { nodes: Vec<Node> }
struct Node { neighbors: Vec<usize> }

impl Graph {
    fn neighbors_of(&self, i: usize) -> &[usize] { &self.nodes[i].neighbors }
    fn add_edge(&mut self, a: usize, b: usize) {
        self.nodes[a].neighbors.push(b);
        self.nodes[b].neighbors.push(a);      // ✅ 两次独立的短借用
    }
}
```

**代价**：
- 每次访问要 `graph.nodes[i]`，多一次边界检查
- **索引可能失效**（元素被删除后下标改变）→ 用 generational index（见下）
- 类型安全变弱（`usize` 可以传错）→ 用 newtype

**加固版：newtype + generational index**

```rust
#[derive(Copy, Clone, PartialEq, Eq, Hash, Debug)]
pub struct NodeId(u32);                       // ★ newtype，不会和别的索引混淆

// 更强：slotmap crate 提供 generational index，删除后旧 key 自动失效
// use slotmap::{SlotMap, DefaultKey};
```

> ### 什么时候必须用索引
> - 图、树（带父指针）、双向链表
> - 需要序列化的结构（引用没法序列化，索引可以）
> - 需要跨线程/跨 await 传递的"指向某个元素"
>
> **`petgraph`、`slotmap`、rustc 自己（`DefId`/`NodeId`/`RegionVid`）全都用这个模式。**
> 你在第 07/08 章看到的 `'?3`、`bw0`、`mp1` 就是索引。

### 手法 12：arena

**原理**：所有节点存在一个 arena 里，节点之间用索引互指。arena 整体拥有所有数据。

```rust
struct Arena<T> { items: Vec<T> }
impl<T> Arena<T> {
    fn alloc(&mut self, v: T) -> usize { self.items.push(v); self.items.len() - 1 }
    fn get(&self, i: usize) -> &T { &self.items[i] }
    fn get_mut(&mut self, i: usize) -> &mut T { &mut self.items[i] }
}
```

**代价**：所有访问都要经过 arena（需要把它传来传去）；不能单独释放一个节点。
**优点**：分配快（bump allocation）、缓存友好、drop 时一次性释放。

**成熟的 crate**：`typed-arena`、`bumpalo`、`slotmap`、`slab`、`id-arena`。

第 20 章会完整实现一遍。

### 手法 13：`Rc` / `Arc` 共享所有权

```rust
use std::rc::{Rc, Weak};
struct Node { parent: Weak<Node>, children: Vec<Rc<Node>> }    // ★ 父用 Weak，避免循环
```

**代价**：
- 引用计数开销（`Arc` 是原子操作，更贵）
- **循环引用会泄漏**（必须有一个方向用 `Weak`）
- 内部要改就得配 `RefCell`/`Mutex` → 运行时 panic 风险
- `Rc<RefCell<T>>` 的可读性很差

**什么时候该用**：**真正的共享所有权**——多个持有者，谁都不知道谁最后销毁。
**什么时候不该用**：只是为了让借用检查闭嘴。那说明你没想清楚谁拥有数据。

### 手法 14：`Cow`（借用或拥有，按需）

```rust
use std::borrow::Cow;

fn normalize(s: &str) -> Cow<'_, str> {
    if s.contains(' ') { Cow::Owned(s.replace(' ', "_")) }    // 需要改 → 拥有
    else { Cow::Borrowed(s) }                                  // 不用改 → 借用
}
```

**代价**：调用方要处理 `Cow`（虽然它 `Deref` 到 `str`）；类型签名变复杂。
**适用**：**大部分情况不需要修改，少数情况需要**的场景（配置、路径规范化、转义）。

---

## 第五组：最后手段

### 手法 15：内部可变性（`Cell` / `RefCell` / `Mutex`）

**原理**：把编译期检查搬到运行时（第 19 章详解）。

```rust
use std::cell::RefCell;
struct Cache { map: RefCell<HashMap<u32, String>> }
impl Cache {
    fn get(&self, k: u32) -> Option<String> {        // ★ 注意是 &self
        self.map.borrow().get(&k).cloned()
    }
}
```

**代价（★ 必须清楚）**：
- **编译期错误变成运行时 panic**（`already borrowed`）
- `RefCell` 有运行时开销（一个计数器）
- **型变塌了**：加了 `RefCell` 字段，结构体对生命周期参数变成不变（第 09 章）
- `RefCell` 不是 `Sync`，`Cell` 不是 `Sync`

**什么时候该用**：
- ✅ 逻辑上不可变但内部需要缓存（memoization）
- ✅ 观察者模式、回调注册
- ✅ 单线程的图结构（配 `Rc`）
- ❌ **仅仅为了让编译器闭嘴**

**判断法**：如果你能说出"这两个借用在运行时确实可能同时存在，我需要动态检查"，
那是对的。如果你只是不知道怎么重排代码，回到手法 1–8。

### 手法 16：`unsafe` 封装

**原理**：你知道某个不变量成立但编译器不知道，用 `unsafe` 证明一次，包装成安全 API。

```rust
// 这就是 split_at_mut 的实现方式（简化）
pub fn split_at_mut<T>(s: &mut [T], mid: usize) -> (&mut [T], &mut [T]) {
    let len = s.len();
    let ptr = s.as_mut_ptr();
    assert!(mid <= len);
    unsafe {
        (
            std::slice::from_raw_parts_mut(ptr, mid),
            std::slice::from_raw_parts_mut(ptr.add(mid), len - mid),
        )
    }
}
```

**代价**：
- **你要为 soundness 负全责**——写错了就是 UB，且可能几年后才炸
- 必须用 Miri 验证（第 26 章）
- 必须写清楚安全契约（`# Safety` 文档）
- 代码审查成本高

**什么时候该用**：
- ✅ 你在写一个**库**，这个 `unsafe` 会被成千上万人复用（摊薄了成本）
- ✅ 性能确实关键，且 profile 证明了
- ❌ 在业务代码里为了少写几行

**⚠️ 第一原则**：**先去 crates.io 找找有没有人已经写好了。**
`slice::split_at_mut`、`get_disjoint_mut`、`slotmap`、`ouroboros`、`qcell`——
你想要的东西大概率已经存在。

---

## 速查表

| # | 手法 | 适用 | 运行时代价 | 复杂度代价 |
|---|---|---|---|---|
| 1 | 挪动最后一次使用 | region 太大 | 零 | 零 |
| 2 | 拷贝需要的值 | 只需要值不需要引用 | 一次 copy/clone | 零 |
| 3 | 块 `{}` / `drop()` | `Drop` 类型作用域太大 | 零 | 零 |
| 4 | **解构** | 方法借走整个 self | 零 | 零 ★★★★★ |
| 5 | splitter 方法 | 字段私有 | 零 | API 变大 |
| 6 | 自由函数取字段 | 内部逻辑 | 零 | 参数变长 |
| 7 | 重组结构体 | 字段分组明显 | 零 | 重构成本 |
| 8 | `split_at_mut` 家族 | 按位置分割容器 | 零 | 零 ★★★★★ |
| 9 | `mem::take` 家族 | 只有 `&mut` 但要所有权 | 零 | panic 安全性 |
| 10 | 打包成一次操作 | 查找+修改 | 零 | 闭包语法 |
| 11 | **索引 / ID** | 图 / 树 / 需要序列化 | 边界检查 | 索引失效风险 ★★★★★ |
| 12 | arena | 大量同类节点 | 间接一层 | 要传 arena |
| 13 | `Rc` / `Arc` | 真·共享所有权 | 引用计数 | 循环泄漏风险 |
| 14 | `Cow` | 大多不改，偶尔改 | 零（不改时） | 签名复杂 |
| 15 | 内部可变性 | 真需要动态检查 | 计数器/锁 | **运行时 panic** |
| 16 | `unsafe` 封装 | 写库 / 极致性能 | 零 | **soundness 责任** |

---

## 动手实验

### 实验 1：用六种手法解同一个问题

```rust
struct Widget { name: String }
struct App { widgets: Vec<Widget>, log: Vec<String>, counter: u32 }

impl App {
    fn widgets(&self) -> &Vec<Widget> { &self.widgets }
    fn log_mut(&mut self) -> &mut Vec<String> { &mut self.log }
}

// ❌ 这个编译不过：
fn bad(a: &mut App) {
    for w in a.widgets() {
        a.log_mut().push(w.name.clone());
    }
}
```

**任务**：用手法 2、4、5、6、7、10 各写一遍，编译验证，然后**排序**：
哪个最可读？哪个最快？哪个最容易维护？

### 实验 2：把 `Rc<RefCell<>>` 改成索引

找一段用 `Rc<RefCell<T>>` 的代码（自己写的或开源项目里的），
改写成 arena + index 版本。**对比**：
- 代码行数
- 有没有运行时 panic 的可能
- 能不能 `Send`

### 实验 3：判断流程练习

给下面每个错误场景选手法（不看答案）：

1. `let g = m.lock().unwrap();` 之后一大段代码，锁持有太久
2. 遍历 `self.items` 时想调 `self.log(...)`
3. 想同时可变借用 `v[i]` 和 `v[j]`（i≠j 但运行时才知道）
4. 树节点需要指向父节点
5. 函数只有 `&mut self`，但需要 `self.data.into_iter()`
6. 想返回"要么是输入的切片，要么是新分配的 String"

<details><summary>答案</summary>

1. 手法 3（块 / `drop`）
2. 手法 4（解构）或 6（自由函数）；将来是 view types
3. 手法 8（`get_disjoint_mut`）；下标不行
4. 手法 11（索引）或 13（`Weak`）
5. 手法 9（`mem::take`）
6. 手法 14（`Cow`）

</details>

---

## 本章检查清单

- [ ] 能背出第 0 节的判断流程
- [ ] **知道手法 4（解构）、8（split 家族）、11（索引）是三个最高性价比的**
- [ ] 知道 `.clone()` 的正确定位：不是罪，但要知道为什么
- [ ] 知道块 `{}` 只对 `Drop` 类型有意义
- [ ] 知道 `mem::take` 的原理（放替代品保证位置始终有效）和它的 panic 安全性代价
- [ ] 知道内部可变性的四项代价，尤其是"型变塌了"
- [ ] 知道 `unsafe` 封装前先去 crates.io 找现成的
- [ ] 能对任意一个借用错误在 30 秒内选出手法

---

## 常见坑

| 现象 | 说明 |
|---|---|
| 无脑 `.clone()` | 不是错，但你埋掉了一个信号。至少要知道为什么 |
| 无脑 `Rc<RefCell<T>>` | 把编译期检查换成运行时 panic，且失去 `Send` |
| 加块 `{}` 不管用 | 说明不涉及 `Drop` 类型，NLL 已经帮你缩过了 |
| splitter 方法越加越多 | 说明该用手法 7（重组结构体）了 |
| 索引失效导致读到错元素 | 用 generational index（`slotmap`） |
| `mem::take` 后 panic 导致数据丢失 | 用 `scopeguard` 或改成 `replace` 并小心中间状态 |
| 自己写 `unsafe` 分割 | 先找 `split_at_mut` / `get_disjoint_mut` / `slotmap` |

---

下一章：[19 - 内部可变性](19-interior-mutability.md)
