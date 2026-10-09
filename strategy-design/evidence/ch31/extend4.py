# 第31章：延长游戏的四组对照（v0.3 基线 / 只改终局线 18 / 只扩牌堆 / 两者都改）；4~5 人扩牌堆 = 两副 A~6
import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from seatdiag import *
two=lambda n:[(r,s) for s in range(4) for r in range(1,7)]*(2 if n>=4 else 1)
for n in (2,5):
    for tag,kw in (('base',{}),('thr18',dict(threshold=lambda n:18)),('2deck',dict(deck_fn=two)),('thr18+2deck',dict(threshold=lambda n:18,deck_fn=two))):
        res=run(V(3,**kw),n)
        G=len(res); de=100*sum(r['deck']==0 for r in res)/G; m3=100*sum(r['market']<3 for r in res)/G
        report(f'v0.3 n={n} {tag} deck_empty={de:.1f}% market<3={m3:.1f}%',res,ties=('rule','split'))
