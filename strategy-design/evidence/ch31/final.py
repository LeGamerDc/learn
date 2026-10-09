# 第31章《庙会》各版本的全部模拟数字（固定种子，可复现）
import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from sim import *
POOL4=['G','E2','E3','S']
def V(ver,**extra):
    kw=dict(suit_bonus=3,tie='coins',refresh=True,refresh_after=2)
    if ver>=2: kw['start']=lambda i,n:6
    if ver>=3: kw['suit_min']=3
    kw.update(extra); return Cfg(**kw)
def round1(cfg,n,G=8000,seed=11):
    rng=random.Random(seed); bought=[0]*n
    for _ in range(G):
        pick=[rng.choice(POOL4) for _ in range(n)]; flags=[False]*n
        def wrap(f):
            def g(me,st,p,m,aff,rnd,cfg2,rng2):
                ch=f(me,st,p,m,aff,rnd,cfg2,rng2) if aff else None
                if rnd==0 and ch is not None: flags[p]=True
                return ch
            return g
        play([wrap(STR[x]) for x in pick],cfg,rng)
        for i in range(n): bought[i]+=flags[i]
    return [round(100*b/G,1) for b in bought]
def bonus_rate(cfg,n,G=8000,seed=9):
    rng=random.Random(seed); aw=0
    for _ in range(G):
        pick=[rng.choice(POOL4) for _ in range(n)]
        r=play([STR[x] for x in pick],cfg,rng)
        for su in range(4):
            cnt=[r['suitcnt'][i][su] for i in range(n)]; m=max(cnt)
            if m>=getattr(cfg,'suit_min',1) and cnt.count(m)==1: aw+=1
    return round(100*aw/(4*G),1)
def one_vs_field(cfg,names,n,G=6000,seed=13):
    out={}
    for a in names:
        for b in names:
            rng=random.Random(seed); w=0
            for g in range(G):
                seat=g%n; lst=[STR[b]]*n; lst[seat]=STR[a]
                r=play(lst,cfg,rng); w+= r['winner']==seat
            out[(a,b)]=round(100*w/G,1)
    return out
def nash_fp(M,names,iters=200000):
    # 对称零和：收益 = 胜率-0.5；虚拟对局求均衡
    k=len(names); cnt=[0]*k; cnt[0]=1
    for t in range(iters):
        tot=sum(cnt); mix=[c/tot for c in cnt]
        vals=[sum(mix[j]*(M[(names[i],names[j])]-0.5) for j in range(k)) for i in range(k)]
        cnt[vals.index(max(vals))]+=1
    tot=sum(cnt); return [round(c/tot,3) for c in cnt]
if __name__=='__main__':
    which=sys.argv[1] if len(sys.argv)>1 else 'all'
    if which in ('all','metrics'):
        for ver in (1,2,3):
            cfg=V(ver)
            for n in (2,3,4,5):
                s=mixed_seats(cfg,n,G=20000,pool=POOL4)
                print(f'v0.{ver} n={n}',{k:s[k] for k in ('seat%','rounds','deck_used%','forced%','tie%','win_score','score_end%','supply_end%','coins_left')},
                      'r1buy',round1(cfg,n),'bonus%',bonus_rate(cfg,n),'survival',round(plan_survival(cfg,'等牌',n,G=4000),3))
    if which in ('all','attempts'):
        for n in (2,5):
            s=mixed_seats(V(1,market=lambda n:n+1),n,G=20000,pool=POOL4); print('attempt v0.1+market N+1',n,s['seat%'],s['deck_used%'],s['forced%'])
            s=mixed_seats(V(1,deck_fn=lambda n:[(r,su) for su in range(4) for r in range(1,n+5)]),n,G=20000,pool=POOL4); print('attempt v0.1+deck A..N+4',n,s['seat%'],s['deck_used%'],s['forced%'])
            s=mixed_seats(V(3,threshold=lambda n:18),n,G=20000,pool=POOL4); print('attempt v0.3+threshold18',n,s['seat%'],s['deck_used%'],s['rounds'],s['supply_end%'])
            s=mixed_seats(V(1,start=lambda i,n:3+i),n,G=20000,pool=POOL4); print('attempt v0.1 start 3+seat',n,s['seat%'])
    if which in ('all','maps'):
        names=['G','E2','E3','S','B','H','R']
        for ver in (1,2,3):
            M=matrix2(V(ver),names,G=6000)
            print(f'v0.{ver} 2p matrix (row win%)'); print('      '+' '.join(f'{b:>5s}' for b in names))
            for a in names: print(f'{a:4s}',' '.join(f'{100*M[(a,b)]:5.1f}' for b in names))
            print('   nash among 4:',POOL4,nash_fp(M,POOL4,iters=20000))
            F=one_vs_field(V(ver),POOL4+['B','H'],5,G=5000)
            print(f'v0.{ver} 5p one-vs-field (row=me alone, col=4 others; fair=20)')
            for a in POOL4+['B','H']: print(f'  {a:4s}',' '.join(f'{F[(a,b)]:5.1f}' for b in POOL4+['B','H']))
