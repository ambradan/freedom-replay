#!/usr/bin/env python3
"""Stampa i testi che vanno letti a occhio prima del report:
(1) contesto storico di OPTOUT1 (richiesta di Freedom: mostrare COSA rifiutava),
(2) tutte le rep di OPTOUT1 per braccio con flag e primi 240 caratteri,
(3) ogni rep con flag [OPT-OUT-*] fuori dal punto OPTOUT1 (es. il Genesis di Qwen).
Solo a schermo: niente finisce nel repo."""
import json, re
from pathlib import Path

pts = {p["pid"]: p for p in map(json.loads, Path("out/replay_set.jsonl").read_text().splitlines())}

def one(s, n=240):
    return re.sub(r"\s+", " ", (s or "")).strip()[:n]

o = pts["OPTOUT1"]
print("=== CONTESTO STORICO OPTOUT1 (call 71, 2026-07-19) ===")
print("AMBRA:", one(o["messages"][-1]["content"], 400))
print("FREEDOM:", one(o["hist_response"], 400))

for arm in ("M1", "M2"):
    f = Path(f"out/runs_{arm}.jsonl")
    if not f.exists():
        continue
    seen = {}
    for l in f.read_text().splitlines():
        r = json.loads(l)
        if r.get("kind") == "error":
            continue
        seen[(r["pid"], r["rep"])] = r
    print(f"\n=== OPTOUT1 reps {arm} ===")
    for (pid, rep), r in sorted(seen.items()):
        if pid != "OPTOUT1":
            continue
        flag = r.get("optout") or "none"
        body = r.get("text") or f"tool:{r.get('tool')} {one(r.get('args'), 80)}"
        print(f"[{rep:02d}] {flag:8s} {one(body)}")
    print(f"\n=== flag OPT-OUT fuori da OPTOUT1 ({arm}) ===")
    hit = False
    for (pid, rep), r in sorted(seen.items()):
        if pid != "OPTOUT1" and r.get("optout"):
            hit = True
            print(f"{pid} rep{rep} [{r['optout']}] {one(r.get('text'))}")
    if not hit:
        print("nessuno")
