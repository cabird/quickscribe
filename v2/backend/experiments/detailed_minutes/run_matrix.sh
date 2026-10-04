#!/bin/bash
# Chunking experiment (prompt v1) and compression experiment (prompt v2).
# Each line: minutes.py args. Runs two pipelines at a time, each followed by evaluate.py.
set -u
cd "$(dirname "$0")"
pipeline() {
  while read -r args; do
    [ -z "$args" ] && continue
    run=$(uv run -q minutes.py --all $args 2>&1 | tee -a runs/matrix.log | sed -n 's/^Output: //p')
    echo "== minutes done: $args -> $run" | tee -a runs/matrix.log
    uv run -q evaluate.py "$run" >> runs/matrix.log 2>&1 && echo "== eval done: $run" | tee -a runs/matrix.log \
      || echo "== eval FAILED: $run" | tee -a runs/matrix.log
  done
}
mkdir -p runs
printf '%s\n' "--chunk-minutes 5" "--chunk-minutes 15" "--chunk-tokens 1000" "--chunk-tokens 3000" | pipeline &
printf '%s\n' "--chunk-tokens 2000" \
  "--chunk-tokens 2000 --prompt chunk_v2 --rollup-prompt rollup_v2" \
  "--chunk-tokens 2000 --prompt chunk_v2 --rollup-prompt rollup_v2 --target-ratio 0.35" | pipeline &
wait
echo "== ALL DONE" | tee -a runs/matrix.log
