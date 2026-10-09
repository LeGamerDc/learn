import itertools, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from functools import lru_cache
from ledger import reachable
print('C05.2 账本 [1,1] 2轮后收入前', sorted(reachable([1,1],2)))
print('C02.1 账本 对手(2,4,6) 5轮', sorted(reachable([2,4,6],5)), ' 你(1,1,5,5)', sorted(reachable([1,1,5,5],5)))
# C06.2 克制 (2,1,3) 的顺序
orders=list(itertools.permutations((1,2,3)))
def result(me,op):
    w=sum(a>b for a,b in zip(me,op)); l=sum(a<b for a,b in zip(me,op)); return (w>l)-(w<l)
print('C06.2 对(2,1,3)', {o:result(o,(2,1,3)) for o in orders})
print('C06.2 对(1,3,2)', {o:result(o,(1,3,2)) for o in orders})
# C16.3 第一手可取 1~3
@lru_cache(None)
def win(n,cap):
    if n==0: return False
    return any(not win(n-k,k+1) for k in range(1,min(cap,n)+1))
print('C16.3 第一手上限3 必败开局', [n for n in range(1,21) if not win(n,3)], ' 上限2', [n for n in range(1,21) if not win(n,2)])
# C19.2 对手放 2 枚
def sc2(regs):
    s=[0,0]
    for v,(a,b) in regs:
        if a>b: s[0]+=v
        elif b>a: s[1]+=v
    return s
base=[(8,(0,2)),(5,(1,0)),(3,(2,0))]
for i in range(3):
    r1=list(base); v,(a,b)=r1[i]; r1[i]=(v,(a+1,b)); worst=None
    for j,k in itertools.combinations_with_replacement(range(3),2):
        r2=list(r1)
        for t in (j,k):
            v2,(a2,b2)=r2[t]; r2[t]=(v2,(a2,b2+1))
        s=sc2(r2); d=s[0]-s[1]
        if worst is None or d<worst[0]: worst=(d,(j,k),s)
    print('C19.2 对手放2枚：你放区',i,'最坏',worst)
# C22.1 R=4 有磨坊的最好
def run(plan, coins=3):
    mill=False; flour=0
    for a in plan:
        if mill and coins>=1: coins-=1; flour+=2
        if a=='零工': coins+=2
        elif a=='建':
            if coins<3: return None
            coins-=3; mill=True
        elif a=='卖': coins+=2*flour; flour=0
    return coins
for R in (4,5):
    res=[(run(p),p) for p in itertools.product(['零工','建','卖'],repeat=R) if p.count('建')==1 and run(p) is not None]
    print('C22.1 R',R,'建磨坊的最好',max(res))
