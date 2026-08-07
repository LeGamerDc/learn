"""
18 章：SLG 的两个核心参数

① 集结战力的叠加方式：总战力 = (Σ 个人战力)^α
   α = 1.0  线性相加  → 人多的赢
   α < 1.0  次线性    → 钱多的赢
   这一个参数决定了服务器是"组织能力主导"还是"付费能力主导"。

② 战损率与可持续作战频率：
   打仗要损兵，损兵要再生产。战损率决定了一个玩家多久能打一次。
   战损率太低 → 兵是消耗不掉的 sink（第 08 章）；太高 → 没人敢打。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()
rng = np.random.default_rng(3)

# ---------- 服务器人口与战力分布 ----------
TIERS = [("免费玩家", 0.74, 1.0), ("小 R", 0.20, 2.5),
         ("中 R", 0.05, 8.0), ("大 R", 0.01, 30.0)]
N = 3000
pop, power = [], []
for name, share, mult in TIERS:
    k = int(N * share)
    pop += [name] * k
    power += list(rng.lognormal(np.log(mult), 0.35, k))
power = np.array(power)
whale = np.sort(power)[-1]                      # 服里最强的一个大 R

# ==================== ① 集结叠加方式 ====================
alphas = np.linspace(0.5, 1.0, 26)
free_power = np.median([p for n, p in zip(pop, power) if n == "免费玩家"])

need = []
for a in alphas:
    # 需要 n 个免费玩家集结才能打赢一个大 R：(n × free)^a ≥ whale
    n = (whale ** (1 / a)) / free_power
    need.append(n)
need = np.array(need)

print("=== ① 打赢一个顶级大 R 需要多少免费玩家集结 ===")
print(f"（顶级大 R 战力 = 免费玩家中位数的 {whale/free_power:.0f} 倍）\n")
print(f"{'α（叠加指数）':<16}{'所需人数':>12}{'现实可行性':>26}")
print("-" * 56)
for a in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]:
    n = (whale ** (1 / a)) / free_power
    if n <= 20:
        verdict = "一个小队就能打"
    elif n <= 100:
        verdict = "一个联盟能组织起来"
    elif n <= 1000:
        verdict = "需要全服级动员"
    else:
        verdict = "不可能 → 大 R 无敌"
    print(f"{a:<16.1f}{n:>12,.0f}{verdict:>24}")

# ==================== ② 战损与可持续作战 ====================
LOSS_RATES = np.linspace(0.01, 0.30, 30)
DAILY_REBUILD = 0.06        # 每天能补充的兵力占总兵力的比例

print(f"\n=== ② 战损率 vs 可持续作战频率（日再生产能力 {DAILY_REBUILD:.0%}）===")
print(f"{'战损率':>8}{'两次开战的间隔':>16}{'体验':>28}")
print("-" * 54)
for lr in [0.02, 0.05, 0.10, 0.15, 0.25]:
    interval = lr / DAILY_REBUILD
    if interval < 0.5:
        v = "兵损不掉 → 兵不是 sink"
    elif interval <= 3:
        v = "健康：几天一战"
    elif interval <= 10:
        v = "偏重：打一次要缓很久"
    else:
        v = "没人敢打 → 战争系统冻结"
    print(f"{lr:>8.0%}{interval:>14.1f} 天{v:>26}")

# ==================== 出图 ====================
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

axes[0].semilogy(alphas, need, lw=2.5, color="tab:blue")
axes[0].axhline(100, color="tab:green", ls="--", lw=1.5)
axes[0].axhline(1000, color="tab:red", ls="--", lw=1.5)
axes[0].text(0.52, 120, "一个联盟的规模", color="tab:green", fontsize=9)
axes[0].text(0.52, 1200, "全服都打不过", color="tab:red", fontsize=9)
axes[0].set_title("① 打赢一个大 R 需要的免费玩家数\n（纵轴对数）")
axes[0].set_xlabel("α  集结战力叠加指数"); axes[0].grid(alpha=.3, which="both")

axes[1].plot(LOSS_RATES * 100, LOSS_RATES / DAILY_REBUILD, lw=2.5, color="tab:orange")
axes[1].axhspan(0.5, 3, color="tab:green", alpha=.15)
axes[1].text(16, 1.6, "健康区间", color="tab:green", fontsize=10)
axes[1].set_title("② 战损率 vs 两次开战的间隔")
axes[1].set_xlabel("单次作战的兵力损失率 %"); axes[1].set_ylabel("间隔（天）")
axes[1].grid(alpha=.3)

# ③ 不同 α 下，各分层对"全服总战力"的贡献占比
axes[2].set_title("③ 各分层对全服有效战力的贡献")
width = 0.2
for i, a in enumerate([1.0, 0.85, 0.7, 0.55]):
    contrib = []
    for name, _, _ in TIERS:
        p = np.array([q for n, q in zip(pop, power) if n == name])
        contrib.append((p.sum()) ** a)
    contrib = np.array(contrib) / np.sum(contrib)
    axes[2].bar(np.arange(4) + i * width - 1.5 * width, contrib * 100,
                width, label=f"α={a}")
axes[2].set_xticks(range(4))
axes[2].set_xticklabels([t[0] for t in TIERS])
axes[2].set_ylabel("占全服有效战力 %")
axes[2].legend(fontsize=8); axes[2].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m18_slg_alliance.png", dpi=140)
