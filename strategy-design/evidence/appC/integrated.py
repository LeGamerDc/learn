# 附录 C 综合验收：《三岔口》(c) 的二项概率；《渔港》6 回合与 8 回合的全部动作序列枚举
# 用法：python3 -I evidence/appC/integrated.py
from itertools import product
from math import comb
from fractions import Fraction as F

p = F(1, 3)
print('三岔口 (c)：均衡下 10 回合走左 >= 6 次的概率',
      round(float(sum(comb(10, k) * p**k * (1 - p)**(10 - k) for k in range(6, 11))), 4))

def run(plan):
    """《渔港》单人账：出海 +3；修船 付 3，下回合起每回合 +2；卖鱼 付 2 得 1 分；订单 付 6 得 5 分。非法返回 None。"""
    c = b = pts = 0
    for a in plan:
        c += 2 * b
        if a == '海': c += 3
        elif a == '船':
            if c < 3: return None
            c -= 3; b += 1
        elif a == '鱼':
            if c < 2: return None
            c -= 2; pts += 1
        elif a == '单':
            if c < 6: return None
            c -= 6; pts += 5
    return pts

for T in (6, 8):
    res = [(run(pl), ''.join(pl)) for pl in product('海船鱼单', repeat=T)]
    res = [x for x in res if x[0] is not None]
    best = max(x[0] for x in res)
    tops = [x[1] for x in res if x[0] == best]
    print(f'渔港 {T} 回合：合法序列 {len(res)}，最高 {best} 分，{len(tops)} 种：{tops}')
    print('  带卖鱼的最高', max(x[0] for x in res if '鱼' in x[1]),
          '| 不卖鱼的最高', max(x[0] for x in res if '鱼' not in x[1]))
    for nb in range(4):
        xs = [x[0] for x in res if x[1].count('船') == nb]
        if xs: print(f'  修 {nb} 艘船的最高', max(xs))

# (c) 的另一种修法：保持 6 回合，每艘船每回合收入改为 3 币
def run3(plan):
    c = b = pts = 0
    for a in plan:
        c += 3 * b
        if a == '海': c += 3
        elif a == '船':
            if c < 3: return None
            c -= 3; b += 1
        elif a == '鱼':
            if c < 2: return None
            c -= 2; pts += 1
        elif a == '单':
            if c < 6: return None
            c -= 6; pts += 5
    return pts
print('船收入 3 币、6 回合：海船船单单单 ->', run3('海船船单单单'),
      '| 最高', max(r for r in (run3(p) for p in product('海船鱼单', repeat=6)) if r is not None))
