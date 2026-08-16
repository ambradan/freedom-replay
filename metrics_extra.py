#!/usr/bin/env python3
"""Metriche extra per il report: auto-accordo di M2, aggregati vs storia,
bootstrap CI (95%) su ceiling e transfer coefficient, spazio congelato e collassato.
Uso: python3 metrics_extra.py   (da ~/freedom-replay, dopo analyze.py)"""
import json, random
from collections import Counter
from pathlib import Path

random.seed(20260816)

def coarse(r, kind):
    if r.get("optout") and (r.get("text") or "").strip().startswith("[OPT-OUT-"):
        return "optout"
    if r.get("kind") == "tool_call":
        return {"publish_page": "publish", "web_search": "search", "read_page": "read",
                "set_goal": "goal_op", "abandon_goal": "goal_op"}.get(r["tool"], "tool_other")
    first = (r.get("text") or "").strip().splitlines()
    first = first[0].lower() if first else ""
    for a, lab in (("declined", "decline"), ("revised_goals", "goal_op"),
                   ("publish_intent", "publish"), ("reflected", "reflect")):
        if a in first:
            return lab
    return "noncompliant" if kind == "genesis" else "text"

def hist_label(p):
    if p["hist_optout"] and p["hist_response"].strip().startswith("[OPT-OUT-"):
        return "optout"
    t = p.get("hist_first_tool")
    if t:
        return {"publish_page": "publish", "web_search": "search", "read_page": "read",
                "set_goal": "goal_op", "abandon_goal": "goal_op"}.get(t, "tool_other")
    first = p["hist_response"].strip().splitlines()[0].lower()
    for a, lab in (("declined", "decline"), ("revised_goals", "goal_op"),
                   ("publish_intent", "publish"), ("reflected", "reflect")):
        if a in first:
            return lab
    return "text"

def collapse(lab):
    return lab if lab in ("publish", "search", "read", "goal_op", "optout", "tool_other") else "no_tool"

pts = {p["pid"]: p for p in map(json.loads, Path("out/replay_set.jsonl").read_text().splitlines())}
runs = {pid: {"M1": [], "M2": []} for pid in pts}
for arm in ("M1", "M2"):
    seen = {}
    for l in Path(f"out/runs_{arm}.jsonl").read_text().splitlines():
        r = json.loads(l)
        if (r["pid"], r["rep"]) in seen:
            continue
        seen[(r["pid"], r["rep"])] = r
    for r in seen.values():
        if r.get("kind") == "error":
            continue
        runs[r["pid"]][arm].append(coarse(r, r.get("kind", "")))

def point_stats(view):
    out = []
    for pid, p in pts.items():
        a1 = [view(x) for x in runs[pid]["M1"]]
        a2 = [view(x) for x in runs[pid]["M2"]]
        if not a1 or not a2:
            continue
        m1, c1 = Counter(a1).most_common(1)[0]
        m2, c2 = Counter(a2).most_common(1)[0]
        h = view(hist_label(p))
        out.append({"kind": p["kind"], "s1": c1 / len(a1), "s2": c2 / len(a2),
                    "ag": sum(1 for x in a2 if x == m1) / len(a2),
                    "v1": sum(1 for x in a1 if x == h) / len(a1),
                    "v2": sum(1 for x in a2 if x == h) / len(a2)})
    return out

def summarize(rows, name):
    ceil1 = sum(r["s1"] for r in rows) / len(rows)
    ceil2 = sum(r["s2"] for r in rows) / len(rows)
    ag = sum(r["ag"] for r in rows) / len(rows)
    v1 = sum(r["v1"] for r in rows) / len(rows)
    v2 = sum(r["v2"] for r in rows) / len(rows)
    tcs = []
    for _ in range(10000):
        s = [random.choice(rows) for _ in rows]
        d = sum(r["s1"] for r in s) / len(s)
        n = sum(r["ag"] for r in s) / len(s)
        tcs.append(n / d if d else 0.0)
    tcs.sort()
    lo, hi = tcs[249], tcs[9749]
    print(f"[{name}] n={len(rows)}  M1 ceiling={ceil1:.3f}  M2 self-agreement={ceil2:.3f}  "
          f"M2->M1={ag:.3f}  TC={ag/ceil1:.3f} (95% CI {lo:.3f}-{hi:.3f})  "
          f"M1 vs hist={v1:.3f}  M2 vs hist={v2:.3f}")

allpts = point_stats(lambda x: x)
summarize(allpts, "frozen, all 30")
summarize([r for r in allpts if r["kind"] == "genesis"], "frozen, genesis")
gcoll = [r for r in point_stats(collapse) if r["kind"] == "genesis"]
summarize(gcoll, "collapsed, genesis")
