#!/usr/bin/env python3
"""Add / update an extra file (e.g. an imported data module) in a QC cloud project. Usage:
   upload_project_file.py <project name> <local file> [<name in project>]"""
import sys, os, pathlib
sys.path.insert(0, os.path.dirname(__file__))
from deploy_long import call  # noqa: E402

name, path = sys.argv[1], sys.argv[2]
fname = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(path)
pid = next((p["projectId"] for p in call("projects/read", {}).get("projects", []) if p["name"] == name), None)
if pid is None:
    print("project not found"); sys.exit(1)
content = pathlib.Path(path).read_text()
u = call("files/update", {"projectId": pid, "name": fname, "content": content})
if not u.get("success"):
    u = call("files/create", {"projectId": pid, "name": fname, "content": content})
print(fname, "uploaded:", u.get("success"), str(u.get("errors", ""))[:200])
