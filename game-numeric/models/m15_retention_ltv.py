"""
15 章：留存曲线拟合与 LTV 外推

用同一批早期留存点（D1/D3/D7/D14/D30），三种模型拟合并外推到 365 天：
  · 指数     R(t) = A·e^(-kt)          —— 衰减太快，低估 LTV
  · 幂律     R(t) = A·t^(-b)           —— 业界最常用
  · 幂律+底  R(t) = A·t^(-b) + c       —— 带"铁杆玩家"底盘

结论：**三个模型在拟合窗口内几乎重合（LTV30 极差 1.09 倍），
外推到 365 天却相差 5.5 倍，连"回不回本"的结论都相反。**
这就是为什么"LTV 预测"必须标注口径、外推窗口和假设。
"""
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from cnfont import use_cjk_font

use_cjk_font()

# ---------- 观测到的早期留存（典型中等偏上的手游） ----------
OBS_DAYS = np.array([1, 3, 7, 14, 30], dtype=float)
OBS_RET = np.array([0.42, 0.28, 0.20, 0.145, 0.10])

ARPDAU = 2.0         # 每活跃用户日均收入（元，中重度 SLG 量级）
CPI = 25.0           # 单个安装成本（元）
HORIZON = 365


def f_exp(t, A, k):
    return A * np.exp(-k * t)


def f_pow(t, A, b):
    return A * t ** (-b)


# 注意：底盘 c 不是拟合出来的，是**假设**出来的。
# 只有 30 天的数据，根本无法从数据里识别出"长期底盘"这个参数——
# 它必须由你根据同类产品的经验来假定。这一点是本章的核心。
FLOOR = 0.03        # 假设 3% 的玩家是铁杆，长期不流失


def f_pow_floor(t, A, b):
    return A * t ** (-b) + FLOOR


MODELS = {
    "指数 A·e^(-kt)":      (f_exp,       [0.5, 0.1],        ([0, 0], [2, 5])),
    "幂律 A·t^(-b)":       (f_pow,       [0.45, 0.4],       ([0, 0], [2, 3])),
    f"幂律+底(c={FLOOR})":   (f_pow_floor, [0.4, 0.6],        ([0, 0], [2, 3])),
}

t = np.arange(1, HORIZON + 1, dtype=float)
fits, ltvs = {}, {}

print(f"{'模型':<22}{'拟合参数':<34}{'RMSE':>10}")
print("-" * 68)
for name, (fn, p0, bounds) in MODELS.items():
    popt, _ = curve_fit(fn, OBS_DAYS, OBS_RET, p0=p0, bounds=bounds, maxfev=50000)
    pred = fn(OBS_DAYS, *popt)
    rmse = np.sqrt(np.mean((pred - OBS_RET) ** 2))
    curve = np.clip(fn(t, *popt), 0, 1)
    fits[name] = curve
    ltvs[name] = np.cumsum(curve) * ARPDAU
    ps = ", ".join(f"{v:.4f}" for v in popt)
    print(f"{name:<20}{ps:<34}{rmse:>10.5f}")

print(f"\n{'模型':<22}{'LTV30':>10}{'LTV90':>10}{'LTV180':>10}{'LTV365':>10}")
print("-" * 64)
for name, l in ltvs.items():
    print(f"{name:<20}{l[29]:>10.2f}{l[89]:>10.2f}{l[179]:>10.2f}{l[364]:>10.2f}")

print(f"\n三种模型的 LTV365 极差："
      f"{max(v[364] for v in ltvs.values()) / min(v[364] for v in ltvs.values()):.2f} 倍")
print(f"三种模型的 LTV30  极差："
      f"{max(v[29] for v in ltvs.values()) / min(v[29] for v in ltvs.values()):.2f} 倍")
print("  ↑ 拟合窗口内几乎没差别，外推越远差别越大 —— 这就是外推的危险")

print(f"\n=== 回本分析（CPI = {CPI} 元，含商店 30% 抽成）===")
NET = 0.70
for name, l in ltvs.items():
    net = l * NET
    idx = np.where(net >= CPI)[0]
    day = idx[0] + 1 if len(idx) else None
    print(f"  {name:<20}"
          + (f"第 {day} 天回本" if day else f"365 天内不回本（净 LTV365 = {net[364]:.1f}）"))

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

axes[0].plot(OBS_DAYS, OBS_RET, "ko", ms=8, zorder=5, label="观测点")
for name, c in fits.items():
    axes[0].plot(t, c, lw=2, label=name)
axes[0].set_xscale("log"); axes[0].set_yscale("log")
axes[0].set_title("① 留存曲线（双对数轴）\n幂律在双对数下是直线")
axes[0].set_xlabel("天"); axes[0].set_ylabel("留存率")
axes[0].legend(fontsize=8); axes[0].grid(alpha=.3, which="both")

for name, l in ltvs.items():
    axes[1].plot(t, l, lw=2, label=name)
axes[1].axvline(30, color="gray", ls=":", lw=1.5)
axes[1].text(33, axes[1].get_ylim()[1] * .1, "拟合窗口边界", fontsize=8, color="gray")
axes[1].set_title("② 累计 LTV（毛口径）")
axes[1].set_xlabel("天"); axes[1].set_ylabel("元")
axes[1].legend(fontsize=8); axes[1].grid(alpha=.3)

for name, l in ltvs.items():
    axes[2].plot(t, l * NET, lw=2, label=name)
axes[2].axhline(CPI, color="tab:red", ls="--", lw=2)
axes[2].text(150, CPI * 1.05, f"CPI = {CPI} 元", color="tab:red", fontsize=9)
axes[2].set_title("③ 净 LTV vs 获客成本\n线在红线上方 = 回本")
axes[2].set_xlabel("天"); axes[2].set_ylabel("元")
axes[2].legend(fontsize=8); axes[2].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m15_retention_ltv.png", dpi=140)
