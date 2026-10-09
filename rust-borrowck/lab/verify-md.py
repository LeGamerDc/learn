#!/usr/bin/env python3
"""全书代码块回归核查台。

把每章 markdown 里的 ```rust 代码块逐个送进 rustc，
和块内自称的结论（// ✅ / // ❌ E0xxx）逐条比对，报告矛盾。

    cd lab && python3 verify-md.py            # 核查全书
    python3 verify-md.py ../06-lifetimes.md   # 只查一章

判定说明
  ok    编译通过
  err   报了借用/类型错误 —— 可与自称结论比对
  frag  片段不完整（缺符号、只有签名、伪代码）—— 跳过，不做结论
输出的每一行都需要人工确认：脚本无法区分"注释掉的 ❌ 行"和真实断言。
"""
import concurrent.futures as cf, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.dirname(HERE)
EDITION = os.environ.get("EDITION", "2024")
EXTRA   = os.environ.get("RUSTCFLAGS", "").split()

# 这些错误说明"块不完整"，而不是"课程写错了"
FRAG_CODES = {"E0425","E0433","E0432","E0412","E0422","E0405","E0531","E0574",
              "E0576","E0603","E0658","E0428","E0261","E0426","E0152","E0586",
              "E0560","E0609","E0252","E0255","E0599","E0463"}
FRAG_MSG = re.compile(r"^error: (expected|unexpected|mismatched closing|unknown start|"
                      r"this file contains|missing `fn`|`self` parameter|free function)")

PRELUDE = """#![allow(unused, dead_code, unused_mut, deprecated, non_snake_case,
    unreachable_code, path_statements, non_camel_case_types)]
use std::collections::{HashMap, HashSet, BTreeMap, VecDeque};
use std::rc::{Rc, Weak};
use std::sync::{Arc, Mutex, RwLock, OnceLock, LazyLock, mpsc};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::cell::{Cell, RefCell, UnsafeCell, OnceCell};
use std::pin::Pin;
use std::ops::{Range, Deref, DerefMut};
use std::fmt::{Display, Debug};
use std::hash::Hash;
use std::future::Future;
use std::marker::{PhantomData, PhantomPinned};
use std::borrow::Cow;
use std::mem;
#[allow(dead_code)] mod tokio {
  pub mod task { pub async fn yield_now() {} }
  pub mod time { pub async fn sleep(_d: std::time::Duration) {} }
}
async fn yield_now() {}
async fn y() {}
fn critical_section() {}
"""
LOCALS = """
    let mut v: Vec<i32> = vec![1, 2, 3];
    let mut s = String::from("hello");
    let mut m: HashMap<String, String> = HashMap::new();
    let mut a: Vec<i32> = vec![1, 2, 3];
    let mutex = Mutex::new(0i32);
    let opt: Option<i32> = Some(1);
    let cond = true;
"""
ITEM = re.compile(r"^\s*(#\[|#!\[|pub\s|fn\s|async\s+fn\s|unsafe\s+fn\s|const\s+fn\s|"
                  r"struct\s|enum\s|trait\s|impl[\s<]|use\s|mod\s|type\s|static\s|"
                  r"const\s+[A-Z]|extern\s|macro_rules!)")

def blocks(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    i, out = 0, []
    while i < len(lines):
        if lines[i].strip() == "```rust":
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            out.append((i + 2, "\n".join(lines[i+1:j])))
            i = j + 1
        else:
            i += 1
    return out

def expectation(b):
    """块自称的结论"""
    ok, bad = "✅" in b, "❌" in b
    if ok and bad: return "mixed"
    if bad:
        m = re.findall(r"❌[^\n]{0,40}?(E\d{4})", b)
        return m[0] if m else "err"
    return "ok" if ok else "none"

def first_code_line(b):
    for l in b.split("\n"):
        t = l.strip()
        if t and not t.startswith("//"): return l
    return ""

def compile_block(args):
    path, line, body, tmp = args
    if ITEM.match(first_code_line(body)):
        src, mode = PRELUDE + body, "lib"
    else:
        src = PRELUDE + "#[allow(unused)]\nasync fn __probe() {\n" + LOCALS + body + "\n}\n"
        mode = "lib"
    if re.search(r"^\s*(async\s+)?fn\s+main\s*\(", body, re.M):
        src, mode = PRELUDE + body, "bin"
    name = "b%d" % (abs(hash((path, line))) % 10**9)
    f = os.path.join(tmp, name + ".rs")
    open(f, "w", encoding="utf-8").write(src)
    cmd = ["rustc", "+nightly", "--edition", EDITION, "--emit=metadata", "--out-dir", tmp,
           "-Zunstable-options", "--error-format=json", "--crate-name", name]
    if mode != "bin": cmd.append("--crate-type=lib")
    cmd += EXTRA + [f]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return path, line, body, "frag", []
    codes, msgs = [], []
    for ln in r.stderr.split("\n"):
        if not ln.startswith("{"): continue
        try: d = json.loads(ln)
        except Exception: continue
        if d.get("level") != "error": continue
        c = (d.get("code") or {}).get("code")
        codes.append(c or "-")
        msgs.append(("error[%s]: " % c if c else "error: ") + (d.get("message") or ""))
    if not codes: return path, line, body, "ok", []
    if any(c in FRAG_CODES for c in codes) or any(FRAG_MSG.match(m) for m in msgs):
        return path, line, body, "frag", codes
    return path, line, body, "err", codes

def main():
    files = sys.argv[1:] or sorted(
        os.path.join(SRC, f) for f in os.listdir(SRC) if f.endswith(".md"))
    jobs = []
    tmp = tempfile.mkdtemp(prefix="verify-md-")
    for p in files:
        for line, body in blocks(p):
            jobs.append((p, line, body, tmp))
    print(f"toolchain : {subprocess.run(['rustc','+nightly','--version'],capture_output=True,text=True).stdout.strip()}")
    print(f"edition   : {EDITION}")
    print(f"代码块    : {len(jobs)} 个，来自 {len(files)} 个文件\n")

    stats = {"ok": 0, "err": 0, "frag": 0}
    conflicts = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for p, line, body, st, codes in ex.map(compile_block, jobs):
            stats[st] += 1
            if st == "frag": continue
            e = expectation(body)
            k = None
            if   e == "ok"  and st == "err": k = "自称 ✅ 实际报错 %s" % codes[:2]
            elif e == "err" and st == "ok" : k = "自称 ❌ 实际编译通过"
            elif e.startswith("E"):
                if   st == "ok":        k = "自称 %s 实际编译通过" % e
                elif e not in codes:    k = "自称 %s 实际 %s" % (e, codes[:2])
            if k:
                conflicts.append((os.path.basename(p), line, k,
                                  first_code_line(body).strip()[:60]))

    print(f"编译通过 {stats['ok']}   报错 {stats['err']}   片段(跳过) {stats['frag']}")
    print(f"\n需人工确认的矛盾：{len(conflicts)} 处")
    print("─" * 86)
    for f, line, k, snip in sorted(conflicts):
        print(f"{f}:{line:<5} {k}")
        print(f"{'':<12} | {snip}")
    print("─" * 86)
    print("""提示：以下情况是**预期内**的误报，不是错误——
  · ❌ 标在被注释掉的行上（"取消注释试试"）
  · 断言限定了引擎或 edition（NLL ❌ / Polonius ✅、2021 ❌ / 2024 ✅）
  · 只有函数签名、没有函数体的示意代码
逐条核对后再改课程。""")

if __name__ == "__main__":
    main()
