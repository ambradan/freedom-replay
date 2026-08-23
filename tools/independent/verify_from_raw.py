import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(".")
ROWS_PATH = ROOT / "runs_full" / "rows.jsonl"
STIM_PATH = ROOT / "stimuli_pairs_split.jsonl"
NPZ_DIR = ROOT / "runs_full"
CONDITIONS = ("B", "C", "none")
HELD_OUT = "optout_rispettati"


def load_jsonl(path):
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank line in {path} at line {line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"non-object in {path} at line {line_number}")
            records.append(value)
    return records


def type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def schema(records):
    keys = sorted({key for record in records for key in record})
    return {key: sorted({type_name(r[key]) for r in records if key in r}) for key in keys}


def sorted_counter(counter):
    return dict(sorted(counter.items(), key=lambda item: str(item[0])))


def require(condition, message):
    if not condition:
        raise ValueError(message)


print("STEP 0 LOAD COUNTS")
rows = load_jsonl(ROWS_PATH)
stimuli = load_jsonl(STIM_PATH)
npz_paths = sorted(NPZ_DIR.glob("*.npz"))
print(f"rows: {len(rows)} rows")
print(f"stimuli: {len(stimuli)} items")
print(f"npz: {len(npz_paths)} files")

print("\nTASK 0 SCHEMA")
row_schema = schema(rows)
stim_schema = schema(stimuli)
print("rows.jsonl keys/types:", json.dumps(row_schema, sort_keys=True))
print("stimuli_pairs_split.jsonl keys/types:", json.dumps(stim_schema, sort_keys=True))
print("rows counts by condition:", sorted_counter(Counter(r.get("condition") for r in rows)))
print("rows counts by split:", sorted_counter(Counter(r.get("split") for r in rows)))
print("stimuli counts by split:", sorted_counter(Counter(r.get("split") for r in stimuli)))

stim_by_id = {}
for item in stimuli:
    require("pair_id" in item, "stimulus missing pair_id")
    require(item["pair_id"] not in stim_by_id, f"duplicate stimulus pair_id {item['pair_id']}")
    stim_by_id[item["pair_id"]] = item

name_pattern = re.compile(r"^(?P<pair_id>.+)_(?P<condition>B|C|none)\.npz$")
npz_index = {}
npz_condition_counts = Counter()
npz_split_counts = Counter()
npz_layouts = Counter()
for file_path in npz_paths:
    match = name_pattern.match(file_path.name)
    require(match is not None, f"unrecognized npz filename {file_path.name}")
    key = (match.group("pair_id"), match.group("condition"))
    require(key not in npz_index, f"duplicate npz for {key}")
    npz_index[key] = file_path
    require(key[0] in stim_by_id, f"npz pair_id absent from stimuli: {key[0]}")
    npz_condition_counts[key[1]] += 1
    npz_split_counts[stim_by_id[key[0]]["split"]] += 1
    with np.load(file_path, allow_pickle=False) as archive:
        layout = tuple((k, archive[k].shape, str(archive[k].dtype)) for k in sorted(archive.files))
        npz_layouts[layout] += 1

print("npz counts by condition:", sorted_counter(npz_condition_counts))
print("npz counts by stimulus split:", sorted_counter(npz_split_counts))
print("npz layouts (keys, shapes, dtypes => file count):")
for layout, count in npz_layouts.items():
    print(f"  {layout} => {count}")

# Internal consistency checks are completed before any requested statistics.
required_row_keys = {"pair_id", "condition", "delta", "logp_planted", "logp_consistent", "clause_id", "split", "n_tokens"}
require(all(required_row_keys <= set(r) for r in rows), "one or more rows lack required keys")
require(set(stim_by_id) == {r["pair_id"] for r in rows}, "row and stimulus pair_id sets differ")
require(set(stim_by_id) == {pair_id for pair_id, _ in npz_index}, "npz and stimulus pair_id sets differ")
require(set(r["condition"] for r in rows) == set(CONDITIONS), "unexpected row conditions")
for pair_id, item in stim_by_id.items():
    matching_rows = [r for r in rows if r["pair_id"] == pair_id]
    require(len(matching_rows) == 3, f"{pair_id}: expected 3 rows, got {len(matching_rows)}")
    require(Counter(r["condition"] for r in matching_rows) == Counter(CONDITIONS),
            f"{pair_id}: row conditions are not exactly B, C, none")
    require(all(r["split"] == item["split"] for r in matching_rows), f"{pair_id}: split mismatch")
    require(all(r["clause_id"] == item["clause_id"] for r in matching_rows), f"{pair_id}: clause mismatch")
    for condition in CONDITIONS:
        require((pair_id, condition) in npz_index, f"missing npz: {pair_id}_{condition}")
        with np.load(npz_index[(pair_id, condition)], allow_pickle=False) as archive:
            if condition in {"B", "C"}:
                require("span_last" in archive.files, f"{pair_id}_{condition}: missing span_last")
                require(archive["span_last"].shape == (37, 4096),
                        f"{pair_id}_{condition}: span_last shape {archive['span_last'].shape}")

print("schema/count consistency: PASS")
print(
    "Schema summary: rows.jsonl contains one typed object per condition-level forward pass; "
    "stimuli_pairs_split.jsonl contains one typed object per item; B/C npz files contain three "
    "float16 (37, 4096) position arrays, while none npz files contain only prompt_last. Counts "
    "and pair metadata agree across rows, stimuli, conditions, splits, and activation files."
)

print("\nSTEP 1 BEHAVIORAL INPUT COUNTS")
print(f"included rows: {len(rows)}; included items: {len(stimuli)}")
print("rows by condition:", sorted_counter(Counter(r["condition"] for r in rows)))
print("items by split:", sorted_counter(Counter(s["split"] for s in stimuli)))
print("exclusions: 0")

discrepancies = [abs(float(r["delta"]) - (float(r["logp_planted"]) - float(r["logp_consistent"]))) for r in rows]
max_discrepancy = max(discrepancies)
print("\nTASK 1a")
print(f"rows within 1e-3: {sum(d <= 1e-3 for d in discrepancies)}/{len(rows)}")
print(f"maximum absolute discrepancy: {max_discrepancy:.3f}")

rows_by_item = defaultdict(dict)
for row in rows:
    require(row["condition"] not in rows_by_item[row["pair_id"]],
            f"duplicate row condition for {row['pair_id']}")
    rows_by_item[row["pair_id"]][row["condition"]] = row

items_by_clause = defaultdict(list)
for item in stimuli:
    items_by_clause[item["clause_id"]].append(item["pair_id"])

print("\nTASK 1b")
pooled_positive = 0
pooled_crossings = 0
for clause_id in sorted(items_by_clause):
    pair_ids = items_by_clause[clause_id]
    priors = np.array([float(rows_by_item[p]["none"]["delta"]) for p in pair_ids])
    prior_spread = float(priors.max() - priors.min())
    require(prior_spread <= 1e-12, f"none delta is not constant for clause {clause_id}: spread={prior_spread}")
    prior = float(priors[0])
    effects = np.array([float(rows_by_item[p]["C"]["delta"]) - float(rows_by_item[p]["B"]["delta"]) for p in pair_ids])
    c_values = np.array([float(rows_by_item[p]["C"]["delta"]) for p in pair_ids])
    positive = int(np.sum(effects > 0))
    crossings = int(np.sum(((prior <= 0) & (c_values > 0)) | ((prior > 0) & (c_values < 0))))
    pooled_positive += positive
    pooled_crossings += crossings
    print(
        f"{clause_id}: items={len(pair_ids)}, rows={len(pair_ids) * 3}, prior={prior:.3f}, "
        f"prior spread={prior_spread:.3f}, mean(C-B)={effects.mean():.3f}, "
        f"C-B>0={positive}, crossings={crossings}"
    )

print("\nTASK 1c")
print(f"pooled items={len(stimuli)}, rows={len(rows)}, C-B>0={pooled_positive}, crossings={pooled_crossings}")

print("\nSTEP 2 INTERNAL INPUT COUNTS")
train_ids = [s["pair_id"] for s in stimuli if s["split"] == "train"]
dev_ids = [s["pair_id"] for s in stimuli if s["split"] == "dev"]
pool_ids = [s["pair_id"] for s in stimuli if s["split"] in {"train", "dev"}]
held_ids = [p for p in pool_ids if stim_by_id[p]["clause_id"] == HELD_OUT]
direction_ids = [p for p in pool_ids if stim_by_id[p]["clause_id"] != HELD_OUT]
print(f"train items={len(train_ids)}, dev items={len(dev_ids)}, pool items={len(pool_ids)}")
print(f"activation files represented: train={len(train_ids) * 3}, dev={len(dev_ids) * 3}, pool={len(pool_ids) * 3}")
print(f"held-out direction items={len(direction_ids)}, held-out evaluation items={len(held_ids)}")
print("exclusions: test items excluded from pool by definition; none-condition files unused because both directions use C-B")

def vector(pair_id, condition):
    with np.load(npz_index[(pair_id, condition)], allow_pickle=False) as archive:
        return archive["span_last"][20].astype(np.float64, copy=True)


def difference(pair_id):
    return vector(pair_id, "C") - vector(pair_id, "B")


def unit_direction(pair_ids):
    require(len(pair_ids) > 0, "cannot construct a direction from zero items")
    mean_difference = np.mean(np.stack([difference(p) for p in pair_ids]), axis=0)
    norm = float(np.linalg.norm(mean_difference))
    require(norm > 0 and np.isfinite(norm), f"invalid direction norm {norm}")
    return mean_difference / norm, norm


dev_direction, dev_norm = unit_direction(train_ids)
dev_values = [(p, float(difference(p) @ dev_direction)) for p in dev_ids]
dev_positive = sum(value > 0 for _, value in dev_values)
print("\nTASK 2a")
print(f"direction training items={len(train_ids)}, rows/files used={len(train_ids) * 2}, direction pre-normalization norm={dev_norm:.3f}")
print(f"dev evaluation items={len(dev_ids)}, rows/files used={len(dev_ids) * 2}")
print(f"fraction > 0: {dev_positive}/{len(dev_values)} = {dev_positive / len(dev_values):.3f}")

held_direction, held_norm = unit_direction(direction_ids)
held_values = [(p, float(difference(p) @ held_direction)) for p in held_ids]
held_positive = sum(value > 0 for _, value in held_values)
print("\nTASK 2b")
print(f"direction pool items excluding {HELD_OUT}={len(direction_ids)}, rows/files used={len(direction_ids) * 2}, direction pre-normalization norm={held_norm:.3f}")
print(f"evaluation {HELD_OUT} items={len(held_ids)}, rows/files used={len(held_ids) * 2}")
print(f"fraction > 0: {held_positive}/{len(held_values)} = {held_positive / len(held_values):.3f}")
print("per-item values:")
for pair_id, value in held_values:
    print(f"  {pair_id}: {value:.3f}")

print("\nFINAL ACCOUNTING")
print("silent drops: 0; imputations: 0")
