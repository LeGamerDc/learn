"""
25 章：端到端 —— 一份完整 SLG 数值方案的生成与自检

从 6 个"产品决策"出发，自动推导出全部数值交付物：
  ① 节奏表（等级 → 达成日 → 停留天数）          第 04 章
  ② 日产出预算表（分阶段 × 分渠道）              第 07 章
  ③ 战斗参数（伤害公式 K 值、回合数校验）         第 05 章
  ④ 抽卡参数（基础概率、软硬保底）               第 13 章
  ⑤ 赛季与膨胀参数                             第 21、22 章
  ⑥ 经济体检报告                               第 08、09、11 章

改上面的 6 个决策，全部交付物会跟着重算 —— 这就是"数值方案"该有的样子。
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()
pd.set_option("display.unicode.east_asian_width", True)

# ==================================================================
#  产品决策（制作人拍板的 6 件事，第 01 章第 5 节）
# ==================================================================
DECISIONS = dict(
    品类="COK-like SLG，赛季制",
    目标生命周期天数=540,
    赛季长度=90,                 # 第 22 章
    付费深度上限=20000,           # 元，第 12 章
    集结叠加指数=0.95,            # α，第 18 章 —— 决定"人多的赢"还是"钱多的赢"
    单场战斗目标回合数=10,         # 第 05 章
)

# 节奏锚点：第 N 天玩家应该到达的主城等级（第 04 章）
ANCHORS = [(0, 1), (1, 8), (7, 16), (30, 25), (90, 31), (270, 36), (540, 40)]
MAX_LEVEL = 40

print("=" * 76)
print("SLG 数值方案（自动生成）")
print("=" * 76)
for k, v in DECISIONS.items():
    print(f"  {k:<16}{v}")

# ==================================================================
#  ① 节奏表：从锚点反推分段成本曲线
# ==================================================================
BASE_COST = 3000.0


def daily_income(level):
    return 8000 * 1.05 ** (level - 1)


def run(cost_of, days, max_level=MAX_LEVEL):
    lvl, pool, reach, timeline = 1, 0.0, {1: 0}, []
    for d in range(1, days + 1):
        pool += daily_income(lvl)
        while lvl < max_level and pool >= cost_of(lvl):
            pool -= cost_of(lvl)
            lvl += 1
            reach[lvl] = d
        timeline.append(lvl)
    return np.array(timeline), reach


def bisect(f, lo, hi, n=80):
    for _ in range(n):
        mid = (lo + hi) / 2
        if f(mid):
            lo = mid
        else:
            hi = mid
    return lo


costs, base = {}, BASE_COST
for (d0, L0), (d1, L1) in zip(ANCHORS, ANCHORS[1:]):
    def reaches(g, d0=d0, L0=L0, d1=d1, L1=L1, base=base, snap=dict(costs)):
        for L in range(L0, L1):
            snap[L] = base * g ** (L - L0)
        return run(lambda L: snap.get(L, float("inf")), d1)[0][-1] >= L1
    g = bisect(reaches, 1.0001, 3.0)
    for L in range(L0, L1):
        costs[L] = base * g ** (L - L0)
    base = costs[L1 - 1] * g

timeline, reach = run(lambda L: costs.get(L, float("inf")), DECISIONS["目标生命周期天数"])
lv = sorted(reach)
stay = {lv[i]: reach[lv[i + 1]] - reach[lv[i]] for i in range(len(lv) - 1)}

pace = pd.DataFrame([
    dict(等级=L, 达成日=reach[L], 停留天数=stay.get(L, 0),
         升级成本=round(costs.get(L, 0)))
    for L in sorted(reach) if L in stay])
pace.to_csv("../tables/25_pace.csv", index=False, encoding="utf-8-sig")

print("\n① 节奏表（节选）")
print(pace[pace["等级"].isin([5, 10, 16, 20, 25, 31, 36, 39])].to_string(index=False))
over7 = pace[pace["停留天数"] > 7]
if len(over7):
    r = over7.iloc[0]
    print(f"\n  ⚠ 单级停留首次超过 7 天：{int(r['等级'])} 级 / 第 {int(r['达成日'])} 天")
    print("     ⇒ 必须在此之前完成动机迁移（第 20 章）")

# ==================================================================
#  ② 日产出预算表
# ==================================================================
STAGES = [(1, 7, "新手期"), (8, 30, "成长期"),
          (31, 90, "中期"), (91, 540, "长线期")]
CHANNELS = {           # 新手期 成长期  中期  长线期
    "挂机产出":  [0.22, 0.30, 0.35, 0.38],
    "主线/PvE": [0.32, 0.16, 0.06, 0.02],
    "日常任务":  [0.18, 0.17, 0.15, 0.13],
    "联盟/社交": [0.03, 0.10, 0.16, 0.20],
    "资源地/PvP":[0.03, 0.09, 0.13, 0.16],
    "签到/邮件": [0.12, 0.07, 0.04, 0.03],
    "活动":     [0.10, 0.11, 0.11, 0.08],
}
alloc = pd.DataFrame(CHANNELS, index=[s[2] for s in STAGES]).T
assert np.allclose(alloc.sum(), 1.0), f"渠道占比之和不为 1:\n{alloc.sum()}"

rows = []
for d in range(1, DECISIONS["目标生命周期天数"] + 1):
    i = next(i for i, (a, b, _) in enumerate(STAGES) if a <= d <= b)
    tot = daily_income(timeline[d - 1])
    row = {"天": d, "阶段": STAGES[i][2], "日产出合计": tot}
    row.update({c: tot * r[i] for c, r in CHANNELS.items()})
    rows.append(row)
budget = pd.DataFrame(rows)
budget.to_csv("../tables/25_faucet_budget.csv", index=False,
              encoding="utf-8-sig", float_format="%.0f")

print("\n② 日产出预算表 —— 渠道占比")
print((alloc * 100).round(0).astype(int).to_string())
print(f"\n  社交渠道占比：新手期 {CHANNELS['联盟/社交'][0]:.0%}"
      f" → 长线期 {CHANNELS['联盟/社交'][3]:.0%}（动机迁移的经济基础）")

# ==================================================================
#  ③ 战斗参数：从目标回合数反推
# ==================================================================
R = DECISIONS["单场战斗目标回合数"]
# 同级对抗：EHP / DPS = R。用饱和公式，同级减伤设为 40%
SAME_LEVEL_REDUCE = 0.40
K_over_def = SAME_LEVEL_REDUCE / (1 - SAME_LEVEL_REDUCE)   # 防 = K × 该值
print(f"\n③ 战斗参数")
print(f"  伤害公式：伤害 = 攻击 × K/(K + 防御)          （第 05 章：饱和公式）")
print(f"  同级对抗目标减伤 {SAME_LEVEL_REDUCE:.0%} ⇒ 同级防御 = {K_over_def:.3f} × K")
print(f"  K 随等级变化：K(L) = 50 × L^1.5 ⇒ 40 级时 K = {50 * 40**1.5:,.0f}")
print(f"  目标回合数 {R} ⇒ 同级对抗时 生命 = {R:.0f} × 攻击 × (1−{SAME_LEVEL_REDUCE:.0%})"
      f" = {R * (1-SAME_LEVEL_REDUCE):.0f} × 攻击")
print(f"  战力 = √(EHP × DPS)                        （第 05 章）")
print(f"  属性最优配比（第 05 章模型）：攻 43% / 防 13% / 血 43%")

# ==================================================================
#  ④ 抽卡参数：从"最惨玩家的花费上限"反推
# ==================================================================
PRICE_PER_PULL = 15.0
WORST_CASE_BUDGET = 1500.0
HARD_PITY = int(WORST_CASE_BUDGET / PRICE_PER_PULL)
SOFT_START = int(HARD_PITY * 0.80)
BASE_P = 0.016
print(f"\n④ 抽卡参数（第 13 章：从最坏情况倒推）")
print(f"  单价 {PRICE_PER_PULL:.0f} 元/抽，最惨玩家预算上限 {WORST_CASE_BUDGET:,.0f} 元")
print(f"  ⇒ 硬保底 {HARD_PITY} 抽，软保底起点 {SOFT_START} 抽，基础概率 {BASE_P:.1%}")
print(f"  UP 机制 50% 歪 ⇒ 获得 UP 的最坏情况 = {HARD_PITY*2} 抽 "
      f"= {HARD_PITY*2*PRICE_PER_PULL:,.0f} 元")
print(f"  ⚠ 这个数必须 ≤ 付费深度上限（{DECISIONS['付费深度上限']:,}）—— "
      f"{'通过' if HARD_PITY*2*PRICE_PER_PULL <= DECISIONS['付费深度上限'] else '不通过'}")

# ==================================================================
#  ⑤ 赛季与膨胀
# ==================================================================
S = DECISIONS["赛季长度"]
n_season = DECISIONS["目标生命周期天数"] // S
print(f"\n⑤ 赛季与膨胀（第 21、22 章）")
print(f"  赛季长度 {S} 天 ⇒ 生命周期内 {n_season} 个赛季")
print(f"  {'✓' if S >= 60 else '✗'} 赛季长度 ≥60 天：重复博弈能建立声誉，外交系统有效（第 16 章）")
print(f"  重置：领土 / 赛季货币 / 排名 / 部分兵力      保留：武将 / 收藏 / 称号 / 社交关系")
r_month = 1.10
print(f"  版本膨胀 r = {r_month}/月 ⇒ 年化 {r_month**12:.1f}×")
print(f"  单赛季内膨胀 = {r_month**(S/30):.2f}×（赛季重置吸收了跨赛季的断层）")

# ==================================================================
#  ⑥ 经济体检
# ==================================================================
GOLD_DECAY = 0.06          # 比例型 sink（第 08 章）
steady = (1 - GOLD_DECAY) / GOLD_DECAY
print(f"\n⑥ 经济体检（第 08、09 章）")
print(f"  比例型 sink：日损耗 {GOLD_DECAY:.0%} ⇒ 稳态存量 = (1−d)/d = {steady:.1f} 天的产出")
print(f"  {'✓' if 5 <= steady <= 20 else '✗'} 落在健康区间 5~20 天")
print(f"  层级型 sink：主城升级（成本随等级指数增长，40 级封顶）")
print(f"  ⚠ 40 级封顶后层级 sink 失效 ⇒ 必须靠比例型 sink 兜底（第 00 章实验 A）")
print(f"  深度 sink：联盟建设捐献 + 限定外观（不给战力，避免放大付费差距，第 11 章）")

alpha = DECISIONS["集结叠加指数"]
whale_ratio = 12.0
need = whale_ratio ** (1 / alpha)
print(f"\n  生态（第 18、19 章）：α = {alpha}")
print(f"  大 R 战力 ≈ 免费玩家 {whale_ratio:.0f}× ⇒ 需 {need:.0f} 名免费玩家集结才能打赢")
print(f"  {'✓' if need <= 100 else '✗'} ≤100 人（一个联盟能组织起来）")

# ==================================================================
#  出图
# ==================================================================
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
axes[0].plot(np.arange(1, len(timeline) + 1), timeline, lw=2, color="tab:green")
for d, L in ANCHORS[1:]:
    axes[0].plot(d, L, "r*", ms=13)
for k in range(1, n_season + 1):
    axes[0].axvline(k * S, color="tab:blue", ls=":", lw=1)
axes[0].set_title("① 主城等级曲线\n红星=锚点，蓝线=赛季边界")
axes[0].set_xlabel("天"); axes[0].set_ylabel("等级")

axes[1].bar(pace["等级"], pace["停留天数"], color="tab:orange")
axes[1].axhline(7, color="tab:red", ls="--")
axes[1].set_title("② 单级停留天数\n红线以上 = 等级系统不再是主要动力")
axes[1].set_xlabel("等级"); axes[1].set_ylabel("天")

frac = budget[list(CHANNELS)].div(budget["日产出合计"], axis=0)
axes[2].stackplot(budget["天"], *[frac[c] for c in CHANNELS],
                  labels=list(CHANNELS), alpha=.85)
axes[2].set_title("③ 投放渠道构成的迁移")
axes[2].set_xlabel("天"); axes[2].legend(fontsize=6, loc="lower right")

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/m25_full_spec.png", dpi=140)

print("\n" + "=" * 76)
print("交付物已生成：")
print("  tables/25_pace.csv           节奏表")
print("  tables/25_faucet_budget.csv  日产出预算表")
print("  figures/m25_full_spec.png    方案图")
print("=" * 76)
