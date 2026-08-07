"""
20 章：内容跑道（content runway）

内容以固定速度生产，玩家以不同速度消耗。
核心问题：**头部玩家什么时候会追上你的内容产能？**

一旦追上，他们就进入"长草期"——这是高付费玩家流失的头号原因。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

DAYS = 540
CONTENT_AT_LAUNCH = 300          # 上线时的内容储备（"内容点"，可理解为关卡/养成层数）
CONTENT_PER_DAY = 1.6            # 团队的日均内容产能（≈ 每月 48 点）

# 各分层的消耗速度（内容点/天），以及它们的人数占比
TIERS = {
    "免费玩家": (0.9, 0.74),
    "小 R":    (1.3, 0.20),
    "中 R":    (2.2, 0.05),
    "大 R":    (4.5, 0.01),
}

t = np.arange(0, DAYS + 1)
supply = CONTENT_AT_LAUNCH + CONTENT_PER_DAY * t

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

print(f"内容储备 {CONTENT_AT_LAUNCH} 点，日产能 {CONTENT_PER_DAY} 点/天"
      f"（≈ 每月 {CONTENT_PER_DAY*30:.0f} 点）\n")
print(f"{'分层':<12}{'消耗速度':>10}{'追上内容的时间':>16}{'那时的内容量':>14}")
print("-" * 54)
catchup = {}
for name, (speed, share) in TIERS.items():
    consumed = speed * t
    axes[0].plot(t, consumed, lw=2, label=f"{name}（{speed}/天）")
    hit = np.where(consumed >= supply)[0]
    day = hit[0] if len(hit) else None
    catchup[name] = day
    if day:
        print(f"{name:<10}{speed:>10.1f}{f'第 {day} 天':>16}{supply[day]:>14,.0f}")
    else:
        print(f"{name:<10}{speed:>10.1f}{'540 天内未追上':>16}{'—':>14}")

axes[0].plot(t, supply, "k--", lw=2.5, label=f"内容供给（{CONTENT_PER_DAY}/天）")
for name, day in catchup.items():
    if day:
        axes[0].plot(day, supply[day], "r*", ms=14, zorder=5)
axes[0].set_title("① 内容消耗 vs 内容供给\n红星 = 该分层进入长草期")
axes[0].set_xlabel("天"); axes[0].set_ylabel("累计内容点")
axes[0].legend(fontsize=8); axes[0].grid(alpha=.3)

# ---------- 需要多大的产能才能喂饱各分层 ----------
speeds = np.linspace(0.5, 6.0, 60)
axes[1].plot(speeds, speeds, "k--", lw=2, label="所需日产能 = 消耗速度")
for name, (speed, share) in TIERS.items():
    axes[1].axvline(speed, ls=":", lw=1.5)
    axes[1].text(speed + .05, 0.5, name, rotation=90, fontsize=9, va="bottom")
axes[1].axhline(CONTENT_PER_DAY, color="tab:red", lw=2)
axes[1].text(0.6, CONTENT_PER_DAY + .15, f"当前产能 {CONTENT_PER_DAY}", color="tab:red")
axes[1].set_title("② 要让某分层永不长草，需要多大产能\n红线以上的分层注定会追上你")
axes[1].set_xlabel("分层的消耗速度（点/天）"); axes[1].set_ylabel("所需日产能")
axes[1].legend(fontsize=8); axes[1].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m20_content_runway.png", dpi=140)

print(f"\n=== 结论 ===")
fast = [n for n, (s, _) in TIERS.items() if s > CONTENT_PER_DAY]
print(f"消耗速度超过日产能（{CONTENT_PER_DAY}）的分层：{', '.join(fast)}")
print("这些分层**必然**会追上内容，只是早晚问题。")
print("加大产能不是解法（产能是线性的，而你追不上所有人）——")
print("解法是给他们**不消耗内容储备**的目标：PvP、赛季、排名、社交地位。")

# 长草期的人口占比
share_starved = sum(s for n, (sp, s) in TIERS.items()
                    if catchup[n] is not None and catchup[n] <= 365)
print(f"\n第 365 天时，已进入长草期的玩家占总人口：{share_starved:.0%}")
print(f"但他们贡献的流水远高于这个比例 —— 这就是问题的严重性。")
