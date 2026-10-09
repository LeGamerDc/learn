# C02.1 小集市 ①③；C02.4 三子消失井字棋 倒推
from fractions import Fraction as F
from collections import Counter
seen=[6,4,2]+[5,5,1,1]+[3,5,1]
deck=Counter({v:4 for v in range(1,7)}); deck.subtract(Counter(seen))
print('C02.1 牌堆',dict(deck),'共',sum(deck.values()))
opp_coins=1+3; me_coins=0+4
print('对手收入后',opp_coins,'你收入后',me_coins)
good=deck[3]+deck[4]
print('补牌是3或4的概率',F(good,sum(deck.values())))
# C02.4 三子井字棋：放第4子时先移走自己最早的子
LINES=[(1,2,3),(4,5,6),(7,8,9),(1,4,7),(2,5,8),(3,6,9),(1,5,9),(3,5,7)]
def won(s): return any(all(i in s for i in l) for l in LINES)
import itertools
states=set()
def all_queues(k_excl):
    pass
# 枚举所有状态：X序列、O序列(有序，最多3)，轮到谁。从空开始 BFS 生成可达状态
from collections import deque
start=((),(),0)
succ={}; pred={}
q=deque([start]); seenS={start}
while q:
    s=q.popleft(); X,O,t=s
    if won(set(X)) or won(set(O)): succ[s]=[]; continue
    mine,other=(X,O) if t==0 else (O,X)
    occ=set(X)|set(O)
    nxt=[]
    for cell in range(1,10):
        base=mine[1:] if len(mine)==3 else mine
        # 先移走最早的子，再落子；落子格必须在移走后为空（规定：不能落在刚移走的格子）
        if cell in occ: continue
        nm=base+(cell,)
        ns=(nm,other,1) if t==0 else (other,nm,0)
        nxt.append(ns)
        if ns not in seenS: seenS.add(ns); q.append(ns)
    succ[s]=nxt
print('可达状态数',len(succ))
# 倒推：值从轮到者角度 WIN/LOSS，其余为循环（和）
val={}
for s,n in succ.items():
    X,O,t=s
    if won(set(X)) or won(set(O)):
        # 上一手的人赢了；轮到的人输
        val[s]='L'
for s in succ:
    for n in succ[s]: pred.setdefault(n,[]).append(s)
cnt={s:len(succ[s]) for s in succ}
q=deque([s for s in val])
while q:
    s=q.popleft()
    for p in pred.get(s,[]):
        if p in val: continue
        if val[s]=='L': val[p]='W'; q.append(p)
        else:
            cnt[p]-=1
            if cnt[p]==0: val[p]='L'; q.append(p)
print('开局价值（轮到X）:',val.get(start,'循环/和'))
# 第一手各格价值
for cell in range(1,10):
    ns=((cell,),(),1); print(cell, {'W':'O胜','L':'X胜'}.get(val.get(ns),'和'), end='; ')
print()
