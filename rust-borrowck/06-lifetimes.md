# 06 - 生命周期不是"活多久"

> 本章目标：完成**本课程最重要的一次认知翻转**。
> 如果你现在认为 `'a` 表示"这个引用活多久"，那么第 07 章之后的所有内容你都只能死记硬背。
> 读完这章，你应该能说出：`'a` 是一个**变量**，它的值是一个**集合**，
> 而生命周期标注是**约束方程**，不是事实陈述。
> 预计用时：3 小时。这是全课程最该慢读的一章。

---

## 1. 先摧毁错误模型

### 1.1 大多数教程给你的模型

> "`'a` 表示引用的生命周期。`fn longest<'a>(a: &'a str, b: &'a str) -> &'a str`
> 意思是返回值的生命周期和参数一样长。"

这个说法有三处严重误导：

1. **"生命周期"听起来像一段时间** → 于是你以为它有起点和终点，是连续的
2. **"和参数一样长"** → 于是你以为标注**决定**了引用能活多久
3. **"引用的生命周期"** → 于是你把 `'a` 和"被引用的数据活多久"混为一谈

### 1.2 三个反例，逐个击破

**反例 1：`'a` 不是连续的时间段**

```rust
fn f(cond: bool, x: &mut i32, y: &mut i32) {
    let r = if cond { x } else { y };
    *r += 1;
}
```

`x` 的借用在 `cond == true` 的路径上活着，在 `cond == false` 的路径上从没被用过。
`'a` 在 CFG 上是**一组点**，可以是不连通的。

**反例 2：标注不"决定"任何东西**

```rust
fn make<'a>() -> &'a str {
    let s = String::from("hi");
    &s                          // ❌ E0515
}
```

如果标注能决定生命周期，那 `'a` 想多长有多长，这段就该编译过。
**它编译不过，因为标注只是一个要求，编译器要去证明这个要求能被满足。**

**反例 3：`'a` 和"数据活多久"是两回事**

```rust
fn main() {
    let s = String::from("hello");     // s 活到 main 结束
    {
        let r: &str = &s;              // 这个借用的 'a 只覆盖下一行
        println!("{}", r);
    }                                  // 'a 结束，但 s 还活着
    println!("{}", s);
}
```

**数据的存活期（scope）** 和 **借用的有效期（region）** 是两个独立的东西。
借用的 region **必须包含在**数据的 scope 里，但通常小得多。

### 1.3 正确模型

> ## `'a` 是一个**推断变量**。生命周期标注是**写在签名里的约束**，编译器求解这些约束。
> ## 它的"值"是什么，取决于用哪一代模型：
> ## · **Polonius（当前）**：一组**贷款（loan）**——"这个引用可能来自哪几次借用"
> ## · **NLL（上一代）**：控制流图上的一组**程序点**——"这个引用在哪些点上有效"
>
> 两种模型都是"**集合**"，都不是"一段时间"。第 07 章会把两者讲透，
> 并说明为什么从"点集"换成"贷款集"能提高精度。

用 Go 类比：`'a` 之于借用检查，就像**类型变量**之于类型推断。

```go
// Go 的类型推断
x := someFunc()        // 编译器推断 x 的类型

// Rust 的 region 推断
let r = &v[0];         // 编译器推断这个借用的 region（一组点）
```

你写 `fn longest<'a>(a: &'a str, b: &'a str) -> &'a str` 时，
**不是在说"它们一样长"**，而是在写一个方程：

```
'a ⊆ region(a)   且   'a ⊆ region(b)   且   region(返回值) ⊆ 'a
```

编译器会求解出满足所有约束的最小 `'a`。**第 07 章会带你手工解一次。**

---

## 2. 术语正名

| 你在文档里看到的 | rustc 内部叫什么 | 精确含义 |
|---|---|---|
| lifetime（生命周期）`'a` | **region**；Polonius 里叫 **origin** | ★ **一组贷款**："这个引用可能来自哪几次借用" |
| lifetime 参数 | `RegionVid`（region 变量） | 待求解的推断变量 |
| 生命周期标注 | region constraint / outlives constraint | 约束方程 |
| 借用 | **loan**（贷款） | 一次 `&`/`&mut` 操作产生的记录，编号 `bw0`/`bw1`… |
| （NLL 时代的 region） | region = 点集 | CFG 上的一组程序点（上一代模型，第 07 章附录） |

> **强烈建议**：在心里把 `'a` 念成 **"origin a"（起源 a）** 或 **"region a"（区域 a）**，
> 不要念成"生命周期 a"。这一个词的改变能消除 80% 的困惑。
>
> 本章后面主要用"region"（因为省略规则、`'static`、outlives 这些概念在两代模型里是一样的），
> 第 07 章开始换成 Polonius 的"origin"。

**为什么当年选了 "lifetime" 这个名字？** 因为面向用户时"这个引用能活多久"更直观。
代价就是本章要花 3 小时来纠正它。

---

## 3. 生命周期从哪里来

### 3.1 三个来源

```rust
// 1. 显式标注
fn f<'a>(x: &'a str) -> &'a str { x }

// 2. 省略规则自动补上（elision）
fn g(x: &str) -> &str { x }         // 等价于上面

// 3. 完全推断（函数体内部的所有借用）
fn h() { let v = vec![1]; let r = &v[0]; }   // r 的 region 完全由编译器推断，你无法标注
```

**极其重要的区分**：

| | 函数**签名**里的生命周期 | 函数**体**内的生命周期 |
|---|---|---|
| 谁决定 | **你**（或省略规则） | **编译器完全推断** |
| 作用 | 契约：约束调用方和实现方 | 内部分析，不可见 |
| 能标注吗 | ✅ | ❌ 你写不了（`let r: &'a i32` 里的 `'a` 只能是签名里已有的） |

**这个区分解释了一个常见困惑**：
> "为什么我在函数体里加生命周期标注没用？"
>
> 因为函数体里的 region 是编译器算出来的，不是你声明的。
> 你能控制的只有**签名**——而签名正是局部推理的边界（第 03 章）。

### 3.2 省略规则（elision）：精确的三条

省略规则**只作用于函数签名和 impl 块**，是纯语法糖，规则如下：

> **规则 1**：每一个被省略的**输入**生命周期，各自分配一个**独立**的新 region 变量。
>
> ```rust
> fn f(a: &str, b: &str)              →  fn f<'a, 'b>(a: &'a str, b: &'b str)
> fn f(a: &str, b: &&str)             →  fn f<'a, 'b, 'c>(a: &'a str, b: &'b &'c str)
> ```
>
> **规则 2**：如果**恰好有一个**输入生命周期（不管是显式还是省略的），
> 它被赋给**所有**省略的输出生命周期。
>
> ```rust
> fn f(a: &str) -> &str               →  fn f<'a>(a: &'a str) -> &'a str
> fn f(a: &str) -> (&str, &str)       →  fn f<'a>(a: &'a str) -> (&'a str, &'a str)
> ```
>
> **规则 3**：如果输入里有 `&self` 或 `&mut self`（即这是个方法），
> **`self` 的生命周期**被赋给所有省略的输出生命周期。**规则 3 优先于规则 2。**
>
> ```rust
> impl S {
>     fn f(&self, x: &str) -> &str    →  fn f<'a, 'b>(&'a self, x: &'b str) -> &'a str
> }                                                                             ^^^ self 的！
> ```
>
> **如果三条规则跑完还有输出生命周期没被赋值 → `error[E0106]: missing lifetime specifier`**

**规则 3 是无数 bug 的来源**，请重点记住这个例子：

```rust
struct Parser { data: String }
impl Parser {
    // 你以为返回值绑定到 input
    fn parse(&self, input: &str) -> &str {
        input                       // ❌ 报错
    }
    // 因为省略规则把它变成了：
    // fn parse<'a, 'b>(&'a self, input: &'b str) -> &'a str
    // 返回值绑定到 self，但你返回了 input！
}
```

**实测的报错**（注意：这个错误**没有错误码**，是裸的 `error:`）：

```
error: lifetime may not live long enough
 --> parser.rs:2:58
  |
2 | impl Parser { pub fn parse(&self, input: &str) -> &str { input } }
  |                            -             -               ^^^^^ method was supposed to return data
  |                            |             |                     with lifetime `'2` but it is
  |                            |             |                     returning data with lifetime `'1`
  |                            |             let's call the lifetime of this reference `'1`
  |                            let's call the lifetime of this reference `'2`
  |
help: consider introducing a named lifetime parameter and update trait if needed
  |
2 | impl Parser { pub fn parse<'a>(&self, input: &'a str) -> &'a str { input } }
```

> **`error: lifetime may not live long enough` 是生命周期错误里最常见的无编号错误。**
> 它的意思固定是：**某个 region 需要包含另一个 region，但签名里没有这条约束**。
> 编译器给的 `help` 通常就是正确答案。

**修法**：显式标注你真正想要的。

```rust
fn parse<'b>(&self, input: &'b str) -> &'b str { input }        // ✅
```

> ### 一个立即可用的诊断技巧
> 遇到方法返回引用的诡异错误，**先把省略的生命周期全部手工展开**，
> 90% 的时候错误当场就明显了。

---

## 4. `'static` 的两种含义（高频混淆）

`'static` 出现在两个完全不同的位置，含义**不同**：

### 4.1 `&'static T`：引用本身能活到程序结束

```rust
let s: &'static str = "hello";           // 字面量在二进制的只读段里
static COUNTER: i32 = 0;
let r: &'static i32 = &COUNTER;
let leaked: &'static mut Vec<i32> = Box::leak(Box::new(vec![]));   // 故意泄漏换 'static
```

**含义**：这个引用指向的数据永不销毁。

### 4.2 `T: 'static`：类型里**不含**比 `'static` 短的引用

这是一个 **bound（约束）**，含义完全不同：

```rust
fn f<T: 'static>(t: T) { }

f(String::from("x"));         // ✅ String 里没有借用 → 满足 T: 'static
f(5i32);                      // ✅
f(vec![1, 2, 3]);             // ✅
let s = String::from("x");
f(&s);                        // ❌ &'a String 里有个 'a，不满足
f("literal");                 // ✅ &'static str 满足
```

> ### 关键澄清
> **`T: 'static` 不是"T 必须永生"，是"T 不含短命的借用"。**
>
> 一个 `String` 满足 `T: 'static`，即使它下一行就被 drop 了。
> 因为 `String` 是**拥有**数据的，它内部没有任何引用别人的指针。
>
> 换句话说：`T: 'static` ⟺ **T 可以被安全地永久持有**（如果你愿意）。

**这个区分在哪里咬人**：

```rust
std::thread::spawn(f)  where  F: Send + 'static
```

`spawn` 要求 `'static` **不是因为线程要永远运行**，而是因为
**编译器无法知道线程什么时候结束**，所以它不能持有任何可能提前失效的借用。

```rust
let v = vec![1, 2, 3];
std::thread::spawn(|| println!("{:?}", v));   // ❌ E0373：借用了 v
std::thread::spawn(move || println!("{:?}", v));  // ✅ 移动进去，闭包拥有 v → 'static
```

**scoped thread 就是给这个限制开的正门**（lab/23）：

```rust
std::thread::scope(|s| {
    s.spawn(|| println!("{:?}", v));   // ✅ 借用即可！
});                                     // scope 保证在这里之前所有线程都 join 了
```

`scope` 的签名用了 HRTB（第 10 章），它在类型层面证明了"线程不会活过这个 scope"。

### 4.3 为什么"加 `'static` 让它编译过"通常是错的

```rust
fn bad(s: &str) -> &'static str {
    s                    // ❌ 报错
}
```

实测报错**没有编号**（不是 E0521——那是"借用数据逃出闭包"，见附录 A）：

```
error: lifetime may not live long enough
 --> x.rs:2:5
  |
1 | fn bad(s: &str) -> &'static str {
  |           - let's call the lifetime of this reference `'1`
2 |     s
  |     ^ returning this value requires that `'1` must outlive `'static`
```

`'static` 是一个**更强的要求**。把签名改成 `'static` 不是"关掉检查"，
而是**把问题推给调用方**——现在调用方必须传一个 `&'static str` 进来。

**正确的做法几乎总是三选一**：
1. 返回拥有的值：`fn ok(s: &str) -> String { s.to_owned() }`
2. 正确标注：`fn ok<'a>(s: &'a str) -> &'a str { s }`
3. 用 `Cow`：`fn ok(s: &str) -> Cow<'_, str>`（第 21 章）

---

## 5. 生命周期约束（bounds）

### 5.1 `'a: 'b` —— "outlives"

```rust
fn f<'a, 'b>(x: &'a str, y: &'b str) -> &'b str
where 'a: 'b            // 读作 "'a outlives 'b"，即 'a ⊇ 'b
{
    x                    // ✅ 因为 'a 至少和 'b 一样长
}
```

**用集合的语言**：`'a: 'b` 意思是 **`'b ⊆ 'a`**（`'a` 这个点集包含 `'b`）。

> ⚠️ **注意方向**：`'a: 'b` 读作"'a 长于 'b"，但集合上是 `'b ⊆ 'a`。
> 符号方向和包含方向**相反**，这是个高频混淆点。
>
> 记忆法：`:` 读作 "outlives"，**冒号左边的更长**。

### 5.2 `T: 'a` —— 类型层面的 outlives

```rust
struct Holder<'a, T: 'a> { r: &'a T }         // T 里的所有引用都必须活过 'a
```

现代 Rust 里这个 bound 大多能自动推断（RFC 2093 "infer outlives"），所以你很少手写。

### 5.3 结构体里的生命周期

```rust
struct Parser<'a> {
    input: &'a str,
    pos: usize,
}
```

**含义**：`Parser<'a>` 这个类型的实例，**不能活过 `'a`**。

一旦结构体带上生命周期参数，它就**"传染"**给所有用到它的地方：

```rust
impl<'a> Parser<'a> {
    fn new(input: &'a str) -> Self { Parser { input, pos: 0 } }
    fn rest(&self) -> &'a str { &self.input[self.pos..] }
    //                  ^^^ 注意：不是 &self 的生命周期，是 'a！这是有意的
}
```

`fn rest(&self) -> &'a str` 和 `fn rest(&self) -> &str`（省略成 `&'self str`）的差别很大：
前者返回的引用**不受 `&self` 借用的限制**，可以在 `self` 被再次借用后继续使用。
这是设计带生命周期的 API 时的重要技巧（第 21 章）。

> ### 一个设计警告（第 21 章展开）
> **给公开结构体加生命周期参数是一个重大的 API 决定。**
> 它会传染到所有使用者的类型标注、trait 实现、异步任务、线程边界。
> 很多情况下更好的选择是让结构体**拥有**数据（`String` 而非 `&str`），
> 或者用 `Arc<str>`。只在"零拷贝解析器"这类性能确实关键的场景才用借用结构。

---

## 6. 四个高频错误码，逐个拆解

### 6.1 `E0106: missing lifetime specifier`

```rust
fn f(a: &str, b: &str) -> &str { a }    // ❌
```

**原因**：省略规则跑完，输出的生命周期没被赋值（两个输入，规则 2 不适用；不是方法，规则 3 不适用）。

**诊断问题**：**返回的引用是从哪个参数来的？** 明确回答之后标上去：

```rust
fn f<'a>(a: &'a str, b: &str) -> &'a str { a }    // ✅
```

如果答案是"两个都可能"，就都标 `'a`：

```rust
fn f<'a>(a: &'a str, b: &'a str) -> &'a str { if a.len() > b.len() { a } else { b } }
```

⚠️ 注意这时 `'a` 会被推断成两者 region 的**交集**，调用方会受更强的限制。

### 6.2 `E0597: X does not live long enough`

```rust
let r;
{
    let x = 5;
    r = &x;            // ❌ E0597
}
println!("{}", r);
```

**含义**：借用的 region 超出了被借数据的 scope。

**诊断问题**：**数据的所有者是谁？它什么时候 drop？**
解法通常是**把数据挪到更外层的作用域**，或者**改成拥有**。

### 6.3 `E0515: cannot return reference to local variable`

```rust
fn f() -> &String { let s = String::from("x"); &s }    // ❌
```

E0597 的特例：函数返回时局部变量必然销毁。

**解法**：返回拥有的值 `String`，或者接收一个 `&mut` 缓冲区写进去。

### 6.4 `E0716: temporary value dropped while borrowed`

这个错误涉及 Rust 里最不直观的角落之一：**临时值生命周期延长（temporary lifetime extension）**。

**基本规则**：`let r = &<临时值>;` 时，临时值被**延长**到 `r` 的作用域末尾。
但这条规则**只在特定的语法形状下**生效。下面是完整实测（`rustc 1.96.0`, edition 2024）：

| 代码 | 结果 | 为什么 |
|---|---|---|
| `let r = &String::from("x");` | ✅ | 直接借用临时值 → 延长 |
| `let r = &&String::from("x");` | ✅ | 嵌套借用 → 逐层延长 |
| `let r = &(String::from("x"), 1).0;` | ✅ | 元组字段访问 → 延长穿透 |
| `let r = S(&String::from("x"));` | ✅ | **元组结构体构造器** → 延长穿透 |
| `let r = if c { &String::from("a") } else { &String::from("b") };` | ✅ | if/else 两支都延长 |
| `let r = &String::from("x").len();` | ✅ | 借的是 `.len()` 产出的 `usize` 临时值，它被延长了 |
| `let r = String::from("x").as_str();` | ❌ **E0716** | **方法调用**返回借自临时值的引用 → **不延长** |
| `let v: Vec<&str> = vec![&format!("{}", 1)];` | ❌ **E0716** | 宏/函数调用参数位置 → 不延长 |
| `let r = &RefCell::new(5).borrow();` | ❌ **E0716** | `RefCell` 临时值不延长（`.borrow()` 是方法调用） |
| `let c = RefCell::new(5); let r = &c.borrow();` | ✅ | `c` 有名字了，只有 `Ref` guard 是临时值 → 延长 |

> ### 记忆法
> **延长会穿透"纯语法构造"（借用、字段访问、元组/结构体构造器、if/else 分支），
> 但不穿透"函数/方法调用"。**
>
> 因为函数调用的返回值来自哪里，编译器只从签名看得到；
> 而 `&expr`、`.0`、`S(...)` 这些是语法上可见的结构。

**通用解法**：给临时值一个名字。

```rust
// ❌
let r = String::from("x").as_str();
// ✅
let s = String::from("x");
let r = s.as_str();
```

第 12 章会讲这条规则和 2024 edition 变更的交互（那才是真正咬人的地方）。

---

## 7. 一个完整的推理演练

```rust
struct Cache<'a> {
    source: &'a str,
    tokens: Vec<&'a str>,
}

impl<'a> Cache<'a> {
    fn new(source: &'a str) -> Self {
        Cache { source, tokens: Vec::new() }
    }
    fn tokenize(&mut self) {
        self.tokens = self.source.split(' ').collect();
    }
    fn first(&self) -> Option<&'a str> {
        self.tokens.first().copied()
    }
    fn source_len(&self) -> usize {
        self.source.len()
    }
}

fn main() {
    let text = String::from("hello world");
    let mut c = Cache::new(&text);
    c.tokenize();
    let t = c.first();
    c.tokenize();                    // 再次可变借用 c
    println!("{:?}", t);             // t 还能用吗？
}
```

**逐步推理**：

1. `Cache::new(&text)` → `'a` = `text` 的借用 region，至少覆盖 `c` 的整个使用期
2. `c.tokenize()` → `&mut c` 借用，在语句结束时结束（NLL）
3. `c.first()` → 签名是 `fn first(&self) -> Option<&'a str>`。
   **注意返回的是 `'a` 不是 `&self` 的 region**。
   所以 `&c` 的借用在这一行结束，但 `t` 的 region 绑定到 `'a`（即 `text` 的借用）
4. `c.tokenize()` → 又一次 `&mut c`。因为 `t` **不依赖 `&c`**，所以 ✅
5. `println!("{:?}", t)` → `t` 的 region 是 `'a`，`text` 还活着 ✅

**编译通过。** 现在把 `first` 的签名改成省略版：

```rust
fn first(&self) -> Option<&str> { ... }
// 省略规则 3 → fn first<'s>(&'s self) -> Option<&'s str>
```

**再编译 → ❌ E0502**：因为 `t` 现在绑定到 `&c` 的借用，
`c.tokenize()` 需要 `&mut c`，冲突。

> ### 这个例子的价值
> **同一份函数体，只改签名里的一个生命周期，结果从"通过"变成"E0502"。**
> 它证明了第 03 章的论断：**借用检查只看签名**。
> 你在设计 API 时对生命周期的每个选择，都在决定使用者能写出什么样的代码。

---

## 8. 动手实验

### 实验 1：展开省略规则

不看编译器，手工写出下面每个签名展开后的完整形式：

```rust
fn a(x: &str) -> &str;
fn b(x: &str, y: &str) -> &str;
fn c(x: &i32, y: &mut i32);
fn d(&self) -> &str;
fn e(&self, x: &str) -> &str;
fn f(&mut self, x: &str) -> (&str, &str);
fn g(x: &&str) -> &str;
fn h() -> &str;
```

<details><summary>答案</summary>

```rust
fn a<'a>(x: &'a str) -> &'a str;                                    // 规则 2
fn b(x: &str, y: &str) -> &str;                                     // ❌ E0106
fn c<'a, 'b>(x: &'a i32, y: &'b mut i32);                           // 规则 1，无输出
fn d<'a>(&'a self) -> &'a str;                                      // 规则 3
fn e<'a, 'b>(&'a self, x: &'b str) -> &'a str;                      // 规则 3（★ 绑到 self）
fn f<'a, 'b>(&'a mut self, x: &'b str) -> (&'a str, &'a str);       // 规则 3
fn g<'a, 'b>(x: &'a &'b str) -> &'a str;                            // 规则 2（外层那个）
fn h() -> &str;                                                      // ❌ E0106
```

</details>

### 实验 2：`'static` 的两种含义

预测下面每一行的结果：

```rust
fn needs_static_bound<T: 'static>(_: T) {}
fn needs_static_ref(_: &'static str) {}

fn main() {
    let owned = String::from("x");
    let literal: &'static str = "y";
    let borrowed: &str = &owned;

    needs_static_bound(owned);        // ?
    needs_static_bound(5);            // ?
    needs_static_bound(literal);      // ?
    needs_static_bound(borrowed);     // ?
    needs_static_ref(literal);        // ?
    needs_static_ref(borrowed);       // ?
}
```

<details><summary>答案</summary>

```
needs_static_bound(owned)     ✅  String 不含借用
needs_static_bound(5)         ✅  i32 不含借用
needs_static_bound(literal)   ✅  &'static str 的 region 就是 'static
needs_static_bound(borrowed)  ❌  &'a String，'a ≠ 'static
needs_static_ref(literal)     ✅
needs_static_ref(borrowed)    ❌
```

注意第一行：`owned` 是一个**马上就要 drop 的局部变量**，但它满足 `T: 'static`。
**再次强调：`T: 'static` 说的是"不含短命借用"，不是"永生"。**

</details>

### 实验 3：第 7 节的 Cache 演练

把第 7 节的代码敲进去跑通，然后：
1. 把 `fn first(&self) -> Option<&'a str>` 改成 `-> Option<&str>`，看错误
2. 把 `fn source_len(&self) -> usize` 改成 `fn source(&self) -> &'a str`，
   然后在 `main` 里同时持有 `c.source()` 和调用 `c.tokenize()`，看是否通过
3. 解释为什么

---

## 9. 本章检查清单

**这是全课程最重要的检查清单。没有全部打勾请重读本章。**

- [ ] 能说出 `'a` 的正确模型：**推断变量，值是一个集合**（Polonius：贷款集；NLL：点集）
- [ ] 知道生命周期标注是**约束**不是**事实**，它不延长也不缩短任何东西
- [ ] 知道"数据的 scope"和"借用的 region"是两个东西
- [ ] 能背出省略的三条规则，尤其是**规则 3 优先于规则 2**
- [ ] 能手工展开任意函数签名的省略生命周期
- [ ] 能说出 `&'static T` 和 `T: 'static` 的区别
- [ ] 知道 `String` 满足 `T: 'static`
- [ ] 知道 `'a: 'b` 意味着 `'b ⊆ 'a`（符号方向和集合包含方向相反）
- [ ] 知道函数**体**内的 region 你无法标注，只有**签名**可控
- [ ] 能解释第 7 节里"只改签名就从通过变成报错"的原因

---

## 10. 常见坑

| 误解 / 现象 | 错误码 | 事实 / 处方 |
|---|---|---|
| "加个 `'a` 能让引用活久一点" | — | 标注不改变任何运行时行为。它只是一个待验证的要求 |
| "加 `'static` 能解决报错" | 报错转移到调用点 | `'static` 是更强的要求。改成返回拥有的值，或正确标注 |
| 方法返回引用报生命周期不匹配 | 无编号：`error: lifetime may not live long enough` | 省略规则 3 把返回值绑到了 `self`。手工展开就明白了；编译器的 `help` 通常是对的 |
| 两个 `&str` 参数返回 `&str` | E0106 | 明确回答"返回值来自哪个参数"，标上去 |
| `let r = foo().bar();`（bar 返回引用） | E0716 | 临时值延长**不穿透方法调用**。给临时值一个绑定 |
| 结构体加了 `'a` 之后到处传染 | — | 这是设计决定的后果。考虑改成拥有数据或 `Arc` |
| 在函数体里想标注生命周期 | — | 做不到，也不需要。体内的 region 全由编译器推断 |
| `T: 'static` 以为是"永生" | — | 是"不含短命借用"。`String` 就满足 |
| `'a: 'b` 记反方向 | — | 冒号**左边的更长**；集合上是 `'b ⊆ 'a` |
| 以为 `'a` 是一段连续时间 | — | 是一个**集合**：Polonius 下是贷款集，NLL 下是点集（且可以不连通） |

---

**你已经跨过分水岭了。** 下一章开始，我们打开编译器，看它到底怎么算这些集合。

下一章：[07 - 借用检查的计算模型：贷款、origin 与可达性](07-borrowck-model.md)
