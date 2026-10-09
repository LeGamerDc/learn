# 附录 C：C11.3 拍卖先手——先手从起始 3 枚里付 b 枚（b = 0~3）时的先手胜率
# 规则同 ch15/market_rewrite.py（《小集市》v1，平分后手胜）；只改先手的起始硬币。
# 用法：python3 -I evidence/appC/c11_bid.py
import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ch15'))
import market_rewrite as m

def game(p0, p1, deck, start0, cap=40):
    deck = list(deck); mk = deck[:3]; deck = deck[3:]
    cash = [start0, 3]; cards = [[], []]; pol = (p0, p1)
    for rnd in range(1, cap + 1):
        for s in (0, 1):
            cash[s] += len(cards[s])
            i = m.pick(pol[s], len(cards[s]), cash[s], mk)
            if i is None: cash[s] += 2
            else:
                v = mk[i]; cash[s] -= v; cards[s].append(v)
                if deck: mk[i] = deck.pop(0)
                else: mk.pop(i)
        sc = (sum(cards[0]), sum(cards[1]))
        if max(sc) >= 15:
            return 0 if sc[0] > sc[1] else 1
    return None

POL = ['E2', 'E3', 'G']
print('先手胜率%（先手付 b 枚，起始 3-b；每格 2 万副牌）')
print('对局        ' + ''.join(f'  b={b}' for b in range(4)))
rows = [(p, p) for p in POL] + [('E2', 'E3'), ('E3', 'E2'), ('E2', 'G'), ('G', 'E2')]
for a, b_ in rows:
    out = []
    for b in range(4):
        res = [game(a, b_, d, 3 - b) for d in m.decks]
        done = [r for r in res if r is not None]
        out.append(100 * sum(r == 0 for r in done) / len(done))
    print(f'{a:>3s} 先 vs {b_:<3s}' + ''.join(f'{x:6.1f}' for x in out))

# 变体：出价付"终局分"而不是硬币——先手终局时 -k 分（终局判断仍按牌面点数 ≥15 触发）
def game_pts(p0, p1, deck, k, cap=40):
    deck = list(deck); mk = deck[:3]; deck = deck[3:]
    cash = [3, 3]; cards = [[], []]; pol = (p0, p1)
    for rnd in range(1, cap + 1):
        for s in (0, 1):
            cash[s] += len(cards[s])
            i = m.pick(pol[s], len(cards[s]), cash[s], mk)
            if i is None: cash[s] += 2
            else:
                v = mk[i]; cash[s] -= v; cards[s].append(v)
                if deck: mk[i] = deck.pop(0)
                else: mk.pop(i)
        sc = (sum(cards[0]), sum(cards[1]))
        if max(sc) >= 15:
            return 0 if sc[0] - k > sc[1] else 1
    return None

print()
print('变体：先手终局 -k 分时的先手胜率%')
print('对局        ' + ''.join(f'  k={k}' for k in range(4)))
for a, b_ in rows:
    out = []
    for k in range(4):
        res = [game_pts(a, b_, d, k) for d in m.decks]
        done = [r for r in res if r is not None]
        out.append(100 * sum(r == 0 for r in done) / len(done))
    print(f'{a:>3s} 先 vs {b_:<3s}' + ''.join(f'{x:6.1f}' for x in out))
