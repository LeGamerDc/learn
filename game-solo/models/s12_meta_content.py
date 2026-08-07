"""
12 章：元进程与内容消耗速度

元进程（跨局的永久成长）要同时干两件互相冲突的事：

  ① **把落后的玩家推回健康带**（第 07 章：玩家散落在通关率轴上，
     掉到"太难"那一侧的会流失）
  ② **别把领先的玩家推出健康带**（推过头 = "太易" = 无聊流失）
  ③ 而且**元进程本身就是内容**（第 03 章：局外经济的 sink 几乎都是内容），
     所以给得越快，内容耗尽得越早

本模型对比两种元进程结构：
  · **均匀型**：人人有份、上限相同 —— 整条分布一起往右移
  · **地板型**：只把玩家"补到"一条基线，超过基线的人拿不到 ——
                左尾折叠到基线上，右尾原封不动

并回答：**哪一种能让更多玩家、在更长时间里，留在健康带内？**

⚠️ 第一版模型把"追赶型"实现成了"落后的人涨得快、但上限相同"，
   结果两种结构在 90 天后完全收敛（都顶到同一个上限）——
   **真正的追赶必须让上限也不同。** 这个修正本身就是本章的一半内容。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
import run_model as R

use_cjk_font()

N_PLAYERS = 3000
DAYS = 90
BAND = (0.20, 0.45)          # 第 06 章的 LTV 平顶放宽后的健康带
PG_BASE, SKILL_SCALE = 1.0195, 0.0022     # 技巧 → power_gain
META_MAX, META_RATE = 0.0035, 0.000075    # 元进程的上限与每日增速
CATCHUP = 1.6                             # 追赶型：落后一个标准差，速度乘多少

_cache = {}


def winrate(pg):
    k = round(float(np.clip(pg, 1.010, 1.032)), 4)
    if k not in _cache:
        p = dict(R.P); p["power_gain"] = k
        _cache[k] = R.batch(500, p)[0]
    return _cache[k]


rng = np.random.default_rng(23)
skill = rng.normal(0, 1, N_PLAYERS)


BASE_PG = PG_BASE + skill * SKILL_SCALE      # 每个玩家的裸强度


def meta_of(t, mode, mmax):
    """第 t 天，每个玩家的元进程加成"""
    grown = META_RATE * t * (1 + CATCHUP * np.maximum(-skill, 0))
    if mode == "均匀型":
        # 人人有份，上限相同 —— 整条分布一起右移
        return np.minimum(META_RATE * t, mmax) * np.ones(N_PLAYERS)
    # 地板型：元进程只把玩家"补到"一条基线，已经超过基线的人拿不到
    #   （这才是真正的追赶：不只是涨得快，而是**上限也不同**）
    floor = PG_BASE + mmax
    return np.minimum(grown, np.maximum(floor - BASE_PG, 0.0))


def coverage(t, mode, mmax):
    m = meta_of(t, mode, mmax)
    ws = np.array([winrate(x) for x in PG_BASE + skill * SKILL_SCALE + m])
    return (((ws >= BAND[0]) & (ws <= BAND[1])).mean(),
            (ws < BAND[0]).mean(), (ws > BAND[1]).mean(),
            (m >= mmax - 1e-12).mean())


print("=== ① 元进程的上限该定多高？两种结构给出的答案不同 ===\n")
print(f"（{N_PLAYERS} 名玩家，技巧服从正态分布，±2σ 相当于 power_gain ±"
      f"{2*SKILL_SCALE:.4f}；健康带 = 通关率 {BAND[0]:.0%}~{BAND[1]:.0%}）\n")
print(f"{'元进程上限':>12}{'占技巧跨度':>12}", end="")
for mode in ("均匀型", "地板型"):
    print(f"{mode + ' 90天均值':>16}{mode + ' 终局太易':>16}", end="")
print()
print("-" * 76)

MMAXES = [0.0004, 0.0007, 0.0010, 0.0013, 0.0016, 0.0020, 0.0026, 0.0035, 0.0050]
grid = {}
for mmax in MMAXES:
    print(f"{mmax:>12.4f}{mmax/(4*SKILL_SCALE):>12.0%}", end="")
    for mode in ("均匀型", "地板型"):
        cov = [coverage(t, mode, mmax) for t in range(0, DAYS + 1, 3)]
        grid[(mode, mmax)] = cov
        print(f"{np.mean([c[0] for c in cov]):>16.0%}{cov[-1][2]:>16.0%}", end="")
    print()

best = {m: max(MMAXES, key=lambda x: np.mean([c[0] for c in grid[(m, x)]]))
        for m in ("均匀型", "地板型")}
bu = np.mean([c[0] for c in grid[("均匀型", best["均匀型"])]])
bc = np.mean([c[0] for c in grid[("地板型", best["地板型"])]])

print(f"""
读法 —— **两种结构的性质完全不同，不只是"谁更好"**
--------------------------------------------------
**均匀型**：所有人拿同样的加成 —— **整条分布一起往右移。**
**地板型**：元进程只把玩家"补到"一条基线，超过基线的人拿不到 ——
            **分布的左尾被折叠到基线上，右尾原封不动。**

  · **均匀型最优上限 {best['均匀型']:.4f}，覆盖率 {bu:.0%}。**
    它的问题是**左右手互搏**：落后的还没进带，领先的已经被推出"太易"了。
    上限 0.0050 时有 {grid[('均匀型', 0.0050)][-1][2]:.0%} 的玩家最终变成"太简单"。
    好处是**退化平缓** —— 调错了只是效果差一点。

  · **地板型最优上限 {best['地板型']:.4f}，覆盖率 {bc:.0%}** —— **接近均匀型的两倍。**
    因为它不动右尾，所以能把左尾整个折上来而不伤到强玩家。

⚠️ **但地板型有一个悬崖，这是本节最该记住的：**

    地板 0.0010 → 覆盖率 {np.mean([c[0] for c in grid[('地板型', 0.0010)]]):.0%}
    地板 0.0020 → 覆盖率 {np.mean([c[0] for c in grid[('地板型', 0.0020)]]):.0%}，
    "太易"从 {grid[('地板型', 0.0010)][-1][2]:.0%} 跳到 {grid[('地板型', 0.0020)][-1][2]:.0%}。

    原因很直白：**地板本身如果落在健康带上方，那所有人都会被顶到带外。**
    地板型是把整个左尾"钉"在地板上的 —— **钉错位置，就是全体一起错。**

  ⇒ **⭐ 地板型元进程的唯一硬约束：
     地板对应的通关率必须落在健康带内，而且要靠近下沿**
     （给玩家留出靠技巧继续上升的空间）。

⇒ **怎么选：**

     均匀型   最优覆盖率低，但**退化平缓**   → 适合"还不知道玩家技巧分布"
     地板型   最优覆盖率高约 2 倍，但**悬崖式** → 适合"已经有真实数据"

  ⇒ **上线前用均匀型，拿到真实技巧分布后换地板型。**
    这不是妥协，是"先求稳、再求优"的正确顺序 ——
    **地板型的收益依赖于你知道健康带在哪，而那要等第 14 章的埋点数据。**

⚠️ 最后一个天花板：两种结构都没能把覆盖率做到 80% 以上。
   **元进程救不了所有人** —— 技巧分布本身太宽的时候，
   你需要的是**难度选项**（让玩家自己选档），而不是更强的元进程。
""")

track = {m: [(c[0], c[3]) for c in grid[(m, best[m])]] for m in best}

# ============================================================
# ② 内容消耗速度 vs 你的产能
# ============================================================
print("=== ② 内容消耗速度 vs 你的产能 ===\n")

# 元进程等级数 = 你做出来的内容量；玩家推进速度决定它撑多久
LEVELS = 100
print(f"（元进程共 {LEVELS} 级 = 你做出来的内容；"
      f"下表算「什么时候有一半玩家顶满」）\n")
print(f"{'元进程增速倍数':>16}{'一半玩家顶满':>14}{'90天顶满比例':>14}"
      f"{'需要的月产能':>16}")
print("-" * 62)

for k in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
    half_day = None
    for t in range(DAYS + 1):
        m = np.minimum(META_RATE * k * t * (1 + CATCHUP * np.maximum(-skill, 0)),
                       META_MAX)
        if (m >= META_MAX - 1e-12).mean() >= 0.5 and half_day is None:
            half_day = t
    m90 = np.minimum(META_RATE * k * DAYS * (1 + CATCHUP * np.maximum(-skill, 0)),
                     META_MAX)
    frac = (m90 >= META_MAX - 1e-12).mean()
    # 要让内容永远够用，每月要新增多少级
    need = LEVELS / (half_day / 30) if half_day else 0.0
    print(f"{k:>15.2f}×{(f'{half_day} 天' if half_day else '>90 天'):>14}"
          f"{frac:>14.0%}{(f'{need:.0f} 级/月' if half_day else '—'):>16}")

print(f"""
读法 —— **这是小团队最该先算的一张表**
--------------------------------------
最后一列把"内容消耗速度"翻译成了**你必须持续交付的产能**。

⇒ 三条结论：

  1. **元进程增速是你的产能约束的镜像。**
     你一个人一个月能做出多少新内容？先诚实回答，再反推增速。
     **绝大多数独立开发者的错误是按"手感"定增速，然后被更新压垮。**

  2. **广告注入会成倍放大这个压力**（第 03 章）。
     离线翻倍 + 结算翻倍能让日产出接近 2 倍，
     **等于把你的产能要求也乘了 2**。

  3. **prestige 是唯一能打破这个循环的东西**（第 11 章）：
     它用同一批内容造出新的进度曲线，**产能要求几乎为零。**
     小团队应该把它排在"做新内容"之前。
""")

# ============================================================
# ③ 程序生成的性价比
# ============================================================
print("=== ③ 手作 vs 程序生成：什么时候划算 ===\n")

print(f"{'方案':<28}{'制作成本(人日)':>16}{'产出的不同体验数':>20}{'每份体验的成本':>16}")
print("-" * 82)

# 手作：一个关卡 = 一份体验，成本固定
# 程序生成：先做 K 个"零件"，组合数爆炸，但需要额外的生成器成本
GEN_COST = 25.0        # 写生成器 + 调参的一次性成本（人日）
PIECE_COST = 1.5       # 每个零件的成本
HANDMADE_COST = 3.0    # 每个手作关卡的成本
QUALITY = 0.35         # 程序生成的组合里，只有 35% 是"真的有差别"的

for n in (10, 20, 40, 80):
    hand = n * HANDMADE_COST
    print(f"{f'手作 {n} 个关卡':<26}{hand:>16.0f}{n:>20}{hand/n:>16.2f}")
for k in (8, 12, 16, 20):
    cost = GEN_COST + k * PIECE_COST
    combos = k * (k - 1) * (k - 2) / 6 * QUALITY      # 三选组合 × 有效率
    print(f"{f'程序生成（{k} 个零件）':<26}{cost:>16.0f}{combos:>20.0f}"
          f"{cost/combos:>16.2f}")

print(f"""
读法
----
**程序生成的性价比来自组合数的立方级增长，但有两个前提：**

  · **一次性成本很高**（写生成器 + 调参，模型里 {GEN_COST:.0f} 人日）。
    **零件少于 10 个时，手作更划算。**
  · **组合的"有效率"是关键参数**（模型里 {QUALITY:.0%}）。
    如果零件之间没有真正的交互，100 种组合玩起来是同一种 ——
    **这就是第 07、08 章讲的：协同和凹性决定了组合有没有意义。**

⇒ **给小团队的判断顺序：**

    1. 先做 **prestige**（第 11 章）—— 产能要求最低
    2. 再做 **程序生成的组合**（本节）—— 一次性投入，长期收益
    3. 最后才是**手作内容** —— 成本线性，不可持续

  ⚠️ 但顺序不能反过来用：**没有足够多的、互相有交互的零件，
     程序生成只会产出"看起来不同、玩起来一样"的东西。**
     所以第 07 章那个"通用模块 + 传说件"的池子结构是本节的前置条件。
""")

# ============================================================
# 出图
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

days = np.arange(0, DAYS + 1, 3)
for mode, c in (("均匀型", "tab:gray"), ("地板型", "tab:green")):
    axes[0].plot(days, [x[0] * 100 for x in track[mode]], lw=2.5,
                 color=c, label=mode)
axes[0].set_xlabel("天"); axes[0].set_ylabel("健康带内玩家 %")
axes[0].set_title("① 地板型在最优点覆盖率高得多")
axes[0].legend(fontsize=8)

for mode, c in (("均匀型", "tab:gray"), ("地板型", "tab:green")):
    axes[1].plot(days, [x[1] * 100 for x in track[mode]], lw=2.5,
                 color=c, label=mode)
axes[1].set_xlabel("天"); axes[1].set_ylabel("元进程顶满的玩家 %")
axes[1].set_title("② 地板型让内容按需分配\n需要的人先拿到")
axes[1].legend(fontsize=8)

ns = np.arange(4, 26)
axes[2].plot(ns, ns * HANDMADE_COST / ns, "o-", lw=2,
             color="tab:red", label="手作（每份成本恒定）")
combo = ns * (ns - 1) * (ns - 2) / 6 * QUALITY
axes[2].plot(ns, (GEN_COST + ns * PIECE_COST) / np.maximum(combo, 1), "s-",
             lw=2, color="tab:blue", label="程序生成")
axes[2].set_yscale("log")
axes[2].set_xlabel("零件数量"); axes[2].set_ylabel("每份体验的成本（人日）")
axes[2].set_title("③ 程序生成的交叉点\n零件太少时手作更划算")
axes[2].legend(fontsize=8)

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s12_meta_content.png", dpi=140)
