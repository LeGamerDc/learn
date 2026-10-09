# 16 - Polonius Alpha 现状实测（2026-08）

> 本章目标：给你一份**可复现的、有日期的**现状报告——
> Polonius Alpha 今天到底能做什么、不能做什么、多快、什么时候稳定、你现在该怎么做。
> 本章所有数据都在 `rustc 1.100.0-nightly (8fa1c96cf 2026-08-17)` 上实测。
> 预计用时：2 小时。

> ### ⚠️ 时效声明
> 这是全课程**时效性最强**的一章。写于 **2026-08-18**，Polonius Alpha 在 nightly 默认开启
> 刚好两周（2026-08-04）。**读到这一章时请先用第 8 节的命令自己复测一遍。**

---

## 1. 一页纸现状

| 项 | 状态（2026-08-18 实测/核实） |
|---|---|
| **在哪** | nightly，**默认开启**（2026-08-04 起） |
| **怎么关** | `-Zpolonius=off`；或 `RUSTFLAGS="-Zpolonius=off"`；或 `.cargo/config.toml` |
| **取值** | `legacy`（默认）、`off`、`next`（实测三者中只有 `off` 行为不同） |
| **stable 上有吗** | ❌ 没有。stable 1.96 / 1.97 仍是 NLL |
| **稳定化目标** | **2026 年底前** |
| **负责人 / 团队** | @lqd / rust-lang types-team（Niko Matsakis 开的 issue） |
| **项目目标编号** | rust-project-goals #118「Stabilize and model Polonius Alpha」，2026 **Flagship Goal** |
| **剩余任务** | 修最后一个已知 soundness 问题、扩测试覆盖、在 a-mir-formality 里建形式化模型、性能验证、写稳定化报告 |
| **实现方式** | rustc 原生的 `(origin, point)` 图可达性，**不跑 datalog 引擎** |
| **和完整 Polonius 的关系** | Alpha 是**子集**（官方原话："less powerful than we hoped"） |
| **Alpha 之后** | 官方明确：**稳定化后不再继续 Polonius 的功能开发**，剩余工作转到「The Borrow Checker Within」（第 17 章） |
| **兼容性** | **超集**：接受 NLL 接受的一切，外加更多。不会拒绝现有代码 |

---

## 2. `-Zpolonius` 的三个取值（实测）

```bash
$ rustc +nightly -Zpolonius=bogus x.rs
error: incorrect value `bogus` for unstable option `polonius`
       - either no value or one of `legacy` (the default), `off`, or `next` was expected
```

⚠️ **注意两处"文档陷阱"**：

1. `rustc +nightly -Z help` 里那行
   ```
   polonius=val -- enable polonius-based borrow-checker (default: no)
   ```
   **是过时的帮助文本**。实测证明默认是开的。

2. 错误信息说 `legacy` 是默认值，但历史上 `legacy` 指的是"旧的 datalog 实现"。
   **实测三者的行为**（用 lab 的 5 个 ★ 案例）：

| 取值 | 5 个 ★ 案例 | 结论 |
|---|---|---|
| （不加 flag） | 全部 ✅ | Polonius Alpha 生效 |
| `-Zpolonius=legacy` | 全部 ✅ | 同上 |
| `-Zpolonius=next` | 全部 ✅ | 同上 |
| **`-Zpolonius=off`** | **全部 ❌** | 退回 NLL |

**实用结论**：**只有 `off` 和"非 off"两种状态**。

### 2.1 怎么关掉（如果你需要）

```bash
# 单次
rustc +nightly -Zpolonius=off foo.rs

# cargo
RUSTFLAGS="-Zpolonius=off" cargo +nightly build
```

```toml
# .cargo/config.toml
[build]
rustflags = ["-Zpolonius=off"]
```

**什么时候需要关**：
- 怀疑遇到 Polonius 的 bug（对照一下）
- 想确认代码在 stable 上能不能过（★ **最常用的理由**）
- 遇到编译时间回归

---

## 3. 能力边界：完整实测表

**5 个新增接受**（`lab/run.sh` 的 ★ 案例）：

| 案例 | 形态 | NLL | Polonius |
|---|---|---|---|
| 05 | `match v.first() { Some(x)=>x, None=>{ v.push(..); v.first().unwrap() } }` | ❌ E0502 | ✅ |
| 06 | `HashMap` get-or-insert（`match` 版），**返回借用** | ❌ E0499 | ✅ |
| 07 | 同上的 `loop` 版 | ❌ E0499 | ✅ |
| 08 | `let b = &mut *a; if c { b } else { a }` | ❌ E0499 | ✅ |
| 10 | lending iterator + 条件返回 | ❌ E0499 | ✅ |

**它们的共同骨架**（第 14 章 §3）：

```rust
fn skeleton(x: &mut T) -> &mut U {
    let borrow = x.something_mut();
    if cond(&borrow) { borrow } else { x.other_mut() }
}
```

**9 个仍然拒绝**：

| 案例 | 原因分类 | 会被修好吗 |
|---|---|---|
| 01 迭代器失效 | 真·别名冲突 | ❌ 永远不会（它是对的） |
| 16 返回局部变量引用 | 真·悬垂 | ❌ 永远不会 |
| 22 `spawn` 的 `'static` | 真·约束 | ❌ 永远不会 |
| 24 `Rc` 不是 `Send` | 真·约束 | ❌ 永远不会 |
| 26 `MutexGuard` 跨 await | 真·约束 | ❌ 永远不会 |
| 04 两阶段借用边界 | 规则边界 | 可能重新审视 |
| **12 字段分割（经方法）** | **签名表达力** | **需要 view types**（第 17 章，无时间表） |
| **13 `&mut v[0]` + `&mut v[1]`** | **签名表达力** | 同上 |
| **15 自引用结构** | **签名表达力** | **需要 internal references**（第 17 章，无时间表） |

> ### ★ 最重要的一句话
> **Polonius Alpha 解决的是"分析精度"，不是"表达力"。**
>
> 你日常最常抱怨的三件事（方法借走整个 self、不能同时借两个元素、写不了自引用），
> **它一件都没解决**，而且短期内也不会。

---

## 4. 性能：本课程的实测

### 4.1 官方数据

对 crates.io 下载量前 10000 的 crate 做了测试：
- "relatively few 'significant' regressions"
- **最坏情况约 2–3× 的借用检查耗时**
- 团队认为可以接受

### 4.2 本课程的实测

**测试载荷**：合成的 12800 行代码，800 个函数，每个含 `HashMap` 的
get-or-insert 循环 + 二次遍历（**刻意做成借用密集型**）。

```bash
rustc +nightly --edition 2024 --crate-type=lib --emit=metadata -Ztime-passes [FLAG] big.rs
```

**结果**（5 次取最小值，`rustc 1.100.0-nightly`，Apple Silicon）：

| | `MIR_borrow_checking` | 总编译时间 |
|---|---|---|
| `-Zpolonius=off`（NLL） | **0.178 s** | 0.429 s |
| 默认（Polonius Alpha） | **0.193 s** | 0.445 s |
| **差异** | **+8.4%** | **+3.7%** |

**解读**：
- 在这个**刻意做得借用密集**的载荷上，借用检查慢了不到 10%
- 换算到整体编译时间是 **+3.7%**——而真实项目里借用检查通常只占总时间的 5–15%，
  且 release 构建的大头是 LLVM，所以**实际影响会更小**
- 但**最坏情况仍可能 2–3×**（官方数据），如果你的项目里有超大函数（几千行的 `match`、
  生成代码）要留意

### 4.3 自己测

```bash
cd your-project
# NLL
RUSTFLAGS="-Zpolonius=off -Ztime-passes" cargo +nightly build 2>&1 | grep MIR_borrow_checking
# Polonius
RUSTFLAGS="-Ztime-passes" cargo +nightly build 2>&1 | grep MIR_borrow_checking
```

---

## 5. 你现在该怎么做（决策表）

| 你的处境 | 建议 |
|---|---|
| **写生产代码，stable 工具链** | 照常写。遇到 5 个 ★ 形态时用第 18 章的手法绕开。**不要**为了它切 nightly |
| **写生产代码，已经在 nightly** | ⚠️ **不要依赖 Polonius 特有的接受**。稳定化前 API 和行为都可能变，且 CI 上别人可能用 stable |
| **写库，要发到 crates.io** | ★ **必须**用 stable 验证。`cargo +stable check` 加进 CI |
| **教学 / 学习** | 用 nightly，并**始终**用 `-Zpolonius=off` 对照，理解两代的差别 |
| **想帮忙** | 在自己的项目上跑 nightly，遇到问题去 [rust-lang/rust](https://github.com/rust-lang/rust/issues) 报 issue 并标 `A-polonius`。这正是官方现在最需要的 |
| **在评估要不要用 Rust** | 这次换代**不改变**任何设计权衡。第 03 章的取舍分析仍然完全适用 |

### 5.1 一个实用的 CI 配置

如果你想现在就享受 Polonius 但保持 stable 兼容：

```yaml
# .github/workflows/ci.yml
jobs:
  stable-check:
    steps:
      - run: cargo +stable check --all-targets   # ★ 这个必须过
  polonius-check:
    continue-on-error: true                      # 允许失败，只作参考
    steps:
      - run: cargo +nightly check --all-targets
```

### 5.2 稳定化之后你能做什么

**这不是"以后可以随便写"**。稳定化只是让 5 个 ★ 形态从"要绕"变成"直接写"。
典型的收益：

```rust
// 今天（stable）：必须用 entry API 或 contains_key 预探测
pub fn get_or_default<'a>(m: &'a mut HashMap<u32, Vec<u32>>, k: u32) -> &'a mut Vec<u32> {
    m.entry(k).or_default()
}

// 稳定化后：可以直接写自然的形式（对自定义容器尤其有用，因为它们往往没有 entry API）
pub fn get_or_default<'a>(m: &'a mut MyMap, k: u32) -> &'a mut Vec<u32> {
    match m.get_mut(k) {
        Some(v) => v,
        None => { m.insert(k, vec![]); m.get_mut(k).unwrap() }
    }
}
```

★ **对库作者影响最大**：以前为了绕开这个限制，你必须给自己的容器设计 `entry` 这样的
"打包 API"。稳定化之后，用户可以直接用自然写法，你的 API 表面可以更小。

---

## 6. 已知风险

| 风险 | 说明 |
|---|---|
| **仍有一个已知 soundness 问题** | 项目目标里明确列为剩余任务。**这是不要在生产环境依赖它的首要理由** |
| **形式化模型还没建完** | a-mir-formality 里的建模是稳定化前置条件 |
| **Alpha ≠ 完整 Polonius** | 有些原始 Polonius 能过的程序 Alpha 过不了。别拿论文里的例子当承诺 |
| **诊断信息可能变** | 同一段代码在两个引擎下的错误信息措辞/span 可能不同 |
| **编译时间** | 最坏 2–3×。大函数要留意 |
| **稳定化时间可能滑** | "年底前"是目标不是承诺。NLL 从 RFC 到完全落地用了 5 年（第 02 章） |

---

## 7. 稳定化路线的历史参照

**NLL 的稳定化用了 5 年**（第 02 章）：

| 阶段 | NLL | Polonius Alpha（推测对照） |
|---|---|---|
| RFC / 立项 | 2017-08（RFC 2094） | 2018（项目启动） |
| nightly 可用 | 2018 上半年（`-Znll`） | 2024–2025（`-Zpolonius=next`） |
| **nightly 默认开启** | 2018 下半年 | **2026-08-04** ← 现在在这里 |
| 新 edition 稳定 | 1.31 / 2018 edition（2018-12） | 目标 2026 底 |
| 回移到旧 edition | 1.36（2019-07） | ？ |
| 旧实现彻底删除 | 1.63（2022-08） | ？ |

**注意 NLL 的一个重要差别**：NLL 需要 edition 隔离，因为它**改变了行为**（虽然是放宽）。
Polonius Alpha 是**纯超集**，理论上不需要 edition 隔离——它只接受更多代码。

---

## 8. 动手实验

### 实验 1：复测本章所有结论（★ 必做）

```bash
cd lab
rustc +nightly --version           # 记下你的版本和日期
./run.sh                           # 跑完整对照表
```

**核对**：
- ★ 案例是不是还是 5 个？
- 「两者都拒绝」是不是还是 9 个？
- 有没有出现「⚠ Polonius 回归」？（如果有，那是个 bug，请上报）

### 实验 2：三个 flag 值的行为

```bash
cd lab
for mode in "" "-Zpolonius=off" "-Zpolonius=legacy" "-Zpolonius=next"; do
  n=$(rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir out $mode \
      cases/08-conditional-reborrow.rs 2>&1 | grep -c "^error")
  printf "%-22s errors=%s\n" "${mode:-<默认>}" "$n"
done
```

### 实验 3：在自己的项目上测

```bash
cd your-project
cargo +nightly check 2>&1 | tail -5
RUSTFLAGS="-Zpolonius=off" cargo +nightly check 2>&1 | tail -5
```

**如果两者结果不同**，说明你的代码里有 ★ 形态。**把它找出来**——
那正是你以前"绕过"的地方，现在可以简化了（等稳定之后）。

### 实验 4：性能对比

```bash
# 用第 4.2 节的方法生成 big.rs，或直接用你的项目
for f in "-Zpolonius=off" ""; do
  echo -n "${f:-默认}: "
  for i in 1 2 3 4 5; do
    rustc +nightly --edition 2024 --crate-type=lib --emit=metadata --out-dir /tmp/o \
          -Ztime-passes $f big.rs 2>&1 | awk '/MIR_borrow_checking/{print $2}'
  done | tr -d ';' | sort -n | head -1
done
```

---

## 9. 本章检查清单

- [ ] 知道 Polonius Alpha 的**准确状态**：nightly 默认开启，目标 2026 底稳定
- [ ] 知道 `-Zpolonius` 只有 `off` / 非 `off` 两种实际行为
- [ ] 知道 `-Z help` 的那行帮助文本是过时的
- [ ] **能说出 5 个新增接受的形态和它们的共同骨架**
- [ ] **能说出 3 个"表达力"类的拒绝，且知道 Polonius 不解决它们**
- [ ] 知道 Alpha ≠ 完整 Polonius，且后续不再开发
- [ ] 知道还有一个已知 soundness 问题未修
- [ ] 知道自己该按哪一行决策表行动
- [ ] 跑过 `lab/run.sh` 复测

---

## 10. 常见坑

| 误解 | 事实 |
|---|---|
| "切到 nightly 就能享受 Polonius" | 能，但**稳定化前不要在生产/库代码里依赖**，且有一个已知 soundness 问题 |
| "Polonius 稳定后借用错误就少一半了" | 只少 5 类特定形态。字段粒度、自引用、索引这三大痛点完全没动 |
| "Polonius 会让编译变慢很多" | 本课程实测 +8.4%（借用检查）/ +3.7%（总时间）。官方最坏 2–3× |
| "Polonius 可能拒绝我现有的代码" | 不会。它是 NLL 的**超集** |
| "`-Zpolonius=next` 比默认更强" | 实测行为相同 |
| "网上说 Polonius 遥遥无期" | 那是 2023 年之前的说法。2026-08 已经 nightly 默认开启了 |
| "既然要稳定了，我现在写代码可以按 Polonius 来" | ⚠️ 如果你的 CI/用户在 stable 上，会直接编译失败 |

---

下一章：[17 - 未来：The Borrow Checker Within](17-borrow-checker-within.md)
