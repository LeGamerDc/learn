"""
24 章：从经济流水里揪出异常账号

造一批玩家的日流水（金币获取），其中混入三类异常：
  · 刷金脚本  —— 产出量远超正常上限
  · 工作室    —— 产出不算极端，但**极度规律**（24 小时无休、方差极小）
  · 搬砖小号  —— 产出正常，但几乎不消费，资源持续外流给他人

演示三种检测手段，并说明为什么"只看产出总量"会漏掉最麻烦的一类。
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()
rng = np.random.default_rng(42)

DAYS = 30
N_NORMAL, N_BOT, N_STUDIO, N_MULE = 4000, 25, 40, 60


def gen(n, mean, cv, active_hours_mean, spend_ratio, transfer_ratio):
    """生成 n 个玩家 DAYS 天的：日产出、活跃小时、消费比、转出比"""
    base = rng.lognormal(np.log(mean), 0.5, (n, 1))
    daily = base * rng.lognormal(0, cv, (n, DAYS))
    hours = np.clip(rng.normal(active_hours_mean, 1.5, (n, DAYS)), 0.2, 24)
    spend = np.clip(rng.normal(spend_ratio, 0.12, (n, DAYS)), 0, 1.5)
    trans = np.clip(rng.normal(transfer_ratio, 0.08, (n, DAYS)), 0, 1.0)
    return daily, hours, spend, trans


groups = {
    "正常玩家":   (N_NORMAL, 10_000, 0.45, 3.0, 0.85, 0.02),
    "刷金脚本":   (N_BOT,    95_000, 0.35, 14.0, 0.30, 0.55),
    "工作室":     (N_STUDIO, 26_000, 0.06, 21.0, 0.20, 0.70),   # 产出不极端，但极度规律
    "搬砖小号":   (N_MULE,   12_000, 0.40, 4.0, 0.10, 0.80),   # 产出正常，几乎不消费，全部转出
}

rows = []
for name, (n, mean, cv, hrs, sp, tr) in groups.items():
    daily, hours, spend, trans = gen(n, mean, cv, hrs, sp, tr)
    for i in range(n):
        rows.append(dict(
            群体=name,
            日均产出=daily[i].mean(),
            产出变异系数=daily[i].std() / daily[i].mean(),
            日均活跃小时=hours[i].mean(),
            消费比=spend[i].mean(),
            转出比=trans[i].mean()))
df = pd.DataFrame(rows)
truth = df["群体"] != "正常玩家"

print(f"样本：{len(df):,} 个账号，其中异常 {truth.sum()}（{truth.mean():.1%}）\n")
print(df.groupby("群体", sort=False).mean(numeric_only=True).round(2).to_string())


def evaluate(name, flag):
    tp = (flag & truth).sum()
    fp = (flag & ~truth).sum()
    fn = (~flag & truth).sum()
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    print(f"{name:<34}召回 {rec:>6.1%}  精确率 {prec:>6.1%}"
          f"  漏掉 {fn:>3} 个  误伤 {fp:>4} 个")
    # 按群体看漏了谁
    missed = df.loc[~flag & truth, "群体"].value_counts().to_dict()
    if missed:
        print(f"{'':34}漏掉的构成：{missed}")


print("\n=== 三种检测手段 ===")
p999 = df.loc[~truth, "日均产出"].quantile(0.999)
evaluate("① 只看产出总量（>正常P99.9）", df["日均产出"] > p999)

evaluate("② 加上活跃时长（>12h）",
         (df["日均产出"] > p999) | (df["日均活跃小时"] > 12))

evaluate("③ 再加：低消费 + 高转出",
         (df["日均产出"] > p999)
         | (df["日均活跃小时"] > 12)
         | ((df["消费比"] < 0.35) & (df["转出比"] > 0.4)))

evaluate("④ 再加：产出过于规律（CV<0.15）",
         (df["日均产出"] > p999)
         | (df["日均活跃小时"] > 12)
         | ((df["消费比"] < 0.35) & (df["转出比"] > 0.4))
         | (df["产出变异系数"] < 0.15))

# ==================== 出图 ====================
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
colors = {"正常玩家": "tab:blue", "刷金脚本": "tab:red",
          "工作室": "tab:orange", "搬砖小号": "tab:green"}
for g, c in colors.items():
    sub = df[df["群体"] == g]
    a = 0.25 if g == "正常玩家" else 0.9
    s = 4 if g == "正常玩家" else 14
    axes[0].scatter(sub["日均产出"], sub["日均活跃小时"], s=s, alpha=a, c=c, label=g)
    axes[1].scatter(sub["消费比"], sub["转出比"], s=s, alpha=a, c=c, label=g)
    axes[2].scatter(sub["日均产出"], sub["产出变异系数"], s=s, alpha=a, c=c, label=g)

axes[0].set_xscale("log")
axes[0].set_xlabel("日均产出（对数）"); axes[0].set_ylabel("日均活跃小时")
axes[0].set_title("① 产出 × 时长")
axes[1].set_xlabel("消费比"); axes[1].set_ylabel("转出比")
axes[1].set_title("② 消费 × 转出\n左上角 = 只进不出的搬砖号")
axes[2].set_xscale("log")
axes[2].set_xlabel("日均产出（对数）"); axes[2].set_ylabel("产出变异系数")
axes[2].set_title("③ 产出 × 规律性\n底部 = 机器般稳定的工作室")
for ax in axes:
    ax.legend(fontsize=8); ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig("../figures/m24_anomaly.png", dpi=140)
