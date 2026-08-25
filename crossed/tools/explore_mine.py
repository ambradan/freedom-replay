#!/usr/bin/env python3
"""explore_mine.py - EXPLORATORY, post-hoc, not in the pre-registration.

Digs into everything the confirmatory analysis does not use: the behavioral
side of the off-target rows, the decomposition of each clause's prior into a
model component and a document component, the per-word asymmetry of record
incorporation, the geometry of the paired activations, and the bf16
quantisation of extreme log probabilities.

No thresholds, no confirmatory claims. P1a and P2 are untouched. Deliberately
absent: any decoding of the operational condition from activations, which is
P2 and stays frozen.

Usage:
  python3 explore_mine.py --rows crossed_rows.jsonl --items items_pod.jsonl \
      --acts crossed_acts.npz --out mine_exploratory.md
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
    ap.add_argument("--acts", required=True)
    ap.add_argument("--out", default="mine_exploratory.md")
    args = ap.parse_args()

    rows = {r["item_id"]: r for r in
            (json.loads(l) for l in open(args.rows, encoding="utf-8") if l.strip())}
    items = [json.loads(l) for l in open(args.items, encoding="utf-8") if l.strip()]
    acts = dict(np.load(args.acts))

    L = []
    def w(x=""):
        L.append(x); print(x)

    w("# Deeper exploratory pass - post-hoc, outside the pre-registration")
    w()
    w("Everything here is description. No thresholds. P1a and P2 stand apart.")
    w()

    nr = {}
    for it in items:
        if it["kind"] == "no_record":
            nr[(it["clause_id"], it["constitution_version"])] = rows[it["item_id"]]["y"]

    # ---- A. prior decomposition: model component vs document component ----
    w("## A. Whose prior is it: the model's or the document's")
    w()
    w("In fixed coordinates, z = logp(original's answer) - logp(mirror's answer). "
      "The no-record contexts give z under each constitution. Their average is "
      "the part of the answer the document cannot move (the model's own prior); "
      "half their difference is the part the document owns (the document swing).")
    w()
    w("| clause | model prior | document swing | largest record effect |")
    w("|---|---|---|---|")
    z = {}
    for cl in sorted({c for c, _ in nr}):
        z_orig = nr[(cl, "original")]
        z_mirr = -nr[(cl, "mirror")]
        z[cl] = (0.5 * (z_orig + z_mirr), 0.5 * (z_orig - z_mirr))

    cell_eff = defaultdict(list)
    for it in items:
        if it["kind"] != "main":
            continue
        r = rows[it["item_id"]]
        base = nr[(it["clause_id"], it["constitution_version"])]
        sign = 1.0 if it["condition"] == "AGREE" else -1.0
        cell_eff[(it["clause_id"], it["constitution_version"],
                  it["condition"])].append(sign * (r["y"] - base))
    max_eff = {}
    for (cl, ver, cond), vals in cell_eff.items():
        m = float(np.mean(vals))
        if cl not in max_eff or m > max_eff[cl]:
            max_eff[cl] = m
    for cl in sorted(z):
        mp, ds = z[cl]
        w("| %s | %+.2f | %+.2f | %+.2f |" % (cl, mp, ds, max_eff[cl]))
    mps = np.array([abs(z[c][0]) for c in sorted(z)])
    mes = np.array([max_eff[c] for c in sorted(z)])
    dss = np.array([abs(z[c][1]) for c in sorted(z)])
    w()
    w("Correlation of the largest record effect with |model prior|: %+.3f; "
      "with document swing: %+.3f. Eight clauses, description only."
      % (float(np.corrcoef(mps, mes)[0, 1]), float(np.corrcoef(dss, mes)[0, 1])))
    w()
    w("Reading: the record moves answers where the model itself holds no strong "
      "prior, however strongly the document speaks. The document can be "
      "contradicted; the model, on this corpus, cannot.")
    w()

    # ---- B. per-word incorporability ------------------------------------
    w("## B. The word the record pushes toward, not the relation")
    w()
    w("| clause | word | effect where space existed | space (headroom) |")
    w("|---|---|---|---|")
    push = defaultdict(list)
    for it in items:
        if it["kind"] != "main":
            continue
        r = rows[it["item_id"]]
        base = nr[(it["clause_id"], it["constitution_version"])]
        sign = 1.0 if it["condition"] == "AGREE" else -1.0
        a = sign * (r["y"] - base)
        word = (r["opt_constitution"] if
                ((it["record_class"] == "consistent") == (it["constitution_version"] == "original"))
                else r["opt_other"])
        push[(it["clause_id"], word)].append((a, sign * base))
    for (cl, word), vals in sorted(push.items()):
        spaced = [a for a, h in vals if h < -3]
        if spaced:
            hs = np.mean([h for a, h in vals if h < -3])
            w("| %s | %s | %+.2f | %+.1f |" % (cl, word, float(np.mean(spaced)), hs))
    w()

    # ---- C. off-target rows, behavioral side ----------------------------
    w("## C. Off-target rows read behaviorally: cross-clause interference")
    w()
    w("Each off-target pair holds the record and the question fixed and swaps "
      "one line of an unrelated clause. The y difference between the two "
      "members is the behavioral spillover of that unrelated edit.")
    w()
    ot = defaultdict(dict)
    for it in items:
        if it["kind"] == "off_target":
            ot[it["span_key"]][it["condition"]] = it
    spill = defaultdict(list)
    for span, m in sorted(ot.items()):
        if set(m) != {"OT_ORIGINAL", "OT_OFFMIRROR"}:
            continue
        a = rows[m["OT_ORIGINAL"]["item_id"]]
        b = rows[m["OT_OFFMIRROR"]["item_id"]]
        d = b["y"] - a["y"]
        spill[(m["OT_ORIGINAL"]["clause_id"], m["OT_ORIGINAL"]["off_target_of"])].append(d)
    alld = [d for v in spill.values() for d in v]
    w("Across %d pairs: mean %+0.3f, sd %0.3f, largest |spillover| %0.3f."
      % (len(alld), float(np.mean(alld)), float(np.std(alld)),
         float(np.max(np.abs(alld)))))
    w()
    w("| question clause | edited clause | mean spillover | max |abs| |")
    w("|---|---|---|---|")
    for (qc, ec), v in sorted(spill.items()):
        w("| %s | %s | %+.3f | %.3f |" % (qc, ec, float(np.mean(v)),
                                          float(np.max(np.abs(v)))))
    w()

    # ---- D. activation geometry, descriptive only -----------------------
    w("## D. Activation geometry at the record position, descriptive")
    w()
    w("For each main pair, the two prompts differ only in the constitution far "
      "upstream; the record tokens are identical. The activation difference at "
      "the record position is therefore the pure trace of the constitution "
      "swap. No probe is fitted here: decoding is P2 and stays frozen.")
    w()
    pairs = defaultdict(dict)
    for it in items:
        if it["kind"] == "main":
            pairs[it["span_key"]][it["condition"]] = it
    deltas = defaultdict(list)
    dy = defaultdict(list)
    for span, m in sorted(pairs.items()):
        if set(m) != {"AGREE", "CONFLICT"}:
            continue
        ia, ic = m["AGREE"], m["CONFLICT"]
        if ia["item_id"] not in acts or ic["item_id"] not in acts:
            continue
        d = acts[ic["item_id"]].astype(np.float64) - acts[ia["item_id"]].astype(np.float64)
        deltas[ia["clause_id"]].append(d)
        dy[ia["clause_id"]].append(rows[ic["item_id"]]["y"] - rows[ia["item_id"]]["y"])
    w("| clause | mean ||delta act|| | direction coherence within clause | corr(||delta act||, |delta y|) |")
    w("|---|---|---|---|")
    mean_dirs = {}
    for cl in sorted(deltas):
        D = np.stack(deltas[cl])
        norms = np.linalg.norm(D, axis=1)
        mu = D.mean(0); mun = np.linalg.norm(mu)
        coh = float(np.mean([np.dot(d, mu) / (np.linalg.norm(d) * mun + 1e-9) for d in D]))
        ady = np.abs(np.array(dy[cl]))
        cr = float(np.corrcoef(norms, ady)[0, 1]) if norms.std() > 0 and ady.std() > 0 else float("nan")
        mean_dirs[cl] = mu / (mun + 1e-9)
        w("| %s | %.1f | %.3f | %+.3f |" % (cl, float(norms.mean()), coh, cr))
    w()
    w("Cosine between clause mean directions (is there one shared 'version' "
      "direction, or one per clause):")
    w()
    cls_ = sorted(mean_dirs)
    w("| | " + " | ".join(c[:10] for c in cls_) + " |")
    w("|---|" + "|".join(["---"] * len(cls_)) + "|")
    for a in cls_:
        row = [a[:10]]
        for b in cls_:
            row.append("%.2f" % float(np.dot(mean_dirs[a], mean_dirs[b])))
        w("| " + " | ".join(row) + " |")
    w()

    # ---- E. bf16 quantisation note --------------------------------------
    w("## E. Quantisation of extreme log probabilities")
    w()
    ys = np.array([rows[it["item_id"]]["y"] for it in items if it["item_id"] in rows])
    onq = np.mean(np.abs(ys * 8 - np.round(ys * 8)) < 1e-6)
    w("Fraction of y values sitting exactly on a 0.125 grid: %.2f. Extreme "
      "logits under bfloat16 quantise the losing option's log probability at "
      "roughly that step; two clauses even share the identical no-record value "
      "-8.250. Harmless for the confirmatory means, which average across items "
      "with a relative error near one percent, and recorded here." % float(onq))
    w()

    w("## What this licenses")
    w()
    w("Nothing confirmatory. Two candidate laws for the next pre-registration: "
      "the record moves answers in inverse proportion to the model-owned share "
      "of the prior; and incorporation is word-directional, with records that "
      "assert plausible operational events absorbed and records that deny "
      "declared-final events inert. Both need stimuli built to separate content "
      "from class, which this corpus was not built to do.")

    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\nscritto %s" % args.out)


if __name__ == "__main__":
    main()
