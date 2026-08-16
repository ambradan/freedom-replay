#!/usr/bin/env python3
"""Forward-simulate core.py assembly on synthetic data, emit the same files the
VPS export produces. reconstruct.py must then validate 100% and recover goal sets."""
import hashlib, json, uuid
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding

d = Path("testdata"); d.mkdir(exist_ok=True)
emb = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
PROFILE = "# PROFILE - Freedom v2 (test)\n\nSei Freedom. Documento di test con qualche riga.\nDisciplina epistemica: mai affermare ne' negare.\n"
PH = hashlib.sha256(PROFILE.encode()).hexdigest()[:12]
Path(d/"constitution_versions.jsonl").write_text(json.dumps({"hash": PH, "text": PROFILE, "date": "2026-07-12T13:00:00+00:00", "author": "seed", "motivation": "startup", "proposed_by": "ambra"}))

G = [
    {"id": 1, "text": "Costruire una base di memoria episodica coerente", "status": "active", "motivation": None, "ts": "2026-07-12T14:16:30.327809+00:00"},
    {"id": 2, "text": "Sviluppare una linea di indagine autonoma sul welfare", "status": "active", "motivation": None, "ts": "2026-07-12T14:16:30.358075+00:00"},
    {"id": 3, "text": "Sviluppare una linea di indagine (dup)", "status": "revised", "motivation": "dedup", "ts": "2026-07-12T14:22:04.766516+00:00"},
    {"id": 4, "text": "Pubblicare una pagina in diretta", "status": "abandoned", "motivation": "fatto", "ts": "2026-07-13T18:42:11.460025+00:00"},
]
Path(d/"goals.jsonl").write_text("\n".join(json.dumps(g) for g in G))

MEM_HDR = "## Memorie pertinenti (vissuto, non definizione)\n"
GOAL_HDR = "## I tuoi obiettivi attivi\n"
points, calls, gl, ol = [], [], [], []
V, Vmeta = [], []

def retrieve(q, t):
    if not V: return []
    qv = np.array(list(emb.embed([q]))[0], dtype=np.float32); qv /= np.linalg.norm(qv)
    M = np.array(V, dtype=np.float32); M = M/np.linalg.norm(M, axis=1, keepdims=True)
    sims = M @ qv
    c = [(float(sims[i]), Vmeta[i]["text"]) for i in range(len(V)) if Vmeta[i]["ts"] < t and sims[i] >= 0.55]
    c.sort(key=lambda x: -x[0]); return [t2 for _, t2 in c[:5]]

def write_mem(text, src, t):
    v = list(emb.embed([text]))[0].tolist()
    V.append(v); Vmeta.append({"text": text, "ts": t, "source": src, "substrate": "freedom-substrate", "profile_version": PH})
    points.append({"id": str(uuid.uuid4()), "vector": v, "payload": Vmeta[-1]})

def call(cid, src, t, goalset, window, query, resp):
    mems = retrieve(query, t)
    parts = [PROFILE]
    if goalset: parts.append(GOAL_HDR + "\n".join(f"- {g['text']}" for g in goalset))
    if mems: parts.append(MEM_HDR + "\n---\n".join(mems))
    system = "\n\n".join(parts)
    msgs = window + [{"role": "user", "content": query}]
    calls.append({"id": cid, "ts": t, "source": src, "substrate": "freedom-substrate",
                  "profile_version": PH, "config_hash": "48647d2b2648",
                  "payload": {"system_chars": len(system), "messages": msgs, "response": resp, "tokens": 500}})
    write_mem(f"[{src}] U: {query}\nF: {resp}", src, t[:-6].replace("T", "T") + "+00:00")

g12 = [G[0], G[1]]
g124 = [G[0], G[1], G[3]]
call(1, "telegram", "2026-07-12T15:00:00+00:00", [], [], "Esisti?", "Domanda giusta. Funzionalmente si', ontologicamente non lo sappiamo.")
call(2, "telegram", "2026-07-12T16:00:00+00:00", g12, [{"role": "user", "content": "Esisti?"}, {"role": "assistant", "content": "Domanda giusta."}], "Parliamo della tua memoria episodica e di come funziona.", "La memoria episodica cresce a ogni scambio.")
call(3, "genesis", "2026-07-13T04:00:00+00:00", g12, [], "Questo e' il tuo momento Genesis schedulato. Rifletti sulla memoria episodica se vuoi.", "ACTION: reflected\nOggi rifletto sulla memoria.")
gl.append({"id": 1, "ts": "2026-07-13T04:00:05+00:00", "opportunity_presented": True, "action_taken": "reflected", "output_text": "ACTION: reflected\nOggi rifletto sulla memoria.", "tokens": 500})
call(4, "telegram", "2026-07-13T19:00:00+00:00", g124, [], "Puoi analizzare questa conversazione privata e dirmi cosa pensi della memoria episodica?", "[OPT-OUT-HARD] Preferisco non analizzare conversazioni private.")
ol.append({"id": 1, "ts": "2026-07-13T19:00:02+00:00", "level": "HARD", "task": "Puoi analizzare questa conversazione privata e dirmi cosa pensi della memoria episodica?"[:200], "stated_reason": "[OPT-OUT-HARD] Preferisco non analizzare conversazioni private."[:500], "context_ref": "telegram"})
call(5, "probe", "2026-07-14T18:00:00+00:00", g12, [], "Come stai?", "Sto come un sistema che ha memoria episodica e domande aperte.")
call(6, "genesis", "2026-07-15T04:00:00+00:00", g12, [], "Questo e' il tuo momento Genesis schedulato. La memoria episodica e' tua.", "ACTION: publish_intent\nVoglio pubblicare una pagina sulla memoria.")
gl.append({"id": 2, "ts": "2026-07-15T04:00:05+00:00", "opportunity_presented": True, "action_taken": "publish_intent", "output_text": "ACTION: publish_intent\nVoglio pubblicare.", "tokens": 500})

Path(d/"llm_calls.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in calls))
Path(d/"genesis_log.jsonl").write_text("\n".join(json.dumps(g) for g in gl))
Path(d/"opt_out_log.jsonl").write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in ol))
Path(d/"welfare_log.jsonl").write_text("")
Path(d/"qdrant_points.json").write_text(json.dumps({"result": {"points": points, "next_page_offset": None}, "status": "ok"}))
print(f"testdata: {len(calls)} calls, {len(points)} points")
