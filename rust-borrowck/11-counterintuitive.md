# 11 - 反直觉合集：25 个最小复现

> 本章目标：把散落在各章的"这不科学"集中起来，每个给出**最小复现 + 根因 + 处方**。
> 这是一章**查阅型**内容——建议先通读一遍建立索引，遇到问题时回来查。
> 所有例子都在 `rustc 1.96.0` / `1.100.0-nightly`、edition 2024 上实测过。
> 预计用时：3 小时。

**图例**：`✅` 编译通过 · `❌` 编译失败 · `💥` 编译通过但运行时出事 · `⚠️` 有警告

---

## 目录

| # | 反直觉 | 类别 |
|---|---|---|
| 1 | `let _ = x` 立刻 drop，`let _n = x` 不会 | drop |
| 2 | `let _ = x` 在 `move` 闭包里**不捕获** x | 闭包 |
| 3 | `drop(&x)` 什么也不做 | drop |
| 4 | 局部变量逆序 drop，结构体字段顺序 drop | drop |
| 5 | 借用止于最后一次使用，drop 在作用域末尾 | drop |
| 6 | `v.push(v.len())` ✅ 但 `Vec::push(&mut v, v.len())` ❌ | 借用 |
| 7 | `let s = r;` 是移动，`let s: &mut T = r;` 是重借用 | 借用 |
| 8 | `&T` 是 `Copy`，`&mut T` 不是 | 类型 |
| 9 | 数组的常量下标**也不能**分割借用 | 借用 |
| 10 | 方法借走整个 `self`，直接访问字段不会 | 借用 |
| 11 | `T: 'static` 不代表"永生" | 生命周期 |
| 12 | 加一个 `impl Drop` 可能让下游代码编译不过 | dropck |
| 13 | 加一个 `RefCell` 字段可能让远处的生命周期报错 | 型变 |
| 14 | 闭包不享受生命周期省略规则 | 闭包 |
| 15 | 方法返回 `&str` 默认绑到 `&self` 而非参数 | 生命周期 |
| 16 | `struct update` 语法是**部分**移动 | 移动 |
| 17 | `arr[0]` 不能移动出来，但 `arr` 整体可以 | 移动 |
| 18 | `a + "b"` 消耗 `a` | 移动 |
| 19 | `Box<T>` 能 deref-move，`Rc<T>` 不能 | 移动 |
| 20 | `RefCell` 不是"绕过"检查，是移到运行时 | 内部可变性 |
| 21 | 2021 edition 的 `if let` 会在 `else` 分支里持锁 → 死锁 | edition |
| 22 | 2021 edition 的尾表达式临时值 drop 顺序会报 E0597 | edition |
| 23 | 2018 edition 的闭包捕获整个结构体 | edition |
| 24 | 临时值延长规则**不穿透方法调用** | 临时值 |
| 25 | `Polonius` 接受的代码在 stable 上仍然编译不过 | 版本 |

---

## 类别一：drop 与作用域

### 1. `let _ = x` 立刻 drop，`let _n = x` 不会

```rust
struct D(&'static str);
impl Drop for D { fn drop(&mut self) { println!("drop {}", self.0); } }

{ let _  = D("A"); println!("after"); }   // 输出: drop A / after   ★ 立刻
{ let _n = D("B"); println!("after"); }   // 输出: after / drop B
```

**根因**：`_` 不是绑定，是**丢弃模式**。`let _ = expr;` 的语义是"求值 expr 然后立刻扔掉"。

**咬人的场景**：

```rust
let _ = refcell.borrow_mut();        // 💥 借用立刻释放，临界区裸奔
critical_section();

let _guard = refcell.borrow_mut();   // ✅
critical_section();
```

> ### ★ 2026 更新：`Mutex`/`RwLock` 这一种编译器已经拦住了
> ```rust
> let _ = mutex.lock().unwrap();
> // error: non-binding let on a synchronization lock  ← deny-by-default 的 let_underscore_lock
> ```
> 但这个 lint **只认标准库的同步锁**。实测下面这些一律放行：
>
> | 写法 | 编译器拦不拦 |
> |---|---|
> | `let _ = mutex.lock().unwrap();` | ✅ 拦（`let_underscore_lock`，硬错误） |
> | `let _ = rwlock.write().unwrap();` | ✅ 拦 |
> | `let _ = refcell.borrow_mut();` | ❌ **不拦** |
> | `let _ = File::open(..);` | ❌ **不拦** |
> | `let _ = my_custom_guard();` | ❌ **不拦** |
>
> **所以这条反直觉今天依然咬人**——只是咬人的位置从 `Mutex` 挪到了
> `RefCell`、tracing 的 span guard、以及你自己写的 RAII 类型上。

**处方**：任何 RAII guard（`MutexGuard`、`RefMut`、`File`、span guard）**必须绑定到具名变量**。
用 `_guard` 这个名字既能避免 unused 警告，又能保住作用域。

---

### 2. `let _ = x` 在 `move` 闭包里**不捕获** x

```rust
use std::rc::Rc;
let r = Rc::new(1);
std::thread::spawn(move || { let _ = r; });          // ✅ 编译通过！

let r = Rc::new(1);
std::thread::spawn(move || { println!("{}", r); });  // ❌ E0277: Rc<i32> cannot be sent
```

**根因**：同第 1 条——`_` 不是绑定，所以闭包捕获分析认为 `r` 根本没被用到。

**为什么重要**：这是一个**假阴性**。你以为写了 `let _ = r;` 就"用到了" `r`（比如为了保住它的生命期），
其实什么都没发生。lab 的 24 / 25 号案例就是这一对。

**处方**：想在闭包里保住一个值，用 `let _keep = r;` 或 `drop(r);`。

---

### 3. `drop(&x)` 什么也不做

```rust
let g = mutex.lock().unwrap();
drop(&g);                            // ⚠️ 什么也没发生，锁还持有着
println!("{}", *g);                  // 还能用，证明没 drop
```

**实测警告**（rustc 默认开启的 lint）：

```
warning: calls to `std::mem::drop` with a reference instead of an owned value does nothing
  = note: `#[warn(dropping_references)]` on by default
```

**根因**：`drop<T>(_: T)` 接受**所有权**。传 `&g` 进去，drop 的是那个引用（零大小，无 `Drop`），
`g` 本身纹丝不动。

**处方**：`drop(g)`（不加 `&`）。

---

### 4. 局部变量逆序 drop，结构体字段顺序 drop

```rust
{ let _x = D("x"); let _y = D("y"); }          // drop y, drop x     ← 逆序
struct S { a: D, b: D }
{ let _s = S { a: D("a"), b: D("b") }; }       // drop a, drop b     ← 顺序
```

**为什么方向相反**：局部变量之间可以互相借用（`let a = ...; let b = &a;`），
必须先销毁借用方；结构体字段不能互相借用（那是自引用），所以用最自然的声明顺序。

**实用技巧**：想控制结构体内部的 drop 顺序，**调整字段声明顺序**。
典型场景：一个持有 `MutexGuard` 和被保护数据副本的结构体，
把 guard 放在**前面**保证它先释放。

---

### 5. 借用止于最后一次使用，drop 在作用域末尾

```rust
{
    let a = D("A");
    let r = &a;
    println!("{}", r.0);       // r 的借用到此结束（NLL/Polonius）
    // 此刻 a 上没有活跃借用，但 a 还没 drop
}                              // drop A 在这里
```

**这个不对称造成两类相反的困惑**：

- **借用结束得比想的早** → `let r; { let a = ...; r = &a; }` 报 E0597，
  不是借用的问题，是 `a` 被 drop 了
- **值 drop 得比想的晚** → `MutexGuard` 早就不用了但锁还持有着

**处方**：有 `Drop` 的类型必须显式管理作用域（`{}` 或 `drop(x)`）；没有 `Drop` 的靠 NLL 自动处理。

---

## 类别二：借用规则的边界

### 6. `v.push(v.len())` ✅ 但 `Vec::push(&mut v, v.len())` ❌

```rust
let mut v = vec![1, 2, 3];
v.push(v.len());                     // ✅ 两阶段借用
Vec::push(&mut v, v.len());          // ❌ E0502
(&mut v).push(v.len());              // ❌ E0502
```

**根因**：**两阶段借用只对 autoref（方法调用语法自动插入的 `&mut`）生效**（第 05 章）。

**处方**：用方法调用语法；或者把参数先算出来 `let n = v.len(); v.push(n);`。

---

### 7. `let s = r;` 是移动，`let s: &mut T = r;` 是重借用

```rust
let mut x = 5;

let r = &mut x;
let _s = r;
// *r += 1;              // ❌ E0382: use of moved value

let r = &mut x;
let s: &mut i32 = r;     // 有类型标注 → 重借用
// *r += 1;              // ❌ E0503: cannot use *r because it was mutably borrowed
*s += 1;
*r += 1;                 // ✅ s 用完了
```

**判据**：**`E0382` = 移动；`E0503`/`E0502` = 重借用**。看错误码就知道发生了什么。

**处方**：需要保留 `r` 时显式写 `&mut *r`。

---

### 8. `&T` 是 `Copy`，`&mut T` 不是

```rust
let a = &5;
let b = a;
println!("{}", a);       // ✅ &i32 是 Copy

let mut x = 5;
let a = &mut x;
let b = a;
// println!("{}", a);    // ❌ 移动了
```

**根因**：复制一个独占引用就有两个了，那还叫什么独占。

**推论**：`&mut T` 的"复用"靠**重借用**（栈式嵌套），不是复制。
这个"栈式"直觉就是第 26 章 Stacked Borrows 模型的来源。

---

### 9. 数组的常量下标**也不能**分割借用

很多资料说"固定长度数组用常量下标可以分割借用"。**实测是错的**：

```rust
let mut a = [1, 2, 3];
let x = &mut a[0];
let y = &mut a[1];       // ❌ error[E0499]: cannot borrow `a[_]` as mutable more than once
*x += *y;
```

★ 注意报错里的 **`a[_]`**——下标被打成 `_`，**证明编译器根本没记录常量值**。

**对比 `Vec`**：报错是 `cannot borrow \`v\``（整个 `v`），
因为 `v[i]` 走 `IndexMut` trait，借的是整个容器。**两种失败机制不同，但都失败。**

**能过的写法**（实测）：

```rust
let [x, y, _] = &mut a;                          // ✅ 模式解构
let (l, r) = a.split_at_mut(1);                  // ✅ 签名声明了分割
let [x, y] = v.get_disjoint_mut([0,1]).unwrap(); // ✅ 1.86+
let (x, y) = (&mut t.0, &mut t.1);               // ✅ 元组字段
let (x, y) = (&mut s.a, &mut s.b);               // ✅ 结构体字段
```

> **一句话**：**分割借用只有两条路——模式/字段（语法可见），或签名声明分割的 API。
> 下标永远不行。**

---

### 10. 方法借走整个 `self`，直接访问字段不会

```rust
struct S { a: Vec<i32>, b: Vec<i32> }

// ✅ 直接字段
fn ok(s: &mut S) { let ra = &s.a; s.b.push(ra.len() as i32); println!("{}", ra.len()); }

// ❌ 经方法
impl S { fn get_a(&self) -> &Vec<i32> { &self.a } fn push_b(&mut self, x: i32) { self.b.push(x) } }
fn bad(s: &mut S) { let a = s.get_a(); s.push_b(a.len() as i32); }   // E0502
```

**根因**：borrow checker **只看签名**（第 03 章局部推理）。
`fn get_a(&self)` 说的是"我借走整个 self"，签名里没有"我只碰 `a`"。

**这是 Polonius Alpha 也解决不了的**（lab/12）——它需要 **view types**（第 17 章）。

**处方**（第 18 章详解）：splitter 方法返回元组 / 拆成自由函数 / 把值先拷出来 / 重组结构体。

---

## 类别三：生命周期与型变

### 11. `T: 'static` 不代表"永生"

```rust
fn needs<T: 'static>(_: T) {}

let owned = String::from("x");
needs(owned);              // ✅ 尽管 owned 下一行就 drop 了

let s = String::from("y");
needs(&s);                 // ❌ &'a String 里有个短命的 'a
```

**正确读法**：`T: 'static` = **"T 内部不含任何比 `'static` 短的引用"**，
也就是"T 可以被安全地永久持有（如果你想）"。

**处方**：看到 `spawn` 要求 `'static` 别慌——把数据 `move` 进去就满足了，
或者用 `thread::scope`。

---

### 12. 加一个 `impl Drop` 可能让下游代码编译不过

```rust
struct Holder<'a>(&'a str);
struct NoDrop<'a>(&'a str);
impl<'a> Drop for Holder<'a> { fn drop(&mut self) { println!("{}", self.0); } }

pub fn a() { let _h;  let s = String::from("hi"); _h = NoDrop(&s);  }   // ✅
pub fn b() { let _h;  let s = String::from("hi"); _h = Holder(&s);  }   // ❌ E0597
```

**两段代码一模一样，唯一差别是有没有 `impl Drop`。**

**根因（dropck）**：有 `Drop` 的类型，其生命周期参数必须**严格长于**它自己——
因为 `drop` 可能会读那个引用。

**处方**：给带生命周期参数的公开类型加 `Drop` 之前三思。
标准库用 `#[may_dangle]`（不稳定）来豁免，你不能用。

---

### 13. 加一个 `RefCell` 字段可能让远处的生命周期报错

```rust
struct A<'a> { data: Vec<&'a str> }             // 对 'a 协变
struct B<'a> { data: RefCell<Vec<&'a str>> }    // ★ 对 'a 不变
```

一旦有 `Cell`/`RefCell`/`Mutex`/`UnsafeCell` 字段，**整个结构体对 `'a` 变成不变的**（第 09 章）。
于是 `B<'static>` 不能用在需要 `B<'a>` 的地方，而 `A<'static>` 可以。

**症状**：加了内部可变性之后，**完全不相关的地方**冒出 `lifetime may not live long enough`。

**处方**：让结构体拥有数据（`String` 而非 `&str`）；或整体泛型化。

---

### 14. 闭包不享受生命周期省略规则

```rust
let f = |s: &str| s;         // ❌ error: lifetime may not live long enough
let f = |s| s;               // ✅ 不标注类型就好了
fn f(s: &str) -> &str { s }  // ✅ 函数有省略规则
```

**根因**：省略规则只作用于**函数签名和 impl 块**，闭包的参数/返回值生命周期各自独立推断。

**处方**：去掉类型标注；或用 helper 强制高阶签名：

```rust
fn hrtb<F: for<'a> Fn(&'a str) -> &'a str>(f: F) -> F { f }
let f = hrtb(|s: &str| s);   // ✅
```

---

### 15. 方法返回 `&str` 默认绑到 `&self` 而非参数

```rust
impl Parser {
    fn parse(&self, input: &str) -> &str { input }   // ❌
}
```

**实测报错**（无错误码）：

```
error: lifetime may not live long enough
  | method was supposed to return data with lifetime `'2` but it is returning data with lifetime `'1`
```

**根因**：省略规则 **3**（有 `&self` 时，输出绑到 `self`）**优先于**规则 2。

**处方**：手工展开省略的生命周期再看。想绑到参数就显式标注：

```rust
fn parse<'b>(&self, input: &'b str) -> &'b str { input }
```

---

## 类别四：移动语义的意外

### 16. `struct update` 语法是**部分**移动

```rust
struct S { a: String, b: String }
let s = S { a: "1".into(), b: "2".into() };
let t = S { a: "x".into(), ..s };     // 只移走了 s.b！
println!("{}", s.a);                  // ✅ s.a 还在
// println!("{:?}", s);               // ❌ s 已部分移动
```

**根因**：`..s` 只取**未显式指定的字段**。`a` 显式给了，所以 `s.a` 没被碰。

**很多人以为 `..s` 会消耗整个 `s`。它不会。**

---

### 17. `arr[0]` 不能移动出来，但 `arr` 整体可以

```rust
let arr = [String::from("a"), String::from("b")];
let x = arr[0];                   // ❌ E0508: cannot move out of type `[String; 2]`
let [x, y] = arr;                 // ✅ 模式解构可以
let x = arr[0].clone();           // ✅
let mut arr2 = arr;
let x = std::mem::take(&mut arr2[0]);   // ✅
```

同理 `Vec`：

```rust
let v = vec![String::from("a")];
let x = v[0];                     // ❌ E0507: cannot move out of index of `Vec<String>`
let x = v.into_iter().next().unwrap();  // ✅
let x = v.remove(0);              // ✅（需要 &mut）
```

**根因**：移动一个元素会让容器处于"有个洞"的状态，而容器的 `Drop` 会遍历所有元素。
**模式解构可以**，因为那时整个容器被消耗掉了。

---

### 18. `a + "b"` 消耗 `a`

```rust
let a = String::from("a");
let b = a + "b";
println!("{}", a);                // ❌ E0382: borrow of moved value
```

**根因**：`impl Add<&str> for String { fn add(self, ...) }`——**接收者是 `self` 不是 `&self`**。
这是刻意设计：可以复用 `a` 的堆缓冲区，避免额外分配。

**处方**：`format!("{}{}", a, "b")`；或 `let mut a = ...; a.push_str("b");`。

---

### 19. `Box<T>` 能 deref-move，`Rc<T>` 不能

```rust
let b: Box<String> = Box::new("x".into());
let s: String = *b;                        // ✅ Box 是语言内置的，有特权

let r: Rc<String> = Rc::new("x".into());
// let s: String = *r;                     // ❌ E0507
let s = Rc::try_unwrap(r).unwrap();        // ✅ 仅当计数 == 1
```

**根因**：`Box` 的解引用移动由编译器特殊支持（`DerefMove` 这个 trait **不存在**，
但编译器对 `Box` 开了后门）。任何用户自定义的智能指针都做不到。

---

## 类别五：内部可变性

### 20. `RefCell` 不是"绕过"检查，是移到运行时

```rust
let c = RefCell::new(5);
let a = c.borrow_mut();
let b = c.borrow_mut();           // ✅ 编译通过
                                  // 💥 运行时 panic: already mutably borrowed
```

**为什么编译器不拦**：`borrow_mut` 的签名是 `fn borrow_mut(&self) -> RefMut<T>`——
**参数是 `&self`**。从借用检查的角度这只是两个共享借用，完全合法。

**判断法则**：**看到 `fn xxx(&self) -> 某种可写的东西`，就是内部可变性，
借用检查被有意转移到运行时了。**

**处方**：缩小 `borrow()` 的作用域；或者重新设计（`RefCell` 常常是"没想清楚数据结构"的信号）。

---

## 类别六：edition 差异（★ 容易踩，因为老代码/老资料）

### 21. 2021 edition 的 `if let` 会在 `else` 分支里持锁 → 💥 死锁

```rust
use std::sync::RwLock;
fn f(l: &RwLock<Option<i32>>) -> i32 {
    if let Some(v) = *l.read().unwrap() { v } else { *l.write().unwrap() = Some(0); 0 }
}
```

**实测**（同一份代码，同一个编译器）：

| edition | 结果 |
|---|---|
| **2021** | 💥 **死锁**（读锁的临时 guard 活到整个 `if let` 结束，`else` 里再取写锁 → 自锁） |
| **2024** | ✅ 输出 `result = 0` |

**根因**：2024 edition 把 `if let` scrutinee 的临时值作用域缩短到
"then 块结束 / 进入 else 块之前"。

**处方**：升级到 edition 2024。留在 2021 的话必须手工拆开：

```rust
let opt = *l.read().unwrap();     // 显式结束读锁
if let Some(v) = opt { v } else { ... }
```

---

### 22. 2021 edition 的尾表达式临时值 drop 顺序会报 E0597

```rust
use std::cell::RefCell;
pub fn f() -> i32 { let c = RefCell::new(5); *c.borrow() }
```

| edition | 结果 |
|---|---|
| **2021** | ❌ `error[E0597]: c does not live long enough` |
| **2024** | ✅ |

**根因**：2024 起，尾表达式的临时值在**局部变量之前** drop。

---

### 23. 2018 edition 的闭包捕获整个结构体

```rust
struct S { a: String, b: String }
fn f(s: &mut S) {
    let mut c = || s.a.push('x');
    c();
    s.b.push('y');
}
```

| edition | 结果 |
|---|---|
| **2018** | ❌ 闭包捕获整个 `s` |
| **2021 / 2024** | ✅ RFC 2229：按字段精确捕获 |

---

## 类别七：临时值与版本

### 24. 临时值延长规则**不穿透方法调用**

**实测表**（rustc 1.96.0, edition 2024）：

| 代码 | 结果 |
|---|---|
| `let r = &String::from("x");` | ✅ 延长 |
| `let r = &&String::from("x");` | ✅ 逐层延长 |
| `let r = &(String::from("x"), 1).0;` | ✅ 元组字段访问穿透 |
| `let r = S(&String::from("x"));` | ✅ 元组结构体构造器穿透 |
| `let r = if c { &String::from("a") } else { &String::from("b") };` | ✅ if/else 分支穿透 |
| `let r = String::from("x").as_str();` | ❌ **E0716** |
| `let v: Vec<&str> = vec![&format!("{}", 1)];` | ❌ **E0716** |
| `let r = &RefCell::new(5).borrow();` | ❌ **E0716** |
| `let c = RefCell::new(5); let r = &c.borrow();` | ✅ |

**记忆法**：**延长穿透"纯语法构造"（`&`、`.0`、`S(...)`、if/else），
不穿透"函数/方法调用"。**

**处方**：给临时值一个名字。

---

### 25. Polonius 接受的代码在 stable 上仍然编译不过

```rust
pub fn f(a: &mut u8) -> &mut u8 {
    let b = &mut *a;
    if *b > 0 { b } else { a }
}
```

| 工具链 | 结果 |
|---|---|
| `rustc +nightly`（Polonius Alpha 默认） | ✅ |
| `rustc +nightly -Zpolonius=off` | ❌ E0499 |
| **stable 1.96 / 1.97** | ❌ E0499 |

**目前有 5 类这样的形态**（lab 的 5 个 ★ 案例）。
**在 Polonius 稳定化（目标 2026 年底）之前，别在生产代码里依赖它们。**

**处方**：用第 18 章的手法改写，等稳定了再简化。

---

## 动手实验

### 实验：一次性验证全部 25 条

```bash
cd lab && ./run.sh                  # 案例 1-28 的三态表
EDITION=2021 ./run.sh               # 对比 edition 差异（19/20 号会变）
```

然后把本章每条的最小复现敲进 `/tmp/counter.rs`，编译，**逐条核对错误码**。
把和你预期不符的圈出来——**那些就是你真正的知识盲区**。

### 实验：死锁复现（第 21 条）

```bash
cd /tmp && cat > iflet.rs <<'RSEOF'
use std::sync::RwLock;
fn f(l: &RwLock<Option<i32>>) -> i32 {
    if let Some(v) = *l.read().unwrap() { v } else { *l.write().unwrap() = Some(0); 0 }
}
fn main() { let l = RwLock::new(None); println!("result = {}", f(&l)); }
RSEOF
for ed in 2021 2024; do
  rustc --edition $ed iflet.rs -o iflet_$ed 2>/dev/null
  echo -n "edition $ed: "
  timeout 3 ./iflet_$ed || echo "【超时 → 死锁】"
done
```

**这是本章最值得亲手跑一遍的实验**——同一份代码，改一个 edition 号，
一个死锁一个正常。它能让你永远记住"临时值作用域"这件事。

---

## 本章检查清单

- [ ] 25 条都读过一遍，知道去哪里查
- [ ] 亲手跑过第 21 条的死锁实验
- [ ] 记住 `let _ =` 的两个坑（立刻 drop、不捕获）
- [ ] 记住 `E0382`（移动）vs `E0503`（重借用）的判据
- [ ] 记住"分割借用只有模式/字段 + 声明分割的 API 两条路"
- [ ] 记住"延长穿透纯语法构造，不穿透函数调用"
- [ ] 知道自己的项目在哪个 edition 上，以及那意味着什么

---

下一章：[12 - 场景化 corner case](12-corner-cases.md)——按真实开发场景组织的深水区。
