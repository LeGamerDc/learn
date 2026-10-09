from functools import lru_cache
def ptable(moves,N):
    w={0:False}
    for n in range(1,N+1): w[n]=any(not w[n-m] for m in moves if m<=n)
    return w
for mv in ([1,2,5],[1,3,5],[2,3]):
    w=ptable(mv,20); print(mv,'必败',[n for n in range(21) if not w[n]])
w=ptable([1,2,5],20); print('{1,2,5} 16枚 必胜走法',[m for m in (1,2,5) if not w[16-m]])
print('{1,2,5} 13枚 必胜走法',[m for m in (1,2,5) if m<=13 and not w[13-m]])
# 双堆：从一堆取1或2枚，或两堆各取1枚；取最后一枚者胜(normal)/负(misere)
def dp(N,misere):
    @lru_cache(None)
    def win(a,b):
        if a==0 and b==0: return misere
        mv=[]
        for k in (1,2):
            if a>=k: mv.append((a-k,b))
            if b>=k: mv.append((a,b-k))
        if a>=1 and b>=1: mv.append((a-1,b-1))
        return any(not win(*m) for m in mv)
    return win
for mis in (False,True):
    win=dp(8,mis)
    P=[(a,b) for a in range(7) for b in range(a,7) if not win(a,b)]
    print('misere' if mis else 'normal','必败(a<=b<=6):',P)
    a,b=3,4
    def moves(a,b):
        mv=[]
        for k in (1,2):
            if a>=k: mv.append(((a-k,b),f'第一堆取{k}'))
            if b>=k: mv.append(((a,b-k),f'第二堆取{k}'))
        if a>=1 and b>=1: mv.append(((a-1,b-1),'两堆各取1'))
        return mv
    print(' (3,4) 先手', '胜' if win(3,4) else '败', [d for s,d in moves(3,4) if not win(*s)])
    print(' (2,4) 先手', '胜' if win(2,4) else '败', [d for s,d in moves(2,4) if not win(*s)])
# 每人每局可以跳过一次（取币 1~2，取最后一枚者胜）
@lru_cache(None)
def winp(n,me_pass,op_pass):
    if n==0: return False
    opts=[not winp(n-m,op_pass,me_pass) for m in (1,2) if m<=n]
    if me_pass: opts.append(not winp(n,op_pass,False))
    return any(opts)
print('跳过变体 必败(双方都有跳过):',[n for n in range(1,16) if not winp(n,True,True)])
print('跳过变体 n=1..12 先手(双方都有跳过):',{n:winp(n,True,True) for n in range(1,13)})
print('只我有跳过时必败点:',[n for n in range(1,16) if not winp(n,True,False)],' 只对手有:',[n for n in range(1,16) if not winp(n,False,True)])
