# 20 - 图 / 树 / 链表到底怎么写

> 本章目标：把第 18 章的手法 11–13 落到具体代码上。
> 我们会把同一个"带父指针的树"用**四种方式**实现，逐一对比代价。
> 这一章的结论会颠覆一个流传很广的印象：**Rust 里写链式结构的正确答案通常不是指针，是索引。**
> 预计用时：3 小时。

---

## 1. 为什么链式结构在 Rust 里特别难

回到公理（第 03 章）。链式结构的本质是**多条路径指向同一个节点**：

```
       root
      /    \
     A      B
      \    /
        C          ← C 被 A 和 B 同时指向 = 别名
```

如果还要能**修改** C，就直接违反了 Aliasing XOR Mutability。

**其它语言怎么做**：
- **Java/Go**：GC 保证内存不会提前释放，别名可变是"你自己小心"
- **C++**：`shared_ptr` + 纪律
- **Rust**：必须显式选一种方案，编译器强制你面对这个问题

**四种方案**：

| 方案 | 别名怎么办 | 可变怎么办 |
|---|---|---|
| **A. 独占树（`Box`）** | 禁止别名——每个节点只有一个父 | `&mut` 自然可用 |
| **B. `Rc` + `Weak` + `RefCell`** | 引用计数允许别名 | `RefCell` 运行时检查 |
| **C. arena + 索引** | 索引不是引用，随便复制 | 通过 arena 的 `&mut` 访问 |
| **D. `unsafe` + 裸指针** | 你自己保证 | 你自己保证 |

---

## 2. 方案 A：独占树（`Box`）

**适用**：真正的树——每个节点恰好一个父，不需要父指针。

```rust
#[derive(Debug)]
pub struct Tree<T> {
    pub value: T,
    pub children: Vec<Tree<T>>,
}

impl<T> Tree<T> {
    pub fn new(value: T) -> Self { Tree { value, children: Vec::new() } }

    pub fn push(&mut self, child: Tree<T>) { self.children.push(child); }

    /// 深度优先遍历（不可变）
    pub fn walk(&self, f: &mut impl FnMut(&T)) {
        f(&self.value);
        for c in &self.children { c.walk(f); }
    }

    /// 深度优先遍历（可变）
    pub fn walk_mut(&mut self, f: &mut impl FnMut(&mut T)) {
        f(&mut self.value);
        for c in &mut self.children { c.walk_mut(f); }
    }

    /// 找到第一个满足条件的节点，返回可变引用
    pub fn find_mut(&mut self, pred: &impl Fn(&T) -> bool) -> Option<&mut Tree<T>> {
        if pred(&self.value) { return Some(self); }
        for c in &mut self.children {
            if let Some(found) = c.find_mut(pred) { return Some(found); }
        }
        None
    }
}
```

**单向链表**（`Box` 的经典用法）：

```rust
pub struct List<T> { head: Option<Box<Node<T>>> }
struct Node<T> { value: T, next: Option<Box<Node<T>>> }

impl<T> List<T> {
    pub fn push_front(&mut self, value: T) {
        let old = self.head.take();                        // ★ Option::take
        self.head = Some(Box::new(Node { value, next: old }));
    }
    pub fn pop_front(&mut self) -> Option<T> {
        let node = self.head.take()?;
        self.head = node.next;
        Some(node.value)
    }
}
```

> ### ⚠️ 一个必须知道的坑：递归 `Drop` 会爆栈
> 上面这个 `List` 在有 10 万个节点时，默认的递归 `Drop` 会**栈溢出**。
> 标准做法是手写迭代版 `Drop`：
>
> ```rust
> impl<T> Drop for List<T> {
>     fn drop(&mut self) {
>         let mut cur = self.head.take();
>         while let Some(mut node) = cur { cur = node.next.take(); }
>     }
> }
> ```
>
> **同样的问题存在于深树、JSON AST、表达式树**。这不是借用检查问题，
> 但它是链式结构在 Rust 里的第二大陷阱。

**代价**：不能有父指针、不能共享节点、不能有环。

---

## 3. 方案 B：`Rc` + `Weak` + `RefCell`

**适用**：单线程，真的需要共享所有权和父指针。

```rust
use std::cell::RefCell;
use std::rc::{Rc, Weak};

pub struct Node {
    pub value: i32,
    parent: RefCell<Weak<Node>>,          // ★ 父用 Weak，避免循环引用泄漏
    children: RefCell<Vec<Rc<Node>>>,
}

impl Node {
    pub fn new(value: i32) -> Rc<Node> {
        Rc::new(Node { value, parent: RefCell::new(Weak::new()), children: RefCell::new(vec![]) })
    }
    pub fn add_child(parent: &Rc<Node>, child: Rc<Node>) {
        *child.parent.borrow_mut() = Rc::downgrade(parent);
        parent.children.borrow_mut().push(child);
    }
    pub fn parent(&self) -> Option<Rc<Node>> { self.parent.borrow().upgrade() }
}
```

**代价清单（★ 全都要付）**：

| 代价 | 说明 |
|---|---|
| **引用计数开销** | 每次 clone/drop 都改计数 |
| **`RefCell` panic 风险** | 遍历时一不小心就 `already borrowed`（第 19 章） |
| **必须记得用 `Weak`** | 忘了就内存泄漏，且**编译器不会提醒** |
| **不是 `Send`/`Sync`** | 整个结构困在一个线程里 |
| **可读性差** | `node.children.borrow()[0].value` |
| **缓存不友好** | 节点散落在堆各处 |
| **难以序列化** | `Rc` 的图结构没法直接序列化 |

**多线程版本**：`Arc<RwLock<Node>>` + `Weak`——所有代价加倍（原子计数 + 真锁）。

> ### ★ 什么时候真的该用它
> - 节点的**生命周期确实不一致**（有的先死有的后死）
> - 需要从外部持有某个节点的**长期句柄**
> - 结构确实是 DAG 或图，且节点会被多处引用
>
> **如果只是"想要父指针"，用方案 C。**

---

## 4. 方案 C：arena + 索引（★ 推荐默认方案）

**核心思想**：所有节点存在一个 `Vec` 里，节点之间用 `usize` 索引互指。

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeId(u32);                     // ★ newtype，防止和别的索引混淆

#[derive(Debug)]
pub struct Node<T> {
    pub value: T,
    pub parent: Option<NodeId>,
    pub children: Vec<NodeId>,
}

#[derive(Debug, Default)]
pub struct Arena<T> { nodes: Vec<Node<T>> }

impl<T> Arena<T> {
    pub fn new() -> Self { Arena { nodes: Vec::new() } }

    pub fn alloc(&mut self, value: T) -> NodeId {
        let id = NodeId(self.nodes.len() as u32);
        self.nodes.push(Node { value, parent: None, children: Vec::new() });
        id
    }

    pub fn get(&self, id: NodeId) -> &Node<T> { &self.nodes[id.0 as usize] }
    pub fn get_mut(&mut self, id: NodeId) -> &mut Node<T> { &mut self.nodes[id.0 as usize] }

    pub fn add_child(&mut self, parent: NodeId, child: NodeId) {
        self.get_mut(parent).children.push(child);       // ★ 两次独立的短借用
        self.get_mut(child).parent = Some(parent);       //    完全没有借用冲突
    }

    /// 深度优先遍历
    pub fn walk(&self, root: NodeId, f: &mut impl FnMut(NodeId, &T)) {
        f(root, &self.get(root).value);
        // ★ 注意：这里要先把 children 拷出来，否则遍历时借着 self
        for &c in &self.get(root).children.clone() { self.walk(c, f); }
    }

    /// 可变遍历：用显式栈，避免同时持有多个 &mut
    pub fn walk_mut(&mut self, root: NodeId, f: &mut impl FnMut(&mut T)) {
        let mut stack = vec![root];
        while let Some(id) = stack.pop() {
            f(&mut self.get_mut(id).value);
            stack.extend(self.get(id).children.iter().copied());
        }
    }

    /// ★ 同时修改两个不相关的节点 —— 方案 B 做不到的
    pub fn swap_values(&mut self, a: NodeId, b: NodeId) where T: Default {
        if a == b { return; }
        let (i, j) = (a.0 as usize, b.0 as usize);
        let (lo, hi) = if i < j { (i, j) } else { (j, i) };
        let (l, r) = self.nodes.split_at_mut(hi);        // ★ 第 18 章手法 8
        std::mem::swap(&mut l[lo].value, &mut r[0].value);
    }
}
```

**用起来**：

```rust
let mut arena = Arena::new();
let root = arena.alloc("root");
let a = arena.alloc("a");
let b = arena.alloc("b");
arena.add_child(root, a);
arena.add_child(root, b);
arena.walk(root, &mut |id, v| println!("{:?} = {}", id, v));
```

### 4.1 代价与好处

| | |
|---|---|
| ✅ **没有任何借用冲突** | 索引是 `Copy`，随便传 |
| ✅ **`Send` + `Sync`** | 只要 `T` 是（可以跨线程整体传递） |
| ✅ **缓存友好** | 节点连续存储 |
| ✅ **可序列化** | 索引就是数字 |
| ✅ **分配快** | `Vec::push`，摊还 O(1) |
| ✅ **drop 快** | 一次性释放整个 `Vec` |
| ❌ **需要携带 arena** | 每个操作都要 `&arena` 或 `&mut arena` |
| ❌ **删除麻烦** | 删了会让后面的索引失效 → 见 4.2 |
| ❌ **多一次边界检查** | `self.nodes[i]` |
| ❌ **类型安全弱一点** | 用错 arena 的 id 不会被编译器发现 → newtype + 4.2 |

### 4.2 索引失效：generational index

**问题**：

```rust
let a = arena.alloc("a");
arena.remove(a);               // 如果用 swap_remove，最后一个元素挪到了 a 的位置
let v = arena.get(a);          // 💥 读到了别的节点，且没有任何报错
```

**解法：给每个槽位加一个"代数"**：

```rust
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Key { index: u32, generation: u32 }

struct Slot<T> { generation: u32, value: Option<T> }

pub struct SlotArena<T> { slots: Vec<Slot<T>>, free: Vec<u32> }

impl<T> SlotArena<T> {
    pub fn insert(&mut self, value: T) -> Key {
        if let Some(i) = self.free.pop() {
            let s = &mut self.slots[i as usize];
            s.generation += 1;                     // ★ 代数递增，旧 Key 自动失效
            s.value = Some(value);
            Key { index: i, generation: s.generation }
        } else {
            self.slots.push(Slot { generation: 0, value: Some(value) });
            Key { index: (self.slots.len() - 1) as u32, generation: 0 }
        }
    }
    pub fn get(&self, k: Key) -> Option<&T> {
        let s = self.slots.get(k.index as usize)?;
        if s.generation == k.generation { s.value.as_ref() } else { None }   // ★ 校验
    }
    pub fn remove(&mut self, k: Key) -> Option<T> {
        let s = self.slots.get_mut(k.index as usize)?;
        if s.generation != k.generation { return None; }
        self.free.push(k.index);
        s.value.take()
    }
}
```

**生产环境直接用 crate**：

| crate | 特点 |
|---|---|
| **`slotmap`** | ★ generational index 的标准实现，API 完善 |
| **`slab`** | 简单的 index arena，无代数 |
| **`id-arena`** | 类型化的 id |
| **`typed-arena`** | 返回 `&T` 而非 index（用生命周期绑定） |
| **`bumpalo`** | bump 分配器，适合编译器/解析器 |
| **`petgraph`** | 完整的图库，内部就是 arena + index |

### 4.3 谁在用这个模式

**几乎所有 Rust 里的严肃链式结构**：

| 项目 | 做法 |
|---|---|
| **rustc 自己** | `DefId`、`NodeId`、`RegionVid`、`BasicBlock`、`Local` 全是索引（你在第 07/08 章见过 `'?3`、`bw0`、`mp1`） |
| `rust-analyzer` | arena + salsa |
| `petgraph` | `NodeIndex` / `EdgeIndex` |
| Bevy（游戏引擎） | ECS，本质是 generational index |
| `servo` / DOM 实现 | arena |

> ### ★ 本章最重要的一句话
> **"Rust 写不了链表"这个印象的真正含义是：
> Rust 逼你放弃"到处都是指针"这种设计，改用索引。
> 而索引在大部分场景下本来就是更好的设计。**

---

## 5. 方案 D：`unsafe` + 裸指针

**只在写库时考虑**。标准库的 `LinkedList` 就是这么写的：

```rust
use std::ptr::NonNull;
use std::marker::PhantomData;

pub struct LinkedList<T> {
    head: Option<NonNull<Node<T>>>,
    tail: Option<NonNull<Node<T>>>,
    len: usize,
    _marker: PhantomData<Box<Node<T>>>,     // ★ 第 09 章：声明所有权 + 协变
}

struct Node<T> {
    next: Option<NonNull<Node<T>>>,
    prev: Option<NonNull<Node<T>>>,
    element: T,
}
```

**三个关键点**：

1. **`NonNull<T>` 而不是 `*mut T`**——`NonNull` 是**协变**的且非空（第 09 章）
2. **`PhantomData<Box<Node<T>>>`**——告诉编译器"我拥有这些节点"，让 dropck 正确工作
3. **每个 `unsafe` 块都要有 `// SAFETY:` 注释**说明为什么不变量成立

**必须做的事**：

```bash
cargo +nightly miri test              # ★ 第 26 章
MIRIFLAGS=-Zmiri-tree-borrows cargo +nightly miri test
```

**先问三遍**：
1. 方案 C（arena）真的不行吗？
2. crates.io 上有现成的吗？
3. 我有 profile 数据证明这个性能差别重要吗？

---

## 6. 四种方案对比

| | A. `Box` 树 | B. `Rc/RefCell` | C. arena+索引 | D. unsafe |
|---|---|---|---|---|
| 父指针 | ❌ | ✅ | ✅ | ✅ |
| 共享节点 | ❌ | ✅ | ✅ | ✅ |
| 环 | ❌ | ✅（要 `Weak`） | ✅ | ✅ |
| 借用冲突 | 少 | **运行时 panic** | **无** | 你负责 |
| `Send`/`Sync` | ✅ | ❌（`Arc` 版可以但更贵） | ✅ | 要手动 `unsafe impl` |
| 缓存友好 | 中 | ❌ | ✅ | 中 |
| 可序列化 | ✅ | ❌ | ✅ | ❌ |
| 删除单个节点 | ✅ | ✅ | 需要 generational | ✅ |
| 代码复杂度 | 低 | 中 | **中低** | 高 |
| soundness 风险 | 无 | 无 | 无 | **有** |
| **推荐度** | 纯树用它 | 谨慎 | ★★★★★ | 写库时 |

---

## 7. 动手实验

### 实验 1：三种方式实现同一棵带父指针的树

实现一个文件系统树，要求：
- 每个节点有 `name: String`、父指针、子节点列表
- 支持 `path_of(node) -> String`（需要向上遍历到根）
- 支持 `move_node(node, new_parent)`

分别用方案 B 和方案 C 实现，对比：
- 代码行数
- 有没有运行时 panic 的可能
- 能不能 `Send`

<details><summary>提示</summary>

方案 C 的 `path_of`：

```rust
impl Arena<String> {
    pub fn path_of(&self, mut id: NodeId) -> String {
        let mut parts = vec![];
        loop {
            parts.push(self.get(id).value.clone());
            match self.get(id).parent { Some(p) => id = p, None => break }
        }
        parts.reverse();
        parts.join("/")
    }
}
```

**注意这个循环在方案 B 下有多难写**——`node.parent.borrow().upgrade()` 返回
一个新的 `Rc`，你要小心不要在循环里持有 `Ref`。

</details>

### 实验 2：递归 Drop 爆栈

```rust
struct Node { next: Option<Box<Node>> }

fn main() {
    let mut head = None;
    for _ in 0..200_000 {
        head = Some(Box::new(Node { next: head }));
    }
    println!("built");
}       // ← 这里会怎样？
```

**实测输出**（`rustc 1.96.0`，debug）：

```
built
thread 'main' (532193) has overflowed its stack
fatal runtime error: stack overflow, aborting
zsh: abort      ./dropstack        (exit=134)
```

★ 注意 `built` **打印出来了**——说明构造没问题，**炸在 `main` 结束时的递归 drop 上**。
这类 bug 在测试里用小数据完全发现不了。

然后加上手写的迭代 `Drop`，再跑：

```rust
impl Drop for Node {
    fn drop(&mut self) {
        let mut cur = self.next.take();
        while let Some(mut node) = cur { cur = node.next.take(); }
    }
}
```

### 实验 3：generational index

给第 4.2 节的 `SlotArena` 补上 `iter()`，然后写一个测试：

```rust
let mut a = SlotArena::new();
let k1 = a.insert("first");
a.remove(k1);
let k2 = a.insert("second");        // 复用了 k1 的槽位
assert_eq!(a.get(k1), None);        // ★ 旧 key 必须失效
assert_eq!(a.get(k2), Some(&"second"));
```

### 实验 4：读 rustc 的做法

```bash
rustc +nightly -Zunpretty=mir your_file.rs
```

观察输出里的 `_1`、`_2`、`bb0`——**这些全是索引**。
然后想想：如果 rustc 用 `Rc<RefCell<Statement>>` 来表示 MIR，会是什么样子。

---

## 8. 本章检查清单

- [ ] 知道链式结构难写的根因是"多路径指向 + 可变"
- [ ] 知道纯树用 `Box`，且知道**递归 Drop 爆栈**这个坑
- [ ] 能列出 `Rc<RefCell<T>>` 方案的七项代价
- [ ] 知道父指针必须用 `Weak`，否则泄漏
- [ ] **能手写一个 arena + NodeId 的树，并说出它的六个好处**
- [ ] 知道索引失效问题及 generational index 的原理
- [ ] 知道 `slotmap` / `slab` / `petgraph` 这几个 crate
- [ ] 知道 `unsafe` 方案里 `NonNull` + `PhantomData` 各自的作用
- [ ] **知道 rustc 自己用的就是 arena + 索引**

---

## 9. 常见坑

| 现象 | 原因 | 处方 |
|---|---|---|
| 深链表/深树 drop 时爆栈 | 递归 `Drop` | 手写迭代版 `Drop` |
| `Rc` 循环导致内存泄漏 | 忘了用 `Weak` | 父/反向指针一律用 `Weak` |
| 遍历 `Rc<RefCell<T>>` 树时 panic | 借用重叠 | 把需要的值 clone 出来；或改用 arena |
| 索引失效读到错节点 | `swap_remove` 之类改变了下标 | generational index / `slotmap` |
| arena 到处传很烦 | 设计问题 | 把 arena 和操作封装成一个结构体，方法都在它上面 |
| 用错 arena 的 id | `usize` 没有类型区分 | newtype `NodeId(u32)` |
| 自己写的 `unsafe` 链表有 UB | 不变量没保住 | Miri（第 26 章）；先考虑方案 C |
| arena 里同时改两个节点 | 借用冲突 | `split_at_mut`（见 `swap_values`）或 `get_disjoint_mut` |

---

下一章：[21 - 用生命周期设计 API](21-api-design.md)
