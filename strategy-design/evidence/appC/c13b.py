# C13.2 三人末轮：顺序 丙(你)→甲→乙；动作：自己+2，或让某人-3；最高分独胜，并列最高则无人独胜（都算没赢）
# 每人偏好：先求自己独胜；不能独胜时，按题设偏好（默认：让"当前不可能被自己追上"的…）——这里用：不能赢时什么也不在乎，取第一个动作（+2）。
import itertools
ORDER=['丙','甲','乙']
def acts(me):
    return ['+2']+[f'-3{o}' for o in ORDER if o!=me]
def apply(s,me,a):
    s=dict(s)
    if a=='+2': s[me]+=2
    else: s[a[2:]]-=3
    return s
def solo(s):
    m=max(s.values()); w=[k for k in s if s[k]==m]; return w[0] if len(w)==1 else None
def solve(s,idx,tieprefs):
    if idx==3: return s,[]
    me=ORDER[idx]; best=None
    for a in acts(me):
        fin,seq=solve(apply(s,me,a),idx+1,tieprefs)
        w=solo(fin)
        key=(1 if w==me else 0, tieprefs[me](fin))
        if best is None or key>best[0]: best=(key,fin,[(me,a)]+seq)
    return best[1],best[2]
neutral=lambda f:0
for sc in ({'丙':8,'甲':10,'乙':9},{'丙':9,'甲':10,'乙':9},{'丙':7,'甲':10,'乙':9}):
    print(sc)
    # 你作为丙，逐个动作看结果（甲乙按最优）
    for a in acts('丙'):
        fin,seq=solve(apply(sc,'丙',a),1,{'丙':neutral,'甲':neutral,'乙':neutral})
        print('  丙',a,'->',seq,fin,'独胜',solo(fin))
