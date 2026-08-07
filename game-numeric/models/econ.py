"""
通用资源流仿真引擎（第 03 章引入，后续章节反复复用）

三个基本元件对应 Machinations 的词汇：
    source     源  —— 凭空产出资源（faucet / 投放）
    drain      汇  —— 让资源消失（sink / 回收）
    converter  转换器 —— 消耗一组资源，产出另一组

核心设计：**所有资源池的增减都必须经过 _give / _take**，
引擎据此自动生成"哪个节点动了哪种资源多少"的账本。
这样 audit() 出来的收支平衡表才是完整且不会算错的。
自定义节点也必须用 _give/_take，不要直接改 econ.p[...]。

用法：
    e = Economy(gold=0, troops=0).cap(stamina=120)
    e.source("矿场", "gold", lambda e: 100 * e.p["level"])
    e.converter("练兵", cost={"gold": 50}, gain={"troops": 1}, times=10)
    e.drain("战损", "troops", lambda e: 0.05 * e.p["troops"])
    df = e.run(180)
    e.audit(df)
"""
from collections import defaultdict

import pandas as pd


class Economy:
    def __init__(self, **initial):
        self.p = {k: float(v) for k, v in initial.items()}   # 资源池 pools
        self.caps = {}          # 资源上限；超出部分算作"溢出"
        self.nodes = []         # [(名字, 类型, 函数)]
        self.t = 0
        self._hist = []
        self._cur = None        # 当前正在执行的节点，用于账本归属
        self._ledger = None     # {(节点, 资源): 净流量}
        self._overflow = {}

    # ---------------- 配置 ----------------
    def cap(self, **kw):
        """设置资源上限（体力上限、仓库容量……）"""
        self.caps.update({k: float(v) for k, v in kw.items()})
        return self

    def add(self, name, kind, fn):
        """挂一个自定义节点。fn(economy) 的返回值会被记录为 @名字 列。"""
        self.nodes.append((name, kind, fn))
        return self

    # ---------------- 三个基本元件 ----------------
    def source(self, name, res, rate):
        """投放：rate 可以是数字，也可以是 fn(economy) -> 数字"""
        def fn(e):
            amt = float(rate(e) if callable(rate) else rate)
            return e._give(res, amt)
        return self.add(name, "source", fn)

    def drain(self, name, res, rate):
        """回收：rate 可以是数字，也可以是 fn(economy) -> 数字"""
        def fn(e):
            amt = float(rate(e) if callable(rate) else rate)
            return e._take(res, amt)
        return self.add(name, "drain", fn)

    def converter(self, name, cost, gain, times=1):
        """
        转换器：消耗 cost 产出 gain，本步最多执行 times 次。
        资源不够就少执行几次。返回实际执行次数。
        """
        def fn(e):
            n = int(times(e) if callable(times) else times)
            done = 0
            for _ in range(max(n, 0)):
                if not all(e.p.get(k, 0.0) >= v for k, v in cost.items()):
                    break
                for k, v in cost.items():
                    e._take(k, v)
                for k, v in gain.items():
                    e._give(k, v)
                done += 1
            return done
        return self.add(name, "converter", fn)

    # ---------------- 池操作（一切增减都走这两个）----------------
    def _give(self, res, amt):
        """加资源，返回实际加进去的量（受上限限制，超出记为溢出）"""
        cur = self.p.get(res, 0.0)
        cap = self.caps.get(res)
        actual = amt
        if cap is not None and cur + amt > cap:
            actual = max(cap - cur, 0.0)
            self._overflow[res] = self._overflow.get(res, 0.0) + (amt - actual)
        self.p[res] = cur + actual
        self._ledger[(self._cur, res)] += actual
        return actual

    def _take(self, res, amt):
        """扣资源，返回实际扣掉的量（不会扣成负数）"""
        cur = self.p.get(res, 0.0)
        actual = min(cur, max(amt, 0.0))
        self.p[res] = cur - actual
        self._ledger[(self._cur, res)] -= actual
        return actual

    # ---------------- 运行 ----------------
    def step(self):
        self.t += 1
        self._overflow = {}
        self._ledger = defaultdict(float)
        row = {"t": self.t}
        for name, kind, fn in self.nodes:
            self._cur = name
            row[f"@{name}"] = fn(self)
        self._cur = None
        for (node, res), v in self._ledger.items():
            row[f"流|{node}|{res}"] = v
        row.update(self.p)
        row.update({f"溢出_{k}": v for k, v in self._overflow.items()})
        self._hist.append(row)
        return row

    def run(self, steps):
        for _ in range(steps):
            self.step()
        return self.history()

    def history(self):
        return pd.DataFrame(self._hist).fillna(0.0).set_index("t")

    # ---------------- 体检 ----------------
    def audit(self, df=None, skip=()):
        """
        按资源打印收支平衡表 —— 判断经济健康的第一步。

        注意：跨资源求和没有意义（金币和兵不能相加），所以必须分资源记账。
        流入 = 该资源所有正向流量之和；流出 = 所有负向流量之和。

        skip: 不参与收支平衡的池子名（等级、进度这类"计数器"，它们本来就只增不减）
        """
        df = self.history() if df is None else df
        flows = defaultdict(dict)     # {资源: {节点: 累计净流量}}
        for c in df.columns:
            if isinstance(c, str) and c.startswith("流|"):
                _, node, res = c.split("|")
                if res in skip:
                    continue
                flows[res][node] = df[c].sum()

        for res in flows:
            print(f"\n=== 资源：{res} ===")
            print(f"{'节点':<14}{'累计流量':>16}")
            print("-" * 32)
            inflow = outflow = 0.0
            for node, v in flows[res].items():
                print(f"{node:<14}{v:>+16,.0f}")
                if v >= 0:
                    inflow += v
                else:
                    outflow += -v
            print("-" * 32)
            print(f"{'投放合计':<20}{inflow:>16,.0f}")
            print(f"{'回收合计':<20}{outflow:>16,.0f}")
            if inflow > 0:
                rate = outflow / inflow
                warn = "   ← 回收不足，会通胀" if rate < 0.85 else ""
                print(f"{'回收率':<20}{rate:>15.1%}{warn}")
            print(f"{'期末存量':<20}{df[res].iloc[-1]:>16,.0f}")
            ovf = f"溢出_{res}"
            if ovf in df.columns and df[ovf].sum() > 0:
                print(f"{'累计溢出':<20}{df[ovf].sum():>16,.0f}   ← 被浪费的投放")
        return df
