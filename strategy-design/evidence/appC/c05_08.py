# 附录 C：第 05~08 章补充题验算
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fractions import Fraction as F
from functools import lru_cache
from math import comb
from collections import Counter

print("== C05.1 机会成本：两个行动")
# 动作：砍柴 +2木；卖柴 3木->4分；大订单 5木->8分；零工 +1分
def best(wood0, acts=2):
    res = {}
    for seq in itertools.product('ABCD', repeat=acts):
        w, s, ok = wood0, 0, True
        for a in seq:
            if a == 'A': w += 2
            elif a == 'B':
                if w < 3: ok = False; break
                w -= 3; s += 4
            elif a == 'C':
                if w < 5: ok = False; break
                w -= 5; s += 8
            else: s += 1
        if ok: res[''.join(seq)] = s
    return res
for w0 in (1, 3):
    r = best(w0); print('起始木', w0, sorted(r.items(), key=lambda x: -x[1]))

print("== C05.2 稳定集市：单人，市场永远有 1~6，最早第几轮结束时到达目标")
def min_round(start_round, coins_after_income, cards, target, deadline=12):
    # 返回从当前（已收入、待行动）到 >= target 所需的最早'轮结束'
    @lru_cache(None)
    def f(rnd, c, n, s):
        # 当前轮待行动，已收入
        best = None
        for a in ['pass'] + list(range(1, 7)):
            if a == 'pass': c2, n2, s2 = c + 2, n, s
            else:
                if a > c: continue
                c2, n2, s2 = c - a, n + 1, s + a
            if s2 >= target: r = rnd
            elif rnd >= deadline: r = None
            else: r = f(rnd + 1, c2 + n2, n2, s2)
            if r is not None and (best is None or r < best): best = r
        return best
    out = {}
    for a in ['pass'] + list(range(1, 7)):
        c, n, s = coins_after_income, len(cards), sum(cards)
        if a == 'pass': c2, n2, s2 = c + 2, n, s
        else:
            if a > c: continue
            c2, n2, s2 = c - a, n + 1, s + a
        if s2 >= target: out[a] = start_round
        else: out[a] = f(start_round + 1, c2 + n2, n2, s2)
    return out
print("第3轮 面前[1,1] 收入后4币 目标15:", min_round(3, 4, (1, 1), 15))
print("第3轮 面前[1,1] 收入后4币 目标20:", min_round(3, 4, (1, 1), 20))
print("第3轮 面前[1,1] 收入后4币 目标12:", min_round(3, 4, (1, 1), 12))
# 从开局（第1轮，3币，无牌）
print("开局 目标15:", min_round(1, 3, (), 15), " 目标20:", min_round(1, 3, (), 20))

print("== C06.1 12 局 6 次布，p=1/3")
p = F(1, 3)
P = sum(comb(12, k) * p**k * (1 - p)**(12 - k) for k in range(6, 13))
print("P(>=6)=", float(P))
# 任意一种手势 >=6 的概率（多重比较）
import random
rng = random.Random(1); N = 200000; hit = 0
for _ in range(N):
    c = Counter(rng.randrange(3) for _ in range(12))
    if max(c.values()) >= 6: hit += 1
print("任一手势>=6 模拟", hit / N)
# 精确
cnt = 0; tot = 0
for a in range(13):
    for b in range(13 - a):
        c = 12 - a - b
        ways = comb(12, a) * comb(12 - a, b)
        tot += ways
        if max(a, b, c) >= 6: cnt += ways
print("任一手势>=6 精确", cnt / tot, F(cnt, tot))

print("== C06.2 三张牌比大小")
orders = list(itertools.permutations((1, 2, 3)))
def result(me, op):
    w = sum(1 for a, b in zip(me, op) if a > b); l = sum(1 for a, b in zip(me, op) if a < b)
    return 1 if w > l else (-1 if w < l else 0)
print("对 3,2,1:", {o: result(o, (3, 2, 1)) for o in orders})
for o in orders:
    rs = [result(o, op) for op in orders]
    print(o, "对随机: 胜", rs.count(1), "平", rs.count(0), "负", rs.count(-1), "/6")
print("对 (1,3,2) 的结果:", {o: result(o, (1, 3, 2)) for o in orders})
print("我出(1,3,2)时对手各顺序结果(对手视角):", {op: -result((1, 3, 2), op) for op in orders})

print("== C07.2 花色奖励 末轮")
SUITS = 'SHDC'
def score(cards):
    s = sum(v for _, v in cards)
    cnt = Counter(su for su, _ in cards)
    return s + 3 * sum(1 for x in cnt.values() if x >= 3)
me = [('H', 2), ('H', 5), ('S', 4), ('C', 3)]
op = [('D', 6), ('D', 5), ('S', 1), ('S', 2)]
market = [('H', 1), ('D', 4), ('S', 6)]
print("我", score(me), "对手", score(op))
allc = [(s, v) for s in SUITS for v in range(1, 7)]
def deck_after(bought):
    used = set(me) | set(op) | set(market)
    return [c for c in allc if c not in used]
deck = deck_after(None); print("牌堆张数", len(deck))
def opp_best(op_cards, coins, mk):
    # 对手（后手、最后行动）能达到的最高分
    best = score(op_cards)
    for c in mk:
        if c[1] <= coins: best = max(best, score(op_cards + [c]))
    return best
for my_buy in [('H', 1), ('D', 4)]:
    for opc in (5, 3):
        mine = score(me + [my_buy])
        rest = [c for c in market if c != my_buy]
        win = 0
        for x in deck:
            ob = opp_best(op, opc, rest + [x])
            if mine > ob: win += 1   # 平分后手（对手）胜
        print("我买", my_buy, "我分", mine, "对手收入后币", opc, "我胜概率", F(win, len(deck)))
# 我进货（不买）
for opc in (5, 3):
    mine = score(me); win = 0
    for x in [None]:
        ob = opp_best(op, opc, market)
        print("进货: 我", mine, "对手最好", ob)

print("== 账本可达性检查（小集市 v1，给定最终面前牌、已行动轮数、当前币数）")
def ledger(final_cards, rounds_done, coins_before_income):
    final = sorted(final_cards)
    sols = []
    def dfs(r, coins, owned, remaining, hist):
        if r == rounds_done:
            if not remaining and coins == coins_before_income: sols.append(hist)
            return
        coins += len(owned)
        dfs(r + 1, coins + 2, owned, remaining, hist + ['进货'])
        for v in set(remaining):
            if v <= coins:
                rem = list(remaining); rem.remove(v)
                dfs(r + 1, coins - v, owned + [v], rem, hist + [f'买{v}'])
    dfs(0, 3, [], final, [])
    return sols
for name, cards, coins in [('我 C07.2', [2, 5, 4, 3], 0), ('对手 C07.2', [6, 5, 1, 2], 1)]:
    s = ledger(cards, 5, coins); print(name, len(s), s[:2])
for name, cards, coins in [('对手 C07.2 (3币版)', [6, 5, 1, 2], None)]:
    pass
s = ledger([6, 5, 1, 2], 5, -1)

print("== C08.2 末轮：先手买 4 到 15 还是买 1 卡位")
# 局面：第6轮，你先手，收入后 5 币；你面前 6,3,2 (11分)；对手 6,5,2 (13分)，对手收入前 1 币（收入后 4）
me_cards = [6, 3, 2]; op_cards = [6, 5, 2]; mk = [4, 2, 1]
seen = Counter(me_cards + op_cards + mk)
deckc = Counter({v: 4 for v in range(1, 7)}); deckc.subtract(seen)
deckl = list(deckc.elements()); print("牌堆", dict(deckc), len(deckl))
def p_win(my_buy, opc=4):
    mine = sum(me_cards) + (my_buy or 0)
    rest = list(mk)
    if my_buy: rest.remove(my_buy)
    win = 0
    for x in deckl if my_buy else [None]:
        m2 = rest + ([x] if x else [])
        ob = sum(op_cards) + max([v for v in m2 if v <= opc] + [0])
        # 进货也可以，但不加分
        # 游戏是否结束：若双方都 <15，继续——这里只算本轮结束时
        if mine >= 15 or ob >= 15:
            if mine > ob: win += 1
        else:
            win += F(1, 2)  # 未结束，记为未定（单独报告）
    return F(win, len(deckl) if my_buy else 1)
for b in (4, 2, 1):
    print("买", b, "本轮结束时胜率(未结束记1/2):", p_win(b), float(p_win(b)))
for b in (4,):
    print(" 对手收入后 5 币时 买4:", p_win(b, 5))
