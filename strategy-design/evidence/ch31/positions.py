# 第31章：思考路径 31.3 与练习 5 的局面可达性（完整账本 + 市场序列）
import itertools
H,S,C,D='♥','♠','♣','♦'
def replay(players,start,init_market,refills,actions,rounds):
    """actions[r][p] = ('buy',card) | ('take',)；refills 按招揽顺序依次补入"""
    coins={p:start for p in players}; cards={p:[] for p in players}; market=list(init_market); rf=list(refills)
    seen=set(init_market)|set(refills); assert len(seen)==len(init_market)+len(refills)
    for r in range(rounds):
        for p in players:
            a=actions[r].get(p)
            if a is None: return coins,cards,market,p   # 停在 p 收入之前
            coins[p]+=len(cards[p])
            if a[0]=='take': coins[p]+=2
            else:
                c=a[1]; assert c in market,(r,p,c,market); assert coins[p]>=c[0],(r,p,coins[p],c)
                coins[p]-=c[0]; cards[p].append(c); market.remove(c); market.append(rf.pop(0))
        rep={p:sum(x for x,_ in cards[p]) for p in players}
        assert max(rep.values())<15 or r==rounds-1,(r,rep)
    return coins,cards,market,None
# ---- 31.3：v0.2，3 人，第 5 轮，C 收入前
acts=[{'A':('buy',(3,S)),'B':('buy',(2,S)),'C':('buy',(1,S))},
      {'A':('buy',(4,H)),'B':('buy',(3,H)),'C':('buy',(1,D))},
      {'A':('take',),    'B':('buy',(4,D)),'C':('buy',(2,C))},
      {'A':('buy',(5,H)),'B':('take',),    'C':('buy',(1,H))},
      {'A':('buy',(4,C)),'B':('buy',(6,D))}]
coins,cards,market,stop=replay('ABC',6,[(3,S),(2,S),(6,C)],[(1,S),(3,H),(4,H),(1,D),(4,D),(2,C),(5,H),(1,H),(4,C),(6,D),(2,H),(3,D)],acts,5)
coins['C']+=len(cards['C'])
print('31.3 coins',coins,'market',market)
for p in 'ABC': print(p,cards[p],sum(x for x,_ in cards[p]))
def score(cards,coins,minc=1):
    rep={p:sum(x for x,_ in cards[p]) for p in cards}; tot=dict(rep)
    for su in (H,S,C,D):
        cnt={p:sum(1 for _,s in cards[p] if s==su) for p in cards}; m=max(cnt.values())
        w=[p for p in cnt if cnt[p]==m]
        if m>=minc and len(w)==1: tot[w[0]]+=3
    best=max(tot.values()); ws=[p for p in tot if tot[p]==best]
    mc=max(coins[p] for p in ws); ws=[p for p in ws if coins[p]==mc]
    return tot,max(ws,key=lambda p:'ABC'.index(p) if p in 'ABC' else p)
for minc,tag in ((1,'v0.2'),(3,'v0.3')):
    opts=[('take',None)]+[('buy',c) for c in market if c[0]<=coins['C']]
    for o in opts:
        cc={p:list(v) for p,v in cards.items()}; co=dict(coins)
        if o[0]=='take': co['C']+=2
        else: cc['C'].append(o[1]); co['C']-=o[1][0]
        print(tag,o,score(cc,co,minc))
# ---- 练习 5：v0.3，2 人，O 先手、Y 后手；第 6 轮 Y 收入前
def score2(cards,coins,order,minc=3):
    rep={p:sum(x for x,_ in cards[p]) for p in cards}; tot=dict(rep)
    for su in (H,S,C,D):
        cnt={p:sum(1 for _,s in cards[p] if s==su) for p in cards}; m=max(cnt.values())
        w=[p for p in cnt if cnt[p]==m]
        if m>=minc and len(w)==1: tot[w[0]]+=3
    best=max(tot.values()); ws=[p for p in tot if tot[p]==best]
    mc=max(coins[p] for p in ws); ws=[p for p in ws if coins[p]==mc]
    return tot,max(ws,key=order.index)
def ex5(tag,init,refills,acts):
    coins,cards,market,stop=replay('OY',6,init,refills,acts,6)
    coins['Y']+=len(cards['Y'])
    print(tag,'coins',coins,'market',market,{p:(cards[p],sum(x for x,_ in cards[p])) for p in cards})
    for o in [('take',None)]+[('buy',c) for c in market if c[0]<=coins['Y']]:
        cc={p:list(v) for p,v in cards.items()}; co=dict(coins)
        if o[0]=='take': co['Y']+=2
        else: cc['Y'].append(o[1]); co['Y']-=o[1][0]
        print('   ',o,score2(cc,co,'OY'))
ex5('ex5 base',[(3,S),(5,S),(5,D)],[(5,H),(4,S),(4,D),(3,D),(1,H),(6,S),(2,H),(2,S)],
    [{'O':('buy',(3,S)),'Y':('buy',(5,S))},{'O':('take',),'Y':('take',)},{'O':('buy',(5,H)),'Y':('buy',(4,S))},
     {'O':('buy',(4,D)),'Y':('buy',(3,D))},{'O':('take',),'Y':('buy',(1,H))},{'O':('buy',(6,S))}])
ex5('ex5 variant',[(5,S),(6,S),(5,D)],[(5,H),(4,S),(3,D),(3,S),(1,H),(2,H),(1,S),(2,S)],
    [{'O':('take',),'Y':('buy',(5,S))},{'O':('buy',(6,S)),'Y':('take',)},{'O':('take',),'Y':('buy',(4,S))},
     {'O':('buy',(5,H)),'Y':('buy',(3,D))},{'O':('buy',(3,S)),'Y':('buy',(1,H))},{'O':('buy',(1,S))}])
