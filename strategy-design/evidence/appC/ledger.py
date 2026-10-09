# 小集市 v1 账本可达性：给定面前牌（按点数）、已完成行动轮数，返回所有可能的"下一回合收入前"币数及一条示例账本
def reachable(final_cards, rounds_done):
    final = sorted(final_cards); out = {}
    def dfs(r, coins, owned, remaining, hist):
        if r == rounds_done:
            if not remaining: out.setdefault(coins, hist)
            return
        coins += len(owned)
        if len(remaining) < rounds_done - r:
            dfs(r + 1, coins + 2, owned, remaining, hist + ['进货'])
        for v in sorted(set(remaining)):
            if v <= coins:
                rem = list(remaining); rem.remove(v)
                dfs(r + 1, coins - v, owned + [v], rem, hist + [f'买{v}'])
    dfs(0, 3, [], final, [])
    return out
if __name__ == '__main__':
    for cards in ([2,5,4,3],[6,5,1,2],[2],[3],[1]):
        for rd in (2,5):
            print(cards, rd, {k: v for k, v in sorted(reachable(cards, rd).items())})
