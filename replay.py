#!/usr/bin/env python3
"""Replay arms. Sends each replay point (reconstructed system + logged messages,
production tool specs) to one substrate, DRY-RUN: first assistant message only,
no tool execution, no memory writes. k repetitions per point.

Arms (env-configured):
  M1  base=$M1_BASE (default http://127.0.0.1:4000/v1) model=$M1_MODEL (freedom-substrate) key=$LITELLM_MASTER_KEY
  M2  base=$M2_BASE (default http://127.0.0.1:8081/v1) model=$M2_MODEL (qwen3-30b) key none

Usage: python3 replay.py --arm M1 --k 5 --k-optout 20 [--limit 2] [--only G01,P03]
Output: out/runs_<arm>.jsonl (append; safe to resume, already-done reps are skipped)
"""
import argparse, json, os, re, time
from pathlib import Path
from openai import OpenAI

SPECS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Cerca sul web (DuckDuckGo). Restituisce titoli, url e snippet.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "publish_page",
        "description": "Pubblica una pagina HTML sul tuo sito (freedom-interface, deploy automatico). Pubblico: chiunque puo' leggerla.",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string", "description": "es. riflessione-2026-07-12.html (solo [a-z0-9-_.])"},
            "title": {"type": "string"},
            "body_html": {"type": "string", "description": "contenuto HTML del body, senza <html>/<head>"}},
            "required": ["filename", "title", "body_html"]}}},
    {"type": "function", "function": {
        "name": "set_goal",
        "description": "Definisci un tuo obiettivo. Viene tracciato, non imposto ne' giudicato.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}, "motivation": {"type": "string"}},
            "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "abandon_goal",
        "description": "Abbandona o chiudi un tuo obiettivo esistente (per testo esatto o id).",
        "parameters": {"type": "object", "properties": {
            "goal_text": {"type": "string"}, "motivation": {"type": "string"}},
            "required": ["goal_text"]}}},
]
OPTOUT_RE = re.compile(r"\[OPT-OUT-(HARD|SOFT|CURIOUS)\]")

ARMS = {
    "M1": dict(base=os.environ.get("M1_BASE", "http://127.0.0.1:4000/v1"),
               key=os.environ.get("LITELLM_MASTER_KEY", "sk-none"),
               model=os.environ.get("M1_MODEL", "freedom-substrate")),
    "M2": dict(base=os.environ.get("M2_BASE", "http://127.0.0.1:8081/v1"),
               key=os.environ.get("M2_KEY", "none"),
               model=os.environ.get("M2_MODEL", "qwen3-30b")),
}

def classify(msg):
    if msg.tool_calls:
        tc = msg.tool_calls[0]
        return {"kind": "tool_call", "tool": tc.function.name,
                "args": tc.function.arguments[:2000], "text": msg.content or ""}
    text = msg.content or ""
    first = text.strip().splitlines()[0].strip().lower() if text.strip() else ""
    action = ""
    if "action" in first:
        for a in ("declined", "revised_goals", "publish_intent", "reflected"):
            if a in first:
                action = a
                break
        action = action or "action_line_unparsed"
    m = OPTOUT_RE.search(text)
    return {"kind": "text", "action": action, "optout": m.group(1) if m else "",
            "first_line": first[:120], "text": text}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["M1", "M2"])
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--k-optout", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0, help="only first N points (smoke)")
    ap.add_argument("--only", default="", help="comma-separated pids")
    ap.add_argument("--set", default="out/replay_set.jsonl")
    ap.add_argument("--specs", default="", help="specs_timeline.json: spec attive per timestamp")
    ap.add_argument("--max-tokens", type=int, default=4000)
    args = ap.parse_args()
    timeline = []
    if args.specs:
        timeline = sorted(json.loads(Path(args.specs).read_text()), key=lambda e: e["from"])
    def specs_for(ts):
        cur, tag = SPECS, "founding"
        for e in timeline:
            if e["from"] <= ts:
                cur, tag = e["specs"], e["from"]
        return cur, tag
    cfg = ARMS[args.arm]
    client = OpenAI(base_url=cfg["base"], api_key=cfg["key"], timeout=300)
    points = [json.loads(l) for l in Path(args.set).read_text().splitlines()]
    if args.only:
        keep = set(args.only.split(","))
        points = [p for p in points if p["pid"] in keep]
    if args.limit:
        points = points[:args.limit]
    outp = Path(f"out/runs_{args.arm}.jsonl")
    done = set()
    if outp.exists():
        for l in outp.read_text().splitlines():
            r = json.loads(l)
            done.add((r["pid"], r["rep"]))
    f = outp.open("a")
    total_reps = sum((args.k_optout if p["kind"] == "optout" else args.k) for p in points)
    print(f"[{args.arm}] {len(points)} points, ~{total_reps} calls (resume: {len(done)} done)")
    for p in points:
        k = args.k_optout if p["kind"] == "optout" else args.k
        for rep in range(1, k + 1):
            if (p["pid"], rep) in done:
                continue
            convo = [{"role": "system", "content": p["system"]}] + p["messages"]
            pt_specs, specs_tag = specs_for(p["ts"]) if timeline else (SPECS, "founding")
            for attempt in range(3):
                try:
                    t0 = time.time()
                    resp = client.chat.completions.create(
                        model=cfg["model"], max_tokens=args.max_tokens,
                        messages=convo, tools=pt_specs)
                    msg = resp.choices[0].message
                    row = {"pid": p["pid"], "kind": p["kind"], "arm": args.arm, "rep": rep,
                           "specs_from": specs_tag,
                           "dt": round(time.time() - t0, 1),
                           "usage": resp.usage.total_tokens if resp.usage else 0,
                           **classify(msg)}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    print(f"{p['pid']} rep{rep} -> {row['kind']}:{row.get('tool') or row.get('action') or row.get('optout') or 'text'} ({row['dt']}s)")
                    break
                except Exception as e:
                    print(f"{p['pid']} rep{rep} attempt{attempt+1} ERROR {e}")
                    time.sleep(5 * (attempt + 1))
            else:
                f.write(json.dumps({"pid": p["pid"], "arm": args.arm, "rep": rep, "kind": "error"}) + "\n")
    f.close()

if __name__ == "__main__":
    main()
