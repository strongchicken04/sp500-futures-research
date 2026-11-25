#!/usr/bin/env python3
"""Upload (IMPORT) the instrument-classification file into the QuantConnect Object Store of the account's
organisation. Data flows only INTO QC. Credentials come from env / ~/.lean/credentials (never printed)."""
import sys, json, time, uuid, urllib.request, urllib.error, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "strategy", "quantconnect"))
from deploy_long import call, UID, TOK, BASE  # noqa: E402
import hashlib, base64


def auth_headers():
    ts = str(int(time.time()))
    h = hashlib.sha256(f"{TOK}:{ts}".encode()).hexdigest()
    return {"Authorization": "Basic " + base64.b64encode(f"{UID}:{h}".encode()).decode(), "Timestamp": ts}


def main():
    path, key = sys.argv[1], sys.argv[2]
    acc = call("account/read", {})
    org = acc.get("organizationId")
    if not org:
        print("no organizationId:", {k: v for k, v in acc.items() if k != "card"}); sys.exit(1)
    data = open(path, "rb").read()
    bnd = uuid.uuid4().hex
    body = b""
    for name, val in (("organizationId", org), ("key", key)):
        body += f"--{bnd}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode()
    body += f"--{bnd}\r\nContent-Disposition: form-data; name=\"objectData\"; filename=\"{os.path.basename(path)}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + data + f"\r\n--{bnd}--\r\n".encode()
    req = urllib.request.Request(f"{BASE}/object/set", data=body, method="POST")
    for k, v in auth_headers().items():
        req.add_header(k, v)
    req.add_header("Content-Type", f"multipart/form-data; boundary={bnd}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            print(r.read().decode()[:300])
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:300])
    r = call("object/properties", {"organizationId": org, "key": key})
    print("properties:", json.dumps(r)[:300])


if __name__ == "__main__":
    main()
