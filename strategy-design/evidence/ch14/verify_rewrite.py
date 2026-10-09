"""Chapter 14 rewrite checks (Claude). Run: python3 -I verify_rewrite.py"""
from fractions import Fraction as F
from itertools import product

# ---- 14.1 rescue -------------------------------------------------------
def rescue(vn, vs, ask_cost=0, fuel=6):
    worlds = [(4, 4), (8, 4)]  # (north cost, south cost), equiprobable
    pay = lambda t, w: (vn, vs)[t] if w[t] <= fuel else 0
    blind = [sum(F(pay(t, w), 2) for w in worlds) for t in (0, 1)]
    asked = sum(F(max(pay(t, w) for t in (0, 1)), 2) for w in worlds) - ask_cost
    return blind, asked
b, a = rescue(8, 5)
assert b == [4, 5] and a == F(13, 2)
b, a = rescue(8, 5, ask_cost=2); assert a == F(9, 2) and max(b) == 5      # don't ask
b, a = rescue(12, 5, ask_cost=2); assert b == [6, 5] and a == F(13, 2)  # ask (6.5 > 6)
b, a = rescue(12, 5); assert b == [6, 5] and a == F(17, 2)
# threshold for asking with cost 2 as function of north value v (south 5): ask iff (v+5)/2-2 > max(v/2,5)
for v in range(0, 30):
    _, a = rescue(v, 5, 2); bl = max(rescue(v, 5)[0])
    if v < 9: assert a <= bl, v
    if v > 9: assert a > bl, v
assert rescue(9, 5, 2)[1] == max(rescue(9, 5)[0])  # v=9: 5 vs 5 tie
# review point: "if reachable you must pick the asked station" never lowers optimum, any nonneg values
for vn, vs in product(range(0, 15), repeat=2):
    worlds = [(4, 4), (8, 4)]
    pay = lambda t, w: (vn, vs)[t] if w[t] <= 6 else 0
    free = sum(F(max(pay(t, w) for t in (0, 1)), 2) for w in worlds)
    # constrained: ask north -> if yes must go north; if no free choice. ask south -> south always reachable -> must go south
    ask_n = sum(F(pay(0, w) if w[0] <= 6 else max(pay(t, w) for t in (0, 1)), 2) for w in worlds)
    blind = max(sum(F(pay(t, w), 2) for w in worlds) for t in (0, 1))
    best = max(ask_n, vs, blind)
    assert best == free, (vn, vs)
print('rescue ok')

# ---- PD tournament (12 rounds) --------------------------------------
PAY = {('C','C'):(3,3),('C','D'):(0,5),('D','C'):(5,0),('D','D'):(1,1)}
def mv(n, mine, oth):
    return {'C': 'C', 'D': 'D', 'TFT': oth[-1] if oth else 'C',
            'GRIM': 'D' if 'D' in oth else 'C', 'ALT': 'C' if len(mine) % 2 == 0 else 'D'}[n]
def match(x, y, n=12):
    hx, hy, sx, sy = [], [], 0, 0
    for _ in range(n):
        a, b = mv(x, hx, hy), mv(y, hy, hx)
        p, q = PAY[a, b]; sx += p; sy += q; hx.append(a); hy.append(b)
    return sx, sy
names = ['C', 'D', 'TFT', 'GRIM', 'ALT']
M = {(x, y): match(x, y)[0] for x in names for y in names}
for x in names: print(x, [M[x, y] for y in names], sum(M[x, y] for y in names))
assert [sum(M[x, y] for y in names) for x in names] == [126, 140, 147, 152, 124]
assert match('TFT', 'D') == (11, 16) and match('TFT', 'ALT') == (28, 33) and match('GRIM', 'ALT') == (33, 13)
assert M['TFT','C'] + M['TFT','D'] == 47 and M['D','C'] + M['D','D'] == 72
# drop ALT from pool: TFT vs GRIM tie?
pool = ['C', 'D', 'TFT', 'GRIM']
tot = {x: sum(M[x, y] for y in pool) for x in names}
print('pool without ALT', tot)
assert tot['TFT'] == tot['GRIM'] == 119 and tot['D'] == 104
# noisy: one misread. TFT vs TFT where round 5 player A's C is seen/played as D (A plays D once by mistake)
def match_err(x, y, err_round, n=12):
    hx, hy, sx, sy = [], [], 0, 0
    for r in range(n):
        a, b = mv(x, hx, hy), mv(y, hy, hx)
        if r == err_round: a = 'D'
        p, q = PAY[a, b]; sx += p; sy += q; hx.append(a); hy.append(b)
    return sx, sy, ''.join(hx), ''.join(hy)
e = match_err('TFT', 'TFT', 4); print('TFT pair, A slips round 5', e)
g = match_err('GRIM', 'GRIM', 4); print('GRIM pair, A slips round 5', g)
assert e[:2] == (32, 32) and g[:2] == (23, 23)
assert 12 + 4*(5+0) == 32 and 12 + 5 + 0 + 6 == 23

# ---- 14.2 last two rounds -------------------------------------------
# opponent A: TFT; B: TFT but defects in round 12; C: defects rounds 11 and 12.
def last_two(me, opp):  # me: (r11, r12); history r10 both C
    my10 = 'C'
    o11 = {'A': my10, 'B': my10, 'C': 'D'}[opp]
    o12 = {'A': me[0], 'B': 'D', 'C': 'D'}[opp]
    return PAY[me[0], o11][0] + PAY[me[1], o12][0]
tab = {(m, o): last_two(m, o) for m in product('CD', repeat=2) for o in 'ABC'}
for m in product('CD', repeat=2): print(''.join(m), [tab[m, o] for o in 'ABC'])
assert [tab[('C','D'), o] for o in 'ABC'] == [8, 4, 1]
assert [tab[('D','D'), o] for o in 'ABC'] == [6, 6, 2]
assert [tab[('C','C'), o] for o in 'ABC'] == [6, 3, 0]
assert [tab[('D','C'), o] for o in 'ABC'] == [5, 5, 1]
# round 12: D dominates C for each fixed opponent r12 action
for o in 'CD': assert PAY['D', o][0] > PAY['C', o][0]
# EV with p = P(B), A otherwise: CD = 8-4p, DD = 6
for p in [F(0), F(1, 4), F(1, 2), F(3, 4), F(1)]:
    cd = (1 - p) * 8 + p * 4; dd = 6
    assert cd == 8 - 4 * p
    assert (cd > dd) == (p < F(1, 2))
# with three types pA,pB,pC: CD = 8pA+4pB+1pC ; DD = 6pA+6pB+2pC
pA, pB, pC = F(1, 2), F(1, 4), F(1, 4)
assert 8*pA + 4*pB + pC == F(21, 4) and 6*pA + 6*pB + 2*pC == F(5)
print('last two ok')

# ---- discount threshold ------------------------------------------------
for d in [F(k, 20) for k in range(0, 20)]:
    assert (3 / (1 - d) >= 5 + d / (1 - d)) == (d >= F(1, 2))
# continuation probability interpretation: expected remaining rounds 1/(1-d); d=1/2 -> 2 rounds
assert 1 / (1 - F(1, 2)) == 2

# ---- bargaining ----------------------------------------------------------
weak = [(x, 12 - x) for x in range(13) if x >= 4 and 12 - x >= 3]
strict = [(x, 12 - x) for x in range(13) if x > 4 and 12 - x > 3]
assert weak == [(x, 12 - x) for x in range(4, 10)] and len(weak) == 6
assert strict == [(5, 7), (6, 6), (7, 5), (8, 4)]
# split-the-surplus: surplus 5 -> 2.5 each -> (6.5, 5.5) not integer; integer near: (6,6) or (7,5)
assert 12 - 4 - 3 == 5 and F(4) + F(5, 2) == F(13, 2)

# ---- Catan BATNA arithmetic ------------------------------------------
assert 4 == 4 and 3 < 4  # bank 4:1, generic port 3:1

# ---- Pandemic clock (2013 rulebook: 48 city + 5 event; 2p deal 4 each) ----
def clock(players_cards, epidemics):
    deck = 48 + 5 - players_cards + epidemics
    full_draws = deck // 2
    return deck, full_draws, full_draws + 1  # turns in which actions are taken
assert clock(8, 5) == (50, 25, 26)
assert clock(8, 4) == (49, 24, 25)
assert clock(8, 6) == (51, 25, 26)
assert 26 * 4 == 104 and 26 // 2 == 13
print('all ch14 rewrite checks passed')

# ---- rereview fixes (2026-10-09) -------------------------------------
# info value formula: asked = (max(v,5)+5)/2 - cost ; free info value plateaus at 2.5 for v>=10
for v in range(0, 40):
    _, a = rescue(v, 5); bl = max(rescue(v, 5)[0])
    assert a == F(max(v, 5) + 5, 2)
    val = a - bl
    if v <= 5: assert val == 0
    elif v <= 10: assert val == F(v - 5, 2)
    else: assert val == F(5, 2)
# exercise 7 values 6,8,10,12 with cost 2: ask only at 10,12
assert [rescue(v, 5, 2)[1] > max(rescue(v, 5)[0]) for v in (6, 8, 10, 12)] == [False, False, True, True]
# TFT vs ALT breakdown: rounds where TFT gets 0 are exactly the ALT-defect rounds
_, _, h_t, h_a = (lambda r: r)(match_err('TFT', 'ALT', -1))
per = [PAY[x, y][0] for x, y in zip(h_t, h_a)]
assert per == [3] + [0, 5] * 5 + [0] and sum(per) == 28 == 3 + 5*5 + 6*0
_, _, h_g, h_a2 = match_err('GRIM', 'ALT', -1)
per_g = [PAY[x, y][0] for x, y in zip(h_g, h_a2)]
assert per_g == [3, 0] + [5, 1] * 5 and sum(per_g) == 33 == 3 + 0 + 5*5 + 5*1
# GRIM pair with slip in round 5: round 6 A=C, B=D; from round 7 both D
g = match_err('GRIM', 'GRIM', 4)
assert g[2] == 'CCCCDC' + 'D' * 6 and g[3] == 'CCCCCD' + 'D' * 6
print('rereview checks passed')
