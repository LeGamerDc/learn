"""
09 章：通货膨胀的度量与诊断

一个有玩家市场的经济体：
  · 货币投放随玩家成长增长
  · 稀缺物品每天供给 S 个，玩家用金币竞价 → 成交价由"货币量 ÷ 供给量"决定
  · NPC 商店以**固定价格**卖同类物品

三个场景说明通胀的两个独立来源：
  A 回收充分 + 商品供给跟随增长  → 物价稳定
  B 回收充分 + 商品供给固定      → 仍然通胀（供给侧通胀）
  C 回收不足 + 商品供给固定      → 暴涨（货币侧 + 供给侧叠加）
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

DAYS = 360
PLAYERS = 5000
BID_RATIO = 0.25            # 玩家每天拿出存量的 25% 去竞价
FAUCET_GROWTH = 1.008       # 日投放增长率 → 360 天约 17.8 倍
WARMUP = 30                 # 前 30 天是起步瞬态，物价基准从第 30 天算


def simulate(sink_rate, supply_growth, base_supply=800.0):
    M = 0.0
    rows = []
    for d in range(1, DAYS + 1):
        faucet = PLAYERS * 200 * FAUCET_GROWTH ** d
        M += faucet

        supply = base_supply * supply_growth ** d
        bid_pool = M * BID_RATIO
        price = bid_pool / supply          # 费雪方程的最小形式：P = MV / Q

        sunk = M * sink_rate               # 回收（成交的钱只是玩家间转移，不消失）
        M -= sunk

        rows.append((M, price, faucet, sunk, supply))
    return np.array(rows)


SCENARIOS = {
    "A 回收 6% + 供给跟随": dict(sink_rate=0.06, supply_growth=FAUCET_GROWTH),
    "B 回收 6% + 供给固定": dict(sink_rate=0.06, supply_growth=1.0),
    "C 回收 2% + 供给固定": dict(sink_rate=0.02, supply_growth=1.0),
}

res = {label: simulate(**kw) for label, kw in SCENARIOS.items()}

# NPC 固定价：定为场景 A 在第 30 天市场价的 2 倍（上线时看起来很贵的一个价格）
NPC_PRICE = res["A 回收 6% + 供给跟随"][WARMUP - 1, 1] * 2.0

fig, axes = plt.subplots(2, 2, figsize=(14, 9))
d = np.arange(1, DAYS + 1)
for label, h in res.items():
    M, price, faucet, sunk, supply = h.T
    axes[0, 0].plot(d, M, lw=2, label=label)
    axes[0, 1].plot(d[WARMUP:], price[WARMUP:] / price[WARMUP - 1], lw=2, label=label)
    axes[1, 0].plot(d, M / faucet, lw=2, label=label)
    axes[1, 1].plot(d, NPC_PRICE / price * 100, lw=2, label=label)

axes[0, 0].set_yscale("log")
axes[0, 0].set_title("① 全服货币总量 M（对数轴）\n只由回收率决定")
axes[0, 0].set_xlabel("天"); axes[0, 0].legend(fontsize=8); axes[0, 0].grid(alpha=.3, which="both")

axes[0, 1].set_yscale("log")
axes[0, 1].set_title(f"② 物价指数（第 {WARMUP} 天 = 1）\n这才是玩家真正感受到的通胀")
axes[0, 1].set_xlabel("天"); axes[0, 1].legend(fontsize=8); axes[0, 1].grid(alpha=.3, which="both")

axes[1, 0].set_title("③ 存量 ÷ 日产出：无量纲通胀温度计")
axes[1, 0].set_ylabel("相当于几天的产出"); axes[1, 0].set_xlabel("天")
axes[1, 0].axhspan(5, 20, color="tab:green", alpha=.15)
axes[1, 0].text(120, 21, "健康区间 5~20 天", color="tab:green", fontsize=9)
axes[1, 0].legend(fontsize=8); axes[1, 0].grid(alpha=.3)

axes[1, 1].set_yscale("log")
axes[1, 1].set_title("④ NPC 固定价 ÷ 市场价（%）\n跌破红线后 NPC 商店变成无限套利口")
axes[1, 1].axhline(100, color="tab:red", ls="--", lw=1.5)
axes[1, 1].set_xlabel("天"); axes[1, 1].legend(fontsize=8); axes[1, 1].grid(alpha=.3, which="both")

plt.tight_layout()
plt.savefig("../figures/m09_inflation.png", dpi=140)

print(f"{'场景':<26}{'末货币量':>18}{'物价涨幅':>12}{'存量/日产':>12}")
print("-" * 70)
for label, h in res.items():
    M, price, faucet, sunk, supply = h.T
    print(f"{label:<24}{M[-1]:>18,.0f}"
          f"{price[-1] / price[WARMUP - 1]:>11.1f}×{M[-1] / faucet[-1]:>12.1f}")

print(f"\nNPC 固定售价 = {NPC_PRICE:,.0f}（定为场景 A 第 {WARMUP} 天市场价的 2 倍）")
for label, h in res.items():
    price = h[:, 1]
    below = np.where(price > NPC_PRICE)[0]
    msg = f"第 {below[0] + 1} 天起市场价超过 NPC 固定价 → 套利开始" if len(below) \
        else "360 天内未被套利"
    print(f"  {label:<24}{msg}")
