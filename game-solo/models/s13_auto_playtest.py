"""
13 章：自动化平衡测试

把第 03~12 章的判据全部变成**可执行的断言**，接进 CI。

设计原则（第 07、09 章反复出现的那条教训）：
    **指标本身也需要测试。**
所以本套件不只跑基线，还跑三个**已知有病的版本**，
验证"该报警的检查确实报警了、不该报警的没有误报"。

用法：
    python s13_auto_playtest.py            # 跑全套，退出码 0/1
    python s13_auto_playtest.py --quick    # 冒烟测试（CI 每次提交跑）
"""
import sys
from collections import defaultdict

import numpy as np
import run_model as R

QUICK = "--quick" in sys.argv
N = 400 if QUICK else 2000
rng = np.random.default_rng(31)

# ============================================================
# 被测的"游戏配置" —— 真实项目里这里是你的配表
# ============================================================
BASE = dict(
    power_gain=1.0200,      # 难度（第 06 章）
    n_items=24, n_tags=4, picks=8, offer=3,
    item_lo=0.85, item_hi=1.15,      # 道具价值区间（第 07 章）
    dominant=None,                    # (下标, 价值) —— 注入超模用
    syn_at={3: 0.4, 6: 2.6},          # 协同门槛与回报（第 07 章）
    dim_mode="软上限",                 # 同维叠加规则（第 08 章）
    ad_inject=1.0,                    # 局外广告注入倍数（第 03 章）
    reroll=2,                         # 每局重抽次数（第 09 章）
)

# 三个**已知有病**的版本，用来验证检查项真的会报警
BROKEN = {
    "病例A：单道具超模":   dict(BASE, dominant=(5, 1.85)),
    "病例B：同维乘法":     dict(BASE, dim_mode="同维乘法"),
    "病例C：广告注入过量": dict(BASE, ad_inject=3.0, reroll=8),
}

# ============================================================
# 目标区间 —— 这些数字是你的产品决策，来自第 03~12 章
# ============================================================
TARGET = dict(
    winrate=(0.20, 0.45),        # 第 06 章健康带
    ban_drop=0.06,               # 第 07 章：禁用单件道具导致的通关率跌幅上限
    dead_item_rate=0.05,         # 第 07 章：选取率低于此即废卡
    max_dead_items=2,
    decision_value=1.5,          # 第 08 章：同维叠加的决策价值下限
    peak_ratio=(1.9, 4.5),       # 第 08 章：P99/中位（爆发感）
    synergy_trigger=(0.05, 0.20),  # 第 07/09 章：稀有协同的触发率
    content_life_days=35,        # 第 03 章：内容寿命下限
    ipu=(4.0, 9.0),              # 第 04/05 章：IPU 目标区间
)

# ============================================================
# 被测系统的最小实现（真实项目里换成你自己的战斗/经济代码）
# ============================================================
_wr_cache = {}


def winrate(pg):
    k = round(float(np.clip(pg, 1.008, 1.034)), 4)
    if k not in _wr_cache:
        p = dict(R.P); p["power_gain"] = k
        _wr_cache[k] = R.batch(300 if QUICK else 800, p)[0]
    return _wr_cache[k]


def dim_mult(k, mode, step=0.25):
    if mode == "同维乘法":
        return (1 + step) ** k
    if mode == "同维加法":
        return 1 + step * k
    if mode == "软上限":
        return 1 + step * 6 * k / (k + 3.0)
    raise ValueError(mode)


def simulate(cfg, n=N, seed=0, player="mixed"):
    """
    跑 n 局，返回体检需要的所有原始数据。

    player: "mixed"  —— 混合人群（70% 兼顾协同 / 15% 只看数值 / 15% 噪声），
                        默认，用来测所有"平均体验"类指标
            "greedy" —— 纯数值贪心的探针人群（留作动手任务用）

    cfg["banned"] —— 把某件道具从池子里拿掉，ban_scan 用它做干预实验
    """
    r = np.random.default_rng(seed)
    ni, nt = cfg["n_items"], cfg["n_tags"]
    val = np.random.default_rng(3).uniform(cfg["item_lo"], cfg["item_hi"], ni)
    if cfg["dominant"]:
        val[cfg["dominant"][0]] = cfg["dominant"][1]
    tag = np.arange(ni) % nt

    offered, taken = np.zeros(ni), np.zeros(ni)
    n_with, win_with = np.zeros(ni), np.zeros(ni)
    scores, wins, five = [], 0, 0
    # 重抽的触发线：只有当**整组三选一都很差**时才重抽。
    # ⚠️ 第一版写成"选中的低于中位数就重抽"，结果池子下半部分全变成废卡 ——
    #    那本身就是一条真实的设计教训（见本文件末尾的读法）。
    bar = np.percentile(val, 30)
    banned = cfg.get("banned")
    for i in range(n):
        held = []
        n_pick = int(np.clip(r.poisson(cfg["picks"]), 4, 14))   # 件数有运气（第 09 章）
        for _ in range(n_pick):
            pool = [x for x in range(ni) if x not in held and x != banned]
            off = r.choice(pool, cfg["offer"], replace=False)
            offered[off] += 1
            # 重抽：整组都很差时才用（第 09 章：重抽要限次，且不能删掉随机性）
            for _ in range(cfg["reroll"]):
                if val[off].max() >= bar:
                    break
                off = r.choice(pool, cfg["offer"], replace=False)
                offered[off] += 1
            # 玩家模型：混合人群 or 纯数值贪心探针
            u = 1.0 if player == "greedy" else r.random()
            if u < 0.15:
                c = int(r.choice(off))
            elif u < 0.30 or player == "greedy":
                c = int(off[np.argmax(val[off])])
            else:
                cnt = (np.bincount(tag[held], minlength=nt) if held
                       else np.zeros(nt))
                c = int(off[np.argmax(cnt[tag[off]] * 0.20 + val[off])])
            taken[c] += 1
            held.append(c)
        h = np.array(held)
        cnt = np.bincount(tag[h], minlength=nt)
        bonus = sum(b for need, b in cfg["syn_at"].items() if cnt.max() >= need)
        sc = val[h].sum() + bonus
        five += cnt.max() >= 6
        scores.append(sc)
        pg = cfg["power_gain"] + (sc - 9.0) * 0.0025
        won = R.one_run(seed=i * 7919 + 1, p=dict(R.P, power_gain=float(
            np.clip(pg, 1.008, 1.034))))["died"] is None
        wins += won
        n_with[h] += 1
        win_with[h] += won

    lift = (win_with / np.maximum(n_with, 1)
            - (wins - win_with) / np.maximum(n - n_with, 1))
    return dict(win=wins / n, score=np.array(scores), five=five / n,
                rate=taken / np.maximum(offered, 1), lift=lift, cfg=cfg)


def ban_scan(cfg, base_win, top_k=6, n=None):
    """
    **干预性**的 dominant 检查：把某件道具从池子里拿掉，重跑，看通关率掉多少。

    为什么不用第 07 章那个"边际胜率"（观察性指标）？
      观察性指标有**选择偏差**：一件道具如果强到几乎每局必选，
      "不含它的构筑"就没有样本了 —— **没有对照组，边际胜率根本估不出来。**
      （这不是理论担忧：本套件第一版就在病例 A 上漏报了，原因正是这个。）

    禁用重跑是**干预**，不受选择偏差影响。代价是要多跑 top_k 次仿真。
    """
    n = n or (150 if QUICK else 500)
    cand = np.argsort(-simulate(cfg, n=n, seed=5)["rate"])[:top_k]
    drops = []
    for it in cand:
        c2 = dict(cfg)
        c2["banned"] = int(it)
        drops.append(base_win - simulate(c2, n=n, seed=9)["win"])
    return np.array(drops), cand


def content_life(inject):
    """第 03 章的解析解"""
    A = 5.0 * 100.0 * (1 + inject) / 300.0
    r = 1.030 / 1.035
    return (1 - r ** (-100)) / (A * np.log(r))


def estimate_ipu(cfg):
    """粗估 IPU：点位数 × 渗透率，重抽次数直接进 IPU（第 05 章的简化版）"""
    return 4.2 + 0.55 * cfg["reroll"] + 0.4 * (cfg["ad_inject"] - 1.0)


# ============================================================
# 检查项 —— 每一条都对应一章的判据
# ============================================================
def outlier_z(x):
    med = np.median(x)
    mad = np.median(np.abs(x - med)) or 1e-9
    return (x.max() - med) / (1.4826 * mad)


def checks(d, bans=None):
    cfg = d["cfg"]
    lo, hi = TARGET["winrate"]
    med_w = winrate(cfg["power_gain"] + (np.median(d["score"]) - 9.0) * 0.0025)
    p99 = np.percentile(d["score"], 99) / np.median(d["score"])
    dv = (dim_mult(2, cfg["dim_mode"]) ** 4) / dim_mult(8, cfg["dim_mode"])
    dead = int((d["rate"] < TARGET["dead_item_rate"]).sum())
    life = content_life(cfg["ad_inject"])
    ipu = estimate_ipu(cfg)
    sl, sh = TARGET["synergy_trigger"]
    pl, ph = TARGET["peak_ratio"]
    il, ih = TARGET["ipu"]
    return [
        ("06 中位通关率在健康带", lo <= med_w <= hi, f"{med_w:.1%}",
         f"{lo:.0%}~{hi:.0%}"),
        # ⚠️ 这一项用**干预**（禁用重跑）而不是观察，理由见 ban_scan 的注释
        ("07 无 dominant 道具", bans.max() < TARGET["ban_drop"],
         f"{bans.max():.1%}", f"<{TARGET['ban_drop']:.0%}"),
        ("07 废卡不超标", dead <= TARGET["max_dead_items"], f"{dead} 张",
         f"≤{TARGET['max_dead_items']}"),
        ("07 协同触发率合理", sl <= d["five"] <= sh, f"{d['five']:.1%}",
         f"{sl:.0%}~{sh:.0%}"),
        ("08 分配决策有价值", dv >= TARGET["decision_value"], f"{dv:.2f}×",
         f"≥{TARGET['decision_value']:.1f}×"),
        ("08 爆发感在区间内", pl <= p99 <= ph, f"{p99:.2f}", f"{pl}~{ph}"),
        ("03 内容寿命达标", life >= TARGET["content_life_days"], f"{life:.0f} 天",
         f"≥{TARGET['content_life_days']} 天"),
        ("05 IPU 在目标区间", il <= ipu <= ih, f"{ipu:.1f}", f"{il}~{ih}"),
    ]


def report(name, d, bans):
    rows = checks(d, bans)
    bad = [r for r in rows if not r[1]]
    print(f"\n{'=' * 74}\n{name}   →   "
          f"{'✅ 全部通过' if not bad else f'❌ {len(bad)} 项未通过'}\n{'=' * 74}")
    print(f"{'检查项':<26}{'结果':>12}{'实测':>14}{'目标':>16}")
    print("-" * 74)
    for label, ok, got, want in rows:
        print(f"{label:<24}{'✅ 通过' if ok else '❌ 未通过':>12}{got:>14}{want:>16}")
    return [r[0] for r in bad]


# ============================================================
# 跑：基线 + 三个已知病例
# ============================================================
print(f"数值平衡体检套件{'（冒烟模式）' if QUICK else ''}   每个版本跑 {N} 局")

fails = {}
for name, cfg in [("基线", BASE)] + list(BROKEN.items()):
    d = simulate(cfg)
    bans, _ = ban_scan(cfg, d["win"])
    fails[name] = report("基线版本" if name == "基线" else name, d, bans)

# ============================================================
# 元测试：验证"该报警的报警了、不该报警的没误报"
# ============================================================
EXPECT = {
    "基线": set(),
    "病例A：单道具超模": {"07 无 dominant 道具"},
    "病例B：同维乘法": {"08 分配决策有价值"},
    "病例C：广告注入过量": {"03 内容寿命达标", "05 IPU 在目标区间"},
}

print(f"\n{'=' * 74}\n元测试：检查项本身可靠吗\n{'=' * 74}")
print(f"{'版本':<24}{'预期报警':<28}{'实际报警':<28}{'':>4}")
print("-" * 88)
meta_ok = True
for name, want in EXPECT.items():
    got = set(fails[name])
    ok = want <= got                       # 预期的必须全部报出来（允许额外报警）
    meta_ok &= ok
    extra = got - want
    print(f"{name:<22}{('（无）' if not want else '、'.join(sorted(want))):<26}"
          f"{('（无）' if not got else '、'.join(sorted(got))):<26}"
          f"{'✅' if ok else '❌ 漏报':>4}")
    if extra and name != "基线":
        print(f"{'':<22}  （额外报警：{'、'.join(sorted(extra))}——不算失败，但值得看一眼）")

print(f"""
读法 —— **这一段才是本章的重点**
--------------------------------
上面那张表在问一个元问题：**"我的检查项，真的能抓到问题吗？"**

第 07 章证明过：选取率基尼和最高选取率这两个"看起来很合理"的指标，
**都抓不到单道具超模**。如果没有病例 A 这样的固定用例，
你会一直以为自己有监控 —— **直到线上出事。**

⇒ **⭐ 平衡测试套件里必须常驻"已知坏版本"。**
   每加一个检查项，就配一个能触发它的病例。
   **这和后端的单元测试是同一套工程纪律**：
   没有失败用例的断言，等于没有断言。

⚠️ 注意"额外报警"那一行。病例 A 同时触发了通关率检查 ——
   这不是误报，是**真实的溢出效应**（第 09 章那条教训：
   一个改动会溢出到别的系统）。**额外报警恰恰是套件在帮你发现关联。**

════════════════════════════════════════════════════════════
本套件在开发过程中被自己的元测试抓到过两次，都值得记下来
════════════════════════════════════════════════════════════

**第一次：观察性指标有选择偏差。**

  第 07 章用的"边际胜率"（含它的构筑通关率 − 不含它的）是**观察性**指标。
  它在病例 A 上**漏报**了 —— 因为那件道具强到几乎每局必选，
  **"不含它的构筑"根本没有样本，对照组是空的。**

  ⇒ 换成**干预性**指标：把道具从池子里拿掉、重跑，看通关率掉多少。
    干预不受选择偏差影响。**代价是要多跑 top_k 次仿真 —— 值得。**

  ⇒ 这条规律超出游戏数值：**任何"越强的东西样本越有偏"的场景，
    观察性指标都会低估它。** 后端做 A/B 分析时同一个坑。

**第二次：被测系统自己写错了，而检查项忠实地报了出来。**

  第一版的重抽逻辑写成"选中的道具低于中位数就重抽"，
  结果**池子的下半部分永远不会被选中** —— 废卡检查立刻报了 12 张。

  当时我的第一反应是"检查项太严了，放宽阈值吧"。**那是错的。**
  正确的做法是去看被测系统 —— **重抽应该只在"整组都很差"时触发**，
  否则它会把随机性和半个道具池一起删掉（第 09 章 §4.1 的另一种形态）。

  ⇒ **⭐ 检查项报警时，默认假设是"系统错了"，不是"阈值太严了"。**
    改阈值是最后手段，而且要写清理由。
""")

# ============================================================
# 接进 CI
# ============================================================
print(f"""{'=' * 74}
接进 CI
{'=' * 74}

**分两层跑**（和后端测试的金字塔一样）：

  ┌─ 每次提交：冒烟测试   python s13_auto_playtest.py --quick
  │    局数少、只跑基线、30 秒内出结果
  │    抓的是"改配表改出了明显的低级错误"
  │
  └─ 每天/每次发版：全量   python s13_auto_playtest.py
       跑满局数 + 所有病例 + 元测试
       抓的是"数值漂移"和"检查项失效"

**退出码约定**：全部通过 → 0；有未通过项或元测试漏报 → 1。
CI 直接用退出码判断即可。

**GitHub Actions 最小配置：**

    - name: 数值平衡体检
      run: python models/s13_auto_playtest.py --quick

**三条实践建议：**

  1. **把 TARGET 那个字典单独放一个文件，纳入 code review。**
     改目标区间是产品决策，不该混在配表改动里悄悄过去。

  2. **每次调数值，先看哪些检查项的"实测值"动了** ——
     它比 diff 更能告诉你这次改动的影响面。

  3. **失败时打印实测值，不要只打印 pass/fail。**
     上面每张表都有"实测/目标"两列，就是为了让你一眼看出"差多远"。

⚠️ **最后一条，也是最重要的：**

    **这套东西能告诉你"哪个 build 胜率异常"，
      但告诉不了你"这局好不好玩"。**

    自动化测试是**下限保障**，不是设计工具。
    它防的是"上线后发现某个道具无敌"，
    防不了"数值都对，但玩起来很闷"。**后者只能靠玩。**
""")

sys.exit(0 if (not fails["基线"] and meta_ok) else 1)
