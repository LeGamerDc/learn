"""
03 章：用资源流引擎搭一个迷你 SLG 经济

    矿场 ──→ 金币 ──→ 升级城建 ──┐
                                 ├──→ 产能提升（正反馈回路，回到两个源）
    农田 ──→ 粮食 ──→ 练兵 ──┬───┘
                             ↓
                            兵 ──→ 打仗 ──→ 战损（兵永久消失）
                                    ↑
    体力恢复 ──→ 体力（有上限）──────┘  体力是"门"：决定每天最多打几仗

注意这个设计里的**货币隔离**：金币只喂城建，粮食只喂兵。
两条链互不抢资源，所以可以分别调节。第 06 章会讲为什么必须这么做。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font
from econ import Economy

use_cjk_font()

DAYS = 180

e = Economy(gold=0, food=0, troops=0, level=1, stamina=0)
# 体力有上限 → 超出部分是被浪费的投放。这就是"体力上限"的经济含义。
e.cap(stamina=120)

# ---------------- ① 投放（source）----------------
# 产能随城建等级指数增长 —— 这是正反馈回路的回程
e.source("矿场", "gold", lambda e: 2000 * 1.06 ** (e.p["level"] - 1))
e.source("农田", "food", lambda e: 1500 * 1.06 ** (e.p["level"] - 1))
e.source("体力恢复", "stamina", 30)          # 每天恢复 30，但每天最多用 20


# ---------------- ② 回收：升级城建（金币的唯一 sink）----------------
def upgrade(econ):
    """成本随等级指数增长。返回本步花掉的金币。"""
    spent = 0.0
    while True:
        cost = 5000 * 1.35 ** (econ.p["level"] - 1)
        if econ.p["gold"] < cost:
            break
        spent += econ._take("gold", cost)
        econ._give("level", 1)
    return spent


e.add("升级城建", "drain", upgrade)


# ---------------- ③ 转换器：练兵（粮食 → 兵）----------------
# 兵营产能随城建等级提升，是练兵速度的上限
e.converter("练兵",
            cost={"food": 80},
            gain={"troops": 1},
            times=lambda e: int(15 * e.p["level"]))


# ---------------- ④ 回收：战损（兵的唯一 sink）----------------
def combat(econ):
    """打仗要花体力。体力是门，它决定了每天最多能打几仗。"""
    battles = min(int(econ.p["stamina"]), 20)
    if battles <= 0 or econ.p["troops"] <= 0:
        return 0.0
    econ._take("stamina", battles)
    losses = econ.p["troops"] * 0.04 * (battles / 20)
    return econ._take("troops", losses)


e.add("战损", "drain", combat)

df = e.run(DAYS)
# level 是计数器不是资源（只增不减），排除在收支平衡表之外
e.audit(df, skip=("level",))

# ---------------- 出图 ----------------
fig, axes = plt.subplots(2, 2, figsize=(13, 9))

ax = axes[0, 0]
ax.plot(df.index, df["gold"], label="金币")
ax.plot(df.index, df["food"], label="粮食")
ax.set_title("① 存量：金币被城建吃成锯齿，粮食被练兵吃平")
ax.legend(); ax.grid(alpha=.3)

ax = axes[0, 1]
ax.plot(df.index, df["troops"], color="tab:red")
ax.set_title("② 兵力：练兵（源）与战损（汇）自动收敛到平衡点")
ax.grid(alpha=.3)

ax = axes[1, 0]
ax.plot(df.index, df["流|矿场|gold"].cumsum(), label="金币累计投放")
ax.plot(df.index, (-df["流|升级城建|gold"]).cumsum(), label="金币累计回收", ls="--")
ax.plot(df.index, df["流|农田|food"].cumsum(), label="粮食累计投放")
ax.plot(df.index, (-df["流|练兵|food"]).cumsum(), label="粮食累计回收", ls="--")
ax.set_title("③ 两种资源的收支：线贴得越紧越健康")
ax.set_xlabel("天"); ax.legend(fontsize=8); ax.grid(alpha=.3)

ax = axes[1, 1]
ax.plot(df.index, df["溢出_stamina"].cumsum(), color="tab:orange")
ax.set_title("④ 体力溢出累计：恢复 30/天，只用得掉 20/天")
ax.set_xlabel("天"); ax.grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m03_slg_flow.png", dpi=140)

print(f"\n第 {DAYS} 天：城建 {int(df['level'].iloc[-1])} 级，"
      f"兵力 {df['troops'].iloc[-1]:,.0f}，粮食存量 {df['food'].iloc[-1]:,.0f}")
plt.show()
