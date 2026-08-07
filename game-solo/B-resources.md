# 附录 B - 资料地图与模型索引

---

## 1. 唯一的权威口径：官方文档

**IAA 小游戏的所有【实证】数据都只该从这里来。** 二手文章的数字过期得很快。

| 资料 | 说的什么 | 更新频率 |
|---|---|---|
| **[微信开放文档 · 商业化](https://developers.weixin.qq.com/minigame/introduction/commercialization/)** | 广告组件类型、接入方式、政策总览 | 随时 |
| **[流量主广告变现分成政策](https://developers.weixin.qq.com/community/minigame/doc/00088c1ef7c21079135f6e8a159408)** | **分成比例**（本课取 50%，创意小游戏 200 万/日内 70%） | 变动会公告 |
| **[广告变现激励政策](https://developers.weixin.qq.com/minigame/introduction/commercialization/guide/ad-monetization.html)** | **注册激励**（本课取首 30 天流水 40% 返广告金） | **每年调整** |
| **[虚拟支付激励政策](https://developers.weixin.qq.com/minigame/introduction/commercialization/guide/virtual-payment.html)** | IAP 侧的分成与激励（做混合变现时看） | 每年调整 |
| **[激励视频广告 API](https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/ad/rewarded-video-ad.html)** | 接入细节、频次约束 | 随时 |
| **[腾讯广告 · 流量主成长营](https://training.tencentads.com/)** | 官方的买量与变现培训材料 | 不定期 |

> ⚠️ **本课写于 2026 年 8 月。** 所有标【实证】的数字用之前请回到上面这些页面核对当期口径。
> **公式和取舍结构不会过期，数字会。**

---

## 2. 会随时间显著变化的三样

**这三个数每季度都在动，本课只给量级参考，标记【行业口径】：**

| | 本课取值 | 怎么核实 |
|---|---|---|
| **eCPM** | 60 元/千次（激励视频） | 你自己的后台。上线前只能问同行或看公开分享 |
| **IPU** | 6 次/天（头部 11~12） | 同上 |
| **买量 CPA** | 未固定，用回本线反推 | 直接问渠道报价 |

> **⇒ 这三个数不要抄课程，要抄你自己的后台。**
> 课程给的是"怎么用它们算"，不是"它们是多少"。

---

## 3. 书与公开分享

### 单人玩法设计（本课阶段三、四的来源）

| 资料 | 说明 |
|---|---|
| **Tynan Sylvester《Designing Games: A Guide to Engineering Experiences》**（O'Reilly, 2013） | RimWorld 作者。把游戏设计当工程学科讲。**单人玩法设计的最佳单本教材** |
| **Schreiber & Romero《Game Balance》**（CRC, 2021） | 传递性/非传递性平衡、成本曲线、收益矩阵。第 07、08 章的数学基础 |
| **Short & Adams《Procedural Generation in Game Design》**（CRC, 2017） | 程序化生成的系统性教材。第 12 章 §5 |
| **GDC 2019《Slay the Spire: Metrics Driven Design and Balance》** | Mega Crit 的数据驱动平衡实践。**第 01、07 章的"占优策略反转"直接来自它** |

### 经济与放置数学（本课阶段二、四的来源）

| 资料 | 说明 |
|---|---|
| **Kongregate《The Math of Idle Games》**（三部分） | 指数成本曲线、prestige 层。**第 11 章的主要来源** |
| **Factorio Friday Facts**（官方开发博客） | 比率数学与"加成必须递减"的活教材。**第 10 章的 beacon 案例来自 FFF#409** |
| **Lehdonvirta & Castronova《Virtual Economies》**（MIT, 2014） | 虚拟经济的学术框架。想深入投放/回收看它 |
| **Machinations.io** | 资源流图的可视化工具与文档。`econ.py` 的概念来源 |

### F2P 商业数值（本课直接引用 game-numeric）

见 [game-numeric 附录 B](../game-numeric/B-glossary.md) 与其 README 的资料表。

---

## 4. 可靠性标记约定

本课每个数字都标了来源：

| 标记 | 含义 | 例子 |
|---|---|---|
| **【实证】** | 官方文档或可公开验证 | 分成 50%、注册激励 40% |
| **【行业口径】** | 业内公开分享的量级参考，**会随时间显著变化** | eCPM 60 元、IPU 6 |
| **【推导】** | 我从公开信息反推的，**可能有误** | 第 06 章的"难度 → 次留"钟形曲线 |
| 不标 | 教科书数学，自身成立 | AM-GM、样本量公式、几何分布 |

> **全课最重要的一条【推导】是第 06 章那条钟形曲线。**
> 它决定了所有 LTV 的具体数值。**上线后请用真实 AB 数据替换它**（[第 06 章 §7](./06-difficulty-as-lever.md)）。

---

## 5. 模型索引

**15 个模型，全部可独立运行。** 环境见 [00 章](./00-setup.md)。

### 共享模块

| 文件 | 作用 | 被谁用 |
|---|---|---|
| `cnfont.py` | matplotlib 中文字体 | 全部 |
| `econ.py` | 通用资源流引擎（从 game-numeric 复制） | 03 |
| `run_model.py` | **单局模型本体**：指数赛跑 + `dmg_exp` | 00、02、06、07、12、13 |

### 按章

| 模型 | 章 | 核心产出 |
|---|---|---|
| `s00_first_run.py` | 00 | 指数赛跑；`dmg_exp` 决定品类；增长率差 1.1% → 通关率 6%→88% |
| `s02_session_pacing.py` | 02 | 无效时间 24.3%；**IAA 口径下三种解法排序被洗牌**（B 是 0.67×） |
| `s03_three_economies.py` | 03 | 局内"买得起比例"；**广告注入 ×2 → 内容寿命 79→40 天**；回收率 99.8%→8.8% |
| `s04_ad_revenue.py` | 04 | LTV 拆解；**四个杠杆全是线性的**；回本线；广告金两条账 |
| `s05_ad_placement.py` | 05 | **IPU 饱和 vs 注入线性**（1.7 倍 vs 10 倍）；点位蚕食 64%；触达率 |
| `s06_difficulty_lever.py` | 06 | **(难度 × 倍率) 的 LTV 曲面**；最优区间是平的；内容寿命是不是约束的诊断 |
| `s07_build_diversity.py` | 07 | **三个指标里两个失灵**；边际胜率离群度；超模触发率 |
| `s08_synergy.py` | 08 | **纯乘法叠加的决策价值精确等于 1**；凹性 → 决策价值 |
| `s09_randomness.py` | 09 | 方差归因；保底改尾巴不改均值；**重抽要限次的真正理由** |
| `s10_idle_production.py` | 10 | 比率计算；瓶颈转移；**加成不递减 → 空间不再稀缺** |
| `s11_offline.py` | 11 | **离线上限 ≈ 睡眠时长**（两个约束夹出来的）；prestige 最优周期 |
| `s12_meta_content.py` | 12 | **地板型元进程的悬崖**；内容消耗速度 → 月产能 |
| `s13_auto_playtest.py` | 13 | **可直接抄走的平衡测试套件**；三个已知病例 + 元测试 |
| `s14_metrics.py` | 14 | 广告漏斗；**AB 样本量：留存类实验做不起** |
| `s15_full_spec.py` | 15 | **6 个决策 → 完整方案 + 自洽性检查**；全课的集成测试 |

### 跑法

```bash
cd ~/Project/legamerdc/learn/game-solo/models
source ../../game-numeric/.venv/bin/activate

python s00_first_run.py           # 单个跑
for f in s*.py; do python "$f"; done   # 全跑（几分钟）

python s13_auto_playtest.py --quick    # 平衡体检（2 秒，退出码 0/1）
```

---

## 6. 全课的"反转"与"翻车"索引

**本课有几处是模型推翻了我的假设，它们比正确的结论更值得看：**

| 在哪 | 我原本以为 | 模型说 |
|---|---|---|
| [03 §2.1](./03-three-economies.md) | 定价越高，金币越花不掉 | **玩家会攒着，"结算剩余率"不是好指标** |
| [07 §3](./07-build-diversity.md) | 基尼系数能抓 dominant | **三个指标里两个失灵**，只有边际胜率离群度有效 |
| [08 §3](./08-synergy-scaling.md) | 乘法叠加更爽 | **它让分配决策的价值精确等于 1**，构筑彻底失效 |
| [09 §4.1](./09-randomness.md) | 重抽限次是因为边际递减 | **递减很温和，真正的理由是它会破坏别的系统** |
| [12 §2](./12-meta-and-content.md) | 追赶型元进程更好 | **只改速度不改上限，两种结构会收敛** |
| [13 §4](./13-auto-playtest.md) | 边际胜率能抓超模 | **观察性指标有选择偏差，越严重越抓不到** |
| [06 §4 四](./06-difficulty-as-lever.md) | 留存越好，最优倍率越低 | **完全没漂移**——内容寿命在这套参数下根本不是约束 |
| [15 §5](./15-end-to-end-lab.md) | 单章自洽就够了 | **两个单位错误互相掩盖，端到端串联才暴露** |

> **这一列是本课的方法论：先跑模型，再写结论。当模型和预期冲突时，改结论，不改模型。**

---

## 7. 全课判据速查

| 指标 | 健康值 | 来自 |
|---|---|---|
| 一次会话装下的局数 | **≥ 3** | [02](./02-session-pacing.md) |
| 局内"买得起比例" | 40%~70% | [03](./03-three-economies.md) |
| 成本/产出增速比 | 1.1~1.3 | [03](./03-three-economies.md)、game-numeric 04 |
| 内容寿命 | **≥ 你的留存衰减期** | [03](./03-three-economies.md)、[06](./06-difficulty-as-lever.md) |
| 广告倍率 | 2.0×~4.0× | [05](./05-ad-placement.md)、[06](./06-difficulty-as-lever.md) |
| 单点位收益 | **≥ 2 分钟等效产出** | [05](./05-ad-placement.md) |
| IPU（每天） | 4~9（头部 11~12） | [04](./04-ad-revenue-math.md) |
| 目标通关率 | **28%~33%**（放宽 20%~45%） | [06](./06-difficulty-as-lever.md) |
| 单件道具边际胜率离群度 | **< 3σ** | [07](./07-build-diversity.md) |
| 禁用单件导致的通关率跌幅 | **< 6%** | [13](./13-auto-playtest.md) |
| 超模状态触发率 | **5%~15%** | [07](./07-build-diversity.md) |
| 废卡（选取率 <5%）数量 | ≤ 2 | [07](./07-build-diversity.md) |
| 同维叠加的决策价值 | **≥ 1.5×** | [08](./08-synergy-scaling.md) |
| 爆发感（P99/中位） | 1.9~4.5 | [08](./08-synergy-scaling.md) |
| 每局重抽上限 | **2~3 次** | [09](./09-randomness.md) |
| 离线上限 | **≈ 睡眠时长（6~10h）** | [11](./11-offline-earnings.md) |
| 离线翻倍每日次数 | 1~2 次 | [11](./11-offline-earnings.md) |
| 元进程健康带覆盖率 | 尽可能高（本课最优 72%） | [12](./12-meta-and-content.md) |

**红线（没有折中余地的）：**

> - **不看广告必须能正常通关**，只是慢一些（[第 05 章](./05-ad-placement.md)）
> - **失败必须可归因**，否则会被读成"游戏想坑我看广告"（[第 02](./02-session-pacing.md)、[09 章](./09-randomness.md)）
> - **凡是"率"，埋点要同时有分子和分母**（[第 14 章](./14-metrics.md)）

---

**返回**：[README](./README.md) ｜ [A - 三种商业模式对照表](./A-contrast.md)
