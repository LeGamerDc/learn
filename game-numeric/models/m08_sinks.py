"""
08 章：四种回收策略的 360 天对比

同一套投放（随等级指数增长），换四种 sink：
  A 有上限型   —— 建筑升到 20 级封顶，之后回收归零
  B 无限层级型 —— 成本指数增长，永不封顶
  C 比例损耗型 —— 每天损失存量的 x%（兵损、维护费、交易税都属于这类）
  D 混合型     —— B + C，真实游戏的做法

看存量曲线和回收率，判断哪种能撑住长线。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

DAYS = 360
BASE_INCOME = 2000.0
INCOME_GROWTH = 1.06      # 日产出随等级增长
BASE_COST = 5000.0
COST_GROWTH = 1.35
CAP_LEVEL = 12            # A 方案的封顶等级
DECAY = 0.06              # C 方案：每天损失 6% 存量


def simulate(mode):
    gold, level = 0.0, 1
    hist = []
    for _ in range(DAYS):
        income = BASE_INCOME * INCOME_GROWTH ** (level - 1)
        gold += income
        sunk = 0.0

        # 层级型回收（A/B/D 有，C 没有）
        if mode in ("A", "B", "D"):
            cap = CAP_LEVEL if mode == "A" else None
            while (cap is None or level < cap):
                cost = BASE_COST * COST_GROWTH ** (level - 1)
                if gold < cost:
                    break
                gold -= cost
                sunk += cost
                level += 1

        # 比例损耗型回收（C/D 有）
        if mode in ("C", "D"):
            loss = gold * DECAY
            gold -= loss
            sunk += loss

        hist.append((gold, income, sunk, level))
    return np.array(hist)


MODES = {
    "A": f"A 有上限（{CAP_LEVEL}级封顶）",
    "B": "B 无限层级",
    "C": f"C 比例损耗（每天 {DECAY:.0%}）",
    "D": "D 混合（层级 + 损耗）",
}

fig, axes = plt.subplots(2, 2, figsize=(14, 9))
results = {}

for mode, label in MODES.items():
    h = simulate(mode)
    results[mode] = h
    gold, income, sunk, level = h.T
    axes[0, 0].plot(gold, lw=2, label=label)
    axes[0, 1].plot(np.cumsum(sunk) / np.cumsum(income) * 100, lw=2, label=label)
    # 存量相当于多少天的产出 —— 衡量"浮财"的无量纲指标
    axes[1, 0].plot(gold / income, lw=2, label=label)

axes[0, 0].set_yscale("log")
axes[0, 0].set_title("① 存量（对数轴）")
axes[0, 0].set_xlabel("天"); axes[0, 0].legend(fontsize=8); axes[0, 0].grid(alpha=.3, which="both")

axes[0, 1].set_title("② 累计回收率 = 累计回收 / 累计投放")
axes[0, 1].set_ylabel("%"); axes[0, 1].set_xlabel("天")
axes[0, 1].axhline(85, color="tab:red", ls=":", lw=1.5)
axes[0, 1].text(5, 87, "85% 警戒线", color="tab:red", fontsize=9)
axes[0, 1].legend(fontsize=8); axes[0, 1].grid(alpha=.3)

axes[1, 0].set_yscale("log")
axes[1, 0].set_title("③ 存量相当于几天的产出\n这个无量纲指标才是真正的通胀温度计")
axes[1, 0].set_xlabel("天"); axes[1, 0].legend(fontsize=8); axes[1, 0].grid(alpha=.3, which="both")

for mode, label in MODES.items():
    axes[1, 1].plot(results[mode][:, 3], lw=2, label=label)
axes[1, 1].set_title("④ 城建等级（玩家感受到的成长）")
axes[1, 1].set_xlabel("天"); axes[1, 1].legend(fontsize=8); axes[1, 1].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m08_sinks.png", dpi=140)

print(f"{'方案':<26}{'末存量':>16}{'回收率':>10}{'存量/日产':>12}{'末等级':>8}")
print("-" * 74)
for mode, label in MODES.items():
    gold, income, sunk, level = results[mode].T
    print(f"{label:<24}{gold[-1]:>16,.0f}{np.sum(sunk)/np.sum(income):>10.1%}"
          f"{gold[-1]/income[-1]:>12.1f}{int(level[-1]):>8}")

# 稳态推导：gold* = (gold* + I)(1-d)  =>  gold* = I(1-d)/d
print(f"\nC 方案的理论平衡点：(1-d)/d = (1-{DECAY})/{DECAY} ≈ {(1-DECAY)/DECAY:.1f} 天的产出")
print(f"C 方案实测：{results['C'][-1, 0] / results['C'][-1, 1]:.1f} 天的产出")
