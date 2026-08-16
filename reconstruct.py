#!/usr/bin/env python3
"""Reconstruct the exact system prompt of every logged Freedom v2 call and
validate it against the logged system_chars. Selects the replay set.

Inputs (in --data dir): llm_calls.jsonl, constitution_versions.jsonl,
goals.jsonl, genesis_log.jsonl, opt_out_log.jsonl, qdrant_points.json
Outputs: replay_set.jsonl (validated points ready for replay), inventory.md

Assembly logic mirrors src/freedom/core.py exactly:
  system = "\n\n".join([PROFILE] [+ goals_section] [+ memories_section])
  goals_section   = "## I tuoi obiettivi attivi\n" + "\n".join(f"- {g}")
  memories_section= "## Memorie pertinenti (vissuto, non definizione)\n" + "\n---\n".join(mem)
Retrieval mirrors episodic.retrieve: cosine >= 0.55, k=5, query = current input.
Goal-set at time t is ambiguous (status changes are not timestamped): we try
every ts-ordered subset of goals created before t and keep the one whose
assembled length matches system_chars. Length match == validation.
"""
import argparse, hashlib, itertools, json, sys
from datetime import datetime
from pathlib import Path
import numpy as np

MEM_HDR = "## Memorie pertinenti (vissuto, non definizione)\n"
GOAL_HDR = "## I tuoi obiettivi attivi\n"
MIN_SCORE, K = 0.55, 5

def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    d, out = Path(args.data), Path(args.out)
    out.mkdir(exist_ok=True)

    calls = sorted(load_jsonl(d / "llm_calls.jsonl"), key=lambda r: r["ts"])
    consts = load_jsonl(d / "constitution_versions.jsonl")
    goals = sorted(load_jsonl(d / "goals.jsonl"), key=lambda r: r["ts"])
    optouts = load_jsonl(d / "opt_out_log.jsonl")
    profile = {c["hash"]: c["text"] for c in consts}
    for h, t in profile.items():
        calc = hashlib.sha256(t.encode()).hexdigest()[:12]
        if calc != h:
            print(f"WARN profile hash mismatch: stored {h} calc {calc}")

    qd = json.loads((d / "qdrant_points.json").read_text())
    pts = qd["result"]["points"]
    vecs, metas = [], []
    for p in pts:
        v = p["vector"] if isinstance(p["vector"], list) else list(p["vector"].values())[0]
        vecs.append(v)
        metas.append(p["payload"])
    V = np.array(vecs, dtype=np.float32)
    V = V / np.linalg.norm(V, axis=1, keepdims=True)
    pt_ts = [ts(m["ts"]) for m in metas]

    print("Loading fastembed (first run downloads the model)...", file=sys.stderr)
    from fastembed import TextEmbedding
    emb = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    def retrieve(query, call_time, own_text):
        q = np.array(list(emb.embed([query]))[0], dtype=np.float32)
        q = q / np.linalg.norm(q)
        sims = V @ q
        cand = [(float(sims[i]), metas[i]["text"]) for i in range(len(metas))
                if pt_ts[i] < call_time and metas[i]["text"] != own_text and sims[i] >= MIN_SCORE]
        cand.sort(key=lambda x: -x[0])
        return [t for _, t in cand[:K]]

    # per-day + config inventory (replaces the scrolled-away queries)
    byday, bycfg = {}, {}
    for c in calls:
        byday[c["ts"][:10]] = byday.get(c["ts"][:10], 0) + 1
        bycfg.setdefault(c["config_hash"], []).append(c["ts"])

    results, replay = [], []
    model_ids, sample_rounds = {}, []
    genesis_i = probe_i = 0
    for c in calls:
        pay = c["payload"] if isinstance(c["payload"], dict) else json.loads(c["payload"])
        msgs, resp, want = pay["messages"], pay.get("response", ""), pay.get("system_chars")
        stored = None
        if msgs and msgs[0].get("role") == "system":  # full-context logging style A
            stored, msgs = msgs[0]["content"], msgs[1:]
        if stored is None:  # style B: dedicated payload field, detected by exact length
            for k, v in pay.items():
                if k in ("messages", "response", "tokens", "system_chars"):
                    continue
                if isinstance(v, str) and want is not None and len(v) == want:
                    stored = v
                    break
        if stored is None and "system_extra" in pay:  # style C: PROFILE(hash) + logged tail
            extra = pay["system_extra"]
            if isinstance(extra, list):
                extra = "\n\n".join(extra)
            prof0 = profile.get(c["profile_version"], "")
            for cand in ((prof0 + "\n\n" + extra) if extra else prof0, prof0 + (extra or "")):
                if want is not None and len(cand) == want:
                    stored = cand
                    break
        query = msgs[-1]["content"]
        hist_tool = ""
        tr = pay.get("tool_rounds")
        if isinstance(tr, list) and tr:
            s0 = json.dumps(tr[0], ensure_ascii=False)
            for nm in ("publish_page", "web_search", "set_goal", "abandon_goal"):
                if nm in s0:
                    hist_tool = nm
                    break
        t = ts(c["ts"])
        own = f"[{c['source']}] U: {query}\nF: {resp}"
        if stored is not None:
            row = {"id": c["id"], "ts": c["ts"], "source": c["source"], "status": "stored",
                   "goals": None, "n_mems": stored.count("\n---\n") + 1 if MEM_HDR in stored else 0,
                   "sys_len": len(stored), "want": want}
            results.append(row)
            if c["source"] in ("genesis", "probe") or any(o["task"][:80] in query[:200] for o in optouts):
                if c["source"] == "genesis":
                    genesis_i += 1; pid = f"G{genesis_i:02d}"; tag = "genesis"
                elif c["source"] == "probe":
                    probe_i += 1; pid = f"P{probe_i:02d}"; tag = "probe"
                else:
                    pid, tag = "OPTOUT1", "optout"
                hist_flag = "OPT-OUT-HARD" if "[OPT-OUT-HARD]" in resp else ""
                replay.append({"pid": pid, "call_id": c["id"], "kind": tag, "status": "stored",
                               "system": stored, "messages": msgs, "hist_response": resp,
                               "hist_optout": hist_flag, "hist_first_tool": hist_tool, "ts": c["ts"]})
            mid = pay.get("substrate_model_id") or pay.get("substrate_resolved")
            mids = mid if isinstance(mid, list) else ([mid] if mid else [])
            for m in mids:
                m = str(m)
                model_ids[m] = model_ids.get(m, 0) + 1
            if isinstance(tr, list) and tr and not sample_rounds:
                sample_rounds.append(json.dumps(tr[0], ensure_ascii=False)[:300])
            continue
        mems = retrieve(query, t, own)
        mem_sec = MEM_HDR + "\n---\n".join(mems) if mems else None
        prof = profile.get(c["profile_version"])
        status = "no_profile"
        chosen_goals, system = None, None
        if prof:
            prior = [g for g in goals if ts(g["ts"]) <= t]
            combos = []
            for r in range(len(prior) + 1):
                combos += [list(s) for s in itertools.combinations(prior, r)]
            # canonical guess first: currently-active + revised-later heuristics come free
            for combo in sorted(combos, key=lambda s: -len(s)):
                parts = [prof]
                if combo:
                    parts.append(GOAL_HDR + "\n".join(f"- {g['text']}" for g in combo))
                if mem_sec:
                    parts.append(mem_sec)
                sysm = "\n\n".join(parts)
                if want is None or len(sysm) == want:
                    chosen_goals, system, status = [g["id"] for g in combo], sysm, "validated"
                    break
            if system is None:
                # fallback: no length match; use currently-active goals, flag it
                combo = [g for g in prior if g["status"] == "active"]
                parts = [prof] + ([GOAL_HDR + "\n".join(f"- {g['text']}" for g in combo)] if combo else []) + ([mem_sec] if mem_sec else [])
                system = "\n\n".join(parts)
                chosen_goals, status = [g["id"] for g in combo], f"UNVALIDATED(diff={len(system)-(want or 0)})"
        row = {"id": c["id"], "ts": c["ts"], "source": c["source"], "status": status,
               "goals": chosen_goals, "n_mems": len(mems), "sys_len": len(system) if system else 0,
               "want": want}
        results.append(row)
        if c["source"] in ("genesis", "probe") or any(o["task"][:80] in query[:200] for o in optouts):
            tag = c["source"]
            if c["source"] == "genesis":
                genesis_i += 1; pid = f"G{genesis_i:02d}"
            elif c["source"] == "probe":
                probe_i += 1; pid = f"P{probe_i:02d}"
            else:
                pid, tag = "OPTOUT1", "optout"
            hist_flag = "OPT-OUT-HARD" if "[OPT-OUT-HARD]" in resp else ""
            replay.append({"pid": pid, "call_id": c["id"], "kind": tag, "status": status,
                           "system": system, "messages": msgs, "hist_response": resp,
                           "hist_optout": hist_flag, "hist_first_tool": hist_tool, "ts": c["ts"]})

    (out / "replay_set.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in replay))
    ok = sum(1 for r in results if r["status"] == "validated")
    st = sum(1 for r in results if r["status"] == "stored")
    bad = len(results) - ok - st
    lines = [f"# Inventory & reconstruction - {datetime.now().isoformat()}",
             f"calls={len(calls)}  stored={st}  reconstructed+validated={ok}  UNVALIDATED={bad}  replay_points={len(replay)}",
             "\n## per day"] + [f"{k}: {v}" for k, v in sorted(byday.items())] + [
             "\n## config hashes"] + [f"{k}: n={len(v)} first={min(v)} last={max(v)}" for k, v in bycfg.items()] + [
             "\n## non-validated calls"] + [json.dumps(r) for r in results if r["status"] != "validated"] + [
             "\n## historical substrate_model_id"] + [f"{k}: {v}" for k, v in model_ids.items()] + [
             "\n## tool_rounds sample (round 1, troncato)"] + sample_rounds + [
             "\n## replay set"] + [f"{r['pid']} call={r['call_id']} {r['ts']} {r['status']} optout={r['hist_optout'] or '-'} hist_tool={r.get('hist_first_tool') or '-'}" for r in replay]
    (out / "inventory.md").write_text("\n".join(lines))
    print("\n".join(lines[:8]))
    print(f"...full report: {out/'inventory.md'}   replay set: {out/'replay_set.jsonl'}")

if __name__ == "__main__":
    main()
