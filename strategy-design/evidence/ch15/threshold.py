"""Exercise: raise end threshold 15 -> 25; deck has 84 points total, so check feasibility. python3 -I threshold.py"""
import random
from itertools import product
import importlib.util, os, sys
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('m', os.path.join(here, 'market_rewrite.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def game(p0, p1, deck, goal, cap=60):
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
        if max(sc) >= goal or (not mk):
            return (0 if sc[0] > sc[1] else 1), rnd
    return None, cap
decks = m.decks[:5000]
for goal in (15, 20, 25):
    out = {}
    for a, b in [('E5', 'E2'), ('G', 'E2'), ('E3', 'E2'), ('H', 'E2')]:
        w = t = 0; R = []; st = 0
        for d in decks:
            for seat, (x, y) in ((0, (a, b)), (1, (b, a))):
                win, r = game(x, y, d, goal)
                if win is None: st += 1; continue
                t += 1; w += (win == seat); R.append(r)
        out[a] = (round(100 * w / t, 1), round(sum(R) / len(R), 2), st)
    print('goal', goal, out)
