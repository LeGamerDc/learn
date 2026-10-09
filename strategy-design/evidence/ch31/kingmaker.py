# 造王机会：最后一轮、座次最后的玩家，自己已经不可能赢，但他的不同动作会让不同的人赢
import sys,os,copy; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from final import *
def winner_of(st,cfg):
    sc=final_scores(st,cfg); m=max(sc); ws=[i for i,v in enumerate(sc) if v==m]
    if cfg.tie=='coins':
        mc=max(st[i]['c'] for i in ws); ws=[i for i in ws if st[i]['c']==mc]
    return max(ws)
def measure(cfg,n,G=8000,seed=21,tie_shared=False):
    rng=random.Random(seed); km=0; last_can_win=0; games=0
    for _ in range(G):
        pick=[rng.choice(POOL4) for _ in range(n)]
        snap={}
        def wrap(f,idx):
            def g(me,st,p,m,aff,rnd,cfg2,rng2):
                if p==n-1:
                    snap['state']=(copy.deepcopy(st),list(m),rnd)
                return f(me,st,p,m,aff,rnd,cfg2,rng2) if aff else None
            return g
        r=play([wrap(STR[x],i) for i,x in enumerate(pick)],cfg,rng)
        games+=1
        if 'state' not in snap or snap['state'][2]!=r['rounds']-1:
            # 最后一轮他没有任何买得起的牌：只能进货，不存在造王选择
            if r['winner']==n-1: last_can_win+=1
            continue
        st,m,rnd=snap['state']   # 最后一轮座次最后者决策前的状态，收入已加
        outcomes=set()
        # 进货
        s2=copy.deepcopy(st); s2[n-1]['c']+=cfg.take; outcomes.add(winner_of(s2,cfg))
        for i,c in enumerate(m):
            if cost(c,st[n-1],cfg)<=st[n-1]['c']:
                s2=copy.deepcopy(st); s2[n-1]['c']-=cost(c,st[n-1],cfg); s2[n-1]['cards'].append(c); outcomes.add(winner_of(s2,cfg))
        if (n-1) in outcomes: last_can_win+=1
        elif len(outcomes)>=2: km+=1
    return round(100*km/games,1), round(100*last_can_win/games,1)
def measure_any(cfg,n,G=8000,seed=21):
    return measure(cfg,n,G,seed)
for ver in (2,3):
    for n in (3,4,5):
        print('v0.%d'%ver,n,'kingmaker% , last-seat-can-win%',measure(V(ver),n))
# 对照：多数平局时并列者都得奖励
import sim
def fs_shared(st,cfg):
    sc=[sum(r for r,s in p['cards']) for p in st]
    if cfg.suit_bonus:
        for s in range(4):
            cnt=[sum(1 for c in p['cards'] if c[1]==s) for p in st]
            m=max(cnt)
            if m>=getattr(cfg,'suit_min',1):
                for i,v in enumerate(cnt):
                    if v==m: sc[i]+=cfg.suit_bonus
    return sc
sim.final_scores.__code__=fs_shared.__code__
for n in (3,5): print('v0.2 tie-shared',n,measure(V(2),n))
