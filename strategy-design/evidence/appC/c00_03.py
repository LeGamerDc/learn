# 附录 C：第 00~03 章补充题验算
from fractions import Fraction as F
from functools import lru_cache
import itertools

def ptable(moves, N, misere=False):
    win = {}
    for n in range(N + 1):
        if n == 0:
            win[n] = misere  # 没有硬币轮到你：普通规则你输（对手取了最后一枚）；反常规则你赢
            continue
        win[n] = any(not win[n - m] for m in moves if m <= n)
    return win

print("== C00.1 取 {1,2,4}，9 枚")
w = ptable([1, 2, 4], 12)
print("必败:", [n for n in range(13) if not w[n]])
w = ptable([1, 2, 6], 12)
print("{1,2,6} 必败:", [n for n in range(13) if not w[n]])
print("{1,2,6} 9 枚先手的必胜走法:", [m for m in (1, 2, 6) if m <= 9 and not w[9 - m]])

print("== C00.2 7 枚取1/2，对手随机")
@lru_cache(None)
def pwin_me(n, my_turn, policy_first=None):
    # 我采用最优（对必败点）策略，对手随机等概率合法动作；返回我赢的概率
    if n == 0:
        return F(0) if my_turn else F(1)  # 轮到我时没硬币 = 对手取了最后一枚
    if my_turn:
        return max(pwin_me(n - m, False) for m in (1, 2) if m <= n)
    opts = [m for m in (1, 2) if m <= n]
    return sum(pwin_me(n - m, True) for m in opts) / len(opts)
print("先手取1:", pwin_me(6, False), "先手取2:", pwin_me(5, False))
print("对随机对手，各剩余数下我最优胜率:", {n: str(pwin_me(n, True)) for n in range(1, 8)})

print("== C02.2 井字棋")
LINES = [(1,2,3),(4,5,6),(7,8,9),(1,4,7),(2,5,8),(3,6,9),(1,5,9),(3,5,7)]
def winner(b):
    for l in LINES:
        v = {b[i] for i in l}
        if len(v) == 1 and None not in v:
            return b[l[0]]
    return None
@lru_cache(None)
def solve(bt, player):
    b = dict(zip(range(1, 10), bt))
    w = winner(b)
    if w: return 1 if w == 'X' else -1
    empt = [i for i in range(1, 10) if b[i] is None]
    if not empt: return 0
    vals = []
    for i in empt:
        nb = list(bt); nb[i - 1] = player
        vals.append(solve(tuple(nb), 'O' if player == 'X' else 'X'))
    return max(vals) if player == 'X' else min(vals)
def board(X, O):
    return tuple('X' if i in X else 'O' if i in O else None for i in range(1, 10))
def moves_eval(X, O, player):
    bt = board(X, O)
    res = {}
    for i in range(1, 10):
        if bt[i - 1] is None:
            nb = list(bt); nb[i - 1] = player
            res[i] = solve(tuple(nb), 'O' if player == 'X' else 'X')
    return res
print("X 5,9 / O 1, O 走:", moves_eval({5, 9}, {1}, 'O'))
print("X 5,8 / O 1, O 走:", moves_eval({5, 8}, {1}, 'O'))
print("X 5,6 / O 1, O 走:", moves_eval({5, 6}, {1}, 'O'))

print("== C02.3 重力三连 求解")
COLS, ROWS = 5, 4
def g_lines():
    L = []
    for c in range(COLS):
        for r in range(ROWS):
            for dc, dr in ((1,0),(0,1),(1,1),(1,-1)):
                cells = [(c + k*dc, r + k*dr) for k in range(3)]
                if all(0 <= x < COLS and 0 <= y < ROWS for x, y in cells):
                    L.append(cells)
    return L
GL = g_lines()
def g_win(grid):
    for l in GL:
        v = {grid.get(p) for p in l}
        if len(v) == 1 and None not in v:
            return grid[l[0]]
    return None
@lru_cache(None)
def g_solve(state, player):
    grid = dict(state)
    w = g_win(grid)
    if w: return 1 if w == 'X' else -1
    legal = []
    for c in range(COLS):
        h = sum(1 for r in range(ROWS) if (c, r) in grid)
        if h < ROWS: legal.append((c, h))
    if not legal: return 0
    vals = []
    for p in legal:
        g2 = dict(grid); g2[p] = player
        vals.append(g_solve(tuple(sorted(g2.items())), 'O' if player == 'X' else 'X'))
    return max(vals) if player == 'X' else min(vals)
def g_eval(grid, player):
    res = {}
    for c in range(COLS):
        h = sum(1 for r in range(ROWS) if (c, r) in grid)
        if h < ROWS:
            g2 = dict(grid); g2[(c, h)] = player
            res[c + 1] = g_solve(tuple(sorted(g2.items())), 'O' if player == 'X' else 'X')
    return res
def G(s):
    # s: dict "列行"->X/O，列行从1开始
    return {(int(k[0]) - 1, int(k[1]) - 1): v for k, v in s.items()}
# 局面：行1: X O . . X ; 行2: . X . . . ; 轮到 O（X 4 子 O 3 子? 需平衡）
pos = G({'11': 'X', '21': 'O', '31': 'X', '22': 'X', '41': 'O', '32': 'O'})
print("局面A 轮到X:", g_eval(pos, 'X'))
pos2 = G({'11': 'X', '21': 'O', '31': 'X', '22': 'X', '41': 'O', '32': 'O', '51': 'X'})
print("局面A+X51 轮到O:", g_eval(pos2, 'O'))
