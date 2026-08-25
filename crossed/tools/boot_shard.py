#!/usr/bin/env python3
"""boot_shard.py - runs one slice of the P2 bootstrap, using the frozen code.

The pre-registered bootstrap draws resample b with its own generator, seeded
SEED + 1 + b, and the resamples do not talk to each other. So resample b gives
the same number whether it runs first, last, or in its own process. This
script computes a contiguous slice of them and writes the raw macro accuracies
to disk; boot_collect.py concatenates the slices in index order and applies
the frozen percentile rule.

Nothing in analyze_crossed.py is touched: this imports it and calls its
functions. Same estimator, same grid, same folds, same seeds, same thresholds.

Usage (one slice):
  python3 boot_shard.py --rows R --acts A --items I --start 0 --end 100 \
      --outdir shards

Usage (all slices, 24 at a time):
  see the loop printed by --plan
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


def load_units(rows_path, items_path, acts):
    rows = {r["item_id"]: r for r in
            (json.loads(l) for l in open(rows_path, encoding="utf-8") if l.strip())}
    items = [json.loads(l) for l in open(items_path, encoding="utf-8") if l.strip()]
    pairs = defaultdict(dict)
    for it in items:
        if it["kind"] == "main":
            pairs[it["span_key"]][it["condition"]] = it
    units = []
    for span, m in sorted(pairs.items()):
        if set(m) != {"AGREE", "CONFLICT"}:
            continue
        ia, ic = m["AGREE"], m["CONFLICT"]
        if ia["item_id"] in acts and ic["item_id"] in acts:
            units.append({"clause": ia["clause_id"], "cls": ia["record_class"],
                          "span": span, "id_agree": ia["item_id"],
                          "id_conflict": ic["item_id"]})
    return units, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--acts", required=True)
    ap.add_argument("--tools", default="tools",
                    help="directory holding the frozen analyze_crossed.py")
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--outdir", default="shards")
    ap.add_argument("--plan", type=int, default=0,
                    help="print the launch loop for N slices and exit")
    args = ap.parse_args()

    sys.path.insert(0, args.tools)
    import analyze_crossed as ac

    if args.plan:
        n = ac.N_BOOT_P2
        step = (n + args.plan - 1) // args.plan
        print("# %d resample totali, %d fette da %d" % (n, args.plan, step))
        print("mkdir -p shards")
        for i in range(args.plan):
            s, e = i * step, min((i + 1) * step, n)
            if s >= e:
                break
            print("nohup python3 boot_shard.py --rows %s --items %s --acts %s "
                  "--tools %s --start %d --end %d --outdir shards "
                  "> shards/s%03d.log 2>&1 &" %
                  (args.rows, args.items, args.acts, args.tools, s, e, i))
        return

    acts_npz = np.load(args.acts)
    acts = {k: acts_npz[k].astype(np.float64) for k in acts_npz.files}
    units, _ = load_units(args.rows, args.items, acts)

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / ("boot_%05d_%05d.json" % (args.start, args.end))

    vals = []
    for b in range(args.start, args.end):
        r2 = np.random.default_rng(ac.SEED + 1 + b)      # identico al frozen
        sample = ac.strat_resample(units, r2)
        m2, _, _ = ac.loco_paired_accuracy(sample, acts, r2)
        vals.append(m2)
        if (b - args.start + 1) % 20 == 0:
            print("%d/%d" % (b - args.start + 1, args.end - args.start), flush=True)

    target.write_text(json.dumps({"start": args.start, "end": args.end,
                                  "seed": ac.SEED, "values": vals}), encoding="utf-8")
    print("scritto %s, %d valori" % (target, len(vals)), flush=True)


if __name__ == "__main__":
    main()
