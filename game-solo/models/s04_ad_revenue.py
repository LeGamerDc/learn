"""
04 章：IAA 收入的数学 —— 从 ARPDAU 到回本

    日收入   = DAU × IPU × eCPM ÷ 1000 × 分成
    ARPDAU   = IPU × eCPM ÷ 1000              （流水口径）
    LTV(D)   = Σ(d=0..D) 留存(d) × ARPDAU_到手
    回本      = LTV / CPA > 1

本模型回答四个问题：
  ① 一个用户到底值多少钱？（LTV 拆解）
  ② 四个杠杆（IPU / eCPM / 次留 / 衰减斜率）哪个最值得投入？
  ③ 给定买量成本，我需要多少 IPU 和多少次留才能回本？（回本线）
  ④ 微信的"广告金"激励，实际把回本线往下压了多少？

⚠️ 本模型的 eCPM、CPA 都是**量级参考**，会随时间显著变化。
   课程教的是公式与取舍结构，具体数字请自行核实当期口径。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

# ---------------- 基准假设 ----------------
IPU = 6.0             # 人均广告展示次数 / 天
ECPM = 60.0           # 元 / 千次展示【行业口径，需自行核实】
SHARE = 0.50          # 【实证】微信小游戏开发者分成 50%
R1 = 0.40             # 次留
DECAY = 0.504         # 留存衰减斜率（由 次留40% / 7留15% / 30留6% 拟合）
WINDOW = 90           # LTV 计算窗口（天）

# 【实证】2026 年注册激励：首 30 天广告流水的 40%，以广告金返还（只能买量）
GRANT_RATE = 0.40
GRANT_WINDOW = 30


def retention(d, r1=R1, a=DECAY):
    """幂律留存曲线。d=0 是安装当天，留存 100%"""
    return np.where(d == 0, 1.0, r1 * np.maximum(d, 1) ** (-a))


def active_days(days=WINDOW, r1=R1, a=DECAY):
    """窗口内的累计活跃天数 = Σ 留存(d)"""
    return retention(np.arange(days + 1), r1, a).sum()


def ltv(days=WINDOW, ipu=IPU, ecpm=ECPM, r1=R1, a=DECAY, share=SHARE):
    """到手 LTV（现金口径）"""
    return active_days(days, r1, a) * ipu * ecpm / 1000 * share


def grant(ipu=IPU, ecpm=ECPM, r1=R1, a=DECAY):
    """广告金：首 30 天**流水**的 40%（注意是流水，不是到手）"""
    return active_days(GRANT_WINDOW, r1, a) * ipu * ecpm / 1000 * GRANT_RATE


# ==================== ① 一个用户值多少钱 ====================
print("=== ① 一个用户到底值多少钱 ===\n")
print(f"假设：IPU {IPU:.0f} 次/天，eCPM {ECPM:.0f} 元，分成 {SHARE:.0%}，"
      f"次留 {R1:.0%}，衰减 {DECAY:.3f}\n")

arpdau_gross = IPU * ECPM / 1000
print(f"{'流水 ARPDAU':<22}{arpdau_gross:>10.3f} 元")
print(f"{'到手 ARPDAU':<22}{arpdau_gross * SHARE:>10.3f} 元   ← 所有商业决策的锚")
print()
for D in (1, 7, 30, 90, 180):
    print(f"{'累计活跃天数（' + str(D) + '天窗口）':<26}{active_days(D):>8.2f} 天"
          f"      到手 LTV {ltv(D):>6.2f} 元")

print(f"""
读法
----
一个用户在 90 天里总共只活跃 {active_days(90):.1f} 天，给你带来 {ltv(90):.2f} 元现金。
**先把这个量级刻进脑子：一个买来的用户，一辈子值一两块钱。**

关于窗口，两件事：

  · 前 7 天赚到 90 天的 {ltv(7)/ltv(90):.0%}，前 30 天赚到 {ltv(30)/ltv(90):.0%}。
    幂律留存有长尾，但它来得很慢 —— 90 天到 180 天只多赚 {ltv(180)/ltv(90)-1:.0%}。

  · **实践中要用 30 天窗口做决策**，原因不是长尾不存在，是：
      1. 买量的现金流压力在前 30 天，你等不起 90 天；
      2. 微信的广告金激励窗口正好是 30 天（见 ④），平台也是这么算的。

⚠️ 用 90 天 LTV 去论证"我这个 CPA 出得起"，是 IAA 新手最常见的自欺。
""")

# ==================== ② 四个杠杆哪个最值得投入 ====================
print("=== ② 四个杠杆：各提升 10%，LTV 涨多少 ===\n")
base = ltv()
levers = [
    ("IPU（多加广告点位）",        ltv(ipu=IPU * 1.1)),
    ("eCPM（优化人群/点位质量）",   ltv(ecpm=ECPM * 1.1)),
    ("次留（改前 3 分钟体验）",     ltv(r1=R1 * 1.1)),
    ("衰减斜率（加长线内容）",      ltv(a=DECAY * 0.9)),
]
print(f"{'杠杆':<30}{'新 LTV':>10}{'提升':>10}")
print("-" * 52)
for name, v in levers:
    print(f"{name:<28}{v:>10.2f}{v/base - 1:>10.1%}")

print(f"""
读法 —— 这个结果本身就是一条结论
--------------------------------
**四个杠杆几乎都是线性的，没有一个能以小博大。**

  IPU / eCPM   严格线性（它们直接乘在 ARPDAU 上）
  次留          略低于线性（因为安装当天的留存恒为 100%，不受它影响）
  衰减斜率      **唯一略超线性的**，因为它作用在整条曲线的形状上

⇒ **IAA 是纯粹的规模生意，没有捷径。**
   这和 F2P 有本质区别：F2P 里 0.1% 的鲸鱼可能贡献一半收入，
   付费深度是个长尾杠杆；**IAA 每个用户的价值上限就是 IPU × eCPM，封顶的。**

⇒ 实践含义：**别指望某个"神点位"救活变现。**
   要么把四个杠杆各推一点（复利），要么在买量成本上做文章。
""")

# ==================== ③ 回本线 ====================
print("=== ③ 回本线：给定买量成本，需要多少 IPU 和次留 ===\n")

ipu_grid = np.arange(2, 15, 1.0)
r1_grid = np.arange(0.20, 0.61, 0.05)
CPAS = (1.5, 3.0, 5.0)

print(f"（eCPM {ECPM:.0f} 元，分成 {SHARE:.0%}，90 天窗口，**只算现金、不含广告金**）\n")
print(f"{'次留':>6}", end="")
for ipu in ipu_grid[::2]:
    print(f"{'IPU=' + str(int(ipu)):>9}", end="")
print("   ← 单元格 = 到手 LTV(90天)，元")
print("-" * 66)
for r1 in r1_grid:
    print(f"{r1:>6.0%}", end="")
    for ipu in ipu_grid[::2]:
        print(f"{ltv(ipu=ipu, r1=r1):>9.2f}", end="")
    print()

print(f"\n{'买量成本 CPA':<16}{'需要的 LTV':>12}{'次留 40% 时需要的 IPU':>24}")
print("-" * 54)
for cpa in CPAS:
    need_ipu = cpa / (active_days() * ECPM / 1000 * SHARE)
    g = grant(ipu=need_ipu)
    need_ipu_g = cpa / (active_days() * ECPM / 1000 * SHARE
                        + active_days(GRANT_WINDOW) * ECPM / 1000 * GRANT_RATE)
    print(f"{cpa:>13.1f} 元{cpa:>11.2f} 元{need_ipu:>20.1f} 次"
          f"   （算上广告金：{need_ipu_g:.1f} 次）")

print(f"""
读法
----
**这张表是你的产品定位工具。**

  · 次留 40%、IPU 6 → 到手 LTV {ltv():.2f} 元。
    CPA 超过 {ltv():.2f} 元就是亏本买量。
  · 想扛住 CPA 3 元，次留 40% 的话需要 IPU ≈ {3.0/(active_days()*ECPM/1000*SHARE):.1f} 次
    —— 那已经是**行业头部水平**（公开分享里做到 11~12 次的是百万 DAU 产品）。

⇒ **绝大多数 IAA 小游戏做不到"纯现金买量回本"。**
   这不是你的产品差，是这个模式的结构就是这样。
   活下来的路只有三条：
     1. 自然量 / 社交裂变（CPA 趋近 0）—— 微信生态最大的价值所在
     2. 平台激励（广告金，见 ④）
     3. 混合变现（加 IAP：去广告礼包、月卡）—— 第 05 章
""")

# ==================== ④ 广告金把回本线压低了多少 ====================
print("=== ④ 广告金激励的实际效果 ===\n")
print(f"【实证】2026 年注册激励：首 {GRANT_WINDOW} 天广告**流水**的 {GRANT_RATE:.0%}，")
print("        以广告金形式返还（只能用于买量，365 天内有效）\n")

cash = ltv()
g = grant()
print(f"{'现金 LTV（90天到手）':<30}{cash:>10.2f} 元")
print(f"{'广告金（首30天流水的40%）':<30}{g:>10.2f} 元")
print(f"{'合计可用价值':<30}{cash + g:>10.2f} 元   ← 提升 {g/cash:.0%}")
print(f"""
⚠️ 但广告金**不是利润，是只能买量的代金券**。所以要分两条线记账：

  现金线：{cash:.2f} 元/用户  → 决定你能不能盈利
  买量线：{cash:.2f} + {g:.2f} = {cash + g:.2f} 元/用户  → 决定你能出多高的 CPA

  如果 CPA 在 {cash:.2f} ~ {cash + g:.2f} 元之间，你的状态是：
  **规模能滚起来，但账上不赚钱。**
  这正是平台想要的——它在补贴"买量→变现→再买量"这个循环本身。

⇒ 做决策时永远问一句：**我是在优化现金线还是买量线？**
""")

# ==================== 出图 ====================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

# ① 留存曲线与累计 LTV
d = np.arange(0, WINDOW + 1)
axes[0].plot(d, retention(d) * 100, lw=2.5, color="tab:blue", label="留存率")
axes[0].set_xlabel("天"); axes[0].set_ylabel("留存 %", color="tab:blue")
ax2 = axes[0].twinx()
cum = np.cumsum(retention(d)) * IPU * ECPM / 1000 * SHARE
ax2.plot(d, cum, lw=2.5, color="tab:red", ls="--", label="累计 LTV")
ax2.set_ylabel("累计到手 LTV（元）", color="tab:red")
axes[0].axvline(30, color="k", ls=":", lw=1.2)
axes[0].text(32, 60, f"30 天已赚到\n{ltv(30)/ltv(90):.0%}", fontsize=9)
axes[0].set_title("① 幂律留存的长尾很薄\n钱基本在前 30 天赚完")

# ② 回本热力图
LT = np.array([[ltv(ipu=i, r1=r) for i in ipu_grid] for r in r1_grid])
im = axes[1].imshow(LT, origin="lower", aspect="auto", cmap="RdYlGn",
                    extent=[ipu_grid[0], ipu_grid[-1],
                            r1_grid[0] * 100, r1_grid[-1] * 100])
for cpa, c in zip(CPAS, ("k", "b", "purple")):
    axes[1].contour(ipu_grid, r1_grid * 100, LT, levels=[cpa],
                    colors=c, linewidths=2.2)
    axes[1].plot([], [], color=c, lw=2.2, label=f"CPA {cpa} 元回本线")
axes[1].set_xlabel("IPU（次/天）"); axes[1].set_ylabel("次留 %")
axes[1].set_title("② 回本线\n线的右上方才能靠现金回本")
axes[1].legend(fontsize=8, loc="upper left")
plt.colorbar(im, ax=axes[1], label="到手 LTV(90天) 元")

# ③ 四个杠杆
names = [n.split("（")[0] for n, _ in levers]
gains = [(v / base - 1) * 100 for _, v in levers]
axes[2].barh(names, gains, color=["tab:blue", "tab:cyan", "tab:orange", "tab:red"])
axes[2].axvline(10, color="k", ls=":", lw=1.5)
axes[2].text(10.1, -0.4, "线性参考线 +10%", fontsize=8, rotation=90)
axes[2].set_xlabel("LTV 提升 %")
axes[2].set_title("③ 各提升 10% 的效果\n几乎全是线性——没有捷径")
axes[2].grid(alpha=.3, axis="x")

axes[0].grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s04_ad_revenue.png", dpi=140)
