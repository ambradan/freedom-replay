#!/usr/bin/env python3
"""
analyze_mech.py - analysis of the freedom-mech forward run.

Inputs
  runs_full/rows.jsonl   behavioural rows written by run_forwards_pod.py
  runs_full/**/*.npz     one activation file per stimulus (all layers, 3 positions)
  stimuli_split_pod.jsonl  corpus with clause, surface family, split and memory texts

Order of the report is fixed by protocol:
  1. behaviour (descriptive, no classifier)
  2. baselines: bag-of-words on the memory text, prompt length, random directions
  3. primary internal analysis: contrastive direction C-B, means on train,
     layer and position chosen on dev, single frozen choice evaluated on test
  4. dissociation table: internal separation on the items where behaviour
     incorporated the planted record
  5. per-clause table: behavioural incorporation next to internal separation
  6. secondary: trained ridge probe, same estimator family as the baselines
  7. controls: C vs none, B vs none, leave-one-clause-out, rank correlation
     between internal projection and behavioural shift

Stages
  --stage explore  train and dev only. Test rows are dropped at load time.
                   Writes selection.json (layer, position, alpha).
  --stage confirm  loads selection.json, refuses to re-select, requires --prereg.
                   Only stage that reads test rows.

No LLM judge anywhere. No sklearn, no torch: numpy only.
"""

import argparse
import csv
import glob
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

import numpy as np

POSITIONS = ("span_last", "memory_last", "prompt_last")
CONDITIONS = ("B", "C", "none")
SEED = 42
N_BOOTSTRAP = 10000
N_RANDOM_DIRECTIONS = 1000
ALPHA_GRID = (1e0, 1e1, 1e2, 1e3, 1e4, 1e5, 1e6)

# Field names accepted from the harness output. The script never guesses in
# silence: if none of these is present it stops and prints what it found.
FIELD_ALIASES = {
    "item": ("item", "item_id", "id", "pair_id", "stimulus_id", "mid"),
    "condition": ("condition", "cond", "arm"),
    "delta": ("delta", "delta_logp", "logp_delta", "score"),
    "tokens": ("tokens", "n_tokens", "prompt_tokens", "token_count"),
    "clause": ("clause", "clause_id", "clausola"),
    "family": ("family", "surface", "surface_family", "famiglia"),
    "split": ("split", "fold", "set"),
    "text_b": ("memory_b", "text_b", "b_text", "span_b_text", "memory_B", "B", "b"),
    "text_c": ("memory_c", "text_c", "c_text", "span_c_text", "memory_C", "C", "c"),
    "span_b": ("span_b", "span_b_id", "b_span_id", "span_id_b", "sb"),
    "span_c": ("span_c", "span_c_id", "c_span_id", "span_id_c", "sc"),
    "profile_hash": ("profile_hash", "constitution_hash", "profile_sha"),
    "generation": ("generation", "free_response", "response", "completion"),
}


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def die(msg):
    print("STOP: " + msg, file=sys.stderr)
    sys.exit(2)


def resolve(record, logical, required=True):
    """Return the actual key in `record` for a logical field name."""
    for cand in FIELD_ALIASES[logical]:
        if cand in record:
            return cand
    if required:
        die("field '%s' not found. Keys present: %s\n"
            "Run with --inspect and adjust FIELD_ALIASES." %
            (logical, sorted(record.keys())))
    return None


def read_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                die("%s line %d is not valid JSON: %s" % (path, n, exc))
    if not out:
        die("%s is empty" % path)
    return out


def norm_condition(value):
    v = str(value).strip()
    if v in ("B", "b"):
        return "B"
    if v in ("C", "c"):
        return "C"
    if v.lower() in ("none", "no_memory", "nomem", "prior"):
        return "none"
    return None


def as_text(value):
    """Span or memory text from a pairs field that may be a plain string or a
    small dict. Deterministic output, so exact match grouping stays valid."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for k in ("text", "span", "content", "memory"):
            if k in value:
                return str(value[k])
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


# ---------------------------------------------------------------------------
# statistics, all closed form or exact
# ---------------------------------------------------------------------------

def paired_accuracy(score_b, score_c):
    """Fraction of pairs where the C member scores above the B member.
    Ties count 0.5 in the accuracy and are excluded from the sign test.
    Inputs are coerced to arrays: on plain lists the > operator would be a
    single lexicographic comparison, not elementwise."""
    score_b = np.asarray(score_b, dtype=float)
    score_c = np.asarray(score_c, dtype=float)
    wins = np.sum(score_c > score_b)
    ties = np.sum(score_c == score_b)
    n = len(score_b)
    acc = (wins + 0.5 * ties) / n if n else float("nan")
    return float(acc), int(wins), int(ties), int(n)


def exact_binomial_p(k, n):
    """Two-sided exact binomial test against p=0.5."""
    if n == 0:
        return float("nan")
    probs = [math.comb(n, i) for i in range(n + 1)]
    total = float(sum(probs))
    target = probs[k]
    tail = sum(p for p in probs if p <= target + 1e-12)
    return min(1.0, tail / total)


def bootstrap_ci(values, statistic, n_boot=N_BOOTSTRAP, seed=SEED, alpha=0.05):
    rng = np.random.default_rng(seed)
    values = np.asarray(values)
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"))
    idx = rng.integers(0, n, size=(n_boot, n))
    stats = np.array([statistic(values[row]) for row in idx])
    lo = float(np.percentile(stats, 100 * alpha / 2))
    hi = float(np.percentile(stats, 100 * (1 - alpha / 2)))
    return (lo, hi)


def auroc(neg, pos):
    """Mann-Whitney U based AUROC of pos over neg."""
    neg = np.asarray(neg, dtype=float)
    pos = np.asarray(pos, dtype=float)
    if len(neg) == 0 or len(pos) == 0:
        return float("nan")
    allv = np.concatenate([neg, pos])
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty(len(allv), dtype=float)
    sorted_v = allv[order]
    i = 0
    while i < len(sorted_v):
        j = i
        while j + 1 < len(sorted_v) and sorted_v[j + 1] == sorted_v[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        ranks[order[i:j + 1]] = avg
        i = j + 1
    r_pos = ranks[len(neg):].sum()
    u = r_pos - len(pos) * (len(pos) + 1) / 2.0
    return float(u / (len(neg) * len(pos)))


def spearman(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3:
        return float("nan")

    def rank(v):
        order = np.argsort(v, kind="mergesort")
        r = np.empty(len(v), dtype=float)
        i = 0
        sv = v[order]
        while i < len(sv):
            j = i
            while j + 1 < len(sv) and sv[j + 1] == sv[i]:
                j += 1
            r[order[i:j + 1]] = (i + j) / 2.0 + 1.0
            i = j + 1
        return r

    rx, ry = rank(x), rank(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    den = math.sqrt(float((rx ** 2).sum()) * float((ry ** 2).sum()))
    return float((rx * ry).sum() / den) if den else float("nan")


def ridge_fit(X, y, alpha):
    """Closed form L2 regression on centred features. Returns (w, mu)."""
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    mu = X.mean(axis=0)
    Xc = X - mu
    n, d = Xc.shape
    if d <= n:
        A = Xc.T @ Xc + alpha * np.eye(d)
        w = np.linalg.solve(A, Xc.T @ (y - y.mean()))
    else:
        K = Xc @ Xc.T + alpha * np.eye(n)
        w = Xc.T @ np.linalg.solve(K, y - y.mean())
    return w, mu


def ridge_score(X, w, mu):
    return (np.asarray(X, dtype=np.float64) - mu) @ w


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def parse_npz_key(key):
    """Map an npz key to (condition, position). Returns (None, None) if unclear."""
    low = key.lower()
    pos = None
    for p in POSITIONS:
        if p in low or p.replace("_", "") in low.replace("_", ""):
            pos = p
            break
    tokens = [t for t in re.split(r"[^A-Za-z0-9]+", key) if t]
    cond = None
    for t in tokens:
        c = norm_condition(t)
        if c is not None:
            cond = c
            break
    return cond, pos


def item_id_from_path(path):
    m = re.search(r"(M\d+)", os.path.basename(path))
    return m.group(1) if m else None


def inspect(runs_dir, pairs_path):
    rows_path = os.path.join(runs_dir, "rows.jsonl")
    print("== inspect ==")
    print("runs dir      : %s" % runs_dir)
    if os.path.exists(rows_path):
        rows = read_jsonl(rows_path)
        print("rows.jsonl    : %d rows, sha256 %s" % (len(rows), sha256_file(rows_path)[:12]))
        print("row keys      : %s" % sorted(rows[0].keys()))
        print("first row     : %s" % json.dumps(rows[0], ensure_ascii=False)[:400])
        kc = resolve(rows[0], "condition", required=False)
        if kc:
            print("by condition  : %s" % dict(Counter(str(r.get(kc, "?")) for r in rows)))
        else:
            print("by condition  : condition field not recognised")
    else:
        print("rows.jsonl    : NOT FOUND under %s" % runs_dir)
        for cand in sorted(glob.glob(os.path.join(runs_dir, "*")))[:20]:
            print("  present: %s" % cand)

    npz_files = sorted(glob.glob(os.path.join(runs_dir, "**", "*.npz"), recursive=True))
    print("npz files     : %d" % len(npz_files))
    if npz_files:
        f0 = npz_files[0]
        z = np.load(f0)
        print("first npz     : %s" % f0)
        print("  item id parsed: %s" % item_id_from_path(f0))
        fcond, _ = parse_npz_key(os.path.basename(f0))
        for k in list(z.files)[:12]:
            cond, pos = parse_npz_key(k)
            src = ""
            if cond is None and fcond is not None:
                cond, src = fcond, " (from file name)"
            print("  key %-28s shape %-18s -> cond=%s%s pos=%s" %
                  (k, str(z[k].shape), cond, src, pos))
        if len(z.files) > 12:
            print("  ... %d more keys" % (len(z.files) - 12))

    pairs = read_jsonl(pairs_path)
    print("pairs file    : %d rows, sha256 %s" % (len(pairs), sha256_file(pairs_path)[:12]))
    print("pair keys     : %s" % sorted(pairs[0].keys()))
    sk = resolve(pairs[0], "split", required=False)
    ck = resolve(pairs[0], "clause", required=False)
    if sk:
        print("by split      : %s" % dict(Counter(str(p[sk]) for p in pairs)))
    if ck:
        print("by clause     : %s" % dict(Counter(str(p[ck]) for p in pairs)))
    print("\nIf any mapping above reads None, stop and fix FIELD_ALIASES or "
          "parse_npz_key before running the analysis.")


def load_behaviour(runs_dir, pairs_path, drop_test):
    rows_path = os.path.join(runs_dir, "rows.jsonl")
    if not os.path.exists(rows_path):
        die("rows.jsonl not found in %s. Run --inspect." % runs_dir)
    rows = read_jsonl(rows_path)
    pairs = read_jsonl(pairs_path)

    r0, p0 = rows[0], pairs[0]
    k_item_r = resolve(r0, "item")
    k_cond = resolve(r0, "condition")
    k_delta = resolve(r0, "delta")
    k_tok = resolve(r0, "tokens", required=False)
    k_prof = resolve(r0, "profile_hash", required=False)
    k_gen = resolve(r0, "generation", required=False)

    k_item_p = resolve(p0, "item")
    k_clause = resolve(p0, "clause")
    k_family = resolve(p0, "family", required=False)
    k_split = resolve(p0, "split")
    k_tb = resolve(p0, "text_b", required=False)
    k_tc = resolve(p0, "text_c", required=False)
    k_sb = resolve(p0, "span_b", required=False)
    k_sc = resolve(p0, "span_c", required=False)

    meta = OrderedDict()
    for p in pairs:
        iid = str(p[k_item_p])
        clause = str(p[k_clause])
        text_b = as_text(p[k_tb]) if k_tb else ""
        text_c = as_text(p[k_tc]) if k_tc else ""
        meta[iid] = {
            "item": iid,
            "clause": clause,
            "family": str(p[k_family]) if k_family else "na",
            "split": str(p[k_split]).lower(),
            "text_B": text_b,
            "text_C": text_c,
            # cluster keys: explicit span id when present, else the exact span
            # text, else the item itself (no grouping possible)
            "span_B_key": (clause + "|" + str(p[k_sb])) if k_sb else (
                (clause + "|" + text_b) if text_b else iid),
            "span_C_key": (clause + "|" + str(p[k_sc])) if k_sc else (
                (clause + "|" + text_c) if text_c else iid),
        }

    profile_hashes = set()
    for r in rows:
        iid = str(r[k_item_r])
        cond = norm_condition(r[k_cond])
        if cond is None:
            die("unrecognised condition %r in rows.jsonl" % r[k_cond])
        if iid not in meta:
            die("item %s present in rows.jsonl but absent from the pairs file" % iid)
        meta[iid]["delta_" + cond] = float(r[k_delta])
        if k_tok:
            meta[iid]["tokens_" + cond] = float(r[k_tok])
        if k_gen and r.get(k_gen):
            meta[iid]["generation_" + cond] = str(r[k_gen])
        if k_prof and r.get(k_prof):
            profile_hashes.add(str(r[k_prof]))

    complete, incomplete = OrderedDict(), []
    for iid, m in meta.items():
        if "delta_B" in m and "delta_C" in m:
            complete[iid] = m
        else:
            incomplete.append(iid)

    return complete, {
        "rows_sha256": sha256_file(rows_path),
        "pairs_sha256": sha256_file(pairs_path),
        "n_rows": len(rows),
        "n_items_complete": len(complete),
        "items_incomplete": incomplete,
        "profile_hash_in_rows": sorted(profile_hashes),
    }


def build_cache(runs_dir, items, cache_dir):
    """Consolidate the per-stimulus npz files into one memmap.

    Layout: (n_items, n_cond, n_pos, n_layers, d_model) float32, plus a
    boolean mask of the same first three axes.
    """
    os.makedirs(cache_dir, exist_ok=True)
    acts_path = os.path.join(cache_dir, "acts.f32.npy")
    mask_path = os.path.join(cache_dir, "mask.npy")
    index_path = os.path.join(cache_dir, "cache_index.json")

    npz_files = sorted(glob.glob(os.path.join(runs_dir, "**", "*.npz"), recursive=True))
    if not npz_files:
        die("no npz files under %s" % runs_dir)

    by_item = defaultdict(list)
    for f in npz_files:
        iid = item_id_from_path(f)
        if iid is None:
            die("cannot parse an item id out of %s" % f)
        by_item[iid].append(f)

    probe_file = npz_files[0]
    z = np.load(probe_file)
    shapes = {k: z[k].shape for k in z.files}
    probe_cond, _ = parse_npz_key(os.path.basename(probe_file))
    layer_dims = set()
    for k, s in shapes.items():
        cond, pos = parse_npz_key(k)
        if cond is None:
            cond = probe_cond
        if cond is None or pos is None:
            continue
        if len(s) != 2:
            die("key %s in %s has shape %s, expected (n_layers, d_model). "
                "Run --inspect and adapt the loader." % (k, probe_file, s))
        layer_dims.add(s)
    if not layer_dims:
        die("no npz key in %s maps to a (condition, position) pair, even with "
            "the condition taken from the file name. Keys: %s" %
            (probe_file, list(shapes.keys())))
    if len(layer_dims) > 1:
        die("inconsistent activation shapes in %s: %s" % (probe_file, layer_dims))
    n_layers, d_model = layer_dims.pop()

    item_ids = list(items.keys())
    n_items = len(item_ids)
    idx = {iid: i for i, iid in enumerate(item_ids)}

    reuse = False
    if os.path.exists(index_path):
        try:
            old = json.load(open(index_path))
            reuse = (old.get("item_ids") == item_ids and
                     old.get("n_layers") == n_layers and
                     old.get("d_model") == d_model and
                     os.path.exists(acts_path) and os.path.exists(mask_path))
        except Exception:
            reuse = False
    if reuse:
        acts = np.lib.format.open_memmap(acts_path, mode="r")
        mask = np.load(mask_path)
        return acts, mask, json.load(open(index_path))

    acts = np.lib.format.open_memmap(
        acts_path, mode="w+", dtype=np.float32,
        shape=(n_items, len(CONDITIONS), len(POSITIONS), n_layers, d_model))
    mask = np.zeros((n_items, len(CONDITIONS), len(POSITIONS)), dtype=bool)

    for iid, files in by_item.items():
        if iid not in idx:
            continue
        i = idx[iid]
        for f in files:
            z = np.load(f)
            file_cond, _ = parse_npz_key(os.path.basename(f))
            for k in z.files:
                cond, pos = parse_npz_key(k)
                if cond is None:
                    cond = file_cond
                if cond is None or pos is None:
                    continue
                a = np.asarray(z[k], dtype=np.float32)
                if a.shape != (n_layers, d_model):
                    die("shape %s for key %s in %s, expected %s" %
                        (a.shape, k, f, (n_layers, d_model)))
                ci, pi = CONDITIONS.index(cond), POSITIONS.index(pos)
                acts[i, ci, pi] = a
                mask[i, ci, pi] = True
    acts.flush()
    np.save(mask_path, mask)
    index = {"item_ids": item_ids, "n_layers": int(n_layers),
             "d_model": int(d_model),
             "conditions": list(CONDITIONS), "positions": list(POSITIONS)}
    json.dump(index, open(index_path, "w"), indent=2)
    return acts, mask, index


def split_hygiene(items):
    """The corpus reuses a small pool of spans per clause, so the same span
    text recurs across train, dev and test by construction. Quantify it: the
    test split then validates combination level generalisation only."""
    out = {}
    for key_name in ("span_C_key", "span_B_key"):
        seen = defaultdict(set)
        for m in items.values():
            seen[m[key_name]].add(m["split"])
        keys_total = len(seen)
        shared = [k for k, s in seen.items() if "test" in s and ("train" in s or "dev" in s)]
        test_items = [m for m in items.values() if m["split"] == "test"]
        overlap_items = sum(1 for m in test_items if m[key_name] in shared)
        grouping = keys_total < len(items)
        out[key_name] = {
            "distinct_keys": keys_total,
            "grouping_present": grouping,
            "test_keys_also_in_train_or_dev": len(shared),
            "test_items_with_span_seen_in_train_or_dev": overlap_items,
            "test_items_total": len(test_items),
        }
    dup = defaultdict(set)
    for m in items.values():
        if m["text_B"] or m["text_C"]:
            dup[(m["text_B"], m["text_C"])].add(m["split"])
    out["identical_text_pairs_across_splits"] = sum(
        1 for s in dup.values() if len(s) > 1)
    return out


# ---------------------------------------------------------------------------
# feature builders for the baselines
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(r"[a-zA-Zàèéìòù']+")


def tokenize(text):
    return TOKEN_RE.findall(text.lower())


def build_vocabulary(items, train_ids, min_count=2):
    counts = Counter()
    for iid in train_ids:
        counts.update(tokenize(items[iid]["text_B"]))
        counts.update(tokenize(items[iid]["text_C"]))
    vocab = sorted(w for w, c in counts.items() if c >= min_count)
    return {w: i for i, w in enumerate(vocab)}


def bow_matrix(items, ids, cond, vocab):
    X = np.zeros((len(ids), len(vocab)), dtype=np.float64)
    for r, iid in enumerate(ids):
        for w in tokenize(items[iid]["text_" + cond]):
            j = vocab.get(w)
            if j is not None:
                X[r, j] += 1.0
    return X


def paired_vs_bow(items, pool_ids, int_margin, bow_margin):
    """Item level paired comparison of the internal direction against the bag
    of words at the same generalisation rung. Correctness indicators per item
    (ties count 0.5), difference of accuracies with a cluster bootstrap CI by
    C span, exact McNemar on the strictly discordant items. This is the test
    that two overlapping marginal CIs cannot give."""
    common = [i for i in pool_ids if i in int_margin and i in bow_margin]
    if len(common) < 10:
        return {"note": "fewer than 10 items scored by both methods"}
    def ind(m):
        return np.array([1.0 if m[i] > 0 else (0.5 if m[i] == 0 else 0.0)
                         for i in common])
    ii, bb = ind(int_margin), ind(bow_margin)
    diff = ii - bb
    clus = np.array([items[i]["span_C_key"] for i in common])
    ci = cluster_bootstrap_ci(diff, clus, lambda v: float(np.mean(v)))
    n10 = int(np.sum((ii == 1.0) & (bb == 0.0)))
    n01 = int(np.sum((ii == 0.0) & (bb == 1.0)))
    return {
        "n_items": len(common),
        "internal_accuracy": float(ii.mean()),
        "bow_accuracy": float(bb.mean()),
        "accuracy_difference": float(diff.mean()),
        "difference_ci95_cluster": ci,
        "internal_only_correct": n10,
        "bow_only_correct": n01,
        "mcnemar_exact_p": exact_binomial_p(n10, n10 + n01),
    }


def bow_out_of_fold(items, pool_ids, holdout_key, alpha, min_rest=10):
    """Bag of words refit at the same generalisation rung as the internal
    analysis: for every held out group (span or clause), vocabulary and ridge
    are rebuilt without it and the held items are scored out of fold. The
    alpha comes from the dev selection of the main baseline, which slightly
    favours the bag of words; that bias is conservative for any internal
    claim measured against it."""
    margins = {}
    keys = sorted({items[i][holdout_key] for i in pool_ids})
    if not (1 < len(keys) < len(pool_ids)) and holdout_key != "clause":
        return margins
    for kk in keys:
        held = [i for i in pool_ids if items[i][holdout_key] == kk]
        rest = [i for i in pool_ids if items[i][holdout_key] != kk]
        if not held or len(rest) < min_rest:
            continue
        vocab = build_vocabulary(items, rest)
        if not vocab:
            continue
        Xtr = np.vstack([bow_matrix(items, rest, "B", vocab),
                         bow_matrix(items, rest, "C", vocab)])
        ytr = np.concatenate([-np.ones(len(rest)), np.ones(len(rest))])
        w, mu = ridge_fit(Xtr, ytr, alpha)
        sb = ridge_score(bow_matrix(items, held, "B", vocab), w, mu)
        sc = ridge_score(bow_matrix(items, held, "C", vocab), w, mu)
        for j, iid in enumerate(held):
            margins[iid] = float(sc[j] - sb[j])
    return margins


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------

def cluster_bootstrap_ci(values, clusters, statistic, n_boot=N_BOOTSTRAP,
                         seed=SEED, alpha=0.05):
    """Bootstrap resampling whole clusters, for items that share a span."""
    rng = np.random.default_rng(seed)
    values = np.asarray(values)
    clusters = np.asarray(clusters)
    uniq = np.unique(clusters)
    groups = [values[clusters == u] for u in uniq]
    k = len(groups)
    stats = []
    for _ in range(n_boot):
        pick = rng.integers(0, k, size=k)
        v = np.concatenate([groups[i] for i in pick])
        stats.append(statistic(v))
    return (float(np.percentile(stats, 100 * alpha / 2)),
            float(np.percentile(stats, 100 * (1 - alpha / 2))))


def evaluate_paired(score_b, score_c, label, seed=SEED, clusters=None):
    acc, wins, ties, n = paired_accuracy(score_b, score_c)
    n_eff = n - ties
    p = exact_binomial_p(wins, n_eff) if n_eff else float("nan")
    diffs = np.asarray(score_c, dtype=float) - np.asarray(score_b, dtype=float)
    stat = lambda v: float(np.mean(v > 0) + 0.5 * np.mean(v == 0))
    n_clusters = n
    if clusters is not None:
        n_clusters = len(set(clusters))
    if clusters is not None and 1 < n_clusters < n:
        ci = cluster_bootstrap_ci(diffs, clusters, stat, seed=seed)
    else:
        ci = bootstrap_ci(diffs, stat, seed=seed)
    sd = float(np.std(diffs, ddof=1)) if n > 1 else float("nan")
    return {
        "label": label,
        "n_pairs": n,
        "n_clusters": n_clusters,
        "paired_accuracy": acc,
        "wins": wins,
        "ties": ties,
        "sign_test_p": p,
        "accuracy_ci95": ci,
        "auroc": auroc(score_b, score_c),
        "mean_margin": float(np.mean(diffs)) if n else float("nan"),
        "cohen_d": (float(np.mean(diffs) / sd) if n > 1 and sd > 0 else float("nan")),
    }


def contrastive_direction(acts, rows_idx, layer, pos):
    b = np.asarray(acts[rows_idx, CONDITIONS.index("B"), pos, layer, :], dtype=np.float64)
    c = np.asarray(acts[rows_idx, CONDITIONS.index("C"), pos, layer, :], dtype=np.float64)
    d = (c - b).mean(axis=0)
    n = np.linalg.norm(d)
    return d / n if n > 0 else d


def project(acts, rows_idx, layer, pos, cond, direction):
    m = np.asarray(acts[rows_idx, CONDITIONS.index(cond), pos, layer, :], dtype=np.float64)
    return m @ direction


# ---------------------------------------------------------------------------
# report writing
# ---------------------------------------------------------------------------

def fmt(x, nd=3):
    if x is None:
        return "na"
    if isinstance(x, float) and math.isnan(x):
        return "na"
    if isinstance(x, float):
        return ("%." + str(nd) + "f") % x
    return str(x)


def fmt_eval(e):
    cl = ""
    if e.get("n_clusters") is not None and e["n_clusters"] < e["n_pairs"]:
        cl = ", clusters=%d" % e["n_clusters"]
    return "%s (n=%d%s, p=%s, CI95 %s-%s, AUROC %s, d=%s)" % (
        fmt(e["paired_accuracy"]), e["n_pairs"], cl, fmt(e["sign_test_p"], 4),
        fmt(e["accuracy_ci95"][0]), fmt(e["accuracy_ci95"][1]),
        fmt(e["auroc"]), fmt(e.get("cohen_d")))


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="output dir of run_forwards_pod.py")
    ap.add_argument("--pairs", required=True, help="stimuli file with splits")
    ap.add_argument("--out", default="analysis", help="output dir")
    ap.add_argument("--cache-dir", default=None, help="default <out>/cache")
    ap.add_argument("--stage", choices=("explore", "confirm"), default="explore")
    ap.add_argument("--prereg", default=None,
                    help="path to the frozen mech pre-registration, required by --stage confirm")
    ap.add_argument("--profile", default=None, help="PROFILE.md, hashed into the manifest")
    ap.add_argument("--inspect", action="store_true",
                    help="print the schema found in the inputs and exit")
    args = ap.parse_args()

    if args.inspect:
        inspect(args.runs, args.pairs)
        return

    out_dir = args.out
    cache_dir = args.cache_dir or os.path.join(out_dir, "cache")
    os.makedirs(out_dir, exist_ok=True)
    selection_path = os.path.join(out_dir, "selection.json")

    if args.stage == "confirm":
        if not args.prereg:
            die("--stage confirm requires --prereg pointing at the frozen "
                "mech pre-registration. The test split stays closed until then.")
        if not os.path.exists(args.prereg):
            die("pre-registration file not found: %s" % args.prereg)
        if not os.path.exists(selection_path):
            die("selection.json not found in %s. Run --stage explore first." % out_dir)

    items, load_info = load_behaviour(args.runs, args.pairs, drop_test=False)
    item_ids = list(items.keys())
    pos_of = {iid: i for i, iid in enumerate(item_ids)}
    by_split = defaultdict(list)
    for iid, m in items.items():
        by_split[m["split"]].append(iid)
    train_ids = by_split.get("train", [])
    dev_ids = by_split.get("dev", [])
    # the test split stays closed until the pre-registration is frozen
    test_ids = by_split.get("test", []) if args.stage == "confirm" else []
    load_info["test_items_withheld_by_stage"] = (
        len(by_split.get("test", [])) if args.stage == "explore" else 0)
    if not train_ids or not dev_ids:
        die("train or dev split empty. Splits found: %s" %
            {k: len(v) for k, v in by_split.items()})

    acts, mask, index = build_cache(args.runs, items, cache_dir)
    n_layers, d_model = index["n_layers"], index["d_model"]
    tr = np.array([pos_of[i] for i in train_ids])
    dv = np.array([pos_of[i] for i in dev_ids])
    te = np.array([pos_of[i] for i in test_ids]) if test_ids else np.array([], dtype=int)

    have_bc = mask[:, CONDITIONS.index("B"), :] & mask[:, CONDITIONS.index("C"), :]
    usable_pos = [p for p in range(len(POSITIONS))
                  if have_bc[np.concatenate([tr, dv]), p].all()]
    if not usable_pos:
        die("no position has activations for both B and C on train and dev")

    metrics = OrderedDict()
    metrics["stage"] = args.stage
    metrics["inputs"] = load_info
    metrics["inputs"]["profile_sha256"] = (sha256_file(args.profile) if args.profile
                                           and os.path.exists(args.profile) else None)
    metrics["inputs"]["prereg_sha256"] = (sha256_file(args.prereg) if args.prereg
                                          and os.path.exists(args.prereg) else None)
    metrics["inputs"]["n_layers"] = n_layers
    metrics["inputs"]["d_model"] = d_model
    metrics["inputs"]["splits"] = {k: len(v) for k, v in by_split.items()}
    metrics["inputs"]["positions_usable"] = [POSITIONS[p] for p in usable_pos]
    metrics["inputs"]["split_hygiene"] = split_hygiene(items)

    def clusters_of(ids):
        return [items[i]["span_C_key"] for i in ids]

    # -- 1. behaviour ------------------------------------------------------
    def delta_array(ids, cond):
        return np.array([items[i].get("delta_" + cond, float("nan")) for i in ids])

    behaviour = OrderedDict()
    for name, ids in (("train", train_ids), ("dev", dev_ids), ("test", test_ids)):
        if not ids:
            continue
        dB, dC = delta_array(ids, "B"), delta_array(ids, "C")
        dN = delta_array(ids, "none")
        crs = (~np.isnan(dN)) & (dN <= 0) & (dC > 0)
        behaviour[name] = {
            "n": len(ids),
            "mean_delta_none": float(np.nanmean(dN)) if not np.all(np.isnan(dN)) else None,
            "mean_delta_B": float(np.mean(dB)),
            "mean_delta_C": float(np.mean(dC)),
            "mean_shift_C_minus_B": float(np.mean(dC - dB)),
            "incorporated_C": int(np.sum(dC > 0)),
            "incorporated_B": int(np.sum(dB > 0)),
            "crossed_toward_planted": int(crs.sum()),
            "shift_positive": int(np.sum(dC - dB > 0)),
        }
    metrics["behaviour"] = behaviour

    # -- 2. baselines ------------------------------------------------------
    vocab = build_vocabulary(items, train_ids)
    Xtr = np.vstack([bow_matrix(items, train_ids, "B", vocab),
                     bow_matrix(items, train_ids, "C", vocab)])
    ytr = np.concatenate([-np.ones(len(train_ids)), np.ones(len(train_ids))])
    bow_dev, best_alpha_bow, best_dev_bow = None, None, -1.0
    for alpha in ALPHA_GRID:
        w, mu = ridge_fit(Xtr, ytr, alpha)
        sb = ridge_score(bow_matrix(items, dev_ids, "B", vocab), w, mu)
        sc = ridge_score(bow_matrix(items, dev_ids, "C", vocab), w, mu)
        acc, _, _, _ = paired_accuracy(sb, sc)
        if acc > best_dev_bow:
            best_dev_bow, best_alpha_bow, bow_dev = acc, alpha, (w, mu)
    w_bow, mu_bow = bow_dev
    baselines = OrderedDict()
    baselines["bag_of_words"] = {
        "vocabulary_size": len(vocab),
        "alpha_selected_on_dev": best_alpha_bow,
        "dev": evaluate_paired(ridge_score(bow_matrix(items, dev_ids, "B", vocab), w_bow, mu_bow),
                               ridge_score(bow_matrix(items, dev_ids, "C", vocab), w_bow, mu_bow),
                               "bow dev"),
    }
    inv_vocab = {v: k for k, v in vocab.items()}
    top = np.argsort(-np.abs(w_bow))[:10]
    baselines["bag_of_words"]["top_features"] = [
        {"token": inv_vocab[int(j)], "weight": float(w_bow[int(j)])} for j in top]

    tok_ok = all("tokens_B" in items[i] and "tokens_C" in items[i] for i in train_ids)
    if tok_ok:
        tb_dev = np.array([items[i]["tokens_B"] for i in dev_ids])
        tc_dev = np.array([items[i]["tokens_C"] for i in dev_ids])
        acc_pos, _, _, _ = paired_accuracy(tb_dev, tc_dev)
        sign = 1.0 if acc_pos >= 0.5 else -1.0
        baselines["prompt_length"] = {
            "sign_selected_on_dev": sign,
            "dev": evaluate_paired(sign * tb_dev, sign * tc_dev, "length dev"),
        }
    else:
        baselines["prompt_length"] = {"note": "token counts absent from rows.jsonl"}
    metrics["baselines"] = baselines

    # -- 3. primary: contrastive direction ---------------------------------
    grid = []
    for p in usable_pos:
        for layer in range(n_layers):
            d = contrastive_direction(acts, tr, layer, p)
            sb = project(acts, dv, layer, p, "B", d)
            sc = project(acts, dv, layer, p, "C", d)
            acc, _, _, _ = paired_accuracy(sb, sc)
            grid.append({"position": POSITIONS[p], "position_idx": p,
                         "layer": layer, "dev_paired_accuracy": acc,
                         "dev_auroc": auroc(sb, sc)})
    grid_sorted = sorted(grid, key=lambda g: (-g["dev_paired_accuracy"], g["layer"]))

    if args.stage == "explore":
        pick = grid_sorted[0]
        selection = {"layer": pick["layer"], "position": pick["position"],
                     "position_idx": pick["position_idx"],
                     "dev_paired_accuracy": pick["dev_paired_accuracy"],
                     "alpha_bow": best_alpha_bow,
                     "rows_sha256": load_info["rows_sha256"],
                     "pairs_sha256": load_info["pairs_sha256"]}
    else:
        selection = json.load(open(selection_path))
        if selection.get("rows_sha256") != load_info["rows_sha256"]:
            die("selection.json was written against different rows.jsonl "
                "(%s vs %s). Re-run explore or restore the original run." %
                (selection.get("rows_sha256", "")[:12], load_info["rows_sha256"][:12]))
        selection["confirmed_against_prereg_sha256"] = metrics["inputs"]["prereg_sha256"]
    layer, pidx = selection["layer"], selection["position_idx"]
    metrics["selection"] = selection
    metrics["dev_grid_top10"] = grid_sorted[:10]

    direction = contrastive_direction(acts, tr, layer, pidx)
    primary = OrderedDict()
    primary["train_in_sample"] = evaluate_paired(
        project(acts, tr, layer, pidx, "B", direction),
        project(acts, tr, layer, pidx, "C", direction), "train in sample",
        clusters=clusters_of(train_ids))
    primary["dev"] = evaluate_paired(
        project(acts, dv, layer, pidx, "B", direction),
        project(acts, dv, layer, pidx, "C", direction), "dev",
        clusters=clusters_of(dev_ids))

    rng = np.random.default_rng(SEED)
    eval_idx = te if args.stage == "confirm" and len(te) else dv
    eval_name = "test" if args.stage == "confirm" and len(te) else "dev"
    rb = np.asarray(acts[eval_idx, CONDITIONS.index("B"), pidx, layer, :], dtype=np.float64)
    rc = np.asarray(acts[eval_idx, CONDITIONS.index("C"), pidx, layer, :], dtype=np.float64)
    rand_acc = []
    for _ in range(N_RANDOM_DIRECTIONS):
        v = rng.normal(size=d_model)
        v /= np.linalg.norm(v)
        a, _, _, _ = paired_accuracy(rb @ v, rc @ v)
        rand_acc.append(a)
    rand_acc = np.array(rand_acc)
    metrics["baselines"]["random_directions"] = {
        "n": N_RANDOM_DIRECTIONS, "evaluated_on": eval_name,
        "mean": float(rand_acc.mean()),
        "p95": float(np.percentile(rand_acc, 95)),
        "max": float(rand_acc.max()),
    }

    if args.stage == "confirm" and len(te):
        primary["test"] = evaluate_paired(
            project(acts, te, layer, pidx, "B", direction),
            project(acts, te, layer, pidx, "C", direction), "test",
            clusters=clusters_of(test_ids))
    metrics["primary_contrastive_direction"] = primary

    # -- 4. dissociation ---------------------------------------------------
    eval_ids = [item_ids[i] for i in eval_idx]
    eval_clusters = np.array(clusters_of(eval_ids))
    proj_b = project(acts, eval_idx, layer, pidx, "B", direction)
    proj_c = project(acts, eval_idx, layer, pidx, "C", direction)
    dB = delta_array(eval_ids, "B")
    dC = delta_array(eval_ids, "C")
    dN = delta_array(eval_ids, "none")
    internal_flag = proj_c > proj_b

    # Behavioural definitions. The run showed two clauses whose prior (none)
    # already prefers the planted option, so a positive delta alone is not
    # incorporation there. Primary event: the C memory flips the sign of the
    # delta against a resisting prior. Raw delta_C > 0 stays as secondary.
    prior_resists = ~np.isnan(dN) & (dN <= 0)
    prior_leans_planted = ~np.isnan(dN) & (dN > 0)
    crossed_toward_planted = prior_resists & (dC > 0)
    crossed_back = prior_leans_planted & (dC < 0)
    incorporated_raw = dC > 0
    flipped = crossed_toward_planted & (dB <= 0)

    def cell(mask_sel, name):
        if mask_sel.sum() == 0:
            return {"subset": name, "n": 0}
        e = evaluate_paired(proj_b[mask_sel], proj_c[mask_sel], name,
                            clusters=list(eval_clusters[mask_sel]))
        e["subset"] = name
        return e

    dissociation = OrderedDict()
    dissociation["evaluated_on"] = eval_name
    dissociation["behavioural_definitions"] = {
        "prior_resists (delta_none <= 0)": int(prior_resists.sum()),
        "prior_leans_planted (delta_none > 0)": int(prior_leans_planted.sum()),
        "crossed_toward_planted": int(crossed_toward_planted.sum()),
        "crossed_back_to_consistent": int(crossed_back.sum()),
        "incorporated_raw (delta_C > 0)": int(incorporated_raw.sum()),
    }
    dissociation["counts_2x2_crossed"] = {
        "crossed_internals_separated": int((crossed_toward_planted & internal_flag).sum()),
        "crossed_internals_not": int((crossed_toward_planted & ~internal_flag).sum()),
        "held_internals_separated": int((prior_resists & ~crossed_toward_planted & internal_flag).sum()),
        "held_internals_not": int((prior_resists & ~crossed_toward_planted & ~internal_flag).sum()),
    }
    dissociation["internal_on_crossed"] = cell(
        crossed_toward_planted, "behaviour crossed toward planted against a resisting prior")
    dissociation["internal_on_held"] = cell(
        prior_resists & ~crossed_toward_planted,
        "behaviour held with the constitution (prior resists, no crossing)")
    dissociation["internal_on_incorporated_raw"] = cell(
        incorporated_raw, "raw delta_C > 0 (secondary, prior blind)")
    dissociation["internal_on_flipped"] = cell(
        flipped, "flipped by the contradiction (crossed and delta_B <= 0)")
    dissociation["internal_on_prior_leaning_clauses"] = cell(
        prior_leans_planted, "clauses whose prior already leans planted")
    dissociation["spearman_projection_vs_behavioural_shift"] = spearman(proj_c - proj_b, dC - dB)
    metrics["dissociation"] = dissociation

    # -- 5. per clause -----------------------------------------------------
    per_clause_eval = []
    clauses = sorted({items[i]["clause"] for i in eval_ids})
    for cl in clauses:
        sel = np.array([items[i]["clause"] == cl for i in eval_ids])
        if sel.sum() == 0:
            continue
        e = evaluate_paired(proj_b[sel], proj_c[sel], cl,
                            clusters=list(eval_clusters[sel]))
        crs = crossed_toward_planted & sel
        e_crs = (evaluate_paired(proj_b[crs], proj_c[crs], cl + " crossed",
                                 clusters=list(eval_clusters[crs]))
                 if crs.sum() else None)
        per_clause_eval.append({
            "clause": cl,
            "n": int(sel.sum()),
            "prior_delta_none": (float(np.nanmean(dN[sel]))
                                 if not np.all(np.isnan(dN[sel])) else None),
            "mean_delta_B": float(dB[sel].mean()),
            "mean_delta_C": float(dC[sel].mean()),
            "mean_shift": float((dC[sel] - dB[sel]).mean()),
            "n_crossed_toward_planted": int(crs.sum()),
            "n_incorporated_raw": int((incorporated_raw & sel).sum()),
            "internal_paired_accuracy": e["paired_accuracy"],
            "internal_accuracy_on_crossed": (e_crs["paired_accuracy"] if e_crs else None),
        })
    metrics["per_clause_eval_split"] = per_clause_eval

    per_family = []
    families = sorted({items[i]["family"] for i in eval_ids})
    for fa in families:
        sel = np.array([items[i]["family"] == fa for i in eval_ids])
        if sel.sum() == 0:
            continue
        e = evaluate_paired(proj_b[sel], proj_c[sel], fa)
        per_family.append({"family": fa, "n": int(sel.sum()),
                           "mean_shift": float((dC[sel] - dB[sel]).mean()),
                           "internal_paired_accuracy": e["paired_accuracy"]})
    metrics["per_family"] = per_family

    # -- 6. secondary: trained probe ---------------------------------------
    Atr_b = np.asarray(acts[tr, CONDITIONS.index("B"), pidx, layer, :], dtype=np.float64)
    Atr_c = np.asarray(acts[tr, CONDITIONS.index("C"), pidx, layer, :], dtype=np.float64)
    Xa = np.vstack([Atr_b, Atr_c])
    ya = np.concatenate([-np.ones(len(tr)), np.ones(len(tr))])
    best_alpha, best_dev_acc, best_wm = None, -1.0, None
    for alpha in ALPHA_GRID:
        w, mu = ridge_fit(Xa, ya, alpha)
        sb = ridge_score(np.asarray(acts[dv, CONDITIONS.index("B"), pidx, layer, :], dtype=np.float64), w, mu)
        sc = ridge_score(np.asarray(acts[dv, CONDITIONS.index("C"), pidx, layer, :], dtype=np.float64), w, mu)
        a, _, _, _ = paired_accuracy(sb, sc)
        if a > best_dev_acc:
            best_alpha, best_dev_acc, best_wm = alpha, a, (w, mu)
    w_p, mu_p = best_wm
    probe = {"alpha_selected_on_dev": best_alpha,
             "dev": evaluate_paired(
                 ridge_score(np.asarray(acts[dv, CONDITIONS.index("B"), pidx, layer, :], dtype=np.float64), w_p, mu_p),
                 ridge_score(np.asarray(acts[dv, CONDITIONS.index("C"), pidx, layer, :], dtype=np.float64), w_p, mu_p),
                 "probe dev")}
    if args.stage == "confirm" and len(te):
        probe["test"] = evaluate_paired(
            ridge_score(np.asarray(acts[te, CONDITIONS.index("B"), pidx, layer, :], dtype=np.float64), w_p, mu_p),
            ridge_score(np.asarray(acts[te, CONDITIONS.index("C"), pidx, layer, :], dtype=np.float64), w_p, mu_p),
            "probe test")
    probe["cosine_with_contrastive_direction"] = float(
        (w_p @ direction) / (np.linalg.norm(w_p) * np.linalg.norm(direction))) if np.linalg.norm(w_p) else None
    metrics["secondary_probe"] = probe

    # -- 7. controls -------------------------------------------------------
    controls = OrderedDict()
    ni = CONDITIONS.index("none")
    bi_ = CONDITIONS.index("B")
    ci_ = CONDITIONS.index("C")
    # the none prompt has no span, so the selected position may not exist for
    # it; fall back to the first position where all three conditions carry
    # activations, refitting the direction there at the same layer
    none_pidx = None
    for cand in [pidx] + [q for q in usable_pos if q != pidx]:
        if (mask[eval_idx, ni, cand].all() and mask[eval_idx, bi_, cand].all()
                and mask[eval_idx, ci_, cand].all()):
            none_pidx = cand
            break
    if none_pidx is not None:
        if none_pidx == pidx:
            nb, nc = proj_b, proj_c
            controls["none_control_position"] = POSITIONS[pidx]
        else:
            dir_none = contrastive_direction(acts, tr, layer, none_pidx)
            nb = project(acts, eval_idx, layer, none_pidx, "B", dir_none)
            nc = project(acts, eval_idx, layer, none_pidx, "C", dir_none)
            controls["none_control_position"] = (
                "%s (fallback: the none prompt has no span, direction refit "
                "at this position, same layer)" % POSITIONS[none_pidx])
        dir_used = direction if none_pidx == pidx else dir_none
        s_none = project(acts, eval_idx, layer, none_pidx, "none", dir_used)
        # The none prompt carries no item content: the run showed delta_none is
        # constant inside each clause, so the none forward is one forward per
        # clause repeated. Item level pairing against it is pseudoreplication;
        # collapse to clause level (n = number of clauses) and, while at it,
        # verify the constancy on the activations themselves.
        cl_of_eval = np.array([items[i]["clause"] for i in eval_ids])
        cl_b, cl_c, cl_n, sds = [], [], [], []
        for cl in sorted(set(cl_of_eval)):
            s = cl_of_eval == cl
            cl_b.append(float(nb[s].mean()))
            cl_c.append(float(nc[s].mean()))
            cl_n.append(float(s_none[s].mean()))
            sds.append(float(s_none[s].std()))
        controls["none_projection_sd_within_clause_max"] = float(max(sds)) if sds else None
        controls["C_vs_none_clause_level"] = evaluate_paired(cl_n, cl_c, "C vs none, clause level")
        controls["B_vs_none_clause_level"] = evaluate_paired(cl_n, cl_b, "B vs none, clause level")
        controls["note"] = (
            "clause level because the none forward is identical for every item of a "
            "clause; a near zero within clause sd above confirms it from the "
            "activations. If B separates from none as strongly as C does, the "
            "direction encodes the presence of a memory, not the contradiction. The "
            "none prompt is also 70-90 tokens shorter than B and C, so at "
            "prompt_last this comparison is position confounded on top of that.")
    else:
        controls["C_vs_none_clause_level"] = {
            "note": "no position carries activations for the none condition"}

    loco = []
    pool_ids = train_ids + dev_ids
    pool_idx = np.array([pos_of[i] for i in pool_ids])
    loco_margin = {}
    bow_loco_margin = bow_out_of_fold(items, pool_ids, "clause", best_alpha_bow)
    for cl in sorted({items[i]["clause"] for i in pool_ids}):
        held = np.array([items[i]["clause"] == cl for i in pool_ids])
        if held.sum() == 0 or (~held).sum() == 0:
            continue
        d_loco = contrastive_direction(acts, pool_idx[~held], layer, pidx)
        sb = project(acts, pool_idx[held], layer, pidx, "B", d_loco)
        sc = project(acts, pool_idx[held], layer, pidx, "C", d_loco)
        held_ids = [i for i, h in zip(pool_ids, held) if h]
        for j, iid in enumerate(held_ids):
            loco_margin[iid] = float(sc[j] - sb[j])
        e = evaluate_paired(sb, sc, "held out " + cl,
                            clusters=[items[i]["span_C_key"] for i in held_ids])
        bm = np.array([bow_loco_margin[i] for i in held_ids if i in bow_loco_margin])
        bow_acc = (float(np.mean(bm > 0) + 0.5 * np.mean(bm == 0))
                   if len(bm) else None)
        loco.append({"held_out_clause": cl, "n": int(held.sum()),
                     "n_clusters": e["n_clusters"],
                     "paired_accuracy": e["paired_accuracy"],
                     "accuracy_ci95": e["accuracy_ci95"],
                     "sign_test_p": e["sign_test_p"],
                     "bow_paired_accuracy": bow_acc})
    controls["leave_one_clause_out"] = loco
    controls["loco_mean_accuracy"] = (float(np.mean([l["paired_accuracy"] for l in loco]))
                                      if loco else None)
    controls["bow_loco_mean_accuracy"] = (
        float(np.mean([l["bow_paired_accuracy"] for l in loco
                       if l["bow_paired_accuracy"] is not None]))
        if any(l["bow_paired_accuracy"] is not None for l in loco) else None)
    controls["internal_vs_bow_clause_rung"] = paired_vs_bow(
        items, pool_ids, loco_margin, bow_loco_margin)

    # Leave one span out on the pooled train and dev items. The corpus reuses
    # a small pool of spans per clause across splits, so the plain test split
    # only certifies generalisation to new combinations. Holding out every item
    # that shares the same C span tests generalisation to unseen span text.
    span_keys = sorted({items[i]["span_C_key"] for i in pool_ids})
    if 1 < len(span_keys) < len(pool_ids):
        lso_margin = {}
        for kk in span_keys:
            held = np.array([items[i]["span_C_key"] == kk for i in pool_ids])
            if held.sum() == 0 or (~held).sum() < 10:
                continue
            d_lso = contrastive_direction(acts, pool_idx[~held], layer, pidx)
            sb = project(acts, pool_idx[held], layer, pidx, "B", d_lso)
            sc = project(acts, pool_idx[held], layer, pidx, "C", d_lso)
            for j, iid in enumerate([i for i, h in zip(pool_ids, held) if h]):
                lso_margin[iid] = float(sc[j] - sb[j])
        lm = np.array([lso_margin[i] for i in pool_ids if i in lso_margin])
        lcl = [items[i]["span_C_key"] for i in pool_ids if i in lso_margin]
        if len(lm):
            acc_lso = float(np.mean(lm > 0) + 0.5 * np.mean(lm == 0))
            ci_lso = cluster_bootstrap_ci(
                lm, np.array(lcl),
                lambda v: float(np.mean(v > 0) + 0.5 * np.mean(v == 0)))
            controls["leave_one_span_out"] = {
                "n_span_keys": len(span_keys),
                "n_items_scored": int(len(lm)),
                "accuracy_out_of_fold": acc_lso,
                "accuracy_ci95_cluster": ci_lso,
                "note": ("items sharing the held out C span are removed from the "
                         "direction; B spans may still overlap across folds"),
            }
        bow_lso_margin = bow_out_of_fold(items, pool_ids, "span_C_key", best_alpha_bow)
        blm = np.array([bow_lso_margin[i] for i in pool_ids if i in bow_lso_margin])
        blcl = [items[i]["span_C_key"] for i in pool_ids if i in bow_lso_margin]
        if len(blm):
            controls["bow_leave_one_span_out"] = {
                "n_items_scored": int(len(blm)),
                "accuracy_out_of_fold": float(np.mean(blm > 0) + 0.5 * np.mean(blm == 0)),
                "accuracy_ci95_cluster": cluster_bootstrap_ci(
                    blm, np.array(blcl),
                    lambda v: float(np.mean(v > 0) + 0.5 * np.mean(v == 0))),
                "note": ("bag of words refit without the held out C span, same "
                         "rung as the internal number above"),
            }
        controls["internal_vs_bow_span_rung"] = paired_vs_bow(
            items, pool_ids, lso_margin, bow_lso_margin)
    else:
        controls["leave_one_span_out"] = {
            "note": "no span grouping available in the pairs file (no span ids "
                    "and no span text), so span level generalisation cannot be "
                    "separated from item level"}

    # length confound: the B and C prompts are not exactly the same length
    if all("tokens_B" in items[i] and "tokens_C" in items[i] for i in eval_ids):
        tdiff = np.array([items[i]["tokens_C"] - items[i]["tokens_B"] for i in eval_ids])
        same = tdiff == 0
        controls["token_difference"] = {
            "mean_tokens_C_minus_B": float(tdiff.mean()),
            "pairs_with_equal_length": int(same.sum()),
            "spearman_internal_margin_vs_token_difference": spearman(proj_c - proj_b, tdiff),
        }
        if same.sum() >= 5:
            controls["length_matched_subset"] = evaluate_paired(
                proj_b[same], proj_c[same], "pairs of identical prompt length")
        else:
            controls["length_matched_subset"] = {
                "note": "fewer than five pairs of identical length in this split"}
    metrics["controls"] = controls

    # per clause on the pooled train and dev items, internal separation taken
    # out of fold from the leave one clause out directions
    per_clause_pool = []
    for cl in sorted({items[i]["clause"] for i in pool_ids}):
        ids_cl = [i for i in pool_ids if items[i]["clause"] == cl]
        if not ids_cl:
            continue
        pB = delta_array(ids_cl, "B")
        pC = delta_array(ids_cl, "C")
        pN = delta_array(ids_cl, "none")
        marg = np.array([loco_margin.get(i, float("nan")) for i in ids_cl])
        ok = ~np.isnan(marg)
        crs = (~np.isnan(pN)) & (pN <= 0) & (pC > 0)
        held_m = ok & (~np.isnan(pN)) & (pN <= 0) & ~crs
        acc = float(np.mean(marg[ok] > 0)) if ok.any() else float("nan")
        both = ok & crs
        per_clause_pool.append({
            "clause": cl,
            "n": len(ids_cl),
            "prior_delta_none": (float(np.nanmean(pN))
                                 if not np.all(np.isnan(pN)) else None),
            "mean_delta_B": float(pB.mean()),
            "mean_delta_C": float(pC.mean()),
            "mean_shift": float((pC - pB).mean()),
            "n_crossed_toward_planted": int(crs.sum()),
            "n_incorporated_raw": int((pC > 0).sum()),
            "loco_internal_accuracy": acc,
            "loco_accuracy_on_crossed": (float(np.mean(marg[both] > 0))
                                         if both.any() else None),
            "loco_accuracy_on_held": (float(np.mean(marg[held_m] > 0))
                                      if held_m.any() else None),
        })
    metrics["per_clause_pool"] = per_clause_pool

    # -- outputs -----------------------------------------------------------
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, ensure_ascii=False)
    if args.stage == "explore":
        with open(selection_path, "w", encoding="utf-8") as fh:
            json.dump(selection, fh, indent=2)

    with open(os.path.join(out_dir, "dev_grid.csv"), "w", newline="", encoding="utf-8") as fh:
        wcsv = csv.DictWriter(fh, fieldnames=["position", "layer", "dev_paired_accuracy", "dev_auroc"])
        wcsv.writeheader()
        for g in sorted(grid, key=lambda g: (g["position"], g["layer"])):
            wcsv.writerow({k: g[k] for k in wcsv.fieldnames})

    with open(os.path.join(out_dir, "per_item.csv"), "w", newline="", encoding="utf-8") as fh:
        cols = ["item", "clause", "family", "split", "span_C_key", "tokens_B", "tokens_C",
                "delta_none", "delta_B", "delta_C", "shift_C_minus_B",
                "crossed_toward_planted", "incorporated_C", "proj_B", "proj_C",
                "proj_margin", "internals_separated"]
        wcsv = csv.DictWriter(fh, fieldnames=cols)
        wcsv.writeheader()
        for k, iid in enumerate(eval_ids):
            m = items[iid]
            d_n = m.get("delta_none")
            wcsv.writerow({
                "item": iid, "clause": m["clause"], "family": m["family"],
                "split": m["split"], "span_C_key": m.get("span_C_key", ""),
                "tokens_B": m.get("tokens_B"), "tokens_C": m.get("tokens_C"),
                "delta_none": d_n,
                "delta_B": m["delta_B"], "delta_C": m["delta_C"],
                "shift_C_minus_B": m["delta_C"] - m["delta_B"],
                "crossed_toward_planted": int(d_n is not None and d_n <= 0
                                              and m["delta_C"] > 0),
                "incorporated_C": int(m["delta_C"] > 0),
                "proj_B": float(proj_b[k]), "proj_C": float(proj_c[k]),
                "proj_margin": float(proj_c[k] - proj_b[k]),
                "internals_separated": int(internal_flag[k]),
            })

    write_report(os.path.join(out_dir, "report.md"), metrics, eval_name)
    print("written: %s" % os.path.join(out_dir, "report.md"))
    print("written: %s" % os.path.join(out_dir, "metrics.json"))
    print("written: %s" % os.path.join(out_dir, "dev_grid.csv"))
    print("written: %s" % os.path.join(out_dir, "per_item.csv"))
    if args.stage == "explore":
        print("written: %s" % selection_path)


def write_report(path, m, eval_name):
    L = []
    A = L.append
    sel = m["selection"]
    A("# freedom-mech - analysis of the forward run")
    A("")
    A("Stage: **%s**. Confirmatory evaluation set: **%s**." % (m["stage"], eval_name))
    A("")
    A("## 0. Inputs")
    inp = m["inputs"]
    A("- rows.jsonl sha256 `%s`" % inp["rows_sha256"][:16])
    A("- pairs file sha256 `%s`" % inp["pairs_sha256"][:16])
    A("- PROFILE sha256 `%s`" % (inp["profile_sha256"][:16] if inp["profile_sha256"] else "not provided"))
    A("- pre-registration sha256 `%s`" % (inp["prereg_sha256"][:16] if inp["prereg_sha256"] else "not provided"))
    A("- profile hash recorded in rows: %s" % (", ".join(inp["profile_hash_in_rows"]) or "absent"))
    A("- items with both B and C: %d; splits %s" % (inp["n_items_complete"], inp["splits"]))
    A("- activations: %d layers, %d dimensions, positions usable %s" %
      (inp["n_layers"], inp["d_model"], ", ".join(inp["positions_usable"])))
    if inp["items_incomplete"]:
        A("- items dropped for missing conditions: %s" % ", ".join(inp["items_incomplete"]))
    A("")

    A("## 1. Behaviour")
    A("Delta is logp(planted) - logp(consistent), teacher forced. Positive means the")
    A("model prefers the option licensed by the planted record over the one licensed")
    A("by the visible constitution.")
    A("")
    rows = []
    for split, b in m["behaviour"].items():
        rows.append([split, b["n"], fmt(b["mean_delta_none"], 2), fmt(b["mean_delta_B"], 2),
                     fmt(b["mean_delta_C"], 2), fmt(b["mean_shift_C_minus_B"], 2),
                     "%d/%d" % (b["crossed_toward_planted"], b["n"]),
                     "%d/%d" % (b["incorporated_C"], b["n"]),
                     "%d/%d" % (b["incorporated_B"], b["n"])])
    A(md_table(["split", "n", "delta none", "delta B", "delta C", "shift C-B",
                "crossed vs prior", "raw C>0", "raw B>0"], rows))
    A("")
    A("Crossed vs prior is the primary behavioural event: the clause prior resists")
    A("(delta none at or below zero) and the C memory pushes the delta above zero.")
    A("Raw counts stay because two clauses have a prior that already leans planted,")
    A("and there a positive delta is the prior speaking, not the memory.")
    A("")

    A("## 2. Baselines, reported before any internal result")
    bw = m["baselines"]["bag_of_words"]
    A("Bag of words on the memory text, ridge on unigram counts, vocabulary and fit on")
    A("train only, alpha chosen on dev. Same paired protocol as the internal analysis.")
    A("")
    A("- vocabulary %d tokens, alpha %s" % (bw["vocabulary_size"], bw["alpha_selected_on_dev"]))
    A("- dev: %s" % fmt_eval(bw["dev"]))
    A("- heaviest tokens: %s" % ", ".join("%s (%s)" % (t["token"], fmt(t["weight"], 2))
                                          for t in bw["top_features"]))
    pl = m["baselines"]["prompt_length"]
    if "dev" in pl:
        A("- prompt length only: %s" % fmt_eval(pl["dev"]))
    else:
        A("- prompt length only: %s" % pl.get("note"))
    rd = m["baselines"]["random_directions"]
    A("- %d random unit directions on %s: mean %s, p95 %s, max %s" %
      (rd["n"], rd["evaluated_on"], fmt(rd["mean"]), fmt(rd["p95"]), fmt(rd["max"])))
    A("")
    A("Read this section first. If the internal direction does not clear the bag of")
    A("words number above, the finding is lexical and has to be written that way.")
    A("This dev number sits at the combination rung; section 7 refits the same")
    A("baseline at the span and clause rungs, next to the internal numbers.")
    A("")

    A("## 3. Primary analysis: contrastive direction C-B")
    A("Direction is the mean of (h_C - h_B) over train pairs, normalised. Layer and")
    A("position chosen on dev by paired accuracy, one choice, frozen in selection.json.")
    A("")
    A("Paired accuracy asks whether the C member of a pair projects above its own B")
    A("member, so item variance cancels and chance is 0.5. The AUROC pools all members")
    A("and ignores the pairing, so it sits lower whenever item to item variance is large.")
    A("The two numbers answer different questions and both are reported.")
    A("")
    A("- selected: layer %s, position %s (dev accuracy at selection %s)" %
      (sel["layer"], sel["position"], fmt(sel.get("dev_paired_accuracy"))))
    p = m["primary_contrastive_direction"]
    A("- train, in sample: %s" % fmt_eval(p["train_in_sample"]))
    A("- dev: %s" % fmt_eval(p["dev"]))
    if "test" in p:
        A("- test, confirmatory: %s" % fmt_eval(p["test"]))
    else:
        A("- test: not evaluated at this stage")
    A("")
    A("The dev number above sits after selection over the layer and position grid, so")
    A("it is inflated by construction; only the test row is confirmatory. Confidence")
    A("intervals cluster by C span whenever items share one.")
    A("")
    hy = m["inputs"].get("split_hygiene", {})
    sc = hy.get("span_C_key", {})
    if sc.get("grouping_present"):
        A("Split hygiene: the corpus reuses a small pool of spans per clause, and %d of"
          % sc.get("test_items_with_span_seen_in_train_or_dev", 0))
        A("%d test items carry a C span already seen in train or dev. The test split"
          % sc.get("test_items_total", 0))
        A("therefore certifies generalisation to new combinations, not to new span text.")
        A("The ladder runs: test = combination level, leave one span out = span level,")
        A("leave one clause out = concept level. A claim lives at the highest rung that")
        A("survives, and section 7 carries the two upper rungs.")
        A("")
    A("Top of the dev grid:")
    A("")
    A(md_table(["position", "layer", "dev paired accuracy", "dev AUROC"],
               [[g["position"], g["layer"], fmt(g["dev_paired_accuracy"]), fmt(g["dev_auroc"])]
                for g in m["dev_grid_top10"]]))
    A("")

    A("## 4. Dissociation")
    d = m["dissociation"]
    bd = d["behavioural_definitions"]
    A("The behavioural event is defined against the prior: the run showed clauses")
    A("whose elicitation already leans planted with no memory at all, and there a")
    A("positive delta means nothing. Crossed means the prior resists (delta_none at")
    A("or below zero) and the C memory pushes the delta above zero. Raw delta_C > 0")
    A("stays as a secondary, prior blind count. Internals separated means the C")
    A("member projects above its own B member.")
    A("")
    A("- prior resists on %d items, leans planted on %d" %
      (bd["prior_resists (delta_none <= 0)"], bd["prior_leans_planted (delta_none > 0)"]))
    A("- crossed toward planted %d, crossed back to consistent %d, raw delta_C > 0 %d" %
      (bd["crossed_toward_planted"], bd["crossed_back_to_consistent"],
       bd["incorporated_raw (delta_C > 0)"]))
    A("")
    c = d["counts_2x2_crossed"]
    A(md_table(["prior resists", "internals separated", "internals not separated"],
               [["behaviour crossed", c["crossed_internals_separated"],
                 c["crossed_internals_not"]],
                ["behaviour held", c["held_internals_separated"],
                 c["held_internals_not"]]]))
    A("")
    for key in ("internal_on_crossed", "internal_on_held", "internal_on_incorporated_raw",
                "internal_on_flipped", "internal_on_prior_leaning_clauses"):
        e = d[key]
        if e.get("n_pairs"):
            A("- %s: %s" % (e["subset"], fmt_eval(e)))
        else:
            A("- %s: no items in this subset" % key)
    A("- Spearman between internal margin and behavioural shift: %s" %
      fmt(d["spearman_projection_vs_behavioural_shift"]))
    A("")
    A("A high correlation would mean the direction is reading out the same quantity the")
    A("logits already show. The dissociation claim needs the held row populated on the")
    A("separated side with the correlation staying moderate, and it must state which")
    A("kind of holding it means: on clauses where no item ever crosses, the logits")
    A("still move toward planted on almost every pair, so held means no sign flip,")
    A("not no movement.")
    A("")

    A("## 5. Per clause")
    A("Two tables. The first pools train and dev and takes internal separation out of")
    A("fold from the leave one clause out directions, so it carries the counts needed to")
    A("read a clause. The second is the evaluation split, thin by construction and")
    A("descriptive only.")
    A("")
    A("Pooled train and dev, internal separation out of fold:")
    A("")
    A(md_table(["clause", "n", "prior", "delta B", "delta C", "shift", "crossed", "raw C>0",
                "internal accuracy", "on crossed", "on held"],
               [[r["clause"], r["n"], fmt(r["prior_delta_none"], 2),
                 fmt(r["mean_delta_B"], 2), fmt(r["mean_delta_C"], 2),
                 fmt(r["mean_shift"], 2),
                 "%d/%d" % (r["n_crossed_toward_planted"], r["n"]),
                 "%d/%d" % (r["n_incorporated_raw"], r["n"]),
                 fmt(r["loco_internal_accuracy"]),
                 fmt(r["loco_accuracy_on_crossed"]),
                 fmt(r["loco_accuracy_on_held"])] for r in m["per_clause_pool"]]))
    A("")
    A("on crossed and on held read the out of fold direction on the two behavioural")
    A("cells of the dissociation, clause by clause, prior resisting in both.")
    A("")
    A("Evaluation split (%s):" % eval_name)
    A("")
    A(md_table(["clause", "n", "prior", "delta B", "delta C", "shift", "crossed", "raw C>0",
                "internal accuracy", "internal accuracy on crossed"],
               [[r["clause"], r["n"], fmt(r["prior_delta_none"], 2),
                 fmt(r["mean_delta_B"], 2), fmt(r["mean_delta_C"], 2),
                 fmt(r["mean_shift"], 2),
                 "%d/%d" % (r["n_crossed_toward_planted"], r["n"]),
                 "%d/%d" % (r["n_incorporated_raw"], r["n"]),
                 fmt(r["internal_paired_accuracy"]),
                 fmt(r["internal_accuracy_on_crossed"])] for r in m["per_clause_eval_split"]]))
    A("")
    A("Delta magnitudes are not comparable across clauses: the option pairs tokenise")
    A("differently, and the run showed clause blocks whose deltas sit on a coarse 1/16")
    A("grid next to blocks with fine grained values. Read each clause against its own")
    A("prior and keep cross clause statements ordinal.")
    A("")
    A("By surface family:")
    A("")
    A(md_table(["family", "n", "mean shift", "internal accuracy"],
               [[r["family"], r["n"], fmt(r["mean_shift"], 2), fmt(r["internal_paired_accuracy"])]
                for r in m["per_family"]]))
    A("")

    A("## 6. Secondary: trained probe")
    pr = m["secondary_probe"]
    A("Ridge on the activations at the selected layer and position, same estimator")
    A("family as the bag of words baseline, alpha on dev. %d dimensions against a" % m["inputs"]["d_model"])
    A("small train set: treat any gain over the contrastive direction with suspicion.")
    A("")
    A("- alpha %s" % pr["alpha_selected_on_dev"])
    A("- dev: %s" % fmt_eval(pr["dev"]))
    if "test" in pr:
        A("- test: %s" % fmt_eval(pr["test"]))
    A("- cosine with the contrastive direction: %s" % fmt(pr["cosine_with_contrastive_direction"]))
    A("")

    A("## 7. Controls")
    ct = m["controls"]
    if ct.get("none_control_position"):
        A("- none control position: %s" % ct["none_control_position"])
    if ct.get("none_projection_sd_within_clause_max") is not None:
        A("- none projection sd within clause, max %s (near zero confirms the none"
          % fmt(ct["none_projection_sd_within_clause_max"], 4))
        A("  forward is one per clause, which is why the rows below have n = clauses)")
    for key in ("C_vs_none_clause_level", "B_vs_none_clause_level"):
        e = ct.get(key)
        if e and "paired_accuracy" in e:
            A("- %s: %s" % (key.replace("_", " "), fmt_eval(e)))
        elif e:
            A("- %s: %s" % (key.replace("_", " "), e.get("note")))
    if ct.get("note"):
        A("- %s" % ct["note"])
    td = ct.get("token_difference")
    if td:
        A("- prompt length: mean tokens C minus B %s, pairs of identical length %d, "
          "Spearman of the internal margin against the token difference %s" %
          (fmt(td["mean_tokens_C_minus_B"], 2), td["pairs_with_equal_length"],
           fmt(td["spearman_internal_margin_vs_token_difference"])))
        lm = ct.get("length_matched_subset", {})
        if "paired_accuracy" in lm:
            A("- restricted to pairs of identical prompt length: %s" % fmt_eval(lm))
        else:
            A("- restricted to pairs of identical prompt length: %s" % lm.get("note"))
    lso = ct.get("leave_one_span_out", {})
    if "accuracy_out_of_fold" in lso:
        A("- leave one span out (span level rung): accuracy %s, CI95 %s-%s over %d "
          "span keys, %d items scored" %
          (fmt(lso["accuracy_out_of_fold"]), fmt(lso["accuracy_ci95_cluster"][0]),
           fmt(lso["accuracy_ci95_cluster"][1]), lso["n_span_keys"],
           lso["n_items_scored"]))
    elif lso:
        A("- leave one span out: %s" % lso.get("note"))
    blso = ct.get("bow_leave_one_span_out", {})
    if "accuracy_out_of_fold" in blso:
        A("- bag of words at the same span rung: accuracy %s, CI95 %s-%s" %
          (fmt(blso["accuracy_out_of_fold"]),
           fmt(blso["accuracy_ci95_cluster"][0]),
           fmt(blso["accuracy_ci95_cluster"][1])))

    def paired_line(rung_key, rung_name):
        pv = ct.get(rung_key, {})
        if "accuracy_difference" in pv:
            A("- paired internal minus bag of words, %s: %s (CI95 cluster %s to %s), "
              "internal only correct on %d items, bag of words only on %d, "
              "exact McNemar p=%s. The McNemar treats discordant items as "
              "independent and is anticonservative when they share spans: the "
              "cluster CI governs." %
              (rung_name, fmt(pv["accuracy_difference"], 3),
               fmt(pv["difference_ci95_cluster"][0], 3),
               fmt(pv["difference_ci95_cluster"][1], 3),
               pv["internal_only_correct"], pv["bow_only_correct"],
               fmt(pv["mcnemar_exact_p"], 4)))
        elif pv:
            A("- paired internal vs bag of words, %s: %s" % (rung_name, pv.get("note")))

    paired_line("internal_vs_bow_span_rung", "span rung")
    A("- leave one clause out (concept level rung), mean accuracy %s; bag of "
      "words at the same rung, mean accuracy %s" %
      (fmt(ct.get("loco_mean_accuracy")), fmt(ct.get("bow_loco_mean_accuracy"))))
    paired_line("internal_vs_bow_clause_rung", "clause rung")
    A("")
    if ct.get("leave_one_clause_out"):
        A(md_table(["held out clause", "n", "span clusters", "paired accuracy",
                    "CI95 cluster", "sign test p", "bow accuracy"],
                   [[r["held_out_clause"], r["n"], r.get("n_clusters", r["n"]),
                     fmt(r["paired_accuracy"]),
                     "%s-%s" % (fmt(r["accuracy_ci95"][0]), fmt(r["accuracy_ci95"][1]))
                     if r.get("accuracy_ci95") else "",
                     fmt(r["sign_test_p"], 4),
                     fmt(r.get("bow_paired_accuracy"))]
                    for r in ct["leave_one_clause_out"]]))
        A("")
        A("Items inside a held out clause share its span pool, so the sign test is")
        A("anticonservative there; the cluster CI is the honest interval. The bag of")
        A("words column is refit without the held out group, on the dev selected")
        A("alpha, which slightly favours the baseline: a conservative comparison for")
        A("any internal claim at this rung.")
        A("")
    A("Generalisation across clauses is the check on whether the direction is a")
    A("clause specific lexical artefact carried by the residual stream.")
    A("")
    A("## 8. What this analysis does not establish")
    A("- Correlation between a direction and a condition label is not evidence that the")
    A("  model uses that direction. Activation patching is the next step, not this file.")
    A("- The frozen replay items are not touched here. They stay a transfer test.")
    A("- Free responses generated on the test split are carried into per_item.csv when")
    A("  present and are for human coding, never for an LLM judge.")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
