"""ch16 rewrite: independent exact solve of take-away and 'no repeat of opponent's last take' variants.
Rule: normal play (taking last coin wins); a player with no legal move loses; no overdraw, no pass.
python3 -I takeaway_rewrite.py"""
from functools import lru_cache
from fractions import Fraction as F
from math import prod

def legal(n, last, K, var):
    return [k for k in range(1, K + 1) if k <= n and not (var and k == last)]

@lru_cache(None)
def W(n, last, K, var):  # True: player to move wins
    return any(not W(n - k, k if var else 0, K, var) for k in legal(n, last, K, var))

def paths(n, last, K, var):
    ms = legal(n, last, K, var)
    if not ms: return [()]
    return [(k,) + t for k in ms for t in paths(n - k, k if var else 0, K, var)]

def stats(n, K, var):
    P = paths(n, 0, K, var)
    # choice nodes along a path: nodes with >=2 legal moves
    def choices(path):
        c = 0; m = n; last = 0
        for k in path:
            if len(legal(m, last, K, var)) >= 2: c += 1
            m -= k; last = k if var else 0
        return c
    reach = set()
    def visit(m, last):
        if (m, last) in reach: return
        reach.add((m, last))
        for k in legal(m, last, K, var): visit(m - k, k if var else 0)
    visit(n, 0)
    branch_states = sum(1 for (m, l) in reach if len(legal(m, l, K, var)) >= 2)
    return dict(paths=len(P), max_choices=max(map(choices, P)), min_choices=min(map(choices, P)),
                lengths=(min(map(len, P)), max(map(len, P))), reach=len(reach), branch_states=branch_states)

# --- K=2 (take 1 or 2) ---
print('K=2 table n: orig | var start, last1, last2')
for n in range(0, 13):
    print(n, int(W(n, 0, 2, False)), '|', int(W(n, 0, 2, True)), int(W(n, 1, 2, True)), int(W(n, 2, 2, True)))
for n in range(0, 600):
    assert W(n, 0, 2, False) == (n % 3 != 0)
    assert W(n, 0, 2, True) == (n % 3 != 0)
    assert W(n, 1, 2, True) == (n % 3 == 2)
    assert W(n, 2, 2, True) == (n % 3 != 0)
s0, s1 = stats(7, 2, False), stats(7, 2, True)
print('n=7 orig', s0); print('n=7 var', s1)
assert s0['paths'] == 21 and s1['paths'] == 2
assert s0['max_choices'] == 6 and s1['max_choices'] == 1
assert s0['lengths'] == (4, 7) and s1['lengths'] == (4, 5)
assert s0['reach'] == 8 and s1['reach'] == 10
assert paths(7, 0, 2, True) == [(1, 2, 1, 2, 1), (2, 1, 2, 1)]
# first-move rule in the variant: n%3==1 -> take 1 only; n%3==2 -> both win; n%3==0 -> both lose
for n in range(1, 300):
    good = [k for k in legal(n, 0, 2, True) if not W(n - k, k, 2, True)]
    assert good == ([] if n % 3 == 0 else [1] if n % 3 == 1 else [1, 2])
# original: n%3==2 -> only take 2 wins
for n in range(2, 300):
    good = [k for k in legal(n, 0, 2, False) if not W(n - k, 0, 2, False)]
    assert good == ([] if n % 3 == 0 else [n % 3])
# exercise positions
assert paths(8, 0, 2, True) == [(1, 2, 1, 2, 1), (2, 1, 2, 1, 2)]
assert paths(9, 0, 2, True) == [(1, 2, 1, 2, 1, 2), (2, 1, 2, 1, 2, 1)]
assert paths(4, 2, 2, True) == [(1, 2, 1)] and paths(4, 1, 2, True) == [(2, 1)]
assert not W(1, 1, 2, True) and W(1, 2, 2, True)
print('K=2 reductions', F(19, 21), F(5, 6), 'reach +', F(2, 8))

# --- K=3 contrast (take 1..3) ---
print('\nK=3: n orig | var start last1 last2 last3')
rows = []
for n in range(0, 25):
    r = (int(W(n, 0, 3, False)), int(W(n, 0, 3, True)), int(W(n, 1, 3, True)), int(W(n, 2, 3, True)), int(W(n, 3, 3, True)))
    rows.append(r); print(n, r)
for n in range(0, 400): assert W(n, 0, 3, False) == (n % 4 != 0)
# find period of variant
def col(l): return [int(W(n, l, 3, True)) for n in range(0, 400)]
for l in (0, 1, 2, 3):
    c = col(l)
    per = next(p for p in range(1, 60) if all(c[i] == c[i + p] for i in range(30, 300)))
    print('last', l, 'period', per, 'losing n<30:', [n for n in range(30) if not c[n]])
for n in (7, 10, 12):
    print('n', n, 'K3 orig', stats(n, 3, False), '\n      var', stats(n, 3, True))
# winning first moves K=3 variant
print('K3 var winning first moves', {n: [k for k in legal(n, 0, 3, True) if not W(n - k, k, 3, True)] for n in range(1, 25)})
print('K3 orig winning first moves', {n: [k for k in legal(n, 0, 3, False) if not W(n - k, 0, 3, False)] for n in range(1, 25)})

# --- positions where the old heuristic (leave a multiple of 4) is impossible or wrong in K=3 variant ---
print('\nK3 variant mid-game positions (n,last): legal, winning moves, old-heuristic move')
for n in range(1, 14):
    for l in (1, 2, 3):
        lg = legal(n, l, 3, True)
        win = [k for k in lg if not W(n - k, k, 3, True)]
        old = n % 4 if n % 4 else None
        flag = ''
        if old is not None and old not in lg: flag = 'OLD-BANNED'
        elif old is not None and old not in win: flag = 'OLD-WRONG'
        elif old is None and win: flag = 'OLD-SAYS-LOST-BUT-WIN'
        print((n, l), lg, 'win', win, 'old', old, flag)

# --- rereview: closed-form losing set for K=3 variant, plus the proof's two lemmas ---
import sys
sys.setrecursionlimit(10000)
def in_L(n, l): r = n % 4; return r == 0 or (r == l and l in (1, 3))
for n in range(0, 1001):
    for l in (0, 1, 2, 3):
        assert W(n, l, 3, True) == (not in_L(n, l)), (n, l)
        succ = [(n - k, k) for k in legal(n, l, 3, True)]
        if in_L(n, l): assert all(not in_L(*s) for s in succ)   # lemma 1
        else: assert any(in_L(*s) for s in succ)                # lemma 2
# after the opening, n>=3 implies exactly two legal numbers
for n in range(0, 50):
    for l in (1, 2, 3): assert n < 3 or len(legal(n, l, 3, True)) == 2
# counterexample to 'opponent's needed number banned is enough': (8,last1) take 2 -> (6,2) still winning for mover
assert W(6, 2, 3, True) and not W(5, 1, 3, True) and not W(3, 3, 3, True)
# thinking path 16.2: (4, any last) is a loss for mover
assert all(not W(4, l, 3, True) for l in (0, 1, 2, 3))
assert W(10, 2, 3, True) and not W(9, 1, 3, True) and not W(8, 3, 3, True)
print('K=3 variant closed form + proof lemmas verified to n=1000')
