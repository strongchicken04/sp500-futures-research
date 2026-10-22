#!/usr/bin/env python3
"""Fetch order tags from a QC backtest via REST API."""
import base64, hashlib, json, os, sys, time, urllib.request, urllib.error, pathlib

BASE = "https://www.quantconnect.com/api/v2"
UID = os.environ["QC_USER_ID"]
TOK = os.environ["QC_API_TOKEN"]


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
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"success": False, "http_error": e.code, "body": e.read().decode()[:500]}


def main():
    pid = int(sys.argv[1])
    bid = sys.argv[2]
    out_path = sys.argv[3]
    tags = []
    PAGE = 100  # QC pages orders in small batches
    start = 0
    total = None
    while True:
        r = call("backtests/orders/read", {"projectId": pid, "backtestId": bid, "start": start, "end": start + PAGE})
        if total is None:
            total = r.get("length", 0)
            print(f"  total orders: {total}")
        orders = r.get("orders", [])
        if not orders:
            print(f"  empty batch at start={start}, stopping")
            break
        for o in orders:
            tag = o.get("tag") or ""
            if tag:
                tags.append(tag)
        if start % 2000 == 0:
            print(f"  fetched {len(tags)} tags so far (start={start})")
        if start + len(orders) >= total:
            break
        start += PAGE
    pathlib.Path(out_path).write_text("\n".join(tags) + "\n")
    print(f"saved {len(tags)} tags -> {out_path}")


if __name__ == "__main__":
    main()
