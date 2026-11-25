#!/bin/bash
# Run one Stage 3 mode of xup_s3_panel_inqc.py in QC and append runtime statistics + log lines (aggregates only)
# to results/xup_s3_<mode>_raw.txt.  Usage: run_s3.sh MODE [label]
MODE=$1; LABEL=${2:-v1}
cd "$(dirname "$0")/../.."
SRC=strategy/quantconnect/inqc/xup_s3_panel_inqc.py
TMP=$(mktemp -d)/main_s3.py
sed "s/^MODE = \"AUDIT\"/MODE = \"$MODE\"/" $SRC > $TMP
X=$(ls strategy/quantconnect/inqc/xup_ic_*.py | tr '\n' ',' | sed 's/,$//')
OUT=results/xup_s3_$(echo $MODE | tr A-Z a-z)_raw.txt
LOG=/tmp/s3_${MODE}_log.txt
for i in $(seq 1 90); do
  QC_EXTRA_FILES=$X python3 strategy/quantconnect/deploy_long.py MSXB_1792352605 $TMP > $LOG 2>&1
  if grep -qi "no spare nodes" $LOG; then sleep 60; continue; fi
  break
done
echo "### xup s3 $MODE $LABEL" >> $OUT
python3 - "$LOG" >> $OUT <<'PY'
import json, re, sys
sys.path.insert(0, "strategy/quantconnect")
from deploy_long import call
d = json.load(open("qc_result_MSXB_1792352605.json"))
bt = d.get("backtest", d)
rs = bt.get("runtimeStatistics") or {}
for k in sorted(rs):
    if k.split(" ")[0] in ("Equity", "Fees", "Holdings", "Net", "Probabilistic", "Return", "Unrealized", "Volume"):
        continue
    print(k, "=", rs[k])
print("err", str(bt.get("error"))[:300])
log = open(sys.argv[1]).read()
pid = int(re.findall(r"project (\d+)", log)[-1]); bid = re.findall(r"backtest\] id (\w+)", log)[-1]
lines = []
for s0 in range(0, 2000, 200):
    r = call("backtests/read/log", {"projectId": pid, "backtestId": bid, "start": s0, "end": s0 + 200, "format": "json", "query": " "})
    L = r.get("logs", [])
    lines += L
    if len(L) < 200:
        break
print("--- LOG ---")
for l in lines:
    l = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", l)
    if l.startswith(("Launching", "Warning", "Request for future")):
        continue
    print(l)
PY
git checkout -- qc_result_MSXB_1792352605.json 2>/dev/null
tail -3 $LOG
