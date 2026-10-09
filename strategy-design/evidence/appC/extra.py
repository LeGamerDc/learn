# 附录 C 补充验算：C10.4 侦察价值、C27.3 两名坏人同在 3 人队、C17.3 后手选骰
from fractions import Fraction as F
from math import comb
from itertools import product
g=F(4,5); print('C10.4 侦察期望', g*(2-1)+(1-g)*(4-1), '对比均衡 8/5')
print('C27.3 两坏人同在随机3人队', F(comb(3,1),comb(5,3)))
D={'A':[4,4,4,4,0,0],'B':[3]*6,'C':[6,6,2,2,2,2],'D':[5,5,5,1,1,1]}
pw=lambda x,y:F(sum(a>b for a,b in product(D[x],D[y])),36)
print('C17.3 先手选每颗骰子时后手最佳胜率',{x:max(pw(y,x) for y in D if y!=x) for x in D})
