# 04 - 所有权与移动

> 本章目标：把"所有权"从口号变成可以精确推演的规则。
> 重点是三件事：**移动到底发生了什么**（答案可能出乎意料）、**drop 的精确时机和顺序**、
> **NLL 时代最大的不对称性——借用止于最后一次使用，但 drop 在作用域末尾**。
> 预计用时：2.5 小时。

---

## 1. 所有权的三条规则

Rust 官方教材的经典表述：

1. Rust 中每一个值都有一个**所有者（owner）**
2. 值在任一时刻**有且只有一个**所有者
3. 当所有者离开作用域，这个值将被 **drop**

这三条是第 03 章公理的直接推论（销毁是最彻底的写，所以销毁权必须独占）。

但这个表述有个问题：它把"所有权"说得像个运行时概念。**它不是。**
所有权完全是编译期的：**没有任何运行时数据结构记录"谁是所有者"**。
编译器只是在每个变量上追踪一个静态标记——"此刻已初始化 / 已被移走"。

---

## 2. 移动到底发生了什么

### 2.1 一个必须打破的误解

```rust
let a = String::from("hello");
let b = a;                        // "移动"
```

很多教程说"所有权从 a 移动到 b"，配一张箭头图。这在语义层面是对的，
但**在机器层面发生的事情是**：

```
1. 把 a 的栈上表示（ptr, len, cap，共 24 字节）按位复制到 b
2. 编译器把 a 标记为「已移走（moved-out）」，之后禁止读取
3. 编译器把「在作用域末尾 drop a」这个动作删掉，改成 drop b
```

**注意第 1 步：移动就是 memcpy。** 它**不比 Copy 便宜**。
`let b = a;` 对 `String` 和对 `[u8; 24]` 生成的机器码是一样的（都是 24 字节复制，
且大多被优化掉）。

**移动和复制在运行时是同一件事，区别纯粹在编译期**：
- `Copy` 类型：复制之后，**源仍然可用**
- 非 `Copy` 类型：复制之后，**源被标记为失效**，且 drop 责任转移

> ### 这个认知能解决一大类困惑
>
> "移动大结构体是不是很慢？" → 和复制一样快/慢；且 `let b = a;` 通常被优化成零指令
> （编译器直接让 b 用 a 的栈槽）。真正的开销来自**跨函数边界的按值传参**，
> 那是 ABI 决定的，和所有权无关。
>
> "为什么不能 `let b = a;` 之后还用 a？" → 因为两个变量会在作用域末尾各自 drop 一次，
> 那就是 double free。禁止使用 a 是**唯一**能防止这件事的办法。

### 2.2 什么操作会移动

```rust
let s = String::from("x");

let t = s;                 // 赋值
fn f(s: String) {}  f(s);  // 按值传参
fn g() -> String { s }     // 按值返回
let v = vec![s];           // 放进容器
let c = move || drop(s);   // move 闭包捕获
match s { _ => {} }        // match 一个非 Copy 值（除非模式是 ref / &）
for x in v {}              // IntoIterator 消耗容器
```

### 2.3 `Copy`：什么时候复制不算移动

```rust
#[derive(Clone, Copy)]
struct Point { x: f64, y: f64 }

let p = Point { x: 1.0, y: 2.0 };
let q = p;
println!("{}", p.x);          // ✅ p 仍然可用
```

`Copy` 是一个 **marker trait**，含义是"这个类型按位复制之后，两个副本都是有效的独立值"。

**能实现 `Copy` 的条件**：
1. 所有字段都是 `Copy`
2. **没有实现 `Drop`**（第 2 点是硬性的：`Copy` 和 `Drop` 互斥）

第 2 点的理由回到公理：如果一个类型既 `Copy` 又 `Drop`，那么 `let b = a;` 之后
两个变量都会 drop，还是 double free。

**内置 `Copy` 的类型**：所有整数/浮点/bool/char、`&T`（**共享引用是 Copy 的！**）、
裸指针、由 `Copy` 组成的数组和元组、`Option<T> where T: Copy`。

**内置**不是** `Copy` 的重要类型**：`String`、`Vec<T>`、`Box<T>`、
**`&mut T`**（独占引用不能 Copy——复制一份就有两个独占了，见第 05 章的 reborrow）。

### 2.4 `Clone`：显式的深拷贝

```rust
let a = String::from("hi");
let b = a.clone();            // 分配新的堆内存并复制内容
println!("{} {}", a, b);      // 两个都可用
```

> ### 关于 `.clone()` 的一句忠告
>
> 新手会被告诫"不要滥用 clone"。这个建议**有害**。正确的说法是：
>
> **`.clone()` 是一个完全正当的工程手段。它的问题从来不是性能，是它掩盖了设计问题。**
>
> - 克隆一个 8 字节的 `String`？成本可忽略，随便用
> - 在热循环里克隆一个 10MB 的 `Vec`？那是性能问题，但你会 profile 出来
> - **用 `.clone()` 让一个借用错误消失，而你不知道为什么会有那个错误**？
>   ← 这才是真正的问题。你埋掉了一个信号
>
> 本课程的立场：先用 `.clone()` 让代码跑起来，然后**回头问自己为什么需要它**。
> 如果答案是"因为两个地方都要拥有这份数据"，那 clone 是对的。
> 如果答案是"不知道，编译器让我加的"，回来读第 18 章。

---

## 3. Drop：精确的时机与顺序

这一节的所有结论都在 macOS / rustc 1.96 上实测过（脚本见本章第 8 节）。

### 3.1 `Drop` trait

```rust
struct D(&'static str);
impl Drop for D {
    fn drop(&mut self) { println!("drop {}", self.0); }
}
```

注意签名是 `fn drop(&mut self)`——**不是** `fn drop(self)`。
理由：如果是 `self`，drop 函数结束时又要 drop 一次，无限递归。
所以 `Drop::drop` 拿到的是 `&mut self`，**你不能在里面把字段移走**（E0507），
需要移走的话得用 `Option::take` 或 `ManuallyDrop`。

**你不能手动调用 `x.drop()`**（E0040）。要提前销毁请用 `drop(x)`（那个函数的实现是 `fn drop<T>(_: T) {}`——
把 x 移进去，函数结束时自然销毁，非常优雅）。

### 3.2 顺序（实测结果）

| 场景 | 顺序 | 记忆法 |
|---|---|---|
| **同一作用域的局部变量** | **逆序**（后声明的先 drop） | 栈：后进先出 |
| **结构体字段** | **顺序**（声明顺序） | 和局部变量相反！ |
| **元组元素** | 顺序（左到右） | 同结构体 |
| **`Vec<T>` 的元素** | 顺序（下标 0 → n） | 同结构体 |
| **枚举变体的字段** | 顺序 | 同结构体 |

```rust
{ let _x = D("x"); let _y = D("y"); }
// drop y
// drop x                    ← 逆序

struct S { a: D, b: D }
{ let _s = S { a: D("a"), b: D("b") }; }
// drop a
// drop b                    ← 顺序！
```

> **为什么局部变量逆序而字段顺序？**
> 局部变量逆序是因为后声明的可能借用了先声明的（`let a = ...; let b = &a;`），
> 必须先销毁借用方。结构体字段之间不能互相借用（那是自引用，第 13 章说了做不到），
> 所以没有这个约束，用最自然的声明顺序。

### 3.3 `let _ = ...` 的经典陷阱（实测）

```rust
{ let _ = D("A"); println!("after"); }
// drop A
// after                     ← A 立刻就 drop 了！

{ let _n = D("B"); println!("after"); }
// after
// drop B                    ← B 活到作用域末尾
```

**`_` 不是一个绑定，是"丢弃模式"。** `let _ = expr;` 的意思是"求值 expr 然后立刻扔掉"，
所以值在**语句结束时**就 drop 了。而 `let _n = expr;` 创建了一个真实的绑定。

**这个差别会造成真实的 bug**：

```rust
let _ = mutex.lock().unwrap();      // ❌ 锁立刻就释放了！后面的代码没有保护
critical_section();

let _guard = mutex.lock().unwrap(); // ✅ 锁持有到作用域末尾
critical_section();
```

**同一个陷阱的另一面**（第 11 章会再遇到）：`let _ = x;` 在 `move` 闭包里
**不会捕获 x**（因为 `_` 不是绑定）——所以下面这段能编译：

```rust
let r = Rc::new(1);
std::thread::spawn(move || { let _ = r; });    // ✅ 编译通过！r 根本没被捕获
```

而把 `let _ = r;` 换成 `println!("{}", r);` 立刻变成 `E0277: Rc<i32> cannot be sent`。
（lab 里的 24 / 25 号案例就是这一对。）

### 3.4 ★ 最重要的不对称性：借用止于最后一次使用，drop 在作用域末尾

**这是 NLL 时代最容易出错的地方，请重点记住。**

```rust
{
    let a = D("A");
    let r = &a;
    println!("{}", r.0);      // r 的借用在这里结束（NLL）
    println!("r 已经没用了");   // 此刻 a 上没有活跃借用
}                             // drop A 在这里
```

```
时间轴：
      let a          let r=&a       用 r         作用域末尾
        │               │             │              │
  a:    ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━● drop
  借用r:                ●━━━━━━━━━━━━━●
                                      ↑
                              借用在这里就结束了（NLL），
                              但 a 一直活到作用域末尾
```

**为什么这个不对称很重要？** 因为它造成两类相反的困惑：

**困惑 A：借用结束得比我想的早**
```rust
let r;
{
    let a = String::from("x");
    r = &a;              // ❌ E0597: `a` does not live long enough
}
println!("{}", r);
```
这里失败不是因为借用，是因为 **`a` 在块末尾被 drop 了**。

**困惑 B：值 drop 得比我想的晚**（第 12 章展开）
```rust
let m = Mutex::new(0);
let g = m.lock().unwrap();
// ... 一大段不用 g 的代码
// 锁一直持有到作用域末尾，即使 g 早就不用了
```
**借用会因为 NLL 提前结束，但 `Drop` 不会。** 有 `Drop` 实现的类型（`MutexGuard`、
`File`、`RefMut`）**必须显式管理作用域**：

```rust
{
    let g = m.lock().unwrap();
    *g += 1;
}                              // 锁在这里释放
// 或者
drop(g);
```

### 3.5 dropck：drop 检查的额外约束

有 `Drop` 实现的类型会触发一层额外的检查，叫 **dropck**。下面三个函数的差别只有声明顺序
和有没有 `Drop`，但结果完全不同（**已实测**）：

```rust
struct Holder<'a>(&'a str);
impl<'a> Drop for Holder<'a> {
    fn drop(&mut self) { println!("{}", self.0); }   // ★ drop 时读了那个引用
}
struct NoDrop<'a>(&'a str);                          // 没有 Drop 实现

pub fn ok() {
    let s = String::from("hi");
    let _h = Holder(&s);          // ✅ 局部变量逆序 drop：_h 先死，s 后死
}

pub fn bad() {
    let _h;
    let s = String::from("hi");
    _h = Holder(&s);              // ❌ E0597: `s` does not live long enough
}                                 //    因为 _h 先声明 → 后 drop，此时 s 已经没了

pub fn nodrop_ok() {
    let _h;
    let s = String::from("hi");
    _h = NoDrop(&s);              // ✅ 一模一样的顺序，但没有 Drop → 通过
}
```

**`bad` 和 `nodrop_ok` 的唯一差别就是有没有 `impl Drop`。** 这就是 dropck 的全部含义：

> **如果类型 `T` 实现了 `Drop`，那么 `T` 的所有生命周期参数和泛型参数
> 必须严格长于 `T` 本身**——因为 `T::drop` 可能会用到它们。
>
> 没有 `Drop` 的类型不受此限：它的字段可以和它同时死掉（反正没人会去读）。

**逃生舱 `#[may_dangle]`**（不稳定，标准库专用）：`Vec<T>` 的 `Drop` 需要遍历元素来 drop 它们，
但它承诺"我只 drop 元素，绝不读取它们内部的引用"，所以标了：

```rust
unsafe impl<#[may_dangle] T, A: Allocator> Drop for Vec<T, A> { ... }
```

这是 `Vec<&'a str>` 能和 `'a` 同时死掉的原因。第 26 章会再讲它和 unsafe 契约的关系。

**实用推论**：如果你给一个带生命周期参数的类型加了 `impl Drop`，
**你可能会让下游用户的代码莫名其妙编译不过**。加 `Drop` 之前先问自己是不是真的需要。

## 4. 部分移动（partial move）

```rust
struct Pair { a: String, b: String }

let p = Pair { a: "x".into(), b: "y".into() };
let a = p.a;                 // 只移走 a 字段
println!("{}", p.b);         // ✅ b 还在
// println!("{:?}", p);      // ❌ E0382: p 已被部分移动，整体不可用
```

**编译器按 place（位置）粒度追踪初始化状态**，不是按变量。
`p.a` 被移走了，`p.b` 没有，所以 `p` 处于"部分初始化"状态：
- 可以继续访问 `p.b`
- 不能把 `p` 整体传走
- 作用域结束时只 drop `p.b`

⚠️ **两个限制**：

1. **实现了 `Drop` 的类型不能部分移动**（E0509）。因为 drop 需要完整的值。
   ```rust
   struct P { a: String } 
   impl Drop for P { fn drop(&mut self) {} }
   let p = P { a: "x".into() };
   let a = p.a;    // ❌ E0509: cannot move out of type `P`, which implements `Drop`
   ```

2. **不能从引用后面部分移动**（E0507）：
   ```rust
   fn f(p: &Pair) { let a = p.a; }    // ❌ E0507: cannot move out of `p.a` which is behind a shared reference
   ```
   这条极其常见，见下一节。

---

## 5. E0507：不能从借用里移动——以及五种解法

```rust
fn take_name(person: &Person) -> String {
    person.name          // ❌ E0507
}
```

**为什么禁止**：你只借了 `person`，移走 `name` 会让所有者手上的 `person` 变成部分初始化，
但所有者对此一无所知。

**五种解法**，按优先级：

| 手法 | 代码 | 适用场景 |
|---|---|---|
| **1. 改成借用** | `fn take_name(p: &Person) -> &str { &p.name }` | 调用方只需要读 → **首选** |
| **2. clone** | `p.name.clone()` | 调用方需要拥有，且复制成本可接受 |
| **3. 改成拿所有权** | `fn take_name(p: Person) -> String { p.name }` | 调用方不再需要 `Person` |
| **4. `mem::take`** | `fn take_name(p: &mut Person) -> String { std::mem::take(&mut p.name) }` | 有 `&mut`，且留个默认值可接受 |
| **5. `mem::replace`** | `std::mem::replace(&mut p.name, "unknown".into())` | 同上但要指定替代值 |
| **6. `Option::take`** | 字段本身是 `Option<T>`，`p.name.take()` | 字段语义上就是"可能没有" |

**`mem::take` / `mem::replace` / `mem::swap` 是本课程最重要的三个工具函数**，
第 18 章会把它们提升到"标准手法"的地位。它们的作用是：
**在只有 `&mut` 的情况下，合法地把值搬出来**——办法是**同时放一个替代品进去**，
保证 `&mut` 指向的位置始终是有效值。

```rust
// 三者的关系
pub fn replace<T>(dest: &mut T, src: T) -> T;              // 放 src 进去，把旧的拿出来
pub fn take<T: Default>(dest: &mut T) -> T;                // = replace(dest, T::default())
pub fn swap<T>(a: &mut T, b: &mut T);                      // 交换两处的值
```

一个典型应用——**在 `&mut self` 方法里重建 self 的一部分**：

```rust
impl Buffer {
    fn flush(&mut self) -> Vec<u8> {
        std::mem::take(&mut self.data)     // 拿走数据，留一个空 Vec
    }
    fn transform(&mut self) {
        let old = std::mem::take(&mut self.data);
        self.data = old.into_iter().map(|x| x * 2).collect();   // 消耗 old
    }
}
```

`transform` 里如果直接写 `self.data = self.data.into_iter()...` 会报 E0507——
因为 `into_iter` 要消耗 `self.data`，而你只有 `&mut self`。

---

## 6. `Box` 的特权：可以移动出来

```rust
let b: Box<String> = Box::new("x".into());
let s: String = *b;          // ✅ 可以！
```

**`Box<T>` 是唯一可以"解引用移动（deref move）"的类型**——因为它是语言内置的
（`box_deref` 是编译器特殊处理的）。任何自定义的智能指针（包括 `Rc`）都做不到：

```rust
let r: Rc<String> = Rc::new("x".into());
let s: String = *r;          // ❌ E0507: cannot move out of an `Rc`
let s: String = Rc::try_unwrap(r).unwrap();   // ✅ 只有引用计数 == 1 时才行
```

这个特权在写递归数据结构时很有用（第 20 章）。

---

## 7. 与 Go 的对照速查

| 操作 | Go | Rust | 关键差别 |
|---|---|---|---|
| `b := a`（结构体） | 浅拷贝，两个都可用 | 移动，`a` 失效（除非 `Copy`） | Rust 防止了 double free |
| `b := a`（slice） | 复制 header，**共享底层数组** | 移动 `Vec`，或 `&`/`&mut` 借用 | Go 的隐式共享是别名 bug 之源 |
| 传结构体给函数 | 复制一份 | 移动，或借用 | — |
| `defer f.Close()` | 手动 | `Drop` 自动 | Rust 不可能忘 |
| 提前关闭 | `f.Close()` | `drop(f)` 或用块 | — |
| 结构体字段部分取出 | 随便取 | 部分移动，有 `Drop` 时禁止 | — |
| `nil` | 到处都是 | 不存在；用 `Option<T>` | — |
| GC 决定何时回收 | 不确定 | **编译期确定** | Rust 可以做确定性资源管理 |

---

## 8. 动手实验

### 实验 1：亲手验证 drop 顺序

```bash
mkdir -p /tmp/drop-lab && cd /tmp/drop-lab && cat > main.rs <<'RSEOF'
struct D(&'static str);
impl Drop for D { fn drop(&mut self) { println!("drop {}", self.0); } }
struct S { a: D, b: D }

fn main() {
    println!("-- 局部变量 --");
    { let _x = D("x"); let _y = D("y"); }
    println!("-- 结构体字段 --");
    { let _s = S { a: D("field.a"), b: D("field.b") }; }
    println!("-- Vec 元素 --");
    { let _v = vec![D("v0"), D("v1")]; }
    println!("-- let _ vs let _name --");
    { let _  = D("underscore");      println!("  after"); }
    { let _n = D("underscore_name"); println!("  after"); }
    println!("-- 借用早结束，drop 在作用域末尾 --");
    { let a = D("A"); let r = &a; println!("  use {}", r.0); println!("  r 已不用"); }
}
RSEOF
rustc --edition 2024 main.rs -o drop_lab && ./drop_lab
```

**预期输出**（本课程实测）：
```
-- 局部变量 --
drop y
drop x                       ← 逆序
-- 结构体字段 --
drop field.a
drop field.b                 ← 顺序
-- Vec 元素 --
drop v0
drop v1
-- let _ vs let _name --
drop underscore              ← 立刻！
  after
  after
drop underscore_name         ← 作用域末尾
-- 借用早结束，drop 在作用域末尾 --
  use A
  r 已不用
drop A
```

### 实验 2：移动的真实成本

```rust
fn main() {
    let big = vec![0u8; 100_000_000];    // 100MB
    let t = std::time::Instant::now();
    let moved = big;                      // 移动
    println!("移动 100MB Vec 耗时: {:?}", t.elapsed());
    println!("{}", moved.len());
}
```

用 `cargo run --release` 跑。你会看到耗时是**纳秒级**——因为移动只复制了
24 字节的 `(ptr, len, cap)`，堆上的 100MB 一个字节都没动。

然后把 `let moved = big;` 改成 `let moved = big.clone();`，再跑一次。**对比数量级。**

### 实验 3：E0507 的五种解法

```rust
#[derive(Debug)]
struct Person { name: String, age: u32 }

fn main() {
    let mut p = Person { name: "Alice".into(), age: 30 };

    // 补全下面五个函数，让 main 编译通过
    // fn by_ref(p: &Person) -> &str        { todo!() }
    // fn by_clone(p: &Person) -> String    { todo!() }
    // fn by_value(p: Person) -> String     { todo!() }
    // fn by_take(p: &mut Person) -> String { todo!() }
    // fn by_replace(p: &mut Person) -> String { todo!() }
}
```

<details><summary>答案</summary>

```rust
fn by_ref(p: &Person) -> &str           { &p.name }
fn by_clone(p: &Person) -> String       { p.name.clone() }
fn by_value(p: Person) -> String        { p.name }
fn by_take(p: &mut Person) -> String    { std::mem::take(&mut p.name) }
fn by_replace(p: &mut Person) -> String { std::mem::replace(&mut p.name, "unknown".into()) }
```

注意 `by_take` 之后 `p.name` 变成 `""`，`by_replace` 之后变成 `"unknown"`。
**它们都保证了 `p` 在任何时刻都是完整有效的值**——这就是为什么它们是安全的。

</details>

---

## 9. 本章检查清单

- [ ] 知道"移动"在机器层面就是 memcpy + 编译期标记
- [ ] 能说出 `Copy` 的两个前提条件，以及为什么 `&mut T` 不是 `Copy`
- [ ] 能背出五种 drop 顺序（局部变量逆序，字段/元组/Vec 顺序）
- [ ] 知道 `let _ = x` 和 `let _n = x` 的区别，以及它在 `Mutex` 和闭包捕获上的后果
- [ ] **能画出"借用止于最后一次使用，drop 在作用域末尾"的时间轴**
- [ ] 知道 `Drop` 类型不能部分移动（E0509）
- [ ] 知道 E0507 的五种解法，尤其是 `mem::take` / `mem::replace` 的原理
- [ ] 知道 `Box` 可以 deref move 而 `Rc` 不行

---

## 10. 常见坑

| 现象 | 错误码 | 原因 | 处方 |
|---|---|---|---|
| 移动后又使用 | E0382 | 非 `Copy` 类型被移走 | 传 `&`；或 `.clone()`；或调整顺序 |
| 从引用后面移动 | E0507 | 只有借用权，没有所有权 | 见第 5 节的六种解法 |
| `Drop` 类型部分移动 | E0509 | drop 需要完整的值 | 把字段改成 `Option<T>` 用 `take()`；或用 `ManuallyDrop` |
| 手动调 `x.drop()` | E0040 | 会导致 double drop | 用 `drop(x)` |
| 锁没有按预期释放 | 无（逻辑 bug） | `MutexGuard` 活到作用域末尾 | 用块 `{}` 收缩作用域；或 `drop(guard)` |
| 锁根本没生效 | 无（逻辑 bug） | 写成了 `let _ = m.lock()` | 改成 `let _guard = m.lock()` |
| `impl Copy` 报错 | E0184 | 类型实现了 `Drop` | 二选一 |
| 结构体字段 drop 顺序不对 | 无 | 字段是**声明顺序** drop | 调整字段声明顺序（这是个真实的技巧，比如让 `MutexGuard` 字段排在被保护数据之前） |
| `Vec` 的 `into_iter` 之后原变量不可用 | E0382 | `IntoIterator for Vec<T>` 消耗容器 | 用 `.iter()` 或 `&v` |

---

下一章：[05 - 借用、重借用、两阶段借用](05-borrowing.md)
