# 《小集市》v1 续局模拟器（附录 C 用）
# 规则：A~6 各 4 张；市场 3 张；收入=面前张数；动作：进货+2 或买牌（点数=价格=分数）后从牌堆补 1 张；
# 每轮（后手行动完）检查，若有人 >=15 结束，高分胜，平分后手胜。牌堆空不补。
import random
from collections import Counter

def pol_E(k):
    def f(me, op, market, rnd):
        aff = [v for v in market if v <= me['c']]
        if not aff: return None
        return min(aff) if len(me['cards']) < k else max(aff)
    return f
def pol_G(me, op, market, rnd):
    aff = [v for v in market if v <= me['c']]
    return max(aff) if aff else None
POL = {'E2': pol_E(2), 'E3': pol_E(3), 'G': pol_G}

def full_deck():
    return [v for v in range(1, 7) for _ in range(4)]

def play_from(state, policies, rng, max_round=40):
    """state: dict(round, turn(0=先手待行动/1=后手待行动), stage('income'/'action'),
    p=[{'c':coins,'cards':[...]}, ...], market=[...]). deck = 其余牌随机。
    返回胜者 0(先手)/1(后手)。"""
    p = [{'c': s['c'], 'cards': list(s['cards'])} for s in state['p']]
    market = list(state['market'])
    used = Counter(market)
    for s in p: used.update(s['cards'])
    deck = Counter({v: 4 for v in range(1, 7)}); deck.subtract(used)
    assert all(x >= 0 for x in deck.values()), deck
    deck = list(deck.elements()); rng.shuffle(deck)
    rnd = state['round']; turn = state['turn']; stage = state['stage']
    while True:
        while turn < 2:
            me = p[turn]
            if stage == 'income':
                me['c'] += len(me['cards'])
            stage = 'income'
            if 'forced' in state and state['forced'] is not None:
                choice = state['forced']; state = dict(state); state['forced'] = None
            else:
                choice = policies[turn](me, p[1 - turn], market, rnd)
            if choice is None or choice == 'pass' or me['c'] < choice:
                me['c'] += 2
            else:
                market.remove(choice); me['c'] -= choice; me['cards'].append(choice)
                if deck: market.append(deck.pop())
            turn += 1
        sc = [sum(x['cards']) for x in p]
        if max(sc) >= 15 or rnd >= max_round or (not market and not deck):
            return 0 if sc[0] > sc[1] else 1
        rnd += 1; turn = 0

def evaluate(state, actions, n=20000, seed=1, me=None):
    """对'当前行动者'的各候选动作，双方续局分别用 E2/E3/G 的 9 种组合，返回每个动作的胜率区间与平均。"""
    me = state['turn'] if me is None else me
    out = {}
    for a in actions:
        rates = []
        for mine in POL:
            for theirs in POL:
                pols = [None, None]; pols[me] = POL[mine]; pols[1 - me] = POL[theirs]
                rng = random.Random(seed)
                st = dict(state); st['forced'] = a
                w = sum(1 for _ in range(n) if play_from(st, pols, rng) == me)
                rates.append(w / n)
        out[a] = (min(rates), max(rates), sum(rates) / len(rates))
    return out
