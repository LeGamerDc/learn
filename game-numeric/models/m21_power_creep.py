"""
21 章：数值膨胀的两面性

模型：每个版本（30 天）推出的新内容，战力价值是上个版本的 r 倍。
老玩家累积了所有版本的内容；新玩家只能从最近几个版本补起。

于是同一个参数 r 同时决定了两件相反的事：
  ① 老玩家的历史积累贬值多快      —— r 越大越糟
  ② 新玩家需要补多少历史内容才能追上 —— r 越大越好

**这两件事的权衡，就是"数值膨胀速度"这个决策的全部内容。**
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

VERSION_DAYS = 30
YEARS = 2
V = YEARS * 365 // VERSION_DAYS          # 总版本数


def total_power(r, v=V):
    """老玩家累积 v+1 个版本的总战力"""
    return sum(r ** i for i in range(v + 1))


def latest_share(r, v=V):
    """最新版本内容占老玩家总战力的比例"""
    return r ** v / total_power(r, v)


def versions_needed(r, target=0.85, v=V):
    """新人从最新版本往回补，补几个版本才能达到老玩家的 target"""
    tot = total_power(r, v)
    acc = 0.0
    for k in range(1, v + 2):
        acc += r ** (v - k + 1)
        if acc / tot >= target:
            return k
    return None


def devaluation(r, months=12):
    """一年前获得的内容，现在还值总战力的百分之多少（相对它当时的占比）"""
    v_then = V - months
    return (r ** v_then / total_power(r, V)) / (r ** v_then / total_power(r, v_then))


RATES = [1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40]

print(f"设定：每 {VERSION_DAYS} 天一个版本，共 {V+1} 个版本（{YEARS} 年）\n")
print(f"{'膨胀率 r':<10}{'最新版占比':>12}{'新人需补版本数':>16}{'≈ 老玩家多少天的积累':>22}"
      f"{'一年前积累的保值率':>20}")
print("-" * 74)
for r in RATES:
    k = versions_needed(r)
    print(f"{r:<10.2f}{latest_share(r):>12.1%}{k:>14} 个"
          f"{k * VERSION_DAYS:>18} 天{devaluation(r):>20.1%}")

print("""
读法
----
· 「最新版占比」越高 → 老内容越不值钱 → 新人越容易追上。
· 「新人需补版本数」是新人的追赶成本，直接对应他要肝/氪多久。
· 「一年前积累的保值率」是老玩家的痛感来源。

两列是同一个参数的正反面：**你不可能同时让老玩家保值、又让新人容易追上。**
这就是为什么"数值膨胀速度"必须由制作人拍板 —— 它是一个纯粹的取舍，没有最优解。
""")

# ==================== 出图 ====================
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
rs = np.linspace(1.001, 1.45, 120)

axes[0].plot(rs, [latest_share(r) * 100 for r in rs], lw=2.5)
axes[0].set_title("① 最新版本内容占老玩家总战力的比例")
axes[0].set_xlabel("每版本膨胀率 r"); axes[0].set_ylabel("%")
axes[0].grid(alpha=.3)

axes[1].plot(rs, [versions_needed(r) * VERSION_DAYS for r in rs], lw=2.5, color="tab:green")
axes[1].axhline(60, color="tab:red", ls="--", lw=1.5)
axes[1].text(1.01, 68, "60 天可接受线", color="tab:red", fontsize=9)
axes[1].set_title("② 新人追到老玩家 85% 需补的内容量\n（折算成老玩家当初积累的天数）")
axes[1].set_xlabel("每版本膨胀率 r"); axes[1].set_ylabel("天")
axes[1].grid(alpha=.3)

axes[2].plot(rs, [devaluation(r) * 100 for r in rs], lw=2.5, color="tab:orange")
axes[2].axhline(50, color="tab:red", ls="--", lw=1.5)
axes[2].text(1.01, 53, "腰斩线", color="tab:red", fontsize=9)
axes[2].set_title("③ 一年前的积累，现在的保值率")
axes[2].set_xlabel("每版本膨胀率 r"); axes[2].set_ylabel("%")
axes[2].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m21_power_creep.png", dpi=140)

# ---------- 找出兼顾两端的窗口 ----------
print("=== 同时满足「新人 ≤ 90 天追上」和「一年积累保值 ≥ 40%」的 r 区间 ===")
ok = [r for r in rs
      if versions_needed(r) * VERSION_DAYS <= 90 and devaluation(r) >= 0.40]
if ok:
    print(f"  r ∈ [{min(ok):.3f}, {max(ok):.3f}]"
          f"  → 折算成年化膨胀 {min(ok)**12:.1f}× ~ {max(ok)**12:.1f}×")
else:
    print("  空集 —— 说明这两个目标在当前版本节奏下不可兼得，"
          "必须改变版本周期或引入赛季重置（第 22 章）")
