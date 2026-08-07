"""
11 章：离线收益与放置数学

离线收益是放置类唯一的、也是最强的回访钩子。它只有三个参数：

    离线效率（离线时拿到在线的百分之几）
    离线上限（最多累积几小时）
    翻倍广告（看广告把这一次的离线收益 ×2）

本模型算三件事：
  ① **离线上限决定玩家一天上线几次** —— 也就决定了你的会话数，进而决定 IPU
  ② **离线翻倍广告的价值**：它买的不只是 IPU，还有 DAU
  ③ **prestige（重置换永久加成）的最优周期**

第 ③ 段用的是 Kongregate《The Math of Idle Games》那套指数成本/产出框架。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

R_HOUR = 100.0        # 在线时每小时的基础产出
OFF_EFF = 0.50        # 离线效率：离线只拿在线的 50%
SLEEP_H = 8.0         # 睡眠时长


def day_gaps(n_logins):
    """一天上线 n 次时的间隔序列：一段睡眠 + 白天均分"""
    awake = 24.0 - SLEEP_H
    if n_logins <= 1:
        return [24.0]
    return [SLEEP_H] + [awake / (n_logins - 1)] * (n_logins - 1)


def daily_offline(cap, n_logins):
    """一天通过离线收益拿到的总量"""
    return sum(min(g, cap) for g in day_gaps(n_logins)) * OFF_EFF * R_HOUR


# ============================================================
# ① 离线上限决定玩家一天上线几次
# ============================================================
CAPS = [1, 2, 4, 8, 12, 24]
LOGINS = [2, 3, 4, 6, 8]

print("=== ① 离线上限 → 玩家一天上线几次 ===\n")
print(f"（离线效率 {OFF_EFF:.0%}，睡眠 {SLEEP_H:.0f} 小时；"
      f"表格 = 一天拿到的离线收益）\n")
print(f"{'离线上限':>10}", end="")
for k in LOGINS:
    print(f"{'上线' + str(k) + '次':>11}", end="")
print(f"{'2→3次的增益':>14}{'睡眠捕获率':>12}{'判断':>16}")
print("-" * 100)

motive, capture = {}, {}
for cap in CAPS:
    print(f"{str(cap) + 'h':>10}", end="")
    vals = [daily_offline(cap, k) for k in LOGINS]
    for v in vals:
        print(f"{v:>11.0f}", end="")
    gain = vals[1] / vals[0] - 1
    cap_rate = min(cap, SLEEP_H) / SLEEP_H
    motive[cap], capture[cap] = gain, cap_rate
    if cap_rate < 1.0:
        tag = "睡眠被浪费"
    elif gain < 0.10:
        tag = "没有回访动机"
    else:
        tag = "← 两者兼得"
    print(f"{gain:>14.0%}{cap_rate:>12.0%}{tag:>16}")

print(f"""
读法 —— **离线上限是一个 DAU 旋钮，不是一个"福利"旋钮**
--------------------------------------------------------
两个要同时满足的条件，正好把答案夹在一个点上：

  **① 回访动机** = "一天上线 2 次改成 3 次能多拿多少"
     当上限**小于所有间隔**时，收益严格正比于上线次数 —— 增益恒为 50%，**动机最强**。
     上限一旦超过睡眠时长（{SLEEP_H:.0f}h），睡眠那一段就吃不满了，增益开始掉：
     12h 时降到 {motive[12]:.0%}，24h 时归零（**玩家一天来一次就够了**）。

  **② 睡眠捕获率** = 睡醒那次拿到了睡眠时长的百分之几。
     上限低于 {SLEEP_H:.0f}h 时，**玩家睡一觉在亏钱** —— 早上打开会很失望，
     而"早上打开"恰恰是一天里最重要的那次回访。

⇒ **两条曲线的交点就是答案：离线上限 ≈ 睡眠时长（6~10 小时）。**

    · 低于它 → 睡眠被浪费，最重要的那次回访体验很差
    · 高于它 → 回访动机开始下降，玩家一天只来一次

  **这不是经验值，是这两个约束夹出来的。**
  也解释了为什么市面上放置类游戏的离线上限几乎都落在 8~12 小时。

⚠️ **这一条对 IAA 至关重要，因为会话数直接乘在 IPU 上。**
   第 05 章的意愿模型是**按会话**建的：一个会话有一份意愿预算。
   玩家一天来 3 次 vs 1 次，**广告观看次数差的不是 3 倍也不是 1 倍，
   而是"3 份会话预算"和"1 份会话预算"的差别** —— 因为疲劳会在会话内累积，
   跨会话会重置。

   ⇒ **拆分会话是提高 IPU 最"干净"的手段**：它不加广告倍率、
     不吃内容寿命，只是把同样的注意力分成几次用。
""")

# ============================================================
# ② 离线翻倍广告：它同时买 IPU 和 DAU
# ============================================================
print("=== ② 离线翻倍广告的两重价值 ===\n")

CAP = 8.0
base3 = daily_offline(CAP, 3)
print(f"（离线上限取甜点区 {CAP:.0f}h，玩家一天上线 3 次）\n")
print(f"{'方案':<26}{'日离线收益':>12}{'相对基线':>10}{'广告次数/天':>14}")
print("-" * 66)
print(f"{'不看广告':<24}{base3:>12.0f}{1.0:>10.2f}×{0:>14.0f}")
for n_ad, label in ((1, "只在睡醒那次翻倍"), (3, "每次上线都翻倍")):
    gaps = sorted(day_gaps(3), reverse=True)[:n_ad]
    extra = sum(min(g, CAP) for g in gaps) * OFF_EFF * R_HOUR
    print(f"{label:<24}{base3 + extra:>12.0f}{(base3+extra)/base3:>10.2f}×"
          f"{n_ad:>14.0f}")

print(f"""
读法
----
**只在"睡醒那次"翻倍，就拿到了大部分价值** ——
因为睡眠那一段是唯一能吃满上限的间隔，白天几段都不足 {CAP:.0f} 小时。

⇒ **两条设计含义：**

  1. **离线翻倍应该按"这次能翻多少"动态展示**，而不是固定文案。
     睡醒那次弹"+800"，白天那次弹"+280" —— 玩家自己会判断值不值。
     **弹一个不值的广告，比不弹更伤**（它会拉低玩家对所有广告点位的预期）。

  2. **它是第 05 章说的"会话开头点位"的最佳人选**：
     意愿预算满、价值最高、且**它本身就是玩家打开游戏的理由**。

⚠️ 但别忘了第 03、10 章那条红线：**离线翻倍是吃内容寿命最狠的点位。**
   上面"每次上线都翻倍"那一行让日产出接近 2 倍 ——
   按第 03 章的模型，那会把内容寿命砍掉近一半。

   ⇒ **建议：每天限 1~2 次，并且优先给最大的那一段。**
     这既是内容预算的要求，也恰好是玩家体验最好的做法 —— 两者难得地一致。
""")

# ============================================================
# ③ prestige：重置换永久加成的最优周期
# ============================================================
print("=== ③ prestige：多久重置一次最划算 ===\n")

# 一轮之内，进度会**饱和** —— 因为升级成本涨得比产出快（第 03、10 章都算过）：
#     P(c) = P_MAX · c / (c + T_HALF)          饱和公式
# 重置有**固定开销**：重来一遍早期流程要花 OVERHEAD 小时，跟本轮玩多久无关。
# prestige 收益按 √P 结算（√ = 递减，第 10 章那条通用规律的药）。
P_MAX, T_HALF, OVERHEAD, B = 100.0, 8.0, 3.0, 0.01
HORIZON = 24 * 60          # 折算成 60 天的"有效小时"


def total_points(cycle_h, horizon=HORIZON):
    """每 cycle_h 小时重置一次，horizon 小时后累计的 prestige 点数"""
    pts, t = 0.0, 0.0
    while t + cycle_h + OVERHEAD <= horizon:
        mult = 1 + B * pts                                  # 永久加成
        p = P_MAX * mult * cycle_h / (cycle_h + T_HALF)      # 本轮进度（饱和）
        pts += np.sqrt(p)
        t += cycle_h + OVERHEAD
    return pts


print(f"（一轮内进度饱和：半效时间 {T_HALF:.0f}h；每次重置有 {OVERHEAD:.0f}h 的"
      f"'重爬早期'固定开销）\n")
print(f"{'重置周期':>10}{'总重置次数':>12}{'本轮进度(满额%)':>18}"
      f"{'60 天后的加成':>16}{'相对最优':>10}")
print("-" * 70)
cycles = [0.5, 1, 1.5, 2, 3, 4, 6, 8, 12, 24]
res = {c: total_points(c) for c in cycles}
best = max(res, key=res.get)
for c in cycles:
    n = int(HORIZON // (c + OVERHEAD))
    frac = c / (c + T_HALF)
    print(f"{str(c) + 'h':>10}{n:>12}{frac:>18.0%}"
          f"{1 + B * res[c]:>16.1f}{res[c]/res[best]:>10.1%}")

print(f"""
读法
----
**存在一个明确的最优重置周期（本模型是 {best} 小时），两边都会变差：**

  · **周期太短** → 每轮只吃到 {0.5/(0.5+T_HALF):.0%} 的进度，
    而每次重置还要付 {OVERHEAD:.0f} 小时的"重爬早期"固定开销 —— **开销吃掉了收益**
  · **周期太长** → 进度早就饱和了（{24/(24+T_HALF):.0%} vs {best/(best+T_HALF):.0%}，
    多花 {24-best:.0f} 小时只多拿一点点），**你在浪费时间等一个已经不涨的数**

⚠️ 注意这个最优点是**两个机制夹出来的**，缺一个就不存在：
   只有饱和、没有重置开销 → 越短越好；
   只有开销、没有饱和     → 越长越好。
   **设计 prestige 时这两样必须同时有。**

⇒ **prestige 的设计要点：**

  1. **最优周期必须是"玩家算得出来、但要想一想"的。**
     如果最优是"随时重置"或"永远别重置"，这个系统就没有决策。
  2. **加成用 √P 而不是 P**（第 10 章那条通用规律的又一次应用）：
     线性加成会让"攒一大波再重置"永远最优，**同样是消灭决策。**
  3. **每一轮都要比上一轮快** —— 这是 prestige 的爽点来源：
     "上次花 6 小时的进度，这次 40 分钟就到了"。

⚠️ **prestige 对 IAA 的特殊价值：它是一个几乎免费的内容延长器。**
   第 03 章证明内容寿命是留存的天花板，而 prestige **用同一批内容
   造出了新的进度曲线** —— 这是小团队最划算的长线手段。

   代价：**它只对"愿意重复"的那部分玩家有效。**
   第 12 章会讲怎么判断你的玩家里有多少这种人。
""")

# ============================================================
# 出图
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

for k in LOGINS:
    axes[0].plot(CAPS, [daily_offline(c, k) for c in CAPS], "o-", lw=2,
                 label=f"一天上线 {k} 次")
axes[0].set_xlabel("离线上限（小时）"); axes[0].set_ylabel("日离线收益")
axes[0].set_title("① 上限越大，多上线越没用\n线挤在一起 = 回访动机消失")
axes[0].legend(fontsize=8)

axes[1].plot(CAPS, [motive[c] * 100 for c in CAPS], "o-", lw=2.5, color="tab:red")
axes[1].axvspan(6, 10, color="tab:green", alpha=.15)
axes[1].text(6.2, max(motive.values()) * 60, "甜点区 6~10h", fontsize=9,
             color="tab:green")
axes[1].set_xlabel("离线上限（小时）"); axes[1].set_ylabel("2→3 次上线的收益增益 %")
axes[1].set_title("② 回访动机强度\n它就是你的会话数旋钮")

axes[2].plot(cycles, [res[c] for c in cycles], "o-", lw=2.5, color="tab:blue")
axes[2].axvline(best, color="k", ls=":", lw=1.5)
axes[2].set_xlabel("重置周期（小时）"); axes[2].set_ylabel("60 天后的 prestige 点数")
axes[2].set_title(f"③ prestige 有内部最优（{best}h）\n饱和 + 重置开销，两者夹出来的")

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s11_offline.png", dpi=140)
