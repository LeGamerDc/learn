"""
16 章：用博弈论解兵种平衡

给定一个"我方兵种 × 敌方兵种"的胜率矩阵，求混合策略纳什均衡。
均衡解 = 玩家在充分博弈后，各兵种的实际使用率。

这个工具的真正用途：**用均衡使用率来判断平衡，而不是用胜率。**
胜率 50% 不代表平衡——一个所有人都不用的兵种，胜率也可以是 50%。
"""
import numpy as np
from scipy.optimize import linprog

np.set_printoptions(precision=3, suppress=True)


def solve_zero_sum(A, names):
    """
    求零和博弈的混合策略纳什均衡（行玩家视角）。
    A[i][j] = 我方用 i、敌方用 j 时我方的收益（这里用"胜率 − 0.5"）。

    LP 形式：max v  s.t.  Σ_i x_i·A[i][j] ≥ v  ∀j;  Σx=1;  x≥0
    变量向量 = [x_1 ... x_n, v]
    """
    n = A.shape[0]
    # linprog 求最小值 → 目标 = -v
    c = np.zeros(n + 1)
    c[-1] = -1.0
    # 约束：v − Σ_i x_i·A[i][j] ≤ 0   ∀j
    A_ub = np.hstack([-A.T, np.ones((n, 1))])
    b_ub = np.zeros(n)
    A_eq = np.zeros((1, n + 1))
    A_eq[0, :n] = 1.0
    b_eq = [1.0]
    bounds = [(0, None)] * n + [(None, None)]
    r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                bounds=bounds, method="highs")
    return r.x[:n], r.x[-1]


def report(title, win_rate, names):
    print(f"\n=== {title} ===")
    A = win_rate - 0.5              # 转成零和收益
    x, v = solve_zero_sum(A, names)
    print("胜率矩阵（行=我方，列=敌方）:")
    header = "        " + "".join(f"{n:>8}" for n in names)
    print(header)
    for i, n in enumerate(names):
        print(f"{n:>8}" + "".join(f"{win_rate[i][j]:>8.0%}" for j in range(len(names))))
    print("\n均衡使用率:")
    for n, p in zip(names, x):
        bar = "█" * int(p * 40)
        flag = "   ← 无人使用（废兵种）" if p < 0.01 else ""
        print(f"  {n:>8} {p:>7.1%} {bar}{flag}")
    print(f"  博弈价值 v = {v:+.4f}（0 = 完全对称）")
    return x


# ---------- ① 标准三角克制 ----------
names3 = ["步兵", "骑兵", "弓兵"]
W = np.array([
    [0.50, 0.65, 0.35],     # 步兵 克 骑兵，被 弓兵 克
    [0.35, 0.50, 0.65],     # 骑兵 克 弓兵
    [0.65, 0.35, 0.50],     # 弓兵 克 步兵
])
report("① 对称三角克制（克制加成 ±15%）", W, names3)

# ---------- ② 把骑兵调强 5% ----------
W2 = W.copy()
W2[1, :] += 0.05
W2[:, 1] -= 0.05
np.fill_diagonal(W2, 0.5)
report("② 骑兵整体强 5%（一次看似很小的改动）", W2, names3)

# ---------- ③ 加入一个"全面略强"的兵种：传递性坍缩 ----------
names4 = ["步兵", "骑兵", "弓兵", "重甲"]
W3 = np.full((4, 4), 0.5)
W3[:3, :3] = W
W3[3, :3] = 0.55        # 重甲对三个都略占优
W3[:3, 3] = 0.45
report("③ 新增'重甲'：对所有旧兵种胜率 55%", W3, names4)

# ---------- ④ 尝试修复：给重甲一个克星 ----------
W4 = W3.copy()
W4[2, 3] = 0.62         # 弓兵克重甲
W4[3, 2] = 0.38
report("④ 尝试修复：让弓兵克重甲（62%）—— 注意结果", W4, names4)

# ---------- ⑤ 五兵种循环克制 ----------
names5 = ["步兵", "骑兵", "弓兵", "重甲", "术士"]
n = 5
W5 = np.full((n, n), 0.5)
for i in range(n):
    W5[i][(i + 1) % n] = 0.65          # 克下一个
    W5[(i + 1) % n][i] = 0.35
    W5[i][(i + 2) % n] = 0.60          # 也克下下个（弱一些）
    W5[(i + 2) % n][i] = 0.40
report("⑤ 五兵种循环克制", W5, names5)

# ---------- ⑥ 支撑集奇偶性的实证 ----------
print("\n=== ⑥ 均衡支撑集大小的分布（随机生成的对称克制矩阵，各 200 次）===")
rng = np.random.default_rng(0)
from collections import Counter
for n in (4, 5, 6):
    cnt = Counter()
    for _ in range(200):
        M = rng.normal(0, 0.15, (n, n))
        A = (M - M.T) / 2               # 反对称 = 对称零和博弈
        x, _ = solve_zero_sum(A, None)
        cnt[int((x > 1e-6).sum())] += 1
    print(f"  {n} 个兵种 → 被实际使用的兵种数分布：{dict(sorted(cnt.items()))}")

print("""
关键结论
--------
② 一次 5% 的数值改动，就让均衡使用率从 33/33/33 变成 44/33/22。
   **非传递性系统对数值极其敏感**——这是它的代价，也是它的价值。

③ 只要存在一个"对所有人都略占优"的选项，均衡就会坍缩到它身上，
   其余兵种使用率归零 —— 这就是传递性占优（dominant strategy）。
   注意重甲的胜率只有 55%，看起来"只强一点点"，但均衡使用率是 100%。
   **胜率 55% 和使用率 100% 之间的这个落差，是新手最容易低估的。**

④ 给重甲加一个克星并没有救活它 —— 重甲的使用率变成了 0%。
   只调两个格子解决不了问题。

⑤⑥ 原因在这里：**对称零和博弈的均衡支撑集必然是奇数。**
   （数学上：反对称矩阵的秩必为偶数，由此可推出均衡支撑集为奇数。）
   实证也印证了：4 个和 6 个兵种时，被使用的数量永远是 1 或 3 或 5，
   **绝不会是 2、4、6**。

   ⇒ **偶数个兵种的纯克制系统，注定会有一个兵种没人用。**
   ⇒ 要让偶数个兵种都有价值，必须引入零和之外的因素：
      造价差异、情境价值（地形/关卡/阵容）、组合效应、产能限制。
   ⇒ 或者干脆把兵种数设计成奇数（⑤ 的五兵种循环，均衡是漂亮的 20% × 5）。
""")
