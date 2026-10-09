# 附录 B - 术语表

> 中英对照，含 rustc 内部术语。★ 标记的是本课程的核心概念。
> 括号里是首次出现的章节。

---

## 核心概念

| 术语 | 英文 | 含义 |
|---|---|---|
| ★ **别名与可变互斥** | Aliasing XOR Mutability | 本课程的核心公理：对任意数据，要么多处可读，要么一处可写（03） |
| ★ **所有权** | ownership | 每个值有唯一所有者，负责 drop（04） |
| ★ **借用** | borrow | 通过 `&`/`&mut` 临时访问而不取得所有权（05） |
| **共享引用** | shared reference `&T` | 可以有多个，只读（且 `Copy`）（05） |
| ★ **独占引用** | exclusive reference `&mut T` | 同一时刻只有一个；**"可变引用"是历史遗留的误称**（03） |
| ★ **贷款** | **loan** | 一次 `&`/`&mut` 操作产生的记录，编译器编号 `bw0`/`bw1`（07） |
| ★ **起源** | **origin** | Polonius 里 `'a` 的真身：**这个引用可能来自哪些贷款**的集合（07） |
| **区域** | **region** | NLL 里 `'a` 的真身：CFG 上的一组程序点。rustc 内部主导术语（06/07） |
| ★ **位置** | **place** | 可读写的内存位置的路径表达式：`x`、`x.a`、`*p`、`v[i]`。**借用检查的粒度**（05） |
| **移动** | move | 转移所有权；机器层面就是 memcpy + 编译期标记源失效（04） |
| **部分移动** | partial move | 只移走结构体的部分字段（04） |
| ★ **重借用** | **reborrow** | 从 `&mut r` 派生新借用，期间 `r` 被冻结。`&mut` 复用的机制（05） |
| ★ **两阶段借用** | two-phase borrow | autoref 产生的 `&mut` 分"保留/激活"两阶段，让 `v.push(v.len())` 合法（05） |
| **型变** | variance | 子类型关系如何穿过泛型：协变/逆变/不变（09） |
| **协变** | covariant | `A <: B` ⟹ `F<A> <: F<B>`（09） |
| **逆变** | contravariant | `A <: B` ⟹ `F<B> <: F<A>`（09） |
| **不变** | invariant | 没有任何关系。`&mut T` 对 `T`、`Cell<T>` 对 `T` 都是（09） |
| ★ **高阶 trait 约束** | HRTB (Higher-Ranked Trait Bound) | `for<'a>`，全称量词（10） |
| **早绑定/晚绑定** | early-bound / late-bound | 生命周期参数在"引用函数时"还是"调用时"确定（10） |

---

## 编译器内部

| 术语 | 英文 | 含义 |
|---|---|---|
| **MIR** | Mid-level IR | 控制流图形式的中间表示，借用检查在它上面做（07） |
| **基本块** | basic block, `bbN` | 一串顺序语句 + 一个终结符（07） |
| **程序点** | point | Polonius 里是 `Start(bbN[i])` / `Mid(bbN[i])` 两个半步（07） |
| **终结符** | terminator | 基本块末尾的跳转/调用/返回（07） |
| **假读** | `FakeRead` | 编译器插入的假读，让 `let`/`match` 的借用检查符合直觉（07） |
| **展开路径** | unwind path | panic 时的清理路径。**借用检查也要考虑它**（07） |
| **全局区域** | universal region / free region / placeholder | 函数签名里的生命周期，值由调用方决定（08/15） |
| **占位贷款** | placeholder loan | 给 universal region 分配的假想贷款（15） |
| **数据流分析** | dataflow analysis | borrowck 跑三个：`Borrows`、`MaybeUninitializedPlaces`、`EverInitializedPlaces`（08） |
| **移动路径** | move path, `mpN` | 移动分析追踪的 place 路径（08） |
| **place 冲突** | `places_conflict` | 判定两个 place 是否可能指向同一处（08） |
| **不动点** | fixpoint | 反复应用规则直到不再产生新事实（07/15） |
| **局部化约束** | localized constraint | Polonius Alpha 里 `(origin, point)` 图上的边（07） |

---

## 生命周期相关

| 术语 | 英文 | 含义 |
|---|---|---|
| **省略规则** | lifetime elision | 三条自动补生命周期的规则；★ **规则 3 优先于规则 2**（06） |
| **`'static`（引用）** | `&'static T` | 引用的数据永不销毁（06） |
| ★ **`'static`（约束）** | `T: 'static` | **T 内部不含任何短命引用**。`String` 满足！（06） |
| **outlives** | `'a: 'b` | `'a` 长于 `'b`；集合上是 `'b ⊆ 'a`（**方向相反**）（06） |
| **临时值生命周期延长** | temporary lifetime extension | `let r = &temp;` 时临时值被延长；**不穿透函数调用**（06/12） |
| **drop 检查** | dropck | 有 `Drop` 的类型，其生命周期参数必须严格长于它自己（04） |
| **`#[may_dangle]`** | — | dropck 的逃生舱（不稳定，标准库专用）（04/26） |

---

## 类型系统

| 术语 | 英文 | 含义 |
|---|---|---|
| **仿射类型** | affine type | 每个值**最多**使用一次。Rust 的移动语义（01） |
| **线性类型** | linear type | 每个值**恰好**使用一次。Rust **不是**（01） |
| **自动 trait** | auto trait | 编译器自动为"所有字段满足"的类型实现：`Send`/`Sync`/`Unpin`/`Sized`（22） |
| ★ **`Send`** | — | 类型可以安全地**移动**到另一个线程（22） |
| ★ **`Sync`** | — | `&T` 可以给另一个线程；**⟺ `&T: Send`**（22） |
| **`Unpin`** | — | "我不在乎被移动"。99% 的类型都是（13） |
| **`Sized`** | — | 编译期已知大小（隐式默认 bound）（13） |
| **泛型关联类型** | GAT | 关联类型带泛型/生命周期参数，1.65 稳定（14） |
| **RPIT / RPITIT** | return-position `impl Trait` (in trait) | 返回位置的 `impl Trait`；RPITIT 1.75 稳定（21/25） |
| **AFIT** | `async fn` in trait | 1.75 稳定；不能直接 `dyn`（25） |
| **dyn 兼容** | dyn compatible（旧称 object safe） | 能否做 trait object（25） |
| **精确捕获** | `use<'a>` | 2024 edition 用来控制 RPIT 捕获哪些生命周期（21） |

---

## 内部可变性

| 术语 | 英文 | 含义 |
|---|---|---|
| ★ **内部可变性** | interior mutability | 通过 `&T` 修改数据（19） |
| ★ **`UnsafeCell`** | — | **唯一的合法裂缝**，语言项；所有内部可变性类型的基础（19） |
| **`Cell<T>`** | — | 整体读写替换，不泄漏引用，**零开销**（19） |
| **`RefCell<T>`** | — | 运行时借用计数，违反 panic（19） |
| **`OnceLock`/`LazyLock`** | — | 线程安全的"只写一次"，1.80 稳定，取代 `lazy_static!`（19） |
| **锁中毒** | lock poisoning | 持锁线程 panic 后 `lock()` 返回 `Err`（19） |

---

## 自引用与 async

| 术语 | 英文 | 含义 |
|---|---|---|
| **自引用结构** | self-referential struct | 字段指向同结构的另一部分。安全 Rust 里"能建但不能移动"（13） |
| ★ **`Pin<P<T>>`** | — | 保证 `!Unpin` 的值在 drop 前不移动。**零运行时开销**（13） |
| **pin 投影** | pin projection | 从 `Pin<&mut Struct>` 得到字段的 `Pin<&mut Field>`。用 `pin-project-lite`（13） |
| **无栈协程** | stackless coroutine | Future 是编译器生成的状态机，没有独立栈（02/24） |
| ★ **取消安全** | cancellation safety | 在任意 `await` 点被 drop 都不留下不一致状态（24/25） |
| **`spawn_blocking`** | — | 把阻塞操作隔离到专用线程池（25） |

---

## `unsafe` 与别名模型

| 术语 | 英文 | 含义 |
|---|---|---|
| ★ **健全 / 不健全** | sound / unsound | sound = 不可能接受违反规则的程序；**unsound 是最严重的 bug 类别**（03/26） |
| **完备 / 不完备** | complete / incomplete | complete = 不会拒绝正确程序。**Rust 选择 incomplete**（03） |
| **未定义行为** | UB (Undefined Behavior) | 编译器可以假设不会发生的事（26） |
| ★ **Stacked Borrows** | — | 别名模型：每个内存位置有一个借用栈。**Miri 默认**（26） |
| ★ **Tree Borrows** | — | 更宽松的别名模型：树 + 状态机（`Reserved`/`Active`/`Frozen`/`Disabled`）（26） |
| **Miri** | — | Rust 的 UB 检测解释器。`cargo +nightly miri test`（26） |
| **soundness 边界** | soundness boundary | safe/unsafe 的分界；库不能让 safe 代码触发 UB（03/26） |
| **安全契约** | safety contract | `unsafe fn` 的 `# Safety` 文档 + 每个 `unsafe {}` 的 `// SAFETY:` 注释（26） |

---

## 历史与路线图

| 术语 | 英文 | 含义 |
|---|---|---|
| **词法生命周期** | lexical lifetimes | 1.0 时代：借用活到作用域末尾（02） |
| ★ **NLL** | Non-Lexical Lifetimes | 2018 起：region = CFG 点集，借用止于最后一次使用（02/07） |
| ★ **Polonius** | — | 下一代：origin = 贷款集，贷款活跃性 = 图可达性（07/15/16） |
| ★ **Polonius Alpha** | — | **2026-08-04 起 nightly 默认开启**，目标 2026 底稳定（16） |
| **problem case #N** | — | RFC 2094 列出的四个典型难题；**只有 #3 留给了 Polonius**（14） |
| **view types** | — | 提案：`&mut {counter} self`，声明只访问哪些字段（17） |
| **place-based lifetimes** | — | 提案：`'map`、`'self.text`，用 place 命名生命周期（17） |
| **internal references** | — | 提案：`&'self.text str`，结构体持有指向自己数据的引用（17） |
| **typestate** | — | 早期 Rust 特性，2012 年在 0.4 移除（02） |
| **RFC 2229** | disjoint closure capture | 2021 edition：闭包按字段捕获（12） |
| **leakpocalypse** | — | 1.0 前的争论，结论：**Rust 放弃"drop 一定执行"的保证**（03） |

---

## 工程手法（第 18 章）

| 术语 | 含义 |
|---|---|
| **解构** | `let S { a, b } = s;` 让编译器在语法上看到不相交 ★ |
| **splitter 方法** | `fn split(&mut self) -> (&mut A, &mut B)` |
| **`mem::take`/`replace`/`swap`** | 在只有 `&mut` 时合法地搬出值（放替代品进去） |
| **entry 风格 API** | 把"查找 + 可能修改"打包成一次操作 |
| ★ **索引代替引用** | 用 `usize`/newtype id 代替 `&T`，所有借用问题消失 |
| **arena** | 所有节点存一个 `Vec`，用索引互指 |
| **代际索引** | generational index：索引 + 代数，删除后旧 key 自动失效（`slotmap`） |
| **`Cow`** | Clone-on-Write：借用或拥有，按需 |
| **控制反转** | 传回调进去，让被调方决定借用顺序 |

---

## 常用 flag 速查

| 命令 | 作用 | 章节 |
|---|---|---|
| `rustc -Zunpretty=mir` | 打印 MIR | 07 |
| `rustc -Zdump-mir=nll -Zdump-mir-dir=out` | dump region 推断结果 | 07/08 |
| `rustc -Znll-facts -Znll-facts-dir=facts` | dump Polonius 输入事实 | 08/15 |
| `rustc -Zpolonius=off` | 退回 NLL | 16 |
| `rustc -Ztime-passes` | 各 pass 耗时（含 `MIR_borrow_checking`） | 16 |
| `rustc -Ztreat-err-as-bug=1` | 第一个错误直接 panic，拿 backtrace | 08 |
| `RUSTC_LOG=rustc_borrowck=debug` | borrowck 详细日志 | 08 |
| `cargo +nightly miri test` | UB 检测 | 26 |
| `MIRIFLAGS=-Zmiri-tree-borrows` | 换别名模型 | 26 |
| `cargo fix --edition` | edition 迁移 | 12 |
