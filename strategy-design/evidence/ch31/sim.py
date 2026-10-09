# 第31章：端到端实战的固定策略模拟器（N 人通用）
import random, statistics, itertools
from collections import Counter, defaultdict

class Cfg:
    def __init__(self, **kw):
        self.ranks=range(1,7); self.suits=4; self.market=lambda n:3; self.start=lambda seat,n:3
        self.take=2; self.threshold=lambda n:15; self.suit_bonus=0; self.max_rounds=40
        self.deck_fn=None; self.tie='late'  # late seat wins ties
        self.discount=False
        self.__dict__.update(kw)
    def deck(self,n):
        if self.deck_fn: return self.deck_fn(n)
        return [(r,s) for s in range(self.suits) for r in self.ranks]

def cost(card, me, cfg):
    r,s=card
    if cfg.discount:
        d=sum(1 for c in me['cards'] if c[1]==s)
        return max(0,r-d)
    return r

def score(me,cfg,allp=None):
    sc=sum(r for r,s in me['cards'])
    return sc

def final_scores(st,cfg):
    sc=[sum(r for r,s in p['cards']) for p in st]
    if cfg.suit_bonus:
        for s in range(4):
            cnt=[sum(1 for c in p['cards'] if c[1]==s) for p in st]
            m=max(cnt)
            if m>0 and cnt.count(m)==1:
                sc[cnt.index(m)]+=cfg.suit_bonus
    return sc

def play(strats, cfg, rng, log=None):
    n=len(strats)
    deck=cfg.deck(n)[:]; rng.shuffle(deck)
    msize=cfg.market(n)
    market=[deck.pop() for _ in range(min(msize,len(deck)))]
    st=[{'c':cfg.start(i,n),'cards':[],'forced':0,'turns':0,'took':0} for i in range(n)]
    rnd=0; ended_by=None
    stats={'forced':0,'turns':0,'empty_market_turns':0}
    while True:
        bought_this_round=False
        for p in range(n):
            me=st[p]; me['c']+=len(me['cards']); me['turns']+=1; stats['turns']+=1
            aff=[i for i,c in enumerate(market) if cost(c,me,cfg)<=me['c']]
            if not market: stats['empty_market_turns']+=1
            if not aff: stats['forced']+=1
            if getattr(cfg,'pre_hook',None): cfg.pre_hook(p,me,market)
            ch=strats[p](me,st,p,market,aff,rnd,cfg,rng) if aff else None
            if getattr(cfg,'post_hook',None): cfg.post_hook(p,me,market,ch)
            if ch is None:
                me['c']+=cfg.take; me['took']+=1
            else:
                card=market.pop(ch); me['c']-=cost(card,me,cfg); me['cards'].append(card); bought_this_round=True
                if deck: market.append(deck.pop())
        rnd+=1
        if not bought_this_round: idle_rounds=locals().get('idle_rounds',0)+1
        else: idle_rounds=0
        if getattr(cfg,'refresh',False) and idle_rounds>=getattr(cfg,'refresh_after',1) and deck:
            stats['refreshes']=stats.get('refreshes',0)+1; idle_rounds=0
            # 整轮无人买牌：市场的牌放到牌堆底，重新翻开
            old=market[:]; market.clear()
            deck[:0]=old
            for _ in range(min(msize,len(deck))): market.append(deck.pop())
        raw=[sum(r for r,s in x['cards']) for x in st]
        if max(raw)>=cfg.threshold(n): ended_by='score'; break
        if not market and not deck: ended_by='supply'; break
        if rnd>=cfg.max_rounds: ended_by='cap'; break
    sc=final_scores(st,cfg)
    m=max(sc); winners=[i for i,v in enumerate(sc) if v==m]
    if cfg.tie=='late': w=max(winners)
    elif cfg.tie=='coins':
        mc=max(st[i]['c'] for i in winners); ws=[i for i in winners if st[i]['c']==mc]; w=max(ws)
    else: w=winners[0]
    return {'winner':w,'rounds':rnd,'ended_by':ended_by,'scores':sc,
            'coins_left':[x['c'] for x in st],'deck_left':len(deck)+len(market),
            'forced_frac':stats['forced']/stats['turns'],'empty_frac':stats['empty_market_turns']/stats['turns'],
            'refreshes':stats.get('refreshes',0),'cards':[len(x['cards']) for x in st],'suitcnt':[[sum(1 for c in x['cards'] if c[1]==su) for su in range(4)] for x in st]}

# ---------- 固定策略 ----------
def greedy(me,st,p,m,aff,rnd,cfg,rng):
    return max(aff,key=lambda i:(m[i][0],-i))
def engine(k):
    def f(me,st,p,m,aff,rnd,cfg,rng):
        if len(me['cards'])<k: return min(aff,key=lambda i:(cost(m[i],me,cfg),i))
        return max(aff,key=lambda i:(m[i][0],-i))
    f.__name__=f'engine{k}'; return f
def big(me,st,p,m,aff,rnd,cfg,rng):
    a=[i for i in aff if m[i][0]>=5]
    return max(a,key=lambda i:m[i][0]) if a else None
def rnd_s(me,st,p,m,aff,rnd,cfg,rng):
    if rng.random()<0.5: return None
    return rng.choice(aff)
def suit_col(me,st,p,m,aff,rnd,cfg,rng):
    # 花色收集：先定主花色（第一张牌的花色），优先买主花色里最贵的，否则按 engine2
    if me['cards']:
        cnt=Counter(c[1] for c in me['cards']); main=cnt.most_common(1)[0][0]
        a=[i for i in aff if m[i][1]==main]
        if a: return max(a,key=lambda i:m[i][0])
    return engine(2)(me,st,p,m,aff,rnd,cfg,rng)
STR={'冲分':greedy,'引擎2':engine(2),'引擎3':engine(3),'囤大':big,'随机':rnd_s}

def mirror(cfg, name, n, G=20000, seed=1):
    rng=random.Random(seed); res=[play([STR[name]]*n,cfg,rng) for _ in range(G)]
    return res

def summarize(res,n):
    G=len(res)
    seat=Counter(r['winner'] for r in res)
    return {
      'rounds':round(statistics.mean(r['rounds'] for r in res),2),
      'score_end%':round(100*sum(r['ended_by']=='score' for r in res)/G,1),
      'supply_end%':round(100*sum(r['ended_by']=='supply' for r in res)/G,1),
      'cap%':round(100*sum(r['ended_by']=='cap' for r in res)/G,1),
      'deck_left':round(statistics.mean(r['deck_left'] for r in res),2),
      'coins_left':round(statistics.mean(statistics.mean(r['coins_left']) for r in res),2),
      'forced%':round(100*statistics.mean(r['forced_frac'] for r in res),1),
      'cards_each':round(statistics.mean(statistics.mean(r['cards']) for r in res),2),
      'win_score':round(statistics.mean(max(r['scores']) for r in res),2),
      'seat%':[round(100*seat[i]/G,1) for i in range(n)],
    }

def mixed(cfg, names, n, G=20000, seed=2):
    # 每局随机给各座位分配策略（可重复），统计每种策略的胜率 / 期望 1/n
    rng=random.Random(seed); wins=Counter(); plays=Counter()
    for _ in range(G):
        pick=[rng.choice(names) for _ in range(n)]
        r=play([STR[x] for x in pick],cfg,rng)
        for x in pick: plays[x]+=1
        wins[pick[r['winner']]]+=1
    return {x: round(wins[x]/plays[x]*n,3) for x in names}  # 1.0 = 平均水平

def matrix2(cfg, names, G=4000, seed=3):
    # 2 人：行=我，列=对手；先后手各一半；返回我的胜率
    out={}
    for a in names:
        for b in names:
            rng=random.Random(seed); w=0
            for g in range(G):
                if g%2==0:
                    r=play([STR[a],STR[b]],cfg,rng); w+= r['winner']==0
                else:
                    r=play([STR[b],STR[a]],cfg,rng); w+= r['winner']==1
            out[(a,b)]=w/G
    return out

# ---------- 计划存活率：你看中一张"下回合才买得起"的牌，它到你下回合还在不在 ----------
def plan_survival(cfg, name, n, G=4000, seed=5):
    """计划存活率：某玩家本回合拿币（未买牌），且市场里有一张"下回合才买得起"的牌，
    记最大的那张为目标；到他下一个回合开始（收入之后、决策之前）检查它是否仍在市场。
    修正版：用 play() 的钩子，每个回合都会检查，不论当回合有没有买得起的牌。"""
    rng=random.Random(seed); cnt={'alive':0,'total':0}; targets={}
    def pre(p,me,market):
        if p in targets:
            cnt['total']+=1; cnt['alive']+= targets[p] in market; del targets[p]
    def post(p,me,market,ch):
        if ch is None:
            inc=len(me['cards'])
            nxt=[c for c in market if me['c']<cost(c,me,cfg)<=me['c']+inc+cfg.take]
            if nxt: targets[p]=max(nxt)
    old_pre,old_post=getattr(cfg,'pre_hook',None),getattr(cfg,'post_hook',None)
    cfg.pre_hook,cfg.post_hook=pre,post
    try:
        for _ in range(G):
            targets.clear(); play([STR[name]]*n, cfg, rng)
    finally:
        cfg.pre_hook,cfg.post_hook=old_pre,old_post
    return cnt['alive']/cnt['total'] if cnt['total'] else None

def saver(me,st,p,m,aff,rnd,cfg,rng):
    # 等牌：若市场上有一张"下回合才买得起、且比现在能买的最贵牌高 2 点以上"的牌，就进货等它
    inc=len(me['cards'])
    best_now=max((m[i][0] for i in aff),default=0)
    nxt=[c for c in m if me['c']<cost(c,me,cfg)<=me['c']+inc+cfg.take and c[0]>=best_now+2]
    if nxt: return None
    if not aff: return None
    return engine(2)(me,st,p,m,aff,rnd,cfg,rng)
STR['等牌']=saver

STR['花色']=suit_col
POOL=['冲分','引擎2','引擎3','花色']
def mixed_seats(cfg, n, G=10000, seed=7, pool=POOL):
    rng=random.Random(seed); seat=Counter(); res=[]
    for _ in range(G):
        pick=[rng.choice(pool) for _ in range(n)]
        r=play([STR[x] for x in pick],cfg,rng); res.append(r)
    s=summarize(res,n)
    ties=sum(1 for r in res if sorted(r['scores'])[-1]==sorted(r['scores'])[-2])/len(res)
    s['tie%']=round(100*ties,1)
    s['deck_used%']=round(100*(1-s['deck_left']/len(cfg.deck(n))),1)
    return s

def final_scores_v(st,cfg):
    sc=[sum(r for r,s in p['cards']) for p in st]
    if cfg.suit_bonus:
        for s in range(4):
            cnt=[sum(1 for c in p['cards'] if c[1]==s) for p in st]
            m=max(cnt)
            if m>=getattr(cfg,'suit_min',1) and cnt.count(m)==1:
                sc[cnt.index(m)]+=cfg.suit_bonus
    return sc
final_scores.__code__=final_scores_v.__code__

def suit_engine(k=2):
    def f(me,st,p,m,aff,rnd,cfg,rng):
        cnt=Counter(c[1] for c in me['cards'])
        main=cnt.most_common(1)[0][0] if cnt else None
        if len(me['cards'])<k:
            # 便宜优先；同价时偏好主花色
            return min(aff,key=lambda i:(cost(m[i],me,cfg), 0 if m[i][1]==main else 1, i))
        best=max(m[i][0] for i in aff)
        a=[i for i in aff if m[i][1]==main and m[i][0]>=best-2]
        if a: return max(a,key=lambda i:m[i][0])
        return max(aff,key=lambda i:(m[i][0],-i))
    return f
STR['花色2']=suit_engine(2)

def blocker(k=2, slack=2):
    # 抢花：先按引擎买够 k 张；之后在"不比最贵可买牌低 slack 点以上"的牌里，优先买对手最集中的那个花色（拆他的老大）
    def f(me,st,p,m,aff,rnd,cfg,rng):
        if len(me['cards'])<k: return min(aff,key=lambda i:(cost(m[i],me,cfg),i))
        # 找对手里某花色张数最多的（且 >= 我在该花色的张数）
        target=None; best_cnt=0
        for q,op in enumerate(st):
            if q==p: continue
            cnt=Counter(c[1] for c in op['cards'])
            for su,c in cnt.items():
                mine=sum(1 for x in me['cards'] if x[1]==su)
                if c>best_cnt and c>=mine: best_cnt=c; target=su
        best=max(m[i][0] for i in aff)
        if target is not None and best_cnt>=2:
            a=[i for i in aff if m[i][1]==target and m[i][0]>=best-slack]
            if a: return max(a,key=lambda i:m[i][0])
        return max(aff,key=lambda i:(m[i][0],-i))
    return f
STR['抢花']=blocker()

# 与第 15 章一致的代号
STR['E2']=STR['引擎2']; STR['E3']=STR['引擎3']; STR['G']=STR['冲分']; STR['H']=STR['囤大']
STR['S']=STR['花色2']; STR['B']=STR['抢花']; STR['R']=STR['随机']
