import sys,os,random; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from functools import lru_cache
from fractions import Fraction as F
from collections import Counter
print('== C15.1 批发：拿3币但下回合不收入；对比进货2币')
for n in range(0,5): print(' 面前',n,'张：批发净得',3-n,'进货',2, '批发更好' if 3-n>2 else ('一样' if 3-n==2 else '进货更好'))
print('== C15.2 人格卡矩阵（不同终局线）')
def pol(kind):
    def f(me,op,m):
        aff=[v for v in m if v<=me['c']]
        if kind=='H': aff=[v for v in aff if v>=5]
        if not aff: return None
        if kind=='L': return min(aff)
        if kind.startswith('E'):
            k=int(kind[1:]); return min(aff) if len(me['cards'])<k else max(aff)
        return max(aff)
    return f
def play(p1,p2,seed,target):
    r=random.Random(seed); deck=[v for v in range(1,7) for _ in range(4)]; r.shuffle(deck)
    m=[deck.pop() for _ in range(3)]; st=[{'c':3,'cards':[]},{'c':3,'cards':[]}]; P=[p1,p2]; rnd=0
    while True:
        rnd+=1
        for i in (0,1):
            me=st[i]; me['c']+=len(me['cards']); ch=P[i](me,st[1-i],m)
            if ch is None: me['c']+=2
            else:
                m.remove(ch); me['c']-=ch; me['cards'].append(ch)
                if deck: m.append(deck.pop())
        sc=[sum(x['cards']) for x in st]
        if max(sc)>=target or rnd>=40 or (not m): return 0 if sc[0]>sc[1] else 1
names=['E2','E3','G','H','L']
N=6000
for target in (15,10):
    print('终局线',target,'（行=我，两个座位各半）')
    for a in names:
        row=[]
        for b in names:
            w=0
            for s in range(N):
                w+= play(pol(a),pol(b),s,target)==0
                w+= play(pol(b),pol(a),s,target)==1
            row.append(100*w/(2*N))
        print('  ',a,' '.join('%5.1f'%x for x in row))
print('== C16 取币：第一手取1或2；之后每手可取 1..(对手上一手+1)；取最后一枚者胜')
@lru_cache(None)
def win(n,cap):
    if n==0: return False
    return any(not win(n-k,k+1) for k in range(1,min(cap,n)+1))
for n in range(1,13):
    print(' 开局',n,'先手', '胜' if win(n,2) else '败', '必胜第一手',[k for k in (1,2) if k<=n and not win(n-k,k+1)])
for n,last in ((4,1),(4,2),(5,1),(5,2),(6,2),(6,1),(7,1),(7,3)):
    cap=last+1
    print(' 剩',n,'对手上一手',last,'可取1~',cap, '胜' if win(n,cap) else '败',[k for k in range(1,min(cap,n)+1) if not win(n-k,k+1)])
# 状态数 / 选择点
reach=set(); 
def walk(n,cap):
    if (n,cap) in reach: return
    reach.add((n,cap))
    for k in range(1,min(cap,n)+1): walk(n-k,k+1)
walk(9,2); print(' 9 枚开局可到达(剩余,上限)状态数',len(reach))
