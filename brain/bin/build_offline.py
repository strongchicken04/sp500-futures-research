"""Build brain/jarvis_offline.html: the Jarvis page with a snapshot of the core
database embedded, so it works when opened as a plain file (no live db).

The snapshot comes from brain/snapshot/<collection>/<doc>.json, written by the
ArtifactData tool ('list' with out_dir=brain/snapshot) for the collections
brain, strategies, queue, indicators and reports.

Usage: python3 brain/bin/build_offline.py
"""
import datetime as dt
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
snap = {"taken": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "brain": {}}
for col_dir in sorted((ROOT / "snapshot").iterdir()):
    if not col_dir.is_dir():
        continue
    docs = {f.stem: json.loads(f.read_text()) for f in sorted(col_dir.glob("*.json"))}
    if col_dir.name == "brain":
        snap["brain"] = docs
    else:
        snap[col_dir.name] = [dict(v, _id=k) for k, v in docs.items()]
page = (ROOT / "jarvis.html").read_text()
data = json.dumps(snap, ensure_ascii=False).replace("</", "<\\/")
marker = "<script>\n(() => {"
assert marker in page
out = page.replace(marker, f"<script>window.JARVIS_SNAPSHOT = {data};</script>\n{marker}", 1)
head = '<!doctype html>\n<html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body style="margin:0">\n'
(ROOT / "jarvis_offline.html").write_text(head + out + "\n</body></html>\n")
print("wrote", ROOT / "jarvis_offline.html", {k: len(v) for k, v in snap.items() if isinstance(v, (list, dict))})
