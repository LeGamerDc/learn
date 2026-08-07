"""
19 章：服务器生态的耦合动力学

四个分层不是独立的，它们互相依赖：
  · 免费玩家被压得越狠，流失越快
  · 大 R 失去对手和观众后，也会流失（他的动机是 Power + Competition）
  · 中小 R 夹在中间，两头受影响

模型的核心是这两条耦合。对比三种参数下服务器的命运。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

DAYS = 360
TIERS = ["免费玩家", "小 R", "中 R", "大 R"]
INIT = np.array([7400.0, 2000.0, 500.0, 100.0])
POWER = np.array([1.0, 2.5, 8.0, 30.0])        # 各层的人均战力

BASE_CHURN = np.array([0.006, 0.004, 0.003, 0.003])   # 自然流失率/天
NEW_PER_DAY = np.array([107.0, 18.2, 1.5, 0.30])      # 每天新进（买量+自然量）
# 这组数值经过标定：在 α=1.0 时各层恰好维持在初始规模（稳态）

OPPRESS_K = 0.055      # 免费/小 R 对"被压迫"的敏感度
AUDIENCE_K = 0.030     # 大 R 对"没人陪玩"的敏感度


def simulate(alpha, oppress_k=OPPRESS_K, audience_k=AUDIENCE_K, days=DAYS):
    """alpha: 第 18 章的集结叠加指数。α 越低，大 R 的有效战力占比越高。"""
    pop = INIT.copy()
    base_free = INIT[0]
    hist = []
    for _ in range(days):
        # 各层的"有效战力"：α 作用在**人数**上（多少人能有效合力），不是作用在总战力上。
        # α=1 时 100 个免费玩家 = 100 份战力；α=0.7 时只等于 25 份。
        eff = pop ** alpha * POWER
        whale_share = eff[3] / eff.sum()            # 大 R 占全服有效战力的比例

        # ① 免费/小 R：被压迫程度 = 大 R 的有效战力占比
        churn = BASE_CHURN.copy()
        churn[0] += oppress_k * whale_share
        churn[1] += oppress_k * 0.6 * whale_share

        # ② 大 R：观众指数 = 免费玩家相对初始的存量
        audience = pop[0] / base_free
        churn[3] += audience_k * max(0.0, 1.0 - audience)
        churn[2] += audience_k * 0.5 * max(0.0, 1.0 - audience)

        pop = pop * (1 - churn) + NEW_PER_DAY
        pop = np.maximum(pop, 0.0)
        hist.append(np.concatenate([pop, [whale_share, pop.sum()]]))
    return np.array(hist)


SCENARIOS = {
    "α=1.00 集结线性相加": 1.00,
    "α=0.85 中等次线性":   0.85,
    "α=0.70 个人战力主导": 0.70,
}

res = {k: simulate(a) for k, a in SCENARIOS.items()}

print(f"{'场景':<24}{'第360天总人数':>16}{'相对初始':>10}{'大R战力占比':>14}{'免费玩家':>12}")
print("-" * 80)
for k, h in res.items():
    print(f"{k:<22}{h[-1,5]:>16,.0f}{h[-1,5]/INIT.sum():>9.0%}"
          f"{h[-1,4]:>14.1%}{h[-1,0]:>12,.0f}")

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
d = np.arange(1, DAYS + 1)

for k, h in res.items():
    axes[0].plot(d, h[:, 5], lw=2, label=k)
    axes[1].plot(d, h[:, 4] * 100, lw=2, label=k)
axes[0].set_title("① 服务器总人数")
axes[0].set_xlabel("天"); axes[0].set_ylabel("人")
axes[1].set_title("② 大 R 占全服有效战力的比例\n这条线上升 = 生态正在恶化")
axes[1].set_xlabel("天"); axes[1].set_ylabel("%")

h = res["α=0.70 个人战力主导"]
for i, t in enumerate(TIERS):
    axes[2].plot(d, h[:, i] / INIT[i] * 100, lw=2, label=t)
axes[2].set_title("③ α=0.70 时各分层的存活曲线\n免费玩家先走，大 R 随后")
axes[2].set_xlabel("天"); axes[2].set_ylabel("相对初始人数 %")

for ax in axes:
    ax.legend(fontsize=8); ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/m19_ecology.png", dpi=140)

# ---------- 各层的相对损失 ----------
print("\n=== α=0.70 场景下，各层第 360 天相对初始的存量 ===")
for i, t in enumerate(TIERS):
    idx = np.where(h[:, i] < INIT[i] * 0.5)[0]
    when = f"（第 {idx[0]+1} 天跌破 50%）" if len(idx) else ""
    print(f"  {t:<10}{h[-1, i] / INIT[i]:>8.0%}   {when}")

print("""
关键发现：免费玩家只掉了两成，大 R 却掉了三分之二。
**大 R 对生态恶化的敏感度远高于免费玩家** —— 基本盘的小幅萎缩，
会被放大成头部的大幅流失。原因在第 02 章：大 R 的动机是 Power + Competition，
而这两样都需要别人在场才成立。

推论：**不要用大 R 的流失来判断生态健康，那时已经晚了。**
要盯的先行指标是"大 R 占全服有效战力的比例"（图 ②）—— 它一路上行就是警报。""")
