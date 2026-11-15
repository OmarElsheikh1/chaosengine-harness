#!/usr/bin/env bash
# Interleaved campaign: A1 B1 C1 ... A5 B5 C5. A recorded timeout is not a crash.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
for run in 1 2 3 4 5; do
  for arm in A B C; do
    echo "START $arm $run"
    if ! "$ROOT/run.sh" "$arm" "$run"; then
      echo "ACTION_REQUIRED: run.sh crashed on $arm $run" >&2
      exit 1
    fi
    echo "DONE_RUN $arm $run"
  done
done
echo "DONE: campaign complete"
