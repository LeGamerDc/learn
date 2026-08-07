"""
06 章：货币隔离
两条养成线（战力线 / 收集线），设计意图是让玩家两边都发展。
对比：
  A 共用一种货币 —— 玩家会把 100% 资源投进"性价比最高"的那条线
  B 各自独立货币 —— 玩家被迫两边都走，设计意图得以实现
  C 单向兑换（收集币可换战力币，反之不行）—— 看看能不能守住
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

DAYS = 180
INCOME = 10000.0            # 每天的资源总投放（折算成通用价值）


def power_gain(spent_on_power):
    """战力线：花钱换战力，边际递减"""
    return 200 * np.sqrt(max(spent_on_power, 0) / 100)


def collect_gain(spent_on_collect):
    """收集线：花钱换收集度，边际递减更快"""
    return 60 * np.sqrt(max(spent_on_collect, 0) / 100)


def simulate(mode):
    """玩家每天把当天资源按'战力收益最大化'来分配"""
    power = collect = 0.0
    hist = []
    for _ in range(DAYS):
        if mode == "A":
            # 共用货币：玩家只看战力，全投战力线
            p, c = INCOME, 0.0
        elif mode == "B":
            # 独立货币：投放时就已经分成两份，玩家没得选
            p, c = INCOME * 0.6, INCOME * 0.4
        else:  # C 单向兑换：收集币可以换成战力币
            p, c = INCOME * 0.6 + INCOME * 0.4, 0.0
        power += power_gain(p)
        collect += collect_gain(c)
        hist.append((power, collect))
    return np.array(hist)


fig, axes = plt.subplots(1, 2, figsize=(13, 5))
labels = {"A": "A 共用一种货币", "B": "B 两种独立货币", "C": "C 单向兑换（收集→战力）"}
results = {}
for mode in "ABC":
    h = simulate(mode)
    results[mode] = h
    axes[0].plot(h[:, 0], lw=2, label=labels[mode])
    axes[1].plot(h[:, 1], lw=2, label=labels[mode])

axes[0].set_title("① 战力线发展")
axes[0].set_xlabel("天"); axes[0].set_ylabel("战力"); axes[0].legend(); axes[0].grid(alpha=.3)
axes[1].set_title("② 收集线发展\nA 和 C 完全归零 —— 设计意图彻底落空")
axes[1].set_xlabel("天"); axes[1].set_ylabel("收集度"); axes[1].legend(); axes[1].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m06_currency.png", dpi=140)

print(f"{'方案':<26}{'第180天战力':>14}{'第180天收集度':>16}")
print("-" * 58)
for mode in "ABC":
    h = results[mode]
    print(f"{labels[mode]:<24}{h[-1, 0]:>14,.0f}{h[-1, 1]:>16,.0f}")
print("\n结论：只要两种货币之间存在兑换通道（哪怕是单向的），")
print("      它们在经济上就是同一种货币，你的分配设计会被玩家的最优化行为抹平。")
