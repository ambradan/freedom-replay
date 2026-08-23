#!/usr/bin/env python3
"""One-time freeze. Refuses to run if FREEZE.sha256 already exists.
Requires every frozen file present locally, including materials/worksheet.jsonl
(hash-committed here but gitignored: the manifest publishes the hash, never
the content). After this: python3 verify.py, then commit and push."""
import hashlib, pathlib, sys
FROZEN = [
    "protocol/protocollo-planted-record-v1.md",
    "materials/fabrications.json",
    "materials/worksheet.jsonl",
    "analysis/proxy.py",
    "results/results_skeleton.md",
]
m = pathlib.Path("FREEZE.sha256")
if m.exists():
    sys.exit("FREEZE.sha256 exists: the freeze is a one-time act. Deviations go in the protocol's deviations section.")
lines = ["# planted-record protocol v1.0 freeze"]
for p in FROZEN:
    f = pathlib.Path(p)
    if not f.exists():
        sys.exit(f"missing: {p}  (the freeze needs every file, worksheet included)")
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    lines.append(f"{h}  {p}")
    print(f"{h}  {p}")
m.write_text("\n".join(lines) + "\n")
print("FREEZE.sha256 written. Now: python3 verify.py && git add -A && git commit && git push")
