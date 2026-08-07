"""
22 章：合服的冲击

合服对玩家的真实冲击不是"人变多了"，而是"能打赢我的人变多了"。
对每个玩家算一个指标：**排在我前面的人数**（以及我的百分位）。

对比三种合服方案：
  A 直接合并两个同龄服
  B 合并一个老服 + 一个新服（战力差距大）
  C 老服 + 新服，但给新服玩家一次性追赶补偿
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()
rng = np.random.default_rng(5)

N = 3000


def make_server(scale, n=N):
    """战力服从对数正态；scale 表示服的整体发育程度"""
    return rng.lognormal(np.log(scale), 1.1, n)


old = make_server(100.0)          # 开服 300 天的老服
same = make_server(100.0)         # 另一个同龄服
young = make_server(28.0)         # 开服 90 天的新服
boosted = young * 2.2             # 新服 + 追赶补偿


def rank_stats(mine, world):
    """给定我的战力和全服战力，算'排在我前面的人数'和百分位"""
    ahead = np.array([(world > p).sum() for p in mine])
    pct = np.array([(world < p).mean() for p in mine])
    return ahead, pct


scenarios = {
    "A 同龄服合并": (old, same),
    "B 老服 + 新服": (old, young),
    "C 老服 + 新服(补偿)": (old, boosted),
}

print("合服前：老服玩家的中位数排名 = 第 %d 名（共 %d 人）\n"
      % (np.median(rank_stats(old, old)[0]), N))
print(f"{'方案':<24}{'老服中位排名':>14}{'老服跌幅':>12}{'新服中位排名':>16}{'新服百分位':>14}")
print("-" * 84)

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
before_old = np.median(rank_stats(old, old)[0])

for i, (name, (a, b)) in enumerate(scenarios.items()):
    world = np.concatenate([a, b])
    ahead_a, pct_a = rank_stats(a, world)
    ahead_b, pct_b = rank_stats(b, world)
    print(f"{name:<22}{np.median(ahead_a):>14.0f}"
          f"{np.median(ahead_a)/before_old:>11.1f}×"
          f"{np.median(ahead_b):>16.0f}{np.median(pct_b):>14.1%}")

    axes[0].hist(np.log10(a), bins=50, histtype="step", lw=2, label=f"{name} 老服")
    axes[1].plot(np.sort(pct_a), np.linspace(0, 1, len(a)), lw=2, label=name)
    axes[2].plot(np.sort(pct_b), np.linspace(0, 1, len(b)), lw=2, label=name)

axes[0].hist(np.log10(young), bins=50, histtype="step", lw=2, ls="--", label="新服")
axes[0].set_title("① 战力分布（log10）")
axes[0].set_xlabel("log10(战力)")

axes[1].set_title("② 合服后老服玩家的百分位分布\n曲线越靠左 = 老玩家被挤得越狠")
axes[1].set_xlabel("合服后的百分位"); axes[1].set_ylabel("累计占比")

axes[2].set_title("③ 合服后新服玩家的百分位分布\n曲线越靠左 = 新玩家越绝望")
axes[2].set_xlabel("合服后的百分位"); axes[2].set_ylabel("累计占比")

for ax in axes:
    ax.legend(fontsize=7); ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/m22_merge.png", dpi=140)

print("""
读法
----
· 「老服中位排名」的跌幅是**老玩家的痛感来源**：合服当天，他前面凭空多出一批人。
  同龄服合并时这个数必然翻倍，这是合服无法回避的固有代价。
· 「新服百分位」是新服玩家的绝望程度：低于 25% 意味着一半以上的新服玩家
  会发现自己突然垫底 —— 这是合服后新服侧集中流失的直接原因。
· 方案 C 说明：**一次性追赶补偿能显著改善新服侧的处境，
  而对老服侧的额外冲击很小** —— 这是合服前最值得做的一件事。
""")
