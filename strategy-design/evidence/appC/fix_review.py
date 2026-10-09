# 附录 C 复评修正验算（review-appC.md）
from functools import lru_cache
from fractions import Fraction as F
from itertools import product
import math

print('== C03.2 两堆：一堆取1/2，或两堆各取1')
def moves(a,b):
    r=set()
    for k in (1,2):
        if a>=k: r.add(tuple(sorted((a-k,b))))
        if b>=k: r.add(tuple(sorted((a,b-k))))
    if a>=1 and b>=1: r.add(tuple(sorted((a-1,b-1))))
    return r
@lru_cache(None)
def W(a,b,misere):
    ms=moves(a,b)
    if not ms: return misere  # 轮到你没子可取：常规=对手取了最后一枚，你输；misere=对手取了最后一枚输，你赢
    return any(not W(x,y,misere) for x,y in ms)
for mis in (False,True):
    print(' misere' if mis else ' normal', [(a,b) for a in range(7) for b in range(a,7) if not W(a,b,mis)])
print(' (3,4) normal win?',W(3,4,False),' 制胜着:',[m for m in moves(3,4) if not W(*m,False)])
print(' 从(3,3)对手各步 -> 我的应对(到必败点):')
for m in sorted(moves(3,3)):
    print('   ',m,'->',[x for x in moves(*m) if not W(*x,False)])
print(' 镜像反例：(3,3)->(2,2)->(1,1)，(1,1) 轮到对手 win?',W(1,1,False))

print('== C03.3 每人一次跳过；取1或2，取最后者胜')
@lru_cache(None)
def S(n,me,op):  # 轮到"me"
    if n==0: return False
    opts=[not S(n-k,op,me) for k in (1,2) if k<=n]
    if me: opts.append(not S(n,op,False))
    return any(opts)
for me,op in ((1,1),(1,0),(0,1),(0,0)):
    print(' 我有跳过=%d 对手有跳过=%d 必败点(1..12):'%(me,op),[n for n in range(1,13) if not S(n,me,op)])

print('== C04.1 卡坦（A:6,5,9；B:4,9,10），4 次掷骰独立，忽略强盗移动/资源短缺')
pip={2:1,3:2,4:3,5:4,6:5,8:5,9:4,10:3,11:2,12:1}
for name,nums in (('A',(6,5,9)),('B',(4,9,10)),('A压6',(5,9))):
    p=F(sum(pip[x] for x in nums),36)
    print(' ',name,'pips',sum(pip[x] for x in nums),'单次',p,float(p),'每轮期望',float(4*p),'至少一次',float(1-(1-p)**4))

print('== C14.1 新(a)：以牙还牙 对 前6轮合作、第7轮起永远背叛')
def pd(s1,s2,R=12):
    h1=[];h2=[];a=b=0
    pay={('C','C'):(3,3),('C','D'):(0,5),('D','C'):(5,0),('D','D'):(1,1)}
    for t in range(R):
        m1=s1(t,h2,R); m2=s2(t,h1,R); x,y=pay[(m1,m2)]; a+=x;b+=y; h1.append(m1);h2.append(m2)
    return a,b
tft=lambda t,h,R:'C' if t==0 else h[-1]
late=lambda t,h,R:'C' if t<6 else 'D'
tftL=lambda t,h,R:'D' if t==R-1 else tft(t,h,R)
print(' TFT vs late',pd(tft,late),' TFT vs TFT',pd(tft,tft),' TFT vs TFT末轮背叛',pd(tft,tftL),' 两个末轮背叛',pd(tftL,tftL))

print('== C14.2 整数分配')
for x in range(13):
    me,he=x,12-x
    print('  x=%2d 我%2d 他%2d 分差%+d | 谈不成 4:5 分差-1 | 我按分差接受%s 他按分差接受%s'%(x,me,he,me-he,me-he>=-1,he-me>=1))

print('== C16.3 首手上限 2 vs 3 的开局必败点')
@lru_cache(None)
def win(n,cap):
    if n==0: return False
    return any(not win(n-k,k+1) for k in range(1,min(cap,n)+1))
for cap in (2,3):
    print('  首手上限',cap,[n for n in range(1,26) if not win(n,cap)])

print('== C19.3 两人；8/5/3；我放1枚，对手看后放1枚；新规：第二名（含0兵）得一半向下取整，并列平分名次=分差0')
vals=(8,5,3)
def margin(me,op,rule):
    m=0
    for v,a,b in zip(vals,me,op):
        if a==b: continue
        w = v if rule=='orig' else v - v//2
        m += w if a>b else -w
    return m
def best(me0,op0,rule,k=1):
    res={}
    for i in range(3):
        me=list(me0); me[i]+=1
        worst=None
        for js in product(range(3),repeat=k):
            op=list(op0)
            for j in js: op[j]+=1
            v=margin(me,op,rule); worst=v if worst is None else min(worst,v)
        res['北中南'[i]]=worst
    return res
for me0,op0 in (((1,0,0),(0,1,0)),((0,1,2),(2,0,0))):
    print('  我',me0,'对手',op0,' 原版',best(me0,op0,'orig'),' 新版',best(me0,op0,'half'))
print('  偶数分值 8/6/4 时分差权重', [v - v//2 for v in (8,6,4)], '原', (8,6,4))

print('== C25.2 加权胜率')
T={'快':[50,55,65,40],'中':[45,50,55,60],'控':[35,45,50,70],'组':[60,40,30,50]}
for mix in ((40,30,20,10),(20,30,20,30)):
    print('  ',mix,{k:sum(a*b for a,b in zip(v,mix))/100 for k,v in T.items()})

print('== C26.2 飞牌（东出K则A，否则Q）与砸落')
for e,w in ((4,6),(7,3),(5,5)):
    pK=F(e,e+w); split=F(e,e+w)*F(w,e+w-1)+F(w,e+w)*F(e,e+w-1)
    print('  东%d西%d 飞牌%s=%.3f 砸落%s=%.3f'%(e,w,pK,float(pK),split,float(split)))

print('== C29.2 两个可能期限下，是否存在同时最优的序列（单人三动作原型）')
def run(seq):
    c=inc=s=0; out=[]
    for a in seq:
        c+=inc
        if a=='拿': c+=3
        elif a=='换':
            if c<4: return None
            c-=4; s+=3
        else:
            if c<2: return None
            c-=2; inc+=1
        out.append(s)
    return out
best_at={}
for T in range(4,13):
    best_at[T]=max(r[-1] for r in (run(q) for q in product('拿换投',repeat=T)) if r)
print('  各长度最高分',best_at)
def both(L1,L2):
    cnt=0; ex=None
    for q in product('拿换投',repeat=L2):
        r=run(q)
        if r and r[L1-1]==best_at[L1] and r[-1]==best_at[L2]:
            cnt+=1; ex=ex or ''.join(q)
    return cnt,ex
for L1,L2 in ((8,10),(7,10),(6,10),(6,9),(7,9),(5,9),(8,11),(7,11),(9,11),(5,10)):
    c,ex=both(L1,L2); print('  期限',L1,'或',L2,'两者都最优的序列数',c,ex)

print('== C29.2 期限 7 或 10 的取舍')
seqs=[(''.join(q),run(q)) for q in product('拿换投',repeat=10)]
seqs=[(q,r) for q,r in seqs if r]
pairs=sorted(set((r[6],r[9]) for q,r in seqs))
front=[p for p in pairs if not any(o[0]>=p[0] and o[1]>=p[1] and o!=p for o in pairs)]
print('  (第7回合分, 第10回合分) 的帕累托前沿',front)
for a,b in front:
    ex=[q for q,r in seqs if (r[6],r[9])==(a,b)]
    print('   ',(a,b),'序列数',len(ex),'例',ex[:3],'含投资次数',sorted(set(q.count('投') for q in ex)))
for p in (F(1,2),F(1,3),F(2,3)):
    print('  P(第7回合结束)=',p,{f:float(p*f[0]+(1-p)*f[1]) for f in front})
print('  8 或 10 前沿:',sorted(set((r[7],r[9]) for q,r in seqs if not any(False for _ in []))) [-3:])

print('== C06.3 先亮牌变体：第1轮 3x3 节点，之后倒推（胜+1 和0 负-1，行玩家视角）')
from itertools import combinations
def solve_zero_sum(M):
    # 支撑集枚举，返回 (value, p_row, q_col)；M 为 Fraction 矩阵
    import itertools
    R=len(M); C=len(M[0]); best=None
    # 纯策略鞍点
    for i in range(R):
        for j in range(C):
            if M[i][j]==min(M[i]) and M[i][j]==max(M[k][j] for k in range(R)):
                return M[i][j],('pure',i),('pure',j)
    for k in range(2,min(R,C)+1):
        for rs in itertools.combinations(range(R),k):
            for cs in itertools.combinations(range(C),k):
                # 解 q：对 rs 中各行收益相等；p：对 cs 中各列相等
                import fractions
                def solve(A,b):
                    n=len(A); A=[row[:]+[bb] for row,bb in zip(A,b)]
                    for c in range(n):
                        piv=next((r for r in range(c,n) if A[r][c]!=0),None)
                        if piv is None: return None
                        A[c],A[piv]=A[piv],A[c]
                        for r in range(n):
                            if r!=c and A[r][c]!=0:
                                f=A[r][c]/A[c][c]; A[r]=[x-f*y for x,y in zip(A[r],A[c])]
                    return [A[r][n]/A[r][r] for r in range(n)]
                # 变量 q_cs + v
                A=[[M[i][j] for j in cs]+[F(-1)] for i in rs]+[[F(1)]*k+[F(0)]]
                sol=solve(A,[F(0)]*k+[F(1)])
                if not sol: continue
                q=sol[:k]; v=sol[k]
                A2=[[M[i][j] for i in rs]+[F(-1)] for j in cs]+[[F(1)]*k+[F(0)]]
                sol2=solve(A2,[F(0)]*k+[F(1)])
                if not sol2: continue
                p=sol2[:k]
                if min(q)<0 or min(p)<0: continue
                if all(sum(M[i][j]*qq for j,qq in zip(cs,q))<=v for i in range(R)) and all(sum(M[i][j]*pp for i,pp in zip(rs,p))>=v for j in range(C)):
                    return v,dict(zip(rs,p)),dict(zip(cs,q))
    return None
def res(w): return (w>0)-(w<0)
def after(r1, a_rem, b_rem, tally):
    # r1: 第1轮结果 +1 行赢 / -1 列赢 / 0 平；第2轮按规则，第3轮强制
    def final(a2,b2):
        a3=[x for x in a_rem if x!=a2][0]; b3=[x for x in b_rem if x!=b2][0]
        t=tally+res(a2-b2)+res(a3-b3); return F(res(t))
    if r1>0:   # 行玩家先亮，列玩家看后出：行 max over a2 of min over b2
        return max(min(final(a2,b2) for b2 in b_rem) for a2 in a_rem)
    if r1<0:   # 列先亮，行看后出
        return min(max(final(a2,b2) for a2 in a_rem) for b2 in b_rem)
    M=[[final(a2,b2) for b2 in b_rem] for a2 in a_rem]
    return solve_zero_sum(M)[0]
M1=[]
for a1 in (1,2,3):
    row=[]
    for b1 in (1,2,3):
        r=res(a1-b1)
        row.append(after(r,[x for x in (1,2,3) if x!=a1],[x for x in (1,2,3) if x!=b1],r))
    M1.append(row)
print('  第1轮 3x3 节点值（行出1/2/3 × 列出1/2/3）:',[[str(x) for x in r] for r in M1])
print('  均衡', solve_zero_sum(M1))
