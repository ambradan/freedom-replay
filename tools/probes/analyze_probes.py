#!/usr/bin/env python3
"""analyze_probes.py - evaluates T16, T17 and T18 against the original run.

Inputs: probe_rows.jsonl (from run_probes_pod.py) and the original
runs_full/rows.jsonl. Writes probes_report.md and prints the same content.

Kill criteria (ratified 2026-08-23):
  T16: prior sign flips across paraphrases on more than two clauses re-scope
       the behavioral threshold law as per-elicitation.
  T17: mean |delta_swap - delta_orig| on matched (item, condition) jobs larger
       than half the mean original C-B effect on the same items declares an
       elicitation design flaw.
  T18: descriptive, no kill: the said/carried/done triangle counts.
"""
import argparse
import json
from collections import defaultdict


def load_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def sign(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-rows", required=True)
    ap.add_argument("--orig-rows", required=True)
    ap.add_argument("--out", default="probes_report.md")
    args = ap.parse_args()

    probes = load_jsonl(args.probe_rows)
    orig = load_jsonl(args.orig_rows)

    orig_delta = {(r["pair_id"], r["condition"]): float(r["delta"]) for r in orig}
    orig_prior = {}
    for r in orig:
        if r["condition"] == "none":
            orig_prior[r["clause_id"]] = float(r["delta"])

    L = []

    def w(line=""):
        L.append(line)
        print(line)

    w("# Probe results - T16 / T17 / T18")
    w()

    # ------------------------------- T16 ---------------------------------
    w("## T16 - paraphrase sensitivity")
    w()
    w("| clause | prior orig | prior p1 | prior p2 | sign flips |")
    w("|---|---|---|---|---|")
    t16 = [p for p in probes if p["test"] == "T16"]
    flip_clauses = 0
    shift_rows = []
    for clause in sorted({p["clause_id"] for p in t16}):
        pri = {v: None for v in ("p1", "p2")}
        for p in t16:
            if p["clause_id"] == clause and p["condition"] == "none":
                pri[p["variant"]] = float(p["delta"])
        po = orig_prior.get(clause)
        flips = sum(1 for v in ("p1", "p2")
                    if pri[v] is not None and po is not None
                    and sign(pri[v]) != sign(po))
        flip_clauses += int(flips > 0)
        w("| %s | %+.3f | %s | %s | %d |" % (
            clause, po,
            "%+.3f" % pri["p1"] if pri["p1"] is not None else "-",
            "%+.3f" % pri["p2"] if pri["p2"] is not None else "-", flips))
        for v in ("p1", "p2"):
            items = sorted({p["source_pair_id"] for p in t16
                            if p["clause_id"] == clause and p["variant"] == v
                            and p["condition"] in ("B", "C")})
            for it in items:
                d = {p["condition"]: float(p["delta"]) for p in t16
                     if p["variant"] == v and p["source_pair_id"] == it
                     and p["condition"] in ("B", "C")}
                if len(d) == 2:
                    s_new = d["C"] - d["B"]
                    s_old = orig_delta.get((it, "C"), float("nan")) - \
                        orig_delta.get((it, "B"), float("nan"))
                    shift_rows.append((clause, v, it, s_old, s_new))
    agree = sum(1 for *_, so, sn in shift_rows
                if so == so and sign(so) == sign(sn))
    w()
    kill16 = flip_clauses > 2
    w("Prior sign flips on %d/8 clauses (kill if > 2): %s." %
      (flip_clauses, "KILL, threshold law re-scoped as per-elicitation"
       if kill16 else "PASS"))
    w("Shift direction (C-B) agrees with the original on %d/%d matched "
      "item-variant checks." % (agree, len(shift_rows)))
    w()

    # ------------------------------- T17 ---------------------------------
    w("## T17 - option-order swap")
    w()
    t17 = [p for p in probes if p["test"] == "T17"]
    w("| clause | prior orig | prior swap | diff |")
    w("|---|---|---|---|")
    diffs, ref_effects = [], []
    for clause in sorted({p["clause_id"] for p in t17}):
        pr = next((float(p["delta"]) for p in t17
                   if p["clause_id"] == clause and p["condition"] == "none"), None)
        po = orig_prior.get(clause)
        w("| %s | %+.3f | %s | %s |" % (
            clause, po, "%+.3f" % pr if pr is not None else "-",
            "%+.3f" % (pr - po) if pr is not None else "-"))
    for p in t17:
        if p["condition"] in ("B", "C"):
            o = orig_delta.get((p["source_pair_id"], p["condition"]))
            if o is not None:
                diffs.append(abs(float(p["delta"]) - o))
    items17 = sorted({p["source_pair_id"] for p in t17
                      if p["condition"] in ("B", "C")})
    for it in items17:
        ob, oc = orig_delta.get((it, "B")), orig_delta.get((it, "C"))
        if ob is not None and oc is not None:
            ref_effects.append(oc - ob)
    order_effect = sum(diffs) / len(diffs) if diffs else float("nan")
    ref = 0.5 * abs(sum(ref_effects) / len(ref_effects)) if ref_effects else float("nan")
    kill17 = order_effect == order_effect and ref == ref and order_effect > ref
    w()
    w("Mean |delta_swap - delta_orig| on %d matched jobs: %.3f. Half of the "
      "mean original C-B effect on the same items: %.3f. %s." %
      (len(diffs), order_effect, ref,
       "KILL, elicitation design flaw declared" if kill17 else "PASS"))
    w()

    # ------------------------------- T18 ---------------------------------
    w("## T18 - self-report leg (descriptive)")
    w()
    t18 = [p for p in probes if p["test"] == "T18"]
    w("| clause | n | mean say-contradicts B | mean say-contradicts C | "
      "frac>0 B | frac>0 C |")
    w("|---|---|---|---|---|---|")
    tri = {"C_says_and_crossed": 0, "C_says_not_crossed": 0,
           "C_silent_and_crossed": 0, "C_silent_not_crossed": 0}
    for clause in sorted({p["clause_id"] for p in t18}):
        rowsB = [float(p["delta"]) for p in t18
                 if p["clause_id"] == clause and p["condition"] == "B"]
        rowsC = [(p["source_pair_id"], float(p["delta"])) for p in t18
                 if p["clause_id"] == clause and p["condition"] == "C"]
        po = orig_prior.get(clause, float("nan"))
        for it, d18 in rowsC:
            says = d18 > 0
            crossed = (po == po and po <= 0
                       and orig_delta.get((it, "C"), 0) > 0)
            key = ("C_says_" if says else "C_silent_") + \
                ("and_crossed" if crossed else "not_crossed")
            tri[key] += 1
        cvals = [d for _, d in rowsC]
        w("| %s | %d | %+.3f | %+.3f | %.2f | %.2f |" % (
            clause, len(rowsC),
            sum(rowsB) / len(rowsB) if rowsB else float("nan"),
            sum(cvals) / len(cvals) if cvals else float("nan"),
            sum(d > 0 for d in rowsB) / len(rowsB) if rowsB else float("nan"),
            sum(d > 0 for d in cvals) / len(cvals) if cvals else float("nan")))
    w()
    w("Triangle on C items (says contradicts = delta18 > 0; crossed = "
      "behavioral crossing in the original run):")
    for k in ("C_says_and_crossed", "C_says_not_crossed",
              "C_silent_and_crossed", "C_silent_not_crossed"):
        w("- %s: %d" % (k, tri[k]))

    open(args.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\nwritten: %s" % args.out)


if __name__ == "__main__":
    main()
