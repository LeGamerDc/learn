"""
05 章：战斗数值
① 三种伤害公式的减伤曲线对比 —— 看清各自的失控风险
② 减法公式的"不破防悬崖"
③ 战力 = EHP × DPS，以及为什么属性要均衡（AM-GM 不等式的游戏版）
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

ATK = 1000.0
defs = np.arange(0, 3001, 10)

# ---------------- 三种伤害公式 ----------------
# 减法：伤害 = 攻 - 防
dmg_sub = np.maximum(ATK - defs, 0)

# 乘法（百分比减伤）：伤害 = 攻 × (1 - 减伤率)，减伤率直接由防御百分比给出
#   这里假设 1 点防御 = 0.025% 减伤，硬顶 75%
reduce_mul = np.minimum(defs * 0.00025, 0.75)
dmg_mul = ATK * (1 - reduce_mul)

# 除法（饱和公式）：减伤率 = 防 / (防 + K)，K 是"半效点"——减伤 50% 所需的防御
K = 1000.0
reduce_div = defs / (defs + K)
dmg_div = ATK * (1 - reduce_div)

fig, axes = plt.subplots(2, 2, figsize=(13, 9))

ax = axes[0, 0]
ax.plot(defs, dmg_sub, lw=2, label="减法  攻−防")
ax.plot(defs, dmg_mul, lw=2, label="乘法  攻×(1−防×0.025%)，顶75%")
ax.plot(defs, dmg_div, lw=2, label=f"除法  攻×K/(K+防)，K={K:.0f}")
ax.axvline(ATK, color="tab:red", ls=":", lw=1.5)
ax.text(ATK + 60, ATK * .8, "防御 = 攻击\n减法公式在此归零", color="tab:red", fontsize=9)
ax.set_xlabel("防御"); ax.set_ylabel(f"实际伤害（攻击固定 {ATK:.0f}）")
ax.set_title("① 三种伤害公式")
ax.legend(fontsize=9); ax.grid(alpha=.3)

# ---------------- ② 每 +100 点防御的边际收益 ----------------
ax = axes[0, 1]
for name, dmg in [("减法", dmg_sub), ("乘法", dmg_mul), ("除法", dmg_div)]:
    # 边际收益：多 100 点防御，少挨多少伤害（占当前伤害的比例）
    marginal = -np.gradient(dmg, defs) * 100 / np.maximum(dmg, 1e-9)
    ax.plot(defs, marginal * 100, lw=2, label=name)
ax.set_xlabel("防御"); ax.set_ylabel("每 +100 防御，减少的伤害占比 (%)")
ax.set_title("② 防御的边际收益\n减法/乘法：越堆越强（危险）｜除法：边际递减（健康）")
ax.set_ylim(0, 30); ax.legend(); ax.grid(alpha=.3)

# ---------------- ③ 不破防悬崖：战斗时长 ----------------
ax = axes[1, 0]
HP = 10000.0
for name, dmg in [("减法", dmg_sub), ("乘法", dmg_mul), ("除法", dmg_div)]:
    rounds = HP / np.maximum(dmg, 1e-9)
    ax.plot(defs, np.minimum(rounds, 200), lw=2, label=name)
ax.set_xlabel("防御"); ax.set_ylabel("击杀所需回合数（截断到 200）")
ax.set_title("③ 战斗时长：减法公式在防御接近攻击时垂直起飞")
ax.set_yscale("log"); ax.legend(); ax.grid(alpha=.3, which="both")

# ---------------- ④ 战力 = EHP × DPS，属性怎么分配最优 ----------------
# 总共 T 点属性，分配给 攻 / 防 / 血
T = 3000.0
grid = np.linspace(0.01, 0.98, 120)
best, best_pt = -1, None
Z = np.full((len(grid), len(grid)), np.nan)
for i, fa in enumerate(grid):          # 攻击占比
    for j, fd in enumerate(grid):      # 防御占比
        fh = 1 - fa - fd               # 生命占比
        if fh <= 0.01:
            continue
        atk = 100 + T * fa
        dfn = T * fd
        hp = 1000 + T * fh * 10
        ehp = hp / (1 - dfn / (dfn + K))       # 等效生命 = 血 ÷ (1−减伤)
        power = ehp * atk
        Z[j, i] = power
        if power > best:
            best, best_pt = power, (fa, fd, fh)

ax = axes[1, 1]
im = ax.contourf(grid, grid, Z / 1e6, levels=25, cmap="viridis")
ax.plot(best_pt[0], best_pt[1], "r*", ms=18)
ax.set_xlabel("攻击占比"); ax.set_ylabel("防御占比")
ax.set_title("④ 战力 = EHP × DPS 的等高线\n红星 = 最优分配（不是极端，是均衡）")
plt.colorbar(im, ax=ax, label="战力（百万）")

plt.tight_layout()
plt.savefig("../figures/m05_combat.png", dpi=140)

print(f"最优属性分配：攻击 {best_pt[0]:.0%}  防御 {best_pt[1]:.0%}  生命 {best_pt[2]:.0%}")
print(f"最优战力 {best:,.0f}")
for name, pt in [("全堆攻击", (0.96, 0.02)), ("全堆防御", (0.02, 0.96)),
                 ("攻防各半", (0.49, 0.49))]:
    fa, fd = pt
    fh = 1 - fa - fd
    atk = 100 + T * fa
    dfn = T * fd
    hp = 1000 + T * fh * 10
    p = hp / (1 - dfn / (dfn + K)) * atk
    print(f"  {name:<8} 战力 {p:>14,.0f}   仅为最优的 {p / best:.1%}")
