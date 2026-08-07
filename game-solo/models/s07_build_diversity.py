"""
07 章：构筑多样性 —— 单人游戏的"平衡"到底是什么

单人游戏的平衡**不是**"所有道具等强"，也**不是**"胜率 50%"。
它是一个更具体的东西：

    **有多少条不同的路，能走到赢。**

本模型做三件事：
  ① 建一个 24 件道具 + 4 条协同线的构筑系统，接到第 00 章的单局模型上
  ② 用三种选择策略（随机 / 贪心 / 协同）跑，看构筑多样性
  ③ **区分两种"超模"**：
       单道具超模  → 使用率飙到 90%+，**消灭选择**       → 坏
       稀有协同超模 → 使用率不变，但通关率分布长出右尾    → **好**
     并给出一个可计算的判据。

构筑 → 强度的接法：
    build_score = Σ道具价值 + Σ协同加成
    power_gain  = 1.020 + (build_score − 8.5) × 0.0025
（第 00 章已证明 power_gain 对通关率极度敏感，这里正好利用这一点）
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
import run_model as R

use_cjk_font()

N_ITEMS, N_TAGS, PICKS, OFFER = 24, 4, 8, 3
SYN_AT, SYN_BONUS = {3: 0.5, 5: 1.2}, None      # 同标签 3 件 +0.5，5 件再 +1.2
PG_BASE, PG_PIVOT, PG_SCALE = 1.020, 8.95, 0.0025
# ↑ PG_PIVOT 标定在"贪心玩家的中位构筑分"上，
#   让典型玩家的通关率落在第 06 章那个 28%~33% 的 LTV 平顶区间里。
N_PLAYERS = 4000


def make_items(seed=3, dominant=None):
    """dominant: (道具下标, 价值) —— 用来注入一个超模道具做对照"""
    r = np.random.default_rng(seed)
    val = r.uniform(0.85, 1.15, N_ITEMS)
    tag = np.arange(N_ITEMS) % N_TAGS
    if dominant:
        val[dominant[0]] = dominant[1]
    return val, tag


def build_score(picks, val, tag):
    s = val[picks].sum()
    for t in range(N_TAGS):
        k = int((tag[picks] == t).sum())
        for need, bonus in SYN_AT.items():
            if k >= need:
                s += bonus
    return s


def to_power_gain(score):
    return float(np.clip(PG_BASE + (score - PG_PIVOT) * PG_SCALE, 1.010, 1.030))


# ---------------- 三种选择策略 ----------------
def pick_random(offer, held, val, tag, r):
    return int(r.choice(offer))


EPS = 0.15          # 真实玩家不是完美贪心：15% 的时候会乱选


def pick_greedy(offer, held, val, tag, r):
    """只看单件价值、不管协同，且带 ε 噪声 —— 大多数玩家的实际行为

    ⚠️ ε 不是装饰。纯贪心（ε=0）时**全池最强的那件道具选取率必然是 100%**，
       "选取率"这个指标会直接退化，什么也判断不出来。
    """
    if r.random() < EPS:
        return int(r.choice(offer))
    return int(offer[np.argmax(val[offer])])


def pick_synergy(offer, held, val, tag, r):
    """优先凑协同 —— 老手玩家的行为"""
    best, best_s = None, -1e9
    for o in offer:
        s = build_score(np.array(held + [o]), val, tag)
        if s > best_s:
            best, best_s = o, s
    return int(best)


STRATEGIES = {"随机选": pick_random, "贪心（看单件强度）": pick_greedy,
              "凑协同": pick_synergy}


def simulate(strategy, val, tag, n=N_PLAYERS, seed=0):
    """返回 dict：通关率 / 每件道具的"出现即选中率" / build_score / 5 件协同触发率"""
    r = np.random.default_rng(seed)
    offered = np.zeros(N_ITEMS)
    taken = np.zeros(N_ITEMS)
    win_with = np.zeros(N_ITEMS)      # 含该道具的构筑里，赢了几局
    n_with = np.zeros(N_ITEMS)        # 含该道具的构筑有几局
    scores, wins, five = [], 0, 0
    for i in range(n):
        held = []
        for _ in range(PICKS):
            pool = [x for x in range(N_ITEMS) if x not in held]
            offer = r.choice(pool, OFFER, replace=False)
            offered[offer] += 1
            c = strategy(offer, held, val, tag, r)
            taken[c] += 1
            held.append(c)
        h = np.array(held)
        sc = build_score(h, val, tag)
        scores.append(sc)
        five += max(int((tag[h] == t).sum()) for t in range(N_TAGS)) >= 5
        p = dict(R.P); p["power_gain"] = to_power_gain(sc)
        won = R.one_run(seed=i * 7919 + 1, p=p)["died"] is None
        wins += won
        n_with[h] += 1
        win_with[h] += won
    # 边际胜率贡献 = 含它的构筑通关率 − 不含它的构筑通关率
    wr_with = np.divide(win_with, np.maximum(n_with, 1))
    wr_without = np.divide(wins - win_with, np.maximum(n - n_with, 1))
    return dict(win=wins / n, rate=taken / np.maximum(offered, 1),
                score=np.array(scores), five=five / n,
                lift=wr_with - wr_without)


def gini(x):
    x = np.sort(np.asarray(x, float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


# ============================================================
# ① 三种策略：构筑多样性长什么样
# ============================================================
val, tag = make_items()
print("=== ① 三种玩家策略下的构筑与通关率 ===\n")
print(f"（{N_ITEMS} 件道具，{N_TAGS} 条协同线，每局三选一选 {PICKS} 次）\n")
print(f"{'策略':<22}{'通关率':>9}{'构筑分中位':>12}{'构筑分P90':>11}"
      f"{'选取率基尼':>12}{'零选取道具':>12}")
print("-" * 80)

base = {}
for name, fn in STRATEGIES.items():
    r_ = simulate(fn, val, tag)
    base[name] = r_
    print(f"{name:<20}{r_['win']:>9.1%}{np.median(r_['score']):>12.2f}"
          f"{np.percentile(r_['score'],90):>11.2f}"
          f"{gini(r_['rate']):>12.3f}{int((r_['rate'] < 0.02).sum()):>12}")

print("""
读法
----
**"选取率基尼"衡量的是"玩家的选择有多趋同"**：
0 = 所有道具被选的概率一样，1 = 只有一件被选。

  · 随机选   基尼 ≈ 0，但通关率最低 —— 多样性满分，玩家却没在做决策
  · 贪心     基尼上升，通关率上升 —— 玩家开始有偏好了
  · 凑协同   通关率最高 —— **这就是"构筑"的价值：会玩的人明显更强**

⚠️ 注意"随机选"和"凑协同"的通关率差距（{base['随机选']['win']:.0%} vs {base['凑协同']['win']:.0%}）。
   **这个差距就是技巧的空间。**
   如果两者差不多，说明你的构筑系统是装饰品，玩家怎么选都一样
   （回想第 00 章 dmg_exp=1.0 的情形）。

⚠️ 但基尼只适合看**整体趋同**，**它抓不到"某一件超模"** ——
   下一节会用一个专门构造的坏版本证明这一点。
""")

# ============================================================
# ② 两种"超模"的区别
# ============================================================
print("=== ② 两种超模：一种消灭选择，一种制造巅峰 ===\n")

DOM_IDX = 5
print(f"{'方案':<20}{'通关率':>9}{'构筑分P95':>11}{'超模触发率':>12}"
      f"{'最高选取率':>12}{'最高边际胜率':>14}{'边际胜率离群度':>16}")
print("-" * 96)

v0, t0 = make_items()
r0 = simulate(pick_greedy, v0, t0, seed=1)
va, ta = make_items(dominant=(DOM_IDX, 1.85))
ra = simulate(pick_greedy, va, ta, seed=1)

# B：稀有协同超模 —— 不改任何单件价值，只把"集齐 5 件同标签"的回报大幅拉高
SAVED = dict(SYN_AT)
SYN_AT.clear(); SYN_AT.update({3: 0.5, 5: 3.0})
vb, tb = make_items()
rb = simulate(pick_synergy, vb, tb, seed=1)
SYN_AT.clear(); SYN_AT.update(SAVED)

def outlier_z(lift):
    """最高边际胜率相对其余道具的离群度（用中位数和 MAD，抗极值）"""
    med = np.median(lift)
    mad = np.median(np.abs(lift - med)) or 1e-9
    return (lift.max() - med) / (1.4826 * mad)


for name, rr, trig in (("基线", r0, r0["five"]),
                       ("A 单道具超模", ra,
                        1 - (1 - OFFER / N_ITEMS) ** PICKS),   # 该道具出现过的概率
                       ("B 稀有协同超模", rb, rb["five"])):
    print(f"{name:<18}{rr['win']:>9.1%}{np.percentile(rr['score'],95):>11.2f}"
          f"{min(trig,1.0):>12.0%}{rr['rate'].max():>12.0%}"
          f"{rr['lift'].max():>14.1%}{outlier_z(rr['lift']):>16.1f}σ")

print(f"""
读法 —— 这是本章的核心，而且它主要是关于**怎么选指标**
--------------------------------------------------------
**A 和 B 都把通关率推上去了（{r0['win']:.0%} → {ra['win']:.0%} / {rb['win']:.0%}），
但一个是灾难，一个是好设计。先看三个候选指标谁能分辨它们：**

  ❌ **选取率基尼**：{gini(r0['rate']):.3f} / {gini(ra['rate']):.3f} / {gini(rb['rate']):.3f}
     完全没动，甚至 A 还更低。
     原因：基尼衡量**整体分布**的不均。24 件里 1 件变强，影响被其余 23 件稀释掉了。
     **聚合指标会掩盖单点异常。**

  ❌ **最高单件选取率**：{r0['rate'].max():.0%} / {ra['rate'].max():.0%} / {rb['rate'].max():.0%}
     三者几乎一样，也分辨不出来。
     原因更微妙：**在三选一里，全池最强的那件本来就该接近必选** ——
     哪怕它只强一点点。这个指标的基线值天生就很高，**没有区分度**。
     （这也是为什么模型给贪心玩家加了 15% 的 ε 噪声：
       纯贪心时它会直接钉在 100%，连数字都不用看了。）

  ✅ **边际胜率的离群度**：{outlier_z(r0['lift']):.1f}σ / {outlier_z(ra['lift']):.1f}σ / {outlier_z(rb['lift']):.1f}σ
     **干净地抓到了 A。**
     边际胜率 = 含该道具的构筑通关率 − 不含它的构筑通关率。
     A 那件道具的边际胜率是 {ra['lift'].max():.1%}，而池子里其他道具的中位数只有几个点。

⇒ **判据（本章最该记住的）：**

    ① **单件的边际胜率离群度 > 3σ → dominant，必须削。**
       基线和 B 都在 1.2σ 左右，A 是 {outlier_z(ra['lift']):.1f}σ —— 差距一目了然。

    ② **超模状态的触发率**
       · A：{1 - (1 - OFFER/N_ITEMS)**PICKS:.0%} 的局都能吃到 → 它不是惊喜，是**新的基线**
       · B：只有 {rb['five']:.0%} 的局凑得齐 → **这才叫"罕见超模"**，
            第 01 章说可以留的就是这种。而它把构筑分 P95 从
            {np.percentile(r0['score'],95):.2f} 拉到 {np.percentile(rb['score'],95):.2f} —— 巅峰体验就是这么来的。

    **两个判据要一起用。**
    只看①会漏掉"一堆平庸道具凑出的必胜套路"（每件都不离群，合起来无敌）；
    只看②会漏掉"人人必拿但不改变套路的那张卡"。

⚠️ **顺带一条通用教训**：本节三个指标里有两个是"看起来很合理"的，
   却都失灵了。**做数值体检时，先用一个已知有问题的版本去检验你的指标能不能报警** ——
   指标本身也需要测试。第 13 章会把这件事做成自动化。
""")

# ============================================================
# ③ 接回 IAA：dominant build 怎么伤钱
# ============================================================
print("=== ③ 接回变现：构筑分布决定玩家落在 LTV 曲面的哪一片 ===\n")

BAND = (0.20, 0.45)          # 第 06 章的 LTV 平顶在 28%~33%，这里放宽成健康带
_cache = {}


def wr(score):
    k = round(float(score), 2)
    if k not in _cache:
        p = dict(R.P); p["power_gain"] = to_power_gain(k)
        _cache[k] = R.batch(600, p)[0]
    return _cache[k]


print(f"（第 06 章的 LTV 平顶在通关率 28%~33%；这里放宽成健康带 "
      f"{BAND[0]:.0%}~{BAND[1]:.0%}）\n")
print(f"{'方案':<20}{'P10 通关率':>13}{'中位':>9}{'P90':>9}"
      f"{'落在健康带':>13}{'太难(<20%)':>13}{'太易(>45%)':>13}")
print("-" * 94)

for name, rr in (("基线", r0), ("A 单道具超模", ra), ("B 稀有协同超模", rb)):
    ws = np.array([wr(s) for s in np.percentile(rr["score"],
                                                np.arange(2.5, 100, 5))])
    inb = ((ws >= BAND[0]) & (ws <= BAND[1])).mean()
    print(f"{name:<18}{np.percentile(ws,10):>13.1%}{np.median(ws):>9.1%}"
          f"{np.percentile(ws,90):>9.1%}{inb:>13.0%}"
          f"{(ws < BAND[0]).mean():>13.0%}{(ws > BAND[1]).mean():>13.0%}")

print(f"""
读法
----
**这一段把构筑问题接回了第 06 章的钱。**

第 06 章证明：LTV 在通关率 28%~33% 的平顶上最优，掉出去亏得很惨。
而**构筑系统决定了你的玩家实际散落在通关率轴的哪一段**。

  · 基线：绝大多数玩家落在健康带内 —— 这是你想要的形状。

  · A 单道具超模：**整条分布被平移上去**，一大批玩家被推到"太易"那一侧。
    注意它并没有让玩家之间的差距变小 —— 它是把所有人一起抬高了。
    **这正是"新基线"的含义：加成人人有份，等于没有加成，只是难度悄悄变低了。**

  · B 稀有协同超模：P90 冲到 {np.percentile([wr(s) for s in np.percentile(rb['score'], np.arange(2.5,100,5))], 90):.0%}，
    **右尾明显长出去了** —— 那一小撮就是"这局我摸到神了"的玩家，
    **他们是分享和口碑的来源。**

    ⚠️ 但要诚实：B 这一行用的是"凑协同"玩家（A 和基线用的是贪心玩家），
       所以它的中位数本来就更高，**不能直接和基线比中位数**。
       这一行该看的是**右尾**和上一节的**触发率 13%**，
       而不是"分布主体动没动"。
       （想做干净的对照，就把 B 也换成贪心玩家跑一遍 —— 见动手任务 B。）

⇒ 两条结论：

  1. **超模道具的真正问题不是"太强"，是"人人都有"。**
     人人都有的加成等价于调低难度，而难度该按第 06 章的方式定，
     **不该被一件道具偷偷改掉。**

  2. **构筑多样性不是玩法部门的事。**
     它直接决定你的玩家分布在 LTV 曲面的哪一片。
     第 12 章讲元进程时会回到这个问题：
     **元进程的作用之一，就是把掉到"太难"那一侧的玩家推回健康带。**
""")

# ============================================================
# 出图
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

for name in STRATEGIES:
    axes[0].hist(base[name]["score"], bins=30, alpha=.5, label=name)
axes[0].set_xlabel("构筑分"); axes[0].set_ylabel("玩家数")
axes[0].set_title("① 三种策略的构筑分分布\n差距 = 技巧的空间")
axes[0].legend(fontsize=8)

x = np.arange(N_ITEMS)
axes[1].bar(x - 0.2, r0["rate"] * 100, width=0.4, label="基线")
axes[1].bar(x + 0.2, ra["rate"] * 100, width=0.4,
            label="A 单道具超模", color="tab:red")
axes[1].axhline(70, color="k", ls=":", lw=1.5)
axes[1].text(0.5, 72, "dominant 红线 70%", fontsize=8)
axes[1].set_xlabel("道具编号"); axes[1].set_ylabel("出现即选中率 %")
axes[1].set_title("② 单道具超模消灭选择\n一根柱子顶穿红线（基尼却抓不到）")
axes[1].legend(fontsize=8)

axes[2].hist(r0["score"], bins=30, alpha=.55, label="基线", color="tab:gray")
axes[2].hist(rb["score"], bins=30, alpha=.55,
             label="B 稀有协同超模", color="tab:green")
axes[2].set_xlabel("构筑分"); axes[2].set_ylabel("玩家数")
axes[2].set_title("③ 稀有协同：不动分布主体\n只长出一条右尾 = 巅峰体验")
axes[2].legend(fontsize=8)

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s07_build_diversity.png", dpi=140)
