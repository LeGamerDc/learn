# 附录 A - 错误码急诊手册

> 用法：拿到报错 → 查错误码 → 看"病因"确认 → 按"处方"改。
> 所有错误信息文本都在 `rustc 1.96.0`（edition 2024）上**实测**采集。
> 每条都给了跳转章节。

---

## 0. 一分钟分诊

```
拿到一个借用相关的报错
   │
   ├─ E0382 / E0505 / E0507 / E0508 / E0509 ──► 【所有权/移动】 第 04 章
   ├─ E0499 / E0502 / E0503 / E0506         ──► 【借用冲突】   第 05 / 12 / 18 章
   ├─ E0106 / E0597 / E0515 / E0716 / 无编号 ──► 【生命周期】   第 06 章
   ├─ E0373 / E0277(Send/Sync)              ──► 【并发】       第 22 / 23 章
   ├─ "future cannot be sent"（无编号）      ──► 【async】      第 24 / 25 章
   ├─ E0596 / E0594                          ──► 【可变性】     第 05 章
   └─ E0733 / "cannot be unpinned"           ──► 【Pin/async】  第 13 / 24 章
```

---

## 1. 借用冲突四兄弟（★ 最高频）

**它们的区别是"已有的贷款种类" × "新访问的种类"的组合**：

| 已有贷款 ↓ / 新操作 → | 共享借用 `&` | 独占借用 `&mut` | 读 | 写/赋值 | 移动 |
|---|---|---|---|---|---|
| **共享借用 `&`** | ✅ | **E0502** | ✅ | **E0506** | **E0505** |
| **独占借用 `&mut`** | **E0502** | **E0499** | **E0503** | **E0506** | **E0505** |

### E0499 — `cannot borrow X as mutable more than once at a time`

**病因**：两个 `&mut` 同时活着。

```rust
let a = &mut v[0];
let b = &mut v[1];      // ❌ E0499（v[i] 借的是整个 v）
*a += *b;
```

**实测文本**：`error[E0499]: cannot borrow \`*v\` as mutable more than once at a time`

**处方**：
1. 挪动最后一次使用（第 18 章手法 1）
2. **解构 / 字段访问**（手法 4）★
3. `split_at_mut` / `get_disjoint_mut` / `iter_mut`（手法 8）★
4. splitter 方法返回元组（手法 5）
5. 如果匹配第 14 章 §3 的"骨架"→ **精度问题**，nightly 上能过

**章节**：05, 12, 14, 18

### E0502 — `cannot borrow X as mutable because it is also borrowed as immutable`

**病因**：`&` 和 `&mut` 同时活着（或反过来）。

```rust
let a = &v[0];
v.push(1);              // ❌ E0502
println!("{}", a);      // ← 这一行让 a 的借用活到这里
```

**★ 解题钥匙在报错的第三段** `` immutable borrow later used here ``——
把那次使用挪到前面，region 就缩小了。

**处方**：同 E0499。

**章节**：05, 07, 12, 18

### E0503 — `cannot use X because it was mutably borrowed`

**病因**：一个 place 被 `&mut` 借着，你还想**直接用**它（不是再借）。

```rust
let mut x = 5;
let r = &mut x;
let _y = x;             // ❌ E0503
*r += 1;
```

**★ 重要判据**（第 05 章）：
- `E0382`（moved）→ 发生了**移动**
- `E0503` / `E0502` → 发生了**重借用**，原变量被冻结

**章节**：05

### E0506 — `cannot assign to X because it is borrowed`

**病因**：给一个正被借用的 place 赋值。

```rust
let mut x = 1;
let r = &x;
x = 2;                  // ❌ E0506
println!("{}", r);
```

**章节**：05, 15（这就是 `loan_killed_at` 对应的场景）

---

## 2. 所有权与移动

### E0382 — `borrow of moved value` / `use of moved value`

**病因**：非 `Copy` 值被移走后又使用。

```rust
let s = String::new();
let _t = s;
println!("{}", s);      // ❌ E0382
```

**常见触发点**：
- 按值传参 / 返回 / 放进容器
- `move` 闭包捕获
- `for x in v`（消耗 v）
- `a + "b"`（`String` 的 `Add` 接收 `self`）
- **无类型标注的 `let s = r;`（`&mut` 被移动而非重借用）**

**处方**：传 `&` / `.clone()` / 调整顺序 / `&mut *r` 显式重借用

**章节**：04, 05, 11

### E0505 — `cannot move out of X because it is borrowed`

```rust
let s = String::new();
let r = &s;
let _t = s;             // ❌ E0505
println!("{}", r);
```

**也是自引用结构失败的错误码**（第 13 章）。

**章节**：04, 13

### E0507 — `cannot move out of X which is behind a shared reference`

```rust
fn f(s: &S) -> String { s.a }      // ❌ E0507
```

**六种处方**（第 04 章 §5）：

| 手法 | 代码 |
|---|---|
| 改成借用 | `-> &str { &s.a }` ★ 首选 |
| clone | `s.a.clone()` |
| 改成拿所有权 | `fn f(s: S)` |
| `mem::take` | `fn f(s: &mut S) -> String { std::mem::take(&mut s.a) }` |
| `mem::replace` | `std::mem::replace(&mut s.a, "".into())` |
| `Option::take` | 字段改成 `Option<T>`，`s.a.take()` |

**章节**：04, 18

### E0508 — `cannot move out of type [T; N], a non-copy array`

```rust
let a = [String::new()];
let _x = a[0];          // ❌ E0508
let [x] = a;            // ✅ 模式解构
```

**章节**：04, 11

### E0509 — `cannot move out of type X, which implements the Drop trait`

```rust
struct D { a: String }
impl Drop for D { fn drop(&mut self) {} }
let d = D { a: String::new() };
let _a = d.a;           // ❌ E0509
```

**病因**：有 `Drop` 的类型不能部分移动（drop 需要完整的值）。

**处方**：字段改成 `Option<T>` 用 `take()`；或用 `ManuallyDrop`。

**章节**：04

### E0384 — `cannot assign twice to immutable variable`

```rust
let x = 1;
x = 2;                  // ❌ E0384
```

**处方**：`let mut x = 1;`

### E0381 — `used binding X isn't initialized`

```rust
let x: i32;
println!("{}", x);      // ❌ E0381
```

**章节**：08（这是 `EverInitializedPlaces` 数据流分析报的）

---

## 3. 生命周期

### E0106 — `missing lifetime specifier`

```rust
fn f(a: &str, b: &str) -> &str { a }        // ❌ E0106
```

**病因**：省略规则三条跑完还有输出生命周期没赋值。

**诊断问题**：**返回的引用是从哪个参数来的？** 答上来就标上去。

```rust
fn f<'a>(a: &'a str, b: &str) -> &'a str { a }
```

**章节**：06

### E0597 — `X does not live long enough`

```rust
let r;
{ let x = 5; r = &x; }      // ❌ E0597
println!("{}", r);
```

**病因**：借用的 region 超出了被借数据的作用域。

**诊断问题**：**数据的所有者是谁？它什么时候 drop？**

**特殊情形**：有 `impl Drop` 的类型会触发 **dropck**，
即使借用本身没问题也可能报这个（第 04 章 §3.5）。

**章节**：04, 06

### E0515 — `cannot return reference to local variable`

```rust
fn f(x: &i32) -> &String { let _ = x; let s = String::new(); &s }   // ❌ E0515
```

⚠️ **别把无参版本当例子**：`fn f() -> &String { ... }` 报的是 **E0106**（缺生命周期标注），
不是 E0515。因为**省略规则先跑**——签名连不上生命周期就直接失败，borrowck 根本没机会运行。
这条顺序（解析 → 省略/类型 → borrowck）决定了你先看到哪个错。

E0597 的特例。**处方**：返回拥有的值；或接收 `&mut` 缓冲区。

**章节**：06

### E0716 — `temporary value dropped while borrowed`

```rust
let r = String::from("x").as_str();
println!("{r}");                              // ❌ E0716

let v: Vec<&str> = vec![&format!("{}", 1)];
println!("{v:?}");                            // ❌ E0716
```

⚠️ **后面那行 `println!` 不能省**。借用不被使用就没有活跃区间，也就没有冲突——
去掉打印这两行都能编译。**"报不报错"取决于借用活到哪里，不取决于它被创建。**

**病因**：临时值生命周期延长规则**不穿透函数/方法调用**。

**完整规则表**见第 12 章 §4.1。**记忆法**：
**延长穿透"纯语法构造"（`&`、`.0`、`S(...)`、if/else），不穿透"函数调用"。**

**处方**：给临时值一个名字。

**章节**：06, 11, 12

### E0521 — `borrowed data escapes outside of closure`

```rust
let mut v: Vec<&i32> = Vec::new();
let mut push = |x: &i32| v.push(x);      // ❌ E0521
let n = 1;
push(&n);
```

**病因**：闭包参数的生命周期是 HRTB（对任意 `'a`），把它存进外部容器就要求 `'a` 活得
和容器一样久——而 `'a` 可以任意短。

⚠️ **别拿它当"返回 `&'static` 失败"的错误码用**：那个报的是**无编号**的
`error: lifetime may not live long enough`（见本附录末尾）。E0521 **只在闭包场景出现**。

**处方**：给闭包参数显式标注一个具名生命周期；或改用 `fn` 接收。

**章节**：10

### E0621 — `explicit lifetime required in the type of X`

```rust
fn f<'a>(x: &'a str, y: &str) -> &'a str { y }      // ❌ E0621
```

**处方**：按编译器的 `help` 加标注。

### E0700 — `hidden type for impl Trait captures lifetime that does not appear in bounds`

```rust
// edition 2021
fn f<'a, 'b>(x: &'a str, _y: &'b str) -> impl Display { x }     // ❌ E0700
```

**注意**：**2024 edition 下这段是合法的**（RPIT 默认捕获所有生命周期）。
想排除某个生命周期用 `+ use<'a>`。

**章节**：10, 21

### 无编号：`error: lifetime may not live long enough`

**这是最常见的无编号生命周期错误**，含义固定：
**某个 region 需要包含另一个 region，但签名里没有这条约束。**

```rust
impl Parser {
    fn parse(&self, input: &str) -> &str { input }      // ❌
}
// 省略规则 3 把返回值绑到了 self，但你返回了 input
```

**★ 编译器给的 `help` 通常就是正确答案。**

**常见来源**：
- 省略规则 3（方法返回值默认绑 `self`）→ 第 06 章 §3.2
- 型变问题（`&mut T` 对 T 不变）→ 第 09 章
- 闭包没有省略规则 → 第 10 章 §5.1
- early-bound vs late-bound → 第 10 章 §6

**章节**：06, 09, 10, 11

---

## 4. 可变性

### E0596 — `cannot borrow X as mutable, as it is behind a & reference`

```rust
fn f(x: &Vec<i32>) { x.push(1); }       // ❌ E0596
```

**处方**：参数改成 `&mut Vec<i32>`；或者上游给你 `&mut`。

### E0594 — `cannot assign to X, which is behind a & reference`

```rust
fn f(x: &i32) { *x += 1; }              // ❌ E0594
```

⚠️ 注意 E0596（借用为可变）和 E0594（赋值）是**两个不同的码**。

### E0040 / E0599 — 手动调 `drop`

```rust
let s = String::new();
s.drop();               // ❌
```

**处方**：`drop(s)`（那个自由函数）。

---

## 5. 并发

### E0373 — `closure may outlive the current function, but it borrows X`

```rust
let v = vec![1];
std::thread::spawn(|| println!("{:?}", v));      // ❌ E0373
```

**处方**：
1. 加 `move`
2. **用 `std::thread::scope`**（★ 能直接借用）
3. `Arc` 共享

**章节**：06, 22, 23

### E0277（Send/Sync 系列）

| 报错文本 | 含义 | 处方 |
|---|---|---|
| `X cannot be sent between threads safely` | `X: !Send` | 见第 22 章替换表 |
| `X cannot be shared between threads safely` | `X: !Sync` | 同上 |

**常见的 `!Send`**：`Rc<T>`、`*mut T`、`MutexGuard`
**常见的 `!Sync`**：`Cell<T>`、`RefCell<T>`、`Rc<T>`

**排查技巧**：

```rust
fn is_send<T: Send>() {}
fn is_sync<T: Sync>() {}
is_send::<MyType>();        // 二分定位到具体哪个字段
```

**章节**：22, 23

---

## 6. async

### 无编号：`error: future cannot be sent between threads safely`

```
note: future is not `Send` as this value is used across an await
  |  has type `MutexGuard<'_, i32>` which is not `Send`
```

**★ 报错里有三段关键信息**：哪个类型、哪个变量、哪个 await。

**★ 判据（第 24/25 章）**：**是"作用域跨越 await"，不是"最后一次使用在 await 之前"。**

```rust
async fn a() { let r = Rc::new(1); println!("{}", r); y().await; }   // ❌ !Send
async fn b() { { let r = Rc::new(1); println!("{}", r); } y().await; } // ✅
```

**处方**：
1. **用块 `{}` 限定作用域** ★
2. 显式 `drop(x)`
3. 抽成子函数
4. 换 `Send` 的等价物（`Rc`→`Arc`，`std::Mutex`→`tokio::Mutex`）
5. 用单线程 executor（`spawn_local`）

**章节**：24, 25

### E0733 — `recursion in an async fn requires boxing`

```rust
async fn rec(n: u32) { if n > 0 { rec(n-1).await; } }        // ❌ E0733
async fn rec(n: u32) { if n > 0 { Box::pin(rec(n-1)).await; } }  // ✅
```

**章节**：25

### E0277 — `X cannot be unpinned`

```rust
let mut fut = async { 42 };
let p = Pin::new(&mut fut);         // ❌ async 块是 !Unpin
let mut fut = Box::pin(fut);        // ✅
let mut fut = std::pin::pin!(async { 42 });     // ✅ 栈上
```

**章节**：13, 24

### 警告：`use of async fn in public traits is discouraged`

**原因**：无法指定 `Send` bound。

**处方**：`fn call(&self) -> impl Future<Output = T> + Send;`

**章节**：21, 25

---

## 7. 其它

### E0310 — `the parameter type T may not live long enough`

**处方**：加 `T: 'static` 或 `T: 'a` bound。

### E0038 / `not dyn compatible`

**病因**：trait 有泛型方法 / `async fn` / 返回 `impl Trait` → 不能做 trait object。

**处方**：`Pin<Box<dyn Future>>`、`#[async_trait]`、或用枚举分发。

**章节**：21, 25

### `implementation of X is not general enough`

**病因**：提供的闭包/类型只对某些生命周期成立，但被要求对所有成立（HRTB）。

**排查**：
1. 闭包参数是不是显式标注了类型？→ 去掉
2. 闭包是不是捕获了带生命周期的东西？
3. 用 helper 函数强制签名（第 10 章 §5.1）

**章节**：10

### 运行时：`RefCell already borrowed` / `already mutably borrowed`

**不是编译错误**，是 `RefCell` 的运行时 panic。

**常见来源**：
- 借用范围太大（用了具名绑定而非临时值）
- 递归/重入
- **2021 edition 的 `if let ... borrow()`**（第 19 章 §6.1）★

**章节**：19

---

## 8. NLL vs Polonius：同一段代码两个结果

如果你在 **nightly 上能编译，stable 上不能**，检查是不是这 5 类之一（第 14/16 章）：

| 形态 | 骨架 |
|---|---|
| 条件返回借用 | `let b = x.get_mut(); if c { b } else { x.other_mut() }` |
| `HashMap` get-or-insert（返回借用） | `match m.get_mut(&k) { Some(v)=>v, None=>{ m.insert(..); m.get_mut(&k).unwrap() } }` |
| 同上的 `loop` 版 | — |
| 条件重借用 | `let b = &mut *a; if c { b } else { a }` |
| lending iterator + 条件返回 | `loop { match it.next() { Some(w) if p(w) => return Some(w), .. } }` |

**验证**：

```bash
rustc +nightly --edition 2024 x.rs                   # Polonius
rustc +nightly --edition 2024 -Zpolonius=off x.rs    # NLL
```

---

## 9. edition 相关的行为差异速查

| 现象 | 2018 | 2021 | 2024 |
|---|---|---|---|
| 闭包捕获粒度 | 整个结构体 | **按字段** | 按字段 |
| `if let` scrutinee 临时值 | 活到整个 `if let` | 活到整个 `if let` | **then 块结束/进 else 前** |
| 尾表达式临时值 drop 顺序 | 局部变量先 drop | 局部变量先 drop | **临时值先 drop** |
| RPIT 生命周期捕获 | 不捕获（要写 `+ 'a`） | 不捕获 | **默认全捕获**（`use<>` 排除） |
| `unsafe_op_in_unsafe_fn` | allow | allow | **deny** |
| `#[no_mangle]` | 直接写 | 直接写 | **`#[unsafe(no_mangle)]`** |

**升级命令**：`cargo fix --edition`

**章节**：11, 12, 19, 21
