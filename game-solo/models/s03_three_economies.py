"""
03 章：三层经济 —— 局内 / 局外 / 广告

IAA 小游戏的经济有三层，**各自的健康指标完全不同**，混为一谈是新手最大的坑：

  ① 局内经济（每局清零）
     不需要 sink —— 结算就是终极 sink。
     健康指标不是"回收率"，是 **"买得起比例"**：
     玩家想买的东西里，买得起几成？全买得起 = 钱不是约束 = 决策没有分量。

  ② 局外经济（跨局累积）
     **需要 sink，会通胀，game-numeric 全套适用。**
     但 IAA 里"通胀"的表现不是物价上涨，是 **内容被提前消耗完**。

  ③ 广告层（注意力 → 资源）
     它是一个**注入到 ② 的龙头**。
     本模型最重要的结论就在这里：广告注入量直接决定你的**内容寿命**。

用 game-numeric 的 econ.py 引擎（原理见 ../game-numeric/03-resource-flow.md）。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
from econ import Economy

use_cjk_font()

# ============================================================
# 第一层：局内经济 —— 健康指标是"买得起比例"
# ============================================================
ROOMS = 50
DROP_0 = 10.0            # 第 1 房的金币掉落
DROP_GROWTH = 1.045      # 掉落随深度增长
SHOP_EVERY = 5           # 每 5 房一个商店
SHOP_SLOTS = 4           # 每次上架 4 件
PRICE_0 = 22.0           # 第 1 房的基准单价
PRICE_GROWTH = 1.045     # 价格与掉落同速增长（保持相对购买力恒定）
ITEM_POWER = 0.06        # 每件商品 +6% 强度


def run_inner(price_mult):
    """跑一局的局内经济，返回统计"""
    e = Economy(coin=0.0, power=10.0)
    stat = dict(offered=0, bought=0, shops=0, empty=0)

    e.source("战斗掉落", "coin", lambda e: DROP_0 * DROP_GROWTH ** (e.t - 1))

    def shop(e):
        if e.t % SHOP_EVERY != 0:
            return 0
        price = PRICE_0 * price_mult * PRICE_GROWTH ** (e.t - 1)
        n = 0
        stat["shops"] += 1
        stat["offered"] += SHOP_SLOTS
        for _ in range(SHOP_SLOTS):
            if e.p["coin"] < price:
                break
            e._take("coin", price)
            e._give("power", ITEM_POWER * e.p["power"])
            n += 1
        stat["bought"] += n
        stat["empty"] += (n == 0)
        return n

    e.add("商店", "converter", shop)

    # 结算清零：这就是局内经济的终极 sink，不需要你再设计别的回收
    def settle(e):
        return e._take("coin", e.p["coin"]) if e.t == ROOMS else 0.0

    e.add("结算清零", "drain", settle)

    df = e.run(ROOMS)
    dropped = df["流|战斗掉落|coin"].sum()
    wasted = -df["流|结算清零|coin"].sum()         # 原本是负数
    return dict(
        afford=stat["bought"] / stat["offered"],
        empty=stat["empty"] / stat["shops"],
        unspent=wasted / dropped,
        power=df["power"].iloc[-1],
        df=df,
    )


print("=== ① 局内经济：为什么它不需要 sink，以及该看什么指标 ===\n")
print("结算清零 = 天然的终极 sink。所以局内不看回收率，看下面这两个：\n")
print(f"{'商店定价':>10}{'买得起比例':>12}{'空手商店比例':>14}"
      f"{'结算剩余率':>12}{'终局强度':>10}   判断")
print("-" * 86)

inner = {}
for pm in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
    r = run_inner(pm)
    inner[pm] = r
    if r["afford"] > 0.95:
        judge = "钱不是约束，选择没分量"
    elif r["empty"] > 0.35:
        judge = "太多商店空手而归"
    elif 0.40 <= r["afford"] <= 0.70:
        judge = "← 健康区间"
    else:
        judge = "偏紧"
    print(f"{pm:>9.2f}×{r['afford']:>12.0%}{r['empty']:>14.0%}"
          f"{r['unspent']:>12.0%}{r['power']:>10.1f}   {judge}")

print("""
读法
----
**局内经济的目标不是"收支平衡"，是让"买不起全部"成为常态。**
买得起比例落在 40%~70% 时，"这次买哪个"才是一个真决策 ——
这正是第 01 章说的：真正稀缺的是**玩家的决策次数**。

定价太低（0.5×）→ 全都买得起，商店退化成"点四下"，决策消失；
定价偏高（1.5~2.0×）→ 买得起比例掉到 30% 以下，四选一变成"只买得起一件"，
                      **选择还在，但选项没了**；
定价过高（3.0×）→ 40% 的商店空手而归，那些节奏点直接变成死点。

⚠️ 这里有两个反直觉的发现，值得单独说：

**一、"结算剩余率"不是一个好指标（1%~16%，还非单调）。**

    原因：玩家买不起就攒着，攒够了照样买。钱最终总会花掉，
    所以浪费不体现在剩余金币上，而体现在**他在商店前站了几次却什么也没买**。

**二、"空手商店比例"是个阶跃，不是渐变（2.0× 时 0%，3.0× 时直接 40%）。**

    原因：本模型里价格与掉落**同速增长**，所以购买力恒定 ——
    要么每次都买得起一件，要么每隔一次才买得起。中间没有过渡。

    ⇒ 这本身就是一条设计经验：**当价格增速 = 产出增速时，
      局内经济的手感是"平的"，调价只会在某个点突然崩掉。**
      想要平滑的紧张感变化，价格增速必须**略快于**产出增速
      （game-numeric 第 04 章的成本/产出增速比，在局内一样适用）。

    ⇒ 局内经济要盯的是**节奏点的有效性**，不是资源的收支。
      这和局外经济正好相反。
""")

# ============================================================
# 第二、三层：局外经济 + 广告注入 —— 广告决定内容寿命
# ============================================================
DAYS = 180
RUNS_PER_DAY = 5          # 每天玩几局
RUN_REWARD_0 = 100.0      # 0 级时每局结算给多少元货币
OUT_GROWTH = 1.030        # 产出随元进程等级增长
COST_0 = 300.0            # 0 级 → 1 级的升级成本
COST_GROWTH = 1.035       # 成本增速（成本/产出增速比 = 0.035/0.030 = 1.17，健康区间）
MAX_LEVEL = 100           # 内容边界：升满 = 你做的内容被消耗完


def run_outer(ad_mult, days=DAYS):
    """
    ad_mult: 广告注入量，以"基础日产出的倍数"表示
             0   = 完全不放广告
             1.0 = 广告让日产出翻倍（结算翻倍 + 离线翻倍 + 免费领，很常见）
    """
    e = Economy(coin=0.0, level=0.0)

    e.source("局内结算", "coin",
             lambda e: RUNS_PER_DAY * RUN_REWARD_0 * OUT_GROWTH ** e.p["level"])
    e.source("广告注入", "coin",
             lambda e: ad_mult * RUNS_PER_DAY * RUN_REWARD_0
             * OUT_GROWTH ** e.p["level"])

    def upgrade(e):
        """元进程升级：局外经济唯一的 sink，也是内容本身"""
        n = 0
        while e.p["level"] < MAX_LEVEL:
            cost = COST_0 * COST_GROWTH ** e.p["level"]
            if e.p["coin"] < cost:
                break
            e._take("coin", cost)
            e._give("level", 1.0)
            n += 1
        return n

    e.add("元进程升级", "converter", upgrade)
    df = e.run(days)

    maxed = df.index[df["level"] >= MAX_LEVEL]
    life = int(maxed[0]) if len(maxed) else None      # 内容寿命（天）
    daily = df["流|局内结算|coin"] + df["流|广告注入|coin"]
    return dict(df=df, life=life, econ=e,
                stock_ratio=(df["coin"] / daily).values,
                ups=df["@元进程升级"].values)


print("\n=== ②③ 局外经济 + 广告注入：广告注入量决定内容寿命 ===\n")
print(f"（元进程共 {MAX_LEVEL} 级 = 你做出来的全部内容；每天玩 {RUNS_PER_DAY} 局）\n")
print(f"{'广告注入':>10}{'日产出倍数':>12}{'内容耗尽':>12}"
      f"{'第7天等级':>11}{'第30天等级':>12}{'寿命缩短':>10}")
print("-" * 68)

outer = {}
for am in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0):
    outer[am] = run_outer(am)
base_life = outer[0.0]["life"] or DAYS
for am in sorted(outer):
    r = outer[am]
    life = r["life"] or DAYS
    lifestr = f"{life} 天" if r["life"] else f">{DAYS} 天"
    print(f"{am:>9.1f}×{1+am:>11.1f}×{lifestr:>12}"
          f"{r['df']['level'].iloc[6]:>11.0f}{r['df']['level'].iloc[29]:>12.0f}"
          f"{1 - life/base_life:>10.0%}")

print(f"""
读法
----
**广告注入直接吃掉你的内容寿命，而且吃得比你以为的快。**

  不放广告        内容能撑 {base_life} 天
  广告让产出翻倍   {outer[1.0]['life']} 天   （缩短 {1 - outer[1.0]['life']/base_life:.0%}）
  广告让产出 ×3    {outer[2.0]['life']} 天   （缩短 {1 - outer[2.0]['life']/base_life:.0%}）

注意这里**不是线性的**：日产出翻倍并不等于寿命减半。
因为升级成本是指数增长的（{COST_GROWTH} 每级），产出多一倍只够多推进
log({1+1.0})/log({COST_GROWTH}) ≈ {np.log(2)/np.log(COST_GROWTH):.0f} 级 ——
**这正是 game-numeric 第 04 章那条"指数成本曲线吸收投放"的性质在保护你。**
广告注入 ×3 只把寿命砍掉 {1 - outer[2.0]['life']/base_life:.0%}，而不是砍掉三分之二。

这就是 IAA 版的通胀。**它的表现不是物价上涨，是"玩家提前把内容玩完了"。**

⚠️ 本章最该记住的一句话：

    **广告注入量必须计入你的内容预算。**

    你每加一个广告点位，都在缩短内容寿命；
    内容一旦耗尽，留存就断、DAU 就掉 —— 你用 IPU 换来的收入会被 DAU 吃回去。
    第 04 章把这笔账接到 LTV 上，第 06 章求最优点。

    **好消息是：指数成本曲线是你的缓冲垫。** 它让"多放一点广告"的代价
    远小于直觉，这也是为什么放置类小游戏敢把广告倍率做到 ×3 甚至更高。
""")

# ============================================================
# 出图
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

# ① 局内：定价 → 买得起比例 / 未花费率
pms = sorted(inner)
axes[0].plot(pms, [inner[p]["afford"] * 100 for p in pms],
             "o-", lw=2.5, label="买得起比例")
axes[0].plot(pms, [inner[p]["unspent"] * 100 for p in pms],
             "s--", lw=2.5, label="金币未花费率")
axes[0].axhspan(40, 70, color="tab:green", alpha=.13)
axes[0].text(2.0, 55, "健康区间", color="tab:green", fontsize=9)
axes[0].set_xlabel("商店定价倍数"); axes[0].set_ylabel("%")
axes[0].set_title("① 局内经济\n目标是让'买不起全部'成为常态")
axes[0].legend(fontsize=8)

# ② 局外：等级推进曲线
for am in (0.0, 1.0, 2.0, 3.0):
    axes[1].plot(outer[am]["df"].index, outer[am]["df"]["level"],
                 lw=2.2, label=f"广告注入 {am:.0f}×")
axes[1].axhline(MAX_LEVEL, color="k", ls=":", lw=1.5)
axes[1].text(3, MAX_LEVEL + 1, "内容边界", fontsize=9)
axes[1].set_xlabel("天"); axes[1].set_ylabel("元进程等级")
axes[1].set_title("② 广告注入 → 内容消耗速度\n线越陡，你的内容被吃得越快")
axes[1].legend(fontsize=8)

# ③ 内容寿命 vs 广告注入
ams = sorted(outer)
lives = [outer[a]["life"] or DAYS for a in ams]
axes[2].plot(ams, lives, "o-", lw=2.5, color="tab:red")
axes[2].set_xlabel("广告注入量（基础日产出的倍数）")
axes[2].set_ylabel("内容耗尽天数")
axes[2].set_title("③ 内容寿命\nIAA 的通胀 = 内容提前被消耗")

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s03_three_economies.png", dpi=140)

# ============================================================
# 收支平衡表：内容耗尽的那一刻，sink 消失
# ============================================================
life = outer[1.0]["life"]
print(f"\n=== 收支平衡表对比（广告注入 1.0×，内容在第 {life} 天耗尽）===")
print("注意：level 是计数器，不参与收支平衡，所以 skip 掉")

print(f"\n【A】只看前 {life - 1} 天（内容还没耗尽）")
run_outer(1.0, days=life - 1)["econ"].audit(skip=("level",))

print(f"\n【B】看满 {DAYS} 天（内容早已耗尽）")
outer[1.0]["econ"].audit(skip=("level",))

print(f"""
⇒ **同一个经济，只因为多跑了 {DAYS - life + 1} 天，回收率就从 99.8% 崩到 8.8%。**

   拐点就是内容耗尽的那一刻。升级是这个经济唯一的 sink，
   等级顶到 {MAX_LEVEL} 之后它彻底失效，投放却一天没停 —— 金币开始无限堆积。

   在 game-numeric 里，这张表读作"回收不足，会通胀"。
   **在 IAA 里它读作另一句话：你的玩家从第 {life} 天起就没有目标了。**

   ⚠️ 所以别被"回收率 100%"骗了 —— 那只说明玩家还在消耗内容。
      真正要盯的是**它还能保持 100% 多少天**。那个天数就是你的留存天花板。
""")
