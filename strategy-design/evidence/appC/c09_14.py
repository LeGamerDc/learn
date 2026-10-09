# 附录 C：第 09~14 章补充题验算
from fractions import Fraction as F
import itertools

def pure_ne(R, C):
    rows, cols = len(R), len(R[0]); out = []
    for i in range(rows):
        for j in range(cols):
            if R[i][j] == max(R[k][j] for k in range(rows)) and C[i][j] == max(C[i][k] for k in range(cols)):
                out.append((i, j))
    return out

print("== C09.1 3x3 纯策略均衡")
R = [[3, 1, 2], [2, 2, 4], [0, 3, 1]]
C = [[1, 2, 0], [3, 1, 2], [2, 3, 1]]
print(pure_ne(R, C))

print("== C09.2 结构判别（行玩家视角 CC, CD, DC, DD）")
mats = {
    'a': ((3, 3), (0, 4), (4, 0), (1, 1)),
    'b': ((4, 4), (0, 2), (2, 0), (2, 2)),
    'c': ((2, 2), (1, 3), (3, 1), (0, 0)),
    'd': ((3, 2), (0, 0), (0, 0), (2, 3)),
}
for k, (cc, cd, dc, dd) in mats.items():
    R = [[cc[0], cd[0]], [dc[0], dd[0]]]; C = [[cc[1], cd[1]], [dc[1], dd[1]]]
    print(k, 'NE', pure_ne(R, C))

print("== C09.3 三格采集：大6 小3 进货2；撞格规则")
acts = ['大', '小', '进货']
val = {'大': 6, '小': 3, '进货': 2}
def payoff(a, b, rule):
    if a == '进货': return 2
    if a == b:
        return 0 if rule == '落空' else F(val[a], 2)
    return val[a]
for rule in ('落空', '平分'):
    R = [[payoff(a, b, rule) for b in acts] for a in acts]
    C = [[payoff(b, a, rule) for b in acts] for a in acts]
    print(rule, [[str(x) for x in r] for r in R], 'NE', [(acts[i], acts[j]) for i, j in pure_ne(R, C)])
# 落空规则下的对称混合均衡（大/小/进货）
x, y = F(2, 3), F(1, 3)
print('落空 对称混合: 大', 6 * (1 - x), '小', 3 * (1 - y), '进货', 2)
print("== C10.1 突袭：进攻方 左/右，防守方 守左/守右")
# 进攻方得分：左未守4 左被守1；右未守2 右被守0
p = F(2, 5)
print('守左时', p * 1 + (1 - p) * 2, '守右时', p * 4 + (1 - p) * 0)
q = F(4, 5)
print('攻左', q * 1 + (1 - q) * 4, '攻右', q * 2 + (1 - q) * 0)
for g in (F(1, 2), F(9, 10), F(4, 5)):
    print('防守方守左', g, '攻左', g * 1 + (1 - g) * 4, '攻右', g * 2)

print("== C10.3 三元循环 X克Y 3, Y克Z 1, Z克X 2")
x, y, z = F(1, 6), F(1, 3), F(1, 2)
print('X', 3 * y - 2 * z, 'Y', 1 * z - 3 * x, 'Z', 2 * x - 1 * y)

print("== C10.2 点球式 改条件（略，见 C10.1）")

print("== C11.1 缩水的蛋糕")
def bargain(pies):
    # pies[k]：第 k 阶段蛋糕大小；第 0 阶段 A 提，第 1 阶段 B 提，交替；最后一阶段之后全为 0；平手接受
    n = len(pies); prop = None
    # 从最后一阶段倒推：提议者拿 pie - 回应者的继续值
    cont = (0, 0)  # (A, B) 若拒绝最后一个提议
    for k in reversed(range(n)):
        proposer = 'A' if k % 2 == 0 else 'B'
        if proposer == 'A':
            give = cont[1]; cont = (pies[k] - give, give)
        else:
            give = cont[0]; cont = (give, pies[k] - give)
    return cont
print('10,6:', bargain([10, 6]), ' 10,6,3:', bargain([10, 6, 3]), ' 10,8,6,4,2:', bargain([10, 8, 6, 4, 2]))

print("== C11.2 开分店（承诺）")
def spe(commit, cost, bonus, B_fight):
    A_fight = 2 + (bonus if commit else 0) - (cost if commit else 0)
    A_share = 5 - (cost if commit else 0)
    A_out = 8 - (cost if commit else 0)
    fight = A_fight > A_share
    B_enter_payoff = B_fight if fight else 3
    enter = B_enter_payoff > 0
    if enter: return ('进入', '价格战' if fight else '共处', A_fight if fight else A_share, B_enter_payoff)
    return ('不进', None, A_out, 0)
for B_fight in (-1, 1):
    print('B打价格战得', B_fight, '不承诺', spe(False, 1, 4, B_fight), '承诺', spe(True, 1, 4, B_fight))

print("== C12.1 情书（初版16张）2人局")
comp = {'守卫': 5, '牧师': 2, '男爵': 2, '侍女': 2, '王子': 2, '国王': 1, '伯爵夫人': 1, '公主': 1}
seen = {'守卫': 2, '国王': 1}  # 明置移除 3 张
mine = {'守卫': 1, '牧师': 1}
opp_played = {'侍女': 1}
unk = {k: comp[k] - seen.get(k, 0) - mine.get(k, 0) - opp_played.get(k, 0) for k in comp}
tot = sum(unk.values()); print('未知', unk, '共', tot)
print({k: str(F(v, tot)) for k, v in unk.items()})

print("== C12.2 简化吹牛骰：对手 5 颗骰子里至少 2 个 4")
from math import comb
p4 = F(1, 6)
def atleast(k, n=5, p=p4): return sum(comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k, n + 1))
prior = atleast(2); print('先验 P(>=2个4)=', prior, float(prior))
for b in (F(1, 4), F(1, 2)):
    post = prior / (prior + (1 - prior) * b)
    print('诈唬率', b, '后验', post, float(post))

print("== C13.1 四人末手")
sc = {'甲': 20, '乙': 19, '丙': 17, '丁': 12}
order = ['甲', '乙', '丙', '丁']
def winner(s):
    m = max(s.values()); return [k for k in order if s[k] == m]
for act in ['扣甲3', '扣乙3', '扣丙3', '自己+2']:
    s = dict(sc)
    if act == '自己+2': s['丁'] += 2
    else: s[act[1]] -= 3
    print(act, s, '胜者', winner(s))

print("== C13.2 三人末轮：你(丙)、甲、乙依次一个动作：自己+2 或 某人-2；最高者胜，并列算并列者都不胜")
import itertools
def best_play(scores, order, prefs):
    # 逆向归纳：每人最大化"自己独胜"；不能独胜时按 prefs[人] 的偏好函数
    def rec(s, idx):
        if idx == len(order): return s
        me = order[idx]; best = None; bestkey = None
        for act in ['+2'] + [f'-{o}' for o in order if o != me]:
            s2 = dict(s)
            if act == '+2': s2[me] += 2
            else: s2[act[1:]] -= 2
            final = rec(s2, idx + 1)
            key = prefs[me](final)
            if bestkey is None or key > bestkey: best, bestkey = (act, final), key
        return best[1]
    return rec
def solo_winner(s):
    m = max(s.values()); w = [k for k in s if s[k] == m]
    return w[0] if len(w) == 1 else None
def pref_factory(me):
    def f(final):
        w = solo_winner(final)
        return (1 if w == me else 0, -max(v for k, v in final.items() if k != me) + final[me])
    return f
def trace(scores, order):
    prefs = {p: pref_factory(p) for p in order}
    # 重新跑一遍记录动作
    def rec(s, idx):
        if idx == len(order): return s, []
        me = order[idx]; best = None
        for act in ['+2'] + [f'-{o}' for o in order if o != me]:
            s2 = dict(s)
            if act == '+2': s2[me] += 2
            else: s2[act[1:]] -= 2
            final, acts = rec(s2, idx + 1)
            key = prefs[me](final)
            if best is None or key > best[0]: best = (key, final, [(me, act)] + acts)
        return best[1], best[2]
    return rec(scores, 0)
for sc0 in ({'丙': 7, '甲': 9, '乙': 8}, {'丙': 8, '甲': 9, '乙': 8}):
    print(sc0, trace(sc0, ['丙', '甲', '乙']))

print("== C14.1 12 轮囚徒困境（CC3/3, DC5/0, DD1/1）")
PAY = {('C', 'C'): (3, 3), ('C', 'D'): (0, 5), ('D', 'C'): (5, 0), ('D', 'D'): (1, 1)}
def tft(h_me, h_op): return 'C' if not h_op else h_op[-1]
def alld(h_me, h_op): return 'D'
def grudger(h_me, h_op): return 'D' if 'D' in h_op else 'C'
def tft_last(h_me, h_op):
    return 'D' if len(h_me) == 11 else tft(h_me, h_op)
def play(a, b, n=12):
    ha, hb = [], []; sa = sb = 0
    for _ in range(n):
        x, y = a(ha, hb), b(hb, ha); pa, pb = PAY[(x, y)]; sa += pa; sb += pb; ha.append(x); hb.append(y)
    return sa, sb
S = {'以牙还牙': tft, '永远背叛': alld, '冷酷': grudger, '末轮背叛的以牙还牙': tft_last}
for a, b in itertools.combinations_with_replacement(S, 2):
    print(a, 'vs', b, play(S[a], S[b]))

print("== C14.2 合伙订单：订单 12，你单干 4，他单干 5")
for x in range(13):
    me, him = x, 12 - x
    pts_ok = me >= 4 and him >= 5
    race_ok = (me - him) >= (4 - 5)
    print(x, '总分视角', pts_ok, '两人争胜视角(分差不变差)', race_ok)
# 三人局：丙领先 20，你 14，他 13；订单使两人都 +，问你是否接受 x
