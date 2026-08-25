#!/usr/bin/env python3
"""boot_collect.py - joins the bootstrap slices and applies the frozen rule.

Checks that the slices cover 0..N_BOOT_P2 exactly once with no gap and no
overlap, sorts them by index so the concatenated list is the one the serial
run would have produced, and reads off the percentile interval with the frozen
CI. Then writes the P2 section, including the leave-one-clause-out table and
the class-wise split, all from the frozen functions.

Usage:
  python3 boot_collect.py --rows R --acts A --items I --shards shards \
      --out p2_section.md
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

from boot_shard import load_units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--acts", required=True)
    ap.add_argument("--tools", default="tools")
    ap.add_argument("--shards", default="shards")
    ap.add_argument("--out", default="p2_section.md")
    args = ap.parse_args()

    sys.path.insert(0, args.tools)
    import analyze_crossed as ac

    files = sorted(Path(args.shards).glob("boot_*.json"))
    if not files:
        raise SystemExit("nessuna fetta in %s" % args.shards)
    pieces = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    pieces.sort(key=lambda p: p["start"])

    seeds = {p["seed"] for p in pieces}
    if seeds != {ac.SEED}:
        raise SystemExit("seed diversi tra le fette: %s" % seeds)

    cursor, draws = 0, []
    for p in pieces:
        if p["start"] != cursor:
            raise SystemExit("buco o sovrapposizione: attesa %d, trovata %d"
                             % (cursor, p["start"]))
        if len(p["values"]) != p["end"] - p["start"]:
            raise SystemExit("fetta %d-%d incompleta" % (p["start"], p["end"]))
        draws.extend(p["values"])
        cursor = p["end"]
    if cursor != ac.N_BOOT_P2:
        raise SystemExit("coperti %d resample su %d" % (cursor, ac.N_BOOT_P2))

    acts_npz = np.load(args.acts)
    acts = {k: acts_npz[k].astype(np.float64) for k in acts_npz.files}
    units, _ = load_units(args.rows, args.items, acts)

    macro, per_clause, per_unit = ac.loco_paired_accuracy(
        units, acts, np.random.default_rng(ac.SEED))
    lo, hi = np.percentile(draws, [(100 - ac.CI) / 2, 100 - (100 - ac.CI) / 2])
    conf = lo > 0.5

    L = []
    def w(x=""):
        L.append(x); print(x)

    w("## P2, decoding of the operational condition, confirmatory")
    w()
    w("Macro paired accuracy = %.3f, %g%% CI [%.3f, %.3f] over %d pairs, "
      "%d bootstrap resamples with the full nested procedure rerun inside each."
      % (macro, ac.CI, lo, hi, len(units), len(draws)))
    w("**%s.**%s" % ("CONFIRMED" if conf else "NOT CONFIRMED",
                     " Substantial." if conf and macro >= ac.P2_SUBSTANTIAL else ""))
    w()
    w("Resamples computed in %d slices, each drawing resample b from a "
      "generator seeded SEED + 1 + b exactly as the frozen script does, then "
      "concatenated in index order. Execution only: same estimator, same grid, "
      "same folds, same seeds, same thresholds." % len(pieces))
    w()
    w("| held-out target clause | paired accuracy |")
    w("|---|---|")
    for c in sorted(per_clause):
        w("| %s | %.3f |" % (c, per_clause[c]))
    w()
    w("Class-wise, from the same pooled predictions with no refit, "
      "description only.")
    for cls in ("consistent", "contradicting"):
        vals = [h for (_c, c2, h) in per_unit.values() if c2 == cls]
        if vals:
            w("- %s: %.3f over %d pairs" % (cls, float(np.mean(vals)), len(vals)))
    w()
    w("Bootstrap distribution: mean %.3f, sd %.3f, min %.3f, max %.3f."
      % (float(np.mean(draws)), float(np.std(draws)),
         float(np.min(draws)), float(np.max(draws))))

    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\nscritto %s" % args.out)


if __name__ == "__main__":
    main()
