from fractions import Fraction as F
from itertools import product
from functools import lru_cache
from math import comb
print('== C17.1 四颗非传递骰子')
D={'A':[4,4,4,4,0,0],'B':[3,3,3,3,3,3],'C':[6,6,2,2,2,2],'D':[5,5,5,1,1,1]}
def pw(x,y): return F(sum(1 for a,b in product(D[x],D[y]) if a>b),36)
for x in D:
    print(x,'均值',F(sum(D[x]),6),{y:str(pw(x,y)) for y in D if y!=x})
print('== C17.2 三档摊位：剩 T 个回合，每回合一个动作')
# 动作：进货+2；小摊 2币->1分且以后每回合+1币；中摊 4币->3分；大摊 7币->6分
def best(T,c,inc):
    @lru_cache(None)
    def f(t,c,inc):
        if t==0: return 0,()
        c+=inc
        opts=[]
        v,p=f(t-1,c+2,inc); opts.append((v,('进货',)+p))
        if c>=2: v,p=f(t-1,c-2,inc+1); opts.append((v+1,('小',)+p))
        if c>=4: v,p=f(t-1,c-4,inc); opts.append((v+3,('中',)+p))
        if c>=7: v,p=f(t-1,c-7,inc); opts.append((v+6,('大',)+p))
        return max(opts)
    return f(T,c,inc)
for T in (3,4,5,6):
    print(' T',T,'起始3币收入0:',best(T,3,0))
def all_first(T,c,inc):
    @lru_cache(None)
    def f(t,c,inc):
        if t==0: return 0
        c+=inc; o=[f(t-1,c+2,inc)]
        if c>=2: o.append(1+f(t-1,c-2,inc+1))
        if c>=4: o.append(3+f(t-1,c-4,inc))
        if c>=7: o.append(6+f(t-1,c-7,inc))
        return max(o)
    c0=c+inc; out={'进货':f(T-1,c0+2,inc)}
    if c0>=2: out['小']=1+f(T-1,c0-2,inc+1)
    if c0>=4: out['中']=3+f(T-1,c0-4,inc)
    if c0>=7: out['大']=6+f(T-1,c0-7,inc)
    return out
for T in (3,4,5,6):
    print(' T',T,'首个动作各自最优总分',all_first(T,3,0))
# 单价表
for k,(c,s) in {'小':(2,1),'中':(4,3),'大':(7,6)}.items(): print(' ',k,'每币分',F(s,c))
print('== C17.3 座位：3 人 12 局，1 号位赢 7 局')
p=F(1,3); P=sum(comb(12,k)*p**k*(1-p)**(12-k) for k in range(7,13)); print(' P(>=7)=',float(P))
# 任一座位 >=7（多项分布精确）
tot=0
for a in range(13):
    for b in range(13-a):
        c=12-a-b
        if max(a,b,c)>=7: tot+=F(comb(12,a)*comb(12-a,b),3**12)
print(' 任一座位>=7',float(tot))
print('== C18.1 2d6>=8',F(sum(1 for a,b in product(range(1,7),repeat=2) if a+b>=8),36))
print('== C18.2 末轮：你10，对手13（已结束），甲 稳拿+3；乙 掷1d6+1；丙 掷2d6取高')
def dist(opt):
    if opt=='甲': return {3:F(1)}
    if opt=='乙': return {k+1:F(1,6) for k in range(1,7)}
    if opt=='丙':
        d={}
        for a,b in product(range(1,7),repeat=2): d[max(a,b)]=d.get(max(a,b),0)+F(1,36)
        return d
for need_tie_wins in (False,True):
    print(' 同分', '你胜' if need_tie_wins else '对手胜')
    for o in '甲乙丙':
        d=dist(o); ev=sum(k*v for k,v in d.items())
        w=sum(v for k,v in d.items() if (10+k>13 or (need_tie_wins and 10+k==13)))
        print('   ',o,'期望',ev,'胜率',w,float(w))
print('== C19.1 多数决 三区')
# 区域 值 / 兵力（你, A, B）。规则：最多者得全分；并列最多者平分（向下取整）；第二名不得分
regions={'北':(6,(2,1,0)),'中':(4,(1,1,2)),'南':(8,(0,2,2))}
def score(regs):
    s=[0,0,0]
    for v,(t) in regs.values():
        m=max(t); w=[i for i in range(3) if t[i]==m and m>0]
        for i in w: s[i]+=v//len(w)
    return s
print(' 现在',score(regions))
for r in regions:
    rr=dict(regions); v,t=rr[r]; t=list(t); t[0]+=1; rr[r]=(v,tuple(t)); print(' 你加到',r,score(rr))
print('== C19.2 两区 你放1，对手放1（看到你后），然后计分；两人；最多者得全分，并列都不得')
def sc2(regs):
    s=[0,0]
    for v,(a,b) in regs:
        if a>b: s[0]+=v
        elif b>a: s[1]+=v
    return s
def solve2(regs):
    res={}
    for i in range(len(regs)):
        r1=[list(x) for x in regs]; r1=[(v,(a,b)) for v,(a,b) in regs]
        v,(a,b)=r1[i]; r1[i]=(v,(a+1,b))
        worst=None
        for j in range(len(regs)):
            r2=list(r1); v2,(a2,b2)=r2[j]; r2[j]=(v2,(a2,b2+1))
            s=sc2(r2); d=s[0]-s[1]
            if worst is None or d<worst[0]: worst=(d,j,s)
        res[i]=worst
    return res
base=[(7,(1,1)),(5,(0,1)),(3,(2,1))]
print(' 区值/兵力',base,'现在',sc2(base),solve2(base))
base2=[(7,(1,1)),(5,(0,1)),(3,(1,1))]
print(' 改:丙区变1:1',base2,'现在',sc2(base2),solve2(base2))
print('== C20.2 收摊：你 9 分；现在宣布 vs 投资')
