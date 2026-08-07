"""
07 章：日产出预算表

真实项目里数值策划最重要的交付物之一。做法是**自顶向下**：
  ① 从节奏表定出"第 N 天玩家应该累计拿到多少资源"（总量目标）
  ② 把总量拆到各个产出渠道（分配）
  ③ 校验：各渠道之和是否等于总量目标；分层玩家的差距是否符合预期
输出 CSV，交付给策划和程序。
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

pd.set_option("display.width", 200)
pd.set_option("display.unicode.east_asian_width", True)

DAYS = 180

# ==================== ① 总量目标 ====================
# 来自第 04 章的节奏表：玩家第 N 天应该达到的累计资源量。
# 这里用分段增长的日产出来表达（早期陡、后期缓）。
STAGES = [
    # (起始天, 结束天, 阶段名,      日产出基准, 每天增长率)
    (1,   7,   "新手期",    12000,  1.120),
    (8,   30,  "成长期",    26000,  1.035),
    (31,  90,  "中期",      57000,  1.012),
    (91,  180, "长线期",   117000,  1.004),
]

# ==================== ② 渠道分配 ====================
# 每个阶段，各渠道占日产出的比例。合计必须 = 1.0
CHANNELS = {
    #  渠道          新手期  成长期   中期   长线期
    "挂机产出":     [0.20,  0.28,  0.34,  0.38],
    "主线关卡":     [0.34,  0.18,  0.06,  0.02],
    "日常任务":     [0.18,  0.18,  0.16,  0.14],
    "联盟/社交":    [0.02,  0.08,  0.14,  0.18],
    "PvP 战利品":   [0.02,  0.06,  0.10,  0.12],
    "签到/邮件":    [0.14,  0.08,  0.05,  0.03],
    "活动":        [0.10,  0.14,  0.15,  0.13],
}
STAGE_NAMES = [s[2] for s in STAGES]

# 校验：每个阶段的渠道占比必须加起来是 1
alloc = pd.DataFrame(CHANNELS, index=STAGE_NAMES).T
bad = alloc.sum()[(alloc.sum() - 1.0).abs() > 1e-9]
assert bad.empty, f"渠道占比之和不为 1：\n{bad}"

# ==================== ③ 玩家分层 ====================
# 关键：付费产出是**一个独立渠道**，不是给已有渠道加成。
# 因为挂机、日常、签到这些渠道有时间和次数上限，付费买不到。
# 数值 = 该分层每天通过付费获得的资源，以"免费玩家日产出"为单位。
TIERS = {
    "免费玩家": 0.0,
    "小 R":    0.3,
    "中 R":    1.5,
    "大 R":    6.0,
}


def daily_total(day):
    """某一天的基准日产出总量（免费玩家）"""
    for d0, d1, _, base, growth in STAGES:
        if d0 <= day <= d1:
            return base * growth ** (day - d0)
    return 0.0


def stage_of(day):
    for i, (d0, d1, name, _, _) in enumerate(STAGES):
        if d0 <= day <= d1:
            return i, name
    return None, None


# ---------- 生成逐日、逐渠道的预算表 ----------
rows = []
for day in range(1, DAYS + 1):
    i, name = stage_of(day)
    total = daily_total(day)
    row = {"天": day, "阶段": name, "日产出合计": total}
    for ch, ratios in CHANNELS.items():
        row[ch] = total * ratios[i]
    rows.append(row)

budget = pd.DataFrame(rows)
budget.to_csv("../tables/07_daily_faucet_budget.csv", index=False,
              encoding="utf-8-sig", float_format="%.0f")

# ---------- 阶段汇总（给人看的版本）----------
summary = budget.groupby("阶段", sort=False).agg(
    天数=("天", "count"),
    日产出_首日=("日产出合计", "first"),
    日产出_末日=("日产出合计", "last"),
    阶段总投放=("日产出合计", "sum"),
)
summary["占全程比例"] = (summary["阶段总投放"] / summary["阶段总投放"].sum())
print("=== 阶段汇总 ===")
print(summary.to_string(formatters={
    "日产出_首日": "{:,.0f}".format, "日产出_末日": "{:,.0f}".format,
    "阶段总投放": "{:,.0f}".format, "占全程比例": "{:.1%}".format}))

print("\n=== 渠道占比（各阶段）===")
print((alloc * 100).round(0).astype(int).to_string())

print("\n=== 各渠道累计投放 ===")
ch_total = budget[list(CHANNELS)].sum().sort_values(ascending=False)
for ch, v in ch_total.items():
    print(f"  {ch:<12}{v:>14,.0f}   {v / ch_total.sum():>6.1%}")

# ---------- 分层玩家的累计投放 ----------
print(f"\n=== 分层玩家 180 天累计投放 ===")
print(f"{'分层':<10}{'累计投放':>16}{'倍数':>8}{'付费渠道占其总投放':>20}")
tier_curves = {}
for tier, pay_mult in TIERS.items():
    paid = budget["日产出合计"] * pay_mult
    cum = (budget["日产出合计"] + paid).cumsum()
    tier_curves[tier] = cum
    share = paid.sum() / (budget["日产出合计"].sum() + paid.sum())
    print(f"  {tier:<8}{cum.iloc[-1]:>16,.0f}"
          f"{cum.iloc[-1] / tier_curves['免费玩家'].iloc[-1]:>7.2f}×{share:>18.0%}")

# ==================== 出图 ====================
fig, axes = plt.subplots(2, 2, figsize=(14, 9))

ax = axes[0, 0]
ax.plot(budget["天"], budget["日产出合计"], lw=2)
for d0, d1, name, _, _ in STAGES:
    ax.axvline(d0, color="gray", ls=":", lw=1)
    ax.text(d0 + 2, budget["日产出合计"].max() * .9, name, fontsize=9, color="gray")
ax.set_yscale("log")
ax.set_title("① 日产出总量（对数轴）：分段增长")
ax.set_xlabel("天"); ax.grid(alpha=.3, which="both")

ax = axes[0, 1]
ax.stackplot(budget["天"], *[budget[c] for c in CHANNELS],
             labels=list(CHANNELS), alpha=.85)
ax.set_title("② 渠道构成：主线让位给挂机和社交")
ax.set_xlabel("天"); ax.legend(fontsize=7, loc="upper left"); ax.grid(alpha=.3)

ax = axes[1, 0]
frac = budget[list(CHANNELS)].div(budget["日产出合计"], axis=0)
for c in CHANNELS:
    ax.plot(budget["天"], frac[c] * 100, lw=1.8, label=c)
ax.set_title("③ 渠道占比随时间的迁移")
ax.set_ylabel("占日产出 %"); ax.set_xlabel("天")
ax.legend(fontsize=7); ax.grid(alpha=.3)

ax = axes[1, 1]
for tier, cum in tier_curves.items():
    ax.plot(budget["天"], cum, lw=2, label=tier)
ax.set_yscale("log")
ax.set_title("④ 分层玩家累计投放（对数轴）\n差距应该是常数倍，不是发散的")
ax.set_xlabel("天"); ax.legend(); ax.grid(alpha=.3, which="both")

plt.tight_layout()
plt.savefig("../figures/m07_faucet_budget.png", dpi=140)
print("\n预算表已导出：tables/07_daily_faucet_budget.csv")
