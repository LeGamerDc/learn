"""
11 章：完整的 SLG 经济仿真 + 自动体检报告

整合前十章：
  第 04 章  分段成长曲线
  第 05 章  战力 = EHP × DPS
  第 06 章  货币隔离（金币→城建，粮食→兵）
  第 07 章  日产出预算 + 付费作为独立渠道
  第 08 章  混合 sink（层级 + 比例损耗）
  第 09 章  通胀三指标

跑 360 天，输出诊断报告：每一项都给出判定，不合格会说明原因。
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()
pd.set_option("display.unicode.east_asian_width", True)

DAYS = 360

# ============ 玩家分层：(名称, 人口占比, 付费产出倍数) ============
TIERS = [
    ("免费玩家", 0.75, 0.0),
    ("小 R",    0.18, 0.3),
    ("中 R",    0.06, 1.5),
    ("大 R",    0.01, 6.0),
]

# ============ 可调数值参数 ============
P = dict(
    gold_base=2000.0,       # 1 级城建日产金币
    food_base=1500.0,       # 1 级城建日产粮食
    output_growth=1.06,     # 每级城建的产能提升
    build_cost=5000.0,      # 城建首级成本
    build_growth=1.32,      # 城建成本增长率
    troop_food=80.0,        # 练 1 兵的粮食成本
    train_cap=15,           # 每级城建提供的日练兵产能
    stamina_regen=30.0,     # 日体力恢复
    stamina_cap=120.0,
    battles_per_day=25,     # 每天最多打几仗（1 仗 1 体力）
    loss_rate=0.05,         # 每天满额作战的兵力损失率（比例型 sink）
    gold_decay=0.03,        # 金币的比例型 sink（维护费/损耗）
    deep_sink_start=15,     # 城建到这一级后开放"高阶强化"深度 sink
    deep_sink_cost=2.0e5,   # 深度 sink 首级成本
    deep_sink_growth=1.55,  # 深度 sink 成本增长（超线性，专吃大 R）
)


def simulate_tier(pay_mult, p=P, days=DAYS):
    gold = food = troops = 0.0
    stamina = 0.0
    level, deep = 1, 0
    rows = []
    for d in range(1, days + 1):
        # ---------- 投放 ----------
        gold_in = p["gold_base"] * p["output_growth"] ** (level - 1) * (1 + pay_mult)
        food_in = p["food_base"] * p["output_growth"] ** (level - 1) * (1 + pay_mult)
        # 体力是时间货币：付费买不到（第 06 章）
        stam_in = p["stamina_regen"]
        gold += gold_in
        food += food_in
        stam_over = max(stamina + stam_in - p["stamina_cap"], 0.0)
        stamina = min(stamina + stam_in, p["stamina_cap"])

        gold_out = food_out = 0.0

        # ---------- 回收 1：城建升级（层级型）----------
        while True:
            cost = p["build_cost"] * p["build_growth"] ** (level - 1)
            if gold < cost:
                break
            gold -= cost
            gold_out += cost
            level += 1

        # ---------- 回收 2：高阶强化（深度 sink，超线性，专吃大 R）----------
        if level >= p["deep_sink_start"]:
            while True:
                cost = p["deep_sink_cost"] * p["deep_sink_growth"] ** deep
                if gold < cost:
                    break
                gold -= cost
                gold_out += cost
                deep += 1

        # ---------- 回收 3：金币比例损耗 ----------
        loss = gold * p["gold_decay"]
        gold -= loss
        gold_out += loss

        # ---------- 转换器：练兵（粮食 → 兵）----------
        can_train = min(int(p["train_cap"] * level), int(food / p["troop_food"]))
        food -= can_train * p["troop_food"]
        food_out += can_train * p["troop_food"]
        troops += can_train

        # ---------- 回收 4：战损（兵的比例型 sink）----------
        battles = min(int(stamina), p["battles_per_day"])
        stamina -= battles
        dead = troops * p["loss_rate"] * (battles / p["battles_per_day"]) if troops > 0 else 0.0
        troops -= dead

        # ---------- 战力：EHP × DPS 的简化版（第 05 章）----------
        ehp = troops * (1 + level * 0.05) * (1 + deep * 0.12)
        dps = troops * (1 + level * 0.05) * (1 + deep * 0.12)
        power = np.sqrt(max(ehp * dps, 0.0))

        rows.append(dict(天=d, 金币=gold, 粮食=food, 兵=troops, 城建=level,
                         深度强化=deep, 战力=power,
                         金币投放=gold_in, 金币回收=gold_out,
                         粮食投放=food_in, 粮食回收=food_out,
                         兵损=dead, 体力溢出=stam_over))
    return pd.DataFrame(rows).set_index("天")


data = {name: simulate_tier(mult) for name, _, mult in TIERS}

# ==================== 体检报告 ====================
print("=" * 78)
print("SLG 经济体检报告   （仿真 360 天）")
print("=" * 78)

report_rows = []
for name, share, mult in TIERS:
    df = data[name]
    gold_rec = df["金币回收"].sum() / df["金币投放"].sum()
    food_rec = df["粮食回收"].sum() / df["粮食投放"].sum()
    gold_days = df["金币"].iloc[-1] / df["金币投放"].iloc[-1]
    report_rows.append(dict(
        分层=name, 人口占比=f"{share:.0%}",
        金币回收率=f"{gold_rec:.1%}", 粮食回收率=f"{food_rec:.1%}",
        存量_日产=f"{gold_days:.1f}",
        末城建=int(df["城建"].iloc[-1]), 深度强化=int(df["深度强化"].iloc[-1]),
        末战力=f"{df['战力'].iloc[-1]:,.0f}"))
print(pd.DataFrame(report_rows).to_string(index=False))

# ---------- 判定 ----------
print("\n--- 判定 ---")
checks = []


def check(name, ok, detail):
    checks.append(ok)
    print(f"  [{'通过' if ok else '不通过'}] {name}：{detail}")


for name, _, _ in TIERS:
    df = data[name]
    rec = df["金币回收"].sum() / df["金币投放"].sum()
    check(f"{name} 金币回收率 ≥ 85%", rec >= 0.85, f"{rec:.1%}")

for name, _, _ in TIERS:
    df = data[name]
    days_held = df["金币"].iloc[-1] / df["金币投放"].iloc[-1]
    check(f"{name} 存量/日产 在 5~20 天", 5 <= days_held <= 20, f"{days_held:.1f} 天")

gap = data["大 R"]["战力"].iloc[-1] / data["免费玩家"]["战力"].iloc[-1]
gap_early = data["大 R"]["战力"].iloc[29] / data["免费玩家"]["战力"].iloc[29]
check("付费战力差距不发散", gap <= gap_early * 1.5,
      f"第30天 {gap_early:.1f}× → 第360天 {gap:.1f}×")

ovf = data["免费玩家"]["体力溢出"].sum() / (P["stamina_regen"] * DAYS)
check("体力溢出率 < 15%", ovf < 0.15, f"{ovf:.1%}")

print(f"\n  ==> {sum(checks)}/{len(checks)} 项通过")

# ==================== 出图 ====================
fig, axes = plt.subplots(2, 3, figsize=(17, 9))
d = np.arange(1, DAYS + 1)

for name, _, _ in TIERS:
    df = data[name]
    axes[0, 0].plot(d, df["战力"], lw=2, label=name)
    axes[0, 1].plot(d, df["金币"] / df["金币投放"], lw=2, label=name)
    axes[0, 2].plot(d, df["金币回收"].cumsum() / df["金币投放"].cumsum() * 100, lw=2, label=name)
    axes[1, 0].plot(d, df["城建"], lw=2, label=name)
    axes[1, 1].plot(d, df["兵"], lw=2, label=name)

axes[0, 0].set_yscale("log"); axes[0, 0].set_title("① 战力（对数轴）\n线平行 = 差距是常数倍")
axes[0, 1].set_title("② 存量 ÷ 日产出"); axes[0, 1].axhspan(5, 20, color="tab:green", alpha=.15)
axes[0, 2].set_title("③ 累计金币回收率 %"); axes[0, 2].axhline(85, color="tab:red", ls=":")
axes[1, 0].set_title("④ 城建等级")
axes[1, 1].set_title("⑤ 兵力（负反馈收敛）")

gaps = [data[n]["战力"] / data["免费玩家"]["战力"] for n, _, _ in TIERS]
for (name, _, _), g in zip(TIERS, gaps):
    axes[1, 2].plot(d, g, lw=2, label=name)
axes[1, 2].set_title("⑥ 相对免费玩家的战力倍数\n应当趋于水平")

for ax in axes.flat:
    ax.set_xlabel("天"); ax.legend(fontsize=8); ax.grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m11_slg_full.png", dpi=140)

pd.concat({n: data[n] for n, _, _ in TIERS}, names=["分层"]).to_csv(
    "../tables/11_slg_sim.csv", encoding="utf-8-sig", float_format="%.1f")
print("\n明细已导出：tables/11_slg_sim.csv")
