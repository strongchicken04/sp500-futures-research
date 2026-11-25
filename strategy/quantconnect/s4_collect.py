#!/usr/bin/env python3
"""Collect one Stage 4 QC backtest (runtime statistics + logs, aggregates only) with a validation verdict.
Usage: s4_collect.py MODE LABEL (LOG_FILE | PROJECT_ID BACKTEST_ID)"""
import json, re, sys, time
sys.path.insert(0, "strategy/quantconnect")
from deploy_long import call
mode, label = sys.argv[1], sys.argv[2]
if len(sys.argv) == 4:
    log = open(sys.argv[3]).read()
    pid = int(re.findall(r"project (\d+)", log)[-1]); bid = re.findall(r"backtest\] id (\w+)", log)[-1]
    bt = json.load(open("qc_result_MSXB_1792352605.json"))
    bt = bt.get("backtest", bt)
else:
    pid, bid = int(sys.argv[3]), sys.argv[4]
    while True:
        bt = call("backtests/read", {"projectId": pid, "backtestId": bid}).get("backtest", {})
        if bt.get("completed"):
            break
        time.sleep(60)
rs = bt.get("runtimeStatistics") or {}
p0 = rs.get("P0 panel", ""); chk = rs.get("S4 CHECK", "")
why = []
if f"mode {mode} " not in p0 + " ":
    why.append("mode line missing or wrong (template / incomplete script?)")
if not chk.startswith("OK"):
    why.append("S4 CHECK not OK")
if str(bt.get("error")) not in ("None", ""):
    why.append("backtest error")
if any(k.startswith("ERR") for k in rs):
    why.append("ERR statistic present")
print(f"### xup s4 {mode} {label} | project {pid} backtest {bid} | {'VALID' if not why else 'INVALID: ' + '; '.join(why)}")
for k in sorted(rs):
    if k.split(" ")[0] in ("Equity", "Fees", "Holdings", "Net", "Probabilistic", "Return", "Unrealized", "Volume"):
        continue
    print(k, "=", rs[k])
print("err", str(bt.get("error"))[:300])
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