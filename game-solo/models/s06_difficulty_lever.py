"""
06 章：难度即变现旋钮 —— 本课的招牌模型

难度这一个参数，同时接在两条**方向相反**的线上：

    难度 ↑ → 死得多 → 复活广告触发多 → IPU ↑ → ARPDAU ↑   （收入 ↑）
    难度 ↑ → 挫败感强 → 次留 ↓ → 活跃天数 ↓                （收入 ↓）

广告倍率也一样：

    倍率 ↑ → 渗透率 ↑ → IPU ↑（但会饱和，第 05 章）        （收入 ↑）
    倍率 ↑ → 局外注入 ↑ → 内容寿命 ↓ → 留存被截断（第 03 章）（收入 ↓）

本模型把前五章全部接起来，在 (难度 × 广告倍率) 的二维平面上求 LTV 最优：

    第 00 章  run_model      难度 → 通关率、每局房间数
    第 02 章  会话结构        → 每会话死亡次数
    第 03 章  内容寿命        局外注入 → 内容还能撑几天（用解析解，不再跑仿真）
    第 04 章  LTV            Σ留存 × IPU × eCPM ÷ 1000 × 分成
    第 05 章  意愿模型        倍率 + 死亡次数 → IPU

⚠️ 本模型里**唯一没有实证支撑的是"难度 → 次留"那条钟形曲线**（标记【推导】）。
   它的形状是假设出来的。上线后你应该用真实 AB 数据替换它 ——
   **但模型的结构（两条相反的线相乘）不依赖那个假设。**
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
import run_model as R

use_cjk_font()
rng = np.random.default_rng(11)

# ---------------- 会话与收入参数（承自第 02、04 章）----------------
ROOM_SECONDS, RESTART_SECONDS, SESSION_MIN = 4.0, 6.0, 15.0
ECPM, SHARE, WINDOW = 60.0, 0.50, 90
DECAY = 0.504                 # 留存衰减斜率
CHURN_TAU = 7.0               # 内容耗尽后，留存的衰减时间常数（天）

# ---------------- 【推导】难度 → 次留 的钟形曲线 ----------------
# 太难 → 挫败流失；太简单 → 无聊流失。左右不对称：太难杀得更快。
R1_MAX, W_STAR, SIG_HARD, SIG_EASY = 0.45, 0.30, 0.15, 0.35


def r1_of_winrate(w):
    """【推导】通关率 → 次留。上线后请用真实 AB 数据替换这条曲线。"""
    sig = np.where(w < W_STAR, SIG_HARD, SIG_EASY)
    return R1_MAX * np.exp(-((w - W_STAR) / sig) ** 2)


# ---------------- 内容寿命：第 03 章模型的解析解 ----------------
RUNS_PER_DAY, RUN_REWARD_0 = 5.0, 100.0
COST_0, OUT_GROWTH, COST_GROWTH, MAX_LEVEL = 300.0, 1.030, 1.035, 100


def content_life(inject):
    """
    局外注入倍数 → 内容耗尽天数。
    dL/dt = 日产出(L)/升级成本(L) = A·r^L，  A = 基础日产出(1+inject)/COST_0，r = OG/CG
    积分得   t(Lmax) = (1 − r^(−Lmax)) / (A·ln r)
    （在第 03 章用离散仿真验证过：inject=0 → 77 天 vs 仿真 79 天）
    """
    A = RUNS_PER_DAY * RUN_REWARD_0 * (1 + inject) / COST_0
    r = OUT_GROWTH / COST_GROWTH
    return (1 - r ** (-MAX_LEVEL)) / (A * np.log(r))


# ---------------- 意愿模型（承自第 05 章）----------------
K, THRESH, FATIGUE = 1.2, 2.0, 0.40    # 承第 05 章（注意 k/10）
SESSIONS_PER_DAY = 1.8                 # 第 11 章：割草类的每天会话数
FIXED_PLACEMENTS = [           # 复活以外的点位，不随难度变
    dict(base_min=1.2, trig=8.0, reach=0.90, layer="局内"),   # 重抽三选一
    dict(base_min=1.0, trig=5.0, reach=0.70, layer="局内"),   # 局内翻倍拾取
    dict(base_min=1.5, trig=4.0, reach=0.85, layer="局内"),   # 临时增益
    dict(base_min=2.0, trig=5.4, reach=1.00, layer="局外"),   # 结算翻倍
    dict(base_min=6.0, trig=1.0, reach=1.00, layer="局外"),   # 离线翻倍
    dict(base_min=2.5, trig=2.0, reach=1.00, layer="局外"),   # 每日免费领
]


def willingness(v):
    return 1.0 / (1.0 + np.exp(-K * (v - THRESH)))


def session_ads(deaths_per_session, mult, n=4000):
    """返回 (IPU, 局外注入的分钟等效量)"""
    places = [dict(base_min=3.0, trig=deaths_per_session, reach=1.0,
                   layer="局内")] + FIXED_PLACEMENTS
    trig = []
    for i, p in enumerate(places):
        trig += [i] * max(int(round(p["trig"] * 10)), 0)
    trig = np.array(trig)
    if len(trig) == 0:
        return 0.0, 0.0
    watched = np.zeros(len(places))
    total = 0
    for _ in range(n):
        k = 0
        for idx in rng.permutation(trig):
            p = places[idx]
            if rng.random() > p["reach"]:
                continue
            if rng.random() < willingness(p["base_min"] * (mult - 1)) * FATIGUE ** (k / 10.0):
                k += 1
                watched[idx] += 1
        total += k
    per_session = total / n / 10.0
    outer = sum(w / n / 10.0 * p["base_min"] * (mult - 1)
                for w, p in zip(watched, places) if p["layer"] == "局外")
    # ⚠️ 换算成**日** IPU —— 第 04 章的 LTV 公式要的是每天的次数
    return per_session * SESSIONS_PER_DAY, outer * SESSIONS_PER_DAY


# ---------------- LTV ----------------
def ltv(r1, ipu, life, window=WINDOW):
    d = np.arange(window + 1)
    base = np.where(d == 0, 1.0, r1 * np.maximum(d, 1) ** (-DECAY))
    # 内容耗尽后，留存额外指数衰减
    tail = np.where(d <= life, 1.0, np.exp(-(d - life) / CHURN_TAU))
    return (base * tail).sum() * ipu * ECPM / 1000 * SHARE


# ============================================================
# ① 难度这一条线：先分别看两个方向
# ============================================================
print("=== ① 难度同时接在两条相反的线上 ===\n")

PGS = [1.014, 1.016, 1.018, 1.019, 1.0195, 1.020, 1.0205, 1.021, 1.022, 1.024, 1.026]
diff = []
for pg in PGS:
    p = dict(R.P); p["power_gain"] = pg
    w, deaths = R.batch(6000, p)
    mean_rooms = (deaths.sum() + w * 6000 * p["rooms"]) / 6000
    run_sec = mean_rooms * ROOM_SECONDS + RESTART_SECONDS
    runs_ps = SESSION_MIN * 60 / run_sec
    dps = runs_ps * (1 - w)
    diff.append(dict(pg=pg, w=w, rooms=mean_rooms, dps=dps, r1=float(r1_of_winrate(w))))

print(f"{'玩家增益':>10}{'通关率':>9}{'每局房间':>10}{'每会话死亡':>12}"
      f"{'次留【推导】':>14}")
print("-" * 56)
for d in diff:
    print(f"{d['pg']:>10.3f}{d['w']:>9.1%}{d['rooms']:>10.1f}"
          f"{d['dps']:>12.2f}{d['r1']:>14.1%}")

print("""
读法：**两列的峰值不在同一个地方。**
  "每会话死亡"随难度单调上升 —— 这是收入面
  "次留"是钟形，峰值在通关率 30% 附近 —— 这是留存面
  ⇒ 最优点必然是两者的妥协。往哪边妥协？往下看。
""")

# ============================================================
# ② 二维扫描：(难度 × 广告倍率) → LTV
# ============================================================
print("=== ② 在 (难度 × 广告倍率) 平面上求 LTV 最优 ===\n")

MULTS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
grid = np.zeros((len(diff), len(MULTS)))
info = {}
for i, d in enumerate(diff):
    for j, m in enumerate(MULTS):
        ipu, outer = session_ads(d["dps"], m)
        inject = outer / (SESSION_MIN * SESSIONS_PER_DAY)   # 分钟等效 → 日产出倍数
        life = content_life(inject)
        v = ltv(d["r1"], ipu, life)
        grid[i, j] = v
        info[(i, j)] = (ipu, inject, life)

print(f"{'通关率':>8}", end="")
for m in MULTS:
    print(f"{str(m) + '×':>9}", end="")
print("   ← 单元格 = 到手 LTV(90天)，元")
print("-" * 64)
for i, d in enumerate(diff):
    print(f"{d['w']:>8.1%}", end="")
    for j in range(len(MULTS)):
        print(f"{grid[i, j]:>9.2f}", end="")
    print()

bi, bj = np.unravel_index(grid.argmax(), grid.shape)
b_ipu, b_inj, b_life = info[(bi, bj)]
best_w = diff[bi]["w"]

# 对照组：只看留存最优 / 只看 IPU 最优
r1s = np.array([d["r1"] for d in diff])
ri = int(r1s.argmax())
ii = int(np.argmax([info[(i, len(MULTS) - 1)][0] for i in range(len(diff))]))

print(f"""
=== ③ 三种"最优"的对比 ===

{'口径':<26}{'通关率':>9}{'倍率':>8}{'LTV':>9}
{'-' * 54}
{'LTV 最优（本模型的答案）':<24}{best_w:>9.1%}{MULTS[bj]:>7.1f}×{grid[bi, bj]:>9.2f}
{'只看留存（体验最优）':<24}{diff[ri]['w']:>9.1%}{'—':>8}{grid[ri].max():>9.2f}
{'只看 IPU（最贪的变现）':<24}{diff[ii]['w']:>9.1%}{MULTS[-1]:>7.1f}×{grid[ii, -1]:>9.2f}

最优点的细节：IPU {b_ipu:.2f}，局外注入 {b_inj:.2f}×，内容寿命 {b_life:.0f} 天
""")

flat = [diff[i]["w"] for i in range(len(diff))
        if grid[i, bj] >= grid[bi, bj] * 0.98]
print(f"""
=== ④ 结论 ===

**一、LTV 最优区间是"平"的，而且它覆盖了体验最优点。**

   LTV 的峰值在通关率 {best_w:.0%}，留存的峰值在 {diff[ri]['w']:.0%}。
   但更重要的是：**LTV 在通关率 {min(flat):.0%}~{max(flat):.0%} 这一整段里几乎不变**
   （都在最大值的 98% 以上）。

   为什么会平？看那两列就明白了：往难的方向走一档，
   次留只掉一点（{diff[ri]['r1']:.1%} → {diff[bi]['r1']:.1%}），
   但每会话死亡从 {diff[ri]['dps']:.2f} 涨到 {diff[bi]['dps']:.2f} ——
   **IPU 的增益刚好抵消了留存的损失。**

   ⇒ **这意味着：在这个区间内，难度该完全按体验来定，变现不用插嘴。**
     这是本章最值得记住的一句话。

   而区间之外就完全不是这样了：
   最贪的那一档（通关率 {diff[ii]['w']:.0%} + 倍率 {MULTS[-1]:.0f}×）
   LTV 只有 {grid[ii, -1]:.2f} 元，**比最优的 {grid[bi, bj]:.2f} 元低 {1 - grid[ii, -1]/grid[bi, bj]:.0%}**。
   "把难度调高逼玩家看广告"在这个模型里是净亏的，而且亏得很惨。

**二、广告倍率有明确的内部最优（第 05 章解不了的问题，在这里解开了）。**

   最优倍率 {MULTS[bj]:.1f}×。往上加倍率，IPU 已经饱和（第 05 章的形状），
   但局外注入还在涨、内容寿命还在掉 —— 净效果是 LTV 下降。

   ⇒ 第 05 章那个"每点注入换 IPU"指标定不出倍率，是因为它缺了留存这一环。
     **把留存接进来，最优点就出现了。**

**三、这两个旋钮不是独立的。**

   难度高 → 死得多 → 复活广告触发多 → 即使倍率不变，注入也变多 → 内容寿命更短。
   **所以调难度的时候必须重新检查内容寿命**，反之亦然。
   这就是为什么它们要放在同一张表上看，而不是分别调。
""")

# ============================================================
# ⑤ 关键敏感度：内容寿命值不值钱，取决于你的留存有多好
# ============================================================
print("=== ⑤ 最优倍率随留存水平漂移 ===\n")
print("固定难度在最优档，只改次留水平，看最优广告倍率往哪走：\n")
print(f"{'次留水平':>10}{'最优倍率':>10}{'该点内容寿命':>14}"
      f"{'最优 LTV':>11}{'倍率5×时的LTV':>16}{'高倍率的代价':>14}")
print("-" * 78)

d0 = diff[bi]
for r1 in (0.20, 0.30, 0.45, 0.60, 0.75):
    vals = []
    for j, m in enumerate(MULTS):
        ipu, inject, life = info[(bi, j)]
        vals.append(ltv(r1, ipu, life))
    vals = np.array(vals)
    j_best = int(vals.argmax())
    _, _, life_best = info[(bi, j_best)]
    print(f"{r1:>10.0%}{MULTS[j_best]:>9.1f}×{life_best:>14.0f} 天"
          f"{vals[j_best]:>11.2f}{vals[-1]:>16.2f}"
          f"{1 - vals[-1]/vals[j_best]:>14.1%}")

print("""
读法 —— 一个原本以为会成立、结果没成立的发现
--------------------------------------------
**我原本预期"留存越好，最优广告倍率越低"** —— 理由是：内容寿命通过
"截断留存曲线的尾巴"起作用，尾巴越粗，截掉的损失越大，所以该压住倍率。

**但在这套参数下，最优倍率完全没漂移：从留存 20% 到 75%，最优都是 4.0×。**

  只有"用 5× 而不是最优倍率的代价"随留存上升了一点：2.3% → 3.2%。
  **方向是对的，量级小到可以忽略。**

⇒ **为什么？因为在这套参数下，内容寿命根本不是约束。**

    最优点的内容寿命 48 天，而玩家 90 天里累计只活跃 7.9 天（第 04 章）。
    **留存曲线在第 48 天早就贴地了 —— 截不截那条尾巴，几乎不影响 LTV。**

⇒ **这给出一个很实用的诊断，比原来那个结论有用得多：**

    **先比较两个数：内容寿命 vs "你的留存曲线衰减到可忽略的天数"。**

      · 内容寿命 **远大于**留存衰减期 → **内容不是瓶颈，倍率可以放心调高**，
        瓶颈在别处（前 3 分钟、构筑深度、点位设计）
      · 内容寿命 **接近或小于**留存衰减期 → **内容是瓶颈**，
        此时才需要压倍率、加 prestige、扩内容（第 11、12 章）

    **本模型属于前者。** 如果你把内容量砍到 30 级，
    结论就会反过来 —— 这是动手任务 F。

⚠️ 顺带一提，这一段是本课少数几个"我预期错了、模型纠正了我"的地方之一。
   **保留它比删掉它有价值**：它提醒你，
   **"某个机制理论上会起作用"和"它在你的参数下真的起作用"是两回事。**
""")

# ============================================================
# 出图
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

ws = np.array([d["w"] for d in diff])
axes[0].plot(ws * 100, [d["dps"] for d in diff], "o-", lw=2.5,
             color="tab:blue", label="每会话死亡次数（收入面）")
axes[0].set_xlabel("通关率 %"); axes[0].set_ylabel("次 / 会话", color="tab:blue")
ax2 = axes[0].twinx()
ax2.plot(ws * 100, r1s * 100, "s--", lw=2.5, color="tab:red",
         label="次留【推导】（留存面）")
ax2.set_ylabel("次留 %", color="tab:red")
axes[0].set_title("① 两条方向相反的线\n峰值不在同一个地方")

im = axes[1].imshow(grid, origin="lower", aspect="auto", cmap="RdYlGn",
                    extent=[0, len(MULTS), 0, len(diff)])
axes[1].set_xticks(np.arange(len(MULTS)) + .5)
axes[1].set_xticklabels([f"{m}×" for m in MULTS], fontsize=8)
axes[1].set_yticks(np.arange(len(diff)) + .5)
axes[1].set_yticklabels([f"{d['w']:.0%}" for d in diff], fontsize=8)
axes[1].plot(bj + .5, bi + .5, "k*", ms=18)
axes[1].set_xlabel("广告倍率"); axes[1].set_ylabel("通关率")
axes[1].set_title("② LTV 曲面\n★ = 最优点")
plt.colorbar(im, ax=axes[1], label="到手 LTV(90天) 元")

axes[2].plot(MULTS, grid[bi], "o-", lw=2.5, color="tab:green", label="LTV")
axes[2].axvline(MULTS[bj], color="k", ls=":", lw=1.5)
ax3 = axes[2].twinx()
ax3.plot(MULTS, [info[(bi, j)][2] for j in range(len(MULTS))],
         "s--", lw=2.2, color="tab:orange")
ax3.set_ylabel("内容寿命（天）", color="tab:orange")
axes[2].set_xlabel("广告倍率"); axes[2].set_ylabel("LTV（元）", color="tab:green")
axes[2].set_title(f"③ 固定最优难度，扫倍率\nLTV 有内部最优")

axes[0].grid(alpha=.3); axes[2].grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/s06_difficulty_lever.png", dpi=140)
