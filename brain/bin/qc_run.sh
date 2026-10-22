#!/usr/bin/env bash
# Run QuantConnect backtests one after another in one reused project ("slot";
# QC allows 50 new projects a day), fetch each run's order tags and store them
# gzipped in data/tags/NAME_tags.txt.gz (and unpacked in $BRAIN_DATA).
# Credentials: env QC_USER_ID / QC_API_TOKEN, else ~/.lean/credentials.
# Never print or commit them.
# Usage: brain/bin/qc_run.sh NAME:path/to/algo.py [NAME:path ...]
cd "$(dirname "$0")/../.." || exit 1
D="${BRAIN_DATA:-/tmp/brain_data}"; mkdir -p "$D"
SLOT="${QC_SLOT:-MSXB_1792352605}"
if [ -z "${QC_USER_ID:-}" ] || [ -z "${QC_API_TOKEN:-}" ]; then
  export QC_USER_ID=$(python3 -c "import json,pathlib;print(json.loads((pathlib.Path.home()/'.lean'/'credentials').read_text())['user-id'])" 2>/dev/null)
  export QC_API_TOKEN=$(python3 -c "import json,pathlib;print(json.loads((pathlib.Path.home()/'.lean'/'credentials').read_text())['api-token'])" 2>/dev/null)
fi
[ -n "$QC_USER_ID" ] && [ -n "$QC_API_TOKEN" ] || { echo "NO QC CREDENTIALS"; exit 2; }
for spec in "$@"; do
  nm="${spec%%:*}"; f="${spec##*:}"
  echo "######## $nm <- $f (slot $SLOT)"
  ok=0
  for attempt in $(seq 1 150); do
    out=$(timeout 2400 python3 strategy/quantconnect/deploy_and_backtest.py "$SLOT" "$f" 2>&1)
    if echo "$out" | grep -q "no spare nodes"; then sleep 40; continue; fi
    echo "$out" | grep -E "BuildError|completed|ERROR|FAILED|failed" | head -5
    echo "$out" | grep -q "\[backtest\] completed" && ok=1
    break
  done
  res="qc_result_${SLOT}.json"
  if [ "$ok" = 1 ] && [ -f "$res" ]; then
    cp "$res" "qc_result_${nm}.json"
    git checkout -- "$res" 2>/dev/null
    pid=$(python3 -c "import json;print(json.load(open('qc_result_${nm}.json'))['projectId'])")
    bid=$(python3 -c "import json;print(json.load(open('qc_result_${nm}.json'))['backtestId'])")
    timeout 1800 python3 brain/bin/fetch_tags.py "$pid" "$bid" "$D/${nm}_tags.txt" 2>&1 | tail -1
    [ -s "$D/${nm}_tags.txt" ] && gzip -9 -c "$D/${nm}_tags.txt" > "data/tags/${nm}_tags.txt.gz"
  else
    echo "no result for $nm"
  fi
done
echo "QUEUE DONE"
