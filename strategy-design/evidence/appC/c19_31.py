# 附录 C：第 19~31 章补充题验算（其余部分）
from fractions import Fraction as F
from functools import lru_cache
from itertools import combinations, product, permutations
from math import comb
from collections import Counter

print("== C19.1 三人多数决：第一名得全分，并列第一平分（向下取整），其余不得分")
REG = {'北': (6, (2, 2, 1)), '中': (4, (1, 0, 1)), '南': (8, (0, 2, 1))}  # (你, 甲, 乙)
def score3(regs):
    s = [0, 0, 0]
    for v, t in regs.values():
        m = max(t)
        if m == 0: continue
        w = [i for i in range(3) if t[i] == m]
        for i in w: s[i] += v // len(w)
    return s
print('现在', score3(REG))
for r in REG:
    rr = dict(REG); v, t = rr[r]; t = list(t); t[0] += 1; rr[r] = (v, tuple(t))
    s = score3(rr); print(' 加到', r, s, '你-甲', s[0] - s[1], '你-乙', s[0] - s[2])

print("== C19.2 两区（三区）：你放 1，对手看到后放 1；多数者得全分")
def sc2(regs, tie_both):
    s = [0, 0]
    for v, (a, b) in regs:
        if a > b: s[0] += v
        elif b > a: s[1] += v
        elif tie_both and a > 0: s[0] += v; s[1] += v
    return s
def solve2(regs, tie_both):
    res = {}
    for i in range(len(regs)):
        r1 = list(regs); v, (a, b) = r1[i]; r1[i] = (v, (a + 1, b))
        worst = None
        for j in range(len(regs)):
            r2 = list(r1); v2, (a2, b2) = r2[j]; r2[j] = (v2, (a2, b2 + 1))
            s = sc2(r2, tie_both); d = s[0] - s[1]
            if worst is None or d < worst[0]: worst = (d, j, s)
        res[i] = worst
    return res
base = [(8, (0, 2)), (5, (1, 0)), (3, (2, 0))]
for tb in (False, True):
    print('并列都得分' if tb else '并列都不得', '现在', sc2(base, tb), solve2(base, tb))

print("== C20.2 打烊")
X = [1, 2, 3]
def p_lose_now(me, op, tie_lose):
    # 你立即宣布；对手最后一回合 +X
    return F(sum(1 for x in X if (op + x > me) or (tie_lose and op + x == me)), 3)
def p_lose_invest(me_final, op, tie_lose):
    return F(sum(1 for a in X for b in X if (op + a + b > me_final) or (tie_lose and op + a + b == me_final)), 9)
for tie_lose in (True, False):
    print('平分宣布者输' if tie_lose else '平分宣布者胜', '立即(10):胜', 1 - p_lose_now(10, 7, tie_lose), ' 投资(13):胜', 1 - p_lose_invest(13, 7, tie_lose),
          ' 投资(12):胜', 1 - p_lose_invest(12, 7, tie_lose))

print("== C22.2 角色选择")
# 每人：工厂数、货物、金币。角色：生产（每人货物+工厂数；选择者额外+1货）、交易（每人可卖 1 货换 3 币；选择者多 +1 币）、
# 建造（每人可花 4 币建 1 厂；选择者只花 3）。本轮只选 1 个角色，然后结束本轮。估值：货 1、币 1、厂 2（本题给定）
def evaluate(me, op, role, selector='me'):
    me = dict(me); op = dict(op)
    for who, d in (('me', me), ('op', op)):
        sel = (who == selector)
        if role == '生产': d['货'] += d['厂'] + (1 if sel else 0)
        elif role == '交易':
            if d['货'] >= 1: d['货'] -= 1; d['币'] += 3
            if sel: d['币'] += 1
        elif role == '建造':
            cost = 3 if sel else 4
            if d['币'] >= cost: d['币'] -= cost; d['厂'] += 1
    val = lambda d: d['货'] + d['币'] + 2 * d['厂']
    return val(me) - val(op), me, op
me0 = {'厂': 1, '货': 2, '币': 3}; op0 = {'厂': 3, '货': 0, '币': 4}
for role in ('生产', '交易', '建造'):
    print(role, evaluate(me0, op0, role))
op1 = {'厂': 3, '货': 0, '币': 2}
print('改：对手只有 2 币')
for role in ('生产', '交易', '建造'):
    print(role, evaluate(me0, op1, role))
base_diff = (me0['货'] + me0['币'] + 2 * me0['厂']) - (op0['货'] + op0['币'] + 2 * op0['厂'])
print('原分差', base_diff, ' 改后原分差', (me0['货'] + me0['币'] + 2 * me0['厂']) - (op1['货'] + op1['币'] + 2 * op1['厂']))

print("== C23.2 选秀 改条件")
def draft(cards, order):
    @lru_cache(None)
    def f(rem, idx):
        if idx == len(order): return 0
        who = order[idx]
        vals = [f(rem - {c}, idx + 1) + (cards[c][0] if who == 'me' else -cards[c][1]) for c in rem]
        return max(vals) if who == 'me' else min(vals)
    out = {}
    for c in cards:
        out[c] = cards[c][0] + f(frozenset(cards) - {c}, 1) if order[0] == 'me' else None
    return out
C1 = {'甲': (5, 1), '乙': (4, 4), '丙': (1, 5), '丁': (3, 3)}
print('交替', draft(C1, ('me', 'op', 'me', 'op')))
print('蛇形', draft(C1, ('me', 'op', 'op', 'me')))
C2 = {'甲': (5, 1), '乙': (4, 2), '丙': (1, 5), '丁': (3, 3)}
print('乙对他只值2 交替', draft(C2, ('me', 'op', 'me', 'op')))

print("== C26.1 斗地主记牌：已出现的牌")
played = ['大王', '2', '2', 'A', 'A', 'A', 'K', 'K', 'Q']
mine = ['2', 'A', 'K', 'K', '10']
full = {'大王': 1, '小王': 1, '2': 4, 'A': 4, 'K': 4, 'Q': 4}
seen = Counter(played) + Counter(mine)
print({k: v - seen.get(k, 0) for k, v in full.items()})

print("== C26.2 飞牌 vs 砸落（K、9 两张黑桃在外）")
def lines(u, l):
    # u：上家（在你之前出牌）未知空位；l：下家
    n = u + l
    fin = F(u, n)
    drop = F(u, n) * F(l, n - 1) + F(l, n) * F(u, n - 1)
    return fin, drop
for u, l in ((4, 6), (7, 3), (5, 5)):
    f, d = lines(u, l); print('上家空位', u, '下家', l, '飞牌', f, float(f), '砸落', d, float(d))

print("== C27.1 阿瓦隆 7 人 3 坏人")
print('随机 4 人队 >=2 坏人', F(comb(3, 2) * comb(4, 2) + comb(3, 3) * comb(4, 1), comb(7, 4)))
print('你(好人)在队里，另 3 人 >=2 坏人', F(comb(3, 2) * comb(3, 1) + comb(3, 3), comb(6, 3)))
print('任务 4 失败（需 2 张失败）若坏人都出失败：等于队里 >=2 坏人')

print("== C27.2 阿瓦隆 5 人贝叶斯")
def post(p):
    others = 'ABCD'; L = {}
    for pair in combinations(others, 2):
        ev = set(pair)
        # 任务1：A、B，恰 1 张失败
        k = len(ev & {'A', 'B'})
        if k == 0: l1 = F(0)
        elif k == 1: l1 = p
        else: l1 = 2 * p * (1 - p)
        # 任务2：你、C、A 成功
        k2 = len(ev & {'C', 'A'}); l2 = (1 - p) ** k2
        L[pair] = l1 * l2
    tot = sum(L.values())
    pe = {x: sum(v for k, v in L.items() if x in k) / tot for x in others}
    return {k: str(v / tot) for k, v in L.items()}, {k: (str(v), round(float(v), 3)) for k, v in pe.items()}
for p in (F(4, 5), F(1)):
    print('p=', p, post(p))

print("== C28.1 四派系对位")
M = {'林': {'林': .5, '河': .7, '山': .3, '城': .5}, '河': {'林': .3, '河': .5, '山': .7, '城': .5},
     '山': {'林': .7, '河': .3, '山': .5, '城': .5}, '城': {'林': .5, '河': .5, '山': .5, '城': .5}}
for share in ({'林': .25, '河': .25, '山': .25, '城': .25}, {'林': .4, '河': .2, '山': .2, '城': .2}):
    print(share, {d: round(sum(M[d][o] * w for o, w in share.items()), 3) for d in M})

print("== C28.2 抵押")
for coins in (4, 2):
    for c in range(0, coins + 1):
        pays = c >= 3
        guard = 3 if pays else c
        merchant = 7 - (3 if pays else c)
        print(' 商人币', coins, '抵押', c, '付款' if pays else '赖账', '守关得', guard, '商人净得', merchant, '对比绕路 3')

print("== C29.1 原型：5 回合，拿 3 币 或 付 4 币得 3 分，起始 0")
def enum(T, gain, cost, pts, start=0):
    best = -1; seqs = []
    for seq in product('拿换', repeat=T):
        c = start; s = 0; ok = True
        for a in seq:
            if a == '拿': c += gain
            else:
                if c < cost: ok = False; break
                c -= cost; s += pts
        if not ok: continue
        if s > best: best, seqs = s, [''.join(seq)]
        elif s == best: seqs.append(''.join(seq))
    return best, seqs
print(enum(5, 3, 4, 3))
print(enum(6, 3, 4, 3))
print("== C29.2 加'投资'：付 2 币，之后每回合开始 +1 币（可多次）")
def best_inv(T, start=0):
    @lru_cache(None)
    def f(t, c, inc):
        if t == 0: return 0, ''
        c += inc; opts = []
        v, s = f(t - 1, c + 3, inc); opts.append((v, '拿' + s))
        if c >= 4: v, s = f(t - 1, c - 4, inc); opts.append((v + 3, '换' + s))
        if c >= 2: v, s = f(t - 1, c - 2, inc + 1); opts.append((v, '投' + s))
        return max(opts)
    return f(T, start, 0)
def all_opt(T, start=0):
    res = []
    for seq in product('拿换投', repeat=T):
        c = start; inc = 0; s = 0; ok = True
        for a in seq:
            c += inc
            if a == '拿': c += 3
            elif a == '换':
                if c < 4: ok = False; break
                c -= 4; s += 3
            else:
                if c < 2: ok = False; break
                c -= 2; inc += 1
        if ok: res.append((s, ''.join(seq)))
    m = max(r[0] for r in res)
    return m, [r[1] for r in res if r[0] == m]
for T in (5, 6, 8, 10):
    m, seqs = all_opt(T); print(' T', T, '最高', m, '最优序列数', len(seqs), seqs[:6], '含投资的', sum(1 for s in seqs if '投' in s))

print("== C31.1 A~7 共 28 张，起始 3/4 币，1 号位第一轮买得到")
for start in (3, 4):
    cheap = 4 * start; exp = 28 - cheap
    p = 1 - F(comb(exp, 3), comb(28, 3)); print(start, p, float(p))
print('对照 A~6 24 张 起始 3:', float(1 - F(comb(12, 3), comb(24, 3))))
print("== C31.2 2 人，A~6，起始 3 币：2 号位第一轮买得到的概率（1 号位策略不同）")
deck = [v for v in range(1, 7) for _ in range(4)]
def seat2(policy, start=3):
    tot = 0; good = 0
    for m in permutations(range(24), 4):
        pass
    return None
# 精确：市场 3 张 + 补牌 1 张，按有序抽样枚举（24*23*22*21 种）
from itertools import permutations as P
def seat_probs(policy, start=3):
    n = 0; s1 = 0; s2 = 0
    vals = deck
    for i, j, k, l in P(range(24), 4):
        mk = [vals[i], vals[j], vals[k]]; refill = vals[l]
        n += 1
        aff = [v for v in mk if v <= start]
        if aff:
            s1 += 1
            b = min(aff) if policy == 'cheap' else max(aff)
            mk2 = list(mk); mk2.remove(b); mk2.append(refill)
        else:
            mk2 = mk
        if any(v <= start for v in mk2): s2 += 1
    return F(s1, n), F(s2, n)
for pol in ('cheap', 'max'):
    for st in (3, 4):
        a, b = seat_probs(pol, st); print(' 1号位', pol, '起始', st, '1号位', round(float(a), 4), '2号位', round(float(b), 4))
