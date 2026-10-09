# 附录 C：第 22~25 章补充题验算
from fractions import Fraction as F
from functools import lru_cache
from itertools import combinations, permutations, product
from math import comb
from collections import Counter

print("== C22.1 磨坊账本")
# 每回合 1 个动作。零工 +2 币；建磨坊 付 3 币（一次）；磨坊每回合开始若交 1 币维护则产 2 面粉（不交不产）；
# 卖面粉：1 个动作，把手里所有面粉按每袋 2 币卖掉。终局只算币。
def run(plan, coins=3, maintain=True):
    mill = False; flour = 0; log = []
    for a in plan:
        if mill and maintain and coins >= 1:
            coins -= 1; flour += 2
        if a == '零工': coins += 2
        elif a == '建': assert coins >= 3; coins -= 3; mill = True
        elif a == '卖': coins += 2 * flour; flour = 0
        log.append((a, coins, flour))
    return coins, flour, log
for plan in (['零工'] * 5, ['建', '零工', '零工', '零工', '卖'], ['建', '零工', '卖', '零工', '卖'], ['建', '卖', '卖', '卖', '卖'],
             ['零工', '建', '零工', '零工', '卖']):
    print(plan, run(plan))
# 最优计划（剩 R 回合）
def best(R, coins=3):
    bestv = None
    for plan in product(['零工', '建', '卖'], repeat=R):
        if plan.count('建') > 1: continue
        try:
            c, f, _ = run(list(plan), coins)
        except AssertionError:
            continue
        if bestv is None or c > bestv[0]: bestv = (c, plan)
    return bestv
for R in (3, 4, 5, 6):
    print('R', R, best(R))

print("== C22.2 工人放置：你先放，交替，各 2 个工人")
SPOTS = {'粮仓': (3, 0), '工坊': (0, 3), '市场': (0, 2), '码头': (1, 1)}  # (食物, 分)
def outcome(me_food, op_food, need=3, pen=2, first='me'):
    names = list(SPOTS)
    @lru_cache(None)
    def f(taken, turn, mf, mp, of, op):
        if len(taken) == 4:
            ms = mp - pen * max(0, need - mf); os_ = op - pen * max(0, need - of)
            return ms - os_, ()
        best = None
        for s in names:
            if s in taken: continue
            fd, pt = SPOTS[s]
            if turn == 'me':
                v, seq = f(taken | {s}, 'op', mf + fd, mp + pt, of, op)
                cand = (v, ((turn, s),) + seq)
                if best is None or v > best[0]: best = cand
            else:
                v, seq = f(taken | {s}, 'me', mf, mp, of + fd, op + pt)
                cand = (v, ((turn, s),) + seq)
                if best is None or v < best[0]: best = cand
        return best
    res = {}
    for s in names:
        fd, pt = SPOTS[s]
        v, seq = f(frozenset({s}), 'op', me_food + fd, pt, op_food, 0)
        res[s] = (v, seq)
    return res
for opf in (1, 2, 3):
    print('你 1 食物，对手', opf, '食物：', {k: (v[0], [x[1] for x in v[1]]) for k, v in outcome(1, opf).items()})

print("== C23.1 不谢谢 计分")
cards = [8, 9, 10, 17, 18, 26, 34]; chips = 4
s = sorted(cards); score = 0
for i, c in enumerate(s):
    if i == 0 or s[i - 1] != c - 1: score += c
print('得分', score - chips)
for take in (25, 27, 16):
    s2 = sorted(cards + [take]); sc2 = sum(c for i, c in enumerate(s2) if i == 0 or s2[i - 1] != c - 1)
    print('拿', take, '后牌面分变化', sc2 - (score), )
print('地产达人 出价 5 后放弃，拿回', 5 // 2, '实付', 5 - 5 // 2)

print("== C23.2 两人选秀：四张牌（对你的价值, 对他的价值）")
CARDS = {'甲': (5, 1), '乙': (4, 4), '丙': (1, 5), '丁': (3, 3)}
def draft(order):
    @lru_cache(None)
    def f(rem, idx):
        if idx == len(order): return 0, ()
        who = order[idx]; best = None
        for c in rem:
            v, seq = f(rem - {c}, idx + 1)
            gain = CARDS[c][0] if who == 'me' else -CARDS[c][1]
            cand = (v + gain, ((who, c),) + seq)
            if best is None or (who == 'me' and cand[0] > best[0]) or (who == 'op' and cand[0] < best[0]): best = cand
        return best
    return f(frozenset(CARDS), 0)
print('交替 我他我他', draft(('me', 'op', 'me', 'op')))
print('蛇形 我他他我', draft(('me', 'op', 'op', 'me')))
# 贪心（各拿对自己最大）
def greedy(order):
    rem = set(CARDS); me = op = 0; seq = []
    for who in order:
        c = max(rem, key=lambda k: CARDS[k][0] if who == 'me' else CARDS[k][1]); rem.remove(c); seq.append((who, c))
        if who == 'me': me += CARDS[c][0]
        else: op += CARDS[c][1]
    return me - op, seq
print('双方贪心 交替', greedy(('me', 'op', 'me', 'op')))
# 我第一手各选择在最优应对下的分差
for first in CARDS:
    order = ('op', 'me', 'op')
    @lru_cache(None)
    def g(rem, idx):
        if idx == 3: return 0
        who = order[idx]
        vals = [g(rem - {c}, idx + 1) + (CARDS[c][0] if who == 'me' else -CARDS[c][1]) for c in rem]
        return max(vals) if who == 'me' else min(vals)
    print(' 交替 先拿', first, '分差', CARDS[first][0] + g(frozenset(CARDS) - {first}, 0))

print("== C24.1 领土：7 铜 + 3 庄园 + 1 银，洗 11 张抽 5")
deck = ['铜'] * 7 + ['庄'] * 3 + ['银']
val = {'铜': 1, '庄': 0, '银': 2}
cnt = Counter()
for h in combinations(range(11), 5):
    cnt[sum(val[deck[i]] for i in h)] += 1
tot = comb(11, 5)
print({k: str(F(v, tot)) for k, v in sorted(cnt.items())})
print('>=5:', F(sum(v for k, v in cnt.items() if k >= 5), tot), float(F(sum(v for k, v in cnt.items() if k >= 5), tot)),
      '>=6:', F(sum(v for k, v in cnt.items() if k >= 6), tot))
# 无银：7 铜 + 3 庄园 + 1 庄园(第4张) 比较
deck2 = ['铜'] * 7 + ['庄'] * 4
cnt2 = Counter(sum(val[deck2[i]] for i in h) for h in combinations(range(11), 5))
print('若买的是庄园：>=5', F(sum(v for k, v in cnt2.items() if k >= 5), tot))

print("== C24.2 小牌库（每回合洗全部牌抽 3 张）")
# 卡：铜(1币) 银(2币,费3) 绿(0币, 2分, 费3)。T 回合，求最大期望分
def money_dist(deckc):
    cards = list(deckc.elements()); n = len(cards)
    d = Counter()
    for h in combinations(range(n), 3):
        d[sum({'铜': 1, '银': 2, '绿': 0}[cards[i]] for i in h)] += 1
    t = comb(n, 3)
    return {k: F(v, t) for k, v in d.items()}
@lru_cache(None)
def V(c, s, g, T):
    if T == 0: return F(0)
    deckc = Counter({'铜': c, '银': s, '绿': g})
    ev = F(0)
    for m, p in money_dist(deckc).items():
        opts = [V(c, s, g, T - 1)]
        if m >= 3:
            opts.append(V(c, s + 1, g, T - 1))
            opts.append(2 + V(c, s, g + 1, T - 1))
        ev += p * max(opts)
    return ev
def choice(c, s, g, T, m):
    opts = {'不买': V(c, s, g, T - 1)}
    if m >= 3:
        opts['银'] = V(c, s + 1, g, T - 1); opts['绿'] = 2 + V(c, s, g + 1, T - 1)
    return {k: float(v) for k, v in opts.items()}
for T in (2, 3, 4, 5, 6):
    print('牌库 6铜1绿，本回合有3币，剩', T, '回合（含本回合）', choice(6, 0, 1, T, 3))

print("== C25.1 抽地")
def hyp(N, K, n, lo, hi):
    return F(sum(comb(K, k) * comb(N - K, n - k) for k in range(lo, hi + 1)), comb(N, n))
p = hyp(60, 24, 7, 2, 4); print('60张24地 起手7张 2~4地', p, float(p))
p = hyp(60, 24, 7, 0, 1); print('  0~1地', float(p), ' 5+地', float(hyp(60, 24, 7, 5, 7)))
p = hyp(40, 17, 7, 2, 4); print('40张17地 2~4地', float(p))

print("== C25.2 四原型环境")
M = {  # 行对列胜率
    '快': {'快': .5, '中': .55, '控': .65, '组': .40},
    '中': {'快': .45, '中': .5, '控': .55, '组': .60},
    '控': {'快': .35, '中': .45, '控': .5, '组': .70},
    '组': {'快': .60, '中': .40, '控': .30, '组': .5},
}
for share in ({'快': .4, '中': .3, '控': .2, '组': .1}, {'快': .2, '中': .3, '控': .2, '组': .3}):
    print(share, {d: round(sum(M[d][o] * w for o, w in share.items()), 4) for d in M})
