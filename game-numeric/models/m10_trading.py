"""
10 章：开不开自由交易，改变的是稀缺物品的分配规则

同一批玩家（付费能力长尾分布），每天全服产出 S 件稀缺物品：
  A 无交易   —— 物品随机掉落给参与的玩家，谁打到算谁的
  B 自由交易 —— 物品最终流向出价最高的人（价高者得）
  C 绑定交易 —— 一部分物品绑定（不可交易），其余可交易

看头部玩家占有稀缺物品的比例，以及基尼系数。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

rng = np.random.default_rng(42)

N = 5000          # 玩家数
DAYS = 180
SUPPLY = 300      # 每天全服产出的稀缺物品数

# 付费能力：对数正态长尾分布（少数大 R + 大量免费玩家）
pay_power = rng.lognormal(mean=0.0, sigma=2.0, size=N)
pay_power = pay_power / pay_power.sum()      # 归一化成"出价份额"


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if x.sum() == 0:
        return 0.0
    idx = np.arange(1, n + 1)
    return (2 * (idx * x).sum() / (n * x.sum())) - (n + 1) / n


def simulate(mode, bound_ratio=0.5):
    owned = np.zeros(N)
    hist = []
    for _ in range(DAYS):
        if mode == "A":
            # 随机掉落：每件物品等概率给一个玩家
            winners = rng.integers(0, N, SUPPLY)
            np.add.at(owned, winners, 1)
        elif mode == "B":
            # 价高者得：按付费能力份额分配
            owned += SUPPLY * pay_power
        else:
            # 绑定部分随机掉落，其余按付费能力分配
            nb = int(SUPPLY * bound_ratio)
            winners = rng.integers(0, N, nb)
            np.add.at(owned, winners, 1)
            owned += (SUPPLY - nb) * pay_power
        top1 = np.sort(owned)[-N // 100:].sum() / owned.sum()
        hist.append((top1, gini(owned)))
    return np.array(hist), owned


MODES = {"A": "A 无交易（随机掉落）",
         "B": "B 自由交易（价高者得）",
         "C": "C 绑定 50%（混合）"}

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
finals = {}
for m, label in MODES.items():
    h, owned = simulate(m)
    finals[m] = (h, owned)
    axes[0].plot(h[:, 0] * 100, lw=2, label=label)
    axes[1].plot(h[:, 1], lw=2, label=label)

axes[0].set_title("① 头部 1% 玩家占有的稀缺物品比例")
axes[0].set_ylabel("%"); axes[0].set_xlabel("天"); axes[0].legend(fontsize=8); axes[0].grid(alpha=.3)

axes[1].set_title("② 稀缺物品占有的基尼系数\n(0=完全平均, 1=完全集中)")
axes[1].set_xlabel("天"); axes[1].set_ylim(0, 1); axes[1].legend(fontsize=8); axes[1].grid(alpha=.3)

for m, label in MODES.items():
    owned = np.sort(finals[m][1])[::-1]
    axes[2].plot(np.arange(1, N + 1) / N * 100, np.cumsum(owned) / owned.sum() * 100,
                 lw=2, label=label)
axes[2].plot([0, 100], [0, 100], "k:", lw=1, label="完全平均")
axes[2].set_title("③ 洛伦兹曲线（第 180 天）")
axes[2].set_xlabel("玩家累计占比 %（按持有量降序）")
axes[2].set_ylabel("持有量累计占比 %")
axes[2].legend(fontsize=8); axes[2].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m10_trading.png", dpi=140)

print(f"{'方案':<26}{'头部1%占有':>12}{'基尼系数':>12}{'零持有玩家':>12}")
print("-" * 62)
for m, label in MODES.items():
    h, owned = finals[m]
    zero = (owned < 1).sum() / N
    print(f"{label:<24}{h[-1, 0]:>11.1%}{h[-1, 1]:>12.2f}{zero:>12.1%}")
