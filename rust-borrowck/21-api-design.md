# 21 - 用生命周期设计 API

> 本章目标：从"怎么让代码编译过"升级到"怎么设计出让**别人**好用的 API"。
> 核心问题：**什么时候该在公开签名里出现 `'a`？** 这是一个有长期成本的决定。
> 预计用时：2.5 小时。

---

## 1. 一个决定的三种答案

设计任何 API 时，对每个数据你要回答：**借用、拥有、还是共享？**

```rust
fn process(data: &str)            { }   // 借用：我只看，不留
fn process(data: String)          { }   // 拥有：给我，我负责销毁
fn process(data: Arc<str>)        { }   // 共享：我们一起持有
fn process(data: Cow<'_, str>)    { }   // 按需：大多不改，偶尔改
```

**决策表**：

| 情况 | 选择 | 理由 |
|---|---|---|
| 函数只在调用期间读数据 | **`&T`** ★ 默认 | 零拷贝，调用方最灵活 |
| 函数要修改调用方的数据 | **`&mut T`** | — |
| 函数要**保存**数据（存进 struct、发给线程、放进容器） | **`T`（拥有）** | 否则要传染生命周期 |
| 多个持有者，生命周期不一致 | **`Arc<T>` / `Rc<T>`** | — |
| 大多数情况只读，少数要改 | **`Cow<'_, T>`** | — |
| 泛型场景，想同时接受借用和拥有 | **`impl Into<T>` / `AsRef<T>`** | — |

> ### ★ 第一条法则
> **参数尽量借用，返回值尽量拥有。**
>
> 参数借用 → 调用方自由（可以传引用、传 `&owned`、传字面量）
> 返回拥有 → **不把生命周期传染给调用方**
>
> 违反它的场景（返回借用）需要充分理由，见第 3 节。

---

## 2. 参数的设计

### 2.1 用最宽松的类型

```rust
// ❌ 太具体：调用方必须有一个 String
fn greet(name: &String) { }

// ✅ 更宽松：&String 会自动 deref 成 &str，字面量也能直接传
fn greet(name: &str) { }
```

**标准的"放宽"阶梯**：

| 别写 | 写 | 好处 |
|---|---|---|
| `&String` | `&str` | 接受字面量、`&String`、`Cow` |
| `&Vec<T>` | `&[T]` | 接受数组、`Vec`、切片 |
| `&Box<T>` | `&T` | — |
| `&PathBuf` | `&Path` | — |
| `&str` | `impl AsRef<str>` | 更宽松，但**增加单态化开销**，且错误信息变差 |

⚠️ **`impl AsRef<str>` 不要滥用**。它让 API 更宽松，但代价是：
- 每个具体类型都单态化一份（代码膨胀）
- 类型推断和错误信息变差
- 文档里看不出到底能传什么

**建议**：公开的、被大量调用的 API 用 `&str`/`&[T]`；
只在**确实需要同时接受 `String` 和 `&str` 且不想让调用方写 `&`** 时才用 `AsRef`。

### 2.2 什么时候要所有权

```rust
// ❌ 借用但内部要 clone —— 把成本藏起来了
fn add_user(&mut self, name: &str) { self.users.push(name.to_string()); }

// ✅ 明说要所有权 —— 调用方可以决定是 move 还是 clone
fn add_user(&mut self, name: String) { self.users.push(name); }
```

**原则**：**如果函数一定要拥有，就在签名里要所有权。**
偷偷 clone 会让调用方无法优化（它明明有个可以 move 的 `String`，
却被迫留着，然后你又 clone 一份）。

**折中方案**：

```rust
fn add_user(&mut self, name: impl Into<String>) { self.users.push(name.into()); }
// 传 &str  → 内部 to_string()
// 传 String → 零拷贝 move
```

### 2.3 `&mut self` 的粒度问题

第 05/12 章的那个痛点，在 API 设计层面的对策：

```rust
// ❌ 用户没法同时用两个
impl App {
    pub fn widgets(&self) -> &[Widget] { &self.widgets }
    pub fn log(&mut self) -> &mut Vec<String> { &mut self.log }
}

// ✅ 方案 1：提供 splitter
impl App {
    pub fn parts(&mut self) -> (&[Widget], &mut Vec<String>) { (&self.widgets, &mut self.log) }
}

// ✅ 方案 2：提供打包好的操作（★ 通常更好）
impl App {
    pub fn log_all_widgets(&mut self) {
        for w in &self.widgets { self.log.push(w.name.clone()); }   // 内部字段访问，没问题
    }
}

// ✅ 方案 3：回调（控制反转）
impl App {
    pub fn with_widget<R>(&mut self, i: usize, f: impl FnOnce(&mut Widget, &mut Vec<String>) -> R) -> Option<R> {
        let w = self.widgets.get_mut(i)?;
        Some(f(w, &mut self.log))
    }
}

// ✅ 方案 4：公开字段（对纯数据结构完全合理）
pub struct App { pub widgets: Vec<Widget>, pub log: Vec<String> }
```

> ### ★ 这是"标准库为什么有 `entry` API"的一般化
> **当借用规则让用户没法组合你的两个方法时，你的责任是提供一个组合好的方法。**
>
> `HashMap::entry`、`Vec::split_at_mut`、`Vec::retain`、`Vec::drain`、
> `Option::get_or_insert_with`——全都是这个模式。

---

## 3. 返回值：什么时候可以返回借用

### 3.1 安全的情形

```rust
impl Config {
    pub fn name(&self) -> &str { &self.name }              // ✅ getter，惯例
    pub fn items(&self) -> &[Item] { &self.items }         // ✅
    pub fn iter(&self) -> impl Iterator<Item = &Item> { self.items.iter() }  // ✅
    pub fn get_mut(&mut self, i: usize) -> Option<&mut Item> { self.items.get_mut(i) }  // ✅
}
```

**共同点**：返回的借用**绑定到 `&self`**，生命周期由省略规则自动处理，
调用方不需要写任何标注。

### 3.2 危险的情形：结构体带生命周期参数

```rust
pub struct Parser<'a> {
    input: &'a str,
    pos: usize,
}
```

**这个 `'a` 会传染到所有使用者**：

```rust
struct MyApp<'a> { parser: Parser<'a> }              // 传染
fn build<'a>(s: &'a str) -> Parser<'a> { ... }       // 传染
trait Handler { fn handle<'a>(&self, p: Parser<'a>); }  // 传染
async fn run(p: Parser<'_>) { }                      // ★ 和 async 交互特别痛（第 24 章）
thread::spawn(move || use_parser(p));                // ❌ 不满足 'static
```

**传染的四个具体后果**：

| 后果 | 说明 |
|---|---|
| **不能跨线程 / 跨 task** | 不满足 `T: 'static`（第 06 章） |
| **不能存进全局 / 长生命周期容器** | 同上 |
| **不能放进 trait object** | `Box<dyn Trait>` 默认是 `+ 'static` |
| **每个持有它的类型都要加 `'a`** | 一路传染到调用栈顶 |

### 3.3 决策：借用结构 vs 拥有结构

| 用 `Parser<'a>`（借用） | 用 `Parser`（拥有 `String`） |
|---|---|
| ✅ 零拷贝 | ❌ 一次拷贝 |
| ❌ 生命周期传染 | ✅ 无传染，满足 `'static` |
| ❌ 不能跨线程/await | ✅ 可以 |
| 适合：短生命周期的、性能关键的解析 | 适合：几乎所有其它场景 |

**实践建议**：

> **默认让结构体拥有数据。** 只在下面三种情况才用借用结构：
> 1. 你在写一个**零拷贝解析器**（`nom`、`serde` 的 `&'de str`），且 profile 证明拷贝是瓶颈
> 2. 数据量很大且明确是短生命周期的（比如一次请求内）
> 3. 你在写一个**视图类型**（`&[T]` 的包装），它的语义本来就是"借用别人的"

**中间路线**：

```rust
// 用 Arc<str> —— 共享所有权 + 零拷贝的克隆 + 满足 'static
pub struct Parser { input: Arc<str>, pos: usize }

// 用 Cow —— 调用方决定
pub struct Parser<'a> { input: Cow<'a, str>, pos: usize }
impl Parser<'static> { pub fn owned(s: String) -> Self { Parser { input: Cow::Owned(s), pos: 0 } } }

// 存 range 而非引用（第 13 章）
pub struct Token { range: Range<usize> }
```

### 3.4 一个真实的对比

标准库自己就在这两条路上都走过：

| API | 选择 | 为什么 |
|---|---|---|
| `str::split(&self)` → `Split<'_>` | 借用 | 迭代器，短生命周期，零拷贝是核心价值 |
| `String::from_utf8(Vec<u8>)` → `Result<String, _>` | 拥有 | 消耗输入，复用缓冲区 |
| `Path::new(&str)` → `&Path` | 借用 | 纯视图类型 |
| `PathBuf` | 拥有 | 需要长期持有时用它 |

**`&Path` / `PathBuf`、`&str` / `String`、`&[T]` / `Vec<T>` 这三对，
就是标准库给你的模板**：**每个借用视图类型，都配一个拥有版本。**

---

## 4. 生命周期标注的技巧

### 4.1 返回 `'a` 而不是 `&self` 的生命周期

```rust
pub struct Cache<'a> { source: &'a str, tokens: Vec<&'a str> }

impl<'a> Cache<'a> {
    // 版本 A：返回 'a —— 不受 &self 借用限制
    pub fn first_a(&self) -> Option<&'a str> { self.tokens.first().copied() }

    // 版本 B：省略 → 绑到 &self
    pub fn first_b(&self) -> Option<&str> { self.tokens.first().copied() }
}
```

**实测差别**（第 06 章 §7）：

```rust
let mut c = Cache::new(&text);
c.tokenize();
let t = c.first_a();      // 版本 A
c.tokenize();             // ✅ 通过
println!("{:?}", t);

let t = c.first_b();      // 版本 B
c.tokenize();             // ❌ E0502
println!("{:?}", t);
```

> ### ★ 一个强大但要小心的技巧
> **返回 `'a` 而非 `&self` 的生命周期，能让调用方在拿到结果后继续可变借用你。**
>
> 前提：返回的数据确实来自 `'a`（借用的外部数据），而不是 `self` 内部拥有的。
> 用错了会编译失败，不会 unsound。

### 4.2 让调用方不必写标注

**好的 API 让 99% 的调用不需要写生命周期。** 检查表：

- [ ] 单参数返回引用 → 省略规则 2 自动处理 ✅
- [ ] 方法返回引用 → 省略规则 3 自动处理 ✅
- [ ] 多个引用参数且返回引用 → **必须标注**，考虑改设计
- [ ] 结构体带 `'a` → 传染，考虑改成拥有

### 4.3 `impl Trait` 的生命周期捕获（★ 2024 edition 变更）

```rust
// 2021 及以前：默认不捕获生命周期，要显式写
fn iter<'a>(v: &'a [i32]) -> impl Iterator<Item = &'a i32> + 'a { v.iter() }

// 2024：RPIT 默认捕获所有在作用域内的生命周期参数
fn iter(v: &[i32]) -> impl Iterator<Item = &i32> { v.iter() }

// 2024：想排除某个生命周期，用精确捕获语法
fn f<'a, 'b>(x: &'a str, y: &'b str) -> impl Display + use<'a> { x }
```

**迁移影响**：2024 edition 下 `impl Trait` 捕获得**更多**，
所以某些以前能编译的代码（返回值不该借用某个参数）可能需要加 `use<>`。

---

## 5. trait 与生命周期

### 5.1 trait object 默认 `'static`

```rust
Box<dyn Error>                    // 等价于 Box<dyn Error + 'static>
Box<dyn Error + 'a>               // 显式允许借用
&'a dyn Error                     // 等价于 &'a (dyn Error + 'a)
```

**这是一个常见的意外**：

```rust
fn store(&mut self, h: Box<dyn Handler>) { }     // 要求 'static
let local = String::new();
store(Box::new(MyHandler { s: &local }));        // ❌ 不满足 'static
```

**解法**：`Box<dyn Handler + 'a>`，或者让 handler 拥有数据。

### 5.2 GAT：关联类型带生命周期

```rust
pub trait LendingIterator {
    type Item<'a> where Self: 'a;
    fn next(&mut self) -> Option<Self::Item<'_>>;
}
```

见第 14 章 §5。**设计建议**：GAT 会让 trait 显著更难用（不能配 `dyn`、
不能用现成的适配器）。**只在标准 `Iterator` 确实表达不了时才用。**

### 5.3 `async fn` in trait（1.75+）

```rust
pub trait Service {
    async fn call(&self, req: Request) -> Response;         // ✅ 1.75+ 稳定
}
```

**限制**（第 24 章展开）：
- 不能直接用于 `dyn Trait`（要用 `async-trait` 宏或 `trait-variant`）
- **无法给返回的 Future 加 `Send` bound**——编译器会警告
  `use of async fn in public traits is discouraged as auto trait bounds cannot be specified`

**公开库的推荐做法**：

```rust
pub trait Service {
    fn call(&self, req: Request) -> impl Future<Output = Response> + Send;   // ★ 能加 Send
}
```

---

## 6. 一个完整的设计案例

**需求**：一个配置解析器，读一个 TOML 字符串，提供按 key 取值的接口。

### 版本 1：天真的借用设计

```rust
pub struct Config<'a> {
    source: &'a str,
    entries: Vec<(&'a str, &'a str)>,
}
impl<'a> Config<'a> {
    pub fn parse(source: &'a str) -> Self { ... }
    pub fn get(&self, key: &str) -> Option<&'a str> { ... }
}
```

**问题**：
- 调用方必须保证 `source` 活得比 `Config` 久
- 不能存进 `OnceLock<Config>`（不满足 `'static`）
- 不能跨 `await`（第 24 章）
- 每个持有 `Config` 的结构都要加 `'a`

### 版本 2：拥有设计（★ 推荐默认）

```rust
pub struct Config {
    entries: Vec<(String, String)>,
}
impl Config {
    pub fn parse(source: &str) -> Self { ... }            // ★ 参数借用
    pub fn get(&self, key: &str) -> Option<&str> { ... }  // ★ 返回绑到 &self
}
```

**好处**：满足 `'static`、可以放进全局、可以跨线程、无传染。
**代价**：解析时多一次拷贝（通常完全可忽略）。

### 版本 3：零拷贝但拥有（两全）

```rust
use std::ops::Range;
pub struct Config {
    source: String,                          // ★ 拥有源
    entries: Vec<(Range<usize>, Range<usize>)>,   // ★ 存 range 而非引用
}
impl Config {
    pub fn parse(source: String) -> Self { ... }
    pub fn get(&self, key: &str) -> Option<&str> {
        self.entries.iter()
            .find(|(k, _)| &self.source[k.clone()] == key)
            .map(|(_, v)| &self.source[v.clone()])
    }
}
```

**这就是第 13 章"存 range 而非引用"的实战应用**：
零拷贝 + 满足 `'static` + 无传染。**代价是内部代码稍复杂。**

### 版本 4：让调用方选

```rust
pub struct Config<S: AsRef<str>> { source: S, entries: Vec<(Range<usize>, Range<usize>)> }
// Config<String>  → 拥有
// Config<&str>    → 借用
// Config<Arc<str>> → 共享
```

**代价**：泛型参数传染（但比生命周期传染温和得多，因为可以用 `Config<String>` 固定住）。

---

## 7. 动手实验

### 实验 1：改造一个借用结构

拿第 6 节的版本 1，改写成版本 2 和版本 3。然后写测试：

```rust
static CONFIG: OnceLock<Config> = OnceLock::new();       // 版本 1 做不到

#[test]
fn can_be_static() { CONFIG.get_or_init(|| Config::parse("a=1")); }

#[test]
fn can_cross_thread() {
    let c = Config::parse("a=1");
    std::thread::spawn(move || { assert_eq!(c.get("a"), Some("1")); }).join().unwrap();
}
```

### 实验 2：设计一个"组合好的方法"

给下面的结构设计 API，让用户能"遍历所有 item 并对满足条件的记日志"：

```rust
pub struct Store { items: Vec<Item>, log: Vec<String> }
```

用第 2.3 节的四种方案各写一遍，然后问：**哪个 API 最好用？**

### 实验 3：看标准库怎么设计

```bash
# 找出标准库里所有"借用视图 / 拥有"配对
# str / String, Path / PathBuf, OsStr / OsString, [T] / Vec<T>, CStr / CString
```

**任务**：对每一对，回答：
1. 借用版本能做什么，拥有版本不能？
2. 反过来呢？
3. 它们之间怎么转换？（`to_owned`、`into`、`as_ref`、`Deref`）

### 实验 4：`impl Trait` 的 edition 差异

```rust
fn f<'a, 'b>(x: &'a str, _y: &'b str) -> impl std::fmt::Display { x }
```

在 2021 和 2024 edition 下分别编译。**实测**：

```
edition 2021: error[E0700]: hidden type for `impl std::fmt::Display`
                            captures lifetime that does not appear in bounds
edition 2024: ✅ 通过
```

然后试 `use<>` 精确捕获：

```rust
pub fn g<'a,'b>(x: &'a str, _y: &'b str) -> impl Display + use<'a> { x }   // ✅ 2024
```

---

## 8. 本章检查清单

- [ ] **能背出第一条法则：参数尽量借用，返回值尽量拥有**
- [ ] 知道 `&str` / `&[T]` / `&Path` 比 `&String` / `&Vec<T>` / `&PathBuf` 更宽松
- [ ] 知道"内部要 clone 就在签名里要所有权"，以及 `impl Into<T>` 的折中
- [ ] **知道结构体带 `'a` 的四个传染后果**
- [ ] 能说出"什么时候才该用借用结构"的三个条件
- [ ] 知道"存 range 而非引用"能同时拿到零拷贝和 `'static`
- [ ] 知道返回 `'a` vs 返回 `&self` 生命周期的差别及适用场景
- [ ] 知道 trait object 默认是 `+ 'static`
- [ ] 知道 2024 edition 的 RPIT 捕获变更和 `use<>` 语法
- [ ] 知道公开 trait 里 `async fn` 的 `Send` bound 问题及替代写法
- [ ] **知道"提供组合好的方法"是应对借用粒度问题的 API 层解法**

---

## 9. 常见坑

| 现象 | 原因 | 处方 |
|---|---|---|
| 结构体加了 `'a` 之后到处传染 | 借用结构的必然后果 | 改成拥有；或存 range；或 `Arc<str>` |
| 不能放进 `OnceLock` / `static` | 不满足 `T: 'static` | 同上 |
| `Box<dyn Trait>` 报生命周期错 | 默认 `+ 'static` | 写 `Box<dyn Trait + 'a>`；或让实现拥有数据 |
| 用户没法同时调你的两个方法 | `&mut self` 粒度 | 提供 splitter / 组合方法 / 回调 / 公开字段 |
| 用户抱怨要写很多 `&` 和 `.clone()` | 参数类型太具体 | `&String`→`&str`，`&Vec<T>`→`&[T]` |
| `impl AsRef<str>` 导致编译变慢 | 单态化膨胀 | 高频 API 用具体类型 |
| 2024 下 `impl Trait` 报"捕获了不该捕获的生命周期" | RPIT 默认捕获变更 | 用 `use<'a>` 精确捕获 |
| 公开 trait 的 `async fn` 有警告 | 无法指定 `Send` bound | 改成 `-> impl Future<Output=T> + Send` |

---

**阶段 4 到此结束。** 你现在有了完整的工程手册。
接下来第 22–25 章把这一切推广到并发和异步。

下一章：[22 - Send / Sync 的本质](22-send-sync.md)
