# N9｜物质帮助与流失定向的证据笔记（补偿心理学、留存定向、损失缓冲先例）

检索日期：2026-09-22。本笔记由主研究者自行检索，补充 N4（心理支撑）与 N5（业界机制）未覆盖的"补偿怎么给才不适得其反"与"该补偿谁"两个问题。阅读深度均为摘要/出版社页面/二手可靠转述，未逐页读全文。

## 1. 该补偿谁：高风险 ≠ 高可挽回

| 来源 | 方法 | 发现 | SLG 转译 |
|---|---|---|---|
| Ascarza (2018) *Retention Futility: Targeting High-Risk Customers Might Be Ineffective*, JMR 55(1). [SAGE](https://journals.sagepub.com/doi/10.1509/jmr.16.0163) · [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759170) | 两个现场实验 + 机器学习（uplift） | 流失风险最高的客户不一定是挽留活动的最佳对象；按"对干预的敏感度"定向显著优于按"流失概率"定向 | "补偿容易流失的玩家"应改成"补偿被补偿后会留下的玩家"。需要随机对照来估计每类玩家的干预增量，而不是只建流失预测模型 |
| Ascarza, Iyengar & Schleicher (2016) *The Perils of Proactive Churn Prevention Using Plan Recommendations*, JMR 53(1). [SAGE](https://journals.sagepub.com/doi/abs/10.1509/jmr.13.0483) · [HBS PDF](https://www.hbs.edu/ris/download.aspx?name=ascarza_iyengar_schleicher_jmr_16.pdf) | 电信现场实验 | 主动推荐更省钱套餐反而提高流失：对照组 3 个月流失 6%，处理组 10%。机制：降低了转换惰性、让过去的使用模式变得显眼 | 主动"提醒"玩家其处境（如推送"你最近损失很大，这是补偿"）可能把本来没想走的人推向盘算离开；干预不能让玩家重新审视沉没成本与替代选项 |
| Lemmens & Gupta (2020) *Managing Churn to Maximize Profits*, Marketing Science 39(5). [INFORMS](https://pubsonline.informs.org/doi/10.1287/mksc.2020.1229) | 基于利润的 uplift 建模 | 按"干预带来的利润增量"定向优于按流失概率或按响应率定向 | 补偿预算应按"增量留存 × 玩家未来价值 − 补偿成本"分配，而非按风险分排序 |

结论：定向补偿要三件套同时成立——风险预测（谁可能走）、增量估计（补偿对谁有效）、价值/成本（值不值）。只有第一件套的"流失预警→发礼包"是业界最常见也最容易失效的做法。

## 2. 补偿多少：递减、匹配、及时

| 来源 | 方法 | 发现 | SLG 转译 |
|---|---|---|---|
| Gelbrich & Roschk (2011) *A Meta-Analysis of Organizational Complaint Handling and Customer Responses*, JSR 14(1). [SAGE](https://journals.sagepub.com/doi/10.1177/1094670510387914) | 元分析 | 补偿、员工友好行为、组织程序 → 分配/互动/程序公正 → 满意 → 忠诚与口碑；分配公正只对"本次交易满意"最重要，对累积满意并非唯一主导 | 战败后的"物质补偿"只影响这一次的感受；长期留存更多取决于过程是否公正、是否被尊重、是否有人解释（互动与程序公正） |
| Gelbrich & Roschk (2011) *Do complainants appreciate overcompensation?* Marketing Letters 22(1). [Springer](https://link.springer.com/article/10.1007/s11002-010-9101-6) | 17 项实验的元分析 | 超额补偿相对简单补偿的边际效果显著更低 | 战损"全额返还"之上再加码，收益递减；预算应投向覆盖面而非单点加码 |
| Gelbrich, Gäthke & Grégoire (2015) *How Much Compensation Should a Firm Offer for a Flawed Service?* JSR 18(1). [SAGE](https://journals.sagepub.com/doi/10.1177/1094670514543149) | 实验 | 补偿→满意是凹函数：<100% 修复的部分补偿边际效果最大；强关系客户对高补偿反应更好，弱关系客户对高补偿不敏感 | 部分补偿（如返还 30–60% 战损）可能是性价比最高区间；对高投入老玩家可以给更高比例，对新/弱关系玩家加码作用小 |
| Roschk & Gelbrich (2014) *Identifying Appropriate Compensation Types for Service Failures*, JSR 17(2). [SAGE](https://journals.sagepub.com/doi/abs/10.1177/1094670513507486) | 元分析 + 实验（资源交换理论） | 补偿资源与损失资源同类时恢复效果最强：金钱损失→即时金钱补偿；服务失败→重新履行；缺乏关注→心理补偿。即时补偿优于延迟 | 兵损→兵/资源；被指挥失误坑→"重新履行"（重打一次的机会、承诺的下一次行动）；被忽视/没人理→被看见、被认可，而不是发资源；补偿越即时越好 |
| Grewal, Roggeveen & Tsiros (2008) *The Effect of Compensation on Repurchase Intentions in Service Recovery*, J. Retailing 84(4). [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0022435908000468) · [作者 PDF](https://www.dhruvgrewal.com/wp-content/uploads/2014/09/2008-JR-Service-Recovery.pdf) | 实验（稳定性 × 责任归属） | 只有当公司要负责且失败频繁发生时，补偿才提升复购意向；偶发或非公司责任的失败，补偿对复购意向无影响 | 玩家把战败归因于"匹配不公/规则问题/官方偏袒"时补偿有效；归因于"我们自己打得差/对面更强"时，物质补偿对留存意向作用弱，此时更需要的是修复路径与关系 |
| de Matos, Henrique & Rossi (2007) *Service Recovery Paradox: A Meta-Analysis*, JSR 10(1). [SAGE](https://journals.sagepub.com/doi/10.1177/1094670507303012) | 元分析 | 服务恢复悖论在满意度上成立，但在复购意向、口碑、形象上不成立 | 不要指望"补偿得好反而更忠诚"；补偿是止损，不是增益 |

## 3. 补偿的动机副作用

| 来源 | 发现 | SLG 转译 |
|---|---|---|
| Deci, Koestner & Ryan (1999) 128 项实验元分析，Psych. Bulletin 125. [PDF](https://home.ubalt.edu/tmitch/642/articles%20syllabus/Deci%20Koestner%20Ryan%20meta%20IM%20psy%20bull%2099.pdf) | 预期的、有形的、与参与/完成/绩效挂钩的奖励削弱自由选择的内在动机（d = −0.40 / −0.36 / −0.28）；正向反馈提升内在动机（d = +0.33） | 把"上线/参战"与补偿硬挂钩会把参战从自愿变成交易；口头/象征性认可（战报中的表彰、称号）在动机层面比资源更"无副作用" |
| Nurmohamed (2020) *The Underdog Effect*, AMJ 63(4). [AOM](https://journals.aom.org/doi/10.5465/amj.2017.0181) | 被视为"不被看好"可通过"想证明别人错了"提升表现；但当评价者可信度高时反而削弱表现 | "弱者叙事"能激发再战，前提是玩家不认为对方的优势是"权威判定/不可撼动"的；面对压倒性氪金差距，弱者叙事可能失效甚至羞辱 |
| Paharia, Keinan, Avery & Schor (2011) *The Underdog Effect*, JCR 37(5). [OUP](https://academic.oup.com/jcr/article-abstract/37/5/775/2907483) | 弱者传记（外部劣势 + 激情与决心）提升认同与忠诚，对自认弱者者更强 | 给败方联盟提供"劣势 + 坚持"的官方叙事（战争史记、称号）可能强化群体认同；但必须是玩家自己认可的故事 |

## 4. 平衡/追赶机制的接受度

- Depping? 未查。**CHI 2024 "The Trick is to Stay Behind?"（Zhu 等，Techandpeople Lab）**：提出平衡机制设计空间六维（Determination、Timing、Targeting、Effect、Feedback、Information）；8 对参与者体验 7 种机制的混合方法研究。发现：帮助落后者比削弱领先者更受欢迎；技能相关的调整会让强者感到被剥夺；"胜利应当是挣来的"（merited victory）是核心诉求，透明度影响公平感。[ACM](https://dl.acm.org/doi/10.1145/3613904.3642441) · [作者 PDF](https://techandpeople.github.io/downloads/2024_chi_balancing.pdf)。样本极小，仅作方向参考。
- Xue 等 (2017, EA) *Dynamic Difficulty Adjustment for Maximized Engagement in Digital Games*, WWW Companion：以长期参与为目标的 DDA 在 EA 多款三消类游戏中提升参与度最高约 9%。[ResearchGate](https://www.researchgate.net/publication/322414816_Dynamic_Difficulty_Adjustment_for_Maximized_Engagement_in_Digital_Games)。单机三消不等于 PvP 联盟战争；但说明"输后降低下一次难度"在产品层有可测收益。

## 5. 损失缓冲的成熟先例（非 SLG）

| 游戏 | 机制 | 规则要点 | 作用的心理机制 | 来源 |
|---|---|---|---|---|
| 王者荣耀 | 勇者积分 / 掉星保护 | 完成排位且无挂机得积分；含连胜、评分、"虽败犹荣"奖励；积分达阈值时输一局扣积分不掉星；满分再赢额外加星 | 把"输"与"失去等级"部分解耦；奖励努力（虽败犹荣）而非结果；给连败者可见的兜底 | [腾讯官方 S12 说明](https://pvp.qq.com/coming/m/system/180629s12.html) · [18183 规则](https://www.18183.com/yxzjol/202206/3986631.html) |
| 王者荣耀 | 排位保护卡 | 首次到钻石 2 张、星耀 3 张；输局不掉星改扣卡；挂机则失效 | 有限次数的"免死"，附带行为条件（不挂机）防止滥用 | 同上 |
| League of Legends | Demotion Shield | 晋升后约 3 局（分段）/10 局（大段）内不会降级；仍扣 LP/MMR | 新晋升者的宽限期，防止"刚上去就掉下来"的挫败 | [Riot 支持页](https://support.riotgames.com/league-of-legends/gameplay/placements-promotions-series-demotions-and-decay) |

SLG 对应的问题：等级/段位在 SLG 中对应的是"城池、领土、兵力、排名与面子"，缓冲要落在这些对象上（见 N5 的伤兵/护盾/迁城/战损返还目录）。共同点是：缓冲有上限、有行为条件、对"努力但输了"给予认可。

## 6. 网络干扰下的评估方法（供 validation-ethics 使用）

- Ugander, Karrer, Backstrom & Kleinberg (2013) *Graph Cluster Randomization*, KDD. [arXiv](https://arxiv.org/abs/1305.6979)：个体级 A/B 在社交干扰下有偏；以图聚类为单位随机化，并定义"网络暴露"条件。
- Eckles, Karrer & Ugander (2017) *Design and analysis of experiments in networks: Reducing bias from interference*, J. Causal Inference. [arXiv](https://arxiv.org/pdf/1404.7530)：聚类随机化 + 邻域暴露分析显著降低干扰偏差。
- SLG 转译：任何"情绪按摩/补偿/隔离"实验都应以联盟（或服务器）为随机化单位；跨盟外交关系意味着联盟间也有溢出，最好以服务器/战区分组，并接受更少的实验单位、更长的实验周期。

## 7. 本笔记的直接结论（供 support-playbook.md / validation-ethics.md 使用）

1. 补偿对象按"增量"选，不按"风险"选；风险模型只做候选池。
2. 补偿数额取凹函数的陡峭段（部分补偿），对强关系老玩家可提高比例；超额补偿收益低。
3. 补偿类型与损失类型同类：兵损给兵，被坑给"重来的机会"，被忽视给关注。
4. 补偿在玩家归因于"系统/规则不公"时最有效；归因于"己方实力不济"时应转向路径与关系支持。
5. 不要让补偿推送本身成为"重新审视要不要走"的触发器；避免把参战与补偿硬挂钩。
6. 平衡机制优先"帮弱"不"削强"，且胜利必须仍显得是挣来的。
7. 评估必须做聚类随机化，否则效应估计不可信。
