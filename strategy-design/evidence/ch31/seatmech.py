# 第31章：第一轮行动顺序通过什么机制变成座位差？按座位统计第一轮买到的牌、各轮末的牌数、硬币、口碑
import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from seatdiag import *
def mech(cfg,n=5,G=20000,seed=2,order=None):
    rng=random.Random(seed); agg=defaultdict(lambda:[0.0]*n); fc=[0]*n; fs=[0]*n
    for _ in range(G):
        snaps={}
        def hook(rnd,st): snaps[rnd]=[(len(x['cards']),x['c'],sum(r for r,s in x['cards'])) for x in st]
        pick=[rng.choice(POOL4) for _ in range(n)]
        r=play2([STR[x] for x in pick],cfg,rng,order=order,hook=hook)
        for p,v in enumerate(r['first']):
            if v is not None: fs[p]+=v; fc[p]+=1
        for R in (0,1,2):
            for p,(k,c,sc) in enumerate(snaps[R]):
                agg[f'cards_end_r{R+1}'][p]+=k; agg[f'coins_end_r{R+1}'][p]+=c; agg[f'rep_end_r{R+1}'][p]+=sc
    out={'first_card_avg':[round(fs[p]/max(1,fc[p]),2) for p in range(n)]}
    for k in ('coins_end_r1','cards_end_r2','coins_end_r2','cards_end_r3','rep_end_r3'):
        out[k]=[round(v/G,2) for v in agg[k]]
    return out
if __name__=='__main__':
    for tag,c in [('start3',V(1)),('start3 market6',V(1,market=lambda n:6)),('start4 market6',V(1,start=lambda i,n:4,market=lambda n:6)),('start6',V(1,start=lambda i,n:6)),('start6 market6',V(1,start=lambda i,n:6,market=lambda n:6))]:
        print(tag,mech(c)); sys.stdout.flush()
