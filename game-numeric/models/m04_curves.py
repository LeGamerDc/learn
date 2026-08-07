"""
04 章：成长曲线
① 四种基本曲线的形状与"感知成长"
② 从目标时长反推成本曲线（真实项目里最常做的一件事）
   先演示单一指数曲线为什么钉不住多个锚点，再用分段曲线解决。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

# ==================== 第一部分：四种曲线 ====================
t = np.arange(2, 101)          # 从 2 开始，避免 ln(1)=0 导致对数曲线取 log 时除零
curves = {
    "线性  a·t":       3.0 * t,
    "多项式 a·t²":      0.03 * t ** 2,
    "指数  a·1.05^t":   1.0 * 1.05 ** t,
    "对数  a·ln(t)":    60.0 * np.log(t),
}

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
for name, y in curves.items():
    axes[0].plot(t, y, lw=2, label=name)
axes[0].set_title("① 四种基本曲线（同一坐标）")
axes[0].set_xlabel("时间"); axes[0].set_ylabel("战力")
axes[0].legend(); axes[0].grid(alpha=.3); axes[0].set_ylim(0, 400)

# 感知成长 ≈ 相对增量 = d(ln y)/dt。第 02 章的结论：人感知的是比例，不是绝对值。
for name, y in curves.items():
    axes[1].plot(t[1:], np.diff(np.log(y)), lw=2, label=name)
axes[1].set_title("② 感知成长 = 相对增量 d(ln 战力)/dt\n只有指数曲线是水平线")
axes[1].set_xlabel("时间"); axes[1].set_ylabel("每天感觉变强了多少（比例）")
axes[1].set_ylim(0, .25); axes[1].legend(); axes[1].grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/m04_curves.png", dpi=140)
plt.close()

# ==================== 第二部分：从目标时长反推 ====================
# 需求："第 1 天到 10 级，第 30 天到 40 级，第 180 天到 60 级"
ANCHORS = [(0, 1), (1, 10), (30, 40), (180, 60)]
DAYS, MAX_LEVEL, BASE_COST = 180, 60, 20.0


def daily_exp(level):
    """日产出经验，随等级缓慢提升"""
    return 1000 * 1.04 ** (level - 1)


def run(cost_of_level, days=DAYS, max_level=MAX_LEVEL):
    """给定 cost_of_level(L) -> 升到 L+1 的花费，模拟每天等级"""
    lvl, pool, timeline, reach = 1, 0.0, [], {1: 0}
    for d in range(1, days + 1):
        pool += daily_exp(lvl)
        while lvl < max_level and pool >= cost_of_level(lvl):
            pool -= cost_of_level(lvl)
            lvl += 1
            reach[lvl] = d
        timeline.append(lvl)
    return np.array(timeline), reach


def bisect(f, lo, hi, iters=90):
    """找最大的 x 使 f(x) 为真（f 单调：x 越小越容易为真）"""
    for _ in range(iters):
        mid = (lo + hi) / 2
        if f(mid):
            lo = mid
        else:
            hi = mid
    return lo


# ---------- 方案 A：单一指数成本曲线 ----------
gA = bisect(lambda g: run(lambda L: BASE_COST * g ** (L - 1))[0][-1] >= MAX_LEVEL,
            1.001, 2.0)
tlA, reachA = run(lambda L: BASE_COST * gA ** (L - 1))
print(f"方案 A（单一指数，g={gA:.4f}）：", end="")
print("  ".join(f"第{d}天 {tlA[d-1]}级(目标{L})" for d, L in ANCHORS[1:]))

# ---------- 方案 B：分段成本曲线 ----------
# 每段独立求一个增长率，段首成本承接上一段段尾，保证连续
seg_growth, costs, base = [], {}, BASE_COST
for (d0, L0), (d1, L1) in zip(ANCHORS, ANCHORS[1:]):
    def reaches(g, d0=d0, L0=L0, d1=d1, L1=L1, base=base, costs=dict(costs)):
        for L in range(L0, L1):
            costs[L] = base * g ** (L - L0)
        tl, _ = run(lambda L: costs.get(L, float("inf")), days=d1)
        return tl[-1] >= L1
    g = bisect(reaches, 1.0001, 3.0)
    for L in range(L0, L1):
        costs[L] = base * g ** (L - L0)
    base = costs[L1 - 1] * g          # 下一段的段首成本，承接上一段
    seg_growth.append((L0, L1, g))

tlB, reachB = run(lambda L: costs.get(L, float("inf")))
print(f"方案 B（分段）：", end="")
print("  ".join(f"第{d}天 {tlB[d-1]}级(目标{L})" for d, L in ANCHORS[1:]))
print("\n分段增长率：")
for L0, L1, g in seg_growth:
    print(f"  {L0:>2}→{L1:>2} 级：每级成本 ×{g:.4f}"
          f"    首级成本 {costs[L0]:>10,.0f}")

# 每级停留天数 = 第 00 章"锯齿宽度"的正式版本
lv = sorted(reachB)
stay = {lv[i]: reachB[lv[i + 1]] - reachB[lv[i]] for i in range(len(lv) - 1)}

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
axes[0].plot(np.arange(1, DAYS + 1), tlA, lw=2, ls="--", color="tab:red",
             label=f"A 单一指数 g={gA:.3f}")
axes[0].plot(np.arange(1, DAYS + 1), tlB, lw=2, color="tab:green", label="B 分段曲线")
for d, L in ANCHORS[1:]:
    axes[0].plot(d, L, "r*", ms=15, zorder=5)
axes[0].set_title("③ 红星是目标锚点：单一指数只能钉住最后一个")
axes[0].set_xlabel("天"); axes[0].set_ylabel("等级")
axes[0].legend(); axes[0].grid(alpha=.3)

axes[1].bar(list(stay), list(stay.values()), color="tab:orange")
for _, L1, _ in seg_growth[:-1]:
    axes[1].axvline(L1, color="tab:blue", ls=":", lw=1.5)
axes[1].set_title("④ 每级停留天数：玩家真正感受到的节奏\n（蓝色虚线 = 分段边界）")
axes[1].set_xlabel("等级"); axes[1].set_ylabel("停留天数"); axes[1].grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/m04_pacing.png", dpi=140)

print("\n交付给团队的节奏表（节选）")
print(f"{'等级':<6}{'达成日':<8}{'停留天数':<10}{'升级成本':>14}")
for L in [5, 10, 20, 30, 40, 50, 55, 59]:
    if L in reachB and L in stay:
        print(f"{L:<6}{reachB[L]:<8}{stay[L]:<10}{costs.get(L, 0):>14,.0f}")
