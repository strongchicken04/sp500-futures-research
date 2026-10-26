#!/usr/bin/env python3
"""Re-read the runtime statistics of finished QC backtests (they are sometimes
still empty when deploy_and_backtest sees 'completed'). Credentials from the
environment / ~/.lean/credentials, never printed.
Usage: refetch_stats.py PROJECT_NAME BACKTEST_ID [BACKTEST_ID ...]"""
import json, pathlib, sys, os
sys.path.insert(0, "brain/bin")
if not os.environ.get("QC_USER_ID"):
    c = json.loads((pathlib.Path.home() / ".lean" / "credentials").read_text())
    os.environ["QC_USER_ID"], os.environ["QC_API_TOKEN"] = str(c["user-id"]), c["api-token"]
from fetch_tags import call  # noqa: E402

name = sys.argv[1]
pid = next(p["projectId"] for p in call("projects/read", {}).get("projects", []) if p["name"] == name)
for bid in sys.argv[2:]:
    bt = call("backtests/read", {"projectId": pid, "backtestId": bid}).get("backtest", {})
    rs = bt.get("runtimeStatistics") or {}
    print(f"### refetch {bid}")
    for k, v in sorted(rs.items()):
        if k[:2] in ("20", "F2"):
            print(k, "=", v)
