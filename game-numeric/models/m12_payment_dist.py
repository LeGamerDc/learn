"""
12 章：付费分布与收入结构

F2P 游戏的付费额是极度长尾的。用对数正态分布建模，回答三个问题：
  ① 收入的多少来自 Top 1% / Top 10%？
  ② "提高付费率" 和 "提高大 R 深度" 哪个更能拉收入？
  ③ 付费深度上限（最贵的东西多少钱）怎么影响总收入？
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()
rng = np.random.default_rng(7)

N = 1_000_000        # 玩家总数（样本要大，否则头部噪声会淹没结论）
PAY_RATE = 0.04      # 付费率 4%
MU, SIGMA = 3.6, 1.9  # 付费额的对数正态参数（单位：元）


def make_payers(n=N, pay_rate=PAY_RATE, mu=MU, sigma=SIGMA, cap=None):
    n_pay = int(n * pay_rate)
    amt = rng.lognormal(mu, sigma, n_pay)
    if cap is not None:
        amt = np.minimum(amt, cap)      # 付费深度上限
    return amt


amt = make_payers()
total = amt.sum()
srt = np.sort(amt)[::-1]

print(f"玩家总数 {N:,}   付费玩家 {len(amt):,}（{PAY_RATE:.1%}）")
print(f"总流水 {total:,.0f} 元   ARPU {total/N:.2f} 元   ARPPU {total/len(amt):.1f} 元")
print(f"付费额中位数 {np.median(amt):.0f} 元   均值 {amt.mean():.0f} 元"
      f"   ← 均值远高于中位数 = 长尾")

print("\n=== 收入集中度 ===")
for q in [0.001, 0.01, 0.05, 0.10, 0.50]:
    k = max(int(len(srt) * q), 1)
    print(f"  付费玩家 Top {q:>6.1%}（{k:>6,} 人）贡献 {srt[:k].sum()/total:>6.1%} 的流水")

print("\n=== 两条增长路径的对比（基线流水 = 100%）===")
base = total
for label, kw in [
    ("付费率 4% → 5%（+25% 付费人数）", dict(pay_rate=0.05)),
    ("付费率 4% → 6%（+50% 付费人数）", dict(pay_rate=0.06)),
    ("加深大 R（sigma 1.9 → 2.1）",      dict(sigma=2.1)),
    ("加深大 R（sigma 1.9 → 2.3）",      dict(sigma=2.3)),
    ("提高客单价（mu +0.2，约 +22%）",    dict(mu=3.8)),
]:
    v = make_payers(**kw).sum()
    print(f"  {label:<34}流水 {v/base:>6.1%}")

print("\n=== 付费深度上限的影响 ===")
# 关键：必须在**同一份样本**上套不同的上限，否则头部重采样的噪声会淹没结论
print(f"  {'上限':>10}{'流水占比':>12}{'受影响玩家':>14}")
for cap in [500, 2000, 10000, 50000, None]:
    capped = np.minimum(amt, cap) if cap else amt
    label = f"{cap:,}元" if cap else "无上限"
    hit = (amt > cap).mean() if cap else 0.0
    print(f"  {label:>10}{capped.sum()/base:>12.1%}{hit:>14.2%}")

# ==================== 出图 ====================
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

axes[0].hist(np.log10(amt), bins=60, color="tab:blue", alpha=.8)
axes[0].set_title("① 付费额分布（横轴 log10 元）\n近似正态 = 对数正态长尾")
axes[0].set_xlabel("log10(付费额)"); axes[0].grid(alpha=.3)

x = np.arange(1, len(srt) + 1) / len(srt) * 100
axes[1].plot(x, np.cumsum(srt) / total * 100, lw=2)
for q in (1, 10):
    k = int(len(srt) * q / 100)
    axes[1].plot(q, srt[:k].sum() / total * 100, "ro")
    axes[1].annotate(f"Top {q}% → {srt[:k].sum()/total:.0%}",
                     (q, srt[:k].sum() / total * 100), textcoords="offset points",
                     xytext=(12, -12), fontsize=9)
axes[1].set_title("② 收入集中度曲线")
axes[1].set_xlabel("付费玩家累计占比 %（按付费额降序）")
axes[1].set_ylabel("流水累计占比 %"); axes[1].grid(alpha=.3)

caps = np.array([200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000])
vals = [np.minimum(amt, c).sum() / base for c in caps]
axes[2].semilogx(caps, np.array(vals) * 100, "o-", lw=2)
axes[2].axhline(100, color="tab:red", ls=":")
axes[2].set_title("③ 付费深度上限 vs 总流水")
axes[2].set_xlabel("单人付费上限（元）"); axes[2].set_ylabel("流水占无上限的 %")
axes[2].grid(alpha=.3, which="both")

plt.tight_layout()
plt.savefig("../figures/m12_payment_dist.png", dpi=140)
