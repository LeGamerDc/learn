# N4 — 战败后玩家的心理/情绪支撑类干预：证据笔记

> 范围：赛季制 SLG（率土之滨、三国志·战略版、RoK、Last War、Whiteout Survival 等）"联盟战败 → 玩家情绪 → 退游潮"课题中，**心理与沟通类**干预（情绪按摩 / 认知与意义 / 团队恢复 / 隔离与宣泄）。物质补偿与游戏机制由 N9 负责，本文只在"补偿如何被感知"（施舍感、程序公正）处与之交叉。
> 方法：2026-09-22 检索，工具 WebSearch / WebFetch / Tavily search+extract，共 60+ 次检索与抓取；对 6 篇 PDF 做了本地文本抽取（pdftotext）。每条来源标注**读取深度**：`全文` / `部分全文`（抓到正文片段或结果段）/ `摘要` / `二手`（经他人综述或新闻转述）/ `记忆待核`（未在本轮抓到原文，凭已有知识写入，须复核）。
> 约定：效应量 d = Cohen's d（0.2 小 / 0.5 中 / 0.8 大），r = 相关（0.1 小 / 0.3 中 / 0.5 大），OR = 比值比。

---

## 0. 一页结论（给设计师）

1. **先分状态再选支持**：战败后玩家不是一种状态。愤怒-外归因、羞耻-内归因、无望、耗竭、被背叛、观望，各自匹配不同支持类型（§1）。"一刀切"的全服安慰或全服复盘是最常见的反作用来源。
2. **最强证据在"团队复盘"而不是"情绪疏导"**：结构化 AAR/debrief 元分析 d = 0.67–0.79（约 +25% 绩效），条件是学习导向、参与式、有客观记录；而单次"情绪复盘/宣泄晤谈"（CISD）Cochrane 结论为无效甚至有害（1 年 PTSD OR 2.51）。
3. **"安慰"要先验证情绪、再给认知重构**：Nils & Rimé 2012 实验显示纯共情式倾听只带来暂时舒缓与亲近感，**真正的情绪恢复只发生在听者引导认知重构时**；而无效化式回应（"别想了""这有什么"）实验中显著升高负性情绪、心率与皮电（Shenk & Fruzzetti 2011）。
4. **帮助方式决定帮助被如何感知**：自主导向（给工具/路径）优于依赖导向（直接给结果）；后者让接受者推断"施舍/维持地位"动机、降低接受意愿（3 实验 N=677）。补偿设计应当"给路径"而非"发救济"。
5. **时机是变量不是常量**：道歉延后（受害者先"被听见"）更有效（Frantz & Bennigson 2005）；获益发现与意义建构宜延后（天–周）；表达性写作不宜在创伤即刻；官方信息与谣言控制则必须最早（CERC "be first"）。
6. **口号类干预效应很小且依赖环境**：成长型思维干预对成绩 d ≈ 0.08（Sisk 2018）、仅在同伴规范支持时对低成就者 +0.10 GPA（Yeager 2019, N>12,000）；希望增强干预对痛苦无效（Weis & Speridakos 2011, k=27）。不要把"正能量文案"当主力。
7. **认可与感谢是低成本高杠杆**：一句针对努力的感谢使再次帮助率从 32%→66%、25%→55%，机制是"社会价值感"而非自我效能（Grant & Gino 2010）；Overwatch 表扬系统上线后"含破坏性行为对局"降 40%（Blizzard 自报）。
8. **凝聚力的方向**：任务凝聚（共同目标）与绩效相关（r≈.43），社会凝聚（互相喜欢）在控制任务凝聚后无独立效应，且"绩效→凝聚"强于"凝聚→绩效"（Mullen & Copper 1994 via MacCoun）。战败后先修"任务"（下一个可达目标），社交活动是辅助。

---

## 1. 状态-支持匹配框架（本笔记的组织轴）

| 战败后状态 | 典型表现（SLG） | 主要支持类型 | 首选干预（详见后文） | 首要禁忌 |
|---|---|---|---|---|
| 愤怒-外归因 | 骂盟主/指挥/匹配/氪金差距，全服喊话 | 信息 + 程序公正 | CERC 式官方说明；发声渠道；冷却期 | 说教、控制性语言、"发泄区"、信息真空 |
| 羞耻-内归因 | "我拖后腿"，沉默、下线 | 尊重/认可 + 认知重构 | 针对努力的具体感谢；归因再训练；自我慈悲提示 | 公开排名羞辱；纯"加油"；依赖式救济 |
| 无望 | "差距太大，赛季已定" | 效能 + 希望（路径） | 把大目标拆小；具体可达路径；小胜利 | 空泛的希望口号；近失暗示 |
| 耗竭 | 连续熬夜、麻木、"打不动了" | 平静 + 安全 | 减刺激、安全期、无新活动；延后复盘 | 立刻复盘、堆活动、逼参与 |
| 被背叛 | 盟主跑路/内鬼/盟友卖队 | 信任修复 + 公正 | 能力型：道歉+说明；诚信型：证据/否认；六要素道歉 | 让诚信型违背者"道歉了事"；黑箱补偿 |
| 观望 | 潜水看风向、犹豫退不退 | 归属 + 意义 | 仪式（赛季告别/纪念）、身份、任务凝聚、"别人也输了"慎用 | 强推社交、拉人头 |

---

## A. 支持匹配与帮助的副作用

### A1. 社会支持最优匹配（Optimal Matching）

**来源**
- Cutrona, C. E., & Russell, D. W. (1990). Type of social support and specific stress: Toward a theory of optimal matching. In Sarason, Sarason & Pierce (Eds.), *Social Support: An Interactional View* (pp. 319–366). Wiley. https://www.researchgate.net/publication/232560583 — 读取深度：**二手**（经引用文献转述）。
- Cutrona, C. E., & Suhr, J. A. (1992). Controllability of stressful events and satisfaction with spouse support behaviors. *Communication Research, 19*(2), 154–174. https://journals.sagepub.com/doi/10.1177/009365092019002002 — 读取深度：**摘要**。

**核心发现**
- 理论：支持分五类（informational / emotional / esteem / network / tangible），归为"行动促进型"（信息、实物）与"抚育型"（情绪、尊重、网络）。**可控事件→行动促进型支持更有效；不可控事件→抚育型支持更有效**。
- 实证（1992）：60 名已婚者向配偶倾诉压力事件，观察者评定事件可控性。结果：**信息型支持在高可控事件中提供最多；五类支持中只有"信息"在高/低可控情境下被评价不同**；结论为"对最优匹配模型提供了有限支持（limited support）"。

**SLG 转译**
- 战败原因可控（指挥失误、集结迟到、资源分配）→ 玩家想要的是"怎么改"（信息/战术支持），此时给情绪安抚会被视为敷衍。
- 战败原因不可控（对面氪金碾压、跨服匹配失衡）→ 情绪与尊重支持优先，此时给"战术建议"等于暗示"你本可以做得更好"，引发抗拒。
- 设计例：战报页面按"可控/不可控"两栏呈现（"我们能改的 3 件事" / "本局无法改变的条件"），分别配不同的后续动作（复盘入口 vs 认可与荣誉入口）。

**边界**：1992 年数据只对"信息支持"检出匹配效应，其它四类未检出；模型更像启发式而非强定律。对 SLG 的启示主要在"不要在不可控失败后给建议"这一方向。

### A2. 自主导向 vs 依赖导向的帮助；接受帮助的自尊威胁

**来源**
- Nadler, A. (2002). Inter-group helping relations as power relations: Maintaining or challenging social dominance between groups through helping. *Journal of Social Issues, 58*(3), 487–502. https://www.humiliationstudies.org/documents/NadlerIntergroupHelping.pdf — 读取深度：**部分全文**。
- Fisher, J. D., Nadler, A., & Whitcher-Alagna, S. (1982). Recipient reactions to aid. *Psychological Bulletin, 91*(1), 27–54. https://cris.tau.ac.il/en/publications/recipient-reactions-to-aid-2 — 读取深度：**摘要**。
- （补充实证）Dependency-Oriented Versus Autonomy-Oriented Help: Inferred Motivations and Intergroup Perceptions. *PMC* (2024). https://pmc.ncbi.nlm.nih.gov/articles/PMC11590873 — 读取深度：**部分全文**。

**核心发现**
- Nadler：**自主导向帮助** = 给接受者解决问题的工具，隐含"你有能力"；**依赖导向帮助** = 直接给完整解决方案，隐含"你不行"，并维持/扩大帮助者与接受者之间的地位差距。高需求、自主导向、非核心身份维度的帮助最易被接受。
- Fisher 等 1982：整合 equity / attribution / reactance / threat-to-self-esteem 四种取向，提出**自尊威胁模型**：帮助中携带的"自我相关信息"（你弱/你被看不起）决定接受者反应是感激还是防御。
- 2024 实证（3 实验，N=677）：接受依赖导向帮助者推断帮助者"维持地位"动机更高、利他动机更低，对帮助者的温暖与能力评价更低，**接受帮助与合作意愿下降；当帮助对接受者越重要、或接受者明确要求自主帮助却被给予依赖帮助时，效应更强**。

**SLG 转译**
- 战败补偿如果是"系统直接发资源"，在自尊受威胁的玩家眼中可能读作"施舍"。更好的形式：给"加速重建的工具"（限时双倍产出、可选的复建蓝图、对指挥的战术工具解锁）——让玩家"自己把它做回来"。
- 盟内互助（大佬给小号送资源）要包装为"任务型/交换型"（护送、共建），避免"救济"语义；给受助者一个回馈路径。
- 设计例：① "重建令"——玩家选择把补偿投向哪条线（兵/城/科技），系统只提供加倍器；② "战友互助"以任务形式出现（"为 3 名盟友护送资源可得联盟贡献"），双方都是行动者；③ 补偿文案避免"抚恤""救济""慰问"，改用"重整""复建""再战"。

**边界**：Nadler 的核心证据来自群际（高地位帮低地位）情境；玩家-官方之间"官方=高地位"的结构与此相符，但盟内平级互助的证据较弱。

### A3. 心理抗拒（Reactance）与被说教

**来源**
- Brehm, J. W. (1966). *A Theory of Psychological Reactance*. Academic Press. — 读取深度：**二手**。
- Rains, S. A. (2013). The nature of psychological reactance revisited: A meta-analytic review. *Human Communication Research, 39*, 47–73. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1468-2958.2012.01443.x — 读取深度：**摘要**（K=20, N=4,942）。
- Miller, C. H., Lane, L. T., Deatrick, L. M., Young, A. M., & Potts, K. A. (2007). Psychological reactance and promotional health messages: The effects of controlling language, lexical concreteness, and the restoration of freedom. *Human Communication Research, 33*(2), 219–240. https://eric.ed.gov?id=EJ755929 — 读取深度：**摘要**；后续检验经 Reynolds-Tylus 2019 综述 https://www.frontiersin.org/journals/communication/articles/10.3389/fcomm.2019.00056/full — **二手**。
- Li & Shi (2026). Message effects on psychological reactance: Meta-analyses. *Human Communication Research, 52*(1), 38–52. doi:10.1093/hcr/hqaf016（28 篇文章、33 项研究）https://scholars.hkbu.edu.hk/en/publications/message-effects-on-psychological-reactance-meta-analyses — 读取深度：**摘要**。
- Reynolds-Tylus, T. (2019). Psychological reactance and persuasive health communication: A review of the literature. *Frontiers in Communication, 4*:56. https://www.frontiersin.org/journals/communication/articles/10.3389/fcomm.2019.00056/full — 读取深度：**部分全文**。

**核心发现**
- 抗拒 = 自由受威胁时的动机状态，测量上为"愤怒 + 反驳认知"的交织体（Rains 2013 元分析支持 intertwined model）。
- 控制性语言（"你必须""不容否认""别再逃避"）引发更多愤怒、反驳与信源贬损。Li & Shi 2026 元分析：高威胁语言→抗拒 r = .20（k=53），→愤怒 r = .21，→负面认知 r = .17；愤怒、负面认知与说服结果分别 r = −.23、−.18。（原笔记"r ≈ .26 / 回弹 r ≈ .08–.13"只出自一篇博客且误挂在 Rains 2013 名下，已删除。）
- Miller 2007：在信息末尾加"恢复自由"后记（原文 "The choice is yours. You are free to decide for yourself"）降低了感知的自由威胁，结果更积极。**后续重复不稳定**：Quick 等 2015 无效；Bessarabova 2017 只在高威胁信息中有效，低威胁时反而降低说服（二手）。含义：先去掉控制性措辞，后记只是补丁。
- 抗拒随"自由的重要性、威胁强度、事先拥有该自由的预期"放大。

**SLG 转译**
- 战败后系统/盟主的"你们应该……""必须每天上线集结"式动员是典型触发。改用自主支持句式："下一次你可以选择……""如果你愿意，这里有 3 条路"。
- 所有战后引导页加"恢复自由后记"：明确"是否参与复盘/重建由你决定"，反而提升参与。
- 设计例：① 盟主公告模板内置"三选一路径 + 选择权声明"；② 系统推送避免"必须""立刻""否则"；③ 对退盟/换服操作不设道德化拦截文案（"真的要抛弃盟友吗？"会触发抗拒并坐实离开）。

### A4. 情绪无效化 / "有毒正能量" / 过早安慰

**来源**
- Shenk, C. E., & Fruzzetti, A. E. (2011). The impact of validating and invalidating responses on emotional reactivity. *Journal of Social and Clinical Psychology, 30*(2), 163–183. https://pure.psu.edu/en/publications/the-impact-of-validating-and-invalidating-responses-on-emotional- — 读取深度：**摘要**（+二手细节：N=60 本科生）。
- Nils, F., & Rimé, B. (2012). Beyond the myth of venting: Social sharing modes determine the benefits of emotional disclosure. *European Journal of Social Psychology, 42*, 672–681. https://www.academia.edu/107375960 — 读取深度：**摘要**。
- Frantz, C. M., & Bennigson, C. (2005). Better late than early: The influence of timing on apology effectiveness. *Journal of Experimental Social Psychology, 41*, 201–207. https://www.sciencedirect.com/science/article/pii/S0022103104001167 — 读取深度：**摘要**（+FIT 转述：Study 1 n=24 真实冲突回忆；Study 2 n=83 情境实验）。
- "Toxic positivity" 相关：目前主要是评论与综述（The Conversation 2021；IJIP 2025 系统综述），缺少高质量实验；其机制证据依赖 Gross & John 2003 的情绪抑制研究（二手）。

**核心发现**
- Shenk & Fruzzetti：心算压力任务下，随机得到**无效化回应**（"我不明白你为什么会这样觉得"）者，负性情绪、心率、皮电随时间显著高于得到**验证回应**（"换我做这个任务也会烦"）者。
- Nils & Rimé（2×2：认知/非认知 × 社会情感/中性）：**情绪恢复只在听者激发倾诉者认知工作（重构）时发生**；社会情感（共情）回应带来社会整合（更亲近、更少孤独）与"感觉好些"的印象，但 2 天后再暴露时情绪并未恢复。即"倾诉/发泄有益"是神话，益处取决于回应模式。
- Frantz & Bennigson：**后置道歉比即刻道歉更有效**，中介是受害者"感到被听见、被理解"。

**SLG 转译**
- 官方/盟主的战后第一句话应是验证（"这一仗大家熬了三晚，输了确实难受"），而不是"胜败乃兵家常事""下赛季再来"——后者就是无效化。
- 验证之后再给"认知重构"素材（我们打出了什么/对手做对了什么/我们能改的是什么），这才是恢复的来源。纯共情频道（"抱团取暖"）能留人但不能恢复。
- 道歉/说明的顺序：先让玩家说（意见收集、投票、语音），确认被听见，再由盟主/官方道歉，效果更好；"秒回道歉"会被读作公关。
- 设计例：① 战败后系统消息两段式：验证句 + 事实句，不出现劝慰语；② 盟内"战后留言板"先于"盟主总结"开放 12–24 小时；③ 官方补偿公告置于玩家反馈窗口之后发布，并引用反馈内容。

**边界**：Nils & Rimé 是实验室观影范式，不是竞技失败；但方向与 Pennebaker/Rimé 一系列研究一致。"有毒正能量"概念本身缺乏直接实验证据，只能借用无效化与情绪抑制研究。

### A5. CISD 与"强制情绪复盘"的风险

**来源**
- Rose, S., Bisson, J., Churchill, R., & Wessely, S. (2002). Psychological debriefing for preventing post traumatic stress disorder (PTSD). *Cochrane Database of Systematic Reviews*, CD000560. https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD000560/full — 读取深度：**摘要（含数据）**。

**核心发现**
- 纳入 RCT：创伤后 1 个月内、单次会谈、含情绪加工/宣泄与反应正常化。**单次个体晤谈不能预防 PTSD、不能降低痛苦**；1–4 个月 PTSD 严重度 SMD 0.11（95% CI 0.10–0.32，方向对干预不利）、6–13 个月 SMD 0.26（0.01–0.50）；**一项试验 1 年时 PTSD 风险显著升高 OR 2.51（1.24–5.09）**（早期版本报 2.88）。对抑郁、焦虑无益，不优于教育性干预。结论："对创伤受害者的强制晤谈应停止。"
- Hobfoll 等 2007 在"不推荐"栏明确列出心理晤谈（可能增强唤醒）。

**SLG 转译**
- 不要在战败当晚组织"全员情绪复盘会"要求每人说感受。
- 允许"不复盘就走"；复盘应是任务/学习导向的 AAR（见 C1），不是情绪导向的宣泄。
- 设计例：① 战后语音/文字"复盘频道"默认关闭情绪话题模板，只提供事实卡片；② 不给"发泄"设奖励（如"吐槽有礼"）；③ 对高情绪玩家提供"离场不扣贡献"的选项。

**边界**：CISD 证据来自真实创伤（事故、犯罪受害）；游戏战败强度远低，但"被要求当众重述失败 + 正常化"这一结构相同，方向性风险可迁移。

### A6. 心理急救（PFA）与 Hobfoll 五要素

**来源**
- Hobfoll, S. E., et al. (2007). Five essential elements of immediate and mid-term mass trauma intervention: Empirical evidence. *Psychiatry, 70*(4), 283–315. https://pubmed.ncbi.nlm.nih.gov/18181708 ; PDF https://escholarship.org/content/qt0983p74m/qt0983p74m_noSplash_fce93e11f427f11a5e7a9a9200b57141.pdf — 读取深度：**部分全文**。
- PFA 证据综述：Fox et al. (2012) *Disaster Med Public Health Prep* 6:247–252 https://www.cambridge.org/core/journals/disaster-medicine-and-public-health-preparedness/article/effectiveness-of-psychological-first-aid-as-a-disaster-intervention-tool-research-analysis-of-peerreviewed-literature-from-19902010/E6F37484F66750D3EB326E9D19029F3B ；Dieltjens et al. (2014) *PLoS ONE* https://pmc.ncbi.nlm.nih.gov/articles/PMC4264843 ；2023 系统综述 https://pmc.ncbi.nlm.nih.gov/articles/PMC10624106 — 读取深度：**摘要/部分全文**。

**核心发现**
- 五要素（专家共识 + 相关领域外推）：①安全感 ②平静 ③自我与集体效能 ④联结 ⑤希望。
- 具体建议（抓到的正文）：问题聚焦应对训练——**把"一个巨大不可解的问题"拆成小的可管理单元**，以提升控制感、创造"小胜利"、并实际减少问题；正常化压力反应；用积极情绪活动（与朋友在一起、运动、喜剧）平静下来；**不推荐**：苯二氮卓类、心理晤谈（可能增强唤醒）。限制反复暴露于媒体画面（"只看事实、不看渲染"）。
- PFA 本身：三轮系统综述一致结论——**"evidence-informed but not evidence-based"**，没有 RCT 证明其效果；它是被广泛推荐的安全底线，不是被证明的疗效。

**SLG 转译**
- 五要素可直接作为战败后 72 小时的检查表：安全（不会被继续追打/城池保护）、平静（减少刺激与推送）、效能（可完成的小任务）、联结（盟内私聊/小队）、希望（下一个具体节点）。
- "拆小"是最可操作的一条：战败后立即给出 3 个 10 分钟内可完成的小目标，而不是"重建联盟"。
- 限制"媒体暴露"的对应物：战败后全服频道/对手嘲讽的可见性可以做默认折叠。
- 设计例：① 战败保护期内关闭跨盟喊话的默认可见；② "重整清单"三件小事 + 即时完成反馈；③ 盟内"值班电话"——指定 2 名在线盟友作为联结点，而非全员语音。

**边界**：五要素是共识框架，其效应量来自各自的原始领域（如效能、社会支持研究），未在整体上被 RCT 验证。

### A7. 危机与应急沟通（CERC）

**来源**
- Reynolds, B., & Seeger, M. W. (2005). Crisis and emergency risk communication as an integrative model. *Journal of Health Communication, 10*(1), 43–55. https://www.researchgate.net/publication/7970925 — 读取深度：**二手 + 摘要**。
- Miller, A. N., et al. Being first, being right, and being credible since 2002: A systematic review of CERC research. *Journal of International Crisis and Risk Communication Research*. https://jicrcr.com/index.php/jicrcr/article/download/38/39 — 读取深度：**部分全文**（400 篇文献的系统综述；CERC 在其中 101 篇为主角）。
- CDC CERC 六原则（Be first, Be right, Be credible, Express empathy, Promote action, Show respect）— 读取深度：**二手**（教材摘要）。

**核心发现**
- 五阶段模型：pre-crisis → initial event → maintenance → resolution → evaluation。**initial event 阶段目标：建立共情、安抚、让响应主体被认识；maintenance 阶段目标：纠正谣言、争取支持与合作；resolution：公开、坦诚地讨论原因/责任/应对是否足够；evaluation：记录并传达教训。**
- 系统综述指出 CERC 主要是最佳实践整合，作为可检验理论的实证研究仍少。

**SLG 转译**
- "Be first"：战败结算后 30 分钟内官方/盟主有第一条说明（哪怕只是"我们知道了，X 小时内给完整说明"），抢在谣言前。
- "Be right / credible"：不确定的就说不确定；不要先承诺补偿再改口。
- "Express empathy" 放在事实之前一句，不多；"Promote action"给一件立刻能做的事；"Show respect"= 不指责玩家没上线。
- 设计例：① 盟主战后公告模板按 CERC 六句结构生成；② 官方对争议判定（如跨服匹配）在 24h 内公布判定依据；③ 争议期设"已知问题/处理进度"看板替代客服私聊。

### A8. 谣言心理学与谣言控制

**来源**
- DiFonzo, N., & Bordia, P. (2007). *Rumor Psychology: Social and Organizational Approaches*. APA. https://psycnet.apa.org/record/2006-13469-003 — 读取深度：**摘要/二手**。
- DiFonzo, N., & Bordia, P. (2000). How top PR professionals handle hearsay: Corporate rumors, their effects, and strategies to manage them. *Public Relations Review, 26*(2), 173–190. https://www.academia.edu/3437287 — 读取深度：**摘要/要点**。
- Bordia, P., DiFonzo, N., & Schultz, C. A. (2000). Source characteristics in denying rumors of organizational closure: Honesty is the best policy. *Journal of Applied Social Psychology* — 读取深度：**二手**。
- Rosnow (1991) 元分析 7 项谣言研究：焦虑与谣言传播 r = .48（经 PMC9015072 转述）— 读取深度：**二手**。

**核心发现**
- 谣言传播的五因素：不确定性、重要性/结果相关卷入、失控感、焦虑、可信度。高焦虑者用更少刺激即可传播谣言；分享谣言是缓解焦虑的策略；"信任下降处，谣言上升"。
- PR 调查：有害组织谣言以"岗位安全/人事变动"为主（对应 SLG："盟主要跑""大佬要退""要合服"）；**最有效策略是"结构化不确定性"（说明指导价值、给出沟通时间表）与"强化正式沟通"**；"无可奉告"最差；否认时信源的诚实与可信度比否认措辞更重要，且效应在高个人相关性时最明显。

**SLG 转译**
- 战败后最危险的谣言是"盟主/核心要走""要解散""官方偏袒对面"。对策不是删帖，而是**给时间表**（"周三 20:00 盟会决定下赛季去向"）和**指导价值**（"我们决定去留的原则是……"）。
- 官方对判定争议：定时更新，即使没有新信息也发"目前没有新信息，下次更新 X 点"。
- 设计例：① 盟内"公告置顶 + 更新时间戳"；② 系统对"联盟解散/盟主转让"等高焦虑事件给出官方状态标签（"盟主在线，未发起解散"）；③ 盟主离线超过 N 小时时自动显示"代理指挥"以压不确定性。

---

## B. 认知与意义类干预（效应量与边界）

### B1. 归因再训练（Attributional Retraining, AR）

**来源**
- Hamm, J. M., Perry, R. P., Chipperfield, J. G., et al. (2017). Attribution-based motivation treatment efficacy in an online learning environment for students who differ in cognitive elaboration. *Motivation and Emotion*. 预印本 https://centaur.reading.ac.uk/72219/3/Hamm%20et%20al.%20AR%20x%20ELAB%20MOEM%20Manuscript%20Aug%2017%202017%20%25281%2529.pdf — 读取深度：**部分全文**。
- Lazowski, R. A., & Hulleman, C. S. (2016). Motivation interventions in education: A meta-analytic review. *Review of Educational Research, 86*(2), 602–640. — 读取深度：**二手**（经 Hamm 2017 转述：AR vs 无处理 d = 0.54）。
- Haynes, Perry, Stupnisky & Daniels (2009) 综述；Perry et al. (2014) 综述 — 读取深度：**二手**。
- Dresel & Haugwitz (2008) 计算机化再归因训练，151 名六年级生：动机 d = 0.45（5 个月后 0.35），数学知识 d = 0.54（随访消失）— 经 Whalen 2024 转述 https://onlinelibrary.wiley.com/doi/10.1111/jcal.12889 — 读取深度：**二手**。

**核心发现**
- AR 把"不可控归因"（能力差、题太难、运气）替换为"可控归因"（努力不足、策略不当），典型形式是 1 次 10–20 分钟的视频/写作 + 巩固练习。
- 效应：AR vs 无处理 d ≈ 0.54（中等），换算为 1–2 个字母等级；Hamm 2017 随机对照（N=806 大一学生，AR vs 压力缓解处理）两学期成绩 d = 0.39，**AR 主要通过降低不可控归因（而非直接提高可控归因）间接提升控制感（+12% SD）**。对低精加工者（不主动反思的人）效果更明显。

**SLG 转译**
- 战报不只显示"输了"，而显示"输在哪一段、哪一个可改变量"（集结时差、兵种克制、资源缺口）；把"对面氪金"这类不可控因素与"我们能改的"分开呈现，让玩家的因果解释落到可控项。
- 对羞耻-内归因玩家，AR 尤其重要：把"我菜"改写为"这次策略 X 不对"。
- 设计例：① 战败复盘卡"三个可改变量"自动生成；② 指挥端提供"归因模板"（禁止"没人上线"这种指向人格/态度的归因，改为"集结提醒未覆盖 30% 成员"）；③ 新赛季前推送"上赛季你改进最多的一项"。

**边界**：AR 证据来自学业情境；对"团队失败"的 AR 研究少。若失败真的不可控（碾压局），AR 强推可控归因会变成责怪受害者——此时应转向 A1 的情绪支持。

### B2. 自我肯定（Self-Affirmation）

**来源**
- Cohen, G. L., & Sherman, D. K. (2014). The psychology of change: Self-affirmation and social psychological intervention. *Annual Review of Psychology, 65*, 333–371. https://ed.stanford.edu/sites/default/files/annurev-psych-psychology_of_change_final_e2.pdf — 读取深度：**部分全文**。
- Epton, T., Harris, P. R., Kane, R., van Koningsbruggen, G. M., & Sheeran, P. (2015). The impact of self-affirmation on health-behavior change: A meta-analysis. *Health Psychology, 34*(3), 187–196. https://research.manchester.ac.uk/en/publications/the-impact-of-self-affirmation-on-health-behavior-change-a-meta-a — 读取深度：**摘要 + 二手数字**。

**核心发现**
- 机制：写 10 分钟"对我最重要的价值"，让威胁在更大的自我图景中变小，减少反刍与防御，使人能面对负面信息并采取建设性行动；Cohen & Sherman 报告 Cohen 2006/2009 的少数族裔学生成绩差距缩小，且效应可持续多年；也承认存在零效应与隐藏调节变量（如特质防御性）。
- Epton 2015 元分析（41 项研究、144 个检验）：**对信息接受 d+ = .17，意图 d+ = .14，行为 d+ = .32**。

**SLG 转译**
- 在玩家面对"战败分析/负面反馈"之前先做微型肯定，能降低防御、提高对复盘的接受度。
- 肯定的对象要是玩家自己认同的价值（"我是靠得住的队友""我在意公平"），不是系统给的头衔。
- 设计例：① 复盘入口前一步："本赛季你最自豪的一件事是？"（选项或一句话）；② 联盟档案展示每名成员的"本赛季角色"（侦察/后勤/前排），在战败后依然可见；③ 对被点名批评的指挥，先展示其历史贡献再进入问题讨论。

**边界**：效应对"受威胁群体"最明显，对未感到威胁者接近零；重复使用会失效；在游戏内做"价值写作"的接受度需测试。

### B3. 成长型思维（Growth Mindset）

**来源**
- Sisk, V. F., Burgoyne, A. P., Sun, J., Butler, J. L., & Macnamara, B. N. (2018). To what extent and under which circumstances are growth mind-sets important to academic achievement? Two meta-analyses. *Psychological Science, 29*(4), 549–571. — 经 Macnamara & Burgoyne (2022, *Psychological Bulletin*) 转述 https://englelab.gatech.edu/articles/2022/Macnamara%20and%20Burgoyne%20%282022%29%20-%20Do%20Growth%20Mindset%20Interventions%20Impact%20Students%E2%80%99%20Academic%20Achievement.pdf — 读取深度：**部分全文**。
- Yeager, D. S., et al. (2019). A national experiment reveals where a growth mindset improves achievement. *Nature, 573*, 364–369. https://www.nature.com/articles/s41586-019-1466-y ；UT Austin 新闻稿 https://news.utexas.edu/2019/08/07/a-growth-mindset-intervention-can-change-students-grades-if-school-culture-is-supportive/ — 读取深度：**摘要 + 新闻稿全文**。

**核心发现**
- Sisk 2018：干预对成绩的元分析效应 **d = 0.08**（95% CI 0.02–0.14）；操纵检验成功的研究反而无显著效应。Macnamara & Burgoyne 2022 在施加质量标准后效应不显著。
- Yeager 2019：12,000+ 名九年级学生、65 所学校、两次 25 分钟在线课程。**低成就学生核心课 GPA +0.10 分**（支持性学校环境中 +0.15–0.17）；低成就学生 D/F 均分比例下降 >5 个百分点；选修高阶数学 +3 个百分点。**效应依赖同伴规范**：当同伴文化支持挑战时才成立。

**SLG 转译**
- "成长型"信息只能作为辅助文案，并且必须有"环境支持"——联盟里真的有人示范"输了之后改进"，否则就是空话。
- 用在"无望"状态时，要把"能力可发展"落实为"这赛季我们哪项数据比上赛季好"，否则不可信。
- 设计例：① 联盟层面的"赛季进步曲线"（集结速度、响应率）替代个人成长口号；② 只在存在同伴示范（老玩家复盘视频）时推送成长信息；③ 不做"你一定能行"的弹窗。

**边界**：小效应、强调节；对高成就者基本无效；对成年竞技玩家的证据缺失。

### B4. 表达性写作（Expressive Writing / Experimental Disclosure）

**来源**
- Frattaroli, J. (2006). Experimental disclosure and its moderators: A meta-analysis. *Psychological Bulletin, 132*(6), 823–865. https://pubmed.ncbi.nlm.nih.gov/17073523 — 读取深度：**摘要**；调节变量经 PMC3830620 转述 — **二手**。

**核心发现**
- 146 项随机研究，总体 **r = .075**（d ≈ .15，小但显著）。调节（2026-09-23 复核全文，多为边缘显著或只在单项结局上成立）：≥3 次写作 r = .082 vs <3 次 .040（边缘）；有躯体健康问题的样本只在"自报健康"上更大（.131 vs .054）；创伤/应激史样本只在"主观影响"上边缘更大；随访 <1 个月的心理健康效应更大（.110 vs .035，显著），总体效应仅边缘。
- "健康大学生样本中 38 项只有 6 项显著"出自 Niles 等 2014（*Anxiety, Stress & Coping* 27(1):1–17）对 Frattaroli 所收研究的统计，不是 Frattaroli 原文。
- 时机（专家指导）：Pennebaker & Chung（2007 章节；2011 *Oxford Handbook of Health Psychology*）：事件后数小时到数天内，否认、分心、拉开距离可能是健康的；"we now encourage clinicians to delay their use of expressive writing until at least 1–2 months after an upheaval or until they think their patient is thinking 'too much' about the event"。[章节预印本](https://c3po.media.mit.edu/wp-content/uploads/sites/45/2016/01/PennebakerChung_FriedmanChapter.pdf)（全文）

**SLG 转译**
- 赛季结束后的"赛季日记/给下赛季自己的信"可作为轻量意义建构工具，但效应小，不宜作为主力。
- 多次写作只比单次略好（边缘显著），不值得为凑次数打扰玩家；写作的主要位置是**季末**，而不是战败后。
- 时机：Pennebaker 建议事件后至少 1–2 个月，或当事人明显"想得太多"时。对应 SLG：赛季末或跨季，或针对战败后数周仍在反复提及的人（特质调节器 R1 反刍）。
- 设计例：① 赛季终"给下赛季的自己"3 段式引导（发生了什么/我学到什么/下次怎么做），不公开；② 指挥的"战术日志"作为 AR + 写作的结合体；③ 不在战败后一周内推送写作任务。

### B5. 意义建构与获益发现

**来源**
- Park, C. L. (2010). Making sense of the meaning literature: An integrative review of meaning making and its effects on adjustment to stressful life events. *Psychological Bulletin, 136*(2), 257–301. https://pubmed.ncbi.nlm.nih.gov/20192563/ — 读取深度：**摘要**。
- Helgeson, V. S., Reynolds, K. A., & Tomich, P. L. (2006). A meta-analytic review of benefit finding and growth. *Journal of Consulting and Clinical Psychology, 74*(5), 797–816. https://psycnet.apa.org/record/2006-13014-002 — 读取深度：**摘要**。

**核心发现**
- Park：区分 global meaning（信念/目标）与 situational meaning，以及 meaning-making efforts（努力）与 meaning made（结果）。经验规律：**"努力寻找意义"本身与更高痛苦相关，"找到意义"与适应相关**——即引导玩家反刍"为什么会输"而不给出可落地的解释，会加重痛苦。
- Helgeson 等（87 项横断研究）：获益发现与**更少抑郁、更多积极幸福感**相关，但也与**更多侵入性/回避性想法**相关；与焦虑、总体痛苦、主观躯体健康、生活质量无关。摘要确认"距应激源的时间"是调节变量；二手资料（Tran 等 2011；Cassidy 2014 引原文 p.809）称时间越长积极关联越明显、与侵入性想法的关联越弱。原笔记的"≥2 年"阈值未能在原文核到，已删除。

**SLG 转译**
- 帮玩家"找到意义"而非"寻找意义"：由系统/盟主给出可信的叙事（"我们用三分之一的战力拖住对手 5 天，让友盟拿下 X"），而不是问"你觉得这次输了有什么意义"。
- 获益发现要延后（战败后 3–7 天）、要具体（数据支撑），并接受它伴随一些反刍。
- 设计例：① 战败后 72 小时生成"本场我们做到的三件事"（数据可核）；② 赛季末"联盟史"页面把战败写成情节而非结局；③ 不在战败当天推"失败是成功之母"类文案。

### B6. 仪式与丧失

**来源**
- Norton, M. I., & Gino, F. (2014). Rituals alleviate grieving for loved ones, lovers, and lotteries. *Journal of Experimental Psychology: General, 143*(1), 266–272. https://www.hbs.edu/ris/Publication%20Files/norton%20gino%202014_e44eb177-f8f4-4f0d-a458-625c1268b391.pdf — 读取深度：**部分全文**。
- Hobson, N. M., Schroeder, J., Risen, J. L., Xygalatas, D., & Inzlicht, M. (2018). The psychology of rituals: An integrative review and process-based framework. *Personality and Social Psychology Review, 22*(3), 260–284. https://osf.io/preprints/psyarxiv/98v3f_v1 — 读取深度：**摘要**。

**核心发现**
- Norton & Gino 3 实验：回忆过去的丧失仪式、或在实验室丧失（抽奖输掉 $200）后执行新编仪式，均降低悲伤；**机制是恢复控制感**（中介），且**不信仪式的人同样受益**；效应来自"做动作"而非"知道别人在做"。实验 3（n≈100）：仪式组控制感 3.35 vs 2.67（p=.002），悲伤 2.95 vs 4.07（p=.001）。
- Hobson 等：仪式的三个调节功能——情绪、绩效目标状态、社会联结；与习惯的区别在于刚性重复 + 象征意义；仪式可减少焦虑并把注意力导向任务。

**SLG 转译**
- 战败/赛季终需要"结束仪式"：集体、可执行、有固定动作（降旗、点名、把本赛季旗帜存入联盟史），恢复控制感。
- 小型个人仪式：战败后的"整军"三步（修城、补兵、签到）本身可以仪式化（固定顺序、固定反馈）。
- 设计例：① 赛季终"退旗仪式"——盟主点名每名成员的角色，成员按一次确认；② 战败后"守夜"（集体在线 10 分钟，只做防御动作）；③ 联盟纪念碑/史册，把战败也写进去。

**边界**：Hobson 指出新仪式可能引发群际偏见（Hobson et al. 2017）——战败仪式如果强化"对面是敌人"，会把愤怒外化为跨盟骚扰。

### B7. 希望理论（Agency + Pathways）

**来源**
- Snyder, C. R. (2002). Hope theory: Rainbows in the mind. *Psychological Inquiry, 13*(4), 249–275. https://www.tcpea.org/uploads/1/5/6/2/15622000/copy_of_hope_theory_rainbows_snyder_2002.pdf — 读取深度：**部分全文**。
- Weis, R., & Speridakos, E. C. (2011). A meta-analysis of hope enhancement strategies in clinical and community settings. *Psychology of Well-Being, 1*:5. https://psywb.springeropen.com/articles/10.1186/2211-1522-1-5 — 读取深度：**摘要 + 部分全文**。
- Corrigan et al. (2023). Hope dimensions (agency/pathways) 与抑郁/焦虑的元分析. *Int J Applied Positive Psychology*. https://link.springer.com/article/10.1007/s41042-023-00099-1 — 读取深度：**摘要**。

**核心发现**
- 希望 = 目标导向的意志（agency）+ 路径（pathways）。Snyder 引用 Barker 等对心理治疗元分析的重析：agency 0.47 SD，pathways 0.55 SD（"叠加"约 1.02 SD——此为作者对治疗共同因素的解释，不是希望干预的效应）。
- 相关：agency 与抑郁 r = −.39、pathways −.33（50 个样本，N=11,081）；与焦虑 −.26 / −.21。
- **干预元分析（27 项研究，N=2,154）：对希望与生活满意度只有小效应，对心理痛苦无总体效应**；调节变量（个体/团体、是否手册化、单次/多次）均不影响。

**SLG 转译**
- 与其"给希望"，不如"给路径"：战败后 24 小时内提供 2–3 条可执行的具体路线（守住 X 城→联合 Y 盟→争 Z 资源州），每条带里程碑。
- agency 由"小胜利"提供（Hobfoll 拆小），pathways 由指挥/系统提供。
- 设计例：① "下一步"面板固定展示 3 条路径与各自的第一步；② 指挥端的"备选方案"功能——战败即弹出 B 计划模板；③ 不做"相信自己"类推送。

**边界**：希望干预对痛苦无效，意味着它不能替代情绪支持；只对"无望"状态中的"看不到路"部分有用。

### B8. 自我慈悲与改进动机

**来源**
- Breines, J. G., & Chen, S. (2012). Self-compassion increases self-improvement motivation. *Personality and Social Psychology Bulletin, 38*(9), 1133–1143. https://static1.squarespace.com/static/50f6f441e4b08191027c661d/t/51663d46e4b060cd9194ed75/1365654854068/Breines+%26+Chen+2012+PSPB.pdf — 读取深度：**部分全文**。
- Neff, K. D. (2023). Self-compassion: Theory, method, research, and intervention. *Annual Review of Psychology*. https://self-compassion.org/wp-content/uploads/2022/08/PsychReviewInPress.pdf — 读取深度：**部分全文**。

**核心发现**
- 4 个实验：诱导自我慈悲（vs 自尊提升 vs 无指导）后，对个人弱点持更强的可塑信念、更愿意为过错道歉与不再重犯；**词汇测试失败后，自我慈悲组为第二次测试学习更久**（学习时长与成绩相关）。自我慈悲优于自尊提升。

**SLG 转译**
- 战败后对个人的反馈用"慈悲框架"：承认难受 + 人人都会犯这种错（共同人性）+ 指向下一步。这比"你很强，别在意"（自尊提升）更能促进改进。
- 设计例：① 指挥犯错后的系统提示："X% 的指挥在首次跨服战都遇到集结时差问题"（共同人性）+ "下次可用集结倒计时广播"（路径）；② 不用"MVP/垫底"式对比。

### B9. 向下社会比较与"别人也输了"

**来源**
- Wills, T. A. (1981). Downward comparison principles in social psychology. *Psychological Bulletin, 90*(2), 245–271. https://psycnet.apa.org/record/1981-30307-001 — 读取深度：**摘要**。
- Snyder, C. R., Lassegard, M., & Ford, C. E. (1986). Distancing after group success and failure: Basking in reflected glory and cutting off reflected failure. *Journal of Personality and Social Psychology, 51*(2), 382–388. https://psycnet.apa.org/record/1986-29969-001 — 读取深度：**摘要**（2026-09-23 复核，[academia.edu](https://www.academia.edu/101764692/Distancing_after_group_success_and_failure_Basking_in_reflected_glory_and_cutting_off_reflected_failure)）。

**核心发现**
- Wills：负性情绪下与"更不幸者"比较可提升主观幸福感（被动或主动）；该原理统一解释了恐惧-亲和、替罪羊、投射、偏见、敌意攻击、幽默等现象。
- Snyder 等 1986（复核后）：群体任务后随机给失败/无信息/成功反馈；失败组在自评疏离与行为指标（拿走、佩戴团队徽章的比例）上都比另两组更少与群体关联，**CORFing 得到可靠支持**；成功组的 BIRGing 只在行为指标上呈趋势、自评不显著。即**失败会驱动"与失败群体切割"**，而胜利带来的"沾光"弱得多——对应 SLG 的退盟/换服。

**SLG 转译**
- "别人也输了"作为安慰有一定效力（尤其对愤怒-外归因者：说明不是我们特别差），但要避免变成对他盟的嘲讽（群际敌意）与"大家都输所以无所谓"的价值贬损。
- 更要紧的是对抗 CORFing：战败后立刻提供"留在群体里的低成本身份收益"（专属称号、联盟史署名），降低切割动机。
- 设计例：① 赛季数据页展示"本赛季 X% 的联盟经历了至少一次主城失守"（常态化，不点名）；② 战败后联盟成员标识不降级、不摘除；③ 不在战败后展示"胜者盟的庆祝"给败者。

**边界**：向下比较对高自尊者作用小，且可能增加对"更不幸者"的敌意（Wills 明确指出与偏见相关）。

### B10. 感谢/认可与游戏内认可系统

**来源**
- Grant, A. M., & Gino, F. (2010). A little thanks goes a long way: Explaining why gratitude expressions motivate prosocial behavior. *Journal of Personality and Social Psychology, 98*(6), 946–955. https://faculty.wharton.upenn.edu/wp-content/uploads/2012/05/GrantGino_A-LitteThanks.pdf — 读取深度：**全文（pdftotext）**。
- Riot Honor 系统：Psychology of Games 2013 https://www.psychologyofgames.com/2013/01/modifying-player-behavior-in-league-of-legends-with-honor ；Jeffrey Lin 数据转述（Nature/Discourse）https://meta.discourse.org/t/measures-taken-against-bad-behaviour-in-league-of-legends/26084 ；ACM CSCW 2023 "Suspecting Sarcasm" https://dl.acm.org/doi/10.1145/3611020 — 读取深度：**二手/摘要**。
- Overwatch Endorsement：GDC 2019 报告转述 https://www.yahoo.com/entertainment/blizzard-reduced-toxic-behavior-overwatch-170059475.html — 读取深度：**二手**。

**核心发现**
- Grant & Gino 4 实验：一句书面感谢使再次帮助同一人的比例 **32%→66%**（N=69）、帮助第三方 **25%→55%**（N=57）；现场实验 41 名募捐员，主管一次当面感谢使次周自愿电话数 **增加 >50%**；中介是**社会价值感（被重视）而非自我效能**。
- Riot：Honor 上线后官方称积极行为上升（缺乏公开效应量）；Lin 报告"举报后 5–10 分钟内反馈，改正率 92%""排位言语毒性降 40%"——这些属于惩戒即时反馈，不是 Honor；2023 CSCW 质性研究中玩家几乎不提 Honor 的作用。
- Overwatch：Endorsement 上线后**"含破坏性行为的对局"下降 40%**，玩家对系统的信任度上升 130%（Blizzard 自报，无对照）。

**SLG 转译**
- 战败后 24 小时内由**具体的人**（盟主/指挥）对**具体的行为**（守了 6 小时、贡献了 X 资源）说谢谢，效果远大于系统群发"感谢参与"。
- 认可要指向"社会价值"（你对我们很重要）而不是"能力"（你很强）——后者在输了之后不可信。
- 设计例：① 战后"点名感谢"工具：指挥从战报勾选 5–10 个行为，一键生成个性化感谢并公开；② 盟友间"战后互赞"（每人 3 票，指向行为标签），累计成不随胜负变化的赛季荣誉；③ 官方在战败补偿邮件中引用本盟真实数据（"你们在 X 战中守了 14 小时"），而不是通稿。

**边界**：游戏公司自报数据无对照；Honor 类系统对"减少毒性"证据弱，对"提升留存"缺证据；感谢过频会贬值。

### B11. 近失效应（Near-miss）与伦理边界

**来源**
- Clark, L., Lawrence, A. J., Astley-Jones, F., & Gray, N. (2009). Gambling near-misses enhance motivation to gamble and recruit win-related brain circuitry. *Neuron, 61*(3), 481–490. https://pubmed.ncbi.nlm.nih.gov/19217383 — 读取深度：**摘要/二手**。
- 后续综述（J Gambling Studies 2025）https://link.springer.com/article/10.1007/s10899-025-10412-z — 读取深度：**二手**。

**核心发现**
- 近失（差一点赢）被评为比全失更不愉快，但**提高继续玩的欲望**，并激活纹状体/脑岛等赢相关回路；效应在玩家有"个人控制"（自己选的）时更强。后续研究：近失后下注更大、时长更长、更持久。

**SLG 转译**
- 战败结算若真实地是"险败"（差 3% 城防/差 2 分钟援军），如实呈现能维持动机；但**人为制造近失感**（把碾压局包装成惜败）属于赌博式操纵，且一旦被识破会摧毁可信度（违反 CERC "be right"）。
- 允许的做法：呈现真实的"最接近的时刻"并挂接具体路径（"下次援军早 2 分钟"）。
- 设计例：① 战报"转折点"仅在真实差距 <10% 时显示；② 绝不做"就差一点"的通用文案；③ 内部准则：近失呈现必须能被玩家从数据复核。

---

## C. 团队/组织层的恢复干预

### C1. 复盘 / After Action Review 的元分析

**来源**
- Tannenbaum, S. I., & Cerasoli, C. P. (2013). Do team and individual debriefs enhance performance? A meta-analysis. *Human Factors, 55*(1), 231–245. https://pubmed.ncbi.nlm.nih.gov/23516804/ — 读取深度：**摘要**；实践手册 Tannenbaum, *Using Debriefs* https://cdn.ymaws.com/www.odnetwork.org/resource/resmgr/2013_education/tannenbaum_using_debriefs_ha.pdf — 读取深度：**全文（pdftotext）**。
- Keiser, N. L., & Arthur, W., Jr. (2021). A meta-analysis of the effectiveness of the after-action review (or debrief) and factors that influence its effectiveness. *Journal of Applied Psychology, 106*(7), 1007–1032. https://www.ovid.com/journals/japsy/fulltext/10.1037/apl0000821~a-meta-analysis-of-the-effectiveness-of-the-after-action — 读取深度：**摘要**；Keiser & Arthur (2022) 任务/训练特征元分析 *J Business & Psychology* https://link.springer.com/article/10.1007/s10869-021-09784-x — 读取深度：**条目**。

**核心发现**
- Tannenbaum & Cerasoli：46 个样本（N=2,136），**d = 0.67，约 +25%**；团队与个体复盘均有效；有引导者的复盘更有效（但无引导者样本少，需谨慎）。定义要素：**反思近期经历、自己构建意义、在非惩罚环境中发现教训**。
- Keiser & Arthur 2021：61 项研究、107 个 d（915 个团队、3,499 人），**总体 d = 0.79**；**与个人或团队目标清晰对齐、用视频/文本等客观材料唤起记忆时更有效**；是否需要受训引导者证据不一。
- 实践要点（手册）：尽量接近事件发生时进行（但见下文体育证据）；描述为"学习机会"而非"批评"；**领导者先听团队再表态**（否则团队会顺从）；讨论 teamwork（沟通、求助、角色）而不只 taskwork；参与者越多受益越大；参与式优于指令式。反作用情形：被视为归责/惩罚、无引导、延迟过久、缺乏心理安全、被权威主导。

**SLG 转译**
- 这是本笔记中效应最大、证据最硬的干预，但前提是"学习导向 + 客观材料 + 参与式"。SLG 战报数据天然是"客观材料"，是最大优势。
- 时机：情绪热期过后（体育与 CISD 证据都指向"冷却后"），但不超过 48 小时。
- 设计例：① 系统生成"AAR 包"：时间线、集结响应率、关键节点回放，指挥只需主持；② 复盘模板固定四问（原计划/实际发生/为什么/下次怎么做），禁用"谁的责任"栏；③ 复盘产出直接变成下一场的"预案"，闭环到 B7 路径。

### C2. 体育：赛后沟通、团队韧性、集体效能

**来源**
- Morgan, P. B. C., Fletcher, D., & Sarkar, M. (2013). Defining and characterizing team resilience in elite sport. *Psychology of Sport and Exercise, 14*, 549–559. https://repository.lboro.ac.uk/articles/journal_contribution/Defining_and_characterizing_team_resilience_in_elite_sport/9621098/1 — 读取深度：**摘要**。
- Morgan, Fletcher & Sarkar (2015). Understanding team resilience in the world's best athletes: A case study of a rugby union World Cup winning team. *PSE, 16*, 91–100. https://www.sciencedirect.com/science/article/abs/pii/S1469029214001149 — 读取深度：**摘要**。
- Morgan, Fletcher & Sarkar (2019). Developing team resilience: A season-long study… *PSE, 45*. https://www.sciencedirect.com/science/article/abs/pii/S146902921830548X — 读取深度：**摘要**。
- AASP, Eight tips for communicating with adolescent athletes immediately after the game. https://appliedsportpsych.org/resources/resources-for-parents/eight-tips-for-communicating-with-adolescent-athletes-immediately-after-the-game-win-or-loss/ — 读取深度：**二手/专家指导**。
- McArdle, Martin, Lennon & Moore (2010). Exploring debriefing in sports: A qualitative perspective. *Journal of Applied Sport Psychology, 22*. — 读取深度：**未能读取正文**（仅条目）。另有 2026 年 APA PsycNet 记录 "Coaches' Communication Patterns After Wins and Losses"（2026-71458-001）— **未能读取**。
- Greenlees, Graydon & Maynard (2000). The impact of individual efficacy beliefs on group goal selection and group goal commitment. *J Sports Sciences*. https://pubmed.ncbi.nlm.nih.gov/10902680/ — 读取深度：**摘要（二手转述）**。

**核心发现**
- 团队韧性四特征（2013，焦点小组）：**群体结构、精熟取向（mastery approaches）、社会资本、集体效能**；五个心理社会过程（2015，世界杯冠军队）：**变革型领导、共享领导、团队学习、社会身份、积极情绪**；发展韧性的促成因素（2019，整赛季）：团队文化、乐趣、身份。
- 赛后沟通（专家共识）：赛后即刻不谈细节，运动员仍在情绪中；**先冷却，当晚或次日再复盘**；先问"你怎么看"再给意见。
- 集体效能可被反馈操纵：三人组自行车计时赛，收到伪造的"低集体效能"反馈的组从第 1 到第 2 次试验显著下调目标，高效能组维持目标。

**SLG 转译**
- 战败后最先修的是"精熟取向 + 集体效能"：把注意力放在"我们哪些流程做对了/可以做得更好"，而非结果；避免系统反馈把联盟标为"弱"（如战力排名骤降的醒目展示会直接压低集体效能与目标）。
- 共享领导：战败后让 2–3 名非盟主成员承担具体职能（外交/后勤/情报），既分散盟主的责任压力也提高参与。
- 设计例：① 战败后联盟战力/排名变化默认延迟 24 小时展示；② "职能委任"面板；③ 赛季中固定"团队学习"节点（每周一次 AAR），不只在战败后。

**边界**：Morgan 系列是质性研究，无效应量；集体效能实验是小样本实验室任务。

### C3. 军事：任务凝聚 vs 社会凝聚、初级群体、士气

**来源**
- MacCoun, R. J., & Hix, W. M. (2010). Unit cohesion and military performance. In *Sexual Orientation and U.S. Military Personnel Policy: An Update of RAND's 1993 Study* (Ch. 5). https://www.law.berkeley.edu/archive/files/csls/Unit_Cohesion_and_Military_Performance_Ch5_MacCoun_Hix.pdf — 读取深度：**全文（pdftotext）**。
- MacCoun, R. J., Kier, E., & Belkin, A. (2006). Does social cohesion determine motivation in combat? An old question with an old answer. *Armed Forces & Society, 32*(4), 646–654. https://palmcenterlegacy.org/wp-content/uploads/2017/12/2006_0925-KierMacCounBelkin.pdf — 读取深度：**部分全文**。
- Siebold, G. L. (2007). The essence of military group cohesion. *Armed Forces & Society, 33*(2), 286–295. — 读取深度：**二手**。
- Shils, E. A., & Janowitz, M. (1948). Cohesion and disintegration in the Wehrmacht in World War II. *Public Opinion Quarterly, 12*(2), 280–315. https://academic.oup.com/poq/article-abstract/12/2/280/1910462 — 读取深度：**部分全文**（2026-09-23 复核，扫描件 pp.280–285）。
- Britt, T. W., & Dickinson, J. M. (2006). Morale during military operations: A positive psychology approach. In Britt, Castro & Adler (Eds.), *Military Life* (Vol. 1). — 读取深度：**二手**（经 sjms.nu 与 PubMed 38075467 转述）。

**核心发现**
- Mullen & Copper 1994（66 个相关、49 项研究，含 10 项军事）：凝聚-绩效相关**主要由"对任务的承诺"驱动**；任务凝聚 r ≈ .43 vs 社会凝聚 .27（Beal 2003：.25 vs .17）；**控制任务凝聚后社会凝聚无独立效应**；**绩效→凝聚的路径比凝聚→绩效更强更可靠**——"表现好的群体变得更凝聚，经历失败的群体变得更不凝聚"。社会凝聚高而任务凝聚低时可能出现"clubbiness"、群体思维等负效应。
- Siebold：标准模型 = 水平（同伴）+ 垂直（领导）+ 组织 + 制度四层；领导是初级群体与组织层之间的枢纽。
- Shils & Janowitz（复核后）：士兵抵抗能力取决于初级群体避免解体的能力；初级群体满足"basic organic needs"并给予"affection and esteem"；因隔断、失去领导、人员耗损、补给中断而瓦解后，抵抗很少；诉诸政治伦理的宣传"mainly unsuccessful"，诉诸人身生存的较有效。北非 443 名战俘中德国人 29% 为逃兵或潜在逃兵，53 名德籍逃兵只有 1 人给出政治动机。适用边界：数据只来自西线/北非；Bartov《Hitler's Army》(1991) 认为东线初级群体被高伤亡摧毁，意识形态起主要作用。
- Britt & Dickinson：士气 = 参与群体规定活动的热情与坚持；六项量表（动机、士气、能量、驱动、热情、渴望），以当前任务为参照；**由"有意义的工作 + 对单位和领导有效性的信心"预测，而不是由痛苦程度预测**。

**SLG 转译**
- 战败是"绩效→凝聚"的负向冲击；对策不是搞社交活动（社会凝聚），而是**迅速重建任务承诺**：一个明确、可达、需要协作的下一目标。
- 士气公式：有意义的任务 + 对指挥/联盟有效性的信心。后者靠 C1 的 AAR 与 C4 的领导者说明来修复。
- 初级群体（小队/军团）是留存单元：战败后保持小队完整（不打散重组），并保证小队内部的联系。
- 设计例：① 战败后 24 小时内发布"下一个需要 20 人协作的目标"；② 小队制不因战败重排；③ 联盟"有效性证据"面板（我们过去 7 天完成了什么），用于对冲无望。

**边界**：军事凝聚研究多为相关设计；SLG 联盟成员的退出成本远低于军队，"初级群体"效力可能更弱、也更容易被"换盟"替代。

### C4. 信任修复与领导者的公开说明（account giving）

**来源**
- Kim, P. H., Ferrin, D. L., Cooper, C. D., & Dirks, K. T. (2004). Removing the shadow of suspicion: The effects of apology versus denial for repairing competence- versus integrity-based trust violations. *Journal of Applied Psychology, 89*(1), 104–118. https://psycnet.apa.org/record/2004-10572-008 — 读取深度：**摘要**。
- Dirks, K. T., Lewicki, R. J., & Zaheer, A. (2009). Repairing relationships within and between organizations: Building a conceptual foundation. *Academy of Management Review, 34*(1), 68–84. https://dx.doi.org/10.5465/amr.2009.35713285 — 读取深度：**摘要**（概念框架，无效应量）。
- Lewicki, R. J., Polin, B., & Lount, R. B. (2016). An exploration of the structure of effective apologies. *Negotiation and Conflict Management Research, 9*(2), 177–196. — APS 转述 https://www.psychologicalscience.org/news/minds-business/effective-apologies-include-six-elements.html — 读取深度：**二手**（Study 1 N=333）。
- Frantz & Bennigson 2005（见 A4）。

**核心发现**
- Kim 等：**能力型违背 → 道歉更有效；诚信型违背 → 否认更有效**（道歉等于承认不诚实）；若后续证据证明有罪，道歉更好；证明无辜，否认更好。
- Lewicki 等六要素：表达悔意、解释、**承认责任**、悔改声明、**修复提议**、请求原谅；要素越多越有效，其中承认责任最重要、修复提议次之，请求原谅最不重要。
- Frantz & Bennigson：延后道歉更有效（先被听见）。

**SLG 转译**
- 盟主/指挥的战后说明要先判断违背类型：**指挥失误 = 能力型 → 公开道歉 + 解释 + 修复提议（下次方案）**；**"卖队友/私吞资源"指控 = 诚信型 → 不能靠道歉，需要证据（日志）或明确否认 + 第三方核查**。
- 官方对"判定不公"的指控同样是诚信型：道歉式补偿会被读作承认偏袒，正确做法是公开判定依据。
- 说明的时机：在玩家反馈窗口之后。
- 设计例：① 盟主"战后说明"模板按六要素分段，去掉"请求原谅"；② 联盟资源流水/指挥操作日志可导出，用于诚信型争议的证据化；③ 官方争议判定附"依据 + 可复核数据"，不附"补偿作为歉意"。

### C5. 程序公正 / 发声效应对补偿分配的意义

**来源**
- Brockner, J., & Wiesenfeld, B. M. (1996). An integrative framework for explaining reactions to decisions: Interactive effects of outcomes and procedures. *Psychological Bulletin, 120*(2), 189–208. https://business.columbia.edu/sites/default/files-efs/pubfiles/405/Brockner_ReactionsToDecisions.pdf — 读取深度：**部分全文**。
- Lind, E. A., & Tyler, T. R. (1988). *The Social Psychology of Procedural Justice*. Plenum. — 读取深度：**二手**。
- van den Bos, K. (2001). Uncertainty management: The influence of uncertainty salience on reactions to perceived procedural fairness. *JPSP*. https://www.researchgate.net/publication/11926563 ；van den Bos & Spruijt (2002). Appropriateness of decisions as a moderator of the psychology of voice. *EJSP*. https://onlinelibrary.wiley.com/doi/10.1002/ejsp.61 — 读取深度：**摘要**。

**核心发现**
- **45 个独立样本：结果越不利，程序公正对反应的影响越大**（反之亦然）。人们在结果不利时进入"意义寻求"模式，此时程序信息最有分量。
- 发声效应：有机会表达意见 → 对程序与结果的评价更正面；在不确定性凸显时公正判断的作用更大（uncertainty management）；**发声若被认为不恰当/无实质影响则效应减弱**（2002 调节研究）——经典的"frustration effect"风险。

**SLG 转译**
- 战败补偿的"多少"不如"怎么分、谁说了算、能否申诉"重要——尤其是结果不利时。补偿分配规则公开、可预期、有申诉路径，比补偿加码更能压住愤怒。
- 发声必须有实质出口：投票决定补偿投向、指挥人选、下赛季方向，且结果要回馈"你的意见如何被采纳"。
- 设计例：① 联盟补偿分配采用事先公示的规则（贡献权重）+ 一次盟内投票；② 官方争议判定的申诉通道有时限承诺与结果公示；③ 每次征集意见后发布"采纳/未采纳及原因"。

### C6. 心理安全的建立行为（Edmondson）

**来源**
- Edmondson, A. C. (2019). *The Fearless Organization*. Wiley；框架整理 https://umbrex.com/resources/frameworks/organization-frameworks/psychological-safety-framework-edmondson/ — 读取深度：**二手**。

**核心发现（领导行为清单）**
1. **设定舞台/框定工作**：把工作定义为"学习挑战"，说明不确定性与相互依赖、"为何重要、对谁重要"。
2. **承认自身可错**："我可能漏掉什么，看到问题请说。"
3. **邀请参与**：提出自己不知道答案的真问题；决策前有结构化的输入机会；让安静者发声。
4. **建设性回应**：感谢 + 去污名化失败 + 对明确违规予以制裁；**对第一个提出问题/承认错误者的回应决定了所有旁观者学到什么**。

**SLG 转译**
- 战败后盟主的第一段话决定复盘能否诚实：承认自己的失误（可错性）→ 邀请指出问题 → 感谢第一个说话的人。
- 对第一个在复盘里说"其实是我集结晚了"的成员，公开感谢而不是追责，会打开信息流。
- 设计例：① 复盘频道置顶"盟主自评"栏先于成员发言；② "首个反馈者"自动获得联盟贡献；③ 对明确违规（内鬼、辱骂）的处理与失误分开公示，避免混淆"犯错"与"违规"。

---

## D. 玩家隔离与宣泄相关证据（"隔离"到底隔什么）

### D1. 宣泄不减少愤怒，反刍增加攻击

- Bushman, B. J. (2002). Does venting anger feed or extinguish the flame? Catharsis, rumination, distraction, anger, and aggressive responding. *PSPB, 28*(6), 724–731. https://journals.sagepub.com/doi/10.1177/0146167202289002 — 读取深度：**全文**（2026-09-23 复核 https://websites.umich.edu/~bbushman/PSPB02.pdf）。
- N = 600（招募 602，剔除 2），三组各 200。被激怒后：打沙袋并想着激怒者（反刍）→ 愤怒高于分心组（d = 0.22）和对照组（d = 0.31），攻击（噪音强度+时长）高于对照组（d = 0.30）；打沙袋并想健身（分心）的攻击居中，与两组差异均不显著；**什么都不做的对照组愤怒与攻击最低**。"发泄区/吐槽区"是反刍装置。

**SLG 转译**：不设"战后吐槽频道"作为情绪出口；提供分心型/任务型出口（修城小任务、副本），或干脆"什么都不做"（安静期）。

### D2. 情绪在群体中传染

- Barsade, S. G. (2002). The ripple effect: Emotional contagion and its influence on group behavior. *Administrative Science Quarterly, 47*(4), 644–675. https://journals.sagepub.com/doi/10.2307/3094912 — 读取深度：**摘要**。
- 训练同伙在小组决策中演出情绪，观察者与自评均检出传染；**正性传染提升合作、降低冲突、提高绩效感知**。

**SLG 转译**：战败后全盟语音/频道是传染通道。"隔离"的正确对象是**高唤醒的负性表达源**（少数人）与**渠道**（全服喊话），不是把难过的玩家隔开；同时让稳定的核心成员在场（正性源）。设计例：① 战后 2 小时联盟频道"冷却模式"（发言间隔、无表情刷屏）；② 指挥/核心成员优先在线的"值守"；③ 对反复煽动退盟者的临时禁言由盟主而非系统执行，并说明理由（程序公正）。

### D3. 与失败群体切割（CORFing）与倾诉的双面性

- Snyder, Lassegard & Ford 1986（见 B9）；Nils & Rimé 2012（见 A4）；Zech & Rimé (2005). Is talking about an emotional experience helpful? *Clinical Psychology & Psychotherapy, 12*(4), 270–287, doi:10.1002/cpp.460 — **摘要**（2026-09-23 复核）：两项实验；被分配谈论情绪经历者在第 3 天、第 7 天和 2 个月时的情绪恢复都不优于对照（只谈事实、谈其他事件、谈琐事、不谈）；但报告了更多主观益处（二手转述为"帮助感与释然感"）。
- 含义：让玩家"抱团倾诉"能提高亲近感与留存倾向（社会整合），但不会消化失败；要配认知重构（AAR、AR）才能恢复。

---

## E. 综合产出

### E1. 证据表

| # | 干预机制 | 原始证据（样本/效应量） | 适用状态 | 适用时机 | SLG 设计转译（例） | 反作用风险 |
|---|---|---|---|---|---|---|
| 1 | 支持类型与可控性匹配 | Cutrona & Suhr 1992，60 人观察研究；仅信息支持检出匹配效应（limited support） | 全部（作为分诊规则） | 战败后 0–24h 决定"给建议还是给情绪" | 战报分"可改/不可改"两栏；不可控败局不推战术建议 | 不可控失败后给建议 = 暗示"你本可以" |
| 2 | 自主导向帮助 | 3 实验 N=677：依赖式帮助→推断施舍动机、接受意愿↓；Nadler 2002 理论 | 羞耻、被背叛、观望 | 补偿发放时（24–72h） | "重建令"由玩家选投向；互助任务化；文案去"救济" | 直接发资源被读作施舍；高需求时更敏感 |
| 3 | 自主支持语言（反抗拒） | Li & Shi 2026：高威胁语言→抗拒 r=.20；Rains 2013 K=20 N=4,942；Miller 2007 恢复自由后记（后续重复不稳定） | 愤怒-外归因 | 所有沟通 | 公告模板"三选一 + 选择权声明"；退盟不设道德化拦截 | 控制性语言→愤怒+反驳+回弹 |
| 4 | 情绪验证 → 认知重构 | Shenk & Fruzzetti 2011 N=60：无效化↑负情绪/心率/皮电；Nils & Rimé 2012：只有认知模式带来恢复 | 全部，尤其愤怒与羞耻 | 验证 0–2h；重构 24–48h | 系统消息"验证句 + 事实句"；留言板先于总结 | 纯"加油"= 无效化；纯共情 = 只暂时舒缓 |
| 5 | 延后道歉/说明 | Frantz & Bennigson 2005，2 研究 n=24/83：后置道歉更有效，中介"被听见" | 被背叛、愤怒 | 反馈窗口之后（12–48h） | 补偿公告引用玩家反馈；盟主说明在留言板之后 | 秒回道歉被读作公关 |
| 6 | 不做单次情绪晤谈 | Rose 2002 Cochrane：无效；1 年 PTSD OR 2.51 | 全部 | 永不（尤其 0–72h） | 复盘频道去情绪模板；允许不复盘 | 强制重述失败↑唤醒 |
| 7 | Hobfoll 五要素 / 拆小 | 专家共识 + 领域证据；PFA 无 RCT | 耗竭、无望 | 0–72h | 保护期折叠喊话；三件小事清单；值守联结点 | 堆活动、逼参与 |
| 8 | CERC 六原则 | 最佳实践整合；400 篇综述 | 愤怒-外归因、观望 | 0–30min 首条；24h 完整 | 六句公告模板；判定依据 24h 公示；进度看板 | 信息真空→谣言 |
| 9 | 谣言控制（结构化不确定性） | DiFonzo & Bordia 2000 调查；Rosnow r=.48（焦虑-传播） | 观望、被背叛 | 0–24h 持续更新 | 决策时间表；官方状态标签；代理指挥 | "无可奉告"最差 |
| 10 | 归因再训练 | Lazowski & Hulleman 2016 d≈0.54；Hamm 2017 N=806 d=0.39 | 羞耻-内归因、无望 | 24–72h | "三个可改变量"卡；归因模板禁人格归因 | 碾压局强推可控归因 = 责怪受害者 |
| 11 | 自我肯定 | Epton 2015：行为 d=.32、意图 .14、接受 .17（41 研究） | 羞耻、被点名批评者 | 复盘之前 | "最自豪的一件事"；成员角色档案 | 对无威胁者无效；重复失效 |
| 12 | 成长型思维信息 | Sisk 2018 d=0.08；Yeager 2019 N>12k 低成就 +0.10 GPA，依赖同伴规范 | 无望（辅助） | 1–7 天 | 联盟进步曲线；仅在有示范时推送 | 空口号；高成就者无效 |
| 13 | 表达性写作 | Frattaroli 2006 r=.075；≥3 次仅边缘更好 | 观望、赛季末 | 1–2 个月后、赛季末（Pennebaker & Chung） | "给下赛季的自己"三段式 | 即刻写作无益 |
| 14 | 意义建构/获益发现 | Park 2010：找到意义≠寻找意义；Helgeson 2006 87 研究：↓抑郁但↑侵入思维 | 观望、无望 | 3–7 天 | "本场做到的三件事"（可核数据）；联盟史 | 逼问"意义"→反刍 |
| 15 | 仪式 | Norton & Gino 2014 3 实验，控制感中介；不信也有效 | 观望、耗竭 | 24–72h；赛季末 | 退旗仪式；守夜；纪念碑 | 强化群际敌意 |
| 16 | 希望=路径 | Weis & Speridakos 2011 k=27 N=2,154：小效应，对痛苦无效 | 无望 | 24h 内给路径 | "下一步"三路径；B 计划模板 | "相信自己"推送 |
| 17 | 自我慈悲框架 | Breines & Chen 2012 4 实验：失败后学习更久，优于自尊提升 | 羞耻 | 24–72h | "X% 指挥也遇到" + 路径 | "你很强别在意"式自尊提升 |
| 18 | 向下比较 / 抗 CORFing | Wills 1981；Snyder 1986（摘要，仅 CORFing 显著） | 观望、愤怒 | 24–72h | 常态化统计；标识不降级；不展示胜者庆祝 | 变成嘲讽他盟、贬损价值 |
| 19 | 具体感谢 | Grant & Gino 2010：32→66%、25→55%、电话 +50%；中介社会价值 | 羞耻、耗竭、观望 | 2–24h | 指挥点名感谢工具；互赞荣誉 | 群发通稿；过频贬值 |
| 20 | 真实近失呈现 | Clark 2009：近失↑继续动机，需个人控制 | 无望 | 结算即刻 | 仅真实差距 <10% 显示转折点 | 人为近失 = 赌博式操纵，毁可信度 |
| 21 | 结构化 AAR | Tannenbaum 2013 46 样本 d=.67；Keiser & Arthur 2021 61 研究 d=.79；客观材料+目标对齐 | 全部（团队层） | 冷却后 12–48h | AAR 包；四问模板；产出变预案 | 归责式/权威主导/无引导/延迟过久 |
| 22 | 团队韧性要素 | Morgan 2013/2015/2019 质性 | 团队层 | 赛季持续 | 职能委任；每周团队学习节点 | 无 |
| 23 | 集体效能保护 | Greenlees 2000：低效能反馈→目标下调 | 无望 | 0–24h | 排名/战力变化延迟展示 | 醒目"变弱"反馈 |
| 24 | 任务凝聚优先 | Mullen & Copper 1994：任务 .43 vs 社会 .27；绩效→凝聚更强 | 观望、耗竭 | 24h 内 | 20 人协作目标；小队不重排 | 只搞社交活动；clubbiness |
| 25 | 士气两要素 | Britt & Dickinson 2006（二手） | 全部 | 持续 | 有效性证据面板 | — |
| 26 | 违背类型匹配的修复 | Kim 2004：能力型→道歉，诚信型→否认/证据 | 被背叛 | 反馈后 | 六要素说明；日志可导出；判定附依据 | 诚信型违背道歉了事；补偿当歉意 |
| 27 | 程序公正 + 发声 | Brockner & Wiesenfeld 1996 45 样本：结果差时程序效应更大；发声需实质 | 愤怒、被背叛 | 补偿分配时 | 公示规则 + 投票；申诉时限；采纳回执 | 黑箱；假发声（frustration effect） |
| 28 | 心理安全行为 | Edmondson（二手清单） | 团队层 | 复盘时 | 盟主自评先行；首个反馈者奖励 | 追责第一个说真话的人 |
| 29 | 不做宣泄区 | Bushman 2002：反刍↑攻击，不做最好 | 愤怒 | 0–24h | 分心/任务型出口；安静期 | 吐槽频道 = 反刍装置 |
| 30 | 隔离传染源与渠道 | Barsade 2002：情绪传染改变群体行为 | 愤怒（群体层） | 0–2h | 频道冷却模式；核心值守；盟主执行禁言并说明 | 把难过者隔开；系统无解释禁言 |

### E2. "不要做"清单（有证据的反作用）

1. **不做强制/集体的单次"情绪复盘"**（Rose 2002：OR 2.51；Hobfoll 2007 明确不推荐）。
2. **不设"发泄/吐槽区"当情绪出口**（Bushman 2002：反刍组最愤怒最具攻击性；不做最好）。
3. **不用无效化式安慰**："别想了""这有什么""下赛季再来"（Shenk & Fruzzetti 2011：↑负情绪、心率、皮电）。
4. **不用控制性语言动员**："必须""立刻""否则"（Rains 2013；Miller 2007）。
5. **不做依赖导向的"救济式"补偿与文案**（Nadler；2024 三实验：被读作施舍、接受意愿↓）。
6. **不秒回道歉、不在玩家发声前发通稿**（Frantz & Bennigson 2005）。
7. **不"无可奉告"、不留信息真空**（DiFonzo & Bordia 2000；Hobfoll）。
8. **不把社交活动当凝聚解药**（Mullen & Copper：社会凝聚无独立效应；高社交低任务更糟）。
9. **不用成长型/希望口号做主力**（Sisk d=0.08；Weis 对痛苦无效）。
10. **诚信型背叛不让当事人"道歉了事"**（Kim 2004：道歉坐实不诚实）。
11. **不人为制造"就差一点"**（Clark 2009 近失机制 = 赌博式；违反 be right）。
12. **不做归责式、权威主导、无客观材料的复盘**（Tannenbaum 手册反作用条件；Keiser & Arthur 对齐/客观材料调节）。
13. **耗竭期不堆新活动、不逼参与**（Hobfoll calming）。
14. **补偿分配不黑箱、不做假发声**（Brockner & Wiesenfeld；van den Bos 2002 恰当性调节）。
15. **不在战败后醒目展示排名骤降/"变弱"反馈**（Greenlees 2000：低效能反馈→目标下调）。
16. **不追责第一个承认错误的人**（Edmondson）。
17. **不把"别人也输了"做成对他盟的嘲讽**（Wills：向下比较与偏见/敌意相关；Hobson：仪式可增群际偏见）。

### E3. 时机窗口的证据小结

| 窗口 | 该做 | 不该做 | 证据依据 |
|---|---|---|---|
| **0–30 分钟** | 官方/盟主首条"我们知道了 + 何时给完整说明"；结算页只有验证句 + 事实句；真实近失点（若有） | 复盘、说教、劝慰文案、补偿承诺、展示胜者庆祝、排名骤降动画 | CERC be first；Shenk & Fruzzetti；Greenlees |
| **30 分钟–2 小时** | 频道冷却模式；核心成员值守；保护期折叠跨盟喊话；三件 10 分钟小事 | 吐槽频道；全员语音；追责 | Barsade；Bushman；Hobfoll 拆小 |
| **2–24 小时** | 具体的人对具体行为的感谢；留言板/意见征集开放；谣言的时间表与指导价值；"下一步"三路径 | 盟主长篇总结；系统群发感谢；直接发救济 | Grant & Gino；DiFonzo & Bordia；Snyder 路径；Nadler |
| **12–48 小时（冷却后）** | 结构化 AAR（学习导向、客观战报、四问模板、盟主自评先行、首个反馈者受谢）；盟主/官方说明（六要素，按违背类型）；补偿规则公示 + 投票 | 归责式复盘；诚信型争议靠道歉；黑箱分配 | Tannenbaum；Keiser & Arthur；Edmondson；Kim；Lewicki；Frantz；Brockner |
| **24–72 小时** | 归因再训练式反馈（可改变量）；自我慈悲框架；仪式（退旗/守夜）；标识不降级；补偿以"重建工具"形式发放 | 碾压局强推可控归因；人为近失 | AR 元分析；Breines & Chen；Norton & Gino；Nadler |
| **3–7 天** | 获益发现与联盟叙事（可核数据）；常态化统计（"X% 联盟经历失守"）；20 人协作的新目标；职能委任 | 逼问意义；社交活动替代任务 | Park；Helgeson；Mullen & Copper；Morgan |
| **1–4 周 / 赛季末** | 表达性写作（赛季末一次性三段式；战败 1–2 个月后）；联盟史；成长信息（有示范时）；信任修复评估 | 口号推送 | Frattaroli；Yeager 2019 环境条件 |

**总原则**：先"安全-平静-信息"，再"认可-联结"，再"复盘-路径"，最后"意义-仪式-成长"。情绪支持早、认知支持稍后、意义支持最后；官方信息永远最早。

---

## F. 未找到 / 未能读取 / 待核清单

- Cutrona & Suhr 1992：只读到摘要，未见各类支持的具体统计量。
- Snyder, Lassegard & Ford 1986：2026-09-23 已复核摘要（见 B9）；各条件徽章比例未取到原表。
- Shils & Janowitz 1948：2026-09-23 已复核部分全文（见 D2）。
- Siebold 2007、Britt & Dickinson 2006、Lind & Tyler 1988、Edmondson 清单、Lazowski & Hulleman 2016：二手转述。
- McArdle et al. 2010（体育复盘质性研究）与 2026 年 "Coaches' Communication Patterns After Wins and Losses"：未能读取正文；赛后"先冷却"目前只有专家指导（AASP）支撑。
- Frattaroli 2006 调节变量：2026-09-23 已复核全文（见 B4）。Helgeson 2006 的时间调节：方向经二手确认，具体阈值未读到原文。
- Bushman 2002（全文）、Zech & Rimé 2005（摘要）：2026-09-23 已复核。
- "Toxic positivity"：未找到高质量实验研究，只能借用无效化与情绪抑制文献。
- Riot Honor 系统对留存/情绪的定量效果：未找到公开数据；Overwatch 40% 为公司自报无对照。
- 直接针对"游戏团队战败后心理干预"的实验研究：未找到。

---

## G. 参考来源汇总（作者/年份/标题/出处/URL/读取深度）

A 块：Cutrona & Russell 1990（Wiley 章节，二手）；Cutrona & Suhr 1992（Communication Research，摘要）https://journals.sagepub.com/doi/10.1177/009365092019002002 ；Nadler 2002（JOSI，部分全文）https://www.humiliationstudies.org/documents/NadlerIntergroupHelping.pdf ；Fisher, Nadler & Whitcher-Alagna 1982（Psych Bull，摘要）https://cris.tau.ac.il/en/publications/recipient-reactions-to-aid-2 ；PMC11590873 2024（部分全文）https://pmc.ncbi.nlm.nih.gov/articles/PMC11590873 ；Rains 2013（HCR，摘要）https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1468-2958.2012.01443.x ；Miller et al. 2007（HCR，摘要）https://eric.ed.gov?id=EJ755929 ；Reynolds-Tylus 2019（Frontiers，部分全文）https://www.frontiersin.org/journals/communication/articles/10.3389/fcomm.2019.00056/full ；Shenk & Fruzzetti 2011（JSCP，摘要）https://pure.psu.edu/en/publications/the-impact-of-validating-and-invalidating-responses-on-emotional- ；Nils & Rimé 2012（EJSP，摘要）https://www.academia.edu/107375960 ；Frantz & Bennigson 2005（JESP，摘要）https://www.sciencedirect.com/science/article/pii/S0022103104001167 ；Rose et al. 2002（Cochrane，摘要含数据）https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD000560/full ；Hobfoll et al. 2007（Psychiatry，部分全文）https://escholarship.org/content/qt0983p74m/qt0983p74m_noSplash_fce93e11f427f11a5e7a9a9200b57141.pdf ；Fox et al. 2012 / Dieltjens et al. 2014 / PMC10624106 2023（PFA 综述，摘要）；Reynolds & Seeger 2005（JHC，二手）https://www.researchgate.net/publication/7970925 ；Miller et al. CERC 系统综述（JICRCR，部分全文）https://jicrcr.com/index.php/jicrcr/article/download/38/39 ；DiFonzo & Bordia 2007（APA，摘要）https://psycnet.apa.org/record/2006-13469-003 ；DiFonzo & Bordia 2000（PRR，要点）https://www.academia.edu/3437287 。

B 块：Hamm et al. 2017（Motiv Emot 预印本，部分全文）https://centaur.reading.ac.uk/72219/ ；Lazowski & Hulleman 2016（RER，二手）；Cohen & Sherman 2014（Annu Rev Psychol，部分全文）https://ed.stanford.edu/sites/default/files/annurev-psych-psychology_of_change_final_e2.pdf ；Epton et al. 2015（Health Psychol，摘要）https://research.manchester.ac.uk/en/publications/the-impact-of-self-affirmation-on-health-behavior-change-a-meta-a ；Sisk et al. 2018（Psych Sci，经 Macnamara & Burgoyne 2022 部分全文）；Yeager et al. 2019（Nature，摘要 + 新闻稿）https://www.nature.com/articles/s41586-019-1466-y ；Frattaroli 2006（Psych Bull，摘要）https://pubmed.ncbi.nlm.nih.gov/17073523 ；Park 2010（Psych Bull，摘要）https://pubmed.ncbi.nlm.nih.gov/20192563/ ；Helgeson et al. 2006（JCCP，摘要）https://psycnet.apa.org/record/2006-13014-002 ；Norton & Gino 2014（JEP:G，部分全文）https://www.hbs.edu/ris/Publication%20Files/norton%20gino%202014_e44eb177-f8f4-4f0d-a458-625c1268b391.pdf ；Hobson et al. 2018（PSPR，摘要）https://osf.io/preprints/psyarxiv/98v3f_v1 ；Snyder 2002（Psych Inquiry，部分全文）；Weis & Speridakos 2011（Psychol Well-Being，摘要+部分）https://psywb.springeropen.com/articles/10.1186/2211-1522-1-5 ；Corrigan et al. 2023（IJAPP，摘要）https://link.springer.com/article/10.1007/s41042-023-00099-1 ；Breines & Chen 2012（PSPB，部分全文）；Wills 1981（Psych Bull，摘要）https://psycnet.apa.org/record/1981-30307-001 ；Snyder, Lassegard & Ford 1986（JPSP，条目）https://psycnet.apa.org/record/1986-29969-001 ；Grant & Gino 2010（JPSP，全文）https://faculty.wharton.upenn.edu/wp-content/uploads/2012/05/GrantGino_A-LitteThanks.pdf ；Riot/Overwatch 报道（二手）；Clark et al. 2009（Neuron，摘要）https://pubmed.ncbi.nlm.nih.gov/19217383 。

C/D 块：Tannenbaum & Cerasoli 2013（Human Factors，摘要）https://pubmed.ncbi.nlm.nih.gov/23516804/ 与手册（全文）https://cdn.ymaws.com/www.odnetwork.org/resource/resmgr/2013_education/tannenbaum_using_debriefs_ha.pdf ；Keiser & Arthur 2021（JAP，摘要）；Morgan, Fletcher & Sarkar 2013/2015/2019（PSE，摘要）；Greenlees et al. 2000（JSS，摘要）https://pubmed.ncbi.nlm.nih.gov/10902680/ ；MacCoun & Hix 2010（RAND ch.5，全文）https://www.law.berkeley.edu/archive/files/csls/Unit_Cohesion_and_Military_Performance_Ch5_MacCoun_Hix.pdf ；MacCoun, Kier & Belkin 2006（AF&S，部分全文）；Siebold 2007（二手）；Shils & Janowitz 1948（POQ，条目）；Britt & Dickinson 2006（二手）；Kim et al. 2004（JAP，摘要）https://psycnet.apa.org/record/2004-10572-008 ；Dirks, Lewicki & Zaheer 2009（AMR，摘要）；Lewicki, Polin & Lount 2016（NCMR，二手）；Brockner & Wiesenfeld 1996（Psych Bull，部分全文）https://business.columbia.edu/sites/default/files-efs/pubfiles/405/Brockner_ReactionsToDecisions.pdf ；van den Bos 2001 / van den Bos & Spruijt 2002（摘要）；Edmondson 2019（二手）；Bushman 2002（PSPB，摘要）https://journals.sagepub.com/doi/10.1177/0146167202289002 ；Barsade 2002（ASQ，摘要）https://journals.sagepub.com/doi/10.2307/3094912 。
