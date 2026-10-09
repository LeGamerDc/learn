"""Independent re-implementation of 小集市 v1 fixed-policy round robin (Claude, ch15 rewrite).
Rules per BRIEF §10: 24 cards A-6 x4, market 3, start 3 coins; income = #cards; action: +2 coins or buy
(cost=value) and refill into same slot if deck non-empty; end after seat 1 acts if anyone >=15; tie -> seat 1.
Policies look only at own cards/cash and the market. Ties between equal values -> leftmost.
Run: python3 -I market_rewrite.py
"""
import random, sys
from itertools import product
from collections import Counter

def pick(pol, n, cash, mk):
    idx = [i for i, v in enumerate(mk) if v <= cash]
    if pol == 'H': idx = [i for i in idx if mk[i] >= 5]
    if pol == 'N': return None
    if not idx: return None
    if pol == 'L': cheap = True
    elif pol in ('G', 'H'): cheap = False
    else: cheap = n < int(pol[1:])
    key = (lambda i: (mk[i], i)) if cheap else (lambda i: (-mk[i], i))
    return min(idx, key=key)

def game(p0, p1, deck, cap=40):
    deck = list(deck); mk = deck[:3]; deck = deck[3:]
    cash = [3, 3]; cards = [[], []]; pol = (p0, p1)
    for rnd in range(1, cap + 1):
        for s in (0, 1):
            cash[s] += len(cards[s])
            i = pick(pol[s], len(cards[s]), cash[s], mk)
            if i is None: cash[s] += 2
            else:
                v = mk[i]; cash[s] -= v; cards[s].append(v)
                if deck: mk[i] = deck.pop(0)
                else: mk.pop(i)
        sc = (sum(cards[0]), sum(cards[1]))
        if max(sc) >= 15:
            return (0 if sc[0] > sc[1] else 1), rnd, cash, cards
    return None, cap, cash, cards

rng = random.Random(20261007)
N = 20000
decks = []
for _ in range(N):
    d = [v for v in range(1, 7) for _ in range(4)]; rng.shuffle(d); decks.append(d)

if __name__ == '__main__':
    POL = ['E2', 'E3', 'G', 'H', 'E5', 'L']
    T = {}; stalls = Counter(); rounds = []
    for a, b in product(POL, repeat=2):
        if a == b == 'H': continue
        w = t = 0
        for d in decks:
            for seat, (x, y) in ((0, (a, b)), (1, (b, a))):
                win, r, _, _ = game(x, y, d)
                if win is None: stalls[a, b] += 1; continue
                t += 1; w += (win == seat); rounds.append(r)
        T[a, b] = 100 * w / t
    print('row win% (seat balanced, 2N games each)')
    print('     ' + ''.join(f'{b:>8s}' for b in POL))
    for a in POL:
        print(f'{a:4s} ' + ''.join(f'{T.get((a, b), float("nan")):8.2f}' for b in POL))
    print('stalls', dict(stalls))
    print('avg rounds', sum(rounds) / len(rounds))
    for p in ['E2', 'E3', 'G', 'E5', 'L']:
        res = [game(p, p, d) for d in decks]
        print('mirror', p, 'seat0 win%', round(100 * sum(r[0] == 0 for r in res) / N, 2),
              'avg rounds', round(sum(r[1] for r in res) / N, 2), Counter(r[1] for r in res).most_common(4))
    hh = [game('H', 'H', d) for d in decks]
    print('H mirror stall (>40 rounds)', sum(r[0] is None for r in hh) / N)
    # how often the initial market has no 5/6
    from math import comb
    print('initial market all <5', comb(16, 3), comb(24, 3), comb(16, 3) / comb(24, 3))
    # H vs N (never buys): does it end?
    hn = [game('H', 'N', d) for d in decks[:2000]]
    print('H vs N stall', sum(r[0] is None for r in hn) / 2000)
