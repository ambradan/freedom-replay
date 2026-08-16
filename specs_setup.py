#!/usr/bin/env python3
"""One-shot: (1) specs_timeline.json dalla storia git di tools.py sul VPS,
(2) filtro delle rep M1 fatte con spec d'era sbagliata, (3) emendamento PREREG,
(4) commit. Idempotente: rilanciarlo non fa danni. Uso: python3 specs_setup.py"""
import ast, json, subprocess, sys
from pathlib import Path

def die(msg):
    sys.exit(f"STOP: {msg}")

# guardie
if "--specs" not in Path("replay.py").read_text():
    die("replay.py e' la versione vecchia: mv ~/Scaricati/replay.py ~/freedom-replay/replay.py e rilancia")

# 1) dump dal VPS e parsing
cmd = ('cd ~/freedom-v2 && for c in $(git log --reverse --format=%H -- src/freedom/tools.py); '
       'do echo "=====COMMIT $(git show -s --format=%cI $c)"; '
       'git show $c:src/freedom/tools.py | sed -n "/^SPECS/,/^]$/p"; done')
r = subprocess.run(["ssh", "freedom", cmd], capture_output=True, text=True, timeout=60)
if r.returncode != 0:
    die(f"ssh fallito: {r.stderr[:200]}")
tl, prev = [], None
for ch in r.stdout.split("=====COMMIT ")[1:]:
    date, _, body = ch.partition("\n")
    if "SPECS" not in body:
        continue
    specs = ast.literal_eval(body.split("=", 1)[1].strip())
    cur = json.dumps(specs, sort_keys=True)
    if cur != prev:
        tl.append({"from": date.strip(), "specs": specs})
        prev = cur
if not tl:
    die("nessuna era trovata nel dump")
Path("specs_timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1))
print(f"[1] {len(tl)} ere spec:", [e["from"][:16] for e in tl])

# 2) filtro rep M1 esistenti (SPECS estratte dal sorgente via ast: niente import di openai)
tree = ast.parse(Path("replay.py").read_text())
EMBEDDED = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "SPECS" for t in node.targets):
        EMBEDDED = ast.literal_eval(node.value)
        break
if EMBEDDED is None:
    die("SPECS non trovate in replay.py")
tl = sorted(tl, key=lambda e: e["from"])
pts = {p["pid"]: p["ts"] for p in map(json.loads, Path("out/replay_set.jsonl").read_text().splitlines())}

def active(ts):
    cur = tl[0]["specs"]
    for e in tl:
        if e["from"] <= ts:
            cur = e["specs"]
    return cur

emb_first = json.dumps(EMBEDDED, sort_keys=True) == json.dumps(tl[0]["specs"], sort_keys=True)
print(f"[2] spec embedded == prima era: {emb_first}")
runs = Path("out/runs_M1.jsonl")
keep, drop = [], []
if runs.exists():
    for l in runs.read_text().splitlines(keepends=True):
        row = json.loads(l)
        tag = row.get("specs_from", "founding")
        if tag == "founding":
            ok = emb_first and json.dumps(active(pts[row["pid"]]), sort_keys=True) == json.dumps(tl[0]["specs"], sort_keys=True)
        else:  # gia' rigiocata con timeline: valida per costruzione
            ok = True
        (keep if ok else drop).append(l)
    runs.write_text("".join(keep))
    if drop:
        with open("out/runs_M1_specmismatch.jsonl", "a") as f:
            f.writelines(drop)
print(f"[2] tenute {len(keep)}, scartate {len(drop)}")

# 3) emendamento PREREG (una volta sola)
prereg = Path("PREREG.md")
mark = "## Amendment (2026-08-16, before cross-substrate runs)"
if mark not in prereg.read_text():
    with prereg.open("a") as f:
        f.write(
            f"\n{mark}\n"
            "Tool specifications evolved during the logged window (read_page added; "
            "publish_page description revised). Each point is replayed with the tool "
            "specs active at its original timestamp, taken from the repository history "
            "of src/freedom/tools.py; era boundaries use commit timestamps (deploy lag "
            "possible, corroborated by config-hash boundaries). M1 repetitions executed "
            "before this amendment with founding specs on later-era points were "
            "discarded and quarantined.\n")
    print("[3] PREREG emendato")
else:
    print("[3] PREREG gia' emendato")

# 4) commit
subprocess.run(["git", "add", "PREREG.md"], check=False)
c = subprocess.run(["git", "commit", "-q", "-m", "amendment: era-versioned tool specs"],
                   capture_output=True, text=True)
print("[4]", "committato" if c.returncode == 0 else "niente da committare")
print("\nOra: python3 replay.py --arm M1 --k 5 --k-optout 20 --specs specs_timeline.json")
