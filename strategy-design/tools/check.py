#!/usr/bin/env python3
"""课程一致性检查：字数、必备小节、思考路径数量、链接目标与锚点、上下章链接、可靠性标注。

链接目标除了要在本机存在，还不能被 .gitignore 忽略（否则分发出去的副本里是断链）。
加 --release 时更严格：链接目标必须已经被 git 跟踪（git ls-files 里有），用于提交 / 分发前的门禁。
锚点检查覆盖文件内锚点（#xxx）和带锚点的相对链接，重名标题按 GitHub 规则加 -1、-2 后缀。
有任何问题时以非零状态退出。

用法：python3 tools/check.py [--release]
章节清单从 README.md 的章节表里按文件名顺序读取（NN-*.md），所以增删章节只需改 README。
"""
import os, re, glob, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
expected = []
for m in re.finditer(r"\]\(\./(\d\d-[a-z0-9-]+\.md)\)", readme):
    if m.group(1) not in expected:
        expected.append(m.group(1))

RELEASE = "--release" in sys.argv
SKIP_DIRS = {".authoring", "notes", ".git", ".obsidian"}
files = []
for dp, dns, fns in os.walk(ROOT):
    dns[:] = [d for d in dns if d not in SKIP_DIRS]
    files += [os.path.join(dp, fn) for fn in fns if fn.endswith(".md")]
files.sort()
missing = [e for e in expected if not os.path.exists(os.path.join(ROOT, e))]
if missing:
    print("MISSING:", missing)

def han_count(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return len(re.findall(r"[一-鿿]", text))

def ignored(path):
    """被 .gitignore 忽略的路径不会随课程分发。不在 git 仓库里时不检查。"""
    try:
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, capture_output=True)
    except FileNotFoundError:
        return False
    return r.returncode == 0

def tracked(path):
    """--release 模式：目标必须已被 git 跟踪。目录则要求其中至少有一个被跟踪的文件。"""
    r = subprocess.run(["git", "ls-files", "--", path], cwd=ROOT, capture_output=True, text=True)
    return bool(r.stdout.strip())

def slug(h):
    """GitHub / Obsidian 风格的标题锚点：去掉标点，空格变连字符，英文转小写。"""
    h = re.sub(r"[*`]", "", h.strip()).lower()
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")

_anchors = {}
def anchors(path):
    if path not in _anchors:
        text = re.sub(r"```.*?```", "", open(path, encoding="utf-8").read(), flags=re.S)
        heads = re.findall(r"^#+ (.+?)\s*$", text, flags=re.M)
        seen, out = {}, set()
        for h in heads:
            base = slug(h)
            k = seen.get(base, 0)
            out.add(base if k == 0 else f"{base}-{k}")
            seen[base] = k + 1
            out.add(h.strip())
        _anchors[path] = out
    return _anchors[path]

INTRO = ("00-how-to-learn.md", "01-what-is-strategy-game.md")
problems = 0
for f in files:
    name = os.path.relpath(f, ROOT)
    text = open(f, encoding="utf-8").read()
    issues = []
    n = han_count(text)
    if name in expected:
        idx = expected.index(name)
        if n < 9000 and name not in INTRO:
            issues.append(f"字数偏少 {n}")
        required = ["动手", "检查清单"] if name in INTRO else ["常见误区", "练习题", "动手", "检查清单", "参考答案"]
        for sec in required:
            if not re.search(r"^##+ .*" + sec, text, flags=re.M):
                issues.append(f"缺小节:{sec}")
        paths = len(re.findall(r"^###+ 思考路径", text, flags=re.M))
        if paths < 2 and name not in INTRO[:1]:
            issues.append(f"思考路径仅 {paths} 个")
        if idx > 0 and expected[idx - 1] not in text:
            issues.append("上一章链接错")
        if idx < len(expected) - 1 and expected[idx + 1] not in text:
            issues.append("下一章链接错")
        if "【推导】" not in text and idx >= 2:
            issues.append("无【推导】标注")
        if re.search(r"[A-Za-z0-9一-鿿] — [A-Za-z0-9一-鿿]", text):
            issues.append("疑似英文 em-dash 用法")
        if re.search(r"```(python|py|go|js)", text):
            issues.append("正文出现代码块（本课不写代码）")
    # 相对链接与锚点（跳过外链、绝对路径和代码块）
    base = os.path.dirname(f)
    body = re.sub(r"```.*?```", "", text, flags=re.S)
    for m in re.finditer(r"\]\(([^)\s]*)\)", body):
        link = m.group(1)
        if not link or re.match(r"[a-z]+:", link) or link.startswith("/"):
            continue
        path_part, _, anchor = link.partition("#")
        target = os.path.normpath(os.path.join(base, path_part)) if path_part else f
        if path_part:
            if not os.path.exists(target):
                issues.append(f"断链:{link}")
                continue
            if target.startswith(ROOT):
                if ignored(target):
                    issues.append(f"链接指向被 git 忽略的文件:{link}")
                elif RELEASE and not tracked(target):
                    issues.append(f"链接指向未被 git 跟踪的文件:{link}")
        if anchor and target.endswith(".md"):
            from urllib.parse import unquote
            a = unquote(anchor)
            if a not in anchors(target) and a.lower() not in anchors(target):
                issues.append(f"锚点不存在:{link}")
    print(f"{name:42s} {n:6d} 字  {'OK' if not issues else '; '.join(issues)}")
    problems += len(issues)
print("TOTAL issues:", problems, "(release 模式)" if RELEASE else "")
sys.exit(1 if problems else 0)
