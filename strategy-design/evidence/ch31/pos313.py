# 思考路径31.3 的构造局面：3 人，最后一轮，C 最后行动
import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from final import *
H,S,C_,D=0,1,2,3  # ♥ ♠ ♣ ♦
A=[(5,H),(4,H),(3,S),(4,C_)]
B=[(6,D),(4,D),(3,H),(2,S)]
C=[(1,H),(2,C_),(1,D),(1,S)]
allc=A+B+C+[(2,H),(3,D),(6,C_)]
assert len(set(allc))==len(allc)
def res(ver,cards_c):
    cfg=V(ver)
    st=[{'c':1,'cards':A},{'c':2,'cards':B},{'c':0,'cards':cards_c}]
    sc=final_scores(st,cfg); return sc
for ver in (2,3):
    print('v0.%d'%ver,'take',res(ver,C),'buy H2',res(ver,C+[(2,H)]),'buy D3',res(ver,C+[(3,D)]))
print('raw',sum(r for r,s in A),sum(r for r,s in B),sum(r for r,s in C))
