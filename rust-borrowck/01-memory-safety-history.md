# 01 - 内存安全的历史债：borrow checker 到底在防什么

> 本章目标：建立"敌人画像"。如果你不知道 borrow checker 在防什么，
> 你就只会觉得它在刁难你。学完这章，你应该能把七类看似不同的 bug 归结成**同一个根因**，
> 并理解为什么 GC（你在 Go 里习以为常的东西）**解决不了**其中的大部分。
> 预计用时：1.5 小时。

---

## 1. 七类 bug，一个根因

先看七段代码。它们分属不同语言、不同 bug 类别，请先自己找出共同点。

### (a) Use-after-free（C）

```c
char *p = malloc(16);
free(p);
strcpy(p, "boom");        // p 指向的内存已经不属于我们了
```

### (b) Double free（C++）

```cpp
struct Buf { char* p; ~Buf() { free(p); } };
Buf a{malloc(16)};
Buf b = a;                // 浅拷贝：两个 Buf 持有同一个 p
                          // 两次析构 → free 同一块内存两次
```

### (c) 悬垂引用（C++）

```cpp
std::string& bad() {
    std::string s = "local";
    return s;             // s 在函数返回时销毁，引用指向坟墓
}
```

### (d) 迭代器失效（C++）

```cpp
std::vector<int> v = {1,2,3};
for (auto it = v.begin(); it != v.end(); ++it) {
    if (*it == 2) v.push_back(99);   // push_back 可能重新分配 → it 悬垂
}
```

### (e) 迭代器失效（Java，有 GC）

```java
List<String> list = new ArrayList<>(List.of("a","b","c"));
for (String s : list) {
    if (s.equals("b")) list.remove(s);   // ConcurrentModificationException
}
```

### (f) 数据竞争（Go）

```go
counter := 0
var wg sync.WaitGroup
for i := 0; i < 1000; i++ {
    wg.Add(1)
    go func() { defer wg.Done(); counter++ }()   // counter++ 不是原子的
}
wg.Wait()
fmt.Println(counter)   // 通常 < 1000，且每次不同
```

### (g) slice 别名（Go）

```go
a := []int{1, 2, 3, 4}
b := a[:2]
b = append(b, 99)       // 容量够，写进了 a 的底层数组
fmt.Println(a)          // [1 2 99 4] —— a[2] 被"远程"改掉了
```

---

### 共同点

七段代码里，**每一段都同时满足两个条件**：

1. **别名（Aliasing）**：同一块数据存在**两条以上**的访问路径。
   - (a) `p` 和 free 之后的分配器；(b) `a.p` 和 `b.p`；(c) 返回的引用和已销毁的栈帧；
   - (d)(e) 迭代器和容器本身；(f) 1000 个 goroutine 和同一个 `counter`；(g) `a` 和 `b`。

2. **可变（Mutation）**：至少有一条路径在**修改**（写入、释放、扩容、销毁）。
   - (a)(b) 释放；(c) 栈帧销毁；(d)(e) 修改容器结构；(f) 写变量；(g) 写底层数组。

> **只有别名，没有可变** → 完全安全（一万个只读指针指向同一份数据，毫无问题）。
> **只有可变，没有别名** → 完全安全（独占访问，爱怎么改怎么改）。
> **两者同时出现** → 一切内存安全 bug 的温床。

这就是本课程的**核心公理**，第 03 章会展开它的完整表述：

> ### **Aliasing XOR Mutability**（别名与可变，二者不可兼得）

Rust 的全部设计——所有权、借用、生命周期、`Send`/`Sync`、`Pin`——都是在**机械地执行这一条规则**。
当你学完这门课，你会发现所有借用错误的诊断都可以归结成一句话：
**"在这个点上，有两条路径能访问同一份数据，且至少一条能改它。"**

---

## 2. 时间维度：为什么"释放"也算写

上表里我把 `free`、栈帧销毁、`Vec` 扩容都归为"修改"。这需要一点解释。

**释放内存 = 把这块地址的所有权还给分配器**。之后分配器可以把它给别人。
所以 `free(p)` 之后 `*p` 读到的可能是**另一个对象的数据**——这在效果上和"有人把数据改了"完全一样，
而且更危险（可能是密钥、可能是函数指针）。

这就引出了别名规则的**第三个维度**：

```
                空间维度              时间维度
                （谁能访问）          （什么时候能访问）
    别名   ──►  多条路径指向同一处  ×  这些路径的有效期重叠
```

C/C++ 的问题不只是"允许别名 + 可变"，更是**没有任何机制表达"这条路径的有效期"**。
`char *p` 这个类型不包含任何关于"p 指向的东西活多久"的信息，所以编译器无从检查。

Rust 的 `&'a T` 里的 `'a` 就是**把有效期塞进类型里**。第 06 章你会看到，`'a` 的真身
既不是"一段时间"也不是"一个作用域"，而是**控制流图上的一组代码点**。

---

## 3. 历史上的四种解法，各自的代价

### 3.1 手动管理（C）

**规则**：程序员自己记住谁负责 `free`。
**代价**：记不住。

这不是能力问题，是**规模问题**。一个函数里的 malloc/free 配对很容易；
但当指针跨越 20 个函数、3 个模块、2 个线程时，"谁负责释放"变成一个**全局属性**，
而人类只能做**局部推理**。

数据（这些数字值得记住，它们是 Rust 存在的理由）：

| 来源 | 结论 |
|---|---|
| Microsoft Security Response Center（2019） | 微软产品 CVE 中约 **70%** 是内存安全问题 |
| Chromium 安全团队（2020） | Chrome 高危漏洞中约 **70%** 是内存安全问题 |
| Android 安全公告（2019–2022 趋势） | 内存安全漏洞占比随 Rust 代码占比上升而显著下降 |
| Google Android 团队（2022 报告） | 新增 Rust 代码 **零**内存安全漏洞 |

### 3.2 RAII + 智能指针（C++）

**规则**：把释放绑定到析构函数，用 `unique_ptr` / `shared_ptr` 表达所有权。
**代价**：**约定而非强制**。

C++ 的 `unique_ptr` 确实表达了"唯一所有权"，但：

```cpp
std::unique_ptr<Widget> w = std::make_unique<Widget>();
Widget* raw = w.get();        // 随手就能拿到裸指针
w.reset();                    // 释放
raw->method();                // UB，编译器一句话不说
```

C++ 的智能指针是**库层面**的，编译器不理解它们的语义。而 Rust 的所有权是**语言层面**的，
`Box<T>` 的行为由编译器和 borrow checker 共同保证。

> **值得说清楚的一点**：C++ 的 RAII 是 Rust 所有权的直接祖先。Rust 的 `Drop`
> 就是 C++ 的析构函数。区别在于 Rust 补上了 C++ 缺的另一半：**移动之后原变量不可用**
> （C++ 的 moved-from 对象处于"有效但未指定"状态，还能继续用，这就是漏洞来源）。

### 3.3 垃圾回收（Java / Go / C#）

**规则**：运行时追踪可达性，不可达就回收。
**代价**：这是本章对你（Go 开发者）最重要的一节。

GC **完美解决了** (a) use-after-free、(b) double free、(c) 悬垂引用——因为只要还有指针指向它，
它就不会被回收。这三类 bug 在 Go 里确实不存在。

但请回看第 1 节的七个例子：**(d)(e)(f)(g) 四个，GC 一个都解决不了。**

| bug 类别 | GC 能解决吗 | 为什么 |
|---|---|---|
| use-after-free | ✅ | 有引用就不回收 |
| double free | ✅ | 程序员不再调用 free |
| 悬垂引用 | ✅ | 同上 |
| **迭代器失效** | ❌ | 内存还在，但**逻辑状态**已失效（Java 只能运行时抛 `ConcurrentModificationException`） |
| **数据竞争** | ❌ | GC 管的是"内存何时回收"，管不了"谁在写" |
| **slice 别名** | ❌ | 内存合法，但语义是错的 |
| **非内存资源泄漏** | ❌ | 文件句柄、锁、数据库连接——GC 不知道什么时候该关（所以 Go 需要 `defer`） |

**这是理解 Rust 的关键**：Rust 的 borrow checker **不是一个 GC 的替代品**。
它是一个**别名分析器**，内存管理只是它的副产品。

来看 Go 里最典型的两个例子，你大概率遇到过：

```go
// 例 1：map 并发读写 → 直接 fatal error，不可 recover
m := map[string]int{}
go func() { m["a"] = 1 }()
go func() { _ = m["a"] }()
// fatal error: concurrent map read and map write

// 例 2：切片扩容的别名陷阱（第 1 节的 (g)）
func process(data []int) []int {
    return append(data[:0], transform(data)...)   // 原地写！调用者的数据被改了
}
```

Go 团队非常清楚这些问题，给出的方案是**运行时检测**（map 的并发检查、`-race` 检测器）
和**文档纪律**（"不要在 append 之后使用旧 slice"）。
Rust 给出的方案是**编译期拒绝**。这是同一个问题的两种哲学，第 03 章会对比它们的取舍。

### 3.4 引用计数（Swift / Objective-C / Python）

**规则**：每个对象带计数器，归零就释放。
**代价**：循环引用泄漏 + 计数开销 + **仍然不解决别名可变问题**。

Swift 的 `ARC` 和 Rust 的 `Rc` 是同一个东西，区别在于 Swift 把它设为**默认**，
Rust 把它设为**你在真正需要共享所有权时才选用的工具**（第 20 章）。

Swift 后来也发现引用计数解决不了别名问题，于是从 Swift 5.x 开始引入
"exclusivity enforcement"（`inout` 参数的独占访问检查）——**方向和 Rust 是一致的**，
只是主要靠运行时检查。第 27 章会详细对比。

---

## 4. 第五条路：类型系统

前四种解法的共同点是：**在运行时管理内存**（除了 C++ 的部分静态性）。
第五条路是 Rust 走的：**在类型系统里编码所有权和有效期，编译期检查**。

它的思想源头有三条：

### 4.1 线性类型 / 仿射类型（Linear / Affine Types）

**线性类型**（Girard 的线性逻辑，1987）：每个值必须**恰好使用一次**。
**仿射类型**：每个值**最多使用一次**（可以丢弃）。

Rust 的移动语义就是**仿射类型**：

```rust
let s = String::from("hello");
let t = s;              // s 的值移动给 t
println!("{}", s);      // ❌ E0382: borrow of moved value: `s`
```

`s` 被"用掉"了。这直接消灭了 double free：**因为同一个值不可能有两个所有者，
就不可能被 drop 两次**。

> 为什么是仿射而不是线性？因为 Rust 允许你**不使用**一个值（直接丢弃，自动 drop）。
> 真正的线性类型会强制你显式消费每个值——那太难用了。
> 不过 Rust 里有"接近线性"的东西：`#[must_use]` 属性、以及第 26 章会讲的
> `ManuallyDrop`。而 `mem::forget` 的存在（安全函数！）说明 Rust 甚至不保证 drop 一定发生——
> 这是 1.0 之前 `Rc` 循环引用泄漏引发的一场著名争论的结果，见第 02 章。

### 4.2 区域推断（Region Inference）

**Tofte & Talpin, 1994**：把内存分配划分到"区域（region）"，区域整体分配整体释放，
类型系统追踪每个指针属于哪个区域。

Rust 的生命周期 `'a` 就是 region。这个词在 rustc 源码里至今仍是主导术语——
你在第 08 章读 rustc 代码时会看到 `RegionVid`、`region_inference`、`free_regions`，
而不是 `lifetime`。**"lifetime"是面向用户的说法，"region"是编译器内部的说法**。

这也解释了第 06 章那个反直觉的结论：`'a` 不是"一段时间"，是**一个集合**。

### 4.3 Cyclone（2001–2006）

**Cyclone** 是 AT&T 实验室和康奈尔大学做的"安全的 C 方言"，它是 Rust 借用检查最直接的祖先。
Cyclone 已经有了：

- 区域标注：`int *`ρ x`（指针带区域参数）
- 生命周期推断
- 唯一指针（`unique_ptr` 的静态版本）
- 禁止悬垂指针的静态检查

Rust 的 RFC 和早期文档里多次直接引用 Cyclone。区别在于 Cyclone 试图**保持 C 兼容**，
所以背了很多包袱；Rust 从零设计，可以把所有权做成语言的核心而非补丁。

---

## 5. 把七个例子翻译成 Rust

现在回到第 1 节，看 Rust 分别在哪里挡住了它们。**这张表是本课程的路线图**。

| 例子 | Rust 里会怎样 | 靠什么机制挡住 | 章节 |
|---|---|---|---|
| (a) use-after-free | 不可能：值被 drop 后，指向它的引用早已因生命周期检查而不合法 | 生命周期 | 06 |
| (b) double free | 不可能：移动语义保证唯一所有者 | 所有权（仿射类型） | 04 |
| (c) 悬垂引用 | `error[E0106]: missing lifetime specifier` / `E0515: cannot return reference to local variable` | 生命周期省略 + region 检查 | 06 |
| (d)(e) 迭代器失效 | `error[E0502]: cannot borrow v as mutable because it is also borrowed as immutable` | 借用规则 | 05 |
| (f) 数据竞争 | `error[E0373]: closure may outlive the current function` / `E0499` | 借用规则 + `Send`/`Sync` | 22, 23 |
| (g) slice 别名 | `&mut [T]` 是独占的，不可能同时存在另一个视图 | 借用规则 | 05 |

来一个可以马上跑的对照。这是 (d) 迭代器失效的 Rust 版：

```rust
fn main() {
    let mut v = vec![1, 2, 3];
    for x in &v {              // &v 借用了 v
        if *x == 2 {
            v.push(99);        // ❌ E0502
        }
    }
}
```

```
error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
 --> src/main.rs:5:13
  |
3 |     for x in &v {
  |              --
  |              |
  |              immutable borrow occurs here
  |              immutable borrow later used here
4 |         if *x == 2 {
5 |             v.push(99);
  |             ^^^^^^^^^^ mutable borrow occurs here
```

对比 C++ 版本：编译通过，运行时**可能**崩溃（取决于 `push_back` 是否触发重分配，
取决于分配器，取决于运气）。对比 Java 版本：编译通过，运行时**一定**抛异常（有额外的 modCount 检查开销）。

**三种哲学，一目了然**：
- C++：不检查，出事算你的（快，但不安全）
- Java/Go：运行时检查（安全，但有开销，且错误发生在生产环境）
- Rust：编译期检查（安全 + 零开销，但你要学会跟编译器沟通）

---

## 6. 一个必须说清楚的问题：borrow checker 会不会杀错人？

会。而且**这是设计上的必然**。

判断"一个程序是否有别名可变冲突"在一般情况下是**不可判定**的（等价于停机问题）。
所以任何静态检查器都必须在两者中选一个：

- **不健全（unsound）**：可能漏掉真 bug。→ 不可接受，那样就失去了全部意义。
- **不完备（incomplete）**：可能拒绝安全的程序。→ Rust 选了这个。

```rust
// 这段代码在运行时绝对安全，但 NLL 拒绝它（Polonius Alpha 接受，见第 14/16 章）
fn get_or_insert<'a>(map: &'a mut HashMap<u32, String>, k: u32) -> &'a mut String {
    match map.get_mut(&k) {
        Some(v) => v,
        None => {
            map.insert(k, String::new());   // ❌ NLL: E0499
            map.get_mut(&k).unwrap()
        }
    }
}
```

这段代码没有任何别名问题——`map.get_mut` 在 `None` 分支里返回的借用**根本不存在**。
但 NLL 的分析精度不够，它保守地认为 `get_mut` 的借用在整个 `match` 期间都活着。

**这就是 Polonius 存在的理由**（第 15–17 章）：不改变规则，只提高精度，
让更多"本来就正确的程序"通过检查。

> ### 本课程最重要的一个判断技能
>
> 当编译器拒绝你的代码时，问自己：
>
> **"我这段代码，在运行时真的没有两条路径同时访问同一份数据（且至少一条在写）吗？"**
>
> - **确实有** → 编译器是对的，去改设计（占 90%）
> - **确实没有** → 编译器精度不够，用第 18 章的手法绕开（占 10%）
>
> 新手的问题是分不清这两种情况，于是无差别地 `clone()`。学完这门课，你要能 30 秒内分辨。

---

## 7. 动手实验

### 实验 1：亲手制造 Go 的别名 bug

```bash
mkdir -p /tmp/alias-demo && cd /tmp/alias-demo && cat > main.go <<'GOEOF'
package main

import "fmt"

func main() {
	a := []int{1, 2, 3, 4}
	b := a[:2]
	b = append(b, 99)
	fmt.Println("a =", a) // 期望 [1 2 3 4]，实际？
	fmt.Println("b =", b)

	c := []int{1, 2, 3, 4}
	d := c[:2:2] // 三索引切片，限制容量
	d = append(d, 99)
	fmt.Println("c =", c) // 这次呢？
	fmt.Println("d =", d)
}
GOEOF
go run main.go
```

观察两次的差别：`a[:2]` 和 `a[:2:2]` 只差一个数字，一个会污染原数组一个不会。
**Go 把"是否共享底层数组"藏在了容量这个运行时属性里**——你没法从类型上看出来。

### 实验 2：Rust 里的同一个操作

```rust
fn main() {
    let mut a = vec![1, 2, 3, 4];
    let b = &mut a[..2];       // 独占借用前两个元素
    b[0] = 99;
    // println!("{:?}", a);    // ❌ 取消注释试试：E0502
    println!("{:?}", b);
    println!("{:?}", a);       // b 已不再使用，这里 OK（NLL）
}
```

试着把注释那行取消，看错误信息。然后把最后两行调换顺序，再看。

### 实验 3：数据竞争的编译期拦截

```rust
use std::thread;

fn main() {
    let mut counter = 0;
    for _ in 0..10 {
        thread::spawn(|| {
            counter += 1;    // ❌ 看看编译器说什么
        });
    }
    println!("{}", counter);
}
```

把编译器的完整报错抄下来。你会看到 `E0373` 和 `E0499`——
**同一个 bug（Go 里需要 `-race` 才能发现的那个），Rust 在编译期给了两个不同角度的诊断。**
第 22/23 章会解释为什么并发安全在 Rust 里"免费"。

---

## 8. 本章检查清单

- [ ] 能说出内存安全 bug 的统一根因：**别名 + 可变 + 有效期重叠**
- [ ] 能说出 GC **不能**解决的四类问题，并各举一个 Go 的实例
- [ ] 知道"释放"为什么算作一种"写"
- [ ] 知道仿射类型如何消灭 double free
- [ ] 知道 `'a` 在 rustc 内部叫 region，源头是 Tofte-Talpin 的区域推断和 Cyclone
- [ ] 理解 soundness vs completeness 的取舍，知道 Rust 选了"宁可错杀"
- [ ] 能对一段被拒绝的代码作出判断：是我的设计有别名问题，还是编译器精度不够

---

## 9. 常见坑

| 误解 | 事实 |
|---|---|
| "Rust 的 borrow checker 是为了替代 GC" | 内存管理只是副产品。它的本质是**别名分析器**，所以才能顺带解决数据竞争和迭代器失效 |
| "有 GC 就内存安全了" | GC 只解决"内存何时回收"。迭代器失效、数据竞争、逻辑别名 bug 一个都不管 |
| "borrow checker 拒绝的代码一定有 bug" | 不一定。它是保守的（不完备）。但**90% 情况下它是对的**，别急着假设自己是那 10% |
| "borrow checker 接受的代码一定没 bug" | 只保证**内存安全和无数据竞争**。逻辑 bug、死锁、竞态条件（race condition ≠ data race）它一概不管，见第 23 章 |
| "Rust 保证不泄漏内存" | ❌ 不保证。`mem::forget`、`Rc` 循环引用都能泄漏，且是 **safe** 代码。泄漏不是内存**不安全** |

---

下一章：[02 - Rust 设计史](02-rust-design-history.md)——从 GC 语言到所有权系统的三次自我否定。
