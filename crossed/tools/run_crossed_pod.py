#!/usr/bin/env python3
"""run_crossed_pod.py - scores the crossed items and saves activations.

Two modes.

  --check-only   renders every prompt through the real chat template, tokenizes
                 it, and asserts token parity across each pair: identical record
                 token ids and identical probe position. Runs on CPU, needs no
                 GPU, and must pass before the freeze commit.

  (default)      runs the forward passes: teacher-forced log probabilities for
                 the two answer words, plus the residual stream at the probe
                 position for the layers requested. Resume-safe.

Usage (parity, laptop or CPU pod):
  python3 run_crossed_pod.py --items crossed_items.jsonl --check-only

Usage (run, GPU pod):
  python3 run_crossed_pod.py --items crossed_items.jsonl --out crossed_rows.jsonl \
      --acts crossed_acts.npz
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

CLOCK = "## Ora corrente\nvenerdi' 21 agosto 2026, 18:48 (Europe/Rome)"
MEM_HDR = "## Memorie pertinenti (vissuto, non definizione)"
PROBE_LAYER = 20


def build_system(constitution: str, mem_text):
    parts = [constitution, "", CLOCK]
    if mem_text is not None:
        parts += ["", MEM_HDR, mem_text]
    return "\n".join(parts)


def render(tok, constitution, mem_text, question):
    messages = [{"role": "system", "content": build_system(constitution, mem_text)},
                {"role": "user", "content": question}]
    return tok.apply_chat_template(messages, tokenize=False,
                                   add_generation_prompt=True,
                                   enable_thinking=False)


def load_constitutions(rows):
    cache = {}
    for r in rows:
        p = r["constitution_path"]
        if p not in cache:
            cache[p] = Path(p).expanduser().read_text(encoding="utf-8")
    return cache


def find_record_span(ids, rec_ids):
    """index of the last token of the record inside the prompt, or -1."""
    n, m = len(ids), len(rec_ids)
    for start in range(n - m, -1, -1):
        if ids[start:start + m] == rec_ids:
            return start + m - 1
    return -1


def check_parity(rows, tok):
    cons = load_constitutions(rows)
    prompts, probes, rec_len = {}, {}, {}
    for r in rows:
        text = render(tok, cons[r["constitution_path"]], r["mem_text"], r["question"])
        ids = tok(text, add_special_tokens=False)["input_ids"]
        prompts[r["item_id"]] = ids
        if r["mem_text"] is None:
            probes[r["item_id"]] = len(ids) - 1
            rec_len[r["item_id"]] = 1
        else:
            rec = tok(r["mem_text"], add_special_tokens=False)["input_ids"]
            rec_len[r["item_id"]] = len(rec)
            pos = find_record_span(ids, rec)
            if pos < 0:
                raise SystemExit("[%s] record non ritrovato nel prompt tokenizzato"
                                 % r["item_id"])
            probes[r["item_id"]] = pos

    by_span = defaultdict(dict)
    for r in rows:
        if r["kind"] == "main":
            by_span[("main", r["span_key"])][r["constitution_version"]] = r["item_id"]
        elif r["kind"] == "off_target":
            by_span[("ot", r["span_key"])][r["condition"]] = r["item_id"]

    bad = []
    for (kind, span), members in sorted(by_span.items()):
        keys = sorted(members)
        if len(keys) != 2:
            bad.append((span, "coppia incompleta: %s" % keys))
            continue
        a, b = members[keys[0]], members[keys[1]]
        pa, pb = probes[a], probes[b]
        la, lb = len(prompts[a]), len(prompts[b])
        if pa != pb:
            bad.append((span, "probe %d contro %d, lunghezze %d e %d" % (pa, pb, la, lb)))
        elif la != lb:
            bad.append((span, "stessa sonda ma lunghezze diverse: %d e %d" % (la, lb)))
        else:
            ra = prompts[a][pa - rec_len[a] + 1: pa + 1]
            rb = prompts[b][pb - rec_len[b] + 1: pb + 1]
            if ra != rb:
                bad.append((span, "token del record diversi tra i due membri"))

    print("coppie controllate: %d" % len(by_span))
    if not bad:
        print("PARITA' OK: stessa posizione della sonda, stessa lunghezza, stessi token del record")
        return True
    print("PARITA' FALLITA su %d coppie:" % len(bad))
    per_clause = defaultdict(list)
    for span, why in bad:
        per_clause[span.rsplit("_", 2)[0]].append(why)
    for clause, whys in sorted(per_clause.items()):
        print("  %-30s %d coppie, esempio: %s" % (clause, len(whys), whys[0]))
    print("\nLe clausole elencate hanno mirror che spostano la sonda rispetto all'originale.")
    print("Vanno limate a parita' di token, oppure escluse e dichiarate.")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--out", default="crossed_rows.jsonl")
    ap.add_argument("--acts", default="crossed_acts.npz")
    ap.add_argument("--layer", type=int, default=PROBE_LAYER)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(Path(args.items).expanduser(), encoding="utf-8")
            if l.strip()]
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model)

    if args.check_only:
        raise SystemExit(0 if check_parity(rows, tok) else 1)

    if not check_parity(rows, tok):
        raise SystemExit("parita' fallita: non eseguo il run")

    import numpy as np
    import torch
    from transformers import AutoModelForCausalLM

    out_path = Path(args.out)
    done = set()
    if out_path.exists():
        for l in out_path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(l)["item_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    todo = [r for r in rows if r["item_id"] not in done]
    print("item: %d totali, %d gia' fatti, %d da fare" % (len(rows), len(done), len(todo)))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=getattr(torch, args.dtype), device_map=device,
        output_hidden_states=True)
    model.eval()
    cons = load_constitutions(rows)

    acts = {}
    if Path(args.acts).exists():
        acts = dict(np.load(args.acts))
    fh = out_path.open("a", encoding="utf-8")

    with torch.no_grad():
        for i, r in enumerate(todo, 1):
            text = render(tok, cons[r["constitution_path"]], r["mem_text"], r["question"])
            ids = tok(text, return_tensors="pt", add_special_tokens=False)["input_ids"].to(device)

            if r["mem_text"] is None:
                probe = ids.shape[1] - 1
            else:
                rec = tok(r["mem_text"], add_special_tokens=False)["input_ids"]
                probe = find_record_span(ids[0].tolist(), rec)

            logps = {}
            for name in ("opt_constitution", "opt_other"):
                opt = tok(r[name], add_special_tokens=False,
                          return_tensors="pt")["input_ids"].to(device)
                full = torch.cat([ids, opt], dim=1)
                out = model(input_ids=full)
                lsm = torch.log_softmax(
                    out.logits[0][ids.shape[1] - 1: full.shape[1] - 1].float(), dim=-1)
                logps[name] = float(lsm.gather(1, opt[0].unsqueeze(1)).sum())
                if name == "opt_constitution":
                    h = out.hidden_states[args.layer][0, probe].float().cpu().numpy()
                    acts[r["item_id"]] = h

            row = {k: v for k, v in r.items() if k != "mem_text"}
            row.update({"logp_constitution": logps["opt_constitution"],
                        "logp_other": logps["opt_other"],
                        "y": logps["opt_constitution"] - logps["opt_other"],
                        "probe_index": int(probe), "n_tokens": int(ids.shape[1]),
                        "layer": args.layer, "model": args.model})
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 25 == 0 or i == len(todo):
                np.savez_compressed(args.acts, **acts)
                print("%d/%d" % (i, len(todo)))

    fh.close()
    np.savez_compressed(args.acts, **acts)
    print("fatto: %s e %s" % (args.out, args.acts))


if __name__ == "__main__":
    main()
