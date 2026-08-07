"""
08 章：协同与爆发的控制

割草类的 DPS 通常是几个维度**相乘**：

    DPS = 攻击力 × 攻速 × 暴击期望 × 弹幕数量

四个维度各 +50%，总 DPS 不是 +200%，是 **×5.06**。
**这就是"数值膨胀爽感"的全部数学。**

但本模型最重要的发现不是这个，而是下面这条 —— 它推翻了一个很常见的直觉：

    **如果同一个维度内部也用乘法叠加，总倍数只取决于"你拿了几件道具"，
      和"你把它们分配到哪些维度"完全无关。**

        ∏_d (1+s)^(k_d) = (1+s)^(Σ k_d) = (1+s)^N

    ⇒ **纯乘法叠加会让构筑决策彻底失效。** 玩家怎么选都一样。

本模型做三件事：
  ① 量化"维度间相乘"的爆炸速度
  ② 用"最优分配 / 最差分配"衡量**分配决策值不值钱**，对比五种同维叠加规则
  ③ 那爆发感从哪来？—— 不是从叠加规则来的。接回第 06、07 章的健康带
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
import run_model as R

use_cjk_font()

DIMS = ["攻击力", "攻速", "暴击期望", "弹幕数量"]
N_DIM = len(DIMS)
PICKS = 8              # 一局平均拿到 8 件道具
STEP = 0.25            # 每件道具给该维度 +25%
N_PLAYERS = 20000

# ============================================================
# ① 维度间相乘：为什么 +50% 会变成 ×5
# ============================================================
print("=== ① 维度间相乘的爆炸速度 ===\n")
print(f"{'每维提升':>10}{'加法直觉（1+4x）':>18}{'实际（(1+x)^4）':>18}{'差距':>10}")
print("-" * 58)
for x in (0.10, 0.25, 0.50, 0.75, 1.00):
    naive, real = 1 + N_DIM * x, (1 + x) ** N_DIM
    print(f"{x:>10.0%}{naive:>18.2f}{real:>18.2f}{real/naive:>10.2f}×")

print(f"""
读法
----
**这是"数值膨胀"的全部数学。** 四个维度各 +50%，
直觉说 1+4×0.5 = 3 倍，实际是 1.5^4 = {1.5**4:.2f} 倍 —— **差了 {1.5**4/3:.2f} 倍**。

  ✅ **正面**：这就是割草类"屏幕炸开"的爽感来源。
     玩家感觉到的不是"我强了 3 倍"，是"我强了 5 倍"，而且每加一件都在加速。
     **在 IAA 里这尤其值钱 —— 爆发是分享和口碑的触发点，而分享是最便宜的量。**

  ⚠️ **反面**：手调时你在一个维度上试参数，感觉"+25% 不多"，
     四个维度一起动的时候实际是 {(1.25**4):.2f} 倍。**跨维度的参数不能分开调。**

⚠️ **维度之间的相乘你改不掉** —— DPS 的物理含义就是几个量的乘积。
   所以你唯一的抓手是：**管住同一个维度内部的叠加方式。** 那正是第 ② 段的主题。
""")


# ============================================================
# ② 同维叠加规则决定"分配决策值不值钱"
# ============================================================
def dim_mult(k, mode):
    """k 件道具堆在同一个维度上，这个维度的倍数"""
    if mode == "同维乘法":
        return (1 + STEP) ** k
    if mode == "同维加法":
        return 1 + STEP * k
    if mode == "递减收益":                      # 第 n 件只有 0.7^(n-1) 的效果
        return 1 + STEP * sum(0.7 ** i for i in range(k))
    if mode == "硬上限":                        # 每维最多吃 3 件
        return 1 + STEP * min(k, 3)
    if mode == "软上限":                        # 饱和公式 1 + M·k/(k+K)
        M, K = STEP * 6, 3.0
        return 1 + M * k / (k + K)
    raise ValueError(mode)


MODES = ["同维乘法", "同维加法", "递减收益", "硬上限", "软上限"]


def total_of(counts, mode):
    out = 1.0
    for k in counts:
        out *= dim_mult(int(k), mode)
    return out


def best_worst(mode, n=PICKS):
    """最优分配（均分）与最差分配（全堆一维）的总倍数"""
    even = [n // N_DIM + (1 if i < n % N_DIM else 0) for i in range(N_DIM)]
    pile = [n] + [0] * (N_DIM - 1)
    return total_of(even, mode), total_of(pile, mode)


rng = np.random.default_rng(5)
counts_rand = rng.multinomial(PICKS, [1 / N_DIM] * N_DIM, size=N_PLAYERS)

print("=== ② 同维叠加规则：分配决策值不值钱 ===\n")
print(f"（每局 {PICKS} 件道具落到 {N_DIM} 个维度，每件给该维度 +{STEP:.0%}）\n")
print(f"{'规则':<12}{'均分总倍数':>12}{'全堆一维':>11}{'决策价值':>10}"
      f"{'随机分配中位':>14}   判断")
print("-" * 82)

res = {}
for mode in MODES:
    ev, pl = best_worst(mode)
    mults = np.array([total_of(c, mode) for c in counts_rand])
    res[mode] = mults
    dv = ev / pl
    if dv < 1.05:
        note = "★ 决策完全失效"
    elif dv < 1.8:
        note = "决策有一点分量"
    else:
        note = "← 决策很有分量"
    print(f"{mode:<12}{ev:>12.2f}{pl:>11.2f}{dv:>10.2f}×"
          f"{np.median(mults):>14.2f}   {note}")

ev_m, pl_m = best_worst("同维乘法")
print(f"""
读法 —— **本章最重要的发现**
-----------------------------
**"决策价值" = 最优分配的总倍数 ÷ 最差分配的总倍数。**
它回答的是："玩家把道具分配对了，能强多少？"如果是 1.0×，**那分配根本不重要。**

  ⚠️ **同维乘法的决策价值恰好是 {ev_m/pl_m:.2f}×** —— 不是接近 1，是**精确等于 1**。

     这不是巧合，是恒等式：
         ∏_d (1+s)^(k_d) = (1+s)^(Σ k_d) = (1+s)^N
     **总倍数只取决于你拿了几件，和怎么分配完全无关。**

     ⇒ **纯乘法叠加会彻底消灭构筑决策。**
       玩家的"三选一"变成了"随便点，反正一样" ——
       这是第 07 章说的"构筑系统是装饰品"的另一种死法，而且更隐蔽，
       因为**数值看起来一直在涨，很爽，只是选择没有意义了。**

  · 同维加法   决策价值 {best_worst('同维加法')[0]/best_worst('同维加法')[1]:.2f}× —— 有分量了。
               背后是 AM-GM 不等式：∏(1+s·k_d) 在均分时最大。
  · 递减收益   {best_worst('递减收益')[0]/best_worst('递减收益')[1]:.2f}×
  · 硬上限     {best_worst('硬上限')[0]/best_worst('硬上限')[1]:.2f}×
  · 软上限     {best_worst('软上限')[0]/best_worst('软上限')[1]:.2f}×  ← 最高

⇒ **规律：同维函数的"凹性"越强，分配决策越值钱。**
  乘法（在对数尺度上是线性的）凹性为零 → 决策价值为 1。
  软上限凹性最强 → 决策价值最高。

⇒ **而且软上限不只是个刹车，它还是个引导。**
  它让"雨露均沾"自动成为最优解，**你不需要写任何规则去强制玩家均衡发展。**
""")

# ============================================================
# ③ 那爆发感从哪来？
# ============================================================
print("=== ③ 爆发感不是从叠加规则来的 ===\n")

# 真实的一局：道具数量有方差（运气），且可能触发协同
SYN_P, SYN_BONUS = 0.13, 1.6      # 13% 的局触发协同（承第 07 章），触发时 ×1.6


def realistic(mode, n=N_PLAYERS):
    picks = rng.poisson(PICKS, n).clip(3, 20)          # 运气：拿到的件数有方差
    out = np.empty(n)
    for i, k in enumerate(picks):
        c = rng.multinomial(int(k), [1 / N_DIM] * N_DIM)
        out[i] = total_of(c, mode)
    out *= np.where(rng.random(n) < SYN_P, SYN_BONUS, 1.0)   # 稀有协同
    return out


print(f"（加入两个真实来源：道具数量的运气方差 + {SYN_P:.0%} 概率的稀有协同 ×{SYN_BONUS}）\n")
print(f"{'规则':<12}{'中位倍数':>10}{'P99 倍数':>11}{'P99/中位':>11}   爆发感")
print("-" * 62)

real = {}
for mode in MODES:
    m = realistic(mode)
    real[mode] = m
    ratio = np.percentile(m, 99) / np.median(m)
    note = ("★ 有巅峰体验" if ratio > 1.9 else
            ("偏平" if ratio > 1.5 else "几乎没有巅峰"))
    print(f"{mode:<12}{np.median(m):>10.2f}{np.percentile(m,99):>11.2f}"
          f"{ratio:>11.2f}   {note}")

print(f"""
读法
----
**对比第 ② 段：加进"运气 + 协同"之后，爆发感才出现了。**

⇒ **爆发感的来源不是叠加规则，是随机性**（拿到多少件、有没有凑齐协同）。
  叠加规则决定的是**另一件事**：分配决策值不值钱。

  **这两件事要分开设计，也要分开体检：**
    · 想要更多巅峰局 → 调随机性（第 09 章）和协同门槛（第 07 章）
    · 想让构筑决策更有分量 → 调同维叠加的凹性（本章第 ② 段）

  **新手最常犯的错是拿错旋钮**：觉得"不够爽"就去改叠加公式，
  改成乘法之后确实数字更大了，**但同时把构筑决策删掉了**，
  玩家会说"越来越无脑"。

⚠️ 注意这里有个陷阱：**同维乘法的 P99/中位 是全场最高的（{np.percentile(real['同维乘法'],99)/np.median(real['同维乘法']):.2f}）。**
   看爆发感指标，它是"最好"的规则！

   但那个方差是从哪来的？—— 从**道具数量的运气**来的。
   乘法把件数的随机波动指数放大了：多拿 3 件就是 ×{1.25**3:.2f}。

   ⇒ **乘法用"玩家控制不了的东西"（运气），换掉了"玩家能控制的东西"（分配）。**
     爆发感的数字很好看，玩家的感受却是"全看脸"。

   ⇒ **这就是为什么爆发感不能只看一个 P99/中位。**
     要同时问：**这个方差是谁贡献的？** 运气贡献的方差和决策贡献的方差，
     在玩家那里是完全不同的两种体验（第 09 章整章讲这个区别）。
""")

# ============================================================
# ④ 接回第 06、07 章的健康带
# ============================================================
print("=== ④ 接回变现：把总倍数换算成通关率 ===\n")

BAND = (0.20, 0.45)
REF = float(np.median(real["同维加法"]))     # 以"同维加法"的中位局为基准局
PG_BASE, PG_SCALE = 1.020, 0.0045
_cache = {}


def winrate(mult):
    pg = round(float(np.clip(PG_BASE + np.log(mult / REF) * PG_SCALE,
                             1.008, 1.032)), 4)
    if pg not in _cache:
        p = dict(R.P); p["power_gain"] = pg
        _cache[pg] = R.batch(600, p)[0]
    return _cache[pg]


print(f"（标定：以'同维加法'的中位局为 power_gain={PG_BASE}，即第 06 章平顶中央；"
      f"健康带 {BAND[0]:.0%}~{BAND[1]:.0%}）\n")
print(f"{'规则':<12}{'中位通关率':>12}{'P99 通关率':>12}"
      f"{'落在健康带':>13}{'太易(>45%)':>13}")
print("-" * 64)

for mode in MODES:
    qs = np.percentile(real[mode], np.arange(2.5, 100, 5))
    ws = np.array([winrate(m) for m in qs])
    inb = ((ws >= BAND[0]) & (ws <= BAND[1])).mean()
    print(f"{mode:<12}{np.median(ws):>12.1%}"
          f"{winrate(np.percentile(real[mode], 99)):>12.1%}"
          f"{inb:>13.0%}{(ws > BAND[1]).mean():>13.0%}")

print(f"""
读法 —— 本章的落点
------------------
**你要的形状是：中位留在健康带内，P99 冲出去。**
（这正是第 07 章 B 方案"稀有协同超模"的形状：主体不动，右尾长出去。）

⇒ **最终建议：同一个维度内部用软上限，维度之间保持相乘。**

  这样你同时得到三样东西：
    1. 维度间相乘 → "每加一件都在加速"的爽感（第 ① 段）
    2. 维度内饱和 → 分配决策最值钱（第 ② 段），且自动引导均衡发展
    3. 随机性 + 协同 → 巅峰局（第 ③ 段），而主体分布不动

  三者是**三个独立的旋钮**，别混着调。
""")

# ============================================================
# 出图
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

ks = np.arange(0, 9)
for mode in MODES:
    axes[0].plot(ks, [dim_mult(int(k), mode) for k in ks], "o-", lw=2, label=mode)
axes[0].set_xlabel("堆在同一维度的件数"); axes[0].set_ylabel("该维度倍数")
axes[0].set_title("① 五种同维叠加规则\n凹性越强，分配决策越值钱")
axes[0].legend(fontsize=8)

dvs = [best_worst(m)[0] / best_worst(m)[1] for m in MODES]
axes[1].barh(MODES, dvs, color=["tab:red", "tab:gray", "tab:olive",
                                "tab:blue", "tab:green"])
axes[1].axvline(1.0, color="k", ls=":", lw=1.5)
axes[1].text(1.02, -0.45, "1.0 = 决策完全无意义", fontsize=8)
axes[1].set_xlabel("决策价值（最优分配 ÷ 最差分配）")
axes[1].set_title("② 纯乘法的决策价值精确等于 1\n数字在涨，选择却消失了")

for mode in ("同维乘法", "同维加法", "软上限"):
    axes[2].hist(np.log10(real[mode]), bins=60, alpha=.5, label=mode)
axes[2].set_xlabel("log10(总倍数)"); axes[2].set_ylabel("局数")
axes[2].set_title("③ 加入运气与协同后的分布\n右尾 = 巅峰体验")
axes[2].legend(fontsize=8)

for ax in (axes[0], axes[1], axes[2]):
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s08_synergy.png", dpi=140)
