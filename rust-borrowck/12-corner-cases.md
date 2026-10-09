# 12 - 场景化 corner case：按开发场景组织的深水区

> 本章目标：把前面所有机制放进**真实开发场景**里，看它们怎么互相绊倒。
> 第 11 章是"按现象"组织的，本章是"按你在写什么代码"组织的——遇到问题时更容易定位。
> 所有例子均在 `rustc 1.96.0`（NLL）和 `1.100.0-nightly`（Polonius Alpha）上实测。
> 预计用时：3 小时。

---

## 场景一：`match` / `if let`

### 1.1 关键区分：借用**返回出去**了吗

这是本章最重要的一条。看这两段几乎一样的代码：

```rust
use std::collections::HashMap;

// b1：借用不离开函数
pub fn b1(m: &mut HashMap<u32, Vec<u32>>) {
    match m.get_mut(&1) {
        Some(v) => v.push(1),
        None => { m.insert(1, vec![]); }        // ✅ NLL 就能过
    }
}

// b2：借用要返回出去
pub fn b2(m: &mut HashMap<u32, Vec<u32>>) -> &mut Vec<u32> {
    match m.get_mut(&1) {
        Some(v) => v,
        None => { m.insert(1, vec![]); m.get_mut(&1).unwrap() }   // ★ NLL ❌ / Polonius ✅
    }
}
```

**实测**：

| | stable 1.96（NLL） | nightly（Polonius Alpha） |
|---|---|---|
| `b1` | ✅ | ✅ |
| `b2` | ❌ E0499 ×2 | ✅ |

**为什么差这么多**：`b2` 把借用返回出去，于是它的 origin 必须包含函数签名里的
universal region `'r`。在 NLL 的点集模型下，`'r` 覆盖函数所有点 → `None` 分支也被覆盖 →
冲突（第 07 章 §9.3）。`b1` 没有这个约束，region 只覆盖 `Some` 分支。

> ### ★ 一条能省你大量时间的判据
> **"NLL problem case #3" 只在借用要跨出函数边界时才咬人。**
> 函数内部的 `match get_mut ... None => insert` 从 NLL 时代就是能过的。
> 网上很多人把这两种情况混为一谈。

**在 stable 上的标准解法**（等 Polonius 稳定后可以简化）：

```rust
// 解法 1：contains_key 先探测（多一次哈希，代码最清晰）
pub fn ok1(m: &mut HashMap<u32, Vec<u32>>) -> &mut Vec<u32> {
    if !m.contains_key(&1) { m.insert(1, vec![]); }
    m.get_mut(&1).unwrap()
}

// 解法 2：entry API（★ 首选，一次哈希）
pub fn ok2(m: &mut HashMap<u32, Vec<u32>>) -> &mut Vec<u32> {
    m.entry(1).or_default()
}
```

**`entry` API 存在的历史原因就是这个 borrow checker 限制**——
它把"查找 + 可能插入"打包成一次操作，避免了两次借用。
这是"用签名表达不变量"的经典范例（第 21 章）。

### 1.2 match 守卫（guard）里的借用

```rust
// ✅ 实测通过
pub fn c2(o: &mut Option<Vec<i32>>) {
    match o {
        Some(v) if v.len() > 0 => v.push(1),
        _ => {}
    }
}
```

**为什么能过**：match 守卫里对绑定变量的访问是**共享借用**，
守卫求值完成后才"激活"分支体里的独占借用。这是编译器专门处理的。

⚠️ **但守卫里不能改被 match 的东西**：

```rust
pub fn bad(v: &mut Vec<i32>) {
    match v.first() {
        Some(_) if { v.push(1); true } => {}     // ❌ 守卫里改 v
        _ => {}
    }
}
```

### 1.3 `if let` 的临时值作用域（★ edition 差异）

**这是 2024 edition 最重要的一处借用相关变更**，第 11 章第 21 条有完整实验。

```rust
use std::sync::RwLock;
fn f(l: &RwLock<Option<i32>>) -> i32 {
    if let Some(v) = *l.read().unwrap() { v } else { *l.write().unwrap() = Some(0); 0 }
}
```

| edition | 结果 |
|---|---|
| 2021 | 💥 **死锁** |
| 2024 | ✅ |

**规则**：
- **2021 及以前**：scrutinee 的临时值活到整个 `if let`（含 `else` 块）结束
- **2024 起**：活到 then 块结束 / 进入 else 块**之前**

**处方**（如果你还在 2021）：把 scrutinee 拆成独立语句。

### 1.4 三种绑定模式的借用后果

```rust
let mut opt = Some(String::from("x"));

match opt        { Some(s) => { /* s: String，opt 被移动 */ } None => {} }
match &opt       { Some(s) => { /* s: &String，opt 被共享借用 */ } None => {} }
match &mut opt   { Some(s) => { /* s: &mut String */ } None => {} }
match opt.as_mut() { Some(s) => { /* 同上，更显式 */ } None => {} }
```

**match ergonomics（默认绑定模式）**：当 scrutinee 是引用时，
模式里的绑定自动变成引用，不需要写 `Some(ref s)`。
这是 2018 引入的语法糖，方便但偶尔会让人搞不清 `s` 到底是什么类型。

**排查技巧**：加个错误的类型标注让编译器告诉你：

```rust
match &opt { Some(s) => { let _: () = s; } None => {} }
// error: expected `()`, found `&String`   ← 编译器告诉你 s 是 &String
```

---

## 场景二：循环

### 2.1 分类：改元素 vs 改结构

```rust
// ✅ 改元素的值
pub fn d1(v: &mut Vec<i32>) { for x in v.iter_mut() { *x += 1; } }

// ❌ 改容器结构
pub fn d(v: &mut Vec<String>) {
    for s in v.iter() {
        if s.is_empty() { v.push("x".into()); }    // E0502
    }
}
```

**这是唯一一个在本章测试里 NLL 和 Polonius 都拒绝的循环形态**——
因为它是**真正的**别名冲突（迭代器持有指向缓冲区的指针，`push` 可能重分配）。

**四种解法**：

```rust
// 1. 先收集，后修改（最常用）
let to_add: Vec<String> = v.iter().filter(|s| s.is_empty()).map(|_| "x".into()).collect();
v.extend(to_add);

// 2. 用索引（放弃借用，接受边界检查）
for i in 0..v.len() { if v[i].is_empty() { /* 注意 len 在变 */ } }

// 3. 用标准库提供的"安全的边迭代边改"API
v.retain(|s| !s.is_empty());
v.drain(..).for_each(|s| { /* 消耗 */ });
v.dedup();

// 4. 先 take 出来，处理完再放回（★ 通用手法）
let old = std::mem::take(v);
*v = old.into_iter().flat_map(|s| if s.is_empty() { vec![s, "x".into()] } else { vec![s] }).collect();
```

### 2.2 `for i in 0..v.len()` 里 push 是安全的

```rust
pub fn c(v: &mut Vec<i32>) {
    for i in 0..v.len() {       // ★ 范围在循环开始前就求值了
        let x = v[i];
        v.push(x);              // ✅ 编译通过，且不会无限循环
    }
}
```

**为什么能过**：`0..v.len()` 是一个 `Range<usize>`，它**不持有任何借用**。
每次 `v[i]` 和 `v.push` 都是独立的短借用。

**但要小心语义**：`v.len()` 只在循环开始时算了一次。这既是安全的来源，
也可能不是你想要的行为。

### 2.3 `while let` 与容器

```rust
// ✅ pop 每次都是独立的可变借用
pub fn e(v: &mut Vec<i32>) {
    while let Some(x) = v.pop() {
        if x > 0 { v.push(x - 1); }
    }
}

// 💥 无限循环（不是借用问题，是逻辑问题）
while let Some(x) = v.last() { /* 没有 pop，永远是同一个 */ }
```

### 2.4 循环里携带 `&mut`（Polonius 的强项）

```rust
// lab/07：loop 版的 get-or-insert
pub fn f<'r, K: Hash + Eq + Copy, V: Default>(map: &'r mut HashMap<K, V>, key: K) -> &'r mut V {
    loop {
        match map.get_mut(&key) {
            Some(v) => return v,
            None => { map.insert(key, V::default()); }
        }
    }
}
```

**实测**：NLL ❌ E0499 / Polonius ✅

**这是循环 + 条件返回借用的组合，NLL 的最弱项。** Polonius 用可达性分析
正确地判断出"`None` 分支执行时，上一轮 `get_mut` 的贷款已经死了"。

---

## 场景三：闭包

### 3.1 捕获就是借用，活到最后一次调用

```rust
pub fn e1(v: &mut Vec<i32>) {
    let mut add = |x| v.push(x);       // 独占借用 v
    // println!("{:?}", v);            // ❌ E0502
    add(1);
    add(2);
    println!("{:?}", v);               // ✅ add 不再使用
}
```

### 3.2 两个闭包借不同的东西（✅）

```rust
pub fn e2(v: &mut Vec<i32>, w: &mut Vec<i32>) {
    let mut a = || v.push(1);
    let mut b = || w.push(1);          // ✅ 不同的 place
    a(); b();
}
```

### 3.3 RFC 2229：按字段捕获（2021 edition 起）

```rust
struct S { a: Vec<i32>, b: Vec<i32> }
impl S {
    pub fn f(&mut self) {
        let c = || self.a.len();       // 2021+：只捕获 self.a
        self.b.push(c() as i32);       // ✅ 2021+；2018 ❌
    }
}
```

**注意**：这是 **edition 相关**的行为。老项目升级 edition 时，
这一条既可能修好一堆代码，也可能改变 `Drop` 的时机（因为捕获的东西变少了）。
`cargo fix --edition` 会在必要处插入 `let _ = &s;` 来保持旧的捕获行为。

### 3.4 闭包不能有生命周期省略

见第 11 章第 14 条。核心：`|s: &str| s` ❌，`|s| s` ✅。

### 3.5 `move` 闭包与 `Drop` 时机

```rust
let data = vec![1, 2, 3];
let c = move || println!("{:?}", data);
// data 现在归闭包所有，闭包 drop 时 data 才 drop
drop(c);      // data 在这里 drop
```

---

## 场景四：临时值与作用域（最容易出隐蔽 bug 的地方）

### 4.1 临时值延长的完整规则（实测表）

| 代码 | 结果 | 规则 |
|---|---|---|
| `let r = &String::from("x");` | ✅ | 直接借用 → 延长 |
| `let r = &&String::from("x");` | ✅ | 嵌套借用 → 逐层延长 |
| `let r = &(String::from("x"), 1).0;` | ✅ | 元组字段访问 → 穿透 |
| `let r = S(&String::from("x"));` | ✅ | 元组结构体构造器 → 穿透 |
| `let r = if c { &String::from("a") } else { &String::from("b") };` | ✅ | if/else → 穿透 |
| `let r = &String::from("x").len();` | ✅ | 借的是 `.len()` 产出的 `usize` 临时值 |
| `let r = String::from("x").as_str();` | ❌ E0716 | **方法调用** → 不穿透 |
| `let v: Vec<&str> = vec![&format!("{}", 1)];` | ❌ E0716 | 宏/函数参数 → 不穿透 |
| `let r = &RefCell::new(5).borrow();` | ❌ E0716 | `RefCell` 临时值不延长 |
| `let c = RefCell::new(5); let r = &c.borrow();` | ✅ | `c` 有名字了 |

> **记忆法**：**延长穿透"纯语法构造"，不穿透"函数/方法调用"。**

### 4.2 语句末尾 drop 的陷阱：`match`/`if` 的 scrutinee

```rust
use std::sync::Mutex;
let m = Mutex::new(vec![1, 2, 3]);

// 💥 死锁风险（2021 及以前）：guard 活到整个 match 结束
match m.lock().unwrap().len() {
    0 => { m.lock().unwrap().push(1); }        // 再次加锁
    _ => {}
}

// ✅ 显式结束
let n = m.lock().unwrap().len();
match n { 0 => { m.lock().unwrap().push(1); } _ => {} }
```

**2024 edition 改了 `if let` 的规则，但 `match` 的 scrutinee 临时值
仍然活到整个 `match` 结束**——这是刻意的（match arm 里可能要用 scrutinee 借出来的东西）。

**处方**：涉及锁 / `RefCell` 时，**永远把 scrutinee 拆成独立语句**。

### 4.3 尾表达式的 drop 顺序（★ edition 差异）

```rust
use std::cell::RefCell;
pub fn f() -> i32 { let c = RefCell::new(5); *c.borrow() }
```

| edition | 结果 |
|---|---|
| 2021 | ❌ E0597（`c` 先于临时 `Ref` 被 drop） |
| 2024 | ✅（临时值在局部变量之前 drop） |

---

## 场景五：方法链与 getter

### 5.1 连续调用 `&mut self` 方法（✅）

```rust
struct S { v: Vec<i32> }
impl S { fn get(&mut self) -> &mut Vec<i32> { &mut self.v } }

pub fn h(s: &mut S) {
    s.get().push(1);
    s.get().push(2);      // ✅ 第一个借用在语句末尾就结束了
}
```

### 5.2 同时持有两个 getter 的结果（❌）

```rust
pub fn bad(s: &mut S) {
    let a = s.get();
    let b = s.get();      // ❌ E0499
    a.push(1);
}
```

**解法**：splitter 方法。

```rust
impl S {
    fn split(&mut self) -> (&mut Vec<i32>, &mut Vec<i32>) { (&mut self.a, &mut self.b) }
}
```

### 5.3 返回借用 self 的迭代器（✅，但有条件）

```rust
struct S { v: Vec<i32> }
impl S { pub fn iter(&self) -> impl Iterator<Item = &i32> { self.v.iter() } }

pub fn g1(s: &mut S) {
    let n: i32 = s.iter().sum();     // 借用在这一句结束
    s.v.push(n);                     // ✅
}
```

⚠️ 但如果把 `sum()` 的结果延迟使用就不行了：

```rust
let it = s.iter();
s.v.push(1);              // ❌ it 还借着 s
let n: i32 = it.sum();
```

---

## 场景六：错误处理与 `?`

### 6.1 `?` 在持锁时（✅ 但危险）

```rust
use std::sync::Mutex;
pub fn f1(m: &Mutex<Option<i32>>) -> Option<i32> {
    let g = m.lock().unwrap();
    Some((*g)? + 1)          // ✅ 编译通过
}                            // g 在这里 drop（含提前 return 的路径）
```

**编译没问题**，因为 `?` 的提前返回路径上 `g` 也会被正确 drop。
**但要小心**：如果 `?` 提前返回时你还持有锁，而调用方随后又要加锁，就死锁了。

### 6.2 `?` 与临时值

```rust
// ✅ HashMap 的 get 返回 Option<&V>，? 之后仍借着 m
pub fn f(m: &HashMap<u32, String>) -> Option<usize> { Some(m.get(&1)?.len()) }
```

---

## 场景七：递归数据结构

**实测五个形态**（`pub struct N { kids: Vec<N>, val: i32 }`）：

```rust
// ✅ 递归遍历
pub fn ok1(n: &mut N) { n.val += 1; for k in n.kids.iter_mut() { ok1(k); } }

// ✅ 同时持有子节点的 &mut 和父节点的另一个字段（不同 place）
pub fn ok2(n: &mut N) { let c = &mut n.kids[0]; n.val += 1; c.val += 1; }

// ✅ 兄弟节点：用 split_at_mut
pub fn ok3(n: &mut N) { let (l, r) = n.kids.split_at_mut(1); l[0].val += r[0].val; }

// ❌ 两个兄弟节点用下标
pub fn bad1(n: &mut N) { let a = &mut n.kids[0]; let b = &mut n.kids[1]; a.val += b.val; }

// ❌ 遍历时改结构
pub fn bad2(n: &mut N) { for k in n.kids.iter_mut() { n.kids.push(N{kids:vec![],val:0}); } }

// ★ 条件返回父或子
pub fn cond(n: &mut N) -> &mut N { let c = &mut n.kids[0]; if c.val > 0 { c } else { n } }
```

**实测结果**：

| 函数 | NLL（stable 1.96） | Polonius Alpha（nightly） |
|---|---|---|
| `ok1` / `ok2` / `ok3` | ✅ | ✅ |
| `bad1`（两个兄弟用下标） | ❌ E0499 | ❌ E0499 |
| `bad2`（遍历时改结构） | ❌ E0499 | ❌ E0499 |
| **`cond`（条件返回父或子）** | ❌ E0499 | **✅** |

**三条结论**：

1. **`ok2` 能过说明借用粒度是 place**：`n.kids[0]` 和 `n.val` 是不相交的路径。
2. **`bad1`/`bad2` 是真正的别名冲突**，Polonius 也不救——需要 `split_at_mut`（`ok3`）
   或者第 20 章的 arena + index。
3. **`cond` 是 Polonius 的强项**：条件返回借用，实测从 ❌ 变 ✅。
   这个形态在树/图的遍历代码里非常常见（"找到就返回子节点，否则返回自己"）。

## 场景八：字符串

```rust
pub fn k(s: &mut String) {
    let first = &s[0..1];        // 借用 s
    println!("{}", first);
    s.push('x');                 // ✅ first 不再使用
}
```

**字符串特有的坑**（不是借用问题，但同样高频）：

```rust
let s = String::from("héllo");
// let c = s[0];                 // ❌ String 不支持整数索引（UTF-8 变长）
let c = s.chars().next();        // ✅
let sub = &s[0..1];              // ✅ 但必须落在字符边界上，否则运行时 panic
```

---

## 动手实验

### 实验 1：b1 vs b2 的分水岭

```bash
cd /tmp && cat > b.rs <<'RSEOF'
use std::collections::HashMap;
pub fn b1(m: &mut HashMap<u32,Vec<u32>>) {
    match m.get_mut(&1) { Some(v)=>v.push(1), None=>{ m.insert(1,vec![]); } }
}
pub fn b2(m: &mut HashMap<u32,Vec<u32>>) -> &mut Vec<u32> {
    match m.get_mut(&1) { Some(v)=>v, None=>{ m.insert(1,vec![]); m.get_mut(&1).unwrap() } }
}
RSEOF
echo "--- stable (NLL) ---";   rustc --edition 2024 --crate-type=lib --emit=metadata --out-dir /tmp/o b.rs 2>&1 | grep "^error"
echo "--- nightly (Polonius) ---"; rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir /tmp/o b.rs 2>&1 | grep "^error"
```

**任务**：解释为什么只有 `b2` 失败。用第 07 章的 origin/贷款模型推演一遍。

### 实验 2：临时值延长的十种形态

把第 4.1 节表格里的十行全部敲进一个文件，编译，确认哪三行报 E0716。
然后对每个失败的，写出修好的版本。

### 实验 3：edition 迁移的影响

拿一个你自己的（或随便找一个）2018/2021 edition 的项目，改成 2024：

```bash
cargo fix --edition
```

**观察 `cargo fix` 插入了什么**。你大概率会看到 `let _ = &s;` 这种语句——
那是为了保持 RFC 2229 之前的闭包捕获行为。

---

## 本章检查清单

- [ ] 知道"NLL problem case #3 只在借用跨出函数时才咬人"
- [ ] 知道 `entry` API 存在的历史原因
- [ ] 能区分"改元素"和"改结构"，并知道各自的解法
- [ ] 知道 `for i in 0..v.len()` 为什么不产生借用冲突
- [ ] 知道闭包捕获的活跃期是"到最后一次调用为止"
- [ ] 知道 RFC 2229 是 edition 相关的，且会影响 `Drop` 时机
- [ ] **能背出临时值延长的记忆法："穿透纯语法构造，不穿透函数调用"**
- [ ] 知道 `match` 的 scrutinee 临时值活到整个 match 结束（2024 也没改）
- [ ] 涉及锁 / `RefCell` 时，条件反射地把 scrutinee 拆成独立语句

---

## 常见坑速查

| 场景 | 症状 | 处方 |
|---|---|---|
| `match get_mut` + `insert` | E0499（仅当要返回借用） | `entry` API；或升 nightly |
| 循环里改容器 | E0502 | 先 collect / `retain` / `mem::take` |
| 闭包借了变量 | E0502 | 缩小闭包作用域；或分开借不同字段 |
| `if let` 里死锁 | 无编译错误，💥 运行时 | 升 edition 2024；或拆 scrutinee |
| `match m.lock()...` 死锁 | 无编译错误，💥 运行时 | **永远**拆成独立语句 |
| `String::from(..).as_str()` | E0716 | 给临时值命名 |
| 两个 getter 同时用 | E0499 | splitter 方法 |
| 迭代器延迟使用 | E0502 | 立即消耗；或 collect |
| `s[0]` on String | 编译错误 | `.chars()` / `&s[a..b]`（注意字符边界） |

---

下一章：[13 - 自引用结构与 Pin](13-self-referential-pin.md)
