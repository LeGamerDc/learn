"""Search small 四次经营·大订单 variants for exercise 7 sample answer. python3 -I variant_search.py"""
from functools import lru_cache
from itertools import product
def make(big, sell, startB, tie=0.5, n=4):
    @lru_cache(None)
    def v(turn, ca, sa, cb, sb, avail):
        if turn == 2 * n: return 1.0 if sa > sb else (tie if sa == sb else 0.0)
        me = turn % 2; k = turn // 2
        c, s = (ca, sa) if me == 0 else (cb, sb)
        mv = [(c + 2, s, avail)]
        if c >= 2: mv.append((c - 2, s + sell[k], avail))
        if c >= 4 and avail: mv.append((c - 4, s + big, False))
        vals = [v(turn + 1, c2, s2, cb, sb, av) if me == 0 else v(turn + 1, ca, sa, c2, s2, av) for c2, s2, av in mv]
        return max(vals) if me == 0 else min(vals)
    return v(0, 0, 0, startB, 0, True)
def route(rA, rB, big, sell, startB, n=4):
    st = {'A': [0, 0], 'B': [startB, 0]}; avail = True
    for turn in range(2 * n):
        p = 'AB'[turn % 2]; r = (rA, rB)[turn % 2]; k = turn // 2; c, s = st[p]
        if r == 'R': m = 'S' if c >= 2 else 'H'
        else:
            if avail and c >= 4: m = 'O'
            elif not avail and c >= 2: m = 'S'
            else: m = 'H'
        if m == 'H': c += 2
        elif m == 'S': c -= 2; s += sell[k]
        else: c -= 4; s += big; avail = False
        st[p] = [c, s]
    return st['A'][1], st['B'][1]
for big, startB, sell in product((6, 7, 8, 9), (0, 1, 2), ((3, 3, 3, 3), (3, 3, 2, 2), (4, 3, 2, 1))):
    val = make(big, sell, startB)
    m = {(a, b): route(a, b, big, sell, startB) for a in 'RB' for b in 'RB'}
    print(big, startB, sell, 'SPE A', val, m)
