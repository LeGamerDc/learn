# 00 - 建模环境准备

> **本章目标**：十分钟内搭好 Python 建模环境，跑出你的第一张经济曲线图，并从这张图里看出一个真实的数值设计现象。

---

## 1. 为什么制作人也要写代码

你选的是"制作人/主策视角"，可能会觉得建模是执行层的事。不是的，理由有三个：

**第一，人对指数增长的直觉是错的。** 你能一眼看出 `1.35^30` 比 `1.06^30` 大，但你估不出大多少（答案：约 **1200 倍**）。数值设计里到处是这种量级判断，而所有靠"感觉差不多"做出的决策，最后都会在第 60 天变成事故。

**第二，你需要能验伪。** 数值策划给你一份方案，说"180 天不会通胀"。你怎么判断？唯一可靠的办法是把他的假设跑一遍。不会跑，你就只能信；信错了，代价是整个服务器的经济。

**第三，仿真是最便宜的试错。** 改一行代码 3 秒钟，上线改一次数值三个月。第 11 章之后，你提的每个数值假设都应该先跑一遍。

**你不需要成为程序员。** 这门课的所有模型都在 100 行以内，用到的库只有三个：`numpy`（算）、`pandas`（表）、`matplotlib`（画）。你要做的是**读懂模型、改参数、看图**，而不是从零写。

---

## 2. 装环境

### 2.1 Python

macOS 自带的 `/usr/bin/python3` 是 3.9，太老且不能随便装包（系统保护）。用 Homebrew 的：

```bash
# 如果还没装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install python

/opt/homebrew/bin/python3 --version   # 应该是 3.13 或更高
```

### 2.2 建课程的虚拟环境

**一定要用 venv**，不要往系统 Python 里装包——新版 Homebrew Python 会直接拒绝（`externally-managed-environment` 错误），而且课程的包和你别的项目会互相污染。

```bash
cd ~/Project/legamerdc/learn/game-numeric

/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate            # 之后每次开新终端都要执行这一句

pip install --upgrade pip
pip install numpy pandas matplotlib scipy
```

装完验证：

```bash
python -c "import numpy, pandas, matplotlib, scipy; print('ok')"
```

> **每次开新终端记得 `source .venv/bin/activate`。** 提示符前面出现 `(.venv)` 才算生效。忘了这步会报 `ModuleNotFoundError: No module named 'numpy'`——这是本课程最高频的"故障"。

四个包各管什么：

| 包 | 作用 | 你会用到的程度 |
|---|---|---|
| `numpy` | 向量化数值计算。180 天 × 10000 个玩家的模拟，用 numpy 是 0.1 秒，用纯 Python 循环是 30 秒 | 全程 |
| `pandas` | 表格。数值策划的产出是表，pandas 是"能编程的 Excel" | 第 07 章起 |
| `matplotlib` | 画图。**曲线不画出来你是看不懂的** | 全程 |
| `scipy` | 曲线拟合、统计分布、最优化。第 15 章拟合留存曲线、第 13 章算概率分布时用 | 第 13、15 章 |

### 2.3 目录约定

课程的所有代码放在 `models/` 下，按章节编号：

```bash
mkdir -p models figures
```

```
game-numeric/
├── README.md
├── 00-setup.md          ← 你在这
├── 01-....md
├── models/              ← 所有可运行模型
│   ├── cnfont.py        ← 中文字体helper（下一节创建）
│   ├── m00_first_sim.py
│   ├── m03_....py
│   └── ...
├── figures/             ← 模型输出的图（不用手动管，脚本会写进来）
└── .venv/
```

如果这个目录在 git 仓库里，把生成物排除掉：

```bash
cat >> .gitignore <<'EOF'
.venv/
figures/
__pycache__/
EOF
```

---

## 3. 先解决中文乱码

matplotlib 默认字体没有中文，画出来的图标题全是方框 `□□□`。这个问题会烦你一整门课，现在一次性解决。

创建 `models/cnfont.py`：

```python
"""中文字体 helper。所有模型脚本开头 import 它即可。"""
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

# macOS 上按优先级尝试；Windows/Linux 的候选也一并列出
CANDIDATES = [
    "PingFang SC", "Hiragino Sans GB", "Songti SC", "STHeiti",   # macOS
    "Microsoft YaHei", "SimHei",                                  # Windows
    "Noto Sans CJK SC", "WenQuanYi Zen Hei",                      # Linux
]


def use_cjk_font():
    """把 matplotlib 全局字体设成一个可用的中文字体。返回选中的字体名。"""
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in CANDIDATES:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False  # 负号也会变方框，一起修
            return name
    print("⚠️  没找到中文字体，图里的中文会显示为方框。")
    print("   可用字体前 20 个：", sorted(available)[:20])
    return None


if __name__ == "__main__":
    print("使用字体：", use_cjk_font())
```

验证：

```bash
cd models && python cnfont.py
```

应该输出 `使用字体： Hiragino Sans GB`（或其他候选之一）。如果输出了警告，从它打印的可用字体列表里挑一个中文字体，加到 `CANDIDATES` 最前面。

---

## 4. 第一个模型：一个 SLG 玩家的 180 天

现在来跑一个真正有内容的模型。场景是 SLG 最基础的循环：

> 玩家的城市每天产出金币 → 攒够了就升级城建 → 城建等级越高产能越强，但下一级的成本涨得更快 → 于是升级越来越慢。

这就是全景图里 ①投放 → ②存量 → ③回收 → ④战力 的最小闭环。

创建 `models/m00_first_sim.py`：

```python
"""
00 章：SLG 最小经济闭环仿真
一个玩家 180 天，城建升级循环。观察投放、回收、存量三者的关系。
"""
import numpy as np
import matplotlib.pyplot as plt
from cnfont import use_cjk_font

use_cjk_font()

DAYS = 180

# ---------------- 数值参数（这就是"数值设计"本身）----------------
BASE_OUTPUT = 2000.0     # 1 级城建的日产金币
OUTPUT_GROWTH = 1.06     # 每升 1 级，产能 ×1.06
BASE_COST = 5000.0       # 升到 2 级的成本
COST_GROWTH = 1.35       # 每升 1 级，成本 ×1.35
# ------------------------------------------------------------


def daily_output(level: int) -> float:
    """投放：等级越高日产越多"""
    return BASE_OUTPUT * (OUTPUT_GROWTH ** (level - 1))


def upgrade_cost(level: int) -> float:
    """回收：从 level 升到 level+1 的花费"""
    return BASE_COST * (COST_GROWTH ** (level - 1))


def simulate(days=DAYS):
    level = 1
    gold = 0.0
    rows = []
    for day in range(1, days + 1):
        income = daily_output(level)
        gold += income

        spent = 0.0
        # 有钱就升级，可能一天升好几级
        while gold >= upgrade_cost(level):
            cost = upgrade_cost(level)
            gold -= cost
            spent += cost
            level += 1

        rows.append((day, level, gold, income, spent))

    return np.array(rows, dtype=float)


data = simulate()
day, level, gold, income, spent = data.T

# 累计投放 / 累计回收
cum_in = np.cumsum(income)
cum_out = np.cumsum(spent)

fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)

axes[0].plot(day, cum_in, label="累计投放（产出的金币）", lw=2)
axes[0].plot(day, cum_out, label="累计回收（升级花掉的）", lw=2, ls="--")
axes[0].set_ylabel("金币")
axes[0].set_title("① 投放 vs 回收：两条线贴得越紧，经济越健康")
axes[0].legend()
axes[0].grid(alpha=.3)

axes[1].plot(day, gold, color="tab:orange", lw=2)
axes[1].set_ylabel("金币存量")
axes[1].set_title("② 存量：每次归零 = 玩家一有钱就花掉了（回收充分）")
axes[1].grid(alpha=.3)

axes[2].step(day, level, where="post", color="tab:green", lw=2)
axes[2].set_ylabel("城建等级")
axes[2].set_xlabel("天")
axes[2].set_title("③ 成长曲线：投放是指数，成本也是指数，相除得到对数形态")
axes[2].grid(alpha=.3)

plt.tight_layout()
plt.savefig("../figures/m00_first_sim.png", dpi=140)
print(f"第 {DAYS} 天：城建 {int(level[-1])} 级，"
      f"日产 {income[-1]:,.0f}，存量 {gold[-1]:,.0f}")
print(f"累计投放 {cum_in[-1]:,.0f}，累计回收 {cum_out[-1]:,.0f}，"
      f"回收率 {cum_out[-1] / cum_in[-1]:.1%}")
plt.show()
```

跑起来：

```bash
cd models && python m00_first_sim.py
```

---

## 5. 读懂这张图

终端会打印：

```
第 180 天：城建 13 级，日产 4,024，存量 90,481
累计投放 599,684，累计回收 509,203，回收率 84.9%
```

图里有四件事值得看，每件都对应一个真实的数值设计原理。

**第一，等级曲线（第三张图）是"对数形态"——前面陡、后面平。** 前 25 天升了 8 级，后 120 天只升了 4 级。

关键在于：**你没有直接设计这条曲线**。它是投放（`1.06^L`）和成本（`1.35^L`）相除的结果。这是数值设计最重要的直觉之一：

> 你能直接控制的是**产出速率**和**成本斜率**这两个参数；玩家实际感受到的成长节奏，是它们相除的商。

想让后期慢下来，你不需要去改等级曲线本身，只要让成本增速比产能增速快就行。反过来，如果把 `COST_GROWTH` 调到接近 `OUTPUT_GROWTH`，等级会变成**线性甚至加速增长**——这是放置游戏"数字爆炸"的来源（第 04 章细讲）。

**第二，存量曲线（第二张图）是锯齿，每次都掉回接近零。** 这说明回收充分：玩家一有钱就花掉，账面上不会积累出巨额浮财。这是健康经济的标志。第 09 章你会看到，当存量曲线不再归零、开始单调上升时，通胀就开始了。

**第三——这一点最重要——锯齿的振幅在持续变大。** 第 10 天的峰值是几千，第 158 天的峰值是 13 万。牙齿的宽度也在变宽：早期两三天升一级，后期要攒 36 天。

这两个变化其实是同一件事，而且它有非常具体的体验含义：

> **锯齿变宽 = 玩家的"下一次正反馈"越来越远。**

第 5 天的玩家每两天就有一次升级的爽感；第 150 天的玩家要盯着进度条等一个多月。**这就是所有长线游戏在中后期必然遇到的问题**，也是为什么中后期必须靠别的东西填补——新养成线、赛季、PvP、限时活动。第 20 章讲长线节奏规划时，本质上就是在设计"用什么去填这些越来越宽的牙缝"。

顺带说，那个 13 万的存量峰值同时也是一个**付费点信号**：玩家手里攥着 13 万金币、还差 6 万才能升级、并且要再等半个月——这个位置卖一个"资源礼包"的转化率会非常高。付费点的位置不是拍脑袋定的，是从这类曲线上读出来的（第 12、20 章）。

**第四，累计回收（第一张图的虚线）是一条落后于投放的阶梯。** 两条线之间的垂直距离就是当前存量。回收率 84.9% 意味着有 15% 的产出还躺在玩家兜里没花掉。

**这张图是整门课最核心的一张图。** 第 09（通胀）、11（完整仿真）、23（数据看板）章都会出现它的变体——只不过那时候纵轴上是几万个玩家的总和，而不是一个人。判断一个服的经济健不健康，第一件事永远是把这两条线画出来看它们的间距是在收敛还是在张开。

---

## 6. 动手：三个调参实验

**别只是读，把这三个跑一遍。** 每个只需要改一两行。下面给出的数字是实际跑出来的，你应该能复现。

作为对照，原始参数的结果是：**末等级 13，末存量 90,481，回收率 84.9%**。

### 实验 A：给回收加一个天花板

真实游戏里，城建都是有满级的。给 `simulate()` 的 while 条件加一个上限：

```python
MAX_LEVEL = 10
...
        while level < MAX_LEVEL and gold >= upgrade_cost(level):
```

结果：

```
末等级 10   末存量 366,291   回收率 35.1%   （第 72 天满级）
存量：第 60 天 18,273 → 第 120 天 163,553 → 第 180 天 366,291
```

第 72 天满级之后，**回收彻底停止，但投放一天没停**。存量曲线从锯齿变成一条笔直上升的斜线，回收率从 84.9% 崩到 35.1%。

这就是通货膨胀最常见、也最容易被忽略的成因——**不是投放太多，而是回收有天花板而投放没有**。

这个失败模式在真实项目里长这样：玩家把所有建筑升满、所有科技点满之后，每天照样产出几百万资源，但已经没有任何东西可买。此时：

- 你之前定的所有商品价格全部失效（因为资源对玩家不再稀缺）；
- 新出的付费礼包卖资源，没人买；
- 老玩家和新玩家之间出现无法弥合的资源鸿沟。

第 08 章会专门讲怎么设计**没有上限的 sink**（提示：SLG 的答案是"兵损"——士兵会死，所以永远要重造）。

> **顺带做个失控实验**：把 `COST_GROWTH` 改成 `1.04`（低于 `OUTPUT_GROWTH` 的 1.06），脚本会直接抛 `OverflowError: Result too large`。
> 当回收的增速低于投放的增速时，系统在数学上就是发散的——Python 的浮点数都装不下。这不是 bug，是数值设计给你的警报。

### 实验 B：加一个"周末双倍"活动

在 `simulate()` 里 `gold += income` 之前加两行：

```python
        if day % 7 in (6, 0):     # 周六周日双倍
            income *= 2
```

结果：

```
末等级 14（原本 13）   末存量 114,086   回收率 85.9%
```

**投放总量增加了 28.6%（7 天里有 2 天翻倍），换来的成长是 1 级。**

理论值也对得上：在指数成本下，资源乘以 `k` 只等价于领先 `log(k)/log(COST_GROWTH)` 级，
即 `log(1.286)/log(1.35) ≈ 0.84` 级。

这是运营最常问的问题之一——"搞个双倍活动能让玩家爽多少？"——的标准答案：

> **在指数成本曲线下，投放量的提升会被对数压扁。想让玩家明显感到变强，你要动的是成本曲线，不是活动力度。**

这也解释了为什么很多游戏的"双倍活动"玩家反馈平平，而"直升 X 级"的道具却极受欢迎。

### 实验 C：付费玩家 vs 免费玩家

把 `BASE_OUTPUT` 分别改成 3 倍（6000）和 10 倍（20000），和原始跑一遍对比：

| | 末等级 | 领先级数（理论） | 末存量 | 回收率 |
|---|---|---|---|---|
| 免费（×1） | 13 | — | 90,481 | 84.9% |
| 付费（×3） | 17 | +4（3.66） | 558,725 | 75.5% |
| 大 R（×10） | 22 | +9（7.67） | 2,281,741 | 77.3% |

两个结论，都很重要：

**第一，付费 10 倍只领先 9 级，不是 10 倍。** 指数成本曲线把付费差距从"倍数"压缩成了"常数差"。

> 这是 SLG 数值设计里最重要的一条杠杆：**指数成本曲线天然压缩付费差距**。

第 19 章讲服务器生态时，这条是"为什么大 R 砸钱也没法把服务器打崩"的数学基础。反过来说，如果你把成本曲线做得太平（接近线性），付费差距就会真的变成倍数差——服务器会在两周内变成大 R 的单机游戏。

**第二，也是新手最容易漏的：大 R 的资源溢出比免费玩家严重得多。** 大 R 兜里躺着 228 万金币花不出去，回收率反而更低。

这意味着：**为免费玩家设计的成本曲线，对大 R 是失效的。** 大 R 的钱没地方花，就会去买别的（黑市、代练、跨服交易），或者干脆流失——"我充了钱却没什么可买的"是高付费用户流失的头号原因之一。第 12 章讲付费深度、第 08 章讲高阶 sink 时都会回到这个问题。

---

## 7. Excel 在哪里用

你选了 Python，但 Excel 在真实项目里不可替代，原因是**沟通**：数值方案要给主美、程序、运营、发行看，他们不会跑你的脚本。

实际的分工是这样：

| 场景 | 用什么 | 为什么 |
|---|---|---|
| 探索"这条曲线该长什么样" | Python | 改参数 + 出图的循环快 10 倍 |
| 多玩家、多天数的随机仿真 | Python | Excel 跑蒙特卡洛会卡死 |
| 最终的数值配置表（要交付给程序的） | **Excel / CSV** | 程序侧导表工具链都是吃表格的 |
| 给团队评审的方案 | **Excel + 图** | 别人要能自己点开改一个格子看结果 |
| 线上数据的临时分析 | 都行 | 看数据量 |

本课程的做法：**Python 出结论，pandas 导出 CSV/Excel 交付。** 第 07 章做日产出预算表时会演示这个流程。

---

## 8. 检查清单

进入第 01 章之前，确认：

- [ ] `source .venv/bin/activate` 之后 `python -c "import numpy, pandas, matplotlib, scipy; print('ok')"` 输出 `ok`
- [ ] `python models/cnfont.py` 打印出了一个中文字体名，没有警告
- [ ] `python models/m00_first_sim.py` 跑通，弹出了三张子图，中文标题正常显示
- [ ] `figures/m00_first_sim.png` 生成了
- [ ] 三个调参实验都跑过，你能说出实验 A 的图和原图**具体哪里不一样**
- [ ] 你能用一句话回答：为什么等级曲线是对数形态，而你并没有设计过它

---

## 9. 常见坑

| 现象 | 原因 | 解决 |
|---|---|---|
| `ModuleNotFoundError: No module named 'numpy'` | 忘了激活 venv | `source .venv/bin/activate`，看提示符有没有 `(.venv)` |
| `error: externally-managed-environment` | 往系统 Python 装包 | 必须用 venv，见 2.2 |
| 图里中文是方框 `□□□` | 字体没设置 | 确认脚本开头调了 `use_cjk_font()`；跑 `python cnfont.py` 看有没有警告 |
| 负号显示成方框 | 中文字体缺 minus 字形 | `cnfont.py` 里的 `axes.unicode_minus = False` 已处理，确认你用的是这个版本 |
| `plt.show()` 没弹窗 / 卡住 | 后端问题或在 SSH 里跑 | 只看图片文件即可，把 `plt.show()` 注释掉，看 `figures/` 下的 png |
| `FileNotFoundError: '../figures/...'` | 没在 `models/` 目录下跑 | `cd models` 之后再 `python m00_xxx.py` |
| 模型跑出来数字大到 `inf` | 指数增长溢出 | 这本身就是一个数值设计信号——第 04 章会讲怎么用对数坐标处理，以及为什么放置游戏必须自己实现大数 |

---

**下一章**：[01 - 数值设计到底在设计什么](./01-what-is-numeric-design.md)
