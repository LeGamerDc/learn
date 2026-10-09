# 02 - Rust 设计史：三次自我否定

> 本章目标：理解 borrow checker **不是设计出来的，是长出来的**。
> 你现在看到的每一条规则，背后都有一次失败的尝试。知道这些历史，
> 你就能预测"哪些抱怨是暂时的（编译器会改进），哪些是永久的（设计公理不会变）"。
> 预计用时：1.5 小时。

---

## 1. 时间线速览

```
2006  Graydon Hoare 个人项目起步
2009  Mozilla 开始赞助
2010  首次公开；此时的 Rust 有：GC、typestate、绿色线程、四种指针 sigil
      ├─ 2012  ✂ 砍掉 typestate（0.4）              ← 第一次自我否定
      ├─ 2013  ✂ 砍掉 @T（GC 指针）→ Rc/Gc 库化
      ├─ 2014  ✂ 砍掉绿色线程和运行时（RFC 230）      ← 第二次自我否定
      │        ✚ 引入 ~T → Box<T>、生命周期系统成型
2015  1.0 发布。borrow checker = 词法生命周期（lexical lifetimes）
      │        借用活到**作用域末尾**，非常难用
2017  RFC 2094 提出 NLL（non-lexical lifetimes）
2018  1.31 / Rust 2018 edition：NLL 上线                ← 第三次自我否定
2019  1.36：NLL 回移到 2015 edition（迁移模式，先警告）
2022  1.63：旧 borrow checker 彻底删除，NLL 成为唯一实现
2018- Polonius 项目启动（Niko Matsakis 的 datalog 重构）
2024  Rust 2024 edition：临时值作用域规则调整
2026  ★ 08-04：Polonius Alpha 在 nightly 默认开启      ← 第四次换代进行中
      目标：2026 年底稳定化
```

**观察**：Rust 用了 9 年（2006→2015）才找到所有权模型，又用了 11 年（2015→2026）
在**不改变模型**的前提下三次提高检查精度。这个模式很重要——
**规则本身极其稳定，实现精度一直在改进**。

---

## 2. 第一次自我否定：砍掉 typestate（2012）

### 2.1 typestate 是什么

早期 Rust 有一个叫 **typestate** 的系统，思想是：
**同一个类型的值，在不同的程序点可以处于不同的"状态"，编译器追踪状态转换**。

伪代码（当年的语法早已不存在，这里用现代语法示意）：

```
// 假想语法
fn open() -> File : closed -> open;
fn read(f: File : open) -> String;
fn close(f: File : open) -> File : closed;

let f = open();
read(f);      // OK，f 处于 open 状态
close(f);
read(f);      // ❌ 编译错误：f 处于 closed 状态
```

这看起来很美：能静态防止"用已关闭的文件"、"用未初始化的变量"、"重复解锁"。

### 2.2 为什么砍掉

三个原因，每一个都值得记住：

1. **和别名冲突**。typestate 追踪的是"某个**变量**的状态"，但如果有两个引用指向同一个 `File`，
   通过 `a` 改变状态之后，`b` 记录的状态就错了。**没有别名控制的 typestate 是不健全的**。

2. **绝大部分用例可以用类型本身表达**。
   ```rust
   // 不需要 typestate，用两个类型就行（"typestate 模式"）
   struct ClosedFile;
   struct OpenFile { fd: i32 }
   impl ClosedFile { fn open(self) -> OpenFile { ... } }
   impl OpenFile    { fn read(&self) -> String { ... }
                      fn close(self) -> ClosedFile { ... } }
   ```
   关键是 `fn open(self)` **消耗**了 `ClosedFile`——移动语义已经提供了"状态转换后旧状态不可用"。

3. **实现复杂度高、用户心智负担重**。

### 2.3 历史教训

> **移动语义（仿射类型）+ 别名控制，覆盖了 typestate 的绝大部分价值，而且更简单。**

今天你在 Rust 里写的"typestate 模式"（用 `self` 消耗做状态机），
就是 2012 年那场删减留下的遗产。第 21 章讲 API 设计时会用到它。

**同时这也解释了一个常见困惑**：为什么 Rust 不能表达"这个 `&mut` 用过一次之后就失效"？
因为那正是 typestate，而 Rust 选择了用**所有权转移**来表达同一件事。

---

## 3. 第二次自我否定：砍掉 GC 指针和绿色线程（2013–2014）

### 3.1 四种指针 sigil 的时代

1.0 之前的 Rust 有一套 sigil 语法：

| 老语法 | 含义 | 今天的样子 |
|---|---|---|
| `~T` | 唯一所有权，堆分配 | `Box<T>` |
| `@T` | **GC 管理**的共享指针（managed pointer） | `Rc<T>` / `Arc<T>`（**库类型**，非语言特性） |
| `&T` | 借用 | `&T`（唯一活下来的） |
| `*T` | 裸指针 | `*const T` / `*mut T` |

**`@T` 意味着 Rust 当年是一门有 GC 的语言**。运行时里有垃圾回收器，`@T` 分配的对象由它管理。

### 3.2 为什么砍掉

核心理由：**如果所有权系统能表达内存管理，GC 就是多余的重量**。

具体代价：
- 有 GC 就必须有运行时；有运行时就不能做嵌入式、不能写内核、不能做 C 库的替代品
- GC 指针和借用指针的交互规则非常复杂
- 大多数程序用不到共享所有权；把它做成**库**（`Rc`），让需要的人付费

**同一时期砍掉的还有绿色线程（M:N 调度）**，理由高度类似：绿色线程需要运行时、
需要可增长栈（segmented stacks）、和 C FFI 交互困难、且强加给所有用户。
RFC 230 把它移出标准库，`std::thread` 变成 1:1 的 OS 线程。

### 3.3 这对你理解 async 至关重要

**Rust 后来的 async/await（2019, 1.39）本质上是绿色线程的"库化重生"**：

| | 老绿色线程（砍掉的） | 今天的 async |
|---|---|---|
| 调度器 | 内置在语言运行时 | **库**（tokio / async-std / smol），你自己选 |
| 栈 | 可增长的独立栈 | **无栈**：Future 是编译器生成的状态机，捕获的变量放在状态机结构体里 |
| 强加给所有人 | 是 | 否，`no_std` 也能用 |

**"无栈"这个选择直接导致了 `Pin` 的存在**：因为状态机结构体里可能有指向自己其他字段的引用
（跨 `await` 持有的局部引用），而 Rust 的默认移动语义会破坏这种自引用。
第 13 / 24 章会详细展开这条因果链——**它的起点就是 2014 年砍掉运行时这个决定**。

---

## 4. 1.0 时代：词法生命周期，以及它有多难用

Rust 1.0（2015-05）的 borrow checker 使用**词法生命周期**：
**一个借用从创建开始，一直活到它所在的词法作用域（`{}`）结束**。

```rust
fn main() {
    let mut v = vec![1, 2, 3];
    let first = &v[0];       // 借用开始
    println!("{}", first);   // 最后一次使用
    v.push(4);               // ❌ 1.0 时代：报错！因为 first 的借用活到函数末尾
}                            // 借用在这里才结束
```

这段代码**在运行时绝对安全**——`first` 之后再没用过。但词法规则看不到这一点。

**当年的标准绕法**，你在老代码里还能看到：

```rust
let mut v = vec![1, 2, 3];
{
    let first = &v[0];       // 用一个块把借用框起来
    println!("{}", first);
}                            // 借用在这里结束
v.push(4);                   // OK
```

这就是为什么 2015–2018 年的 Rust 代码里到处是**莫名其妙的裸块 `{ ... }`**。
今天你看到这种代码，基本可以判断它写于 NLL 之前。

**词法生命周期真正的痛点**不是多打几个括号，而是有些模式**根本绕不过去**：

```rust
// 词法生命周期时代无解的形态
let mut v = vec![1, 2, 3];
match v.first() {
    Some(x) => println!("{}", x),
    None => v.push(1),          // ❌ v.first() 的借用覆盖整个 match
}
```

---

## 5. 第三次自我否定：NLL（2017–2018）

### 5.1 核心转变

**RFC 2094** 的一句话总结：

> 把生命周期从"**词法作用域**"改成"**控制流图（CFG）上的一组代码点**"。

```
词法生命周期                     NLL
─────────────                   ───────────────────
'a = { 第 3 行 到 第 8 行 }       'a = { 点3, 点4, 点5 }
     （一个连续区间）                  （CFG 上的点集，可以不连续！）
```

这个转变的直接后果：**借用在最后一次使用之后就结束了**，不用等到作用域末尾。

上面第 4 节的三个例子，NLL 全部接受。

### 5.2 "点集"这个词请记住

第 06 章的核心认知翻转就是这个：`'a` **不是一段时间，是一个集合**。

集合可以：
- **不连续**：一个借用可以在 if 分支里活着，在 else 分支里死了
- **做交并**：region inference 本质上是在解一个集合约束方程组
- **为空**：一个从未使用的借用，它的 region 是空集

第 07 章会带你手工解一次这个方程组。

### 5.3 顺带引入的：两阶段借用（two-phase borrows）

NLL 上线时还夹带了一个救命补丁。考虑：

```rust
let mut v = vec![1, 2, 3];
v.push(v.len());
```

按字面规则：`v.push(...)` 需要 `&mut v`（自动引用），而参数 `v.len()` 需要 `&v`。
`&mut` 和 `&` 同时存在 → 应该报错。但这段代码显然是安全的，而且极其常见。

**两阶段借用**的解法：`&mut` 分成两个阶段
1. **保留阶段（reserved）**：`&mut v` 已创建但还没"激活"，此期间它表现得像共享借用，允许其他 `&v`
2. **激活阶段（activated）**：真正调用 `push` 时激活，此后独占

所以 `v.len()` 在保留阶段求值，合法。

⚠️ **但两阶段借用只对"自动引用（autoref）"生效**。手写 `&mut` 不享受：

```rust
Vec::push(&mut v, v.len());    // ❌ E0502
```

这是第 05 章会详讲的一个高频反直觉点。lab 里的 `03` 和 `04` 号案例就是这一对。

### 5.4 上线过程（一个工程管理的范例）

| 版本 | 时间 | 状态 |
|---|---|---|
| 1.31 | 2018-12 | NLL 在 **2018 edition** 生效 |
| 1.36 | 2019-07 | NLL 回移到 **2015 edition**，但用"迁移模式"：新检查器拒绝、旧检查器接受的代码只**警告**不报错 |
| 1.63 | 2022-08 | 旧 borrow checker（AST borrowck）**彻底删除**，警告转为硬错误 |

**从提出 RFC 到完全落地，用了 5 年。** 这个节奏对理解 Polonius 的时间表很有参考价值——
第 16 章会看到 Polonius Alpha 正在走同一条路。

---

## 6. 第四次换代：Polonius（2018–2026）

### 6.1 动机

NLL 大幅提高了精度，但留下了几类**已知的**假阳性，社区称为 "NLL problem cases"。
最著名的是 **problem case #3**：

```rust
fn get_or_insert<'r, K, V>(map: &'r mut HashMap<K, V>, key: K) -> &'r mut V {
    match map.get_mut(&key) {
        Some(v) => v,                                  // 借用要活到返回
        None => {
            map.insert(key, V::default());             // ❌ NLL: E0499
            map.get_mut(&key).unwrap()
        }
    }
}
```

**为什么 NLL 拒绝**：NLL 的 region 推断是"以 region 为中心"的——
它给 `map.get_mut(&key)` 产生的借用分配一个 region `'0`，然后要求 `'0` 包含所有
"`'0` 的引用还活着的点"。由于 `Some(v) => v` 分支要把借用返回出去，
`'0` 必须包含函数返回点，而 CFG 上要到达返回点必须经过 `None` 分支的那些点——
于是 `'0` 把 `None` 分支也吞进去了。

**关键洞察**：NLL 追踪的是"**region 有多大**"，但真正该问的是
"**在这个点上，哪些贷款（loan）还活着**"。在 `None` 分支里，`get_mut` 返回的那个
借用**根本没被使用**，它不该活着。

### 6.2 Polonius 的重构

**Niko Matsakis 2018 年提出**：把 borrow check 重新表述成一组 **Datalog 规则**，
从"以 region 为中心"改成"**以 loan 为中心**"。

核心概念的更名，体现了视角转变：

| NLL 术语 | Polonius 术语 | 含义变化 |
|---|---|---|
| region / lifetime `'a` | **origin** | 从"这个引用活多久"变成"这个引用**可能来自哪些贷款**" |
| region 包含点 P | `origin_live_on_entry(O, P)` | 该 origin 在点 P 处是否还有用 |
| — | `loan_live_at(L, P)` | **贷款 L 在点 P 是否还活着**（新的核心谓词） |
| 冲突检查 | `loan_invalidated_at(L, P)` + `errors` | 显式的错误推导规则 |

**这个重构的价值**不只是精度，还有：
- **可形式化验证**：datalog 规则可以用 Alloy / Coq 检查
- **可解释**：能回答"这个错误是哪条规则推出来的"
- **可增量**：datalog 引擎天然支持增量计算

第 15 章会把这套规则完整写出来并手工推演。

### 6.3 2026 年 8 月的现状（本课程写作时实测）

```bash
$ rustc +nightly --version
rustc 1.100.0-nightly (8fa1c96cf 2026-08-17)

$ rustc +nightly -Zpolonius=bogus x.rs
error: incorrect value `bogus` for unstable option `polonius`
       - either no value or one of `legacy` (the default), `off`, or `next` was expected
```

**实测结论**（完整数据见 [lab/](lab/)）：

| 案例 | NLL | Polonius Alpha |
|---|---|---|
| problem case #1（match 一支借用一支修改） | ❌ E0502 | ✅ |
| problem case #3（HashMap get-or-insert，match 版） | ❌ E0499 | ✅ |
| problem case #3（loop 版） | ❌ E0499 | ✅ |
| 条件重借用 `if c { b } else { a }` | ❌ E0499 | ✅ |
| lending iterator + 条件返回 | ❌ E0499 | ✅ |
| **字段分割借用（经方法）** | ❌ E0502 | **❌ E0502** |
| **自引用结构** | ❌ E0505 | **❌ E0505** |
| **同时 `&mut v[0]` 和 `&mut v[1]`** | ❌ E0499 | **❌ E0499** |

> ⚠️ **两个重要的事实核查**：
> 1. `rustc +nightly -Z help` 里那行 `polonius=val ... (default: no)` 是**过时的帮助文本**。
>    实测证明默认就是开的（上表的 ✅ 全部是不加任何 flag 得到的）。
> 2. Polonius Alpha **不是** 2018 年那篇论文里的完整 Polonius。
>    官方明确说明：Alpha 稳定化之后**不再继续 Polonius 的功能开发**，
>    剩下的工作转到另一个项目目标 "The Borrow Checker Within"（第 17 章）。

---

## 7. 从历史里提炼的四条判断准则

这是本章最有价值的部分——**如何预测未来**。

### 准则 1：公理不会变，精度会变

**"Aliasing XOR Mutability" 从 2014 年至今没变过，也不会变。**
所有的改进（NLL、Polonius、view types）都是在**同一条公理下提高分析精度**。

推论：如果你的代码在语义上真的违反了这条公理（比如同时持有两个 `&mut` 指向同一处），
**永远不要指望编译器将来会接受它**。去改设计。

### 准则 2：能做成库的，就不会做进语言

`Rc` / `Arc` / `RefCell` / async runtime / rayon——都是库。
语言只提供最小的、无法在库里表达的原语（`UnsafeCell`、`Pin`、auto traits）。

推论：当你想"要是语言支持 X 就好了"，先问"X 能做成库吗"。
能的话，八成语言不会加。

### 准则 3：先显式，后推断

NLL 之前生命周期要手写得很多，之后省略规则越来越强。
"The Borrow Checker Within" 的路线图明确写着 **"Explicit and concrete first"**：
先给出显式语法（`'self.text`、view types 标注），再考虑推断。

推论：新特性刚出来时会很啰嗦，别因此判断它没用。

### 准则 4：迁移永远走 edition + 警告期

typestate、`@T`、绿色线程的删除都在 1.0 前，代价小。
1.0 之后的每一次变更（NLL、RFC 2229 闭包捕获、2024 的临时值作用域）都走
**edition 隔离 + 长警告期 + 自动迁移工具（`cargo fix`）**。

推论：Polonius 稳定化**不会**破坏你现有的代码——它只**接受更多**代码，不拒绝更少。
（严格说是超集：Alpha 是 NLL 的超集，实测的 5 个 ★ 案例证明了这一点。）

---

## 8. 动手实验

### 实验 1：体验词法生命周期

Rust 没法直接切回 1.0 的检查器（1.63 已删除），但你可以**模拟**它：
把每个借用都想象成活到作用域末尾，然后看下面哪些代码"在 1.0 时代会失败"。

```rust
fn a() { let mut v = vec![1]; let r = &v[0]; println!("{}", r); v.push(2); }
fn b() { let mut v = vec![1]; { let r = &v[0]; println!("{}", r); } v.push(2); }
fn c(m: &mut std::collections::HashMap<u32, u32>) {
    match m.get(&1) { Some(x) => println!("{}", x), None => { m.insert(1, 0); } }
}
```

<details><summary>答案</summary>

- `a`：1.0 ❌（`r` 活到函数末尾） / 今天 ✅（NLL）
- `b`：1.0 ✅ / 今天 ✅（这就是当年的绕法）
- `c`：1.0 ❌ / 今天 ✅（NLL 已能处理 `match` 的这个形态）

</details>

### 实验 2：亲眼看 Polonius 的差别

```bash
cd lab
./run.sh                    # Polonius 默认开启
```

找出输出里所有标 `★ Polonius 新增接受` 的行，逐个打开对应的 `cases/*.rs` 读一遍。
**这 5 个案例就是 2026 年这次换代的全部实质内容**——记住它们的形状，
以后在自己代码里遇到同样的形状，你就知道"这不是我的错，是精度问题"。

### 实验 3：两阶段借用的边界

```bash
cd lab
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out cases/03-two-phase-borrow.rs   # 通过
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out cases/04-two-phase-limit.rs    # E0502
```

两个文件的差别只有一行写法（`v.push(v.len())` vs `Vec::push(&mut v, v.len())`），
语义完全一样，结果不同。**把完整错误信息读三遍**——这是理解"编译器规则不是语义规则"的最好例子。

---

## 9. 本章检查清单

- [ ] 能说出 typestate 被砍的三个原因，以及今天用什么替代它
- [ ] 能说出砍掉绿色线程和 `Pin` 存在之间的因果链
- [ ] 知道词法生命周期 → NLL 的核心转变是"区间 → 点集"
- [ ] 知道两阶段借用只对 autoref 生效
- [ ] 能说出 NLL problem case #3 的形状，以及 NLL 为什么拒绝它
- [ ] 知道 Polonius 的视角转变：region-centric → loan-centric
- [ ] 知道 Polonius Alpha ≠ 完整 Polonius，且后续工作转到了别的项目
- [ ] 记住四条判断准则，尤其是准则 1

---

## 10. 常见坑

| 误解 | 事实 |
|---|---|
| "Polonius 会让所有借用错误消失" | 只解决"条件控制流"这一类假阳性。字段粒度、自引用、索引不相交这三类**完全没动** |
| "等 Polonius 稳定了我再学生命周期" | Polonius 不改变规则，只提高精度。第 04–10 章的内容一个字都不会变 |
| "NLL 是 2018 年的东西，早过时了" | NLL 至今仍是 stable 上唯一的实现，且**一直在改进**（lab 的 28 号案例就是老资料说"NLL 做不到"但今天能过的例子） |
| "老博客说 X 编译不过" | 复核。2015 → 2026 之间借用检查改进了三轮，网上大量资料已经过时。**用 lab/run.sh 实测** |
| "Rust 砍掉 GC 是因为性能" | 主要原因是**运行时依赖**（不能做嵌入式/内核/FFI 替代），性能是次要的 |

---

下一章：[03 - 设计哲学](03-philosophy.md)——一条公理，五个推论。
