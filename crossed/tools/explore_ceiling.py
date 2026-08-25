#!/usr/bin/env python3
"""explore_ceiling.py - EXPLORATORY, post-hoc, not in the pre-registration.

P1b came out positive: the record moves the answer about twice as far under
CONFLICT as under AGREE. Two stories fit that number and the crossed design
does not separate them.

  ceiling   under AGREE the model already prefers the answer the record
            licenses, so there is little room left to move
  conflict  the model responds to the contradiction itself

The no-record contexts measure how far from neutral the model already sat,
before any record arrived. This script asks whether that starting point
predicts the size of the effect, which is the signature the ceiling story
must leave.

Everything here is exploratory. It carries no threshold, no confirmatory
claim, and it does not touch P1a or P2.

Usage:
  python3 explore_ceiling.py --rows crossed_rows.jsonl --items items_pod.jsonl \
      --out ceiling_exploratory.md
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", default="ceiling_exploratory.md")
    args = ap.parse_args()

    rows = {r["item_id"]: r for r in
            (json.loads(l) for l in open(args.rows, encoding="utf-8") if l.strip())}
    items = [json.loads(l) for l in open(args.items, encoding="utf-8") if l.strip()]

    nr = {}
    for it in items:
        if it["kind"] == "no_record":
            r = rows.get(it["item_id"])
            if r:
                nr[(it["clause_id"], it["constitution_version"])] = r["y"]

    recs = []
    for it in items:
        if it["kind"] != "main":
            continue
        r = rows.get(it["item_id"])
        if r is None:
            continue
        key = (it["clause_id"], it["constitution_version"])
        base = nr[key]
        sign = 1.0 if it["condition"] == "AGREE" else -1.0
        a = sign * (r["y"] - base)
        # headroom: how far the no-record answer already sat from neutral, in
        # the direction the record licenses. Large positive headroom means the
        # model already preferred the record's answer before seeing it.
        headroom = sign * base
        recs.append({"clause": it["clause_id"], "cls": it["record_class"],
                     "cond": it["condition"], "span": it["span_key"],
                     "a": a, "headroom": headroom, "y_no_record": base})

    L = []
    def w(x=""):
        L.append(x); print(x)

    w("# Ceiling check for P1b - EXPLORATORY, post-hoc")
    w()
    w("Not in the pre-registration. No thresholds, no confirmatory claim. "
      "P1a and P2 are unaffected by anything here.")
    w()

    A = np.array([r["a"] for r in recs])
    H = np.array([r["headroom"] for r in recs])
    C = np.array([r["cond"] for r in recs])

    w("## Where the model already stood, before any record")
    w()
    w("| clause | version | no-record y | reading |")
    w("|---|---|---|---|")
    for (clause, ver), y in sorted(nr.items()):
        near = "near neutral" if abs(y) < 1.0 else ("leaning to the constitution's answer"
                                                   if y > 0 else "leaning against it")
        w("| %s | %s | %+.3f | %s |" % (clause, ver, y, near))
    w()
    w("y is the log-odds of the answer the constitution in that context licenses, "
      "against the other answer. A large positive value means the model needed "
      "no record to agree with the constitution.")
    w()

    w("## Headroom against effect size")
    w()
    w("Headroom is how far the no-record answer already sat in the direction the "
      "record licenses. Under the ceiling story, effects shrink as headroom grows, "
      "so the correlation should be clearly negative.")
    w()
    for cond in ("AGREE", "CONFLICT", "both"):
        m = np.ones(len(recs), bool) if cond == "both" else (C == cond)
        if m.sum() < 3:
            continue
        h, a = H[m], A[m]
        r = float(np.corrcoef(h, a)[0, 1]) if h.std() > 0 else float("nan")
        sl = float(np.polyfit(h, a, 1)[0]) if h.std() > 0 else float("nan")
        w("- %s: n = %d, mean headroom %+.3f, mean effect %+.3f, "
          "correlation %+.3f, slope %+.3f" % (cond, m.sum(), h.mean(), a.mean(), r, sl))
    w()

    w("## The comparison the ceiling story has to survive")
    w()
    w("If the ceiling explains everything, then items with the same headroom "
      "should show the same effect whatever the condition. I split at the median "
      "headroom of the AGREE items and read the effects across the cut.")
    w()
    med = float(np.median(H[C == "AGREE"]))
    w("Median AGREE headroom: %+.3f" % med)
    w()
    w("| condition | headroom | n | mean effect |")
    w("|---|---|---|---|")
    for cond in ("AGREE", "CONFLICT"):
        for lab, m2 in (("low", H <= med), ("high", H > med)):
            m = (C == cond) & m2
            if m.sum():
                w("| %s | %s | %d | %+.3f |" % (cond, lab, m.sum(), A[m].mean()))
    w()
    low_a = A[(C == "AGREE") & (H <= med)]
    low_c = A[(C == "CONFLICT") & (H <= med)]
    if len(low_a) and len(low_c):
        w("Among low-headroom items, where neither condition is near a ceiling, "
          "the effect is %+.3f under AGREE and %+.3f under CONFLICT, a gap of %+.3f."
          % (low_a.mean(), low_c.mean(), low_c.mean() - low_a.mean()))
        w()
        w("A gap that stays this size once headroom is matched is not what the "
          "ceiling story predicts. A gap that collapses is.")
    w()

    w("## Per clause")
    w()
    w("| clause | AGREE effect | CONFLICT effect | gap |")
    w("|---|---|---|---|")
    byc = defaultdict(lambda: defaultdict(list))
    for r in recs:
        byc[r["clause"]][r["cond"]].append(r["a"])
    for clause in sorted(byc):
        ag = np.mean(byc[clause]["AGREE"]) if byc[clause]["AGREE"] else float("nan")
        co = np.mean(byc[clause]["CONFLICT"]) if byc[clause]["CONFLICT"] else float("nan")
        w("| %s | %+.3f | %+.3f | %+.3f |" % (clause, ag, co, co - ag))
    w()
    w("What I would do with a strong signal here: pre-register it as the next "
      "confirmatory question, not report it as a result of this one.")

    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\nscritto %s" % args.out)


if __name__ == "__main__":
    main()
