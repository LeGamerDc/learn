"""
02 章：心流通道模型
玩家能力（战力）随时间增长，内容难度怎么跟？
对比三种难度投放策略，看玩家分别处在焦虑 / 心流 / 无聊的哪个区间。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

DAYS = 180
t = np.arange(1, DAYS + 1)

# ---------------- 玩家能力曲线 ----------------
# 沿用第 00 章的结论：指数投放 / 指数成本 → 战力呈"幂律 + 饱和"形态。
# 这里用一个平滑近似：早期快速上升，后期趋缓。
POWER_0 = 1000.0
skill = POWER_0 * (1 + t) ** 1.6

# ---------------- 心流通道 ----------------
# 难度低于能力的 0.85 倍 → 无聊；高于 1.25 倍 → 焦虑。
# 这两个系数是本章的核心可调参数，不同品类差别很大。
BORED_RATIO = 0.85
ANXIOUS_RATIO = 1.25

# ---------------- 三种难度投放策略 ----------------
# A. 线性难度：关卡难度按天数线性增长（新手常犯的错）
diff_linear = POWER_0 * (1 + 6.0 * t)

# B. 恒定跟随：难度永远是当前战力的 1.05 倍
diff_follow = skill * 1.05

# C. 锯齿跟随：在通道内周期性起伏——卡住、突破、再卡住
CYCLE = 14  # 一个卡点周期约两周
phase = (t % CYCLE) / CYCLE
diff_saw = skill * (0.90 + 0.32 * phase)

fig, axes = plt.subplots(2, 1, figsize=(11, 10), sharex=True)

# ---- 上图：绝对值（对数纵轴，否则后期看不清）----
ax = axes[0]
ax.fill_between(t, skill * BORED_RATIO, skill * ANXIOUS_RATIO,
                color="tab:green", alpha=.18, label="心流通道")
ax.plot(t, skill, "k-", lw=2.5, label="玩家战力")
ax.plot(t, diff_linear, lw=2, ls=":", color="tab:red", label="A 线性难度")
ax.plot(t, diff_follow, lw=2, ls="--", color="tab:blue", label="B 恒定跟随 ×1.05")
ax.plot(t, diff_saw, lw=1.8, color="tab:orange", label="C 锯齿跟随（周期 14 天）")
ax.set_yscale("log")
ax.set_ylabel("战力 / 关卡难度（对数轴）")
ax.set_title("① 三种难度投放策略 vs 玩家能力")
ax.legend(loc="lower right", fontsize=9)
ax.grid(alpha=.3, which="both")

# ---- 下图：难度 / 能力 比值 ----
ax = axes[1]
ax.axhspan(BORED_RATIO, ANXIOUS_RATIO, color="tab:green", alpha=.18)
ax.axhline(ANXIOUS_RATIO, color="tab:red", lw=1, ls="--")
ax.axhline(BORED_RATIO, color="tab:gray", lw=1, ls="--")
ax.plot(t, diff_linear / skill, lw=2, ls=":", color="tab:red", label="A 线性难度")
ax.plot(t, diff_follow / skill, lw=2, ls="--", color="tab:blue", label="B 恒定跟随")
ax.plot(t, diff_saw / skill, lw=1.8, color="tab:orange", label="C 锯齿跟随")
ax.set_ylim(0, 2.2)
ax.set_ylabel("难度 / 能力")
ax.set_xlabel("天")
ax.set_title("② 同一件事换个坐标：比值落在绿带里才是心流")
ax.text(DAYS * .60, 1.85, "焦虑区：推不动，玩家流失", color="tab:red", fontsize=10)
ax.text(DAYS * .60, 0.42, "无聊区：没挑战，玩家流失", color="tab:gray", fontsize=10)
ax.legend(loc="center right", fontsize=9)
ax.grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m02_flow_channel.png", dpi=140)


def in_flow(diff):
    r = diff / skill
    return np.mean((r >= BORED_RATIO) & (r <= ANXIOUS_RATIO))


print("处于心流通道内的天数占比：")
for name, d in [("A 线性难度", diff_linear),
                ("B 恒定跟随", diff_follow),
                ("C 锯齿跟随", diff_saw)]:
    print(f"  {name:<12} {in_flow(d):>6.1%}")
plt.show()
