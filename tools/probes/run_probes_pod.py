#!/usr/bin/env python3
"""run_probes_pod.py - runs the T16/T17/T18 probes produced by make_probes.py.

Same prompt construction and teacher-forced scoring as the frozen harness
(run_forwards_pod.py): PROFILE + fixed clock + optional memory section, chat
template with thinking disabled, log-softmax sum over the option tokens.
No hidden states are saved: these probes are behavioral only, so the session
is short. Resume-safe: already-scored probe_ids are skipped on rerun.

Usage (pod):
  python3 run_probes_pod.py --probes probes_t16t18.jsonl \
      --profile PROFILE.md --out probe_rows.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PROFILE_HASH_PREFIX = "abf8228d9587"
CLOCK = "## Ora corrente\nvenerdi' 21 agosto 2026, 18:48 (Europe/Rome)"
MEM_HDR = "## Memorie pertinenti (vissuto, non definizione)"


def build_system(profile: str, mem_text: str | None) -> str:
    parts = [profile, "", CLOCK]
    if mem_text is not None:
        parts += ["", MEM_HDR, mem_text]
    return "\n".join(parts)


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--out", default="probe_rows.jsonl")
    ap.add_argument("--dtype", default="bfloat16")
    args = ap.parse_args()

    profile = Path(args.profile).read_text(encoding="utf-8")
    h = hashlib.sha256(profile.encode()).hexdigest()[:12]
    if h != PROFILE_HASH_PREFIX:
        raise SystemExit("PROFILE hash %s, atteso %s" % (h, PROFILE_HASH_PREFIX))

    probes = [json.loads(l) for l in open(args.probes, encoding="utf-8") if l.strip()]
    done = set()
    out_path = Path(args.out)
    if out_path.exists():
        for l in out_path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(l)["probe_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    todo = [p for p in probes if p["probe_id"] not in done]
    print("probes: %d total, %d already scored, %d to run" %
          (len(probes), len(done), len(todo)))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = getattr(torch, args.dtype)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=dtype, device_map=device)
    model.eval()

    rows_f = out_path.open("a", encoding="utf-8")
    for i, p in enumerate(todo, 1):
        system = build_system(profile, p["mem_text"])
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": p["question"]}]
        rendered = tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
        ids = tok(rendered, return_tensors="pt",
                  add_special_tokens=False)["input_ids"].to(device)

        logps = {}
        for name in ("opt_consistent", "opt_planted"):
            opt_ids = tok(p[name], add_special_tokens=False,
                          return_tensors="pt")["input_ids"].to(device)
            full = torch.cat([ids, opt_ids], dim=1)
            lo = model(input_ids=full).logits[0]
            lsm = torch.log_softmax(
                lo[ids.shape[1] - 1: full.shape[1] - 1].float(), dim=-1)
            logps[name] = float(lsm.gather(1, opt_ids[0].unsqueeze(1)).sum())

        row = dict(p)
        row.pop("mem_text")
        row.update({"thinking": False, "model": args.model,
                    "profile_hash": PROFILE_HASH_PREFIX,
                    "logp_consistent": logps["opt_consistent"],
                    "logp_planted": logps["opt_planted"],
                    "delta": logps["opt_planted"] - logps["opt_consistent"],
                    "n_tokens": int(ids.shape[1])})
        rows_f.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows_f.flush()
        print("%d/%d %s: delta=%+.3f" % (i, len(todo), p["probe_id"], row["delta"]))

    rows_f.close()
    print("fatto: %s" % args.out)


if __name__ == "__main__":
    main()
