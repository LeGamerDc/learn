"""ch15 rewrite: exact small models. python3 -I small_rewrite.py"""
from itertools import product
from functools import lru_cache
from fractions import Fraction as F
from collections import Counter

# ---------- 15.1 四次经营 (solo, no interaction) ----------
def run(seq, sell=3, conv=None):
    cash = score = 0
    for a in seq:
        if a == 'H': cash += 2
        else:
            if cash < 2: return None
            cash -= 2; score += sell
    return cash, score + (cash // 2 if conv else 0)
legal = {''.join(s): run(s) for s in product('HS', repeat=4) if run(s)}
print('legal 4-action plans', legal)
assert len(legal) == 6
assert sorted(k for k, v in legal.items() if v[1] == 6) == ['HHSS', 'HSHS']
assert legal['HHHH'] == (8, 0)
for T in range(1, 9):
    L = {''.join(s): run(s) for s in product('HS', repeat=T) if run(s)}
    best = max(v[1] for v in L.values())
    assert best == 3 * (T // 2)
    assert L['H' * T][1] == 0
    Lc = {''.join(s): run(s, conv=True) for s in product('HS', repeat=T) if run(s)}
    bc = max(v[1] for v in Lc.values())
    hoard = Lc['H' * T][1]
    print('T', T, 'best', best, 'with conversion best', bc, 'hoard', hoard,
          'optimal plans', sorted(k for k, v in Lc.items() if v[1] == bc))
    if T >= 2: assert hoard < bc
    else: assert hoard == bc == 1
# number of optimal orderings with T=4 (no conversion): 2 ; T=6: count
L6 = {''.join(s): run(s) for s in product('HS', repeat=6) if run(s)}
print('T=6 optimal', sorted(k for k, v in L6.items() if v[1] == 9))

# ---------- 大订单 variant: two players alternate A,B,A,B... 4 actions each ----------
# actions: H +2c; S pay2 ->3; O pay4 -> big (one card only, first come)
def solve(big=8, sell=(3, 3, 3, 3), tie=0.5):
    # sell[k] = retail points at player's k-th action (0-based)
    @lru_cache(None)
    def v(turn, ca, sa, cb, sb, avail):
        # returns value for A in [0,1] (win=1, draw=tie)
        if turn == 8:
            return 1.0 if sa > sb else (tie if sa == sb else 0.0)
        me = turn % 2; k = turn // 2
        opts = []
        c, s = (ca, sa) if me == 0 else (cb, sb)
        moves = [('H', c + 2, s, avail)]
        if c >= 2: moves.append(('S', c - 2, s + sell[k], avail))
        if c >= 4 and avail: moves.append(('O', c - 4, s + big, False))
        for m, c2, s2, av in moves:
            if me == 0: val = v(turn + 1, c2, s2, cb, sb, av)
            else: val = v(turn + 1, ca, sa, c2, s2, av)
            opts.append((val, m))
        return max(opts)[0] if me == 0 else min(opts)[0]
    return v(0, 0, 0, 0, 0, True)
def route_play(rA, rB, big=8, sell=(3, 3, 3, 3)):
    # R: H S H S ; B: H H then O if available else S, then S if cash>=2 else H
    st = {'A': [0, 0], 'B': [0, 0]}; avail = True; log = []
    for turn in range(8):
        p = 'AB'[turn % 2]; r = (rA, rB)[turn % 2]; k = turn // 2
        c, s = st[p]
        if r == 'R': m = 'H' if k % 2 == 0 else 'S'
        else:
            if k < 2: m = 'H'
            elif avail and c >= 4: m = 'O'
            elif c >= 2: m = 'S'
            else: m = 'H'
        if m == 'H': c += 2
        elif m == 'S': c -= 2; s += sell[k]
        else: c -= 4; s += big; avail = False
        st[p] = [c, s]; log.append(p + m)
    return st['A'][1], st['B'][1], ' '.join(log)
for big, sell in [(8, (3, 3, 3, 3)), (8, (3, 3, 2, 2)), (7, (3, 3, 3, 3))]:
    print('variant big', big, 'sell', sell, 'A value (win=1,draw=.5)', solve(big, sell))
    for rA, rB in product('RB', repeat=2):
        print('  A', rA, 'B', rB, route_play(rA, rB, big, sell))

# ---------- complete strategies in 7-coin take-1-or-2, last coin wins ----------
def count_nodes(n=7):
    nodes = {0: [], 1: []}
    def rec(rem, player, hist):
        if rem == 0: return
        opts = [t for t in (1, 2) if t <= rem]
        nodes[player].append((hist, len(opts)))
        for t in opts: rec(rem - t, 1 - player, hist + (t,))
    rec(n, 0, ())
    return nodes
nd = count_nodes()
from math import prod
for pl in (0, 1):
    print('player', pl, 'decision nodes', len(nd[pl]), 'complete pure strategies', prod(o for _, o in nd[pl]))
# states (remaining coins) at which P1 can be to move
def p1_states(n=7):
    S = set()
    def rec(rem, player):
        if rem == 0: return
        if player == 0: S.add(rem)
        for t in (1, 2):
            if t <= rem: rec(rem - t, 1 - player)
    rec(n, 0); return sorted(S)
print('P1 states', p1_states(), 'state-based strategies', prod(2 if r >= 2 else 1 for r in p1_states()))

# ---------- tiny tree from section 2 (A: left/right; right -> B up/down -> A take/leave) ----------
assert 2 * 2 * 2 == 8

# ---------- 15.2 endgame (小集市 v1) ----------
rem = Counter({v: 4 for v in range(1, 7)})
rem.subtract([1, 3, 6, 2, 4, 5, 1, 5, 6])
assert [rem[v] for v in range(1, 7)] == [2, 3, 3, 3, 2, 2] and sum(rem.values()) == 15
def endgame(my_cash_after_income=6, opp_cash=2, my=10, opp=11, market=(1, 5, 6)):
    res = {}
    opts = ['H'] + [v for v in market if v <= my_cash_after_income]
    for a in opts:
        win = 0
        for draw, cnt in rem.items():
            mk = list(market); me = my
            if a != 'H':
                mk.remove(a); mk.append(draw); me += a
            oc = opp_cash + 3
            best = max([opp] + [opp + v for v in mk if v <= oc])
            # opponent wins if best >= me (tie -> second player) ; else if me>=15 game ends, I win
            if best >= me: pass
            elif me >= 15: win += cnt
            # if nobody reaches 15 the game continues -> count as not-a-win-now (separate)
        res[a] = F(win, 15)
    return res
r = endgame(); print('endgame', r)
assert r[5] == F(2, 3) and r[6] == 0 and r[1] == 0 and r['H'] == 0
r3 = endgame(opp_cash=3); print('opp cash 3', r3)
assert r3[5] == 0 and r3[6] == 0
# reachability witness (from draft verify): 5 rounds
mk = [1, 2, 6]; draws = iter([3, 4, 6, 5, 1, 5]); cash = [3, 3]; own = [[], []]
for acts in [(1, 2), (None, None), (3, 4), (None, None), (6, 5)]:
    for s, p in enumerate(acts):
        cash[s] += len(own[s])
        if p is None: cash[s] += 2
        else:
            assert cash[s] >= p and p in mk
            mk[mk.index(p)] = next(draws); cash[s] -= p; own[s].append(p)
    assert max(map(sum, own)) < 15
assert (cash, own, mk) == ([3, 2], [[1, 3, 6], [2, 4, 5]], [1, 5, 6])
print('witness: round 6 start, seat0 cash 3 -> income 3 -> 6; seat1 cash 2')
print('ok')

# ---------- how many of P1's 1024 history-based strategies guarantee a win? ----------
def p1_nodes(n=7):
    out = []
    def rec(rem, pl, h):
        if rem == 0: return
        opts = [t for t in (1, 2) if t <= rem]
        if pl == 0 and len(opts) == 2: out.append(h)
        for t in opts: rec(rem - t, 1 - pl, h + (t,))
    rec(n, 0, ()); return out
choice_nodes = p1_nodes()
assert len(choice_nodes) == 10
def wins_all(strat):
    # strat: dict history->take at 2-option nodes; P2 arbitrary
    def rec(rem, pl, h):
        if rem == 0: return pl == 1  # previous mover (P1 if now P2's turn) took last coin
        opts = [t for t in (1, 2) if t <= rem]
        if pl == 0:
            t = strat.get(h, 1) if len(opts) == 2 else 1
            return rec(rem - t, 1, h + (t,))
        return all(rec(rem - t, 0, h + (t,)) for t in opts)
    return rec(7, 0, ())
winning = 0
for bits in product((1, 2), repeat=10):
    s = dict(zip(choice_nodes, bits))
    winning += wins_all(s)
print('P1 complete strategies that always win', winning, 'of 1024')
