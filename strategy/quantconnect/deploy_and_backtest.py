#!/usr/bin/env python3
"""Deploy an algorithm to QuantConnect cloud and run a backtest via the REST API.

Reads credentials from ~/.lean/credentials (created by `lean login`) or env
QC_USER_ID / QC_API_TOKEN. No secrets are hard-coded.
"""
import base64, hashlib, json, os, sys, time, urllib.request, urllib.error, pathlib

BASE = "https://www.quantconnect.com/api/v2"


def creds():
    uid = os.environ.get("QC_USER_ID")
    tok = os.environ.get("QC_API_TOKEN")
    if not (uid and tok):
        p = pathlib.Path.home() / ".lean" / "credentials"
        d = json.loads(p.read_text())
        uid = str(d["user-id"]); tok = d["api-token"]
    return str(uid), tok


UID, TOK = creds()


def call(endpoint, payload=None, method="POST"):
    ts = str(int(time.time()))
    h = hashlib.sha256(f"{TOK}:{ts}".encode()).hexdigest()
    auth = base64.b64encode(f"{UID}:{h}".encode()).decode()
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{BASE}/{endpoint}", data=data, method=method)
    req.add_header("Authorization", "Basic " + auth)
    req.add_header("Timestamp", ts)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"success": False, "http_error": e.code, "body": e.read().decode()[:500]}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "NQ_ORB_5min"
    main_py = sys.argv[2] if len(sys.argv) > 2 else "strategy/quantconnect/main.py"
    content = pathlib.Path(main_py).read_text()

    # 1. create project (or reuse if it already exists)
    r = call("projects/create", {"name": name, "language": "Py"})
    if r.get("success") and r.get("projects"):
        pid = r["projects"][0]["projectId"]
        print(f"[create] project {pid}")
    else:
        # find existing
        lp = call("projects/read", {})
        pid = None
        for p in lp.get("projects", []):
            if p["name"] == name:
                pid = p["projectId"]; break
        if pid is None:
            print("FAILED to create/find project:", json.dumps(r)[:400]); sys.exit(1)
        print(f"[reuse] project {pid}")

    # 2. upload main.py (update if present, else create)
    u = call("files/update", {"projectId": pid, "name": "main.py", "content": content})
    if not u.get("success"):
        c = call("files/create", {"projectId": pid, "name": "main.py", "content": content})
        print("[file create]", c.get("success"), json.dumps(c)[:200])
    else:
        print("[file update] ok")

    # 3. compile
    comp = call("compile/create", {"projectId": pid})
    cid = comp.get("compileId")
    print("[compile] id", cid, "state", comp.get("state"))
    if not cid:
        print("compile create failed:", json.dumps(comp)[:400]); sys.exit(1)
    for _ in range(40):
        cr = call("compile/read", {"projectId": pid, "compileId": cid})
        st = cr.get("state")
        if st == "BuildSuccess":
            print("[compile] BuildSuccess"); break
        if st == "BuildError":
            print("[compile] BuildError:", json.dumps(cr.get("logs", ""))[:1000]); sys.exit(1)
        time.sleep(3)
    else:
        print("compile timed out"); sys.exit(1)

    # 4. backtest
    bt_name = f"{name}_{int(time.time())}"
    b = call("backtests/create",
             {"projectId": pid, "compileId": cid, "backtestName": bt_name})
    bid = b.get("backtestId") or (b.get("backtest") or {}).get("backtestId")
    print("[backtest] id", bid)
    if not bid:
        print("backtest create failed:", json.dumps(b)[:500]); sys.exit(1)

    # 5. poll
    last = 0.0
    for i in range(400):
        br = call("backtests/read", {"projectId": pid, "backtestId": bid})
        bt = br.get("backtest", br)
        completed = bt.get("completed")
        progress = bt.get("progress", 0)
        err = bt.get("error") or bt.get("stacktrace")
        if progress != last:
            print(f"  progress {progress:.2%}"); last = progress
        if completed:
            print("[backtest] completed")
            out = {"projectId": pid, "backtestId": bid, "name": bt_name,
                   "statistics": bt.get("statistics"),
                   "runtimeStatistics": bt.get("runtimeStatistics"),
                   "totalPerformance": bt.get("totalPerformance"),
                   "error": err}
            pathlib.Path(f"qc_result_{name}.json").write_text(json.dumps(out, indent=2, default=str))
            print(f"\nSaved qc_result_{name}.json")
            # print key stats
            stats = bt.get("statistics") or {}
            for k in ["Total Trades", "Net Profit", "Compounding Annual Return",
                      "Sharpe Ratio", "Drawdown", "Win Rate", "Loss Rate",
                      "Average Win", "Average Loss", "Profit-Loss Ratio",
                      "Total Fees"]:
                if k in stats:
                    print(f"  {k}: {stats[k]}")
            if err:
                print("  ERROR:", str(err)[:500])
            return
        if err and progress == 0 and i > 3:
            print("[backtest] error:", str(err)[:800]);
        time.sleep(5)
    print("backtest poll timed out")


if __name__ == "__main__":
    main()
