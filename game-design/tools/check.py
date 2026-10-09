#!/usr/bin/env python3
"""课程一致性检查：字数、必备小节、链接目标、上下章链接、可靠性标注。"""
import os, re, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob(os.path.join(ROOT, "*.md")))
chapters = [f for f in files if re.match(r"\d\d-", os.path.basename(f))]
expected = [
 "00-how-to-learn.md","01-what-designers-do.md","02-what-is-a-game.md","03-why-players-play.md",
 "04-mda-and-lenses.md","05-decisions.md","06-systems-and-emergence.md","07-loops.md",
 "08-goals-progression-rewards.md","09-challenge-difficulty-skill.md","10-randomness.md",
 "11-social-design.md","12-narrative.md","13-game-feel-and-feedback.md","14-design-process.md",
 "15-system-design-method.md","16-design-docs.md","17-level-design.md","18-onboarding.md","19-ux.md",
 "20-playtesting-and-validation.md","21-monetization-design.md","22-live-ops-design.md",
 "23-genre-slg.md","24-genre-card-rpg.md","25-genre-openworld-narrative-roguelike.md",
 "26-design-critique.md","27-lead-designer.md","28-pitching-and-greenlight.md","29-end-to-end-lab.md",
]
missing = [e for e in expected if not os.path.exists(os.path.join(ROOT, e))]
if missing:
    print("MISSING:", missing)

def han_count(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return len(re.findall(r"[一-鿿]", text))

problems = 0
for f in files:
    name = os.path.basename(f)
    text = open(f, encoding="utf-8").read()
    issues = []
    if name in expected:
        n = han_count(text)
        if n < 7000 and name not in ("00-how-to-learn.md","01-what-designers-do.md"): issues.append(f"字数偏少 {n}")
        for sec in (["动手", "检查清单"] if name == "00-how-to-learn.md" else ["常见误区", "动手", "检查清单"]):
            if not re.search(r"^##+ .*" + sec, text, flags=re.M):
                issues.append(f"缺小节:{sec}")
        idx = expected.index(name)
        if idx > 0 and expected[idx-1] not in text: issues.append("上一章链接错")
        if idx < len(expected)-1 and expected[idx+1] not in text: issues.append("下一章链接错")
        if "【推导】" not in text and idx >= 2: issues.append("无【推导】标注")
        if "——" in text and re.search(r"[A-Za-z0-9] — [A-Za-z0-9]", text): issues.append("疑似英文 em-dash 用法")
    else:
        n = han_count(text)
    # links
    for m in re.finditer(r"\]\((\.\.?/[^)#]+)(#[^)]*)?\)", text):
        target = os.path.normpath(os.path.join(ROOT, m.group(1)))
        if not os.path.exists(target):
            issues.append(f"断链:{m.group(1)}")
    print(f"{name:45s} {n:6d} 字  {'OK' if not issues else '; '.join(issues)}")
    problems += len(issues)
print("TOTAL issues:", problems)
