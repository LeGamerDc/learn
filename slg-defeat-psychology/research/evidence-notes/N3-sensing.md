# N3｜行为感知与流失预测的证据笔记

检索日期：2026-09-22/23。由主研究者自行检索。读取深度：`摘要` / `部分全文` / `二手` / `记忆待核`。服务于 sensing-and-warning.md 与 validation-ethics.md。

## A. 流失预测文献中被报告为重要的特征

| 来源 | 数据 | 关键特征 / 结果 | 深度 |
|---|---|---|---|
| Kim 等 2017，PLOS ONE，休闲手游/网游日志 | 三款游戏 | 活跃时长（active duration）与游玩次数（play count）最重要；LR/GBM/RF 准确率 77–78% | [PLOS](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0180735)（摘要/二手） |
| Lee 等 2016（经综述转述） | MMO | **购买次数与参加公会活动的次数**是最重要预测因子；最后一次登出时剩余虚拟货币量也有效 | 二手 |
| Runge 等 2014；Lee 等 2020；Fu 等 2017（经综述转述） | 社交手游/MMO | 社交特征：发出的邀请数、**好友退游**、军团（legion）缩减、群体互动率、与流失者互动的人数、好友数、是否入会及**公会职务** | 二手 |
| Periáñez 等 2016 生存集成 | 手游社交游戏 | 生存分析（时间到流失）比二分类更适合定义流失窗 | [arXiv](https://arxiv.org/pdf/1710.02264)（摘要） |
| Lee 等 2018 NCSoft 竞赛（Blade & Soul） | 商业日志 | 提供流失 + 生存双任务基准 | [ResearchGate](https://www.researchgate.net/publication/323003858)（摘要） |
| Park, Cha, Kwak & Chen 2017 *Achievement and Friends* | 51,104 名玩家 | 留存的关键因子随等级变化：初中期是成就特征，**到顶级后社交特征成为最强预测** | [arXiv](https://arxiv.org/abs/1702.08005)（摘要） |
| Kawale 等 2009（见 evidence-games G8） | EverQuest II | 网络扩散特征 + 参与特征优于单一特征 | 见 evidence-games |
| Ducheneaut 等 2007 | WoW 公会 | 成员流失具社会传染性，邻居更可能跟随；月流失≈25% | 二手 |
| Shores 等 2014 | LoL | 毒性指数；毒性玩家让**新玩家**流失，老玩家更有抵抗力 | [ACM](https://dl.acm.org/doi/10.1145/2531602.2531724)（摘要） |

对 SLG 的转译：老玩家（本课题的主要对象）的留存由社交特征主导，因此感知方案的核心不是登录曲线，而是**社交网络的完整性与职务节点的稳定性**。

## B. 预测→干预的实验证据

| 来源 | 发现 | 含义 |
|---|---|---|
| Milošević, Živić & Andjelković 2017，ESWA 83:326–332 | 《Top Eleven》约 200 万玩家；只用注册后第 1 天行为做流失二分类；两种推送召回方式（按玩家常用功能个性化）；摘要称**流失最多降低 28%**。作者 2015 年博客（非论文）：逻辑回归 recall 0.85、precision 0.7；非个性化推送组留存比对照 +30%，个性化组再比非个性化 +40% | 早期流失可预测并可干预；个性化（按玩家实际在玩的内容）比泛推送更有效。论文正文未读到 [Semantic Scholar](https://www.semanticscholar.org/paper/1fc01708b0cab0cdcb9f794d0e0ee7dcd9f5e61e)（摘要）、[Game Developer 博客](https://www.gamedeveloper.com/programming/how-data-scientists-slashed-early-churn-in-top-eleven)（全文） |
| Ascarza 2018（见 N9） | 按"对干预的敏感度"定向显著优于按流失概率定向 | 需要随机对照才能得到 uplift |
| Ascarza 等 2016（见 N9） | 主动干预使流失 6%→10% | 干预可能反向 |
| Lemmens & Gupta 2020（见 N9） | 按利润增量定向 | 预算分配原则 |

## C. 从行为推断情绪状态

- 学术上"从日志推断情绪"属于玩家体验建模（PEM）。Yannakakis & Togelius 2011（*IEEE Trans. Affective Computing* 2(3):147–161）把 PEM 分为主观（自我报告）、客观（生理）、基于游戏行为三类；基于行为的 model-free 方法需要把日志特征映射到体验标签，标签通常来自局后自我报告。该团队主张用**排序/成对偏好**而非打分收集标签（Martinez, Yannakakis & Hallam 2014 "Don't classify ratings of affect; rank them!"；Yannakakis & Martinez 2015 "Ratings are overrated!"）。[PDF](https://yannakakis.net/wp-content/uploads/2015/11/PID3821875.pdf)（部分全文）
- 应用内微问卷回复率（通用 App，非游戏）：Refiner 2025（1,382 份问卷、约 5,030 万次展示）平均 27.5%，移动 App 36.1%；Alchemer/Apptentive 移动端约 13%，娱乐类 18–19%。未找到游戏战后微问卷的公开基准。[Refiner](https://refiner.io/blog/in-app-survey-response-rates)、[Alchemer](https://www.alchemer.com/resources/blog/mobile-survey-response-rates)（厂商博客，二手）
- 游戏流失预测精度：Kim 等 2017（*PLoS ONE* 12(7):e0180735，3 款休闲游戏）AUC 0.686–0.824；Kristensen & Burelli 2019（IEEE CoG）AUC 0.84–0.87；Hadiji 等 2014（5 款 F2P）F1 0.68–0.88；Bonometti 等 2019 F1 0.65–0.70；NCSOFT GDMC 全体用户 F1 约 0.60–0.72，只看忠实用户降到 0.39–0.53。离群值：Perisic & Pahor 2020 AUC 0.53–0.71。结果高度依赖流失定义与预测窗口。[Kim 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5498062)、[Kristensen 2019](https://arxiv.org/abs/1905.10998)（全文表格）
- 聊天文本情绪分析的已知难点：新俚语/黑话不断出现、**反讽是最难的任务之一**（[腾讯云开发者综述](https://cloud.tencent.com/developer/article/2187295)，摘要）。SLG 聊天里的"打得好啊""牛"多为反讽，需要结合上下文（刚失城）判定。
- Riot 2023 行为系统：接入文本模型后可处置的干扰文本量 >15×，说明大规模文本检测在生产环境可行（见 N5 §9）。
- 外部渠道（微信/QQ/Discord）承载大量组织沟通（GameRes：管理者"在微信群中的时间甚至要多于游戏中的时间"），游戏内聊天只是部分信号。

## D. 合规约束

- 《个人信息保护法》：用户标签、画像信息属于个人信息；生物识别、行踪轨迹等属于敏感个人信息；自动化决策须提供拒绝选项；向第三方共享画像需单独同意；处理 100 万人以上需设个人信息保护负责人（[网信办问答](https://www.cac.gov.cn/2026-01/09/c_1769688003183197.htm)、[法条](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)，摘要）。情绪推断结果若以"心理状态"标签形式长期存储并用于差别对待，风险高于一般行为标签；建议只存储行为特征与"风险分"，不存储"情绪诊断"。
- 《互联网信息服务算法推荐管理规定》（2022-03-01 施行）第八条："不得设置诱导用户沉迷、过度消费等违反法律法规或者违背伦理道德的算法模型"；第十七条：应当向用户提供不针对其个人特征的选项或便捷的关闭选项，并提供选择或删除个人特征用户标签的功能；第十八条：不得利用算法推荐服务诱导未成年人沉迷网络。注意 2021-08 征求意见稿条号与措辞不同，不要引用。[网信办原文](https://www.cac.gov.cn/2022-01/04/c_1642894606364259.htm)（全文）
- EU AI Act 第 5(1)(f) 条：禁止在**工作场所与教育机构**用 AI 推断情绪（基于生物特征数据）；对**消费者**的情绪推断属高风险而非禁止，且限于生物特征（声音、面部、步态、生理信号、击键节奏）；基于文本/行为日志的推断不在该定义内（[FPF](https://fpf.org/blog/red-lines-under-eu-ai-act-unpacking-the-prohibition-of-emotion-recognition-in-the-workplace-and-education-institutions/)，摘要）。出海产品仍需按高风险系统的透明与记录要求评估。
- 未成年人：不满 14 周岁个人信息为敏感个人信息；SLG 实名制下可排除。

## E. 结论

1. 最有预测力的三类信号：参与结构变化、社交网络与职务节点变化、付费/资源处置变化。
2. 老玩家留存以社交为主，感知方案应以"关系与角色"为中心。
3. 标签来源以战后微问卷 + 30/60 日行为结果 + 退盟/迁服事件为主；聊天 NLP 作辅助且需反讽处理。
4. 干预效果只能通过随机对照的 uplift 估计，不可从预测模型倒推。
5. 合规上：存行为与风险分，不存"情绪诊断"；提供拒绝个性化的选项；联盟级诊断只给聚合结果。
