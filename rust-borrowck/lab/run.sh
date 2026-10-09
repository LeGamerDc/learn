#!/usr/bin/env bash
# 对 cases/ 下的每个例子，分别用 NLL(-Zpolonius=off) 和 Polonius Alpha(默认) 编译，
# 输出一张三态对照表。需要 2026-08-04 之后的 nightly。
set -u
EDITION="${EDITION:-2024}"
OUT="$(dirname "$0")/out"; mkdir -p "$OUT"
CASES="$(dirname "$0")/cases"

command -v rustc >/dev/null || { echo "找不到 rustc"; exit 1; }
NV=$(rustc +nightly --version 2>/dev/null) || { echo "需要 nightly：rustup toolchain install nightly"; exit 1; }
echo "toolchain : $NV"
echo "edition   : $EDITION"
echo "polonius  : 默认开启（2026-08-04 起）；用 -Zpolonius=off 回退到 NLL"
echo

compile() { # $1=file $2=extra flags -> 打印错误标签(E编号 或 "error")，无错误则空
  local o
  o=$(rustc +nightly --edition "$EDITION" --crate-type=lib --emit=metadata \
        --out-dir "$OUT" $2 "$1" 2>&1)
  local code
  code=$(echo "$o" | grep -o '^error\[E[0-9]*\]' | head -1)
  if [ -n "$code" ]; then echo "${code#error}"
  elif echo "$o" | grep -q '^error'; then echo "[no-code]"
  fi
}

printf "%-34s %-14s %-14s %s\n" "案例" "NLL" "Polonius Alpha" "结论"
printf '%.0s─' {1..92}; echo
diff_count=0; same_fail=0; pass=0
for f in "$CASES"/*.rs; do
  base=$(basename "$f")
  e_nll=$(compile "$f" "-Zpolonius=off")
  e_pol=$(compile "$f" "")
  s_nll=${e_nll:-✅}; s_pol=${e_pol:-✅}
  if [ -z "$e_nll" ] && [ -z "$e_pol" ]; then verdict="两者都接受"; pass=$((pass+1))
  elif [ -n "$e_nll" ] && [ -z "$e_pol" ]; then verdict="★ Polonius 新增接受"; diff_count=$((diff_count+1))
  elif [ -z "$e_nll" ] && [ -n "$e_pol" ]; then verdict="⚠ Polonius 回归（请上报）"
  else verdict="两者都拒绝"; same_fail=$((same_fail+1)); fi
  printf "%-34s %-14s %-14s %s\n" "$base" "$s_nll" "$s_pol" "$verdict"
done
printf '%.0s─' {1..92}; echo
echo "两者都接受: $pass   ★Polonius 新增: $diff_count   两者都拒绝: $same_fail"
