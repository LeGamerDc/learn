# 附录 C：C24.3《小牌库》每回合抽 k 张时，买银 / 买绿的转折点（精确动态规划）
# 规则同 C24.2：每回合洗全部牌抽 k 张，钱 ≥3 时最多买一张：银（产 2）或绿（+2 分，产 0）；铜产 1。
# 起点：6 铜 + 1 绿，本回合有 3 币。用法：python3 -I evidence/appC/c24_draw.py
from itertools import combinations
from functools import lru_cache
from fractions import Fraction as F
from collections import Counter
from math import comb

VAL = {'铜': 1, '银': 2, '绿': 0}
def solve(k):
    def money_dist(c, s, g):
        cards = ['铜'] * c + ['银'] * s + ['绿'] * g; n = len(cards)
        kk = min(k, n); d = Counter()
        for h in combinations(range(n), kk):
            d[sum(VAL[cards[i]] for i in h)] += 1
        t = comb(n, kk)
        return {m: F(v, t) for m, v in d.items()}
    @lru_cache(None)
    def V(c, s, g, T):
        if T == 0: return F(0)
        ev = F(0)
        for m, p in money_dist(c, s, g).items():
            opts = [V(c, s, g, T - 1)]
            if m >= 3:
                opts += [V(c, s + 1, g, T - 1), 2 + V(c, s, g + 1, T - 1)]
            ev += p * max(opts)
        return ev
    return {T: (float(V(6, 1, 1, T - 1)), float(2 + V(6, 0, 2, T - 1))) for T in range(2, 9)}

for k in (3, 4):
    print(f'每回合抽 {k} 张：剩 T 回合（含本回合）时 买银 / 买绿 之后的期望总分')
    for T, (silver, green) in solve(k).items():
        print(f'  T={T}: 银 {silver:.2f}  绿 {green:.2f}  -> {"银" if silver > green else "绿"}')
