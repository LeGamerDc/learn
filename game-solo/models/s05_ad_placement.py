"""
05 章：广告点位设计 —— 把激励视频当资源龙头来定价

三个要算清楚的东西：

  ① **广告倍率**（看一次广告给多少？）
     渗透率对倍率是**饱和**的，但内容消耗对倍率是**线性**的。
     ⇒ 存在一个明确的最优倍率，超过它就是纯亏。

  ② **点位数量**（铺几个点位？）
     玩家一个会话的意愿是有预算的，点位之间**互相蚕食**。
     ⇒ IPU 对点位数量也是饱和的。

  ③ **触达率**（点位放在哪？）
     放在第 40 房的点位，只有 40% 的局能走到（第 00 章的生存曲线）。
     ⇒ 算 IPU 必须乘触达率。

玩家意愿模型：
    玩家愿意花 30 秒看广告，当且仅当收益 ≥ 若干分钟的正常游戏产出。
    p = logistic(K × (收益分钟数 − 阈值))
    每看一次，后续所有点位的意愿 × FATIGUE（疲劳）
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

rng = np.random.default_rng(7)

K = 1.2               # 意愿曲线的陡度
THRESH = 2.0          # 收益要抵得上 2 分钟正常产出，玩家才五五开地愿意看
FATIGUE = 0.40       # 每看**一次真实广告**后，后续意愿的衰减
N_SESSIONS = 20000
# ↑ FATIGUE 是**标定出来的**：调到让基准（7 个点位、倍率 2.5×）的
#   **每会话广告次数 ≈ 3.3**。
#
#   ⚠️ 注意单位：本模型算的是**一个会话**，而第 04 章的 IPU 是**一天**。
#      日 IPU = 每会话广告次数 × 每天会话数（第 11 章）。
#      割草类约 1.8 次会话/天 → 3.3 × 1.8 ≈ 6，与第 04 章的基准对上。
#      **这两个量差一个会话数，混用会让回本模型错 2 倍以上。**
#
# ⚠️ 注意下面 simulate() 里触发次数被 ×10（降低离散误差），
#    所以疲劳指数要写成 FATIGUE ** (k / 10)，**否则疲劳会被多算 10 倍**。
#    第一版就漏了这个除法，导致第 15 章接上去时 IPU 对不上 —— 见第 15 章。


def willingness(value_min):
    """收益折算成"多少分钟正常产出"后，玩家看这次广告的基础意愿"""
    return 1.0 / (1.0 + np.exp(-K * (value_min - THRESH)))


# ---------------- 点位定义 ----------------
# base_min : 该点位的**基础**奖励，折算成"多少分钟正常产出"
# trig     : 每个会话平均触发几次
# reach    : 触达率（局内点位受生存曲线影响）
# layer    : 注入哪一层（局内不吃内容寿命，局外吃）
PLACEMENTS = [
    dict(name="复活",        base_min=3.0, trig=3.6, reach=1.00, layer="局内"),
    dict(name="重抽三选一",   base_min=1.2, trig=8.0, reach=0.90, layer="局内"),
    dict(name="局内翻倍拾取", base_min=1.0, trig=5.0, reach=0.70, layer="局内"),
    dict(name="临时增益",     base_min=1.5, trig=4.0, reach=0.85, layer="局内"),
    dict(name="结算翻倍",     base_min=2.0, trig=5.4, reach=1.00, layer="局外"),
    dict(name="离线翻倍",     base_min=6.0, trig=1.0, reach=1.00, layer="局外"),
    dict(name="每日免费领",   base_min=2.5, trig=2.0, reach=1.00, layer="局外"),
]


def simulate(placements, mult=2.0, n=N_SESSIONS):
    """
    跑 n 个会话，返回 (IPU, 各点位实际观看次数, 局外注入量)
    mult: 广告倍率。额外收益 = base_min × (mult − 1)
    """
    triggers = []
    for i, p in enumerate(placements):
        triggers += [i] * int(round(p["trig"] * 10))   # ×10 后取整，降低离散误差
    triggers = np.array(triggers)

    watched_by = np.zeros(len(placements))
    total = 0
    for _ in range(n):
        order = rng.permutation(triggers)              # 点位在会话内交错出现
        k = 0                                          # 本会话已看次数
        for idx in order:
            p = placements[idx]
            if rng.random() > p["reach"]:              # 没触达
                continue
            val = p["base_min"] * (mult - 1.0)
            if rng.random() < willingness(val) * FATIGUE ** (k / 10.0):
                k += 1
                watched_by[idx] += 1
        total += k
    ipu = total / n / 10.0            # 还原 ×10；单位是"每会话"，不是"每天"
    watched_by = watched_by / n / 10.0
    # 局外注入 = 广告**额外**给出去的那部分（基础奖励本来就要给，不算注入）
    outer = sum(w * p["base_min"] * (mult - 1.0)
                for w, p in zip(watched_by, placements) if p["layer"] == "局外")
    return ipu, watched_by, outer


# ==================== ① 广告倍率的最优点 ====================
print("=== ① 广告倍率：渗透率饱和，内容消耗线性 ===\n")
print(f"（玩家愿意为 ≥{THRESH:.0f} 分钟等效产出看广告；每看一次意愿 ×{FATIGUE}）\n")
print(f"{'广告倍率':>10}{'每会话广告':>11}{'增幅':>9}"
      f"{'局外注入':>11}{'注入增幅':>11}{'每点注入换广告':>16}")
print("（局外注入只算广告**额外**给出去的部分——基础奖励本来就要给）")
print("-" * 72)

mults = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]
rows = []
prev = None
for m in mults:
    ipu, _, outer = simulate(PLACEMENTS, mult=m)
    di = f"{ipu/prev[0]-1:>10.1%}" if prev else f"{'—':>11}"
    do = f"{outer/prev[1]-1:>10.1%}" if prev else f"{'—':>11}"
    print(f"{m:>9.1f}×{ipu:>9.2f}{di}{outer:>11.1f}{do}{ipu/outer:>16.3f}")
    rows.append((m, ipu, outer))
    prev = (ipu, outer)

print(f"""
读法
----
**先看形状，它是本章最该记住的东西：**

  IPU        1.5× → 6.0× 只从 {rows[0][1]:.2f} 涨到 {rows[-1][1]:.2f}（+{rows[-1][1]/rows[0][1]-1:.0%}）—— **饱和**
  局外注入   同一区间从 {rows[0][2]:.1f} 涨到 {rows[-1][2]:.1f}（**{rows[-1][2]/rows[0][2]:.0f} 倍**）—— 停不下来
  ⇒ 你多付出 {rows[-1][2]/rows[0][2]:.0f} 倍的内容代价，只换到 {rows[-1][1]/rows[0][1]:.1f} 倍的广告展示。

  · 低倍率段（1.5× → 2.5×）：IPU 涨得快，这段是"给得太少没人看"，加倍率很划算
  · 高倍率段（3.5× 以上）：**IPU 基本不动了，注入还在涨** —— 这段是纯亏

⚠️ 但注意"每点注入换 IPU"这一列：它**单调递减**，
   意味着这个效率指标**没有内部最优** —— 按它选，答案永远是"倍率越低越好"，
   而那显然不对（倍率 1.0× 等于没有广告，IPU 归零）。

   **⇒ 倍率这个旋钮，在本章的框架内是定不下来的。**
     你必须把"内容寿命"换算成留存、再换算成 LTV，
     才能在"多赚的广告钱"和"少赚的留存钱"之间比大小。

     **这正是第 06 章要做的事。** 本章只给你形状：
     **IPU 会饱和，内容消耗不会。**
""")

# ==================== ② 点位数量的蚕食效应 ====================
print("=== ② 点位互相蚕食：加第 N 个点位，IPU 只涨一点点 ===\n")
print(f"{'点位数':>8}{'新增的点位':>14}{'IPU':>9}{'边际增量':>11}{'该点位自身次数':>16}")
print("-" * 62)

prev_ipu = 0.0
for n in range(1, len(PLACEMENTS) + 1):
    subset = PLACEMENTS[:n]
    ipu, by, _ = simulate(subset, mult=2.5)
    print(f"{n:>8}{subset[-1]['name']:>13}{ipu:>9.2f}"
          f"{ipu - prev_ipu:>11.2f}{by[-1]:>16.2f}")
    prev_ipu = ipu

full_ipu, full_by, _ = simulate(PLACEMENTS, mult=2.5)
naive = 0.0
for p in PLACEMENTS:
    i1, _, _ = simulate([p], mult=2.5)
    naive += i1
print(f"""
  单独测每个点位再相加：{naive:.2f}
  七个点位一起跑：      {full_ipu:.2f}
  **蚕食掉了 {1 - full_ipu/naive:.0%}**

读法
----
**点位不是加法关系。** 玩家一个会话的注意力是有预算的，
你加的第 7 个点位，抢的是前 6 个点位的观看次数。

注意最后一列"该点位自身次数"：越晚加进来的点位，自己拿到的展示越少
（不是因为它差，是因为轮到它时玩家已经看过好几个了）。

⇒ 实践含义有两条，都很重要：

  1. **点位的价值排序要按"单点位效率"，不是按"能不能加"。**
     加满七个不如做好三个。

  2. **点位之间要错开时机**，别都堆在会话前段 ——
     否则疲劳会把后面的点位全废掉。（这就是为什么"离线翻倍"放在
     会话最开头、"结算翻倍"分散在每局之后，是行业默认布局。）
""")

# ==================== ③ 触达率：点位放在哪 ====================
print("=== ③ 触达率：局内点位放在第几房，差别有多大 ===\n")
print("（用第 00 章的生存曲线：走到第 N 房的玩家比例）\n")

# 第 00 章 s00 的生存曲线量级：通关率 33%，死亡中位 36 房
reach_curve = {5: 1.00, 10: 1.00, 20: 0.95, 30: 0.82, 40: 0.45, 48: 0.35}
print(f"{'放在第几房':>12}{'触达率':>10}{'该点位实际展示':>16}{'相对第 5 房':>14}")
print("-" * 54)
base_show = None
for room, reach in reach_curve.items():
    p = dict(name="宝箱广告", base_min=1.8, trig=1.0, reach=reach, layer="局内")
    _, by, _ = simulate(PLACEMENTS + [p], mult=2.5, n=N_SESSIONS)
    show = by[-1]
    if base_show is None:
        base_show = show
    print(f"{room:>12}{reach:>10.0%}{show:>16.3f}{show/base_show:>14.0%}")

print("""
读法
----
**同一个点位，放在第 40 房只能拿到放在第 5 房的四成展示。**

这不是设计问题，是生存曲线的算术后果。两条推论：

  · **把最重要的点位放在前段。** 后段的点位在给"少数走得远的玩家"服务，
    展示量天然就少。
  · **后段点位要用更高的价值补偿**，否则它在你的 IPU 表里会显得莫名其妙地差，
    你会误判成"这个点位设计得不好"。

⚠️ 反过来说：**如果你想让某个点位只服务核心玩家（比如高倍率的挑战奖励），
   放在后段正是对的**——它自动完成了分层。
""")

# ==================== 出图 ====================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

ms = [r[0] for r in rows]
axes[0].plot(ms, [r[1] for r in rows], "o-", lw=2.5, color="tab:blue", label="IPU")
axes[0].set_xlabel("广告倍率"); axes[0].set_ylabel("IPU", color="tab:blue")
ax2 = axes[0].twinx()
ax2.plot(ms, [r[2] for r in rows], "s--", lw=2.5, color="tab:red", label="局外注入")
ax2.set_ylabel("局外注入量", color="tab:red")
axes[0].set_title("① IPU 会饱和，内容消耗不会\n交叉之后的每一分倍率都是纯亏")

ns = list(range(1, len(PLACEMENTS) + 1))
ipus = []
for n in ns:
    i, _, _ = simulate(PLACEMENTS[:n], mult=2.5, n=8000)
    ipus.append(i)
axes[1].plot(ns, ipus, "o-", lw=2.5, color="tab:green", label="实际 IPU")
axes[1].plot(ns, [ipus[0] * k for k in ns], ":", lw=2,
             color="gray", label="线性叠加（假想）")
axes[1].set_xlabel("点位数量"); axes[1].set_ylabel("IPU")
axes[1].set_title("② 点位互相蚕食\n加满七个不如做好三个")
axes[1].legend(fontsize=8)

rooms = list(reach_curve)
axes[2].plot(rooms, [reach_curve[r] * 100 for r in rooms],
             "o-", lw=2.5, color="tab:purple")
axes[2].set_xlabel("点位放在第几房"); axes[2].set_ylabel("触达率 %")
axes[2].set_title("③ 触达率\n后段点位天然吃亏，要用价值补偿")

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s05_ad_placement.png", dpi=140)
