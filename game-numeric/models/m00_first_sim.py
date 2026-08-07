"""
00 章：SLG 最小经济闭环仿真
一个玩家 180 天，城建升级循环。观察投放、回收、存量三者的关系。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

DAYS = 180

# ---------------- 数值参数（这就是"数值设计"本身）----------------
BASE_OUTPUT = 2000.0     # 1 级城建的日产金币
OUTPUT_GROWTH = 1.06     # 每升 1 级，产能 ×1.06
BASE_COST = 5000.0       # 升到 2 级的成本
COST_GROWTH = 1.35       # 每升 1 级，成本 ×1.35
# ------------------------------------------------------------


def daily_output(level: int) -> float:
    """投放：等级越高日产越多"""
    return BASE_OUTPUT * (OUTPUT_GROWTH ** (level - 1))


def upgrade_cost(level: int) -> float:
    """回收：从 level 升到 level+1 的花费"""
    return BASE_COST * (COST_GROWTH ** (level - 1))


def simulate(days=DAYS):
    level = 1
    gold = 0.0
    rows = []
    for day in range(1, days + 1):
        income = daily_output(level)
        gold += income

        spent = 0.0
        # 有钱就升级，可能一天升好几级
        while gold >= upgrade_cost(level):
            cost = upgrade_cost(level)
            gold -= cost
            spent += cost
            level += 1

        rows.append((day, level, gold, income, spent))

    return np.array(rows, dtype=float)


data = simulate()
day, level, gold, income, spent = data.T

# 累计投放 / 累计回收
cum_in = np.cumsum(income)
cum_out = np.cumsum(spent)

fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)

axes[0].plot(day, cum_in, label="累计投放（产出的金币）", lw=2)
axes[0].plot(day, cum_out, label="累计回收（升级花掉的）", lw=2, ls="--")
axes[0].set_ylabel("金币")
axes[0].set_title("① 投放 vs 回收：两条线贴得越紧，经济越健康")
axes[0].legend()
axes[0].grid(alpha=.3)

axes[1].plot(day, gold, color="tab:orange", lw=2)
axes[1].set_ylabel("金币存量")
axes[1].set_title("② 存量：每次归零 = 玩家一有钱就花掉了（回收充分）")
axes[1].grid(alpha=.3)

axes[2].step(day, level, where="post", color="tab:green", lw=2)
axes[2].set_ylabel("城建等级")
axes[2].set_xlabel("天")
axes[2].set_title("③ 成长曲线：投放是指数，成本也是指数，相除得到对数形态")
axes[2].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m00_first_sim.png", dpi=140)
print(f"第 {DAYS} 天：城建 {int(level[-1])} 级，"
      f"日产 {income[-1]:,.0f}，存量 {gold[-1]:,.0f}")
print(f"累计投放 {cum_in[-1]:,.0f}，累计回收 {cum_out[-1]:,.0f}，"
      f"回收率 {cum_out[-1] / cum_in[-1]:.1%}")
plt.show()
