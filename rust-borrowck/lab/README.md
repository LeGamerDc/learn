# lab — 可复现的借用检查实验床

本目录里的每个 `cases/*.rs` 都是一个**独立的最小例子**，用来回答一个问题：
**"这段代码在 NLL 下过不过？在 Polonius Alpha 下过不过？"**

在 2026 年，这已经不再是一个二值问题——所以本课程的所有边界案例都在这里实测，
而不是凭记忆或凭旧博客写。

## 用法

```bash
rustup toolchain install nightly      # 需要 2026-08-04 之后的 nightly
./run.sh                              # 默认 edition 2024
EDITION=2021 ./run.sh                 # 对比 edition 差异（19/20 号案例会变）
```

输出示例（本课程写作时的实测结果，`rustc 1.100.0-nightly (8fa1c96cf 2026-08-17)`）：

```
案例                             NLL            Polonius Alpha 结论
────────────────────────────────────────────────────────────────────
05-problem-case-1.rs               [E0502]        ✅            ★ Polonius 新增接受
06-problem-case-3-match.rs         [E0499]        ✅            ★ Polonius 新增接受
07-problem-case-3-loop.rs          [E0499]        ✅            ★ Polonius 新增接受
08-conditional-reborrow.rs         [E0499]        ✅            ★ Polonius 新增接受
10-lending-iter-conditional.rs     [E0499]        ✅            ★ Polonius 新增接受
12-disjoint-fields-methods.rs      [E0502]        [E0502]        两者都拒绝
13-two-elems-index.rs              [E0499]        [E0499]        两者都拒绝
15-selfref-struct.rs               [E0505]        [E0505]        两者都拒绝
...
```

## `verify-md.py` — 全书代码块回归核查

`run.sh` 管的是 28 个边界案例；`verify-md.py` 管的是**正文里的每一个代码块**。
它把全书 514 个 ```` ```rust ```` 块逐个送进 `rustc`，
和块内自称的结论（`// ✅` / `// ❌ E0xxx`）逐条比对：

```bash
python3 verify-md.py                       # 核查全书
python3 verify-md.py ../06-lifetimes.md    # 只查一章
EDITION=2021 python3 verify-md.py          # 换 edition 重跑
RUSTCFLAGS=-Zpolonius=off python3 verify-md.py   # 用 NLL 引擎重跑
```

写作时的基线输出：

```
编译通过 162   报错 99   片段(跳过) 253
需人工确认的矛盾：8 处
```

那 8 处**全部是预期内的误报**，脚本无法自动判别，含义分别是：

| 位置 | 为什么不是错误 |
|---|---|
| 01:344 | 断言是"NLL ❌ / Polonius ✅"，脚本默认跑 Polonius |
| 01:408、05:273 | ❌ 标在**被注释掉**的行上（正文写着"取消注释试试"） |
| 02:143、02:170 | 断言限定在**词法生命周期时代（Rust 1.0）**，今天当然能过 |
| 02:231 | 脚本注入的 `v: Vec<i32>` 与该块假定的 `Vec<usize>` 类型不符 |
| 25:251 | ❌ 标在被注释掉的 `Box<dyn Svc>` 行上 |
| A:305 | 断言限定 **edition 2021**，脚本默认 2024 |

**规则：改完课程后跑一遍，矛盾数应当仍是 8。多出来的每一条都要查。**

## 目录

| 案例 | 主题 | 讲解章节 |
|---|---|---|
| 01 | 迭代器失效 | 01, 05 |
| 02 | NLL 的基本功（借用止于最后一次使用） | 07 |
| 03 / 04 | 两阶段借用及其边界 | 05 |
| 05 | NLL problem case #1 | 14 |
| 06 / 07 | NLL problem case #3（match 版 / loop 版） | 14, 16 |
| 08 | 条件重借用 | 14, 16 |
| 09 / 10 | lending iterator（基础形态 / 条件返回形态） | 14 |
| 11 / 12 | 字段分割借用：直接访问 vs 方法访问 | 12, 17 |
| 13 / 14 | 同时可变借用两个元素：索引 vs `split_at_mut` | 12, 18 |
| 15 | 自引用结构 | 13, 17 |
| 16 | 返回局部变量引用（真·悬垂） | 06 |
| 17 | 闭包的不相交捕获（RFC 2229） | 12 |
| 18 / 19 / 20 | 临时值作用域与 2024 edition 的变更 | 12 |
| 21 | 跨 await 持有借用 | 24 |
| 22 / 23 | `thread::spawn` 的 `'static` vs scoped thread | 23 |
| 24 / 25 | `Rc` 不是 `Send`；`let _ = x` 不捕获 | 22, 11 |
| 26 / 27 | `MutexGuard` 跨 await | 25 |
| 28 | 链表收集 `&mut`（NLL 也已改进的老难题） | 14 |

## 关于 `-Zpolonius` 的取值（实测）

```
$ rustc +nightly -Zpolonius=bogus x.rs
error: incorrect value `bogus` for unstable option `polonius`
       - either no value or one of `legacy` (the default), `off`, or `next` was expected
```

⚠️ `rustc +nightly -Z help` 里那行 `polonius=val ... (default: no)` 是**过时的帮助文本**，
不要相信它。以实测为准：不加任何 flag 时，上面那 5 个 ★ 案例都能通过，
说明 **Polonius Alpha 确实是默认开启的**。
