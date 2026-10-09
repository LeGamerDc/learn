# 26 - `unsafe` 不关闭 borrow checker

> 本章目标：搞清楚 `unsafe` 之下**规则并没有消失**，只是从"编译器检查"变成"你保证"。
> 我们会用 **Miri** 实际抓出 UB，并对比 **Stacked Borrows** 和 **Tree Borrows**
> 两个别名模型在同一段代码上给出的**不同判决**。
> 预计用时：3 小时（必须动手跑 Miri）。

---

## 1. `unsafe` 到底解锁了什么

**极其常见的误解**："`unsafe` 关闭了 borrow checker。"

**`unsafe` 只解锁五件事**：

1. 解引用裸指针 `*const T` / `*mut T`
2. 调用 `unsafe fn`
3. 实现 `unsafe trait`（`Send`/`Sync`/`GlobalAlloc` 等）
4. 访问/修改 `static mut`（2024 edition 起已基本禁止，改用 `SyncUnsafeCell`）
5. 访问 `union` 的字段

**不在列表里的**：借用检查、类型检查、生命周期检查、初始化检查——**全部照常**。

```rust
unsafe {
    let a = &mut v[0];
    let b = &mut v[1];        // ❌ E0499 —— unsafe 一点忙都帮不上
    *a += *b;
}
```

> ### `unsafe` 的真实语义
> **"编译器，这段代码的正确性由我证明。我保证它不违反 Rust 的内存模型。"**
>
> 注意是"**不违反**"——`unsafe` **不允许**你违反 Aliasing XOR Mutability，
> 它只是不再帮你检查。用裸指针造出两个别名的 `&mut`，那是 **UB**，
> 即使编译通过、即使跑起来结果正确。

---

## 2. 那么"规则"在 `unsafe` 之下具体是什么

这就是 **别名模型（aliasing model）** 要回答的问题：

> **在裸指针层面，哪些操作序列是合法的？**

Rust **至今没有官方的、最终敲定的内存模型**。目前有两个候选，都由
[Ralf Jung](https://www.ralfj.de/) 领衔，都在 Miri 里实现了：

| 模型 | 提出 | 核心比喻 | Miri 里 |
|---|---|---|---|
| **Stacked Borrows** | 2018 | 每个内存位置有一个**借用栈** | ★ **默认** |
| **Tree Borrows** | 2023（PLDI 2025 论文） | 每个指针是**树**上的节点，有状态机 | `-Zmiri-tree-borrows` |

**两者都是"实验性"的**——Miri 的报错里会明说
`the rules it violated are still experimental`。

### 2.1 Stacked Borrows 的核心

每个内存位置维护一个**栈**，栈里是"被授权访问这个位置的标签（tag）"：

```
    let mut x = 0;                    栈: [ x 的所有权 ]
    let r1 = &mut x;                  栈: [ x, r1 ]         ← r1 压栈
    let p = r1 as *mut i32;           栈: [ x, r1, p ]
    let r2 = unsafe { &mut *p };      栈: [ x, r1, p, r2 ]
    *r1 += 1;                         栈: [ x, r1 ]         ★ 用 r1 → 弹出它上面的所有
    *r2 += 1;                         ❌ r2 已不在栈上 → UB
```

**规则一句话**：**用一个标签访问时，把它上面的所有标签弹出；
如果它本身不在栈上，就是 UB。**

**这直接对应第 05 章的"重借用是栈式嵌套"** ——
Stacked Borrows 就是把那个直觉形式化了。

### 2.2 Tree Borrows 的核心

Tree Borrows 用**树 + 每个节点一个状态机**替代栈：

| 状态 | 含义 |
|---|---|
| `Reserved` | `&mut` 已创建但**还没写过**（对应两阶段借用的"保留"阶段！） |
| `Active` | 已经写过，独占有效 |
| `Frozen` | 只读（`&T` 的状态） |
| `Disabled` | 已失效，再用就是 UB |

**转移规则**取决于访问是 **child access**（通过自己或后代）还是
**foreign access**（通过其它分支）。

Tree Borrows 比 Stacked Borrows **更宽松**——它接受更多合法程序。

---

## 3. 实测：两个模型的判决不同

### 3.1 环境准备

```bash
rustup component add miri --toolchain nightly
cargo new miridemo && cd miridemo
cargo +nightly miri run          # 首次会编译一个 Miri 专用的 std，需要几分钟
```

### 3.2 案例 A：两个模型都判 UB

```rust
fn main() {
    let mut x = 5i32;
    let r1: &mut i32 = &mut x;
    let p = r1 as *mut i32;
    let r2: &mut i32 = unsafe { &mut *p };
    *r1 += 1;          // 用父引用
    *r2 += 1;          // ★ 再用子引用 → UB
    println!("{}", x);
}
```

**普通运行**：`case2: 7`——**看不出任何问题**。

**Miri（Stacked Borrows，默认）**：

```
error: Undefined Behavior: attempting a read access using <7560> at alloc2055[0x0],
       but that tag does not exist in the borrow stack for this location
  --> src/main.rs:14:5
14 |     *r2 += 1;
   |     ^^^^^^^^ this error occurs as part of an access at alloc2055[0x0..0x4]
help: <7560> was created by a Unique retag at offsets [0x0..0x4]
12 |     let r2: &mut i32 = unsafe { &mut *p };
help: <7560> was later invalidated at offsets [0x0..0x4] by a write access
13 |     *r1 += 1;
```

**Miri（Tree Borrows）**：

```
error: Undefined Behavior: read access through <7014> at alloc2020[0x0] is forbidden
   = help: the accessed tag <7014> has state Disabled which forbids this child read access
help: the accessed tag <7014> was created here, in the initial state Reserved
help: the accessed tag <7014> later transitioned to Disabled due to a foreign write access
```

**★ 注意 Miri 诊断的质量**：它告诉你**标签在哪创建、在哪失效、因为什么操作**——
比编译器的借用错误还详细。

### 3.3 案例 B：★ 两个模型判决**不同**

```rust
fn main() {
    let mut x = 0u8;
    let p = &mut x as *mut u8;
    let r = unsafe { &mut *p };
    let v = x;            // ★ 通过父级（x 本身）做一次只读
    *r = 1;               // ★ 再通过 r 写
    println!("v={} x={}", v, x);
}
```

**实测结果**：

| 模型 | 判决 |
|---|---|
| **Stacked Borrows**（默认） | ❌ **UB**：`attempting a write access using <589> ... but that tag does not exist in the borrow stack` |
| **Tree Borrows** | ✅ **通过**：输出 `v=0 x=1` |

**为什么不同**：

- **Stacked Borrows**：任何对父级的访问（哪怕只读）都会把 `r` 弹出栈 → 之后用 `r` 就是 UB
- **Tree Borrows**：`r` 创建时处于 `Reserved` 状态，**foreign read 不会让它失效**
  （只有 foreign write 才会）→ 之后写 `r` 是合法的

> ### ★ 这个差异非常重要
> `Reserved` 状态正是**两阶段借用**（第 05 章 §3）在别名模型层面的对应物。
> Stacked Borrows 没有这个概念，所以它拒绝了一些真实代码里常见的合法模式——
> **这正是社区转向 Tree Borrows 的主要动因之一**。
>
> **实用建议**：**两个模型都跑。** 通过 SB 的一定通过 TB；
> 只通过 TB 的说明你依赖了 SB 不允许的模式——目前是灰色地带。

---

## 4. Miri 实用手册

### 4.1 基本用法

```bash
cargo +nightly miri run              # 跑 main
cargo +nightly miri test             # ★ 跑测试（最常用）
cargo +nightly miri test -- name     # 跑指定测试
```

### 4.2 常用 flag

```bash
# 换别名模型
MIRIFLAGS=-Zmiri-tree-borrows cargo +nightly miri test

# 检查内存泄漏（默认开启；关掉用 -Zmiri-ignore-leaks）
MIRIFLAGS=-Zmiri-ignore-leaks cargo +nightly miri test

# 用不同的随机种子跑多次（并发调度是随机的）
for seed in 0 1 2 3 4; do
  MIRIFLAGS="-Zmiri-seed=$seed" cargo +nightly miri test
done

# 完整 backtrace
MIRIFLAGS=-Zmiri-backtrace=full cargo +nightly miri test

# 允许调用 FFI（默认禁止）—— 通常意味着这部分测不了
MIRIFLAGS=-Zmiri-disable-isolation cargo +nightly miri test   # 允许访问时间/文件系统
```

### 4.3 Miri 能抓什么

| 能抓 ✅ | 抓不了 ❌ |
|---|---|
| 别名规则违反（SB / TB） | 没被测试覆盖到的代码路径 |
| 越界访问 | 真实的并发时序（只能靠 seed 采样） |
| use-after-free / double free | 性能问题 |
| 读未初始化内存 | FFI 里的 C 代码 |
| 未对齐访问 | 逻辑 bug |
| 数据竞争（有限） | 平台特定的 UB |
| 内存泄漏 | |
| 无效的 `transmute` | |

> ### ★ Miri 的根本局限
> **Miri 是一个解释器，它只检查"实际执行到的路径"。**
> 所以它的效果**完全取决于你的测试覆盖率**。
>
> 写 `unsafe` 代码时，测试覆盖率不是可选项，是**安全要求**。

### 4.4 速度

Miri 大约比原生执行慢 **50–400 倍**。实践：
- 单独跑一个 `cargo miri test` 的 CI job
- 用 `#[cfg(miri)]` 跳过太慢的测试（比如大数据量的）
- 用 `#[cfg(not(miri))]` 标记依赖 FFI 的测试

```rust
#[test]
fn big_stress_test() {
    let n = if cfg!(miri) { 100 } else { 1_000_000 };
    // ...
}
```

---

## 5. 写 `unsafe` 的纪律

### 5.1 安全契约文档

```rust
/// 把 slice 分成两个不相交的可变切片。
///
/// # Safety
///
/// 调用方必须保证 `mid <= self.len()`。
pub unsafe fn split_at_mut_unchecked(&mut self, mid: usize) -> (&mut [T], &mut [T]) {
    let len = self.len();
    let ptr = self.as_mut_ptr();
    // SAFETY: 调用方保证了 mid <= len；两个切片的地址范围 [0,mid) 和 [mid,len)
    //         不相交，因此同时存在两个 &mut 不违反别名规则。
    unsafe {
        (
            std::slice::from_raw_parts_mut(ptr, mid),
            std::slice::from_raw_parts_mut(ptr.add(mid), len - mid),
        )
    }
}
```

**两种注释各有分工**：

| 注释 | 位置 | 内容 |
|---|---|---|
| `/// # Safety` | `unsafe fn` 的文档 | **调用方**必须保证什么 |
| `// SAFETY:` | 每个 `unsafe {}` 块之前 | **为什么**这里是安全的 |

**用 lint 强制**：

```rust
#![deny(unsafe_op_in_unsafe_fn)]          // unsafe fn 内部也要写 unsafe 块
#![warn(clippy::undocumented_unsafe_blocks)]   // 每个 unsafe 块都要 SAFETY 注释
#![warn(clippy::missing_safety_doc)]           // 每个 unsafe fn 都要 # Safety 文档
```

> **`unsafe_op_in_unsafe_fn` 在 2024 edition 是默认 deny 的**——
> 也就是说 `unsafe fn` 的函数体不再自动是 unsafe 块，你必须显式写。
> 这是个好变化：它逼你标出**具体哪一行**是危险操作。

### 5.2 最小化 `unsafe` 的表面积

```rust
// ❌ 整个函数 unsafe
pub unsafe fn process(p: *mut u8, len: usize) { ... }

// ✅ unsafe 只在最内层，外面包一个安全 API
pub fn process(data: &mut [u8]) {
    let (ptr, len) = (data.as_mut_ptr(), data.len());
    // SAFETY: ...
    unsafe { process_raw(ptr, len) }
}
```

### 5.3 型变与 dropck（第 09 章）

写 `unsafe` 容器时必做的两件事：

```rust
use std::ptr::NonNull;
use std::marker::PhantomData;

pub struct MyVec<T> {
    ptr: NonNull<T>,              // ★ 不用 *mut T：NonNull 是协变的且非空
    len: usize,
    cap: usize,
    _marker: PhantomData<T>,      // ★ 声明"我拥有 T"，让 dropck 和型变正确
}
```

忘了 `PhantomData<T>` 的后果：
- 型变不对（`*mut T` 是不变的，但 `MyVec<T>` 语义上应该协变）
- dropck 不知道你会 drop 里面的 `T`

### 5.4 `unsafe impl Send/Sync`（第 22 章 §6）

```rust
// SAFETY: MyVec 独占它指向的内存，移动 MyVec 会连同所有权一起移动。
unsafe impl<T: Send> Send for MyVec<T> {}      // ★ 别忘了 T: Send
// SAFETY: 所有 &self 方法都只读，且没有内部可变性。
unsafe impl<T: Sync> Sync for MyVec<T> {}
```

### 5.5 检查清单

写完 `unsafe` 代码，逐条过：

- [ ] 每个 `unsafe fn` 都有 `# Safety` 文档
- [ ] 每个 `unsafe {}` 块都有 `// SAFETY:` 注释
- [ ] `unsafe impl Send/Sync` 的泛型 bound 写对了
- [ ] 用了 `NonNull` 而非 `*mut`（如果需要协变）
- [ ] 加了 `PhantomData<T>`（如果拥有 T）
- [ ] `cargo +nightly miri test` 通过
- [ ] `MIRIFLAGS=-Zmiri-tree-borrows cargo +nightly miri test` 通过
- [ ] 多个 `-Zmiri-seed` 都通过（如果有并发）
- [ ] 测试覆盖了所有 `unsafe` 路径（★ Miri 只测执行到的）
- [ ] **想过一遍：能不能用安全代码 / 现成的 crate 实现？**

---

## 6. 编译器已经帮你抓的一些

即使不跑 Miri，rustc 也有几个默认开启的相关 lint：

```rust
let x = 5i32;
let p = &x as *const i32 as *mut i32;
unsafe { *p = 6; }
```

**实测**：

```
error: assigning to `&T` is undefined behavior, consider using an `UnsafeCell`
  = note: `#[deny(invalid_reference_casting)]` on by default
```

**其它有用的 lint**：

| lint | 作用 |
|---|---|
| `invalid_reference_casting` | `&T` → `*mut T` 后写入（deny by default） |
| `dropping_references` | `drop(&x)`（warn by default，第 11 章第 3 条） |
| `unsafe_op_in_unsafe_fn` | 2024 edition 默认 deny |
| `clippy::not_unsafe_ptr_arg_deref` | 公开安全函数解引用了参数里的裸指针 |
| `clippy::mut_from_ref` | 从 `&self` 返回 `&mut`（内部可变性之外通常是 unsound 的信号） |

---

## 7. 动手实验

### 实验 1：抓一个 UB（★ 必做）

```bash
rustup component add miri --toolchain nightly
mkdir -p /tmp/miridemo && cd /tmp/miridemo && cargo init --name miridemo
cat > src/main.rs <<'RSEOF'
fn main() {
    let mut x = 5i32;
    let r1: &mut i32 = &mut x;
    let p = r1 as *mut i32;
    let r2: &mut i32 = unsafe { &mut *p };
    *r1 += 1;
    *r2 += 1;
    println!("{}", x);
}
RSEOF
cargo run                                              # 正常输出 7
cargo +nightly miri run                                # ❌ UB
MIRIFLAGS=-Zmiri-tree-borrows cargo +nightly miri run  # ❌ UB（用不同的话术）
```

**任务**：把两个模型的完整报错抄下来，对比它们的**术语差别**
（borrow stack vs tag state machine）。

### 实验 2：找出两个模型判决不同的例子（★ 最有价值）

```rust
fn main() {
    let mut x = 0u8;
    let p = &mut x as *mut u8;
    let r = unsafe { &mut *p };
    let v = x;            // 通过父级只读
    *r = 1;               // 再通过 r 写
    println!("v={} x={}", v, x);
}
```

**实测**：SB ❌ UB / TB ✅ 通过。

**任务**：
1. 亲手验证
2. 解释为什么（提示：`Reserved` 状态 + foreign read）
3. **思考**：如果你的库依赖这个模式，现在能不能发布？

### 实验 3：给 `split_at_mut` 写一个 unsafe 实现并验证

```rust
pub fn my_split_at_mut<T>(s: &mut [T], mid: usize) -> (&mut [T], &mut [T]) {
    let len = s.len();
    let ptr = s.as_mut_ptr();
    assert!(mid <= len);
    // SAFETY: 写在这里
    unsafe {
        (std::slice::from_raw_parts_mut(ptr, mid),
         std::slice::from_raw_parts_mut(ptr.add(mid), len - mid))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn works() {
        let mut v = vec![1, 2, 3, 4];
        let (a, b) = my_split_at_mut(&mut v, 2);
        a[0] += b[0];
        assert_eq!(v, vec![4, 2, 3, 4]);
    }
    #[test]
    fn edge_cases() {
        let mut v: Vec<i32> = vec![];
        let (a, b) = my_split_at_mut(&mut v, 0);
        assert!(a.is_empty() && b.is_empty());
    }
}
```

```bash
cargo +nightly miri test
```

**然后故意写错**（把 `assert!(mid <= len)` 删掉，测试里传 `mid = 10`），
看 Miri 报什么。

### 实验 4：Miri 的覆盖率局限

```rust
pub fn maybe_ub(flag: bool) {
    let mut x = 0;
    let r1 = &mut x;
    let p = r1 as *mut i32;
    *r1 = 1;
    if flag {
        unsafe { *p = 2; }        // ★ 只有 flag=true 时才是 UB
    }
}

#[test] fn t() { maybe_ub(false); }      // ← Miri 会说"没问题"
```

**任务**：跑 `cargo miri test`，确认它通过。然后加一个 `maybe_ub(true)` 的测试，再跑。
**结论：Miri 的价值上限 = 你的测试覆盖率。**

---

## 8. 本章检查清单

- [ ] **知道 `unsafe` 只解锁五件事，且不包括借用检查**
- [ ] 知道 `unsafe` 是"我保证不违反规则"，不是"规则不适用"
- [ ] 能说出 Stacked Borrows 的核心规则（借用栈，用一个标签就弹掉它上面的）
- [ ] 知道 Stacked Borrows 就是"重借用是栈式嵌套"的形式化
- [ ] 能说出 Tree Borrows 的四个状态（`Reserved`/`Active`/`Frozen`/`Disabled`）
- [ ] **知道 `Reserved` 对应两阶段借用**
- [ ] **亲手跑过 Miri，见过两个模型判决不同的例子**
- [ ] 会用 `cargo miri test` 和主要的 `MIRIFLAGS`
- [ ] 知道 Miri 的根本局限（只检查执行到的路径）
- [ ] 知道 `# Safety` 和 `// SAFETY:` 两种注释的分工
- [ ] 知道写 unsafe 容器要用 `NonNull` + `PhantomData`
- [ ] 知道 2024 edition 的 `unsafe_op_in_unsafe_fn` 默认 deny

---

## 9. 常见坑

| 误解 / 现象 | 事实 / 处方 |
|---|---|
| "`unsafe` 能关掉借用检查" | 不能。只解锁五件事 |
| "跑起来对就没问题" | UB 可能在换编译器版本 / 开优化 / 换平台后才炸。**必须跑 Miri** |
| "只有 `unsafe` 块里才可能 UB" | `unsafe` 块的**影响**可以扩散到整个模块。一个 unsound 的 API 会让安全代码触发 UB |
| Miri 说通过就没问题了 | 只覆盖了你测到的路径。**提高测试覆盖率** |
| 只跑了默认的 Stacked Borrows | 也跑 `-Zmiri-tree-borrows`。两者判决可能不同 |
| `&T as *const T as *mut T` 后写入 | rustc 直接 deny（`invalid_reference_casting`）。用 `UnsafeCell` |
| `unsafe impl<T> Send` 忘了 bound | **soundness bug** |
| 用 `*mut T` 导致容器不协变 | 换 `NonNull<T>` |
| 忘了 `PhantomData<T>` | dropck 和型变都会不对 |
| Miri 太慢 | `#[cfg(miri)]` 缩小数据规模；单独 CI job |
| Miri 报 "unsupported operation" | 涉及 FFI 或系统调用。`-Zmiri-disable-isolation` 或 `#[cfg(not(miri))]` 跳过 |

---

下一章：[27 - 理论边界与横向对比](27-limits-and-comparison.md)
