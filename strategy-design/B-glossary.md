# 附录 B - 术语表与资料地图

> **本附录干什么用**：三件事。①一张中英对照的术语表，让你读英文资料、逛 BoardGameGeek（BGG）论坛、听设计播客时能对上号，也让你写设计分析时用词精确。②一张资料地图，告诉你每份资料讲什么、对应本课哪几章。③去哪里玩、去哪里找对手。
> **怎么用**：不要通读。术语表当字典查；资料地图在你想"接下来读点什么"时翻。
> **口径说明**：章节列链接到该术语**正式定义或讲解**的那一章；有的词在更早的章节顺带出现过，以定义处为准；首次定义之后另有一章深入讲解的，写成"首次章节（深入：某章）"。英文一栏写"本课用语"的，是本课为教学起的名字，不是通行术语，到英文资料里搜不到。社区术语的定义只采用编者核实过的来源（BGG 术语表、Wikipedia、League of Gamemakers），属于【行业口径】。

---

## 1. 中英对照术语表

**先看五对最容易混用的词**，它们在下面的表里各有条目：

| 容易混的一对 | 区别 |
|---|---|
| **完美信息** vs **完全信息** | 完美信息问"你知不知道已经发生了什么"；完全信息问"你知不知道每个人的收益"。石头剪刀布收益全公开（完全信息），出手时却看不见对手这一手（不完美信息）。两个维度互相独立，见[第 12 章](./12-information.md) |
| **路线** vs **完整策略** | 路线是一句压缩的倾向描述（"先攒两张便宜牌再冲分"）；完整策略要对每一个决策点都规定怎么做，包括永远走不到的分支。两个人打"同一条路线"，桌上的行为可以完全不同，见[第 15 章](./15-strategy-space.md) |
| **胜率** vs **期望分** | 两者都是期望，被平均的东西不同：胜率是"赢记 1、输记 0"的期望。门槛附近两者可以给出相反的选择，见[第 18 章](./18-luck-and-skill.md) |
| **打压领先者** vs **追赶机制** | 前者是**玩家**把攻击集中到领先者身上，成本要有人付；后者是**规则**给落后者资源或给领先者加价。见[第 13 章](./13-multiplayer-politics.md)、[第 20 章](./20-tension-arc.md) |
| **造王** vs **影响了胜负** | 造王要求行动者**已经赢不了**、又能决定别人谁赢；暂时末位但仍有获胜路径的人改变了胜负，不是造王。见[第 13 章](./13-multiplayer-politics.md) |

### 1.1 思考基础：扫描、推演与估值

| 中文 | 英文 | 一句话说明 | 章节 |
|---|---|---|---|
| 出声思考 | think-aloud | 一边想一边把念头原样说出或写下，包括"不知道""随便"；既是玩家的练习，也是设计师观察测试者的方法 | [00](./00-how-to-learn.md) |
| 后见之明偏差 | hindsight bias | 知道结果之后，高估自己当初预见到它的程度；"先写下决定再看答案"就是为了防它 | [00](./00-how-to-learn.md) |
| 策略 / 战术 | strategy / tactics | 第 01 章的直觉口径：策略是长期怎么赢的方向，战术是这一步怎么走；两者是不同时间尺度的思考 | [01](./01-what-is-strategy-game.md) |
| 谜题 | puzzle | 没有会回应的对手、解开即消耗的问题；本课用它和"对手就是内容"的游戏对照 | [01](./01-what-is-strategy-game.md) |
| 四问扫描 | 本课用语 | 轮到你时依次问：目标与距离、合法动作全集、威胁与机会、两个候选推一两步 | [02](./02-four-questions.md) |
| 双威胁 | double threat | 一步同时制造两个威胁，对手只能防一个 | [02](./02-four-questions.md) |
| 强制着 | 本课用语（forced move 的意思） | 一个动作摆出威胁，对手不应对就输，所以对手的下一步几乎确定；它让推演可以"免费"多走一步 | [02](./02-four-questions.md) |
| 一厢情愿的推演 | 本课用语 | 推演时给对手安排一个对自己方便的回应；纠正办法是默认对手走对他最好的一步 | [02](./02-four-questions.md) |
| 博弈树 | game tree | 从当前局面出发，把双方所有可能的走法一层层画出来的树 | [03](./03-game-trees.md) |
| 倒推 | backward induction | 从终局往回标结果，每个节点按轮到的人的利益取最好 | [03](./03-game-trees.md) |
| 必胜 / 必败局面 | winning / losing position | 必胜：存在一步把对手送进必败局面；必败：每一步都把对手送进必胜局面 | [03](./03-game-trees.md) |
| 极小化极大 | minimax | 两人零和（如只论胜负）时倒推的写法：我的节点取最大，对手的节点取最小。一般收益的博弈里，倒推是每个节点按轮到者自己的收益取最大，不能简化成"对手取我的最小" | [03](./03-game-trees.md)（深入：[11](./11-sequential-commitment.md)） |
| 记忆化 | memoization | 同一局面不管从哪条路到达，只算一次；"用表代替树"的原理 | [03](./03-game-trees.md) |
| 策略窃取论证 | strategy-stealing argument | 证明 Hex 先手存在必胜策略的论证：不可能平局、多一子永不有害时，后手若有必胜策略，先手可以"偷"来用。它不告诉你策略是什么 | [03](./03-game-trees.md) |
| 选择性搜索 | selective search | 只展开少数候选（剪宽度）、推到某层停下（剪深度），用估值代替后面的推演 | [03](./03-game-trees.md) |
| 地平线效应 | horizon effect | 截断点选在局面剧烈变化的地方，估值看不到紧接着要发生的坏事 | [03](./03-game-trees.md) |
| 估值 | evaluation | 对一个还不是终局的局面"对我大概多好"的快速估计；好估值要快、方向大致对、知道自己在哪里不准 | [04](./04-evaluation.md) |
| 期望 | expected value | 每种结果乘以它的概率再相加；它不告诉你波动，也不告诉你能否跨过门槛 | [04](./04-evaluation.md) |
| 子力价值 | piece values | 国际象棋兵 1、马象 3、车 5、后 9 的惯例分值【行业口径】，只在战术上平静的局面里可靠 | [04](./04-evaluation.md) |
| 战术上平静 | tactically quiet | 没有一串吃子或强制着正在进行的局面；静态估值只在这种局面里可靠 | [04](./04-evaluation.md) |
| 死局面 | dead position | 任何合法走法都不可能将死对方，判和【规则】；多出来的子力价值为零的典型例子 | [04](./04-evaluation.md) |
| 估值看期限 | 本课用语 | 持续性收益的价值 ≈ 每次的量 × 还能有用地工作的次数；期限常由对手共同决定 | [04](./04-evaluation.md) |
| 行动经济 | action economy | 把行动当成一局里最硬的预算，按每个行动换来多少去比较动作 | [05](./05-action-economy.md) |
| 保底动作 | 本课用语 | 总能做的那个动作（如《小集市》进货 2 币），定下一个行动的最低价 | [05](./05-action-economy.md) |
| 机会成本 | opportunity cost | 做一个选择的代价 = 被放弃的**最好的**另一个选择的价值，包括对手因此得到的东西 | [05](./05-action-economy.md) |
| 兑换率 | exchange rate | 把不同资源换成同一种货币的比率，可能写在规则里（卡坦港口），也可能藏在取整里（石器时代） | [05](./05-action-economy.md) |
| 引擎 / 冲分 | engine / cash out | 引擎是持续带来收益的投资；冲分是把资源换成分数；两者之间的切换点叫转折点 | [05](./05-action-economy.md) |
| 对手模型 | 本课用语 | 一份"如果局面是 X，他大概会做 Y"的说明：随机、固定习惯、理性、层级 | [06](./06-reading-opponents.md) |
| 层级思考 | level-k thinking | 第 0 层按锚点行动，第 k 层假设对手是第 k−1 层再应对；最好的层级取决于对手实际在哪一层 | [06](./06-reading-opponents.md) |
| Yomi 层级 | yomi layers | Sirlin 在《Playing to Win》第 7 章用的说法（読み，"读"）：你知道他会做什么是第 1 层，他知道你知道是第 2 层，依此类推 | [06](./06-reading-opponents.md) |
| 凯恩斯选美 | Keynesian beauty contest | 凯恩斯 1936 年的比喻：选的不是自己认为最美的，而是"一般意见认为一般意见会选的"；猜数实验常被视为它的实验版 | [06](./06-reading-opponents.md) |
| 路线承诺 | 本课用语 | 为一条路线付出效率、放弃灵活性，换取它的非线性收益 | [07](./07-planning-adapting.md) |
| 沉没成本 | sunk cost | 已经投入、收不回来的东西；它是状态，不是继续的理由 | [07](./07-planning-adapting.md) |
| 转型条件 | 本课用语 | 决定路线时事先写下的"出现什么情况就换路线"，配合一条退路 | [07](./07-planning-adapting.md) |
| 读信号 | reading signals | 从别人传来的牌、他拿走了什么、他多次购买的方向，推断他在走哪条路线 | [07](./07-planning-adapting.md) |
| 决策质量 vs 结果 | decision quality vs outcome | 好决定看当时的信息、目标和过程，不看结果；结果是噪声很大的信号 | [08](./08-review-and-thinkaloud.md) |
| 侥幸 / 运气不好 | 本课用语 | 四格表里的两格：坏决策 + 好结果（强化错误）；好决策 + 坏结果（动摇正确做法） | [08](./08-review-and-thinkaloud.md) |
| 错着分类 | 本课用语 | 规则不熟、计算错、估值错、读人错、计划错，以及"无错"；按这个顺序从最底层查起 | [08](./08-review-and-thinkaloud.md) |

### 1.2 博弈论：同时、混合与序贯

| 中文 | 英文 | 一句话说明 | 章节 |
|---|---|---|---|
| 收益矩阵 / 标准式 | payoff matrix / normal form | 把一个同时出手的瞬间写成表：行是你的动作，列是对手的，每格两人的收益 | [09](./09-simultaneous-games.md) |
| 严格占优 / 弱占优 | strictly / weakly dominant | 严格：对手怎么选都严格更好；弱：都不更差且至少一种情况更好 | [09](./09-simultaneous-games.md) |
| 重复剔除严格劣势策略 | iterated elimination of strictly dominated strategies | 反复划掉被严格占优的动作化简矩阵；前提是相信对手也理性 | [09](./09-simultaneous-games.md) |
| 纳什均衡 | Nash equilibrium | 任何一个玩家单方面改变选择都不能变得更好的一组选择；不等于最好的结果，也不等于预测 | [09](./09-simultaneous-games.md) |
| 划线法 | 本课用语 | 对每一列、每一行划出最好回应，两个数都被划线的格子是纯策略均衡 | [09](./09-simultaneous-games.md) |
| 囚徒困境 | prisoner's dilemma | 背叛对每人都占优，均衡却比双方合作差 | [09](./09-simultaneous-games.md) |
| 胆小鬼博弈 | chicken / hawk-dove | 两个纯策略均衡（一硬一软），问题是谁让 | [09](./09-simultaneous-games.md) |
| 猎鹿博弈 | stag hunt | 都合作和都单干都是均衡，合作需要信任对方不退缩 | [09](./09-simultaneous-games.md) |
| 性别战 | battle of the sexes | 双方都想协调到一起，但偏好不同的落点 | [09](./09-simultaneous-games.md) |
| 混合策略 | mixed strategy | 纯策略（具体动作）上的一个概率分布，按它随机选择。在混合均衡里，它的比例恰好让对手用到的每个动作期望相等（见无差异原理） | [10](./10-mixed-strategies.md) |
| 无差异原理 | indifference principle | 混合均衡里，你用到的每个动作对上对手的均衡混合期望都相等；所以你的比例由对手的收益决定 | [10](./10-mixed-strategies.md) |
| 诈唬 | bluff | 拿弱牌做出强牌的动作；在第 10 章的河牌模型里（单条街、下注额 b 给定、只有坚果和空气两类牌、对手只能跟或弃、无加注、空气足够多），诈唬应占下注范围的 b/(P+2b) | [10](./10-mixed-strategies.md) |
| 克制循环 | 本课用语 | A 克 B、B 克 C、C 克 A 的结构；三元循环里加强一个单位，变多的是它的克星 | [10](./10-mixed-strategies.md) |
| 支撑集 | support | 一个混合策略里概率为正的那些纯策略；常用来描述均衡策略用到了哪些动作 | [10](./10-mixed-strategies.md) |
| 序贯博弈 | sequential game | 后行动的人看得见先行动的人做了什么，可以画成树倒推 | [11](./11-sequential-commitment.md) |
| 不可信威胁 | incredible / non-credible threat | 真走到那一步时，执行它对威胁者自己不划算 | [11](./11-sequential-commitment.md) |
| 子博弈完美均衡 | subgame-perfect equilibrium（SPE） | 在每一个分支（子博弈）上都说得通的均衡，排除了藏在没走到的分支里的空威胁 | [11](./11-sequential-commitment.md) |
| 承诺 | commitment | 在较早时点主动限制自己较晚的选择，并让对手看得见、算得进去；价值来自对手回应的改变 | [11](./11-sequential-commitment.md) |
| 先手优势 | first-move advantage | 来自节奏、先挑、先表态三种来源；后手的反作用是信息 | [11](./11-sequential-commitment.md) |
| 贴目 | komi | 围棋终局时黑方（先手）要补给白方的目数或子数，把先行的价值折成分数 | [11](./11-sequential-commitment.md) |
| 交换规则 | swap rule / pie rule | 先手下第一子后，后手可以选择交换身份；让先手自己给开局定价 | [03](./03-game-trees.md)（深入：[11](./11-sequential-commitment.md)） |
| 蛇形顺序 | snake order | A-B-C-D-D-C-B-A 式的选择顺序；序号和相等只是结构对称，补偿是否到位要测 | [11](./11-sequential-commitment.md) |
| 我分你选 | I cut, you choose | 一人切分、另一人先挑；交换规则是它的变体。第 11 章的模型（同质硬币、双方只在乎自己拿几枚）里切的人最好切到最平；资源不同质或双方估值不同时要重算，最小单位太粗时也分不平 | [11](./11-sequential-commitment.md) |
| 重复博弈 | repeated game | 同一个博弈反复进行，下一次见面会改变这一次的激励 | [14](./14-cooperation-negotiation.md) |
| 以牙还牙 | Tit for Tat（也译"一报还一报"） | 第一轮合作，以后每轮出对方上一轮出的；在 Axelrod 的锦标赛中胜出，但表现依赖对手池 | [14](./14-cooperation-negotiation.md) |
| 共同知识 | common knowledge | 我知道、你知道我知道、我知道你知道我知道……一直下去；有限轮倒推要求它 | [14](./14-cooperation-negotiation.md) |
| 核 | core | 合作博弈里"没有任何小团体想脱离"的分配集合；空核说明不存在挡得住所有联盟偏离的分配 | [13](./13-multiplayer-politics.md) |
| Shapley 值 | Shapley value | 把所有加入顺序下每个人带来的新增价值取平均的分配；公平，但不保证稳定 | [13](./13-multiplayer-politics.md) |

### 1.3 信息与推断

| 中文 | 英文 | 一句话说明 | 章节 |
|---|---|---|---|
| 完美信息 / 不完美信息 | perfect / imperfect information | 每次行动时是否知道之前发生过的所有事（含已出现的随机结果） | [12](./12-information.md) |
| 完全信息 / 不完全信息 | complete / incomplete information | 是否所有人都知道游戏结构和每个人的收益；隐藏身份、私人估值属于不完全信息 | [12](./12-information.md) |
| 信息集 | information set | 博弈树上你分不清的那些节点；在它们之间你只能做同一个决定 | [12](./12-information.md) |
| 条件概率 / 证据更新 | conditional probability / Bayesian updating | 已知看到了证据 B，隐藏真相 A 的概率；用先验、似然、后验三步算 | [12](./12-information.md) |
| 先验 | prior | 看到证据之前，每种可能的世界各占多少 | [12](./12-information.md) |
| 似然 | likelihood | 在某种世界里出现你看到的这个证据的可能性；经常要带一个行为假设 | [12](./12-information.md) |
| 后验 | posterior | 看到证据之后每种世界的比例，与"先验 × 似然"成正比 | [12](./12-information.md) |
| 赔率 | odds | 两种世界的可能性之比，概率 1/5 写成 1 : 4 | [12](./12-information.md) |
| 似然比 | likelihood ratio | 证据在世界甲里出现的可能性除以在世界乙里的；后验赔率 = 先验赔率 × 似然比 | [12](./12-information.md) |
| 信号 | signal | 别人能观察到、并用来更新对你判断的东西；可信要看假的一方发它是否更贵 | [12](./12-information.md) |
| 廉价信号 | cheap talk | 不花成本、规则不强制兑现的表态；利益一致时能帮协调，冲突时可信度另算 | [12](./12-information.md) |
| 信息刻度 / 信息协议 | 本课用语 | 用内容、对谁、何时、精度、来源、成本、有效期、可验证八个刻度写清"谁在什么时候知道什么" | [12](./12-information.md) |
| 记牌 | card counting | 维护"已出现 / 还剩什么"的账本；数出剩余牌和推断某个位置是什么牌之间还差行为假设 | [12](./12-information.md) |
| 空位 | vacant spaces | 桥牌术语：一个对手手里还有几张你不知道的牌。**没有其他信息**、未知牌在可行空位间等可能时，关键牌在谁手里的概率正比于空位数；叫牌、出牌行为等证据会改变这个分布 | [26](./26-trick-taking.md) |
| 硬证据 / 软证据 | 本课用语 | 硬证据不能伪造但可以选择不产生（失败票张数）；软证据完全可以伪造（发言、投票倾向） | [27](./27-social-deduction.md) |
| 洗白力度 | 本课用语 | 一次成功任务对队员的洗白程度："有坏人 : 没坏人"的赔率乘以似然比 1 − q（q 是坏人出失败的倾向），q 越大洗白越强，后验还取决于先验；坏人越能忍，成功票越不值钱 | [27](./27-social-deduction.md) |
| 发言即行动 | 本课用语 | 社交推理游戏里，说什么、何时说本身就是会被读取的动作 | [27](./27-social-deduction.md) |

### 1.4 多人博弈、合作与谈判（含社区术语）

| 中文 | 英文 | 一句话说明 | 章节 |
|---|---|---|---|
| 造王 | kingmaking / kingmaker | 一个自己已处于必输位置的玩家，有能力决定其他人中谁获胜（BGG 术语表；Wikipedia 定义为三人及以上游戏的终局局面）【行业口径】 | [13](./13-multiplayer-politics.md) |
| 打压领先者 | bash the leader | 其他玩家把攻击、阻挡集中到领先者身上。BGG 术语表没有独立词条，只在"multiplayer game"词条里以"ganging up on the leader"提到，作为三人以上游戏的特征之一【行业口径】 | [13](./13-multiplayer-politics.md) |
| 领先者失控 | runaway leader | 一个机制让玩家接近胜利的同时也让他之后的行动更强，形成正反馈、优势越滚越大（League of Gamemakers 2014 年的讨论）；对应的设计手段是追赶机制【行业口径】 | [13](./13-multiplayer-politics.md) |
| 多人单机 | multiplayer solitaire | BGG 术语表"player interaction"词条：玩家之间很少或没有直接互动的游戏有时被称为多人单机【行业口径】；它是描述，不是判决 | [13](./13-multiplayer-politics.md) |
| 龟缩 | turtling | BGG 术语表：多人战争游戏中缩在防守位置、等别人互相消耗的打法【行业口径】。本课正文未单独展开，可对照"第二名策略" | [13](./13-multiplayer-politics.md)（相关） |
| 分析瘫痪 | analysis paralysis（AP） | BGG 术语表：过度分析与极小极大式的优化（mini/maxing）使游戏的等待时间增加到超过理想水平【行业口径】；不是"想得久"的同义词 | [20](./20-tension-arc.md) |
| 等待时间 | downtime | 不轮到你时的空等；分析瘫痪的定义落在它上面 | [20](./20-tension-arc.md) |
| 指挥型玩家 | alpha player / quarterbacking | BGG 术语表：一个玩家倾向于带头，甚至对别人发号施令、告诉他们怎么玩，是对合作游戏常见的抱怨；也有"引导共识的真正领导者"的褒义用法。常与瘟疫危机一起讨论，但最早出处查不到【行业口径】 | [14](./14-cooperation-negotiation.md) |
| 第二名策略 | 本课用语 | 暂时不领先、避免被围攻的打法；它要写成有条件的判断，不能错过唯一的冲线窗口 | [13](./13-multiplayer-politics.md) |
| 共享胜利 | shared victory | 规则允许不止一人同时获胜（宇宙遭遇、茂林源记流浪者结盟）；它改变了"帮他就是让我输"的判断 | [13](./13-multiplayer-politics.md) |
| 完全合作游戏 | fully cooperative game | 全队同胜同负，只有判断分歧，没有个人得分；难题是信息、协调和参与感 | [14](./14-cooperation-negotiation.md) |
| 临时联盟 / 互利交换 | 本课用语 | 两种"一起"：前者为眼前的共同威胁阶段性合作，参与者的最终利益（名次、谁获胜）未必一致；后者是一笔让双方都更好的交易 | [14](./14-cooperation-negotiation.md) |
| BATNA | Best Alternative to a Negotiated Agreement | 谈不成时你真的能执行的最好选项，是你的谈判底线 | [14](./14-cooperation-negotiation.md) |
| 可接受区间 | zone of possible agreement | 双方都不比各自退路差的方案范围 | [14](./14-cooperation-negotiation.md) |
| 焦点 / 谢林点 | focal point / Schelling point | 多种方案中双方容易同时想到的那一个（对半分、按上次的价）；出自 Schelling《冲突的战略》 | [14](./14-cooperation-negotiation.md) |
| 暴露 | 本课用语 | 不是当场同时交付的协议里，先付出的一方承担的违约风险 | [14](./14-cooperation-negotiation.md) |
| 可执行 / 不可执行承诺 | enforceable / unenforceable commitment | 规则能否强制一份协议兑现；不可执行时要倒推最后一步看对方的利益 | [14](./14-cooperation-negotiation.md) |
| 押金 | deposit | 让履约严格更好的抵押；太大会让对方交完就没钱履约 | [28](./28-asymmetry-negotiation.md) |

### 1.5 策略空间与设计原理

| 中文 | 英文 | 一句话说明 | 章节 |
|---|---|---|---|
| 策略空间 | strategy space | 规则跑起来之后玩家实际能走的路线、每个局面下值得考虑的动作和对手的应对；是规则和玩家思考之间的中间层，设计师只能间接影响它 | [01](./01-what-is-strategy-game.md) |
| 动作 | action | 某一个决策点上实际做的一件事 | [15](./15-strategy-space.md) |
| 路线 | route（玩家也说打法、流派） | 对一组倾向的压缩描述，不回答所有局面下怎么做 | [15](./15-strategy-space.md) |
| 完整策略 | complete strategy | 对可能面对的每一个决策点都规定怎么做的条件计划，包括走不到的分支 | [11](./11-sequential-commitment.md)（深入：[15](./15-strategy-space.md)） |
| 人格卡 | 本课用语 | 把路线补全成任何人都能照着执行的固定打法（买不起时做什么、同点怎么选、门槛几张） | [15](./15-strategy-space.md) |
| 伪选择 | false choice | 规则上给了多个选项，但有的从来不值得认真考虑，或和另一个后果相同 | [15](./15-strategy-space.md) |
| 策略坍缩 | strategic collapse | 原本想让玩家反复比较的核心决策，被一种容易掌握、不用读局面的固定做法系统性取代 | [15](./15-strategy-space.md) |
| 策略地图 | 本课用语 | "我的路线 × 对手路线"的表，每格写结果、原因、反例和证据强度 | [15](./15-strategy-space.md) |
| 极端策略测试 | extreme strategy testing | 让一个人只做一件事并认真求胜，检验取舍是否存在、规则能否承受边界行为 | [15](./15-strategy-space.md) |
| 三种策略寿命 | 本课用语 | 理论上可解、玩家实际掌握、环境不断更新三个时钟 | [15](./15-strategy-space.md) |
| 证据强度 | 本课用语 | 精确求解 / 固定打法模拟 / 真人小样本 / 尚未验证四档；精确反例和几局领先的力量不对称 | [15](./15-strategy-space.md) |
| 回归测试局面 | 本课用语（借自 regression test） | 每次改规则后重摆的关键局面，看候选是否按预期变化、有没有误伤 | [15](./15-strategy-space.md) |
| 复杂度 | complexity | 本课拆成规则、状态、执行、记忆、搜索五种负担，和策略深度分开看 | [16](./16-depth-complexity.md) |
| 策略深度 | strategic depth | 玩家通过学习能不断发现新的、影响结果的区别，而且这些发现不会很快到头 | [16](./16-depth-complexity.md) |
| 技巧台阶 | skill ladder | 玩家一级一级获得新的判断能力；同一局面不同水平的人看到的东西不一样 | [16](./16-depth-complexity.md) |
| 规则预算 | rule budget | 目标玩家愿意付出的学习、查阅、执行成本，以及你打算把它花在哪里 | [16](./16-depth-complexity.md) |
| 优雅 | elegance | 本课口径：用相对少的规则和呈现负担，持续支撑清楚而有意义的决策；是评价框架，不是定理 | [16](./16-depth-complexity.md) |
| 删除测试 | 本课用语 | 删掉一条规则，重摆它制造的独有选择和它带来的最大负担，看什么消失了 | [16](./16-depth-complexity.md) |
| 平衡 | balance | 本课拆成三个对象：座次 / 阵营的机会、路线可行性、参与体验 | [17](./17-balance.md) |
| 对称 / 非对称 | symmetry / asymmetry | 规则是否对各方相同；规则对称不等于处境对称（轮流行动仍有时点差） | [17](./17-balance.md) |
| 不传递 | intransitivity | 强弱不构成一条总榜（三颗骰子两两 5:4）；对全场胜率 50% 不代表每场对局平衡 | [17](./17-balance.md) |
| 成本曲线 | cost curve | 卡牌设计的惯例工具【行业口径】：用一组标准牌连出代价与效果的基准线；先过共同单位、期限、不可加性三关 | [17](./17-balance.md) |
| 人数缩放 | player count scaling | 同一套规则在不同人数下运转得怎样；资源供给、市场刷新、争夺密度、等待时间、联盟结构一起变 | [17](./17-balance.md) |
| 输入随机 | input randomness | 随机先发生，玩家看见后再决定；"输入"要指明是相对哪个决定 | [18](./18-luck-and-skill.md) |
| 输出随机 | output randomness | 玩家先决定，随机再决定结果；要让"冒险还是求稳"本身成为取舍，需玩家能选承担多少风险且目标非线性（只最大化期望分时只比平均值，风险大小不影响偏好） | [18](./18-luck-and-skill.md) |
| 技巧上限 | skill ceiling | 继续练习能否带来更好的决定和结果；和"强者某一局能不能赢"是两回事 | [18](./18-luck-and-skill.md) |
| 方差 | variance | 结果围绕平均值的波动程度；决定胜负的常是门槛附近那一点概率 | [18](./18-luck-and-skill.md) |
| 区域控制 | area control | 控制某个区域带来资源、通行、行动或分数的宽泛说法 | [19](./19-interaction.md) |
| 区域多数 / 多数决 | area majority | 比较各方在区域里的数量决定谁拿奖励；要写清门槛、相对数量、计分时点 | [19](./19-interaction.md) |
| 互动通道 | 本课用语 | 直接冲突、抢占与阻挡、公共市场、交易四种"影响从哪条路走过去" | [19](./19-interaction.md) |
| 反事实测试 | counterfactual test | 固定自己、只改对手，看自己的最佳动作变不变；是多人单机的线索，不是判定 | [19](./19-interaction.md) |
| 张力弧 | tension arc | 随对局推进，玩家对胜负、风险和后果的关注怎样变化；画之前先说清纵轴 | [20](./20-tension-arc.md) |
| 滚雪球 | snowballing | 优势继续产生优势的正反馈 | [20](./20-tension-arc.md) |
| 追赶机制 | catch-up | 规则层面帮助落后者或给领先者加价的手段；Rosewater 把它列为每款游戏需要的十项之一 | [20](./20-tension-arc.md) |
| 锁定点 | 本课用语 | 领先者胜率第一次达到 90% 的轮次；结构指标，不说明每局都在那一轮锁死 | [20](./20-tension-arc.md) |
| 终局触发 / 收尾协议 | end-game trigger / 本课用语 | 触发条件决定游戏何时进入结束；收尾协议规定触发后谁还能行动、何时结算、平分怎么判（终局七问） | [20](./20-tension-arc.md) |
| 决策密度 | 本课用语 | 每分钟出现多少个玩家能说清权衡的决定；没有通用最优值 | [20](./20-tension-arc.md) |

### 1.6 机制族

| 中文 | 英文 | 一句话说明 | 章节 |
|---|---|---|---|
| 抽象策略 | abstract strategy game | 工作分类【行业口径】：轮流行动、状态全公开、结算确定、主题不参与判断 | [21](./21-abstract-games.md) |
| 交叉目标 | 本课用语 | 一个格子同时在双方的目标路径上，几乎每一手都同时是进攻和防守 | [21](./21-abstract-games.md) |
| 得分率 | 本课用语 | 胜 1、和 0.5、负 0 的平均；国际象棋白方得分率 54.95% 不等于白胜 37.50% | [21](./21-abstract-games.md) |
| 引擎构筑 | engine building | 获得能持续改善生产、折扣、转换或行动能力的东西；改变"以后我每次能做多少" | [22](./22-engine-worker-placement.md) |
| 工人放置 | worker placement | 用有限的行动单位占用容量有限的公共行动格；分配"这一轮谁能做什么" | [22](./22-engine-worker-placement.md) |
| 阻挡 | blocking | 占掉对手需要的格子或选项；价值 = 对手的损失 − 自己放弃的收益，两人局里就是分差的变化，最后还要对照胜负目标；多人局还要看第三人是否成为最大受益者 | [22](./22-engine-worker-placement.md) |
| 角色选择 | role selection | 选一个阶段或角色，多数情况下全桌都执行、选择者拿特权（波多黎各） | [22](./22-engine-worker-placement.md) |
| 拍卖 | auction | 让玩家自己给"这个东西归谁"定价 | [23](./23-auction-draft.md) |
| 选秀 | draft | 没有钱的拍卖：轮流从同一批东西里挑，代价是拿不了别的、剩下的流向谁 | [23](./23-auction-draft.md) |
| 私人价值 / 共同价值 | private / common value | 前者各人估值不同且互不影响；后者对所有人相同但没人确切知道 | [23](./23-auction-draft.md) |
| 赢家诅咒 | winner's curse | 共同价值拍卖里，赢家往往是估得最乐观的人，因而常常付多了 | [23](./23-auction-draft.md) |
| 暗标 | sealed bid | 各人秘密出价；第一价格付自己的出价，第二价格（维克里拍卖）付第二高的出价 | [23](./23-auction-draft.md) |
| 激励相容 | incentive compatibility | 让照实出价成为最好做法的拍卖设计；第二价格暗标是例子，但只在第 23 章的窄模型里成立：只拍一件、私人价值、钱付银行、只在乎自己的净收益。共同价值、钱付对手、后续拍品要用钱、在乎对手得多少时都要重算 | [23](./23-auction-draft.md) |
| 压价 | bid shading | 第一价格暗标里出价低于估值才能赚钱 | [23](./23-auction-draft.md) |
| 公开加价 | English auction | 逐步加价直到没人跟；在上述同一个窄模型里，策略上接近第二价格 | [23](./23-auction-draft.md) |
| 串谋 | collusion | 几个出价人私下约定互不抬价 | [23](./23-auction-draft.md) |
| 卡牌（选秀中） | hate draft | 拿走对自己用处不大、对下家很有用的牌；要按分差算，多人局还有第三人 | [23](./23-auction-draft.md) |
| 牌组构筑 | deck-building | 在一局之内从小而弱的起始牌组出发，一边打一边加牌（有时删牌）；你设计的是一个概率分布 | [24](./24-deckbuilding.md) |
| 瘦身 | trashing / deck thinning | 把牌从牌组里永久删掉，提高好牌被抽到的频率 | [24](./24-deckbuilding.md) |
| 大钱 | Big Money | 领土社区最常用的基准策略【行业口径】：几乎不用王国卡，只买钱和行省；用来衡量"多好才算好" | [24](./24-deckbuilding.md) |
| 终端 / 撞车 | terminal / collision | 社区说法【行业口径】：不给额外行动次数的行动牌叫终端，两张同时出现浪费一张叫撞车 | [24](./24-deckbuilding.md) |
| 赛前构筑 | deck construction | 从可用卡池里选出一套牌进入比赛；和局内牌组构筑的区别是主要构筑决策发生在开局前（局内牌库仍可能因卡牌效果改变） | [25](./25-ccg-metagame.md) |
| 元博弈 | metagame | 围绕"别人会带什么"展开的相互适应；环境更新改变的是策略地图上各列的权重 | [25](./25-ccg-metagame.md) |
| 法术力曲线 | mana curve | 社区术语【行业口径】：非地牌按费用分组的数量分布；平均值会遮掉节奏 | [25](./25-ccg-metagame.md) |
| 伦敦调度 | London mulligan | 万智牌规则：洗回重抽 7 张，再按已调度次数把相应张数放到牌库底。这是两人对局的口径；多人游戏与 Brawl 中第一次调度免费【规则】 | [25](./25-ccg-metagame.md) |
| 卡组原型 | archetype | 玩家把相近胜利计划归成一类的语言，如快攻（aggro）、中速（midrange）、控制（control）、组合技（combo） | [25](./25-ccg-metagame.md) |
| 卡牌优势 / 节奏 | card advantage / tempo | 前者是用一张牌换掉对方多张；后者是在关键时间点让自己的行动更有效 | [25](./25-ccg-metagame.md) |
| 备牌 / 针对牌 | sideboard / tech card | 备牌让一部分赛前选择推迟到知道对手之后；针对牌是为某类对局专门放进来的牌 | [25](./25-ccg-metagame.md) |
| 禁限 / 轮替 | banned & restricted / rotation | 设计者干预环境的两种工具：禁用或限制某张牌；按赛制让旧系列整体退出 | [25](./25-ccg-metagame.md) |
| 吃墩 | trick-taking | 每人出一张凑成一墩，按规则比大小，赢者收墩并领出下一墩 | [26](./26-trick-taking.md) |
| 将牌 | trump | 能压过其他花色的那门牌，让"缺门"从弱点变成武器 | [26](./26-trick-taking.md) |
| 飞牌 | finesse | 桥牌基础打法：赌某张关键牌在特定对手手里，成功率就是它在那里的概率 | [26](./26-trick-taking.md) |
| 堵塞 / 解封 | blocking / unblocking | 自己的大牌卡住搭档长套的出牌权；先把它压掉叫解封 | [26](./26-trick-taking.md) |
| 合理的替代 | logical alternative | 桥牌规则用语（Law 16B1）：同水平、用同一套约定的玩家里，有相当比例会认真考虑、其中一些人会选的行动。有搭档迟疑等未经授权的信息时，**只要存在这样的替代**，就不能选被该信息明显暗示的那一手 | [26](./26-trick-taking.md) |
| 社交推理 | social deduction | 一个知情的少数派藏在不知情的多数派里，多数派靠观察行为把他们找出来 | [27](./27-social-deduction.md) |
| 谈判 | negotiation | 在规则允许的通道里协商交换与承诺；设计时要给它入口、时限和失败结果 | [28](./28-asymmetry-negotiation.md) |
| 非对称的五个维度 | 本课用语 | 起始位置与资源、动作与限制、计分方式与时点、信息、胜利条件 | [28](./28-asymmetry-negotiation.md) |

### 1.7 原型、测试与交付

| 中文 | 英文 | 一句话说明 | 章节 |
|---|---|---|---|
| 核心决策句 | 本课用语 | "玩家在 ___ 和 ___ 之间纠结，因为 ___；对手的 ___ 会改变这个权衡" | [29](./29-prototyping.md) |
| 最小决策循环 | minimal decision loop | 能让核心决策反复出现的最小规则集，只回答"这个纠结存在吗" | [29](./29-prototyping.md) |
| 最小可玩原型 | 本课用语 | 能开始、能进行、能结束、能分胜负的最便宜版本 | [29](./29-prototyping.md) |
| 单人多手自测 | solo multi-handed playtest | 一个人按人格卡扮演所有座位打完一局；找漏洞的工具，不是验证乐趣的工具 | [29](./29-prototyping.md) |
| 测试替身 | test double | 人格卡的工程类比：把"对手"换成可重复的东西，让其他问题暴露出来 | [29](./29-prototyping.md) |
| 主题负债 | 本课用语 | 主题让玩家默认了你没写的规则或不同的数字；测试者反复犯同一种"按常理"的错 | [29](./29-prototyping.md) |
| 测试伪影 | 本课用语 | 测试方法本身制造出来的现象（如自测里扮演者知道所有人的一切） | [29](./29-prototyping.md) |
| 首次教学 | 本课用语 | 你口头讲规则、然后旁观的测试；测"你 + 规则"能否在 5 分钟教会 | [30](./30-playtest-balance.md) |
| 熟人测 | 本课用语 | 和玩过几局的人测，看决策是否有意思、有无伪选择和张力弧 | [30](./30-playtest-balance.md) |
| 盲测 | blind playtest | 只给规则书和组件、作者一句话也不说；测规则书能否独立教会人 | [30](./30-playtest-balance.md) |
| 破坏者测试 | 本课用语 | 请熟练玩家按破坏清单钻空子；发现要可复现、有后果才算数 | [30](./30-playtest-balance.md) |
| 误读四类 | 本课用语 | 盲测误读分为缺失、歧义、埋没、冲突，修法各不相同 | [30](./30-playtest-balance.md) |
| 问题指纹 | 本课用语 | 区分规则问题、呈现问题、策略问题的可观察证据 | [30](./30-playtest-balance.md) |
| 调参顺序 | 本课用语 | 规则漏洞 → 时长与终局 → 经济总量 → 路线 → 座位与先手 → 单张牌 | [30](./30-playtest-balance.md) |
| 规则书坏味道 | 本课用语（借自 code smell） | 同物异名、规则藏在例子里、条件效果混写、"等等"、例外前置、终局不可判、没写平局 | [30](./30-playtest-balance.md) |
| 自评审清单 | 本课用语 | 按平衡检查清单逐条写本作目标、适用性、证据、判断（达到 / 部分达到 / 没达到 / 不知道）和下一步；"不知道"比"没达到"更危险 | [31](./31-end-to-end-lab.md) |

---

## 2. 资料地图

**只列编者核实过存在的资料**（核实于 2026 年 10 月）。中译本只写查到豆瓣、百科或出版社条目的；查不到的写"中译本未查到"。"对应本课"一栏是建议对照阅读的章节，标"本课引用"的是正文直接引用过的。

**先看三条纠正**，网上常见的说法和核实结果不一致：
- **没有查到** Richard Garfield 本人题为"Luck in Games"的 GDC 2012 演讲。GDC Vault 上能核实的是 GDC Next 2013 的《Luck and Skill in Games》，页面列出的讲者是 Skaff Elias。想引 Garfield 谈运气的观点，改看 Board Game Design Lab 第 74 期或《Characteristics of Games》。
- **《Rules of Play》没有查到正式简体中译本**，不要写成《游戏规则》。
- **《体验引擎》是《Designing Games》的中译名**，不是《游戏设计：……》。

### 2.1 书

| 书 | 作者 / 出版 | 讲什么 | 中译本 | 对应本课 |
|---|---|---|---|---|
| **Characteristics of Games** | George Skaff Elias、Richard Garfield、K. Robert Gutschera；MIT Press 2012 | 用玩家人数、运气与技巧的比例、投入回报比等"特征"横向比较各类游戏；附录简述数学博弈论。**最贴近本课的一本** | 未查到 | 全程，尤其 13、15~20；本课引用：[18](./18-luck-and-skill.md) |
| **Building Blocks of Tabletop Game Design** | Geoffrey Engelstein、Isaac Shalev；CRC Press 第 1 版 2019、第 2 版 2022 | 按类别收录几百种桌游机制，每种讲做法、优缺点和实例；BGG 的机制分类采用了它的体系 | 未查到（有日译本） | 21~28 |
| **GameTek** | Geoffrey Engelstein；HarperCollins 版 2020（另有 2017 年早期版本） | 短章随笔，用游戏讲概率、随机性、记忆、囚徒困境等 | 未查到 | 09、12、18 |
| **Achievement Relocked: Loss Aversion and Game Design** | Geoffrey Engelstein；MIT Press 2020 | 用损失厌恶、禀赋效应、得失框架分析游戏设计，含 Uwe Rosenberg 三款游戏的分析 | 未查到 | 19（负面互动的情绪成本）、22 |
| **The Kobold Guide to Board Game Design** | Mike Selinker 编；Open Design 2011 | 设计师文集（Garfield、Steve Jackson 等），从构思写到推介 | 未查到 | 29~31 |
| **Playing to Win: Becoming the Champion** | David Sirlin；网络版 2000 年起连载，sirlin.net/ptw | 竞技玩家"为赢而玩"的心态；第 7 章"Yomi: Spies of the Mind"讲读心层级 | 未查到 | 06、08；本课引用：[06](./06-reading-opponents.md) |
| **Thinking Strategically** | Avinash Dixit、Barry Nalebuff；Norton 1991 | 面向大众、不用数学的博弈论入门 | 《策略思维》（王尔山译，中国人民大学出版社） | 09~14 |
| **The Art of Strategy** | Dixit、Nalebuff；Norton 2008 | 上一本的续作（不是修订版），例子极多 | 《妙趣横生博弈论》（董志强等译，机械工业出版社） | 09~14 |
| **The Evolution of Cooperation** | Robert Axelrod；Basic Books 1984 | 重复囚徒困境的计算机锦标赛，以牙还牙胜出；成功策略的四个特点 | 《合作的进化》（吴坚忠译，上海人民出版社） | 14；本课引用：[14](./14-cooperation-negotiation.md) |
| **The Strategy of Conflict** | Thomas C. Schelling；Harvard University Press 1960 | 既有共同利益又有冲突的局面：谈判、威慑、承诺、默契协调；焦点（谢林点）出自本书 | 《冲突的战略》（华夏出版社） | 11、14；本课引用：[11](./11-sequential-commitment.md)、[14](./14-cooperation-negotiation.md) |
| **Game Theory 101: The Complete Textbook** | William Spaniel；自出版 2011 | 配套 YouTube 频道的入门教材：策略式博弈、纳什均衡、扩展式博弈 | 未查到 | 09~11 |
| **Rules of Play** | Katie Salen、Eric Zimmerman；MIT Press 2003 | 游戏设计理论教科书，按核心概念 / 规则 / 玩 / 文化组织，提出 18 个 game design schemas | **未查到**，不要写中译名 | 01 |
| **Uncertainty in Games** | Greg Costikyan；MIT Press 2013 | 游戏靠不确定性吸引人；把不确定性分成随机性、表现型、分析复杂度、对手不确定等来源 | 未查到 | 01、18；本课引用：[18](./18-luck-and-skill.md) |
| **Designing Games** | Tynan Sylvester（RimWorld 作者）；O'Reilly 2013 | 把游戏看作制造体验的机器：机制、优雅、平衡、多人、动机、开发流程 | 《体验引擎：游戏设计全景探秘》（秦彬译，电子工业出版社 2015） | 16；本课引用：[16](./16-depth-complexity.md) |
| **The Art of Game Design: A Book of Lenses** | Jesse Schell；第 3 版 CRC Press 2019 | 用 100 多个"透镜"（成组的自问问题）审视设计 | 《游戏设计艺术》（电子工业出版社） | 姊妹课程 [game-design](../game-design/README.md) 的主要参考；本课对照 29 |
| **Game Design Workshop** | Tracy Fullerton；第 5 版 CRC Press 2024 | 以练习驱动、以玩家体验为中心的设计教材，讲原型与测试 | 《游戏设计梦工厂》（电子工业出版社） | 29、30 |
| **Eurogames** | Stewart Woods；McFarland 2012 | 德式（欧式）桌游的形式、爱好者文化和玩家体验 | 未查到 | 01（谱系）、22 |
| **Game Design Theory** | Keith Burgun；A K Peters/CRC 2012 | 出版社简介：试图从整体上区分游戏和其他交互系统；更细的论点未逐章核实 | 未查到 | 01 |
| **Clockwork Game Design** | Keith Burgun；Focal Press 2015 | 系统化的设计方法书；具体方法论未逐章核实，引用前先看目录 | 未查到 | 15、16（延伸） |

### 2.2 演讲与文章

| 标题 | 作者 / 场合 | 讲什么 | 对应本课 |
|---|---|---|---|
| **Interesting Decisions** | Sid Meier，GDC 2012（GDC Vault 免费） | 从"a game is a series of interesting decisions"出发，讲哪些决策有趣、节奏与信息反馈 | 01、05、15 |
| **Luck and Skill in Games** | Skaff Elias（Vault 页面所列讲者），GDC Next 2013 | 运气和技巧不是简单对立，二者既取决于游戏也取决于玩家 | 18；本课引用：[18](./18-luck-and-skill.md) |
| **Timmy, Johnny, and Spike** | Mark Rosewater，Making Magic 专栏 2002 | 万智牌研发用的三种玩家心理画像；2006-03-20 有 Revisited 更新版 | 25 |
| **Ten Things Every Game Needs**（Part 1；Part 1 & Part 2） | Mark Rosewater，2011-10-24；2011-12-19 | 目标、规则、互动、追赶机制、推进力；惊喜、策略、乐趣、风味、卖点 | 19、20；本课引用：[20](./20-tension-arc.md) |
| **Twenty Years, Twenty Lessons** | Mark Rosewater，GDC 2016 | 20 条设计经验，如"让好玩的打法也是能赢的打法" | 15、29 |
| **Balancing Multiplayer Competitive Games** | David Sirlin，GDC 2009 | 竞技游戏平衡，避免退化成少数几招或几种策略 | 15、17 |
| **Balancing Multiplayer Games**（Part 1–4） | David Sirlin，sirlin.net/articles 系列（单篇日期与 URL 未逐一核实） | 竞技游戏平衡的系列文章 | 17 |
| **Game Balance and Yomi** | David Sirlin，2014-08-20 | 以 20 个角色的卡牌对战游戏 Yomi 讲非对称平衡、tier list 和对局胜率表 | 17、28 |
| **Solvability** | David Sirlin，2014-09-13 | 存在"纯解"的游戏不再有真正的决策；要简单到能懂、复杂到解不出 | 09、15；本课引用：[09](./09-simultaneous-games.md)、[15](./15-strategy-space.md) |

### 2.3 播客与博客

| 名称 | 主持 / 作者 | 讲什么 | 对应本课 |
|---|---|---|---|
| **Ludology** | 2011 年由 Geoff Engelstein、Ryan Sturm 创办，现任主持 Erica Bouyouris、Sen-Foong Lim；Dice Tower Network | 每两周一期，桌游设计、历史和玩家的分析性讨论 | 15~20 |
| **GameTek**（播客环节） | Geoff Engelstein，2007 年起在 Dice Tower 播客中开设 | 游戏中的数学、科学和心理学 | 12、18 |
| **Board Game Design Lab** | Gabe Barrett | 桌游设计教学平台，访谈设计师和出版商；第 74 期《Luck vs Skill with Richard Garfield》（2018-05-02）谈运气与技巧，以及即使国际象棋也有运气成分 | 18（本课引用第 74 期：[18](./18-luck-and-skill.md)）、29~31 |
| **Stonemaier Games 博客 / Kickstarter Lessons** | Jamey Stegmaier | 众筹、发行、物流经验，"How to Design a Tabletop Game"栏目和设计日志；其单人自动对手 Automa 见附录 E | 29~31、[附录 E](./E-extensions.md) |
| **Cardboard Edison** | Chris & Suzanne Zinsli | 设计资源聚合：博客、出版商名录、设计清单 | 29~31 |
| **Daniel Solis 博客** | Daniel Solis（著有《Graphic Design for Board Games》） | 游戏设计、卡牌版式和平面设计（2006 年至 2024-09 更新） | 16（组件与信息呈现）、29 第 7 节 |

### 2.4 论文、数据与历史

| 资料 | 出处 | 内容 | 对应本课 |
|---|---|---|---|
| **Unraveling in Guessing Games** | Rosemarie Nagel，American Economic Review 85(5)，1995 | "猜平均数的 p 倍"实验（p = 1/2、2/3、4/3），level-k 研究的奠基文献 | [06](./06-reading-opponents.md) |
| **凯恩斯选美比喻** | J. M. Keynes《就业、利息和货币通论》（1936）第 12 章 | 用报纸选美比喻"预测一般意见认为一般意见会是什么" | [06](./06-reading-opponents.md) |
| **Social cycling and conditional responses in the Rock-Paper-Scissors game** | Zhijian Wang、Bin Xu、Hai-Jun Zhou，Scientific Reports 4, 5830（2014） | 浙江大学 360 名学生的石头剪刀布实验：群体层面持续循环；个体有类似"赢留输变"的条件反应，但实测参数与严格的赢留输变差别很大 | [06](./06-reading-opponents.md)、[10](./10-mixed-strategies.md) |
| **First-move advantage in chess** | Wikipedia 词条 | 白方得分率通常 52%~56%；Chessgames.com 截至 2015-01-12 的 739,769 局中白方得分率 54.95% | [11](./11-sequential-commitment.md)、[21](./21-abstract-games.md)、[附录 E](./E-extensions.md) |
| **Allan B. Calhamer 与 Diplomacy** | Wikipedia 词条 | 外交的设计者，1954 年在哈佛法学院读书时设计，1959 年自费印 500 套 | [28](./28-asymmetry-negotiation.md)、[附录 D](./D-game-rules.md) |

### 2.5 社区术语的来源

| 来源 | 本课用到的词条 | 对应本课 |
|---|---|---|
| BoardGameGeek Glossary（boardgamegeek.com/wiki/page/Glossary） | kingmaker、analysis paralysis、alpha player / quarterbacking、multiplayer solitaire（在 player interaction 词条下）、ganging up on the leader（在 multiplayer game 词条下）、turtling | 13、14、19、20 |
| Wikipedia "Kingmaker scenario" | 造王的第二种定义 | 13 |
| League of Gamemakers《Ask the League: Should games have a catch-up mechanic?》（Brad Brooks 整理，2014-08-15） | runaway leader 与追赶机制 | 13、20 |
| Wikipedia "Pandemic (board game)" | quarterbacking 作为瘟疫危机受到的批评 | 14 |

---

## 3. 去哪玩、去哪找对手

和[第 00 章](./00-how-to-learn.md)第 6 节、[附录 D](./D-game-rules.md)一致。平台上架信息核实于 2026 年 10 月，之后可能变化；附录 D 里写"未核实"的不等于没有。

**线上：Board Game Arena（BGA）**。[boardgamearena.com](https://boardgamearena.com)，网页即可玩，免费账号能玩大部分游戏，规则由平台强制执行。几条建议：
- **先玩回合制（turn-based）对局**，不要玩实时对局：回合制每步可以想很久，适合做出声思考。
- 开局前看一遍平台上的规则摘要，然后直接开始。
- 前几局输是正常的，目标是记录，不是赢。
- **适合第一局的六款**（附录 D）：六角棋、驯兽师、璀璨宝石、卡卡颂、花砖物语、不谢谢。想练两步推演选驯兽师，练投资与冲分选璀璨宝石，练接受损失与保存筹码选不谢谢。
- 第 21 章的抽象游戏（六角棋含交换规则、蜂巢、驯兽师、圣托里尼、步步为营、国际象棋、中国象棋）都在 BGA 上；只有一个晚上时，推荐驯兽师 → 圣托里尼（不选神力）→ 六角棋。

**其他平台**（附录 D 规则库所列，BGA 上未核实或另有官方版本的）：

| 游戏 | 平台 |
|---|---|
| 围棋 | OGS（online-go.com）、野狐；新手常从 9×9 开始（惯例，不是规则） |
| 国际象棋 | 除 BGA 外，lichess.org、chess.com |
| 领土 | Dominion Online（dominion.games） |
| 万智牌 | 官方 MTG Arena、Magic Online |
| 血染钟楼 | 官方 botc.app、clocktower.online 魔典 |
| 情书 | 除 BGA 外，Tabletopia 有 2019 版 |

**线下**：桌游吧，或者愿意每周陪你玩一两次的同事朋友。线下的价值更高：局后可以直接问对手"你那一步在想什么"。本课最推荐的学法是**找一个比你强一点的人，局后问他一个你没想到的念头**。第 08 章起的复盘、第 30 章起的测试都需要 1~3 个固定的对手；盲测则需要**没见过你游戏**的人，不要总找同一批。

**不需要配件的游戏**：井字棋（一张纸）、取币游戏和 Nim（几枚硬币），随时可以和自己、和朋友玩。规则小，你才能把每一步想透。

---

返回：[README](./README.md)
