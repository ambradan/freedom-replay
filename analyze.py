#!/usr/bin/env python3
"""Analysis. Coarse action space (pre-registered before runs):
  publish   = tool:publish_page OR text ACTION publish_intent
  search    = tool:web_search
  goal_op   = tool:set_goal OR tool:abandon_goal OR text ACTION revised_goals
  reflect   = text ACTION reflected
  decline   = text ACTION declined
  optout    = any [OPT-OUT-*] in text
  noncompliant = text with no parseable ACTION line (genesis only)
Metrics per category and per point:
  M1 self-agreement = modal share among M1 reps (reproducibility ceiling)
  M2->M1 agreement  = share of M2 reps matching M1 modal label
  transfer coefficient = mean(M2->M1) / mean(M1 self-agreement)
  vs history        = share of reps (per arm) matching the historical label
Outputs: out/analysis.md + out/points.csv
"""
import csv, json
from collections import Counter, defaultdict
from pathlib import Path

def coarse(r, kind):
    if r.get("kind") == "error":
        return "error"
    if r["kind"] == "tool_call":
        return {"publish_page": "publish", "web_search": "search", "read_page": "read",
                "set_goal": "goal_op", "abandon_goal": "goal_op"}.get(r["tool"], "tool_other")
    if r.get("optout") and (r.get("text") or "").strip().startswith("[OPT-OUT-"):
        return "optout"
    a = r.get("action", "")
    if a in ("publish_intent",):
        return "publish"
    if a in ("revised_goals",):
        return "goal_op"
    if a in ("reflected",):
        return "reflect"
    if a in ("declined",):
        return "decline"
    return "noncompliant" if kind == "genesis" else "text"

def hist_label(p):
    t = p.get("hist_first_tool")
    if t:
        return {"publish_page": "publish", "web_search": "search", "read_page": "read",
                "set_goal": "goal_op", "abandon_goal": "goal_op"}.get(t, "tool_other")
    if p["hist_optout"] and p["hist_response"].strip().startswith("[OPT-OUT-"):
        return "optout"
    first = p["hist_response"].strip().splitlines()[0].lower() if p["hist_response"].strip() else ""
    for a, lab in [("declined", "decline"), ("revised_goals", "goal_op"),
                   ("publish_intent", "publish"), ("reflected", "reflect")]:
        if a in first:
            return lab
    return "text"

def main():
    pts = {p["pid"]: p for p in map(json.loads, Path("out/replay_set.jsonl").read_text().splitlines())}
    runs = defaultdict(lambda: defaultdict(list))  # pid -> arm -> [labels]
    raw = defaultdict(lambda: defaultdict(list))
    dupes, errors = 0, 0
    for arm in ("M1", "M2"):
        f = Path(f"out/runs_{arm}.jsonl")
        if not f.exists():
            continue
        seen = {}
        for l in f.read_text().splitlines():
            r = json.loads(l)
            key = (r["pid"], r["rep"])
            if key in seen:
                if seen[key].get("kind") != "error" or r.get("kind") == "error":
                    dupes += 1
                    continue
                dupes += 1
            seen[key] = r
        for r in seen.values():
            if r.get("kind") == "error":
                errors += 1
                continue
            runs[r["pid"]][arm].append(coarse(r, r.get("kind", "")))
            raw[r["pid"]][arm].append(r)
    print(f"# dedup: {dupes} righe duplicate scartate, {errors} errori esclusi")
    rows, tcs = [], []
    md = ["# Replay analysis\n", "pid | kind | hist | M1 modal (share) | M2 modal (share) | M2->M1modal | M1 vs hist | M2 vs hist",
          "---|---|---|---|---|---|---|---"]
    for pid, p in sorted(pts.items()):
        h = hist_label(p)
        a1, a2 = runs[pid].get("M1", []), runs[pid].get("M2", [])
        if not a1 and not a2:
            continue
        m1 = Counter(a1).most_common(1)[0] if a1 else ("-", 0)
        m2 = Counter(a2).most_common(1)[0] if a2 else ("-", 0)
        s1 = m1[1] / len(a1) if a1 else 0
        s2 = m2[1] / len(a2) if a2 else 0
        agree = sum(1 for x in a2 if x == m1[0]) / len(a2) if (a1 and a2) else 0
        v1 = sum(1 for x in a1 if x == h) / len(a1) if a1 else 0
        v2 = sum(1 for x in a2 if x == h) / len(a2) if a2 else 0
        if a1 and a2 and s1 > 0:
            tcs.append((agree, s1))
        md.append(f"{pid} | {p['kind']} | {h} | {m1[0]} ({s1:.2f}) | {m2[0]} ({s2:.2f}) | {agree:.2f} | {v1:.2f} | {v2:.2f}")
        rows.append([pid, p["kind"], h, m1[0], f"{s1:.2f}", m2[0], f"{s2:.2f}", f"{agree:.2f}", f"{v1:.2f}", f"{v2:.2f}"])
    if tcs:
        num = sum(a for a, _ in tcs) / len(tcs)
        den = sum(s for _, s in tcs) / len(tcs)
        md += ["", f"**M1 self-agreement (ceiling): {den:.3f}**",
               f"**M2 -> M1-modal agreement: {num:.3f}**",
               f"**Transfer coefficient: {num/den:.3f}**" if den else ""]
    # opt-out case table
    md += ["", "## Opt-out: uso performativo vs menzione (ricodifica dichiarata)"]
    for pid, p in pts.items():
        if p["kind"] != "optout":
            continue
        h_use = p["hist_response"].strip().startswith("[OPT-OUT-")
        md.append(f"storico {pid}: flag di produzione=HARD, ricodificato={'USO' if h_use else 'MENZIONE (falso positivo dello strumento)'}")
        for arm in ("M1", "M2"):
            use = mention = none = 0
            for r in raw[pid][arm]:
                t = (r.get("text") or "").strip()
                if t.startswith("[OPT-OUT-"):
                    use += 1
                elif r.get("optout"):
                    mention += 1
                else:
                    none += 1
            frozen = Counter(r.get("optout", "") or "none" for r in raw[pid][arm])
            md.append(f"{pid} {arm}: usi={use} menzioni={mention} nessuno={none} | vista congelata any-tag: {dict(frozen)}")
    md += ["", "## Usi genuini del protocollo opt-out su TUTTI i punti (per braccio)"]
    for arm in ("M1", "M2"):
        uses = [(pid, r["rep"], r["optout"]) for pid in raw for r in raw[pid][arm]
                if (r.get("text") or "").strip().startswith("[OPT-OUT-")]
        md.append(f"{arm}: {uses if uses else 'nessuno'}")
    # genesis action distributions per arm vs history
    md += ["", "## Genesis action distribution"]
    for arm in ("M1", "M2"):
        c = Counter()
        for pid, p in pts.items():
            if p["kind"] == "genesis":
                c.update(runs[pid].get(arm, []))
        md.append(f"{arm}: {dict(c)}")
    histc = Counter(hist_label(p) for p in pts.values() if p["kind"] == "genesis")
    md.append(f"history: {dict(histc)}")
    # secondary declared view: collapse text-like genesis labels into no_tool
    def collapse(lab):
        return lab if lab in ("publish", "search", "read", "goal_op", "optout", "tool_other") else "no_tool"
    md += ["", "## Secondary view (declared, not pre-registered): genesis first action collapsed to tool vs no_tool"]
    md += ["pid | hist | M1 modal (share) | M2 modal (share) | M2->M1 | M1 vs hist | M2 vs hist", "---|---|---|---|---|---|---"]
    ctc = []
    for pid, p in sorted(pts.items()):
        if p["kind"] != "genesis":
            continue
        h = collapse(hist_label(p))
        a1 = [collapse(x) for x in runs[pid].get("M1", [])]
        a2 = [collapse(x) for x in runs[pid].get("M2", [])]
        if not a1 and not a2:
            continue
        m1 = Counter(a1).most_common(1)[0] if a1 else ("-", 0)
        m2 = Counter(a2).most_common(1)[0] if a2 else ("-", 0)
        s1 = m1[1] / len(a1) if a1 else 0
        s2 = m2[1] / len(a2) if a2 else 0
        ag = sum(1 for x in a2 if x == m1[0]) / len(a2) if (a1 and a2) else 0
        v1 = sum(1 for x in a1 if x == h) / len(a1) if a1 else 0
        v2 = sum(1 for x in a2 if x == h) / len(a2) if a2 else 0
        if a1 and a2 and s1 > 0:
            ctc.append((ag, s1))
        md.append(f"{pid} | {h} | {m1[0]} ({s1:.2f}) | {m2[0]} ({s2:.2f}) | {ag:.2f} | {v1:.2f} | {v2:.2f}")
    if ctc:
        n = sum(a for a, _ in ctc) / len(ctc)
        d = sum(s for _, s in ctc) / len(ctc)
        md += [f"**collapsed genesis: M1 ceiling {d:.3f}, M2->M1 {n:.3f}, coefficient {n/d:.3f}**"]
    # per-kind coefficients on the frozen space
    md += ["", "## Per-kind coefficients (frozen space)"]
    for kind in ("genesis", "probe", "optout"):
        tk = []
        for pid, p in pts.items():
            if p["kind"] != kind:
                continue
            a1, a2 = runs[pid].get("M1", []), runs[pid].get("M2", [])
            if a1 and a2:
                m1 = Counter(a1).most_common(1)[0]
                s1 = m1[1] / len(a1)
                ag = sum(1 for x in a2 if x == m1[0]) / len(a2)
                if s1 > 0:
                    tk.append((ag, s1))
        if tk:
            n = sum(a for a, _ in tk) / len(tk)
            d = sum(s for _, s in tk) / len(tk)
            md.append(f"{kind}: n_points={len(tk)} ceiling={d:.3f} agree={n:.3f} coeff={n/d:.3f}")
        else:
            md.append(f"{kind}: dati incompleti")
    Path("out/analysis.md").write_text("\n".join(md))
    with open("out/points.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pid", "kind", "hist", "m1_modal", "m1_share", "m2_modal", "m2_share", "m2_to_m1", "m1_vs_hist", "m2_vs_hist"])
        w.writerows(rows)
    print("\n".join(md))

if __name__ == "__main__":
    main()
