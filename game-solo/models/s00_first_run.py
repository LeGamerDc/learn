"""
00 章：单机小游戏的最小模型 —— 一局（run）

单局的全部张力，就是"玩家强度的增长"和"敌人强度的增长"两条指数曲线在赛跑。
这是 game-numeric 第 04 章的成长曲线，被压缩到了 30 分钟的尺度上。

模型本体在 run_model.py（第 00、02、11、12 章共用）。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
import run_model as R

use_cjk_font()
P = R.P

# ==================== ① 看一局的张力曲线 ====================
res = R.one_run(seed=17)
room, hp, power, enemy = res["hist"].T

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

axes[0].plot(room, hp, lw=2.5, color="tab:red")
axes[0].fill_between(room, 0, hp, color="tab:red", alpha=.15)
for x in range(P["heal_every"], P["rooms"] + 1, P["heal_every"]):
    axes[0].axvline(x, color="tab:green", ls=":", lw=1.2)
axes[0].set_title("① 一局的血量曲线（绿线 = 休息点）\n锯齿 = 张力的呼吸")
axes[0].set_xlabel("房间"); axes[0].set_ylabel("血量")

axes[1].semilogy(room, power, lw=2.5, label="玩家强度")
axes[1].semilogy(room, enemy, lw=2.5, ls="--", label="敌人强度")
axes[1].set_title("② 两条指数曲线在赛跑\n谁快一点，这局就成谁的")
axes[1].set_xlabel("房间"); axes[1].legend()

axes[2].plot(room, power / enemy, lw=2.5, color="tab:purple")
axes[2].axhline(1.0, color="k", ls=":", lw=1.5)
axes[2].set_title("③ 强度比 = 玩家/敌人\n跌破 1.0 就开始被撕碎")
axes[2].set_xlabel("房间"); axes[2].set_ylabel("强度比")

for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s00_first_run.png", dpi=140)
plt.close()

# ==================== ② 一万局：通关率与死亡分布 ====================
N = 10_000
win_rate, deaths = R.batch(N)
print(f"跑了 {N:,} 局")
print(f"  通关率           {win_rate:>7.1%}")
print(f"  死亡房间中位数     {np.median(deaths):>7.0f} / {P['rooms']}")
print(f"  P10 / P90        {np.percentile(deaths,10):>4.0f} / {np.percentile(deaths,90):.0f}")
early = (deaths <= 10).mean()
print(f"  前 10 房就死的比例 {early:>7.1%}   ← "
      f"{'偏高，玩家会觉得开局就没救' if early > 0.15 else '可接受'}")

fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
axes[0].hist(deaths, bins=np.arange(1, P["rooms"] + 2), color="tab:orange")
axes[0].set_title(f"④ 死亡房间分布（{N:,} 局，通关率 {win_rate:.1%}）")
axes[0].set_xlabel("死在第几个房间"); axes[0].set_ylabel("局数")

surv = [(deaths > i).mean() * (1 - win_rate) + win_rate
        for i in range(P["rooms"] + 1)]
axes[1].plot(range(P["rooms"] + 1), np.array(surv) * 100, lw=2.5, color="tab:blue")
axes[1].set_title("⑤ 生存曲线：走到第 N 个房间的玩家比例")
axes[1].set_xlabel("房间"); axes[1].set_ylabel("%")
for ax in axes:
    ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s00_death_dist.png", dpi=140)

# ==================== ③ 强度比：输赢两组的差别 ====================
win_min, lose_min = [], []
for s in range(1500):
    r = R.one_run(s)
    ratio = r["hist"][:, 2] / r["hist"][:, 3]
    (win_min if r["died"] is None else lose_min).append(ratio.min())
print(f"\n  通关局的最低强度比（中位）  {np.median(win_min):.2f}")
print(f"  失败局的最低强度比（中位）  {np.median(lose_min):.2f}")
print("  ⇒ 两组都会跌破 1.0，差别只有几个百分点 —— 这就是指数赛跑的残酷之处")

# ==================== ④ 敏感度：增长率差一点点，结果差很多 ====================
print(f"\n=== 敏感度：改变玩家的强度增长，通关率怎么变 ===")
print(f"{'普通房增益':>11}{'精英加成':>9}{'等效每房':>10}{'通关率':>9}{'死亡中位':>9}")
print("-" * 50)
for pg, eb in [(1.016, 0.15), (1.018, 0.15), (1.020, 0.15),
               (1.022, 0.15), (1.020, 0.19)]:
    p = dict(P); p["power_gain"] = pg; p["elite_bonus"] = eb
    eff = pg * (1 + eb) ** (1 / p["elite_every"])
    w, d = R.batch(2500, p)
    print(f"{pg:>11.3f}{eb:>9.2f}{eff:>10.4f}{w:>9.1%}"
          f"{(np.median(d) if len(d) else 0):>9.0f}")
print(f"  （对照：敌人每房增长 {P['enemy_growth']:.4f}）")

# ==================== ⑤ 胜负在第几个房间就注定了 ====================
ratios, results = [], []
for s in range(2500):
    r = R.one_run(s)
    h = r["hist"]
    if len(h) < 20:
        continue
    ratios.append(h[:20, 2] / h[:20, 3])
    results.append(1 if r["died"] is None else 0)
ratios, results = np.array(ratios), np.array(results)

print("\n=== 胜负在第几个房间就注定了？ ===")
print(f"{'房间':>6}{'强度比与最终胜负的相关性':>26}")
for k in (1, 3, 5, 10, 15, 20):
    c = np.corrcoef(ratios[:, k - 1], results)[0, 1]
    flag = ("  ← 结局已大半可预测" if abs(c) > 0.6 else
            ("  ← 开始显现" if abs(c) > 0.35 else ""))
    print(f"{k:>6}{c:>22.3f}{flag}")
med = np.median(deaths)
print(f"""
读法：第 5 个房间（进度 10%）时，强度比就已经能解释相当一部分胜负；
到第 20 个房间（进度 40%）解释力更强。而死亡中位数在第 {med:.0f} 房（进度 {med/P['rooms']:.0%}）。

⇒ **玩家在进度 40% 时结局就大半注定了，却要玩到接近终点才揭晓。**

这是纯指数赛跑的固有特征，也是 roguelike 最经典的设计问题之一：
"我早就输了，却又白玩了 20 分钟"。
第 02 章会量化这段"无效时间"，并给出三种解法。""")
