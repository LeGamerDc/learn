# 第31章 座位偏差重新诊断：对照实验
# 用法：python3 -I seatdiag.py [exp...]
import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from final import *

def play2(strats,cfg,rng,order=None,end='round',hook=None,pre=None,post=None,want_deck=False):
    """与 sim.play 相同的规则，增加：order(rnd,n,rng)->本轮行动顺序；end='round'|'immediate'。
    刷新：连续 refresh_after 整轮无人招揽，且牌堆非空，才刷新；刷新后计数归零（与脚本 sim.play 一致）。"""
    n=len(strats); deck=cfg.deck(n)[:]; rng.shuffle(deck); msize=cfg.market(n)
    market=[deck.pop() for _ in range(min(msize,len(deck)))]
    st=[{'c':cfg.start(i,n),'cards':[],'turns':0,'r1':False} for i in range(n)]
    rnd=0; idle=0; ended=None
    while True:
        seq=order(rnd,n,rng) if order else range(n); bought=False; stop=False
        for p in seq:
            me=st[p]; me['c']+=len(me['cards']); me['turns']+=1
            aff=[i for i,c in enumerate(market) if cost(c,me,cfg)<=me['c']]
            if pre: pre(p,me,market,st,deck)
            ch=strats[p](me,st,p,market,aff,rnd,cfg,rng) if aff else None
            if post: post(p,me,market,ch)
            if ch is None: me['c']+=cfg.take
            else:
                card=market.pop(ch); me['c']-=cost(card,me,cfg); me['cards'].append(card); bought=True
                if rnd==0: me['r1']=True; me['first']=card[0]
                if deck: market.append(deck.pop())
            if end=='immediate' and sum(r for r,s in me['cards'])>=cfg.threshold(n): stop=True; break
        if hook: hook(rnd,st)
        rnd+=1
        idle=0 if bought else idle+1
        if cfg.refresh and idle>=cfg.refresh_after and deck:
            idle=0; old=market[:]; market.clear(); deck[:0]=old
            for _ in range(min(msize,len(deck))): market.append(deck.pop())
        raw=[sum(r for r,s in x['cards']) for x in st]
        if stop or max(raw)>=cfg.threshold(n): ended='score'; break
        if not market and not deck: ended='supply'; break
        if rnd>=cfg.max_rounds: ended='cap'; break
    sc=final_scores(st,cfg)
    return {'raw':[sum(r for r,s in x['cards']) for x in st],'sc':sc,'coins':[x['c'] for x in st],'turns':[x['turns'] for x in st],'r1':[x['r1'] for x in st],'first':[x.get('first') for x in st],
            'rounds':rnd,'ended':ended,'deck':len(deck),'market':len(market)}

def credit(r,tie):
    """返回每个座位得到的胜利份额（和为 1）。"""
    sc=r['sc']; n=len(sc); m=max(sc); ws=[i for i in range(n) if sc[i]==m]
    out=[0.0]*n
    if tie=='rule':      # 先比硬币，再座次靠后
        mc=max(r['coins'][i] for i in ws); ws=[i for i in ws if r['coins'][i]==mc]; out[max(ws)]=1
    elif tie=='split':   # 平分胜利
        for i in ws: out[i]=1/len(ws)
    elif tie=='coins_split':
        mc=max(r['coins'][i] for i in ws); ws=[i for i in ws if r['coins'][i]==mc]
        for i in ws: out[i]=1/len(ws)
    elif tie=='late': out[max(ws)]=1
    elif tie=='early': out[min(ws)]=1
    return out

def run(cfg,n,G=20000,seed=2,order=None,end='round',pool=POOL4):
    rng=random.Random(seed); res=[]
    for _ in range(G):
        pick=[rng.choice(pool) for _ in range(n)]
        res.append(play2([STR[x] for x in pick],cfg,rng,order=order,end=end))
    return res

def report(tag,res,ties=('rule','split','coins_split'),extra=True):
    n=len(res[0]['sc']); G=len(res); line=[tag]
    for t in ties:
        acc=[0.0]*n
        for r in res:
            c=credit(r,t); acc=[a+b for a,b in zip(acc,c)]
        line.append(f"{t}:"+'/'.join(f'{100*a/G:.1f}' for a in acc))
    if extra:
        tie=sum(1 for r in res if sorted(r['sc'])[-1]==sorted(r['sc'])[-2])/G
        r1=[100*sum(r['r1'][i] for r in res)/G for i in range(n)]
        line.append(f"tie%={100*tie:.1f} rounds={statistics.mean(r['rounds'] for r in res):.2f} r1buy="+'/'.join(f'{x:.0f}' for x in r1))
        uneq=sum(1 for r in res if len(set(r['turns']))>1)/G
        line.append(f"uneq_turns%={100*uneq:.1f}")
    print('  '.join(line)); sys.stdout.flush()

rot=lambda rnd,n,rng:[(rnd+i)%n for i in range(n)]
rev1=lambda rnd,n,rng: list(range(n))[::-1] if rnd==0 else list(range(n))
def rand1(rnd,n,rng):
    s=list(range(n))
    if rnd==0: rng.shuffle(s)
    return s
def randlater(rnd,n,rng):
    s=list(range(n))
    if rnd>0: rng.shuffle(s)
    return s
def randall(rnd,n,rng):
    s=list(range(n)); rng.shuffle(s); return s

if __name__=='__main__':
    exps=sys.argv[1:] or ['base']
    n=5
    if 'base' in exps:
        for st in (3,4,6,7):
            report(f'v0.1 start{st}',run(V(1,start=lambda i,n,st=st:st),n))
        report('v0.1 market6',run(V(1,market=lambda n:6),n))
        report('v0.1 start4 market6',run(V(1,start=lambda i,n:4,market=lambda n:6),n))
    if 'order' in exps:
        for st in (3,6):
            c=V(1,start=lambda i,n,st=st:st)
            report(f'start{st} round1 reversed',run(c,n,order=rev1))
            report(f'start{st} round1 random',run(c,n,order=rand1))
            report(f'start{st} later rounds random',run(c,n,order=randlater))
            report(f'start{st} all rounds random',run(c,n,order=randall))
            report(f'start{st} rotate start player',run(c,n,order=rot))
    if 'end' in exps:
        for st in (3,6):
            c=V(1,start=lambda i,n,st=st:st)
            report(f'start{st} immediate end',run(c,n,end='immediate'))
