"""
10 章：产出链与比率 —— 放置/模拟经营的核心数学

割草类的核心决策是"三选一拿什么"，放置经营的核心决策是"这块地放什么"。
支撑后者的数学只有三件事：

  ① **比率**：要维持 1 台机器/秒的产出，各级设备各要几台？（Factorio 的核心）
  ② **瓶颈**：产出永远等于最短板；**解决瓶颈就是核心玩法**
  ③ **加成必须递减**：否则空间不再稀缺，布局决策消失

第 ③ 条是本章的落点，也是 Factorio 在 FFF#409 里把 beacon 改成递减的理由。

最后接回 IAA：**放置类的广告卖的是"时间"**（第 03 章），本章给它定价。
"""
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

# ---------------- 一条 4 层生产链 ----------------
# rate = 单台设备的产出速度（个/秒）；inputs = 产 1 个需要的上游数量
RECIPES = {
    "矿石": dict(rate=0.50, inputs={}),
    "铁板": dict(rate=0.60, inputs={"矿石": 1}),
    "齿轮": dict(rate=0.50, inputs={"铁板": 2}),
    "机器": dict(rate=0.25, inputs={"齿轮": 3, "铁板": 2}),
}
ORDER = ["矿石", "铁板", "齿轮", "机器"]


def demand(target, rate):
    """递归展开配方树，返回 (各物品需求速率, 各级设备台数)"""
    need = defaultdict(float)

    def visit(item, r):
        need[item] += r
        for inp, amt in RECIPES[item]["inputs"].items():
            visit(inp, r * amt)

    visit(target, rate)
    machines = {k: v / RECIPES[k]["rate"] for k, v in need.items()}
    return dict(need), machines


# ============================================================
# ① 比率计算
# ============================================================
print("=== ① 比率：要 1 台机器/秒，各级要几台设备 ===\n")
need, mach = demand("机器", 1.0)
print(f"{'物品':<8}{'需求速率':>10}{'单台速度':>10}{'需要台数':>10}{'占比':>8}")
print("-" * 48)
total = sum(mach.values())
for it in ORDER:
    print(f"{it:<8}{need[it]:>10.2f}{RECIPES[it]['rate']:>10.2f}"
          f"{mach[it]:>10.2f}{mach[it]/total:>8.0%}")
print(f"{'合计':<8}{'':>10}{'':>10}{total:>10.2f}")

print(f"""
读法
----
**比率是放置经营唯一的硬数学，其余都是它的包装。**

注意"铁板"占了 {mach['铁板']/total:.0%} 的设备 —— 因为它被两条线消耗
（齿轮吃 {RECIPES['齿轮']['inputs']['铁板']} 个，机器直接吃 {RECIPES['机器']['inputs']['铁板']} 个）。
**这种"汇聚型"配方是所有工厂游戏里最容易被玩家算错的地方**，
也正因为算错才有得玩 —— **让玩家自己发现"铁板不够"就是核心乐趣。**

⇒ 设计含义：
  · **配方的分叉/汇聚结构决定了这条链好不好玩。**
    纯线性链（A→B→C→D）的比率是死的，算一次就完事；
    **有汇聚的链需要玩家反复重算**，每次扩产都是新决策。
  · **比率越不整齐越好。** 如果各级正好都是 1:1，玩家什么都不用想。
    模型里 {mach['铁板']:.2f} 台熔炉这种带小数的数字，
    正是逼玩家权衡"多放一台浪费 vs 少放一台卡住"的地方。
""")

# ============================================================
# ② 瓶颈与瓶颈转移
# ============================================================
print("=== ② 瓶颈：产出等于最短板，而且补完会转移 ===\n")


def throughput(counts):
    """给定各级设备台数，算实际的机器产出速率（个/秒）"""
    lo = 1e18
    for it in ORDER:
        cap = counts[it] * RECIPES[it]["rate"]        # 该级的产能
        per_machine = demand("机器", 1.0)[0][it]       # 产 1 机器/秒 需要的该物品速率
        lo = min(lo, cap / per_machine)
    return lo


def bottleneck(counts):
    ratios = {}
    for it in ORDER:
        cap = counts[it] * RECIPES[it]["rate"]
        ratios[it] = cap / demand("机器", 1.0)[0][it]
    return min(ratios, key=ratios.get), ratios


# 玩家的起手：每级都放 6 台（很自然的"平均分配"直觉）
counts = {it: 6.0 for it in ORDER}
print("玩家起手：每级各放 6 台（'平均分配'的直觉）\n")
print(f"{'步骤':<26}{'产出(机器/秒)':>14}{'瓶颈':>8}{'设备总数':>10}{'边际产出/台':>14}")
print("-" * 76)

prev = throughput(counts)
print(f"{'起手（每级 6 台）':<24}{prev:>14.3f}{bottleneck(counts)[0]:>8}"
      f"{sum(counts.values()):>10.0f}{'—':>14}")

for step in range(1, 7):
    b, _ = bottleneck(counts)
    counts[b] += 4.0                                  # 往瓶颈那一级加 4 台
    now = throughput(counts)
    print(f"{f'第{step}次：给「{b}」加 4 台':<24}{now:>14.3f}"
          f"{bottleneck(counts)[0]:>8}{sum(counts.values()):>10.0f}"
          f"{(now - prev)/4:>14.4f}")
    prev = now

wrong = dict(counts)
nb = max(bottleneck(counts)[1], key=bottleneck(counts)[1].get)   # 最不缺的那一级
before = throughput(wrong)
wrong[nb] += 4.0
print(f"{f'对照：给非瓶颈「{nb}」加 4 台':<24}{throughput(wrong):>14.3f}"
      f"{bottleneck(wrong)[0]:>8}{sum(wrong.values()):>10.0f}"
      f"{(throughput(wrong)-before)/4:>14.4f}   ← 完全白加")

opt_need, opt_mach = demand("机器", throughput(counts))
print(f"""
  作为对照：要达到当前产出 {throughput(counts):.3f} 机器/秒，
  **按比率最优分配只需要 {sum(opt_mach.values()):.0f} 台设备**
  （{'、'.join(f'{k} {opt_mach[k]:.1f}' for k in ORDER)}），
  而玩家实际用了 {sum(counts.values()):.0f} 台 —— **浪费了 {1 - sum(opt_mach.values())/sum(counts.values()):.0%}**。

读法
----
**三件事，每一件都是设计抓手：**

**一、"平均分配"是错的，而且错得很自然。**
   玩家的第一直觉总是每级放一样多。**这个错误是好事** ——
   它给了玩家一个可以被"发现"的知识：**原来铁板要放最多。**
   ⇒ **不要在 UI 里直接告诉玩家比率。** 那等于把核心玩法删掉了。

**二、瓶颈会转移，而且是循环的。**
   看"瓶颈"那一列：补完一个，下一个立刻顶上来。
   **这个"打地鼠"循环就是工厂游戏的核心节奏**，和割草的"三选一"是同一个位置。

**三、选对和选错的差别是"有 vs 无"，不是"多 vs 少"。**
   看最后一列：补对瓶颈时边际产出在 0.012~0.044 之间（差 3.5 倍，取决于补哪一级），
   **而补非瓶颈那一行是 0.0000 —— 完全白加。**

   ⇒ **这就是"决策有分量"最纯粹的形态**：不是"选错了效率低一点"，
     是**"选错了完全没有效果"**。

   ⇒ 对比第 07 章的三选一：那里选错只是弱一点（边际胜率差几个点），
     这里选错是零。**放置经营的决策反馈比割草类更硬、更清晰，
     这也是它对新手更友好的原因** —— 玩家很容易验证自己想对了没有。
""")

# ============================================================
# ③ 加成必须递减 —— 本章的落点
# ============================================================
print("=== ③ 为什么加成必须递减 ===\n")
print("场景：给设备加'速度模块'，n 个模块的加成有两种叠加方式\n")
print(f"{'模块数':>8}{'线性叠加(1+0.5n)':>18}{'递减叠加(1+0.5√n)':>20}"
      f"{'线性时所需设备':>16}{'递减时所需设备':>16}")
print("-" * 82)

base_total = total
for n in (0, 1, 2, 4, 8, 12):
    lin, dim = 1 + 0.5 * n, 1 + 0.5 * np.sqrt(n)
    print(f"{n:>8}{lin:>18.2f}{dim:>20.2f}"
          f"{base_total/lin:>16.1f}{base_total/dim:>16.1f}")

print(f"""
读法 —— **本章的落点**
------------------------
**加成不递减的后果不是"数值太大"，是"空间不再稀缺"。**

  线性叠加、12 个模块时：达到同样产出只需要 {base_total/7:.1f} 台设备
  （原本要 {base_total:.0f} 台）。**玩家的整个工厂缩到原来的 1/7。**

  ⇒ 一旦地不够用不再是问题，"这块地放什么"就不是决策了。
    **而那正是这个品类的核心玩法**（第 01 章：真正稀缺的是决策次数）。

**这就是 Factorio 在 FFF#409 里把 beacon 改成递减叠加的理由。**
不是因为"太强"，是因为**堆满 beacon 之后，布局这件事本身消失了。**

⇒ **通用规律（和第 08 章 §3 是同一条）：**

    **凡是"可以无限堆叠、且线性生效"的加成，最终都会消灭它所在维度的决策。**

    第 08 章：同维乘法叠加 → 分配决策价值精确等于 1
    本章：    加成线性叠加 → 空间稀缺性归零

    **两者是同一个病，药也一样：让叠加函数变凹（√n、饱和公式、递减系数）。**
""")

# ============================================================
# ④ 接回 IAA：放置类的广告卖的是"时间"
# ============================================================
print("=== ④ 广告加速：给'时间'定价 ===\n")

SESSION_MIN = 15.0            # 承第 02、05 章
print(f"当前产出 {throughput(counts):.3f} 机器/秒。"
      f"假设下一次升级需要 200 台机器。\n")

need_machines = 200
wait_sec = need_machines / throughput(counts)
print(f"{'广告形式':<22}{'省下的等待':>14}{'折算分钟等效产出':>20}{'第05章意愿':>12}")
print("-" * 70)


def willingness(v, K=1.2, T=2.0):
    return 1 / (1 + np.exp(-K * (v - T)))


for name, saved in (("离线收益翻倍（8h）", 8 * 3600 * 0.5),
                    ("加速 4 小时", 4 * 3600),
                    ("加速 30 分钟", 1800),
                    ("产出翻倍 5 分钟", 300)):
    mins = saved / 60
    print(f"{name:<20}{saved/3600:>13.1f}h{mins:>20.1f}{willingness(mins):>12.0%}")

print(f"""
读法
----
**放置类的广告点位可以直接用"省下多少分钟"定价** ——
这比割草类容易得多，因为**时间是可以直接换算的**（第 03 章：割草卖容错，放置卖时间）。

套用第 05 章的意愿模型（收益要抵得上 2 分钟正常产出才有 50% 意愿）：
**放置类的所有加速点位几乎都远超阈值，意愿接近 100%。**

⇒ **这解释了两件事：**

  1. **放置类的 IPU 天然比割草类高。** 它的广告点位每一个都"很值"。
  2. **但也正因为很值，最容易过量** —— 第 03 章那条"广告注入吃内容寿命"
     在放置类里最危险：**玩家一天看 10 个加速广告，你三个月的内容一周就没了。**

⇒ **实践建议：放置类的加速广告一定要有每日次数上限**，
  而这个上限该按第 03 章的"内容寿命预算"倒推，**不是按玩家意愿定。**
  意愿会告诉你"他还愿意看"，内容预算才会告诉你"你还给得起"。
""")

# ============================================================
# 出图
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

axes[0].bar(ORDER, [mach[i] for i in ORDER], color="tab:blue")
axes[0].set_ylabel("需要台数"); axes[0].set_title("① 1 台机器/秒 的比率\n汇聚型配方让铁板成为大头")

cnt2 = {it: 6.0 for it in ORDER}
hist = [throughput(cnt2)]
tot = [sum(cnt2.values())]
for _ in range(10):
    cnt2[bottleneck(cnt2)[0]] += 4.0
    hist.append(throughput(cnt2))
    tot.append(sum(cnt2.values()))
axes[1].plot(tot, hist, "o-", lw=2.5, color="tab:green")
axes[1].set_xlabel("设备总数"); axes[1].set_ylabel("产出（机器/秒）")
axes[1].set_title("② 每次补瓶颈都跳一台阶\n补对了跳，补错了平")

ns = np.arange(0, 13)
axes[2].plot(ns, base_total / (1 + 0.5 * ns), "o-", lw=2.5,
             color="tab:red", label="线性叠加")
axes[2].plot(ns, base_total / (1 + 0.5 * np.sqrt(ns)), "s-", lw=2.5,
             color="tab:blue", label="递减叠加(√n)")
axes[2].set_xlabel("速度模块数"); axes[2].set_ylabel("达到同样产出所需设备数")
axes[2].set_title("③ 线性加成会让工厂缩水\n空间不稀缺 = 布局决策消失")
axes[2].legend(fontsize=8)

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s10_idle_production.png", dpi=140)
