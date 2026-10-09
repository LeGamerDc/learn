# 附录 C - 分级练习 40 题

> 用法：**先自己判断/写答案，再展开对照**。
> 每题标了难度（★–★★★★★）和考察章节。
> 所有题目的答案都在 `rustc 1.96.0`（stable/NLL）和 `1.100.0-nightly`（Polonius）上实测过。
>
> **判断题的答案格式**：`✅ 通过` / `❌ 错误码` / `★ NLL ❌ / Polonius ✅` / `💥 运行时`

---

## 第一组：所有权与移动（第 04 章）

### 1. ★ 判断

```rust
let s = String::from("hi");
let t = s;
println!("{}", s);
```

<details><summary>答案</summary>❌ **E0382**：`s` 被移动到 `t`。`String` 不是 `Copy`。</details>

### 2. ★ 判断

```rust
let s = 5;
let t = s;
println!("{}", s);
```

<details><summary>答案</summary>✅ `i32` 是 `Copy`。</details>

### 3. ★★ 输出是什么

```rust
struct D(&'static str);
impl Drop for D { fn drop(&mut self) { println!("drop {}", self.0); } }
struct S { a: D, b: D }
fn main() {
    let _x = D("x");
    let _y = D("y");
    let _s = S { a: D("a"), b: D("b") };
}
```

<details><summary>答案</summary>

```
drop a        ← 结构体字段：声明顺序
drop b
drop y        ← 局部变量：逆序
drop x
```

注意 `_s` 最后声明所以最先 drop，其内部字段按声明顺序。

</details>

### 4. ★★ 输出顺序

```rust
struct D(&'static str);
impl Drop for D { fn drop(&mut self) { println!("drop {}", self.0); } }
fn main() {
    let _  = D("A"); println!("after A");
    let _n = D("B"); println!("after B");
}
```

<details><summary>答案</summary>

```
drop A         ← `let _ =` 立刻 drop！
after A
after B
drop B
```

`_` 是丢弃模式不是绑定。**这就是 `let _ = m.lock()` 那个 bug 的根源。**

</details>

### 5. ★★ 判断 + 修

```rust
struct P { name: String, age: u32 }
fn take_name(p: &P) -> String { p.name }
```

<details><summary>答案</summary>

❌ **E0507**。六种修法（第 04 章 §5）：
`&p.name` / `p.name.clone()` / 改签名拿所有权 / `mem::take` / `mem::replace` / 字段改 `Option` 用 `take()`。

</details>

### 6. ★★ 判断

```rust
struct P { a: String, b: String }
let p = P { a: "1".into(), b: "2".into() };
let q = P { a: "x".into(), ..p };
println!("{}", p.a);
```

<details><summary>答案</summary>✅ `..p` 只移走 `p.b`（`a` 显式给了）。`p.a` 仍可用，但 `p` 整体不可用。</details>

### 7. ★★★ 判断 + 解释

```rust
struct Holder<'a>(&'a str);
impl<'a> Drop for Holder<'a> { fn drop(&mut self) {} }
fn f() { let _h; let s = String::from("hi"); _h = Holder(&s); }
```

<details><summary>答案</summary>

❌ **E0597**。**dropck**：有 `Drop` 的类型，生命周期参数必须严格长于它自己。
`_h` 先声明 → 后 drop，此时 `s` 已没了。

**去掉 `impl Drop` 就能过。** 这是加 `Drop` 会破坏下游代码的经典例子。

</details>

### 8. ★★★ 写代码

在只有 `&mut self` 的情况下，把 `self.data: Vec<i32>` 里所有偶数过滤掉（不用 `retain`）。

<details><summary>答案</summary>

```rust
fn filter(&mut self) {
    let old = std::mem::take(&mut self.data);
    self.data = old.into_iter().filter(|x| x % 2 != 0).collect();
}
```

直接写 `self.data.into_iter()` 会报 E0507。

</details>

---

## 第二组：借用（第 05 章）

### 9. ★ 判断

```rust
let mut v = vec![1, 2, 3];
v.push(v.len());
```

<details><summary>答案</summary>✅ **两阶段借用**。</details>

### 10. ★★ 判断

```rust
let mut v = vec![1, 2, 3];
Vec::push(&mut v, v.len());
```

<details><summary>答案</summary>❌ **E0502**。两阶段借用**只对 autoref 生效**，显式 `&mut` 不享受。</details>

### 11. ★★★ 三个变体分别是什么错误码

```rust
let mut x = 5;
// A
let r = &mut x; let _s = r; *r += 1;
// B
let r = &mut x; let s: &mut i32 = r; *r += 1; *s += 1;
// C
fn g<T: std::fmt::Debug>(_: T) {}
let r = &mut x; g(r); *r += 1;
```

<details><summary>答案</summary>

| | 结果 | 原因 |
|---|---|---|
| A | ❌ **E0382** | 无类型标注 → **移动** |
| B | ❌ **E0503** | 有类型标注 → **重借用**，`*r` 被 `s` 借着 |
| C | ❌ **E0382** | 泛型参数不是强制点 → 移动 |

★ **`E0382` = 移动，`E0503`/`E0502` = 重借用。这是最快的判据。**

C 的修法：`g(&mut *r)`。

</details>

### 12. ★★ 六选一：哪些能过

```rust
struct S { a: i32, b: i32 }
fn p1() { let mut a=[1,2,3]; let [x,y,_] = &mut a; *x += *y; }
fn p2() { let mut a=[1,2,3]; let (l,r) = a.split_at_mut(1); l[0] += r[0]; }
fn p3() { let mut t=(1,2);   let (x,y) = (&mut t.0, &mut t.1); *x += *y; }
fn p4() { let mut a=[1,2,3]; let x=&mut a[0]; let y=&mut a[1]; *x += *y; }
fn p5() { let mut v=vec![1,2,3]; let [x,y]=v.get_disjoint_mut([0,1]).unwrap(); *x += *y; }
fn p6() { let mut s=S{a:1,b:2}; let x=&mut s.a; let y=&mut s.b; *x += *y; }
```

<details><summary>答案</summary>

**只有 `p4` 失败**（❌ E0499，报错是 `cannot borrow \`a[_]\``）。

★ **注意报错里的 `a[_]`**——下标被抹掉了，证明**即使是固定长度数组 + 常量下标也不行**。
很多老资料在这一点上是错的。

**规律：分割借用只有两条路——模式/字段（语法可见），或签名声明分割的 API。下标永远不行。**

</details>

### 13. ★★★ 判断 + 修

```rust
struct App { widgets: Vec<String>, log: Vec<String> }
impl App {
    fn widgets(&self) -> &Vec<String> { &self.widgets }
    fn log_mut(&mut self) -> &mut Vec<String> { &mut self.log }
}
fn f(a: &mut App) { for w in a.widgets() { a.log_mut().push(w.clone()); } }
```

<details><summary>答案</summary>

❌ **E0502**。两个方法都借走整个 `*a`。**Polonius Alpha 也不救**（签名表达力问题）。

四种修法：

```rust
// 1. 解构 ★
fn f1(a: &mut App) { let App{widgets,log}=a; for w in widgets.iter(){ log.push(w.clone()); } }
// 2. 直接字段
fn f2(a: &mut App) { for w in &a.widgets { a.log.push(w.clone()); } }   // ← 这个也行！
// 3. splitter
impl App { fn split(&mut self)->(&Vec<String>,&mut Vec<String>){ (&self.widgets,&mut self.log) } }
// 4. 自由函数
fn log_all(w:&[String], l:&mut Vec<String>){ for x in w { l.push(x.clone()); } }
```

⚠️ 注意 `f2` 能过——**说明问题出在"经过方法"，不是"同时访问两个字段"**。

</details>

---

## 第三组：生命周期（第 06 章）

### 14. ★★ 展开省略的生命周期

```rust
fn a(x: &str) -> &str;
fn b(x: &str, y: &str) -> &str;
fn c(&self, x: &str) -> &str;
fn d(&mut self, x: &str) -> (&str, &str);
```

<details><summary>答案</summary>

```rust
fn a<'a>(x: &'a str) -> &'a str;                              // 规则 2
fn b(x: &str, y: &str) -> &str;                               // ❌ E0106
fn c<'a,'b>(&'a self, x: &'b str) -> &'a str;                 // 规则 3 ★ 绑到 self
fn d<'a,'b>(&'a mut self, x: &'b str) -> (&'a str, &'a str);  // 规则 3
```

</details>

### 15. ★★ 判断

```rust
fn needs<T: 'static>(_: T) {}
let owned = String::from("x");
needs(owned);
```

<details><summary>答案</summary>

✅ **`T: 'static` 不是"永生"，是"不含短命引用"。** `String` 拥有自己的数据，满足。

</details>

### 16. ★★★ 判断 + 解释

```rust
struct Parser { data: String }
impl Parser { fn parse(&self, input: &str) -> &str { input } }
```

<details><summary>答案</summary>

❌ **无编号错误**：`error: lifetime may not live long enough`

省略规则 3 把返回值绑到了 `&self`，但你返回了 `input`。

修：`fn parse<'b>(&self, input: &'b str) -> &'b str { input }`

</details>

### 17. ★★★ 十选三：哪三个是 E0716

```rust
let a = &String::from("x");
let b = &&String::from("x");
let c = &(String::from("x"), 1).0;
let d = if t { &String::from("a") } else { &String::from("b") };
let e = &String::from("x").len();
let f = String::from("x").as_str();
let g: Vec<&str> = vec![&format!("{}", 1)];
let h = &std::cell::RefCell::new(5).borrow();
let i = std::cell::RefCell::new(5); let j = &i.borrow();
```

<details><summary>答案</summary>

❌ E0716 的是：**f**（方法调用返回借自临时值的引用）、
**g**（宏/函数参数位置）、**h**（`RefCell` 临时值不延长）。

其余全部 ✅。

**记忆法：延长穿透"纯语法构造"（`&`、`.0`、`S(...)`、if/else），不穿透"函数/方法调用"。**

</details>

### 18. ★★★★ 解释

下面两个版本的 `first`，为什么一个能过一个不能？

```rust
struct Cache<'a> { source: &'a str, tokens: Vec<&'a str> }
impl<'a> Cache<'a> {
    fn first_a(&self) -> Option<&'a str> { self.tokens.first().copied() }
    fn first_b(&self) -> Option<&str>    { self.tokens.first().copied() }
}
// 调用：
let t = c.first_X();
c.tokenize();          // 需要 &mut c
println!("{:?}", t);
```

<details><summary>答案</summary>

- `first_a` ✅：返回值绑到 `'a`（外部数据的借用），**不依赖 `&self`**，
  所以 `&c` 的借用在那一行就结束了
- `first_b` ❌ **E0502**：省略规则 3 → 返回值绑到 `&self`，`&c` 的借用要活到 `println!`

★ **同一份函数体，只改签名里的一个生命周期，结果从通过变成报错。
这证明了"借用检查只看签名"。**

</details>

---

## 第四组：型变与 HRTB（第 09/10 章）

### 19. ★★★ 十选三：哪三个失败

```rust
fn a<'x>(v: &'static str) -> &'x str { v }
fn b<'x>(v: &'x &'static str) -> &'x &'x str { v }
fn c<'x>(v: &'static mut i32) -> &'x mut i32 { v }
fn d<'x,'y>(v: &'y mut Vec<&'static str>) -> &'y mut Vec<&'x str> { v }
fn e<'x>(v: Vec<&'static str>) -> Vec<&'x str> { v }
fn f<'x>(v: Box<&'static str>) -> Box<&'x str> { v }
fn g<'x>(v: Cell<&'static str>) -> Cell<&'x str> { v }
fn h<'x>(v: UnsafeCell<&'static str>) -> UnsafeCell<&'x str> { v }
fn i<'x>(f: fn(&'x str)) -> fn(&'static str) { f }
fn j<'x>(f: fn() -> &'static str) -> fn() -> &'x str { f }
```

<details><summary>答案</summary>

失败的是 **d**（`&mut T` 对 `T` **不变**）、**g**、**h**（内部可变性 → 不变）。

**用一条规则推出全表**：**只读 → 协变；只写 → 逆变；可读可写 → 不变。**

</details>

### 20. ★★★ 判断

```rust
let f = |s: &str| s;
```

<details><summary>答案</summary>

❌ `error: lifetime may not live long enough`。**闭包不享受生命周期省略规则。**

三种修法：去掉类型标注 `|s| s`；用函数；用 helper：

```rust
fn hrtb<F: for<'a> Fn(&'a str) -> &'a str>(f: F) -> F { f }
let f = hrtb(|s: &str| s);
```

</details>

### 21. ★★★★ 判断 + 解释

```rust
fn late<'a>(x: &'a str) -> &'a str { x }
fn early<'a: 'a>(x: &'a str) -> &'a str { x }
let f: for<'x> fn(&'x str) -> &'x str = late;
let g: for<'x> fn(&'x str) -> &'x str = early;
```

<details><summary>答案</summary>

`f` ✅，`g` ❌ **E0308**。

`<'a: 'a>` 这个**看起来毫无意义**的约束把 `late-bound` 变成了 `early-bound`，
于是函数值不再是高阶类型。

</details>

---

## 第五组：反直觉与 corner case（第 11/12 章）

### 22. ★★ 判断

```rust
use std::rc::Rc;
let r = Rc::new(1);
std::thread::spawn(move || { let _ = r; });
```

<details><summary>答案</summary>

✅ **编译通过！** `let _ = r` 里的 `_` 不是绑定 → 闭包**根本没捕获 `r`**。

改成 `println!("{}", r)` 立刻变成 ❌ E0277。

</details>

### 23. ★★★ 同一份代码在两个 edition 下会怎样

```rust
use std::sync::RwLock;
fn f(l: &RwLock<Option<i32>>) -> i32 {
    if let Some(v) = *l.read().unwrap() { v } else { *l.write().unwrap() = Some(0); 0 }
}
```

<details><summary>答案</summary>

| edition | 结果 |
|---|---|
| **2021** | 💥 **死锁**（读锁的 guard 活到整个 `if let` 结束） |
| **2024** | ✅ 正常 |

2024 edition 把 `if let` scrutinee 的临时值作用域缩短到"进 else 之前"。

</details>

### 24. ★★★ 同上

```rust
use std::cell::RefCell;
pub fn f() -> i32 { let c = RefCell::new(5); *c.borrow() }
```

<details><summary>答案</summary>

2021 ❌ **E0597** / 2024 ✅。2024 起尾表达式的临时值在局部变量**之前** drop。

</details>

### 25. ★★★ 判断 + 说明差别

```rust
use std::collections::HashMap;
fn b1(m: &mut HashMap<u32,Vec<u32>>) {
    match m.get_mut(&1) { Some(v)=>v.push(1), None=>{ m.insert(1,vec![]); } }
}
fn b2(m: &mut HashMap<u32,Vec<u32>>) -> &mut Vec<u32> {
    match m.get_mut(&1) { Some(v)=>v, None=>{ m.insert(1,vec![]); m.get_mut(&1).unwrap() } }
}
```

<details><summary>答案</summary>

| | NLL（stable） | Polonius Alpha |
|---|---|---|
| `b1` | ✅ | ✅ |
| `b2` | ❌ E0499 ×2 | ✅ |

**分水岭是 `-> &mut Vec<u32>`（借用是否跨出函数）。**
`b2` 就是 NLL problem case #3。

stable 上的解法：`m.entry(1).or_default()`。

</details>

### 26. ★★★ 判断（Polonius）

```rust
fn f(a: &mut u8) -> &mut u8 { let b = &mut *a; if *b > 0 { b } else { a } }
```

<details><summary>答案</summary>

★ **NLL ❌ E0499 / Polonius Alpha ✅**

这是第 14 章"骨架"最纯粹的形式，也是 Polonius Alpha 的招牌案例。

</details>

### 27. ★★★★ 判断

```rust
pub struct B<'a> { data: String, view: Option<&'a str> }
fn ok()  { let mut b = B{data:"hi".into(),view:None}; b.view=Some(&b.data); println!("{:?}",b.view); }
fn mv()  { let mut b = B{data:"hi".into(),view:None}; b.view=Some(&b.data); let _c = b; }
fn psh() { let mut b = B{data:"hi".into(),view:None}; b.view=Some(&b.data); b.data.push('x'); }
fn psh2(){ let mut b = B{data:"hi".into(),view:None}; b.view=Some(&b.data); b.data.push('x'); println!("{:?}",b.view); }
```

<details><summary>答案</summary>

- `ok` ✅ —— **安全 Rust 里可以创建自引用结构！**
- `mv` ❌ **E0505** —— 但不能移动它
- `psh` ✅ —— `view` 之后没被读，借用已死（NLL）
- `psh2` ❌ **E0502** —— 读了 `view`，借用还活着

**结论：自引用结构能建，但它是"钉死"的——不能移动、不能返回。这就是 `Pin` 存在的理由。**

</details>

---

## 第六组：内部可变性与数据结构（第 19/20 章）

### 28. ★★ 判断（编译 + 运行）

```rust
let c = std::cell::RefCell::new(5);
let a = c.borrow_mut();
let b = c.borrow_mut();
```

<details><summary>答案</summary>

✅ 编译通过，💥 运行时 panic `already mutably borrowed`。

`borrow_mut` 的签名是 `fn borrow_mut(&self)`——从借用检查看只是两个共享借用。

</details>

### 29. ★★★ 三选一：哪个不是 `Sync`

```rust
struct A { data: Vec<i32> }
struct B { data: std::cell::RefCell<Vec<i32>> }
struct C { data: std::sync::Mutex<Vec<i32>> }
```

<details><summary>答案</summary>

`B` 不是 `Sync`（`RefCell` 的借用计数非原子）。

**推论**：加一个 `RefCell` 字段会让整个结构体失去 `Sync`，
从而不能跨线程共享、不能放进多线程 executor 的 Future 里。

</details>

### 30. ★★★★ 这段代码在两个 edition 下的行为

```rust
use std::cell::RefCell; use std::collections::HashMap;
struct S { cache: RefCell<HashMap<u64,u64>> }
impl S {
    fn get(&self, n: u64) -> u64 {
        if let Some(&v) = self.cache.borrow().get(&n) { v } else {
            let v = n * 2;
            self.cache.borrow_mut().insert(n, v);
            v
        }
    }
}
```

<details><summary>答案</summary>

2021 💥 **panic `RefCell already borrowed`** / 2024 ✅

而且这个 panic **只在缓存未命中的路径上发生**——测试里很容易漏掉。

2021 下的修法：

```rust
let cached = self.cache.borrow().get(&n).copied();
if let Some(v) = cached { return v; }
```

</details>

### 31. ★★★ 写代码

用 arena + 索引实现一个带父指针的树，支持 `path_of(id) -> String`。

<details><summary>参考答案</summary>

```rust
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct NodeId(u32);
pub struct Node { pub name: String, pub parent: Option<NodeId>, pub children: Vec<NodeId> }
#[derive(Default)]
pub struct Arena { nodes: Vec<Node> }

impl Arena {
    pub fn alloc(&mut self, name: String) -> NodeId {
        let id = NodeId(self.nodes.len() as u32);
        self.nodes.push(Node { name, parent: None, children: vec![] });
        id
    }
    pub fn add_child(&mut self, parent: NodeId, child: NodeId) {
        self.nodes[parent.0 as usize].children.push(child);      // ★ 两次独立短借用
        self.nodes[child.0 as usize].parent = Some(parent);
    }
    pub fn path_of(&self, mut id: NodeId) -> String {
        let mut parts = vec![];
        loop {
            parts.push(self.nodes[id.0 as usize].name.clone());
            match self.nodes[id.0 as usize].parent { Some(p) => id = p, None => break }
        }
        parts.reverse();
        parts.join("/")
    }
}
```

**对比一下用 `Rc<RefCell<Node>>` 写 `path_of` 有多难**（要小心不在循环里持有 `Ref`）。

</details>

### 32. ★★★★ 会发生什么

```rust
struct Node { next: Option<Box<Node>> }
fn main() {
    let mut head = None;
    for _ in 0..200_000 { head = Some(Box::new(Node { next: head })); }
    println!("built");
}
```

<details><summary>答案</summary>

```
built
thread 'main' has overflowed its stack
fatal runtime error: stack overflow, aborting
```

★ **`built` 打印出来了**——构造没问题，**炸在 `main` 结束时的递归 `Drop` 上**。

修法：手写迭代版 `Drop`：

```rust
impl Drop for Node {
    fn drop(&mut self) {
        let mut cur = self.next.take();
        while let Some(mut n) = cur { cur = n.next.take(); }
    }
}
```

</details>

---

## 第七组：并发与异步（第 22–25 章）

### 33. ★★ 判断

```rust
let v = vec![1, 2, 3];
std::thread::spawn(|| println!("{:?}", v));
```

<details><summary>答案</summary>

❌ **E0373**。三种修法：加 `move`；用 `thread::scope`；用 `Arc`。

</details>

### 34. ★★★ 判断

```rust
let mut v = vec![1, 2, 3];
std::thread::scope(|s| {
    s.spawn(|| v.push(0));
    s.spawn(|| v.push(1));
});
```

<details><summary>答案</summary>

❌ **E0499**。两个线程都要 `&mut v`。

★ **注意：这就是普通的借用检查**——编译器根本不需要理解"线程"这个概念。
**并发安全是借用规则的免费副产品。**

改成两个 `println!` 就能过（两个 `&v`）。

</details>

### 35. ★★★ 六选二：哪两个不是 `Sync`

```rust
i32, Cell<i32>, RefCell<i32>, Mutex<i32>, Arc<i32>, Arc<Cell<i32>>
```

<details><summary>答案</summary>

`Cell<i32>`、`RefCell<i32>` 不是 `Sync`。

★ **陷阱**：`Arc<Cell<i32>>` **也不是** `Sync`——因为 `Arc<T>: Sync` 需要 `T: Send + Sync`。

**`Arc` 不会"修好"内部类型的线程安全性**，它只解决引用计数的原子性。
想共享可变状态必须 `Arc<Mutex<T>>`。

</details>

### 36. ★★★★ 判断哪个 Future 是 `Send`

```rust
use std::rc::Rc;
async fn y() {}
async fn a() { let r = Rc::new(1); println!("{}", r); y().await; }
async fn b() { let r = Rc::new(1); y().await; println!("{}", r); }
async fn c() { { let r = Rc::new(1); println!("{}", r); } y().await; }
async fn d() { let r = Rc::new(1); println!("{}", r); drop(r); y().await; }
```

<details><summary>答案</summary>

**`a` 和 `b` 都不是 `Send`；`c` 和 `d` 是。**

★★★ **`a` 是本课程最反直觉的一题**：`r` 的最后一次使用在 `await` **之前**，
但它**仍在作用域内**（到函数末尾才 drop）→ 进入状态机 → Future `!Send`。

> **判据是"作用域是否跨越 await"，不是"最后一次使用是否在 await 之前"。**

这是第 04 章"借用止于最后一次使用，但 drop 在作用域末尾"那条不对称性
在 async 里最咬人的后果。

</details>

### 37. ★★★ 判断 + 修

```rust
use std::sync::Mutex;
async fn f(m: &Mutex<i32>) { let g = m.lock().unwrap(); yield_now().await; println!("{}", *g); }
```

<details><summary>答案</summary>

Future **不是 `Send`**（`error: future cannot be sent between threads safely`），
因为 `MutexGuard` 是 `!Send`（POSIX 要求由加锁线程解锁）。

修法（按优先级）：

```rust
// 1. ★ 收缩临界区
async fn ok(m: &Mutex<i32>) { let v = { *m.lock().unwrap() }; yield_now().await; println!("{}", v); }
// 2. 换 tokio::sync::Mutex（只在必须跨 await 持锁时）
// 3. 用 spawn_local（单线程 executor）
```

</details>

### 38. ★★★ 判断

```rust
async fn rec(n: u32) { if n > 0 { rec(n - 1).await; } }
```

<details><summary>答案</summary>

❌ **E0733: recursion in an async fn requires boxing**（状态机会包含自己 → 无限大小）。

修：`Box::pin(rec(n-1)).await`。

</details>

### 39. ★★★★ 这个函数是 cancel-safe 的吗

```rust
async fn transfer(db: &Db) {
    db.begin().await;
    db.debit(a, 100).await;
    db.credit(b, 100).await;
    db.commit().await;
}
```

<details><summary>答案</summary>

❌ **不是**。在每个 `.await` 处画一刀：

- 砍在 `debit` 之后 → **钱扣了，没转** ❌
- 砍在 `credit` 之后 → 事务没提交（可能靠 DB 超时回滚，也可能不）

**因此它不能放进 `tokio::select!` 的分支。**

处方：`tokio::spawn` 出去后 select 它的 `JoinHandle`；或用 DB 的原子事务 API。

</details>

---

## 第八组：综合（★★★★★）

### 40. ★★★★★ 完整诊断

下面这段代码在 stable 上报错。**完成五步诊断**：

```rust
struct Graph { nodes: Vec<Node>, edges: Vec<Edge> }
struct Node { id: usize }
struct Edge { from: usize, to: usize }

impl Graph {
    fn node(&self, i: usize) -> &Node { &self.nodes[i] }
    fn add_edge(&mut self, from: usize, to: usize) { self.edges.push(Edge { from, to }); }
    fn connect_first_two(&mut self) {
        let a = self.node(0);
        let b = self.node(1);
        self.add_edge(a.id, b.id);
    }
}
```

**五步**：
1. 错误码是什么？
2. 手工展开省略的生命周期
3. 属于第 14 章的哪一类（真·冲突 / 表达力不足 / 精度不足）？
4. Polonius Alpha 能过吗？
5. 给出三种修法

<details><summary>答案</summary>

**1.** `error[E0502]: cannot borrow *self as mutable because it is also borrowed as immutable`

**2.**
```rust
fn node<'s>(&'s self, i: usize) -> &'s Node          // 省略规则 3
fn add_edge<'s>(&'s mut self, from: usize, to: usize)
```
`a`/`b` 的类型是 `&'s Node`，`'s` 必须包含 `a.id`/`b.id` 的使用点（最后一行）
→ `&self` 的借用还活着 → 和 `&mut self` 冲突。

**3. 签名表达力不足**：`node(&self)` 借走整个 `self`，签名里没有"我只碰 `nodes`"。
运行时**没有**真实的别名冲突（只是读了两个 `usize`，然后往 `edges` 里 push）。

**4. ❌ Polonius Alpha 也不行**——它解决的是精度问题，不是表达力问题。
需要 **view types**（第 17 章，无时间表）。

**5. 三种修法**：

```rust
// A. 把需要的值先拷出来（usize 是 Copy）★ 最简单
fn connect_first_two(&mut self) {
    let (a, b) = (self.nodes[0].id, self.nodes[1].id);
    self.add_edge(a, b);
}

// B. 直接访问字段，避开方法
fn connect_first_two(&mut self) {
    let (x, y) = (self.nodes[0].id, self.nodes[1].id);
    self.edges.push(Edge { from: x, to: y });
}

// C. 解构 ★
fn connect_first_two(&mut self) {
    let Graph { nodes, edges } = self;
    edges.push(Edge { from: nodes[0].id, to: nodes[1].id });
}
```

**假想的 view types 版本**（第 17 章）：

```rust
// fn node(&{nodes} self, i: usize) -> &Node
// fn add_edge(&mut {edges} self, from: usize, to: usize)
// → 原代码直接就能过
```

</details>

---

## 评分标准

| 答对 | 水平 |
|---|---|
| < 15 | 回去从第 04 章重读 |
| 15–25 | 掌握了机制，需要更多实战。重点补第 11/12/18 章 |
| 26–34 | 能独立处理绝大部分借用问题。补第 09/13/24/25 章的细节 |
| 35–38 | 熟练。可以去读 rustc 源码和写 unsafe 抽象了 |
| 39–40 | 你可以教这门课了 |

**特别检查这五题**——它们是本课程最容易反直觉的地方：

| 题号 | 考点 |
|---|---|
| **4** | `let _ =` 立刻 drop |
| **12** | 数组常量下标**也不能**分割借用 |
| **27** | 自引用结构**能建**，但不能移动 |
| **36** | async 的判据是**作用域**不是最后一次使用 ★★★ |
| **40** | 五步诊断流程 |
