#!/usr/bin/env python3
"""跨章引用检查：'思考路径 N.k' 是否存在；'第 NN 章 X.Y 节 / §X.Y' 指向的小节号是否存在于该章标题中。

小节号精确匹配（引用 4.3 节，就必须有编号为 4.3 的标题，不退回到第 4 节）。
思考路径的章号不存在也算错误。有问题时以非零状态退出。
注意：这个脚本只能发现"引用的编号不存在"，发现不了"编号存在但指错了内容"，后者要人工核对。
"""
import re, glob, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
chap = {}
for f in glob.glob(os.path.join(ROOT, "[0-3][0-9]-*.md")):
    n = int(os.path.basename(f)[:2]); chap[n] = open(f, encoding="utf-8").read()
paths = {n: set(re.findall(r"^#+ 思考路径 (\d+\.\d+)", t, re.M)) for n, t in chap.items()}
secs = {n: set(re.findall(r"^#+ (\d+(?:\.\d+)*)[ .、]", t, re.M)) for n, t in chap.items()}
problems = 0
for f in sorted(glob.glob(os.path.join(ROOT, "*.md"))):
    name = os.path.basename(f); t = open(f, encoding="utf-8").read()
    for m in re.finditer(r"思考路径\s*(\d+)\.(\d+)", t):
        n, k = int(m.group(1)), m.group(2)
        if n not in paths:
            print(f"{name}: 思考路径 {n}.{k} 的章号不存在"); problems += 1
        elif f"{n}.{k}" not in paths[n]:
            print(f"{name}: 思考路径 {n}.{k} 不存在（第 {n:02d} 章有 {sorted(paths[n])}）"); problems += 1
    for m in re.finditer(r"第\s*(\d+)\s*章[^，。；\n第]{0,8}?(?:§\s*(\d+(?:\.\d+)*)|第\s*(\d+(?:\.\d+)*)\s*节|(\d+\.\d+(?:\.\d+)*)\s*节)", t):
        n, s = int(m.group(1)), (m.group(2) or m.group(3) or m.group(4))
        if re.search(r"game-[a-z]+\s*$", t[max(0, m.start() - 20):m.start()]):
            continue  # 引用的是同仓库其他课程（game-numeric、game-design）的章节
        if n not in secs:
            print(f"{name}: 第 {n} 章 不存在"); problems += 1
        elif s not in secs[n]:
            print(f"{name}: 第 {n} 章 {s} 节 不存在"); problems += 1
print("xref problems:", problems)
sys.exit(1 if problems else 0)
