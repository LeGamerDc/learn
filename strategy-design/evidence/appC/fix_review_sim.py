# 附录 C 复评：C15.2 终局线 10 的大样本复算 + 局长；C15.3 改后的收藏家奖励（1~4 各一张 +5，计入终局判断）
import random, math
def pol(kind):
    def f(me,m):
        aff=[v for v in m if v<=me['c']]
        if not aff: return None
        if kind=='C':  # 收藏家：缺的 1~4 点里买得起的最贵一张；都不缺/买不起缺的 → 买最贵
            need=[v for v in aff if v<=4 and v not in me['cards']]
            return max(need) if need else max(aff)
        if kind.startswith('E'):
            k=int(kind[1:]); return min(aff) if len(me['cards'])<k else max(aff)
        return max(aff)
    return f
def score(cards,bonus):
    s=sum(cards)
    if bonus and all(v in cards for v in (1,2,3,4)): s+=5
    return s
def play(p1,p2,r,target,bonus=False):
    deck=[v for v in range(1,7) for _ in range(4)]; r.shuffle(deck)
    m=[deck.pop() for _ in range(3)]; st=[{'c':3,'cards':[]},{'c':3,'cards':[]}]; P=[p1,p2]; rnd=0
    while True:
        rnd+=1
        for i in (0,1):
            me=st[i]; me['c']+=len(me['cards']); ch=P[i](me,m)
            if ch is None: me['c']+=2
            else:
                m.remove(ch); me['c']-=ch; me['cards'].append(ch)
                if deck: m.append(deck.pop())
        sc=[score(x['cards'],bonus) for x in st]
        if max(sc)>=target or rnd>=40 or (not m):
            got=[bonus and all(v in x['cards'] for v in (1,2,3,4)) for x in st]
            return (0 if sc[0]>sc[1] else 1), rnd, got
def matchup(a,b,target,N,bonus=False,seed=0):
    r=random.Random(seed); w=0; L=0; gotA=0
    for s in range(N):
        x,l,g=play(pol(a),pol(b),r,target,bonus); w+=(x==0); L+=l; gotA+=g[0]
        x,l,g=play(pol(b),pol(a),r,target,bonus); w+=(x==1); L+=l; gotA+=g[1]
    p=w/(2*N); se=math.sqrt(p*(1-p)/(2*N))
    return p,se,L/(2*N),gotA/(2*N)
import sys
N=int(sys.argv[1]) if len(sys.argv)>1 else 50000
print('== C15.2 （每个座位 N=%d 局）'%N)
for target in (15,10):
    for a,b in (('E3','G'),('E2','G'),('E2','E3'),('G','G')):
        p,se,L,_=matchup(a,b,target,N,seed=target)
        print('  终局线%d %s 对 %s 胜率 %.2f%% ±%.2f(95%%) 平均局长 %.2f 轮'%(target,a,b,100*p,196*se,L))
print('== C15.3 变体：1~4 各一张 +5（计入终局判断）')
for b in ('E2','E3','G','C'):
    p,se,L,got=matchup('C',b,15,N//5,bonus=True,seed=7)
    print('  收藏家 对 %s 胜率 %.1f%% ±%.1f 平均局长 %.2f 收藏家完成奖励比例 %.1f%%'%(b,100*p,196*se,L,100*got))
for a,b in (('E2','G'),('E3','G'),('E2','E3')):
    p,se,L,got=matchup(a,b,15,N//5,bonus=True,seed=7)
    print('  变体下 %s 对 %s 胜率 %.1f%% ±%.1f  %s 完成奖励 %.1f%%'%(a,b,100*p,196*se,a,100*got))
