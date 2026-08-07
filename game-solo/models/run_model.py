"""
共享的单局（run）模型 —— 第 00、02、11、12 章都用它。

一局 = 连续闯 N 个房间：
  · 敌人强度随深度指数增长
  · 玩家受到的伤害由**强度比**决定，且对它高度敏感（指数 DMG_EXP）
  · 战利品提升玩家强度；精英房给大件
  · 血量归零 = 这局结束

关键设计（第 00 章第 3 节会讲为什么）：
  伤害 = BASE_DMG × (敌人强度 / 玩家强度) ^ DMG_EXP

  DMG_EXP 决定了"跟不上"的惩罚有多陡。
  取 1.0 时死因是血线慢性流失，强度比几乎不起作用；
  取 2.0 时跟不上就会被迅速撕碎 —— 这才是 roguelike 的手感。
"""
import numpy as np

# ---------------- 默认参数 ----------------
P = dict(
    rooms=50,
    hp_max=80.0,
    power_0=10.0,
    enemy_0=10.0,
    enemy_growth=1.0495,     # 敌人强度每房间的增长（略快于玩家等效的 1.0489）
    power_gain=1.020,        # 普通房间的强度提升
    elite_every=5,           # 每几个房间一个精英房/宝箱
    elite_bonus=0.15,        # 精英房的大件战利品
    heal_every=8,            # 每几个房间一个休息点
    heal_amount=20.0,
    luck_sigma=0.35,         # 战利品**幅度**的随机性（不影响方向）
    base_dmg=3.9,            # 强度比 = 1 时每房间受到的伤害
    dmg_exp=2.0,             # 伤害对强度比的敏感度
)


def enemy_power(room, p=P):
    return p["enemy_0"] * p["enemy_growth"] ** (room - 1)


def room_damage(power, enemy, p=P):
    """跟不上就会被迅速撕碎：伤害 ∝ (敌/我)^dmg_exp"""
    return p["base_dmg"] * (enemy / max(power, 1e-9)) ** p["dmg_exp"]


def one_run(seed, p=P, hooks=None):
    """
    跑一局。返回 dict：
      died   死在第几个房间；None = 通关
      hist   逐房间的 (房间, 血量, 玩家强度, 敌人强度)
    hooks: 可选的 {"after_room": fn(state, rng) -> None}，供第 02 章插入翻盘机制
    """
    r = np.random.default_rng(seed)
    hp, power = p["hp_max"], p["power_0"]
    hist = []
    for i in range(1, p["rooms"] + 1):
        enemy = enemy_power(i, p)
        hp -= room_damage(power, enemy, p)
        if hp <= 0:
            hist.append((i, 0.0, power, enemy))
            return dict(died=i, hist=np.array(hist))

        # 战利品：随机性作用在**增益幅度**上，永远为正
        power *= 1 + (p["power_gain"] - 1) * r.lognormal(0, p["luck_sigma"])
        if i % p["elite_every"] == 0:
            power *= 1 + p["elite_bonus"] * r.lognormal(0, p["luck_sigma"])

        if hooks and "after_room" in hooks:
            st = dict(room=i, hp=hp, power=power, enemy=enemy, p=p)
            hooks["after_room"](st, r)
            hp, power = st["hp"], st["power"]
            if hp <= 0:
                hist.append((i, 0.0, power, enemy))
                return dict(died=i, hist=np.array(hist))

        if i % p["heal_every"] == 0:
            hp = min(hp + p["heal_amount"], p["hp_max"])
        hist.append((i, hp, power, enemy))
    return dict(died=None, hist=np.array(hist))


def batch(n=5000, p=P, hooks=None, seed0=0):
    """跑 n 局，返回 (通关率, 死亡房间数组)"""
    deaths, wins = [], 0
    for s in range(seed0, seed0 + n):
        res = one_run(s, p, hooks)
        if res["died"] is None:
            wins += 1
        else:
            deaths.append(res["died"])
    return wins / n, np.array(deaths)


def survivable(hp, power, room, p=P, trials=24, threshold=0.05, seed=0):
    """
    从当前状态出发，蒙特卡洛推演剩余流程，估计通关概率。
    低于 threshold 就认为"这局已经没戏了"（第 02 章用它量化无效时间）。
    """
    r = np.random.default_rng(seed)
    wins = 0
    for _ in range(trials):
        h, pw = hp, power
        alive = True
        for i in range(room, p["rooms"] + 1):
            e = enemy_power(i, p)
            h -= room_damage(pw, e, p)
            if h <= 0:
                alive = False
                break
            pw *= 1 + (p["power_gain"] - 1) * r.lognormal(0, p["luck_sigma"])
            if i % p["elite_every"] == 0:
                pw *= 1 + p["elite_bonus"] * r.lognormal(0, p["luck_sigma"])
            if i % p["heal_every"] == 0:
                h = min(h + p["heal_amount"], p["hp_max"])
        wins += alive
    return wins / trials


if __name__ == "__main__":
    w, d = batch(3000)
    print(f"通关率 {w:.1%}   死亡中位 {np.median(d) if len(d) else '-'}")
