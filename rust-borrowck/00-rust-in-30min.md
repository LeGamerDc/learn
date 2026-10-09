# 00 - Rust 语法速通（Go 开发者对照版）

> 本章目标：让你能**读懂**本课程后面所有的代码示例。不多不少。
> 这不是 Rust 教程——不讲宏、不讲模块系统、不讲 cargo 工作区、不讲错误处理最佳实践。
> 只讲后面 27 章会用到的语法。
> 预计用时：1.5 小时（读 40 分钟 + 自己敲 50 分钟）。

---

## 1. 心智模型的第一次调整

在写第一行代码之前，先记住 Go 和 Rust 最根本的三个差别。后面所有的"不习惯"都源自这三条：

| | Go | Rust |
|---|---|---|
| **内存谁管** | GC。你分配，运行时回收 | 编译期确定。每个值有唯一 owner，owner 作用域结束就 drop |
| **默认语义** | 赋值 = 复制（结构体按值复制，slice/map 复制 header） | 赋值 = **移动**（原变量失效），除非类型实现了 `Copy` |
| **零值** | 每个类型有零值，`var x T` 就能用 | **没有零值**。变量必须初始化后才能读 |

第三条尤其重要。Go 里 `var s []int` 是个可用的 nil slice，`var m map[string]int` 读取是安全的。
Rust 里没有这回事——编译器会追踪"这个变量此刻是否已初始化"，这个追踪机制（moves & initialization 分析）
和 borrow checker 是同一套数据流框架的两个客户，第 08 章会看到它们的源码位置。

---

## 2. 变量、可变性

```rust
let x = 5;              // 不可变绑定。Go: const 但只在这个作用域
let mut y = 5;          // 可变绑定
y += 1;

let z: i64 = 5;         // 显式类型
let w = 5i64;           // 字面量后缀
let v = 5_000_000;      // 下划线分隔

// 遮蔽 (shadowing)：允许重复 let 同名变量，是全新的变量
let s = "5";
let s = s.parse::<i32>().unwrap();   // s 现在是 i32
```

**`mut` 是绑定的属性，不是类型的属性**。这点和 C 的 `const` 完全不同，第 05 章会展开：
`&mut T` 里的 `mut` 才是类型的一部分。

> **Go 对照**：Go 没有不可变变量（除了 `const` 的编译期常量）。Rust 的默认不可变
> 是一个刻意的设计——大部分变量确实不需要改，把"要改"变成需要显式声明的少数派，
> 让 borrow checker 和读代码的人都能更快看出哪里有副作用。

---

## 3. 基本类型

```rust
i8 i16 i32 i64 i128 isize        // 有符号；isize = Go 的 int（指针宽度）
u8 u16 u32 u64 u128 usize        // 无符号；usize = Go 的 uint，索引用它
f32 f64
bool
char                             // 4 字节 Unicode 标量值，不是 Go 的 byte
()                               // unit 类型，只有一个值 ()，相当于 Go 的空 struct{}
!                                // never 类型，永不返回（panic!、loop{}、return 的类型）
```

**字符串是本课程的高频角色**，因为它是"拥有 vs 借用"最直观的例子：

```rust
let owned:   String = String::from("hello");   // 拥有堆上的字节；≈ Go 的 []byte 但保证 UTF-8
let borrowed: &str  = &owned;                  // 借用一段；≈ Go 的 string（只读视图）
let literal: &'static str = "hello";           // 字面量，指向二进制里的只读数据
```

| Rust | Go 里最接近的东西 | 拥有堆内存吗 |
|---|---|---|
| `String` | `[]byte`（可增长） | ✅ 是 owner |
| `&str` | `string`（只读切片视图） | ❌ 借用别人的 |
| `Vec<T>` | `[]T` | ✅ 是 owner |
| `&[T]` | `[]T`（只读用法） | ❌ 借用别人的 |
| `&mut [T]` | `[]T`（可写用法） | ❌ 借用别人的，且**独占** |

> **这张表是整门课的缩影**：Go 把"拥有"和"借用"混在同一个类型里（`[]T` 既可能是
> 你 `make` 出来的，也可能是别人切给你的），所以你必须靠文档和纪律来避免别名 bug。
> Rust 把它们分成两个类型，让编译器来管。

---

## 4. 复合类型

```rust
// 元组
let pair: (i32, &str) = (1, "one");
let (a, b) = pair;                    // 解构
println!("{}", pair.0);

// 数组：长度是类型的一部分，栈上
let arr: [i32; 3] = [1, 2, 3];

// Vec：堆上，可增长
let mut v: Vec<i32> = vec![1, 2, 3];
v.push(4);

// 切片：借用一段连续内存（胖指针 = 起始地址 + 长度）
let s: &[i32] = &v[1..3];
```

**结构体**：

```rust
struct Point { x: f64, y: f64 }              // 具名字段
struct Meters(f64);                          // 元组结构体（newtype，第 21 章重点）
struct Marker;                               // 单元结构体，零大小

let p = Point { x: 1.0, y: 2.0 };
let Point { x, y } = p;                      // 解构
```

**枚举**——这是 Go 里没有的、也是 Rust 最重要的类型构造器（真正的 sum type / tagged union）：

```rust
enum Shape {
    Circle(f64),                    // 变体可以带数据
    Rect { w: f64, h: f64 },
    Empty,
}

// 标准库里两个你会天天见到的枚举：
enum Option<T> { Some(T), None }              // 代替 Go 的 (T, bool) 和 nil
enum Result<T, E> { Ok(T), Err(E) }           // 代替 Go 的 (T, error)
```

> **Go 对照**：Go 用 `(value, ok)`、`(value, err)`、nil 指针来表达"可能没有"。
> Rust 用 `Option<T>`，且**编译器强制你处理 None 分支**。这不只是语法糖：
> `Option<&T>` 和 `&T` 是不同的类型，前者可以是 None，后者**永远是有效引用**——
> 这就是 Rust 没有 nil 解引用的原因。

---

## 5. 控制流

```rust
// if 是表达式
let n = if x > 0 { 1 } else { -1 };

// match：穷尽性检查（Go 的 switch 不强制穷尽，Rust 强制）
match shape {
    Shape::Circle(r)       => 3.14 * r * r,
    Shape::Rect { w, h }   => w * h,
    Shape::Empty           => 0.0,
}

// 通配和守卫
match n {
    0            => "zero",
    x if x < 0   => "negative",
    1..=9        => "small",
    _            => "big",
}

// if let：只关心一个分支时的简写
if let Some(v) = opt { use_it(v); }

// let else：不匹配就提前退出（很常用）
let Some(v) = opt else { return; };

// while let
while let Some(top) = stack.pop() { ... }

// 循环
for i in 0..10 { }                // 0..10 不含 10；0..=10 含
for item in &collection { }       // 借用遍历
for item in collection { }        // 消耗遍历（collection 被移动走了！）
loop { break 'value; }            // loop 可以 break 出值
```

**`match` 里的绑定模式**是借用检查的高发区（第 12 章专门讲），先建立印象：

```rust
match &opt {
    Some(x) => { /* x: &T，借用 */ }
    None => {}
}

match opt {
    Some(x) => { /* x: T，被移动出来了 */ }
    None => {}
}

match &mut opt {
    Some(x) => { /* x: &mut T */ }
    None => {}
}
```

---

## 6. 函数、方法、trait

```rust
fn add(a: i32, b: i32) -> i32 {
    a + b            // 无分号 = 返回值（尾表达式）
}

fn nothing() { }     // 返回 ()

// impl 块：给类型加方法
impl Point {
    fn new(x: f64, y: f64) -> Self { Point { x, y } }   // 关联函数（无 self），≈ Go 的构造函数
    fn len(&self) -> f64 { ... }                        // 不可变借用 self
    fn scale(&mut self, k: f64) { ... }                 // 可变借用 self
    fn into_pair(self) -> (f64, f64) { ... }            // 消耗 self（拿走所有权）
}
```

**`self` 的四种形式是本课程的核心之一**，务必分清：

| 签名 | 含义 | Go 类比 | 调用后原对象 |
|---|---|---|---|
| `fn f(self)` | 拿走所有权 | 值接收者 + 之后不许再用原值 | **失效** |
| `fn f(&self)` | 共享借用 | `func (p *Point)` 但只读 | 可继续用 |
| `fn f(&mut self)` | 独占借用 | `func (p *Point)` 可写 | 可继续用，但**借用期间**不可用 |
| `fn f(self: Rc<Self>)` | 特殊接收者 | — | — |

**trait ≈ Go 的 interface，但有关键差别**：

```rust
trait Area {
    fn area(&self) -> f64;
    fn describe(&self) -> String {          // 可以有默认实现
        format!("area = {}", self.area())
    }
}

impl Area for Point {                        // 显式实现（Go 是隐式满足）
    fn area(&self) -> f64 { 0.0 }
}
```

| | Go interface | Rust trait |
|---|---|---|
| 实现方式 | **隐式**：方法签名匹配即满足 | **显式**：必须写 `impl Trait for Type` |
| 默认方法 | ❌ | ✅ |
| 静态分发 | ❌ 总是动态分发 | ✅ 默认静态（泛型单态化） |
| 动态分发 | `interface{}` | `dyn Trait`（需显式写 `dyn`） |
| 能约束泛型吗 | Go 1.18+ 的约束比较弱 | ✅ trait bound 是泛型的核心 |

**泛型与 trait bound**：

```rust
fn largest<T: PartialOrd>(list: &[T]) -> &T { ... }

// where 从句写法（约束多时更清晰）
fn process<T, U>(t: T, u: U) -> i32
where
    T: Display + Clone,
    U: Clone + Debug,
{ ... }

// 静态分发 vs 动态分发
fn draw_static(item: &impl Area) { }      // 泛型糖，编译期单态化，零开销
fn draw_dynamic(item: &dyn Area) { }      // trait object，运行时 vtable，≈ Go 的 interface
```

**你会反复见到的几个标准 trait**：

| trait | 作用 | 关联章节 |
|---|---|---|
| `Copy` | 赋值时按位复制而非移动 | 04 |
| `Clone` | 显式深拷贝 `.clone()` | 04 |
| `Drop` | 析构函数，值销毁时调用 | 04, 12 |
| `Deref` / `DerefMut` | 自动解引用，`String → &str` 靠它 | 05 |
| `Send` / `Sync` | 能否跨线程移动 / 共享 | 22 |
| `Iterator` | 迭代 | 05, 14 |
| `Sized` | 编译期已知大小（隐式默认 bound） | 13 |
| `Unpin` | 能否安全移动（自引用相关） | 13, 24 |

---

## 7. 引用语法速览（第 05/06 章会彻底展开）

```rust
let x = 5;
let r: &i32 = &x;          // 共享引用（可以有很多个）
println!("{}", *r);        // 解引用；很多场合可省略，编译器自动 deref

let mut y = 5;
let m: &mut i32 = &mut y;  // 可变引用（同一时刻只能有一个，且不能与共享引用共存）
*m += 1;

// 生命周期标注（第 06 章主角）
fn longest<'a>(a: &'a str, b: &'a str) -> &'a str {
    if a.len() > b.len() { a } else { b }
}
```

**现在只要记住三条规则**（第 05 章讲为什么）：
1. 任意时刻，对同一份数据，要么有**任意多个** `&T`，要么有**恰好一个** `&mut T`，**不能同时**。
2. 引用不能比它指向的数据活得更久。
3. 引用永远指向有效数据（没有 nil 引用，没有悬垂引用）。

---

## 8. 闭包

```rust
let add = |a: i32, b: i32| a + b;
let add2 = |a, b| a + b;             // 类型从调用点推断
println!("{}", add2(1, 2));          // ← 没有这行就推断不出来，报 E0284
let block = |x: i32| { let y = x * 2; y + 1 };

// 强制移动捕获
let s = String::from("hi");
let f = move || println!("{}", s);   // s 被移动进闭包
```

闭包按**捕获方式**自动实现三个 trait 之一，这直接决定它能不能跨线程、能不能调用多次：

| trait | 捕获方式 | 能调用几次 | Go 类比 |
|---|---|---|---|
| `Fn` | `&T` 借用 | 多次 | 只读外层变量的闭包 |
| `FnMut` | `&mut T` 借用 | 多次（需 `mut` 绑定） | 修改外层变量的闭包 |
| `FnOnce` | 移动所有权 | **一次** | Go 里没有对应概念 |

> **Go 对照**：Go 的闭包总是按引用捕获（捕获变量会逃逸到堆上）。这也是
> `for i := range xs { go func(){ use(i) }() }` 经典 bug 的来源（Go 1.22 才改）。
> Rust 强制你在 `move` 和借用之间做选择，所以这个 bug 类别在 Rust 里不存在——
> 但代价是你要理解捕获语义。第 22/23 章详述。

---

## 9. 错误处理与 `?`

```rust
fn read_config() -> Result<Config, std::io::Error> {
    let s = std::fs::read_to_string("config.toml")?;   // ? = 出错就 return Err
    Ok(parse(s))
}

opt.unwrap()            // None 就 panic
opt.expect("msg")       // None 就 panic 并打印 msg
opt.unwrap_or(default)
opt.map(|x| x + 1)
opt.and_then(|x| f(x))
```

> **Go 对照**：`?` 就是 `if err != nil { return nil, err }` 的语法糖。
> 本课程里 `unwrap()` 会用得很多——那是为了让例子聚焦在借用上，
> **不是**生产代码的推荐写法。

---

## 10. 智能指针速览（第 19/20 章展开）

| 类型 | 一句话 | Go 类比 |
|---|---|---|
| `Box<T>` | 把 T 放堆上，唯一所有者 | `new(T)` 返回的指针 |
| `Rc<T>` | 引用计数共享所有权，**单线程** | 手写引用计数 |
| `Arc<T>` | 原子引用计数，**可跨线程** | 手写原子引用计数 |
| `RefCell<T>` | **运行时**检查借用规则，违反就 panic | 没有对应物 |
| `Cell<T>` | 整体读写替换，无引用泄漏 | 没有对应物 |
| `Mutex<T>` | 互斥锁，锁住的是**数据本身**不是代码段 | `sync.Mutex` + 被保护的变量（但 Rust 把它们绑在一起） |
| `RwLock<T>` | 读写锁 | `sync.RWMutex` |

⚠️ **`Rc<RefCell<T>>` 是新手的止痛药**。它能让几乎任何借用错误消失，
代价是把编译期检查换成运行时 panic。第 18/19 章会告诉你什么时候它是**正确**的选择，
什么时候它是"你没想清楚数据结构"的信号。

---

## 11. 模块与可见性（够用就行）

```rust
mod network {                       // 内联模块
    pub fn connect() {}             // pub 才对外可见（默认私有）
    pub(crate) fn internal() {}     // 只在本 crate 内可见
    mod server { }                  // 嵌套
}

use std::collections::HashMap;      // 引入
use std::collections::{HashMap, HashSet};
use network::connect as net_connect;
```

`crate` = 一个编译单元（一个 lib 或一个 bin）；`package` = 一个 `Cargo.toml`。
对照 Go：Rust 的 `crate` ≈ Go 的 module，Rust 的 `mod` ≈ Go 的 package（但不需要单独目录）。

---

## 12. 动手：把一段 Go 翻译成 Rust

这是本章唯一的实验。先自己写，再看答案。

**原始 Go 代码**：

```go
type Stack struct {
    items []int
}

func (s *Stack) Push(v int) { s.items = append(s.items, v) }

func (s *Stack) Pop() (int, bool) {
    if len(s.items) == 0 {
        return 0, false
    }
    v := s.items[len(s.items)-1]
    s.items = s.items[:len(s.items)-1]
    return v, true
}

func (s *Stack) Peek() *int {
    if len(s.items) == 0 {
        return nil
    }
    return &s.items[len(s.items)-1]
}
```

<details>
<summary>Rust 版本（点开前先自己试）</summary>

```rust
pub struct Stack {
    items: Vec<i32>,
}

impl Stack {
    pub fn new() -> Self {
        Stack { items: Vec::new() }
    }

    pub fn push(&mut self, v: i32) {
        self.items.push(v);
    }

    // (int, bool) → Option<i32>
    pub fn pop(&mut self) -> Option<i32> {
        self.items.pop()
    }

    // *int → Option<&i32>，注意这里有个隐藏的生命周期
    pub fn peek(&self) -> Option<&i32> {
        self.items.last()
    }
}
```

**三个值得注意的差别**：

1. `(int, bool)` → `Option<i32>`。Go 靠约定，Rust 靠类型。

2. `*int` → `Option<&i32>`。Go 返回的裸指针**可能悬垂**：调用者拿到 `p := s.Peek()`，
   然后 `s.Push(1)` 触发 `append` 扩容重新分配底层数组，`p` 就指向了旧数组。
   Go 的 GC 保证那块内存不会被回收（所以不崩溃），但 `*p` 读到的是**陈旧数据**——
   一个静默的逻辑 bug。

   Rust 版本里，`peek` 的完整签名其实是
   `fn peek<'a>(&'a self) -> Option<&'a i32>`（生命周期省略规则，第 06 章）。
   编译器因此知道返回的引用借用了 `self`，于是：

   ```rust
   let mut s = Stack::new();
   s.push(1);
   let p = s.peek();      // 借用 s
   s.push(2);             // ❌ E0502: cannot borrow `s` as mutable
                          //    because it is also borrowed as immutable
   println!("{:?}", p);
   ```

   **这就是这门课要讲的一切的缩影**：同一个 bug，Go 让你在生产环境里发现，
   Rust 在编译期挡住。而挡住的代价，就是你得学会本课程剩下的 27 章。

3. 如果 `p` 在 `s.push(2)` 之前就不再使用了，上面的代码**是能编译的**——
   这就是 NLL（第 07 章）。删掉最后一行 `println!` 试试。

</details>

---

## 13. 本章检查清单

在进入第 01 章之前，确认你能：

- [ ] 说出 `String` 和 `&str` 的区别，并知道哪个"拥有"数据
- [ ] 说出 `fn f(self)` / `fn f(&self)` / `fn f(&mut self)` 三者的差别
- [ ] 读懂 `match` 的穷尽性和三种绑定模式（`&opt` / `opt` / `&mut opt`）
- [ ] 说出 `Fn` / `FnMut` / `FnOnce` 分别对应哪种捕获
- [ ] 背出借用三规则
- [ ] 独立完成第 12 节的翻译练习，并解释为什么 `peek` 之后不能 `push`

---

## 14. 常见坑（本章范围内）

| 现象 | 原因 | 处方 |
|---|---|---|
| `error[E0382]: borrow of moved value` | 把值传给函数/赋给别人之后又用了原变量 | 传 `&x` 而不是 `x`；或 `.clone()`；第 04 章讲怎么选 |
| `expected &str, found String` | `String` 不会自动变 `&str`（在泛型位置） | 写 `&s` 或 `s.as_str()` |
| `cannot find value x in this scope`（match 之后） | `match opt { Some(x) => ... }` 里的 `x` 只在分支内有效 | 正常，Rust 没有 Go 那种"if 里声明的变量泄漏到外面" |
| `for x in v` 之后 `v` 不能用了 | `IntoIterator for Vec<T>` 消耗了 v | 写 `for x in &v` |
| 到处都要写 `&`、`*`、`.clone()` | 正在用 Go 的方式写 Rust | 正常现象。第 04–06 章之后会好转；如果学完还是这样，说明数据结构设计需要调整 |

---

下一章：[01 - 内存安全的历史债](01-memory-safety-history.md)——borrow checker 到底在防什么。
