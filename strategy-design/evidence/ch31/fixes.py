# 第31章：针对评审意见的复核（供给口径、刷新、计划落空原因、H 卡死、头牌改变胜负、造王筛选、练习1）
import sys,os,copy; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from seatdiag import *
which=sys.argv[1:] or ['all']
A=lambda k: 'all' in which or k in which

if A('supply'):
    # 供给口径：终局时牌堆空、市场<3、牌堆与市场全空；并做"两副 A~6"对照
    for n in (2,5):
        res=run(V(1),n)
        G=len(res)
        print(f'v0.1 n={n} deck_empty%={100*sum(r["deck"]==0 for r in res)/G:.1f} market<3%={100*sum(r["market"]<3 for r in res)/G:.1f} all_empty%={100*sum(r["deck"]==0 and r["market"]==0 for r in res)/G:.1f} ended_supply%={100*sum(r["ended"]=="supply" for r in res)/G:.1f}')
    two=lambda n:[(r,s) for s in range(4) for r in range(1,7)]*2
    report('v0.1 n=5 two decks A~6',run(V(1,deck_fn=two),5),ties=('rule','split'))
    res=run(V(1,deck_fn=two),5); G=len(res)
    print(f'  two decks market<3%={100*sum(r["market"]<3 for r in res)/G:.1f} deck_empty%={100*sum(r["deck"]==0 for r in res)/G:.1f}')

if A('survival'):
    # 计划落空的原因：被对手买走 vs 被刷新
    for ra in (1,2):
        for n in (2,5):
            cfg=V(1,refresh_after=ra); rng=random.Random(5); targets={}; cnt=Counter()
            def pre(p,me,market,st,deck):
                if p in targets:
                    t=targets.pop(p); cnt['total']+=1
                    if t in market: cnt['alive']+=1
                    elif any(t in x['cards'] for x in st): cnt['bought']+=1
                    else: cnt['refreshed']+=1
            def post(p,me,market,ch):
                if ch is None:
                    inc=len(me['cards'])
                    nxt=[c for c in market if me['c']<cost(c,me,cfg)<=me['c']+inc+cfg.take]
                    if nxt: targets[p]=max(nxt)
            for _ in range(4000):
                targets.clear(); play2([STR['等牌']]*n,cfg,rng,pre=pre,post=post)
            T=cnt['total']
            print(f'refresh_after={ra} n={n} alive={100*cnt["alive"]/T:.1f} bought={100*cnt["bought"]/T:.1f} refreshed={100*cnt["refreshed"]/T:.1f} (targets {T})')

if A('stall'):
    for n in (2,3,4,5):
        for cap in (40,400):
            cfg=V(3,max_rounds=cap); rng=random.Random(1); res=[play2([STR['H']]*n,cfg,rng) for _ in range(5000)]
            print(f'v0.3 H mirror n={n} cap={cap} capped%={100*sum(r["ended"]=="cap" for r in res)/len(res):.2f}')
    # 正常混合对局里，若加"第 10 轮结束时终局"会触发多少
    for n in (2,5):
        res=run(V(3),n); print(f'v0.3 mixed n={n} rounds>=10: {100*sum(r["rounds"]>=10 for r in res)/len(res):.2f}% max_rounds={max(r["rounds"] for r in res)}')

def winner_full(sc,coins):
    m=max(sc); ws=[i for i in range(len(sc)) if sc[i]==m]
    mc=max(coins[i] for i in ws); ws=[i for i in ws if coins[i]==mc]; return max(ws)

if A('bonus'):
    # 头牌改变胜负：同一行动轨迹，只在终局去掉头牌，按完整平局裁决（硬币、座次）重算
    for ver in (2,3):
        cfg=V(ver)
        for n in (2,5):
            rng=random.Random(31); G=10000; flips=0; flips_naive=0
            for _ in range(G):
                pick=[rng.choice(POOL4) for _ in range(n)]
                r=play2([STR[x] for x in pick],cfg,rng)
                w=winner_full(r['sc'],r['coins']); w0=winner_full(r['raw'],r['coins'])
                flips+= w!=w0
                m=max(r['raw']); flips_naive+= w not in [i for i in range(n) if r['raw'][i]==m]
            print(f'v0.{ver} n={n} bonus changed winner (full tiebreak)={100*flips/G:.1f}%  naive={100*flips_naive/G:.1f}%')

def _king(shared=False):
    # 造王：最后一轮座次最后者；只统计"无论他怎么做本轮都会终局"的状态
    def measure(cfg,n,G=8000,seed=21):
        rng=random.Random(seed); km=0; km_old=0; branch=0; can=0
        for _ in range(G):
            pick=[rng.choice(POOL4) for _ in range(n)]; snap={}
            def pre(p,me,market,st,deck):
                if p==n-1: snap['s']=(copy.deepcopy(st),list(market),len(deck))
            r=play2([STR[x] for x in pick],cfg,rng,pre=pre)
            st,m,dk=snap['s']
            if r['rounds']-1!=0 and False: pass
            # 必须是最后一轮：用 rounds 判断——pre 每轮覆盖，最后一次即最后一轮
            me=st[n-1]; outs=[]
            def fin(s2):
                return winner_full(final_scores(s2,cfg),[x['c'] for x in s2]), max(sum(c for c,_ in x['cards']) for x in s2)
            s2=copy.deepcopy(st); s2[n-1]['c']+=cfg.take; outs.append(fin(s2))
            for c in m:
                if cost(c,me,cfg)<=me['c']:
                    s2=copy.deepcopy(st); s2[n-1]['c']-=cost(c,me,cfg); s2[n-1]['cards'].append(c); outs.append(fin(s2))
            ws={w for w,_ in outs}
            all_end=all(mx>=cfg.threshold(n) for _,mx in outs)
            if (n-1) in ws: can+=1; continue
            if len(ws)>=2:
                km_old+=1
                if all_end: km+=1
                else: branch+=1
        return round(100*km/G,2), round(100*km_old/G,2), branch, round(100*can/G,1)
    for ver in ((2,) if shared else (2,3)):
        for n in ((3,5) if shared else (3,4,5)):
            print(f'shared={shared} v0.{ver} n={n} kingmaker(all branches end)%, old%, branch-dependent games, last-can-win%:',measure(V(ver),n))

if A('king'): _king()
if A('king_shared'):
    # 对照：v0.2 改成"并列最多者都得 3 分"，同样只统计所有分支都终局的状态
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
    _king(shared=True)
