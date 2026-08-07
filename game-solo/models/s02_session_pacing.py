"""
02 章：单局结构、会话结构，与"无效时间"

第 00 章发现：玩家在进度 40% 时结局就大半注定，却要玩到 72% 才揭晓。
中间那段就是**无效时间** —— 玩家已经赢不了，但还在按键。

本模型做两件事：

  一、量化无效时间，对比三种结构性解法
       A 缩短单局      把 50 房压缩成 25 房（重新标定成同等难度）
       B 加翻盘手段    落后时有高风险高回报的机会
       C 加早期信号    玩家能判断没戏时主动重开

  二、把结果抬到**会话层**看 IAA 的含义
       IAA 里"死亡"不只是失败，还是复活广告的触发点。
       所以每个会话能产生多少次死亡 = 广告触发机会，直接接在收入公式的 IPU 上。
       ⚠️ 触发机会 ≠ 实际观看次数（玩家意愿有上限），第 05、06 章才建那个模型。

"注定失败"用蒙特卡洛判定：从当前状态推演剩余流程，通关概率 < 5% 即认为没戏。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
import run_model as R

use_cjk_font()

DOOM_THRESHOLD = 0.05     # 通关概率低于此值 = 这局已经没戏
CHECK_EVERY = 3           # 每隔几个房间检查一次（省算力）
TRIALS = 16               # 每次检查的推演次数
N_RUNS = 800

# ---- 会话层参数：微信小游戏的尺度 ----
ROOM_SECONDS = 4.0        # 一个房间约 4 秒 → 50 房的一局约 3.3 分钟
SESSION_MIN = 15.0        # 一次会话（打开到退出）约 15 分钟
RESTART_SECONDS = 6.0     # 死亡结算 + 重开的摩擦时间

# ---------------- A：把 50 房压缩成 25 房，保持同等难度 ----------------
P_SHORT = dict(R.P)
P_SHORT.update(
    rooms=25,
    enemy_growth=R.P["enemy_growth"] ** 2,      # 每房的推进量加倍
    power_gain=R.P["power_gain"] ** 2,
    elite_every=3,                              # 精英房也相应变密
    elite_bonus=R.P["elite_bonus"] * 1.45,
    heal_every=4,
    base_dmg=R.P["base_dmg"] * 2.42,            # 标定过：让压缩后的通关率与基线一致
    # ↑ 注意不是简单的 ×2。把 50 房压成 25 房并**保持同等难度**，
    #   需要单独标定伤害基数——这本身就是第 00 章"指数敏感"的又一个例子。
)


# ---------------- B：翻盘手段 ----------------
def comeback_hook(st, rng):
    """后半程落后时，25% 概率遇到"孤注一掷"：55% 大幅拉回 / 45% 掉血"""
    p = st["p"]
    if st["room"] <= p["rooms"] * 0.4:
        return
    if st["power"] / st["enemy"] >= 1.0:
        return
    if rng.random() >= 0.25:
        return
    if rng.random() < 0.55:
        st["power"] *= 1.35
    else:
        st["hp"] -= 14.0


# ---------------- 通用：跑一局并记录"何时注定失败" ----------------
def run_with_doom(seed, p=R.P, hooks=None, early_quit=False):
    """
    返回 (结束房间, 是否通关, 首次判定没戏的房间, 是否主动重开)
    """
    r = np.random.default_rng(seed)
    hp, power = p["hp_max"], p["power_0"]
    doom_at = None
    for i in range(1, p["rooms"] + 1):
        enemy = R.enemy_power(i, p)

        if (i - 1) % CHECK_EVERY == 0:
            q = R.survivable(hp, power, i, p, trials=TRIALS, seed=seed * 977 + i)
            if doom_at is None and q < DOOM_THRESHOLD:
                doom_at = i
                if early_quit:
                    return i, False, doom_at, True      # 玩家主动重开

        hp -= R.room_damage(power, enemy, p)
        if hp <= 0:
            return i, False, doom_at, False

        power *= 1 + (p["power_gain"] - 1) * r.lognormal(0, p["luck_sigma"])
        if i % p["elite_every"] == 0:
            power *= 1 + p["elite_bonus"] * r.lognormal(0, p["luck_sigma"])

        if hooks:
            st = dict(room=i, hp=hp, power=power, enemy=enemy, p=p)
            hooks(st, r)
            hp, power = st["hp"], st["power"]
            if hp <= 0:
                return i, False, doom_at, False

        if i % p["heal_every"] == 0:
            hp = min(hp + p["heal_amount"], p["hp_max"])
    return p["rooms"], True, doom_at, False


VARIANTS = {
    "基线（50 房）":       dict(p=R.P),
    "A 缩短单局（25 房）": dict(p=P_SHORT),
    "B 加翻盘手段":        dict(p=R.P, hooks=comeback_hook),
    "C 加早期信号":        dict(p=R.P, early_quit=True),
}

print(f"跑 {N_RUNS} 局 × 4 种结构（蒙特卡洛判定'没戏'，稍慢）\n")
print("=== ① 单局层：无效时间 ===")
print(f"（房间数已归一化到 50 房尺度，便于横向比较）\n")
print(f"{'结构':<22}{'通关率':>9}{'主动重开':>10}{'平均无效房间':>14}"
      f"{'无效时间占比':>14}{'平均每局房间':>14}")
print("-" * 86)

results = {}
for name, kw in VARIANTS.items():
    p = kw["p"]
    wins = quits = 0
    wasted, played, played_raw = [], [], []
    for s in range(N_RUNS):
        end, won, doom_at, quit_ = run_with_doom(s, **kw)
        wins += won
        quits += quit_
        # 无效房间 = 从"判定没戏"到"实际结束"之间白玩的房间
        w = (end - doom_at) if (doom_at is not None and not won) else 0
        # 归一化到 50 房的尺度，好让 A 可比
        scale = 50 / p["rooms"]
        wasted.append(max(w, 0) * scale)
        played.append(end * scale)
        played_raw.append(end)          # 真实房间数 → 用来算墙钟时间
    mw, mp = np.mean(wasted), np.mean(played)
    results[name] = dict(win=wins / N_RUNS, quit=quits / N_RUNS,
                         waste=mw, waste_frac=mw / mp, rooms=mp,
                         rooms_raw=np.mean(played_raw))
    print(f"{name:<20}{wins/N_RUNS:>9.1%}{quits/N_RUNS:>10.1%}"
          f"{mw:>14.1f}{mw/mp:>14.1%}{mp:>14.1f}")

# ==================== ② 会话层：死亡频率 = 广告触发机会 ====================
print(f"\n=== ② 会话层：死亡频率 = 复活广告的触发机会 ===")
print(f"（假设一房 {ROOM_SECONDS:.0f} 秒，重开摩擦 {RESTART_SECONDS:.0f} 秒，"
      f"一次会话 {SESSION_MIN:.0f} 分钟）\n")
print(f"{'结构':<22}{'单局时长':>10}{'每会话局数':>12}"
      f"{'每会话死亡':>12}{'触发机会指数':>14}")
print("-" * 74)

base_deaths = None
for name in VARIANTS:
    r = results[name]
    run_sec = r["rooms_raw"] * ROOM_SECONDS + RESTART_SECONDS
    runs_per_session = SESSION_MIN * 60 / run_sec
    deaths_per_session = runs_per_session * (1 - r["win"])
    r["run_sec"] = run_sec
    r["runs_ps"] = runs_per_session
    r["deaths_ps"] = deaths_per_session
    if base_deaths is None:
        base_deaths = deaths_per_session
    print(f"{name:<20}{run_sec:>9.0f}s{runs_per_session:>12.1f}"
          f"{deaths_per_session:>12.1f}{deaths_per_session/base_deaths:>13.2f}×")

print(f"""
读法
----
① 单局层（这一层和买断制单机的结论一样）
   基线：24.3% 的游玩时间花在"已经没戏"的状态里，平均每局白玩约 10 房。
   A 缩短单局   —— 同时减少了浪费和总投入，还省开发量。代价是构筑深度受限。
   B 加翻盘手段 —— **它降低无效时间的方式是"让更多局能赢"，不是"让输局早点结束"**。
   C 加早期信号 —— 无效时间归零，但会误杀一部分本来能赢的局。

② 会话层（这一层是 IAA 独有的，而且会改变你的选择）
   IAA 的收入 = DAU × IPU × eCPM ÷ 1000 × 分成。
   死亡是复活广告最自然的触发点，所以**每会话死亡次数 ≈ 广告触发机会的上限**。

   于是三种解法的排序被重新洗牌：
     · A 缩短单局   触发机会大幅上升 —— 单局越短，一个会话里能死越多次
     · C 加早期信号 触发机会上升     —— 把无效时间换成了更多轮"开局→死亡"
     · B 加翻盘手段 触发机会**下降** —— 通关率涨了，死得少了

   **B 在买断制里是个不错的选择，在 IAA 里却直接削减了收入面**，
   除非——你把翻盘手段本身做成广告点位（"看广告获得一次翻盘机会"）。
   那它就从"减少广告触发"变成了"新增一个广告点位"。这是第 05 章的主题。

   ⚠️ 但**触发机会 ≠ 实际观看次数**。玩家一个会话愿意看的广告是有上限的，
   而且会疲劳。把触发机会堆到 10 次以上，IPU 也不会跟着涨 10 倍，
   反而会因为"这游戏一直在让我看广告"而伤留存。
   触发机会要**足够饱和玩家的意愿**，多出来的部分是浪费。第 06 章求这个最优点。
""")

# ==================== 出图 ====================
fig, axes = plt.subplots(1, 4, figsize=(19, 4.6))
names = list(VARIANTS)
colors = ["tab:gray", "tab:blue", "tab:green", "tab:orange"]
short = [n.split("（")[0] for n in names]


def bar(ax, vals, title, ylab):
    ax.bar(range(4), vals, color=colors)
    ax.set_xticks(range(4))
    ax.set_xticklabels(short, fontsize=8, rotation=12)
    ax.set_title(title)
    ax.set_ylabel(ylab)
    ax.grid(alpha=.3, axis="y")


bar(axes[0], [results[n]["waste_frac"] * 100 for n in names],
    "① 无效时间占比\n越低越好", "%")
bar(axes[1], [results[n]["win"] * 100 for n in names],
    "② 通关率\n三种解法对难度的副作用", "%")
bar(axes[2], [results[n]["waste"] for n in names],
    "③ 平均每局白玩的房间数", "房（归一化到 50 房）")
bar(axes[3], [results[n]["deaths_ps"] for n in names],
    "④ 每会话死亡次数\n= 复活广告的触发机会（IAA）", "次 / 15 分钟会话")
axes[3].axhline(results["基线（50 房）"]["deaths_ps"], color="k", ls=":", lw=1.2)

plt.tight_layout()
plt.savefig("../figures/s02_session_pacing.png", dpi=140)
