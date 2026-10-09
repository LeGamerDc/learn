# C22.2 角色选择（最终版）：货 1 分、币 1 分、厂 = FV 分；建造为可选，只有严格有利才建
def evaluate(me, op, role, FV=3):
    me=dict(me); op=dict(op); gain={}
    for who,d in (('me',me),('op',op)):
        sel=(who=='me'); g=0
        if role=='生产': g=d['厂']+(1 if sel else 0)
        elif role=='交易':
            if d['货']>=1: g+=2   # 卖 1 货：-1 货 +3 币
            if sel: g+=1
        elif role=='建造':
            cost=3 if sel else 4
            if d['币']>=cost and FV-cost>0: g=FV-cost
        gain[who]=g
    return gain['me']-gain['op'], gain
me={'厂':1,'货':0,'币':5}
for op,FV,tag in (({'厂':3,'货':2,'币':1},3,'原'),({'厂':3,'货':0,'币':1},3,'对手没有货'),({'厂':3,'货':2,'币':4},5,'厂值5且对手4币')):
    print(tag,{r:evaluate(me,op,r,FV) for r in ('生产','交易','建造')})
