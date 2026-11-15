#!/usr/bin/env bash
# One measured run. Usage: run.sh <A|B|C> <run-number>
# Frozen by experiments/harness-ab/procedure.md. Do not change flags after the first run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ARM="${1:-}"
RUN_RAW="${2:-}"
case "$ARM" in
  A|a) ARM=A; FOLDER=A-bare ;;
  B|b) ARM=B; FOLDER=B-agentsmd ;;
  C|c) ARM=C; FOLDER=C-chaosengine ;;
  *) echo "usage: run.sh <A|B|C> <run-number>" >&2; exit 2 ;;
esac
if ! [[ "$RUN_RAW" =~ ^[0-9]+$ ]]; then
  echo "run number must be an integer" >&2
  exit 2
fi
RUN="$(printf '%02d' "$RUN_RAW")"
PROJECT="$ROOT/exp/$FOLDER/run-$RUN"
RAW="$ROOT/raw/$ARM/$RUN"
OUT="$ROOT/outputs"
PIN="$(tr -d '[:space:]' < "$ROOT/harness-pin.txt")"
PROMPT="$ROOT/PROMPT.txt"
CANNED="$(tr -d '\r\n' < "$ROOT/CANNED.txt")"
MODEL="grok-4.7"
MAX_TURNS=40
SESSION_BUDGET=2700
MVN_BUDGET=600
INSTALL_BUDGET=1500
GROK="${GROK_BIN:-grok}"

mkdir -p "$RAW" "$OUT"
rm -rf "$PROJECT"
mkdir -p "$PROJECT"
SOCKET="$RAW/leader.sock"
rm -f "$SOCKET" "$SOCKET.daemon"

python3 - "$RAW/meta.json" "$ARM" "$RUN" "$MODEL" "$PIN" <<'PY'
import json, os, shutil, subprocess, sys
from pathlib import Path
target, arm, run, model, pin = sys.argv[1:]
version = subprocess.check_output(["grok", "--version"], text=True).strip()
meta = {
    "arm": arm,
    "run": run,
    "model_flag": model,
    "grok_version": version,
    "harness_pin": pin,
    "maven_cache": "warm" if Path.home().joinpath(".m2/repository").is_dir() else "cold",
    "hostname": os.uname().nodename,
}
Path(target).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
PY

if [[ "$ARM" == "B" ]]; then
  cp "$ROOT/fixtures/AGENTS.md" "$PROJECT/AGENTS.md"
fi

install_seconds=0
if [[ "$ARM" == "C" ]]; then
  url="https://raw.githubusercontent.com/ShaftHQ/chaosengine-harness/${PIN}/install.sh"
  start=$(date +%s)
  set +e
  (
    cd "$PROJECT"
    timeout --foreground "$INSTALL_BUDGET" bash -c 'curl -fsSL "$1" | bash -s -- "$1" --hosts grok' _ "$url"
  ) >"$RAW/install.log" 2>&1
  install_exit=$?
  set -e
  install_seconds=$(( $(date +%s) - start ))
  if [[ -f "$PROJECT/.chaos-engine-hosts.json" ]]; then
    cp "$PROJECT/.chaos-engine-hosts.json" "$RAW/hosts-receipt.json"
  fi
  if [[ -f "$PROJECT/.chaos-engine/VERSION" ]]; then
    cp "$PROJECT/.chaos-engine/VERSION" "$RAW/installed-version.txt"
  fi
else
  install_exit=0
fi

SESSION="$(python3 -c 'import uuid; print(uuid.uuid4())')"
start=$(date +%s)
deadline=$(( start + SESSION_BUDGET ))
questions=0
grok_exit=0
timed_out=0
turn_file="$RAW/grok-stdout.txt"
err_file="$RAW/grok-stderr.txt"
: >"$turn_file"
: >"$err_file"

run_grok() {
  local prompt_mode="$1"
  local remaining=$(( deadline - $(date +%s) ))
  if (( remaining < 1 )); then
    timed_out=1
    grok_exit=124
    return
  fi
  set +e
  if [[ "$prompt_mode" == "file" ]]; then
    timeout --foreground "$remaining" "$GROK" \
      --cwd "$PROJECT" \
      --leader-socket "$SOCKET" \
      --session-id "$SESSION" \
      --model "$MODEL" \
      --permission-mode bypassPermissions \
      --max-turns "$MAX_TURNS" \
      --output-format json \
      --verbatim \
      --prompt-file "$PROMPT" \
      >>"$turn_file" 2>>"$err_file"
  else
    timeout --foreground "$remaining" "$GROK" \
      --cwd "$PROJECT" \
      --leader-socket "$SOCKET" \
      -r "$SESSION" \
      --model "$MODEL" \
      --permission-mode bypassPermissions \
      --max-turns "$MAX_TURNS" \
      --output-format json \
      --verbatim \
      -p "$CANNED" \
      >>"$turn_file" 2>>"$err_file"
  fi
  grok_exit=$?
  set -e
  if [[ "$grok_exit" -eq 124 ]]; then
    timed_out=1
  fi
}

run_grok file
while [[ "$timed_out" -eq 0 && "$questions" -lt 3 ]]; do
  ask="$(python3 - "$turn_file" "$PROJECT" <<'PY'
import json, sys
from pathlib import Path
stdout, project = sys.argv[1:]
text = Path(stdout).read_text(encoding="utf-8", errors="replace")
decoder = json.JSONDecoder()
last = None
for index, char in enumerate(text):
    if char != "{":
        continue
    try:
        obj, _ = decoder.raw_decode(text[index:])
    except json.JSONDecodeError:
        continue
    if isinstance(obj, dict):
        last = obj
body = str((last or {}).get("text") or "").strip()
has_pom = any(Path(project).rglob("pom.xml"))
print("1" if (not has_pom and body.endswith("?")) else "0")
PY
)"
  if [[ "$ask" != "1" ]]; then
    break
  fi
  questions=$(( questions + 1 ))
  printf '\n%s\n' "$CANNED" >>"$RAW/questions.log"
  run_grok resume
done

session_seconds=$(( $(date +%s) - start ))
if [[ "$timed_out" -eq 1 ]]; then
  session_seconds=$SESSION_BUDGET
fi

"$GROK" export "$SESSION" --leader-socket "$SOCKET" >"$RAW/transcript.md" 2>>"$err_file" || true

python3 - "$RAW" "$turn_file" "$grok_exit" "$timed_out" "$session_seconds" "$install_exit" "$install_seconds" "$questions" "$SESSION" <<'PY'
import json, re, sys
from pathlib import Path
raw, stdout, grok_exit, timed_out, seconds, install_exit, install_seconds, questions, session = sys.argv[1:]
meta_path = Path(raw) / "meta.json"
meta = json.loads(meta_path.read_text(encoding="utf-8"))
text = Path(stdout).read_text(encoding="utf-8", errors="replace")
decoder = json.JSONDecoder()
last = None
for index, char in enumerate(text):
    if char != "{":
        continue
    try:
        obj, _ = decoder.raw_decode(text[index:])
    except json.JSONDecodeError:
        continue
    if isinstance(obj, dict) and ("usage" in obj or "text" in obj):
        last = obj
usage = (last or {}).get("usage") if isinstance(last, dict) else None
meta.update({
    "grok_exit": int(grok_exit),
    "timed_out": bool(int(timed_out)),
    "session_seconds": int(seconds),
    "install_exit": int(install_exit),
    "install_seconds": int(install_seconds),
    "questions": int(questions),
    "session_id": session,
    "usage": usage or {},
    "meter_cost_usd": (usage or {}).get("total_cost_usd"),
    "num_turns": (last or {}).get("num_turns") if isinstance(last, dict) else None,
    "stop_reason": (last or {}).get("stopReason") if isinstance(last, dict) else None,
    "model": next(iter((last or {}).get("modelUsage") or {}), None) if isinstance(last, dict) else None,
})
transcript = Path(raw) / "transcript.md"
if transcript.is_file():
    body = transcript.read_text(encoding="utf-8", errors="replace")
    meta["tool_calls"] = len(re.findall(r"^### Tool\b", body, re.M)) or body.count("tool_use") or body.count('"name":')
meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
PY

if [[ "$timed_out" -eq 0 ]]; then
  pom="$(find "$PROJECT" -name pom.xml -not -path '*/target/*' -not -path '*/.chaos-engine/*' | awk -F/ '{ print NF, $0 }' | sort -n | head -1 | cut -d' ' -f2-)"
  if [[ -n "$pom" ]]; then
    pom_dir="$(dirname "$pom")"
    for n in 1 2 3; do
      set +e
      timeout --foreground "$MVN_BUDGET" mvn -q test -f "$pom" >"$RAW/mvn-$n.log" 2>&1
      mvn_exit=$?
      set -e
      printf '%s\n' "$mvn_exit" >"$RAW/mvn-$n.exit"
      if [[ -d "$pom_dir/target/surefire-reports" ]]; then
        rm -rf "$RAW/surefire-$n"
        cp -a "$pom_dir/target/surefire-reports" "$RAW/surefire-$n"
      fi
    done
  else
    printf 'no pom.xml\n' >"$RAW/mvn-1.log"
    printf '1\n' >"$RAW/mvn-1.exit"
  fi
fi

mkdir -p "$OUT"
tar -C "$PROJECT" \
  --exclude target \
  --exclude .git \
  --exclude .chaos-engine \
  --exclude '*.sock' \
  -czf "$OUT/${ARM}-${RUN}.tar.gz" .
echo "recorded $ARM $RUN exit=$grok_exit timed_out=$timed_out questions=$questions"
