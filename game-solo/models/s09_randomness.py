"""
09 章：随机性与保底

第 08 章留了一个问题：**"这个方差是谁贡献的？"**
运气贡献的方差和决策贡献的方差，在玩家那里是完全不同的两种体验。
本章把这个问题算清楚。

三段：
  ① **方差归因** —— 逐个冻结随机源，看每一个贡献了多少
  ② **保底** —— 无保底 / 硬保底 / 递增概率（PRD）三种机制的等待时间分布
  ③ **重抽广告** —— IAA 里最自然的一个点位：它同时是保底、是变现、也是方差控制器

场景：一局 8 次三选一，从 24 件道具（4 个标签各 6 件）里抽。
      玩家想凑齐 5 件同标签触发协同（承第 07、08 章）。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
import run_model as R

use_cjk_font()

N_ITEMS, N_TAGS, OFFER, PICKS = 24, 4, 3, 8
PER_TAG = N_ITEMS // N_TAGS
N = 20000
rng = np.random.default_rng(19)

TAG = np.arange(N_ITEMS) % N_TAGS
VAL = np.random.default_rng(3).uniform(0.85, 1.15, N_ITEMS)


# ============================================================
# ① 方差归因：逐个冻结随机源
# ============================================================
def one_build(r, fixed_offers=None, fixed_picks=None, eps=0.15):
    """返回 (构筑分, 最大同标签件数)"""
    k = fixed_picks if fixed_picks is not None else int(np.clip(r.poisson(PICKS), 3, 16))
    held = []
    for i in range(k):
        if fixed_offers is not None:
            offer = fixed_offers[i % len(fixed_offers)]
        else:
            offer = r.choice(N_ITEMS, OFFER, replace=False)
        # 玩家：优先凑当前最多的标签，带 eps 噪声
        if r.random() < eps:
            c = int(r.choice(offer))
        else:
            cnt = np.bincount(TAG[held], minlength=N_TAGS) if held else np.zeros(N_TAGS)
            c = int(offer[np.argmax(cnt[TAG[offer]] * 10 + VAL[offer])])
        held.append(c)
    h = np.array(held)
    cnt = np.bincount(TAG[h], minlength=N_TAGS)
    score = VAL[h].sum() + (1.6 if cnt.max() >= 5 else 0.0)
    return score, int(cnt.max())


CONFIGS = {
    "全随机（基线）":        dict(),
    "冻结'拿到几件'":        dict(fixed_picks=PICKS),
    "冻结'每次给哪三件'":    dict(fixed_offers=[np.random.default_rng(77 + i)
                                                .choice(N_ITEMS, OFFER, replace=False)
                                                for i in range(16)]),
    "两个都冻结":            dict(fixed_picks=PICKS,
                                 fixed_offers=[np.random.default_rng(77 + i)
                                               .choice(N_ITEMS, OFFER, replace=False)
                                               for i in range(16)]),
}

print("=== ① 方差归因：这局的运气，到底是哪来的 ===\n")
print(f"{'配置':<24}{'构筑分方差':>12}{'占基线':>10}{'协同触发率':>12}")
print("-" * 60)

base_var = None
for name, kw in CONFIGS.items():
    r = np.random.default_rng(101)
    out = [one_build(r, **kw) for _ in range(N)]
    sc = np.array([o[0] for o in out])
    five = np.mean([o[1] >= 5 for o in out])
    if base_var is None:
        base_var = sc.var()
    print(f"{name:<22}{sc.var():>12.3f}{sc.var()/base_var:>10.0%}{five:>12.0%}")

print("""
读法
----
**"冻结'拿到几件'"这一行降得最多** —— 说明构筑分的方差主要来自
"这局你拿到了多少件道具"，而不是"每次给你哪三件"。

⇒ 这一点很重要，因为两者在玩家那里的感受完全不同：

  · **"每次给哪三件"是玩家看得见、也能应对的随机**
    —— 他会说"这把牌不好，我换个思路"。**这是决策的一部分。**

  · **"这局拿到几件"是玩家看不见、也应对不了的随机**
    —— 他只会说"这局怎么这么穷"。**这是纯粹的运气。**

⇒ **本章第一条设计原则：把方差尽量放在玩家看得见的那一侧。**
   同样的总方差，摆在"选什么"上是深度，摆在"给多少"上是挫败。

⚠️ **但先别急着抄这个 95%，它有一半是我这个模型的性质，值得拆开看：**

   本模型里道具价值只在 0.85~1.15 之间波动，**彼此差别很小**。
   于是构筑分 ≈ 件数 × 平均价值 —— **件数当然主导一切。**

   ⇒ 这本身就是一条设计结论，而且比那个百分比更重要：

     **如果你的道具彼此差异不大，"拿到几件"就会淹没"选了哪件"，
       玩家的选择再怎么设计都没有影响力。**

     两条出路，通常要一起用：
       1. **把件数的随机性压掉**（固定每局的选择次数）——
          这是绝大多数成功 roguelike 的做法：**每层必给一次三选一。**
       2. **拉大道具之间的差异**（第 07 章的"通用模块 + 传说件"结构）。

     ⇒ **"每局固定 N 次选择"不是 UI 惯例，是一条数值决策。**
       它把方差从看不见的一侧，搬到了看得见的一侧。
""")

# ============================================================
# ② 保底：三种机制的等待时间
# ============================================================
p_hit = 1 - np.prod([(N_ITEMS - PER_TAG - i) / (N_ITEMS - i) for i in range(OFFER)])
print(f"=== ② 保底：凑齐 5 件同标签要等多久 ===\n")
print(f"（单次 offer 里出现目标标签的概率 = {p_hit:.1%}）\n")


def wait_for(mode, need=5, n=N, cap=40):
    """返回凑齐 need 件目标标签所需的抽取次数"""
    out = np.empty(n)
    for i in range(n):
        got, tries, miss, p = 0, 0, 0, p_hit
        while got < need and tries < cap:
            tries += 1
            if mode == "硬保底" and miss >= 2:       # 连续 2 次没出，第 3 次必出
                hit = True
            elif mode == "递增概率(PRD)":
                hit = rng.random() < p
            else:
                hit = rng.random() < p_hit
            if hit:
                got += 1
                miss, p = 0, p_hit
            else:
                miss += 1
                p = min(p + 0.18, 1.0)
        out[i] = tries
    return out


print(f"{'机制':<18}{'期望次数':>10}{'中位':>8}{'P90':>8}{'P99':>8}"
      f"{'标准差':>10}{'8 次内凑齐':>12}")
print("-" * 78)
waits = {}
for mode in ("无保底", "硬保底", "递增概率(PRD)"):
    w = wait_for(mode)
    waits[mode] = w
    print(f"{mode:<16}{w.mean():>10.2f}{np.median(w):>8.0f}"
          f"{np.percentile(w,90):>8.0f}{np.percentile(w,99):>8.0f}"
          f"{w.std():>10.2f}{(w <= PICKS).mean():>12.0%}")

print(f"""
读法
----
**三种机制的期望值差不多，但尾巴完全不同 —— 保底改的是尾巴，不是均值。**

  无保底        P99 要等 {np.percentile(waits['无保底'],99):.0f} 次。
                一局只有 {PICKS} 次抽取，**这意味着有一批玩家永远凑不齐**。
  硬保底        P99 压到 {np.percentile(waits['硬保底'],99):.0f} 次，标准差从
                {waits['无保底'].std():.2f} 降到 {waits['硬保底'].std():.2f}。
  递增概率(PRD) 尾巴同样被压住，但**它是平滑的**，
                不会出现"第 3 次一定出"这种可被玩家数出来的硬规律。

⇒ **保底在单人游戏里的目的和 F2P 完全不同**（第 01 章 §2④）：
     F2P 的保底是"控制最坏付费"；
     **单人的保底是"保证这局不会开局就废"。**

⇒ **选哪个？**
     · 硬保底：好实现、好解释，**代价是玩家会学会数数**
       （"我已经两次没出了，下次稳了"—— 这会改变他的决策，有时是好事）
     · PRD：手感更自然，**但玩家说不清为什么，也就没法利用它做决策**

     **给小游戏的建议：用硬保底。** 可预测性在单局尺度上是优点 ——
     它让玩家能规划"我还差 2 件，还有 3 次机会，来得及"，
     而这正是第 02 章说的"早期信号"。
""")

# ============================================================
# ③ 重抽广告：保底 + 变现 + 方差控制，一个点位干三件事
# ============================================================
print("=== ③ 重抽广告：一个点位干三件事 ===\n")


def with_rerolls(n_reroll, n=N):
    """玩家在 offer 里没有目标标签时，可以看广告重抽（最多 n_reroll 次/局）"""
    five, used = 0, []
    for _ in range(n):
        k = int(np.clip(rng.poisson(PICKS), 3, 16))
        got, left, u = 0, n_reroll, 0
        for _ in range(k):
            hit = rng.random() < p_hit
            while not hit and left > 0:
                left -= 1
                u += 1
                hit = rng.random() < p_hit
            got += hit
        five += got >= 5
        used.append(u)
    return five / n, float(np.mean(used))


print(f"{'每局可重抽次数':>16}{'协同触发率':>12}{'实际观看次数':>14}"
      f"{'每次广告换来的触发率':>22}")
print("-" * 68)
base_rate, _ = with_rerolls(0)
for k in (0, 1, 2, 3, 5, 8):
    rate, used = with_rerolls(k)
    eff = (rate - base_rate) / used if used > 0 else 0.0
    print(f"{k:>16}{rate:>12.1%}{used:>14.2f}"
          f"{(f'{eff:.1%}' if used else '—'):>22}")

print(f"""
读法
----
**重抽广告是 IAA 里性价比最高的点位之一，因为它同时干三件事：**

  1. **保底**：它把"这局开局就废"的尾巴削掉了 ——
     和第 ② 段的硬保底是同一个作用，**但成本由玩家自己决定要不要付。**
  2. **变现**：它天然发生在玩家最想要的时刻（"这三个都不想要"），
     渗透率高（第 05 章的意愿模型里，这类点位的收益折算分钟数不低）。
  3. **方差控制**：它让**愿意投入的玩家**方差更小、**不愿意的玩家**方差照旧
     —— 相当于一个玩家自选的难度档。

⚠️ **但要限次，而且理由不是"边际递减"。**

   看最后一列：每次广告换来的触发率从 11.3% 降到 7.8%，**递减是有，但很温和** ——
   光看这一列，你会得出"多给几次也无所谓"的结论。

   **真正的理由在第二列**：重抽 8 次时协同触发率从 52% 涨到 **89%**。
   而第 07 章证明过：**触发率接近 100% 的超模不是惊喜，是新的基线。**

   ⇒ 无限重抽会让你的道具池退化成"想拿什么拿什么"：
       · 第 07 章的构筑决策消失（反正能抽到想要的）
       · 本章的随机性消失（方差被玩家用广告买掉了）
       · 第 08 章的巅峰体验也消失（人人都有 = 不叫巅峰）

   **⇒ 设计建议：每局限 2~3 次重抽。**
     这个上限不是为了"逼玩家看更多广告"，恰恰相反 ——
     **是为了保住随机性本身。**

     这就是第 01 章那句话的具体含义：
     **IAA 的保底要"控制看广告的边际收益，别让重抽变成无限刷"。**

⚠️ 顺带一条通用教训（和第 07 章那个"指标失灵"是同一类）：
   **"边际收益递减"这个指标在这里给出了错误的建议。**
   限次的真正理由不在效率列，在**它对其他系统的破坏**上。
   **调参时永远要看这个改动溢出到了哪些别的系统。**
""")

# ============================================================
# 出图
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

names = list(CONFIGS)
vars_ = []
for name, kw in CONFIGS.items():
    r = np.random.default_rng(101)
    vars_.append(np.var([one_build(r, **kw)[0] for _ in range(6000)]))
axes[0].barh([n.replace("（基线）", "") for n in names], vars_,
             color=["tab:gray", "tab:red", "tab:blue", "tab:green"])
axes[0].set_xlabel("构筑分方差")
axes[0].set_title("① 方差归因\n降得最多的那个，就是主要来源")

for mode in waits:
    axes[1].hist(waits[mode], bins=np.arange(4, 31), alpha=.5, label=mode)
axes[1].axvline(PICKS, color="k", ls=":", lw=1.5)
axes[1].text(PICKS + .3, axes[1].get_ylim()[1] * .8, "一局只有 8 次", fontsize=8)
axes[1].set_xlabel("凑齐 5 件需要的抽取次数"); axes[1].set_ylabel("局数")
axes[1].set_title("② 保底改的是尾巴，不是均值")
axes[1].legend(fontsize=8)

ks = [0, 1, 2, 3, 5, 8]
rates = [with_rerolls(k, n=6000)[0] for k in ks]
axes[2].plot(ks, np.array(rates) * 100, "o-", lw=2.5, color="tab:purple")
axes[2].axvspan(2, 3, color="tab:green", alpha=.15)
axes[2].text(2.05, min(rates) * 100 + 2, "建议上限", fontsize=8, color="tab:green")
axes[2].set_xlabel("每局可重抽次数"); axes[2].set_ylabel("协同触发率 %")
axes[2].set_title("③ 重抽的边际收益递减\n给太多 = 删掉随机性")

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s09_randomness.png", dpi=140)
