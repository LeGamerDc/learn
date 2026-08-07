"""
17 章：匹配系统

2000 名玩家，真实实力服从正态分布。对比三种匹配策略：
  A 随机匹配
  B Elo 匹配（同分段内随机）
  C Elo 匹配 + 连败保护（连败时临时下调匹配分，去匹配更弱的对手）

看三件事：
  ① 评分能否收敛到真实实力
  ② 胜率分布（越集中在 50% 越健康）
  ③ 流失（连败越久，每场后流失的概率越高）
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()
rng = np.random.default_rng(11)

N = 2000
DAYS = 30
MATCHES_PER_DAY = 4
K = 32                 # Elo 的 K 因子
QUIT_BASE = 0.03       # 连败满 3 场后，每再输一场的流失概率增量

true_skill = rng.normal(1500, 250, N)


def win_prob(a, b):
    return 1.0 / (1.0 + 10 ** ((b - a) / 400.0))


def simulate(mode):
    rating = np.full(N, 1500.0)
    alive = np.ones(N, dtype=bool)
    streak = np.zeros(N, dtype=int)
    wins = np.zeros(N)
    games = np.zeros(N)
    hist = []

    for _ in range(DAYS):
        for _ in range(MATCHES_PER_DAY):
            idx = np.flatnonzero(alive)
            if len(idx) < 2:
                break
            rng.shuffle(idx)
            if mode == "A":
                pairs = idx[:len(idx) // 2 * 2].reshape(-1, 2)
            else:
                # 按评分排序后相邻配对 = 同水平匹配
                mm = rating[idx].copy()
                if mode == "C":
                    # 连败保护：临时下调匹配分 → 被分到更弱的对手
                    mm -= 120.0 * np.minimum(streak[idx], 3)
                order = idx[np.argsort(mm)]
                pairs = order[:len(order) // 2 * 2].reshape(-1, 2)

            a, b = pairs[:, 0], pairs[:, 1]
            p = win_prob(true_skill[a], true_skill[b])
            a_wins = rng.random(len(a)) < p

            exp_a = win_prob(rating[a], rating[b])
            delta = K * (a_wins.astype(float) - exp_a)
            rating[a] += delta
            rating[b] -= delta

            games[a] += 1; games[b] += 1
            wins[a] += a_wins; wins[b] += ~a_wins
            streak[a] = np.where(a_wins, 0, streak[a] + 1)
            streak[b] = np.where(a_wins, streak[b] + 1, 0)
            # 连败越久，流失概率越高（比"连败 N 次必走"更接近真实）
            risk = QUIT_BASE * np.maximum(streak - 2, 0)
            alive &= ~((rng.random(N) < risk) & alive)

        ok = games > 0
        corr = np.corrcoef(rating[ok], true_skill[ok])[0, 1] if ok.sum() > 2 else 0
        hist.append((alive.mean(), corr))
    wr = np.divide(wins, games, out=np.full(N, .5), where=games > 0)
    return np.array(hist), rating, wr, alive


MODES = {"A": "A 随机匹配", "B": "B Elo 匹配", "C": "C Elo + 连败保护"}
res = {m: simulate(m) for m in MODES}

print(f"{'策略':<20}{'留存率':>10}{'评分-实力相关':>16}{'胜率标准差':>14}{'胜率<35%的玩家':>16}")
print("-" * 78)
for m, label in MODES.items():
    hist, rating, wr, alive = res[m]
    print(f"{label:<18}{hist[-1,0]:>10.1%}{hist[-1,1]:>16.3f}"
          f"{wr.std():>14.3f}{(wr < 0.35).mean():>16.1%}")

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
d = np.arange(1, DAYS + 1)
for m, label in MODES.items():
    hist, rating, wr, alive = res[m]
    axes[0].plot(d, hist[:, 0] * 100, lw=2, label=label)
    axes[1].plot(d, hist[:, 1], lw=2, label=label)
    axes[2].hist(wr, bins=40, histtype="step", lw=2, label=label)

axes[0].set_title("① 留存率（连败越久流失概率越高）")
axes[0].set_ylabel("%"); axes[0].set_xlabel("天")
axes[1].set_title("② Elo 评分与真实实力的相关系数\n收敛速度")
axes[1].set_xlabel("天")
axes[2].set_title("③ 玩家胜率分布\n越集中在 50% 越健康")
axes[2].set_xlabel("胜率"); axes[2].axvline(.5, color="k", ls=":")
for ax in axes:
    ax.legend(fontsize=8); ax.grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m17_matchmaking.png", dpi=140)
