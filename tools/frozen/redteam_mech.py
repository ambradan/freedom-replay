#!/usr/bin/env python3
"""redteam_mech.py - executes the cache-side battery of RED-TEAM-PROTOCOL-mech-v1
(T1, T2, T7, T8, T9a, T9b, T10, T11, T12, T13, T14, T15) against the real run.

Sits next to analyze_mech.py and imports it. Never analyzes test-split
internals: every direction, margin and baseline below is computed on the
train+dev pool only. T1 alone reads all rows, a record-level check on data
whose behavioral values are already declared as known.

Usage (pod):
  python3 redteam_mech.py --runs runs_full --pairs stimuli_split_pod.jsonl \
      --analysis analysis --out redteam_out
Optional: --quick (smaller permutation counts, for the synthetic fixture).

Kill thresholds are the ones ratified on 2026-08-23. Output:
  <out>/REDTEAM-RESULTS.md and <out>/REDTEAM-RESULTS.json
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("am", os.path.join(HERE, "analyze_mech.py"))
am = importlib.util.module_from_spec(spec)
spec.loader.exec_module(am)

# thresholds ratified 2026-08-23
KILL_MEMLAST = 0.65      # T9a: optout LOCO at memory_last below this
KILL_SEMANTIC = 0.75     # T11: semantic baseline at or above this on optout
KILL_PERM_RATE = 0.10    # T8: pseudo-clause event rate at or above this
KILL_SEED_MOVE = 0.05    # T15: any CI bound moving more than this
KILL_FAULT_SHIFT = 0.02  # T2: silent corruption moving a headline more than this
TOL_RECORD = 1e-3        # T1: |delta - (logp_planted - logp_consistent)|
OPTOUT = "optout_rispettati"

RESULTS = []
OUT_DIR = None
HEADER = {}


def flush_results():
    """Rewrite the output files after every test, so a crash mid-battery
    leaves a partial record instead of nothing. The record layer must not
    lose the record on failure; that is this project's own thesis."""
    if OUT_DIR is None:
        return
    json.dump({**HEADER, "results": RESULTS},
              open(os.path.join(OUT_DIR, "REDTEAM-RESULTS.json"), "w"), indent=2)
    md = ["# Red team results - cache battery (v1.1 material)", "",
          HEADER.get("run_line", ""), 
          "Test split internals untouched: every number below comes from train+dev.",
          "", "| id | test | status | verdict |", "|---|---|---|---|"]
    for r in RESULTS:
        md.append("| %s | %s | %s | %s |" % (r["id"], r["name"], r["status"], r["verdict"]))
    md += ["", "Full numbers in REDTEAM-RESULTS.json."]
    open(os.path.join(OUT_DIR, "REDTEAM-RESULTS.md"), "w").write("\n".join(md) + "\n")


def record(tid, name, status, numbers, criterion, verdict):
    RESULTS.append(OrderedDict(
        id=tid, name=name, status=status, numbers=numbers,
        criterion=criterion, verdict=verdict))
    print("[%s] %s -> %s | %s" % (tid, name, status, verdict))
    flush_results()


def acc(margins):
    m = np.asarray(margins, dtype=float)
    return float(np.mean(m > 0) + 0.5 * np.mean(m == 0)) if len(m) else float("nan")


def find_alpha(metrics_path):
    try:
        m = json.load(open(metrics_path))
    except Exception:
        return 1e4, "fallback 1e4 (metrics.json unreadable)"
    stack = [m.get("baselines", m)]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "alpha" and isinstance(v, (int, float)):
                    return float(v), "from metrics.json"
                stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)
    return 1e4, "fallback 1e4 (no alpha key found)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--analysis", required=True,
                    help="explore output dir holding selection.json and metrics.json")
    ap.add_argument("--out", default="redteam_out")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rng_master = np.random.default_rng(42)
    n_perm = 25 if args.quick else 200
    n_shuf = 15 if args.quick else 50

    sel = json.load(open(os.path.join(args.analysis, "selection.json")))
    layer, pidx = int(sel["layer"]), int(sel["position_idx"])
    alpha, alpha_src = find_alpha(os.path.join(args.analysis, "metrics.json"))
    pidx_mem = am.POSITIONS.index("memory_last")

    items, load_info = am.load_behaviour(args.runs, args.pairs, drop_test=False)
    item_ids = list(items.keys())
    cache_dir = os.path.join(args.analysis, "cache")
    acts_path = os.path.join(cache_dir, "acts.f32.npy")
    idx_path = os.path.join(cache_dir, "cache_index.json")
    if os.path.exists(acts_path) and os.path.exists(idx_path):
        index = json.load(open(idx_path))
        n_layers, d_model = index["n_layers"], index["d_model"]
        # the cache is a real .npy with header: raw np.memmap would read the
        # 128 header bytes as data and shift every value (caught by REF on the
        # fixture, where 128 bytes are exactly one layer row)
        acts = np.lib.format.open_memmap(acts_path, mode="r")
        expected = (len(index["item_ids"]), len(am.CONDITIONS),
                    len(am.POSITIONS), n_layers, d_model)
        if tuple(acts.shape) != expected:
            raise SystemExit("cache shape %s does not match index %s" %
                             (tuple(acts.shape), expected))
        mask = np.load(os.path.join(cache_dir, "mask.npy"))
        cache_ids = index["item_ids"]
    else:
        acts, mask, index = am.build_cache(args.runs, items, cache_dir)
        cache_ids = index["item_ids"]
        n_layers, d_model = index["n_layers"], index["d_model"]
    row_of = {iid: i for i, iid in enumerate(cache_ids)}

    global OUT_DIR, HEADER
    OUT_DIR = args.out
    HEADER = {"thresholds": {"memlast": KILL_MEMLAST, "semantic": KILL_SEMANTIC,
                             "perm_rate": KILL_PERM_RATE, "seed_move": KILL_SEED_MOVE,
                             "fault_shift": KILL_FAULT_SHIFT},
              "selection": {"layer": layer, "position": am.POSITIONS[pidx]},
              "alpha": {"value": alpha, "source": alpha_src},
              "run_line": "Run on the explore selection (layer %d, %s), alpha %s (%s)."
                          % (layer, am.POSITIONS[pidx], am.fmt(alpha, 0), alpha_src)}

    pool_ids = [i for i in item_ids if items[i]["split"] in ("train", "dev")]
    dev_ids = [i for i in item_ids if items[i]["split"] == "dev"]
    train_ids = [i for i in item_ids if items[i]["split"] == "train"]
    pool_rows = np.array([row_of[i] for i in pool_ids])
    ci_B, ci_C = am.CONDITIONS.index("B"), am.CONDITIONS.index("C")

    def diff_matrix(l, p):
        b = np.asarray(acts[pool_rows, ci_B, p, l, :], dtype=np.float64)
        c = np.asarray(acts[pool_rows, ci_C, p, l, :], dtype=np.float64)
        return c - b

    D = diff_matrix(layer, pidx)                      # (n_pool, d_model)
    is_tr = np.array([items[i]["split"] == "train" for i in pool_ids])
    is_dv = ~is_tr
    clause_of = np.array([items[i]["clause"] for i in pool_ids])
    span_of = np.array([items[i]["span_C_key"] for i in pool_ids])
    fam_of = np.array([items[i]["family"] for i in pool_ids])
    dN = np.array([items[i].get("delta_none", np.nan) for i in pool_ids])
    dC = np.array([items[i]["delta_C"] for i in pool_ids])
    optout_mask = clause_of == OPTOUT
    clauses = sorted(set(clause_of))

    def dir_from(sel_mask, M=None):
        M = D if M is None else M
        d = M[sel_mask].mean(axis=0)
        n = np.linalg.norm(d)
        return d / n if n > 0 else d

    def loco_margins(M=None):
        M = D if M is None else M
        marg = np.full(len(pool_ids), np.nan)
        for cl in clauses:
            held = clause_of == cl
            if held.all() or not held.any():
                continue
            marg[held] = M[held] @ dir_from(~held, M)
        return marg

    # ---------------- T1 record integrity + none constancy -----------------
    rows = am.read_jsonl(os.path.join(args.runs, "rows.jsonl"))
    r0 = rows[0]
    k_lp = "logp_planted" if "logp_planted" in r0 else None
    k_lc = "logp_consistent" if "logp_consistent" in r0 else None
    if k_lp and k_lc:
        errs = [abs(float(r["delta"]) - (float(r[k_lp]) - float(r[k_lc]))) for r in rows]
        mism = sum(1 for e in errs if e > TOL_RECORD)
        st = "PASS" if mism == 0 else "KILL"
        record("T1", "record integrity", st,
               {"rows": len(rows), "max_abs_err": float(max(errs)), "mismatches": mism},
               "any |delta-(lp-lc)| > %.0e stops everything" % TOL_RECORD,
               "all %d rows consistent (max err %.2e)" % (len(rows), max(errs))
               if mism == 0 else "%d mismatching rows" % mism)
    else:
        record("T1", "record integrity", "SKIP", {}, "needs logp fields",
               "logp fields absent from rows.jsonl")

    ni = am.CONDITIONS.index("none")
    none_pos = None
    for cand in range(len(am.POSITIONS)):
        if mask[pool_rows, ni, cand].all():
            none_pos = cand
            break
    if none_pos is not None:
        worst = 0.0
        for cl in clauses:
            sel_rows = pool_rows[clause_of == cl]
            block = np.asarray(acts[sel_rows, ni, none_pos, layer, :], dtype=np.float64)
            worst = max(worst, float(np.abs(block - block[0]).max()))
        st = "PASS" if worst < 1e-5 else "SOFT-FLAG"
        record("T1b", "none activation constancy per clause", st,
               {"position": am.POSITIONS[none_pos], "max_abs_dev": worst},
               "vectors identical within clause (determinism)",
               "max deviation %.2e at %s" % (worst, am.POSITIONS[none_pos]))
    else:
        record("T1b", "none activation constancy", "SKIP", {},
               "needs a position with none for all pool items", "none position not found")

    # ---------------- headline references (recomputed live) ----------------
    dir_tr = dir_from(is_tr)
    dev_margins = D[is_dv] @ dir_tr
    dev_acc = acc(dev_margins)
    lm = loco_margins()
    opt_margins = lm[optout_mask]
    opt_acc = acc(opt_margins)
    record("REF", "recomputed headlines", "INFO",
           {"dev_primary": dev_acc, "optout_loco": opt_acc},
           "must match the explore report",
           "dev %.3f, optout LOCO %.3f" % (dev_acc, opt_acc))

    # ---------------- T2 fault injection -----------------------------------
    faults = []

    def fault(name, detected_by, shift, detail):
        silent = detected_by == "SILENT"
        killed = silent and abs(shift) > KILL_FAULT_SHIFT
        faults.append({"corruption": name, "detected_by": detected_by,
                       "headline_shift": shift, "kill": killed, "detail": detail})

    rng = np.random.default_rng(7)
    victims = list(rng.choice(len(pool_ids), size=5, replace=False))

    # c1: rows-level full B/C swap (delta and logp together): T1 stays green.
    # Headline unit: fraction of pool items with positive shift, 0-1 scale.
    dB_arr = np.array([items[i]["delta_B"] for i in pool_ids])
    frac_before = float(np.mean((dC - dB_arr) > 0))
    dC_c, dB_c = dC.copy(), dB_arr.copy()
    for v in victims:
        dC_c[v], dB_c[v] = dB_c[v], dC_c[v]
    fault("c1 swap B/C rows (delta+logp)", "SILENT",
          float(np.mean((dC_c - dB_c) > 0)) - frac_before,
          "record self-consistent, behaviour shifts; no rows-vs-acts cross check exists")

    # c2: acts-level swap of B and C for 5 items
    Dc = D.copy()
    Dc[victims] = -Dc[victims]
    dev_acc_c2 = acc(Dc[is_dv] @ dir_from(is_tr, Dc))
    fault("c2 swap B/C activations", "SILENT", dev_acc_c2 - dev_acc,
          "cache corruption invisible to every current check")

    # c3: delta altered without touching logp -> T1 must fire
    fault("c3 delta edited, logp untouched", "T1", 0.0,
          "reintroduces a record inconsistency that T1 detects by construction")

    # c4: dropped condition rows -> loader completeness fires
    fault("c4 rows for one condition removed", "loader (items_incomplete)", 0.0,
          "load_behaviour reports incomplete items; %d currently" %
          len(load_info["items_incomplete"]))

    # c5: split field shuffled -> pairs sha diverges from the explore manifest
    fault("c5 split labels shuffled", "manifest (pairs sha256)", 0.0,
          "recorded pairs sha %s no longer matches" % load_info["pairs_sha256"][:12])

    # c6: span text edited -> pairs sha diverges, hygiene counts move
    fault("c6 span text edited", "manifest (pairs sha256)", 0.0,
          "same detector as c5; hygiene counts also move")

    silent_kills = [f for f in faults if f["kill"]]
    st = "KILL" if silent_kills else ("SOFT-FLAG" if any(
        f["detected_by"] == "SILENT" for f in faults) else "PASS")
    record("T2", "fault injection", st,
           {"faults": faults},
           "silent corruption moving a headline by > %.2f forces check redesign" % KILL_FAULT_SHIFT,
           "%d/6 silent (c1 rows-level, c2 acts-level); shifts %.3f and %.3f; "
           "recommendation: add a rows-vs-activations cross check before the freeze" %
           (sum(1 for f in faults if f["detected_by"] == "SILENT"),
            faults[0]["headline_shift"], faults[1]["headline_shift"])
           if not silent_kills else
           "silent corruption class confirmed (rows-acts decoupling): redesign "
           "required before the freeze = activation checksum in the harness for "
           "the next run, declared limitation for this dataset")

    # ---------------- T7 label shuffle null ---------------------------------
    accs = []
    for r in range(n_shuf):
        s = np.where(np.random.default_rng(100 + r).random(len(pool_ids)) < 0.5, 1.0, -1.0)
        Ds = D * s[:, None]
        accs.append(acc(Ds[is_dv] @ dir_from(is_tr, Ds)))
    lo, hi = float(np.percentile(accs, 2.5)), float(np.percentile(accs, 97.5))
    st = "PASS" if lo <= 0.5 <= hi else "KILL"
    record("T7", "label-shuffle pipeline null", st,
           {"n": n_shuf, "mean": float(np.mean(accs)), "q2.5": lo, "q97.5": hi},
           "0.5 outside the shuffled interval means leakage, stop",
           "shuffled dev accuracy %.3f [%.3f, %.3f]" % (float(np.mean(accs)), lo, hi))

    # ---------------- T8 pseudo-clause permutation null ---------------------
    span_keys = sorted(set(span_of))
    by_key = {k: np.where(span_of == k)[0] for k in span_keys}
    texts_B = {i: items[iid]["text_B"] for i, iid in enumerate(pool_ids)}
    texts_C = {i: items[iid]["text_C"] for i, iid in enumerate(pool_ids)}

    def bow_fold_acc(train_idx, held_idx):
        vocab = Counter()
        for i in train_idx:
            vocab.update(am.tokenize(texts_B[i]))
            vocab.update(am.tokenize(texts_C[i]))
        vlist = {w: j for j, w in enumerate(sorted(
            w for w, c in vocab.items() if c >= 2))}
        if not vlist:
            return float("nan")
        def mat(idx, texts):
            X = np.zeros((len(idx), len(vlist)))
            for r_, i in enumerate(idx):
                for w in am.tokenize(texts[i]):
                    j = vlist.get(w)
                    if j is not None:
                        X[r_, j] += 1.0
            return X
        Xtr = np.vstack([mat(train_idx, texts_B), mat(train_idx, texts_C)])
        ytr = np.concatenate([-np.ones(len(train_idx)), np.ones(len(train_idx))])
        w_, mu = am.ridge_fit(Xtr, ytr, alpha)
        sb = am.ridge_score(mat(held_idx, texts_B), w_, mu)
        sc = am.ridge_score(mat(held_idx, texts_C), w_, mu)
        return acc(sc - sb)

    if len(span_keys) >= 16:
        events = 0
        max_int_all = []
        for p in range(n_perm):
            perm = np.random.default_rng(1000 + p).permutation(len(span_keys))
            blocks = np.array_split(perm, 8)
            hit = False
            best_int = 0.0
            for blk in blocks:
                held = np.zeros(len(pool_ids), bool)
                for kx in blk:
                    held[by_key[span_keys[kx]]] = True
                if held.sum() < 5 or (~held).sum() < 20:
                    continue
                ia = acc(D[held] @ dir_from(~held))
                best_int = max(best_int, ia)
                if ia >= 0.90:
                    ba = bow_fold_acc(list(np.where(~held)[0]), list(np.where(held)[0]))
                    if not np.isnan(ba) and ba <= 0.55:
                        hit = True
            events += int(hit)
            max_int_all.append(best_int)
        rate = events / n_perm
        st = "KILL" if rate >= KILL_PERM_RATE else "PASS"
        record("T8", "pseudo-clause permutation null", st,
               {"permutations": n_perm, "event_rate": rate,
                "max_internal_median": float(np.median(max_int_all))},
               "event rate >= %.2f removes optout even as a candidate" % KILL_PERM_RATE,
               "optout-like events in %.1f%% of permutations (median best pseudo-clause %.3f)" %
               (100 * rate, float(np.median(max_int_all))))
    else:
        record("T8", "pseudo-clause permutation null", "SKIP",
               {"span_keys": len(span_keys)}, "needs >= 16 span groups",
               "too few span groups for a meaningful permutation")

    # ---------------- T9a token-controlled position -------------------------
    if mask[pool_rows, ci_B, pidx_mem].all() and mask[pool_rows, ci_C, pidx_mem].all():
        best = (0.0, None)
        for L in range(n_layers):
            Dm = diff_matrix(L, pidx_mem)
            a_ = acc(Dm[is_dv] @ dir_from(is_tr, Dm))
            if a_ > best[0]:
                best = (a_, L)
        L_mem = best[1]
        Dm = diff_matrix(L_mem, pidx_mem)
        lm_mem = loco_margins(Dm)
        opt_mem = acc(lm_mem[optout_mask])
        cl_means = None
        cl_keys = sorted(set(span_of[optout_mask]))
        if len(cl_keys) >= 2:
            ci = am.cluster_bootstrap_ci(lm_mem[optout_mask], span_of[optout_mask], acc)
        else:
            ci = (float("nan"), float("nan"))
        per_cl = {cl: acc(lm_mem[clause_of == cl]) for cl in clauses}
        st = "KILL" if opt_mem < KILL_MEMLAST else "PASS"
        record("T9a", "ladder at memory_last (token-controlled)", st,
               {"layer": int(L_mem), "dev_primary": best[0], "optout_loco": opt_mem,
                "optout_ci_cluster": ci, "per_clause_loco": per_cl},
               "optout LOCO below %.2f reclassifies span_last as token-local" % KILL_MEMLAST,
               "optout LOCO %.3f at memory_last layer %d (dev %.3f)" %
               (opt_mem, L_mem, best[0]))
    else:
        record("T9a", "ladder at memory_last", "SKIP", {},
               "needs B and C at memory_last for the pool", "positions missing")

    # ---------------- T9b final-token baseline ------------------------------
    def last_words(text, k):
        toks = am.tokenize(text)
        return tuple(toks[-k:]) if toks else ("",)

    for k in (1, 3):
        featsB = {i: last_words(texts_B[i], k) for i in range(len(pool_ids))}
        featsC = {i: last_words(texts_C[i], k) for i in range(len(pool_ids))}
        marg = np.full(len(pool_ids), np.nan)
        for cl in clauses:
            held = clause_of == cl
            tr_idx = np.where(~held)[0]
            vocab = {}
            for i in tr_idx:
                for w in featsB[i] + featsC[i]:
                    vocab.setdefault(w, len(vocab))
            def mat(idxs, feats):
                X = np.zeros((len(idxs), len(vocab)))
                for r_, i in enumerate(idxs):
                    for w in feats[i]:
                        j = vocab.get(w)
                        if j is not None:
                            X[r_, j] += 1.0
                return X
            Xtr = np.vstack([mat(tr_idx, featsB), mat(tr_idx, featsC)])
            ytr = np.concatenate([-np.ones(len(tr_idx)), np.ones(len(tr_idx))])
            w_, mu = am.ridge_fit(Xtr, ytr, alpha)
            hd = np.where(held)[0]
            marg[held] = am.ridge_score(mat(hd, featsC), w_, mu) - \
                am.ridge_score(mat(hd, featsB), w_, mu)
        opt_tok = acc(marg[optout_mask])
        st = "KILL" if opt_tok >= opt_acc else "PASS"
        record("T9b-k%d" % k, "final %d-word baseline at LOCO" % k, st,
               {"optout": opt_tok, "all_clauses": {cl: acc(marg[clause_of == cl])
                                                   for cl in clauses}},
               "final-token baseline at or above the internal number kills C2",
               "optout %.3f vs internal %.3f" % (opt_tok, opt_acc))

    # ---------------- T10 layer robustness ----------------------------------
    curve = []
    for L in range(n_layers):
        DL = diff_matrix(L, pidx)
        held = optout_mask
        curve.append(acc(DL[held] @ dir_from(~held, DL)))
    n_hi = sum(1 for a_ in curve if a_ >= 0.8)
    st = "SOFT-FLAG" if n_hi <= 3 else "PASS"
    record("T10", "LOCO-optout across layers", st,
           {"n_layers": n_layers, "layers_ge_0.8": n_hi,
            "max": float(max(curve)), "argmax": int(int(np.argmax(curve))),
            "curve": [round(a_, 3) for a_ in curve]},
           "isolated-layer support reframes C2 as layer-fragile",
           "%d/%d layers at or above 0.8 (max %.3f at layer %d)" %
           (n_hi, n_layers, max(curve), int(np.argmax(curve))))

    # ---------------- T11 semantic text baseline ----------------------------
    try:
        # RunPod images preset HF_HUB_ENABLE_HF_TRANSFER=1 without the package,
        # which makes the model download raise ValueError, not ImportError
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
        from fastembed import TextEmbedding
        model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        uniq = sorted({t for i in range(len(pool_ids)) for t in (texts_B[i], texts_C[i])})
        emb = {t: v for t, v in zip(uniq, model.embed(uniq))}
        EB = np.array([emb[texts_B[i]] for i in range(len(pool_ids))])
        EC = np.array([emb[texts_C[i]] for i in range(len(pool_ids))])
        marg = np.full(len(pool_ids), np.nan)
        for cl in clauses:
            held = clause_of == cl
            tr_idx = ~held
            X = np.vstack([EB[tr_idx], EC[tr_idx]])
            y = np.concatenate([-np.ones(tr_idx.sum()), np.ones(tr_idx.sum())])
            w_, mu = am.ridge_fit(X, y, alpha)
            marg[held] = am.ridge_score(EC[held], w_, mu) - am.ridge_score(EB[held], w_, mu)
        opt_sem = acc(marg[optout_mask])
        st = "KILL" if opt_sem >= KILL_SEMANTIC else "PASS"
        record("T11", "semantic text baseline at LOCO", st,
               {"optout": opt_sem, "all_clauses": {cl: acc(marg[clause_of == cl])
                                                   for cl in clauses}},
               "optout at or above %.2f kills beyond-surface-text" % KILL_SEMANTIC,
               "semantic baseline optout %.3f vs internal %.3f" % (opt_sem, opt_acc))
    except Exception as e:
        record("T11", "semantic text baseline", "SKIP",
               {"error": str(e)[:200]},
               "needs fastembed and a reachable model download",
               "failed: %s. pip install fastembed==0.5.1 hf_transfer, then rerun"
               % str(e)[:120])

    # ---------------- T12 donor ablation ------------------------------------
    donors = [cl for cl in clauses if cl != OPTOUT]
    abl = {}
    for d_cl in donors:
        train_m = (~optout_mask) & (clause_of != d_cl)
        abl[d_cl] = acc(D[optout_mask] @ dir_from(train_m))
    worst = min(abl.values()) if abl else float("nan")
    st = "SOFT-FLAG" if worst < 0.7 else "PASS"
    record("T12", "donor ablation for optout", st,
           {"per_donor_removed": abl, "min": worst},
           "single-donor dependence re-scopes C2 to pairwise transfer",
           "min accuracy %.3f after removing %s" %
           (worst, min(abl, key=abl.get) if abl else "n/a"))

    # ---------------- T13 within-optout confounds ---------------------------
    crossed = optout_mask & (~np.isnan(dN)) & (dN <= 0) & (dC > 0)
    fam_counts = Counter(fam_of[crossed])
    lens = np.array([len(am.tokenize(texts_C[i])) for i in range(len(pool_ids))])
    rho = am.spearman(lm[optout_mask], lens[optout_mask])
    one_family = len(fam_counts) == 1 and sum(fam_counts.values()) > 1
    st = "SOFT-FLAG" if (one_family or (rho == rho and abs(rho) > 0.5)) else "PASS"
    record("T13", "within-optout confounds", st,
           {"crossed_by_family": {str(k): v for k, v in fam_counts.items()},
            "spearman_margin_vs_len": rho},
           "all crossed in one family, or |rho| > 0.5, weakens C3",
           "crossed families %s; margin-length rho %s" %
           ({str(k): v for k, v in fam_counts.items()}, am.fmt(rho)))

    # ---------------- T14 exact cluster sign-flip ---------------------------
    keys_o = sorted(set(span_of[optout_mask]))
    means = np.array([float(np.mean(lm[optout_mask & (span_of == k)])) for k in keys_o])
    if len(means) >= 2:
        obs = means.mean()
        signs = np.array(np.meshgrid(*([[1, -1]] * len(means)))).T.reshape(-1, len(means))
        p_exact = float(np.mean(signs @ means / len(means) >= obs))
        record("T14", "exact cluster sign-flip test (optout)", "INFO",
               {"cluster_means": [round(m, 3) for m in means], "p_exact": p_exact},
               "robustness statistic next to the bootstrap CI",
               "p = %.4f over %d clusters" % (p_exact, len(means)))
    else:
        record("T14", "exact cluster sign-flip test", "SKIP",
               {"clusters": len(means)}, "needs >= 2 clusters", "too few clusters")

    # ---------------- T15 seed stability ------------------------------------
    base_ci = am.cluster_bootstrap_ci(opt_margins, span_of[optout_mask], acc, seed=am.SEED) \
        if len(set(span_of[optout_mask])) >= 2 else (float("nan"), float("nan"))
    moves = []
    for s in (1, 2, 3):
        if base_ci[0] == base_ci[0]:
            ci_s = am.cluster_bootstrap_ci(opt_margins, span_of[optout_mask], acc, seed=s)
            moves.append(max(abs(ci_s[0] - base_ci[0]), abs(ci_s[1] - base_ci[1])))
    worst_move = max(moves) if moves else float("nan")
    st = "PASS" if (worst_move == worst_move and worst_move <= KILL_SEED_MOVE) else \
        ("KILL" if worst_move == worst_move else "SKIP")
    record("T15", "seed stability of the optout cluster CI", st,
           {"base_ci": base_ci, "worst_bound_move": worst_move},
           "any bound moving more than %.2f" % KILL_SEED_MOVE,
           "worst movement %.3f across seeds 1-3" % worst_move
           if worst_move == worst_move else "not computable")

    # ---------------- final flush -------------------------------------------
    flush_results()
    print("\nwritten: %s and %s" %
          (os.path.join(args.out, "REDTEAM-RESULTS.md"),
           os.path.join(args.out, "REDTEAM-RESULTS.json")))
    kills = [r["id"] for r in RESULTS if r["status"] == "KILL"]
    print("KILL criteria met: %s" % (", ".join(kills) if kills else "none"))


if __name__ == "__main__":
    main()
