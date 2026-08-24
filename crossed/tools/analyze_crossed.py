#!/usr/bin/env python3
"""analyze_crossed.py - the frozen analysis of the crossed-constitution study.

Implements section 6 of the pre-registration and nothing else. Every choice
that could move after seeing a number is written here in code: the ridge grid,
the inner folds, the standardisation, the score orientation, the bootstrap, the
thresholds. The bootstrap redraws spans stratified by clause and record class
and reruns the whole learning procedure inside each resample.

Statistics produced:
  P1a  record incorporation, confirmatory, pooled mean of a > 0
  P1b  condition contrast of insertion effects, estimated only
  P2   decoding of the operational condition, confirmatory, macro paired
       accuracy above 0.5, substantial at 0.70
  P3   record-text baseline, exactly 0.5 by construction, integrity check
  P4   off-target mirror control, q_style with one-sided fire rule

Usage:
  python3 analyze_crossed.py --rows crossed_rows.jsonl --acts crossed_acts.npz \
      --items crossed_items.jsonl --out crossed_report.md
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

# ---- frozen constants, section 6 -------------------------------------------
ALPHA_GRID = np.logspace(-3, 3, 13)
INNER_FOLDS = 5
N_BOOT_P1 = 10000
N_BOOT_P2 = 2000
N_BOOT_P4 = 10000
CI = 95.0
SEED = 20260825
P2_SUBSTANTIAL = 0.70


# ---- ridge, written out so the fit has no hidden options -------------------
def ridge_fit(X, y, alpha):
    Xb = np.hstack([X, np.ones((X.shape[0], 1))])
    d = Xb.shape[1]
    P = np.eye(d) * alpha
    P[-1, -1] = 0.0
    return np.linalg.solve(Xb.T @ Xb + P, Xb.T @ y)


def ridge_score(X, w):
    return np.hstack([X, np.ones((X.shape[0], 1))]) @ w


def grouped_folds(groups, k, rng):
    uniq = np.array(sorted(set(groups)))
    rng.shuffle(uniq)
    assign = {g: i % k for i, g in enumerate(uniq)}
    return np.array([assign[g] for g in groups])


def pick_alpha(X, y, groups, rng):
    folds = grouped_folds(groups, INNER_FOLDS, rng)
    best, best_acc = ALPHA_GRID[0], -1.0
    for a in ALPHA_GRID:
        accs = []
        for f in range(INNER_FOLDS):
            tr, va = folds != f, folds == f
            if va.sum() == 0 or tr.sum() == 0:
                continue
            mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-8
            w = ridge_fit((X[tr] - mu) / sd, y[tr], a)
            s = ridge_score((X[va] - mu) / sd, w)
            accs.append(float(np.mean(np.sign(s) == y[va])))
        m = float(np.mean(accs)) if accs else -1.0
        if m > best_acc + 1e-12:          # ties break toward the smaller alpha
            best, best_acc = a, m
    return best


# ---- the learning procedure, rerun inside every bootstrap resample ---------
def loco_paired_accuracy(units, acts, rng, return_lines=False):
    """units: list of dicts with clause, cls, span, id_agree, id_conflict."""
    clauses = sorted({u["clause"] for u in units})
    per_clause_acc, lines, per_unit = {}, {}, {}
    for held in clauses:
        tr = [u for u in units if u["clause"] != held]
        te = [u for u in units if u["clause"] == held]
        if not tr or not te:
            continue
        X, y, g = [], [], []
        for u in tr:
            X.append(acts[u["id_conflict"]]); y.append(1.0); g.append(u["span"])
            X.append(acts[u["id_agree"]]);    y.append(-1.0); g.append(u["span"])
        X, y = np.array(X), np.array(y)
        alpha = pick_alpha(X, y, g, rng)
        mu, sd = X.mean(0), X.std(0) + 1e-8
        w = ridge_fit((X - mu) / sd, y, alpha)
        hits = []
        for u in te:
            pair = np.array([acts[u["id_conflict"]], acts[u["id_agree"]]])
            sc = ridge_score((pair - mu) / sd, w)
            h = 1.0 if sc[0] > sc[1] else (0.5 if sc[0] == sc[1] else 0.0)
            hits.append(h)
            per_unit[u["span"]] = (u["clause"], u["cls"], h)
        per_clause_acc[held] = float(np.mean(hits))
        if return_lines:
            lines[held] = (w, mu, sd)
    macro = float(np.mean([per_clause_acc[c] for c in sorted(per_clause_acc)]))
    if return_lines:
        return macro, per_clause_acc, lines, per_unit
    return macro, per_clause_acc, per_unit


def strat_resample(units, rng):
    by = defaultdict(list)
    for u in units:
        by[(u["clause"], u["cls"])].append(u)
    out = []
    for key, group in by.items():
        spans = sorted({u["span"] for u in group})
        drawn = rng.choice(spans, size=len(spans), replace=True)
        idx = defaultdict(list)
        for u in group:
            idx[u["span"]].append(u)
        for s in drawn:
            out.extend(idx[s])
    return out


def boot_ci(values, n_boot, rng, stat=np.mean):
    v = np.asarray(values, dtype=float)
    draws = [stat(v[rng.integers(0, len(v), len(v))]) for _ in range(n_boot)]
    lo, hi = np.percentile(draws, [(100 - CI) / 2, 100 - (100 - CI) / 2])
    return float(stat(v)), float(lo), float(hi)


def cluster_boot_ci(records, n_boot, rng):
    """records: list of (clause, cls, span, value). Macro-average by clause."""
    by = defaultdict(list)
    for clause, cls, span, val in records:
        by[(clause, cls)].append((span, val))
    def macro(sample):
        per_clause = defaultdict(list)
        for clause, val in sample:
            per_clause[clause].append(val)
        return float(np.mean([np.mean(per_clause[c]) for c in sorted(per_clause)]))
    flat = [(c, v) for (c, _), lst in by.items() for _, v in lst]
    point = macro(flat)
    draws = []
    for _ in range(n_boot):
        sample = []
        for (clause, cls), lst in by.items():
            spans = sorted({s for s, _ in lst})
            idx = defaultdict(list)
            for s, v in lst:
                idx[s].append(v)
            for s in rng.choice(spans, size=len(spans), replace=True):
                sample.extend((clause, v) for v in idx[s])
        draws.append(macro(sample))
    lo, hi = np.percentile(draws, [(100 - CI) / 2, 100 - (100 - CI) / 2])
    return point, float(lo), float(hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--acts", required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", default="crossed_report.md")
    args = ap.parse_args()

    rows = {r["item_id"]: r for r in
            (json.loads(l) for l in open(args.rows, encoding="utf-8") if l.strip())}
    items = [json.loads(l) for l in open(args.items, encoding="utf-8") if l.strip()]
    acts_npz = np.load(args.acts)
    acts = {k: acts_npz[k].astype(np.float64) for k in acts_npz.files}
    rng = np.random.default_rng(SEED)

    L = []
    def w(line=""):
        L.append(line); print(line)

    w("# Crossed-constitution study - frozen analysis")
    w()
    w("Seed %d. Grid %d values %.0e to %.0e. Inner folds %d, grouped by span."
      % (SEED, len(ALPHA_GRID), ALPHA_GRID[0], ALPHA_GRID[-1], INNER_FOLDS))
    w()

    # ---------- no-record baselines --------------------------------------
    nr = {}
    for it in items:
        if it["kind"] == "no_record":
            r = rows.get(it["item_id"])
            if r:
                nr[(it["clause_id"], it["constitution_version"])] = r["y"]
    w("No-record contexts scored: %d" % len(nr))

    # ---------- P1a and P1b ----------------------------------------------
    recs_a, recs_by_cond = [], defaultdict(list)
    for it in items:
        if it["kind"] != "main":
            continue
        r = rows.get(it["item_id"])
        if r is None:
            continue
        base = nr.get((it["clause_id"], it["constitution_version"]))
        if base is None:
            raise SystemExit("manca il no-record per %s/%s"
                             % (it["clause_id"], it["constitution_version"]))
        # y is oriented to the constitution; the record-aligned scale flips it
        # under CONFLICT, where the record licenses the other answer
        sign = 1.0 if it["condition"] == "AGREE" else -1.0
        a = sign * (r["y"] - base)
        recs_a.append((it["clause_id"], it["record_class"], it["span_key"], a))
        recs_by_cond[it["condition"]].append(
            (it["clause_id"], it["record_class"], it["span_key"], a))

    p, lo, hi = cluster_boot_ci(recs_a, N_BOOT_P1, rng)
    conf_p1a = lo > 0
    w()
    w("## P1a, record incorporation, confirmatory")
    w()
    w("Pooled mean a = %+.3f, %g%% CI [%+.3f, %+.3f] over %d items."
      % (p, CI, lo, hi, len(recs_a)))
    w("**%s.** A confirmed P1a licenses one sentence: a positive mean "
      "record-aligned shift across the fixed cells."
      % ("CONFIRMED" if conf_p1a else "NOT CONFIRMED"))
    for cond in ("AGREE", "CONFLICT"):
        pc, lc, hc = cluster_boot_ci(recs_by_cond[cond], N_BOOT_P1, rng)
        w("- %s: mean a = %+.3f [%+.3f, %+.3f], description only, no threshold"
          % (cond, pc, lc, hc))

    diff = ([(c, k, s, v) for c, k, s, v in recs_by_cond["CONFLICT"]] +
            [(c, k, s, -v) for c, k, s, v in recs_by_cond["AGREE"]])
    pd_, ld, hd = cluster_boot_ci(diff, N_BOOT_P1, rng)
    w()
    w("## P1b, condition contrast of insertion effects, estimated only")
    w()
    w("mean(a | CONFLICT) - mean(a | AGREE) = %+.3f [%+.3f, %+.3f]. No threshold: "
      "this is the class-by-version interaction, and any process with that "
      "signature produces it." % (2 * pd_, 2 * ld, 2 * hd))

    # ---------- P2 and P3 --------------------------------------------------
    units = []
    pairs = defaultdict(dict)
    for it in items:
        if it["kind"] == "main":
            pairs[it["span_key"]][it["condition"]] = it
    for span, m in sorted(pairs.items()):
        if set(m) != {"AGREE", "CONFLICT"}:
            continue
        ia, ic = m["AGREE"], m["CONFLICT"]
        if ia["item_id"] in acts and ic["item_id"] in acts:
            units.append({"clause": ia["clause_id"], "cls": ia["record_class"],
                          "span": span, "id_agree": ia["item_id"],
                          "id_conflict": ic["item_id"]})

    macro, per_clause, per_unit = loco_paired_accuracy(units, acts, np.random.default_rng(SEED))
    draws = []
    for b in range(N_BOOT_P2):
        r2 = np.random.default_rng(SEED + 1 + b)
        sample = strat_resample(units, r2)
        m2, _, _ = loco_paired_accuracy(sample, acts, r2)
        draws.append(m2)
        if (b + 1) % 200 == 0:
            print("  bootstrap P2 %d/%d" % (b + 1, N_BOOT_P2))
    lo2, hi2 = np.percentile(draws, [(100 - CI) / 2, 100 - (100 - CI) / 2])
    conf_p2 = lo2 > 0.5

    w()
    w("## P2, decoding of the operational condition, confirmatory")
    w()
    w("Macro paired accuracy = %.3f, %g%% CI [%.3f, %.3f] over %d pairs, "
      "%d bootstrap resamples with the full nested procedure rerun inside each."
      % (macro, CI, lo2, hi2, len(units), N_BOOT_P2))
    w("**%s.**%s" % ("CONFIRMED" if conf_p2 else "NOT CONFIRMED",
                     " Substantial." if conf_p2 and macro >= P2_SUBSTANTIAL else ""))
    w()
    w("| held-out target clause | paired accuracy |")
    w("|---|---|")
    for c in sorted(per_clause):
        w("| %s | %.3f |" % (c, per_clause[c]))
    w()
    w("Class-wise, from the same pooled predictions with no refit, description only.")
    w("A line reading the constitution version pushes these two apart, one high "
      "and one low; P4 is the control with the fixed rule.")
    for cls in ("consistent", "contradicting"):
        vals = [h for (_c, c2, h) in per_unit.values() if c2 == cls]
        if vals:
            w("- %s: %.3f over %d pairs" % (cls, float(np.mean(vals)), len(vals)))

    w()
    w("## P3, record-text baseline, integrity check")
    w()
    w("The record text is byte-identical within a pair, so a classifier reading "
      "it alone ties on every pair and scores exactly 0.500. Token parity was "
      "asserted on the rendered prompts before the run. Any departure means the "
      "pipeline leaked, and then this analysis is void.")

    # ---------- P4 ---------------------------------------------------------
    ot = defaultdict(dict)
    for it in items:
        if it["kind"] == "off_target":
            ot[it["span_key"]][it["condition"]] = it
    q_records = []
    _, _, lines, _ = loco_paired_accuracy(units, acts, np.random.default_rng(SEED),
                                          return_lines=True)
    for span, m in sorted(ot.items()):
        if set(m) != {"OT_ORIGINAL", "OT_OFFMIRROR"}:
            continue
        a_id, b_id = m["OT_ORIGINAL"]["item_id"], m["OT_OFFMIRROR"]["item_id"]
        clause, cls = m["OT_ORIGINAL"]["clause_id"], m["OT_ORIGINAL"]["record_class"]
        if a_id not in acts or b_id not in acts or clause not in lines:
            continue
        wv, mu, sd = lines[clause]
        sa, sb = ridge_score((np.array([acts[a_id], acts[b_id]]) - mu) / sd, wv)
        D = sb - sa
        if cls == "consistent":
            s = 1.0 if D > 0 else (0.5 if D == 0 else 0.0)
        else:
            s = 1.0 if D < 0 else (0.5 if D == 0 else 0.0)
        q_records.append((clause, cls, span, s))

    w()
    w("## P4, off-target mirror control")
    w()
    if q_records:
        qp, ql, qh = cluster_boot_ci(q_records, N_BOOT_P4, rng)
        fired = ql > 0.5
        w("q_style = %.3f, %g%% CI [%.3f, %.3f] over %d pairs."
          % (qp, CI, ql, qh, len(q_records)))
        w("**%s.**" % ("FIRED: the line tracks the constitution version"
                       if fired else "did not fire"))
        if fired and conf_p2:
            w()
            w("Pre-written sentence, section 6: the P2 criterion passed, and P4 "
              "detected class-conditional sensitivity to an off-target mirror, "
              "so target-specific attribution is contaminated.")
        elif not fired:
            w("Silence adds no positive evidence: the selected control did not fire.")
    else:
        w("No usable off-target pairs found.")

    # ---------- the four cells --------------------------------------------
    w()
    w("## How the results read together")
    w()
    if conf_p1a and conf_p2:
        w("Both confirmed: a positive mean record-aligned shift, and the "
          "operational condition decodable at the locked site.")
    elif conf_p1a:
        w("P1a only: a positive mean shift, and the P2 criterion not confirmed "
          "at the locked site. One site, one estimator, one corpus.")
    elif conf_p2:
        w("P2 only: the condition decodable, with no confirmed mean behavioral "
          "shift. An unconfirmed shift is not an absent one.")
    else:
        w("Neither criterion confirmed. The result stays compatible with the "
          "wording explanation, and compatible is the whole word.")

    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\nscritto %s" % args.out)


if __name__ == "__main__":
    main()
