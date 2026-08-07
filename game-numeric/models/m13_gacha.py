"""
13 章：抽卡的数学

对比四种概率机制在**同一期望**下的体验差异：
  A 纯随机 1.6%（无保底）
  B 硬保底 90 抽
  C 软保底（第 74 抽起概率线性上升，90 抽必出）—— 主流做法
  D 伪随机分布 PRD（暴雪 War3/Dota 用的机制）

结论会证明：**方差比期望更影响体验**。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()
rng = np.random.default_rng(2024)

TRIALS = 200_000
BASE_P = 0.016          # 基础概率 1.6%
SOFT_START, HARD_PITY = 74, 90


def pulls_plain():
    """A 纯随机：几何分布"""
    return rng.geometric(BASE_P, TRIALS)


def pulls_hard():
    """B 硬保底：几何分布截断在 90"""
    return np.minimum(rng.geometric(BASE_P, TRIALS), HARD_PITY)


def prob_soft(n):
    """C 软保底：第 n 抽的出货概率"""
    if n < SOFT_START:
        return BASE_P
    # 从 SOFT_START 线性升到 HARD_PITY 处的 100%
    return min(BASE_P + (1.0 - BASE_P) * (n - SOFT_START + 1) / (HARD_PITY - SOFT_START + 1), 1.0)


def pulls_soft():
    out = np.empty(TRIALS, dtype=int)
    probs = np.array([prob_soft(n) for n in range(1, HARD_PITY + 1)])
    for i in range(TRIALS):
        u = rng.random(HARD_PITY)
        hit = np.argmax(u < probs)          # 第一个命中的位置
        out[i] = hit + 1
    return out


def pulls_prd(c):
    """
    D 伪随机分布：第 n 次未出货后，概率为 c*n（线性递增）。
    c 由目标期望反解。这是 War3/Dota 暴击机制的原理。
    """
    out = np.empty(TRIALS, dtype=int)
    for i in range(TRIALS):
        n = 1
        while True:
            if rng.random() < min(c * n, 1.0):
                out[i] = n
                break
            n += 1
    return out


def prd_expected(c, nmax=400):
    """给定 c，算 PRD 的期望抽数"""
    e, surv = 0.0, 1.0
    for n in range(1, nmax + 1):
        p = min(c * n, 1.0)
        e += n * surv * p
        surv *= (1 - p)
        if surv < 1e-12:
            break
    return e


# 用二分法反解 c，使 PRD 的期望等于软保底的期望
soft = pulls_soft()
target = soft.mean()
lo, hi = 1e-5, 0.5
for _ in range(60):
    mid = (lo + hi) / 2
    if prd_expected(mid) > target:
        lo = mid
    else:
        hi = mid
C_PRD = lo

results = {
    "A 纯随机 1.6%（无保底）": pulls_plain(),
    f"B 硬保底 {HARD_PITY} 抽": pulls_hard(),
    f"C 软保底（{SOFT_START} 起爬升）": soft,
    f"D PRD（c={C_PRD:.4f}）": pulls_prd(C_PRD),
}

print(f"{'机制':<28}{'期望':>8}{'标准差':>9}{'中位数':>8}{'P90':>7}{'P99':>7}{'最差':>8}")
print("-" * 78)
for name, x in results.items():
    print(f"{name:<26}{x.mean():>8.1f}{x.std():>9.1f}{np.median(x):>8.0f}"
          f"{np.percentile(x,90):>7.0f}{np.percentile(x,99):>7.0f}{x.max():>8.0f}")

print(f"\n单价按 15 元/抽计算，各机制下'最惨的 1% 玩家'要花：")
for name, x in results.items():
    print(f"  {name:<26}{np.percentile(x, 99)*15:>8,.0f} 元")

print(f"\n=== 十连保底的心理效应 ===")
plain = results["A 纯随机 1.6%（无保底）"]
print(f"  纯随机下，抽 10 次一无所获的玩家占比：{(plain > 10).mean():.1%}")
print(f"  纯随机下，抽 50 次一无所获的玩家占比：{(plain > 50).mean():.1%}")
print(f"  纯随机下，抽 200 次才出货的玩家占比：{(plain > 200).mean():.2%}")

# ==================== 出图 ====================
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

for name, x in results.items():
    axes[0].hist(x, bins=np.arange(0, 200, 4), histtype="step", lw=2,
                 density=True, label=name)
axes[0].set_title("① 出货所需抽数的分布")
axes[0].set_xlabel("抽数"); axes[0].legend(fontsize=7); axes[0].grid(alpha=.3)

for name, x in results.items():
    xs = np.sort(x)
    axes[1].plot(xs, np.arange(1, len(xs) + 1) / len(xs) * 100, lw=2, label=name)
axes[1].set_xlim(0, 200)
axes[1].set_title("② 累积出货率\n越陡越可预期")
axes[1].set_xlabel("抽数"); axes[1].set_ylabel("已出货玩家 %")
axes[1].legend(fontsize=7); axes[1].grid(alpha=.3)

names = list(results)
axes[2].bar(range(len(names)), [results[n].std() for n in names], color="tab:orange")
axes[2].set_xticks(range(len(names)))
axes[2].set_xticklabels([n.split("（")[0] for n in names], fontsize=8, rotation=15)
axes[2].set_title("③ 标准差：同样的期望，差别全在这里")
axes[2].set_ylabel("抽数标准差"); axes[2].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m13_gacha.png", dpi=140)
