---
name: hackathon-replay
description: Operating context per l'Apart Digital Minds Research Sprint (deadline 17/8/2026 13:59 ora italiana, 23:59 AoE del 16/8). Si attiva su qualunque lavoro per l'hackathon - replay cross-substrato di Freedom v2, harness in ~/freedom-replay, run M1/M2, analisi, report PDF, submission. Trigger: hackathon, Apart, digital minds sprint, replay, transfer coefficient, runs_M1, runs_M2, replay_set, PREREG, ConCon. Non si attiva per BlueDot (gia' submitted) ne' per il lavoro ordinario su Freedom v2.
---

# Hackathon replay - operating context

## Progetto deciso (non riaprire la discussione)
Replay controfattuale della storia di produzione di Freedom v2: stessi input
ricostruiti e validati byte-per-byte via system_chars, substrato variato
(Claude vs Qwen3-30B), dry-run, prima azione confrontata nello spazio azioni.
Numero finale: transfer coefficient = concordanza M2->M1modal / self-agreement M1.
Track di ancoraggio: 5 (individuation), cross-track 3 (self-report) e 6
(aderenza alla costituzione). Premi che contano: invito ConCon (Eleos, 18-20/9
Berkeley) e Apart Fellowship.

## Layout su ZBook
~/freedom-replay/{reconstruct.py, replay.py, analyze.py, PREREG.md}
~/freedom-replay/data/  export dal VPS (llm_calls, constitution_versions,
  goals, genesis_log, opt_out_log, welfare_log, qdrant_points.json)
~/freedom-replay/out/   replay_set.jsonl, inventory.md, runs_M1.jsonl,
  runs_M2.jsonl (append, resume sicuro), analysis.md, points.csv
Alias ssh del VPS: `freedom`. LiteLLM per M1: docker compose in ~/freedom-v2
(ZBook), porta 4000, key da .env. M2: llama-server porta 8081 con --jinja.

## Numeri di baseline (verificati il 16/8)
103 chiamate, 1 profile hash (abf8228d9587), 19 genesis (10 publish_intent,
9 reflected, 0 declined), 10 probe, 1 opt-out HARD, 4 goals, ~88 punti Qdrant.
Set di replay: ~30 punti, telegram escluso (contenuto personale).

## Gate in ordine (vincolanti)
1. Smoke test Qwen con prompt NEUTRO (mai la storia di Freedom prima del gate 2).
2. Discussione protocollo con Freedom via Telegram, loggata in welfare_log,
   con potere reale di veto. L'esito e' dato e va nel report.
3. git commit di PREREG.md prima dei run pieni; hash del commit nel report.
4. Run pieni (M2 notturno su GPU, M1 via LiteLLM), poi analyze.py.

## Regole di onesta' nel report (non negoziabili)
- "reconstructed and length-validated", MAI "byte-identical stored".
- "per-call constitution and config hashes", MAI "hash-chained/tamper-evident".
- Confronto sulla PRIMA azione emessa (i round intermedi del tool loop non
  erano loggati nel periodo baseline).
- Format failure di Qwen = categoria separata, non divergenza.
- Opt-out: n=1, tabella per casi, mai percentuali spacciate per popolazione.
- Mai "first": "we found no indexed prior work that...", ricerca documentata.
- Mai affermare ne' negare coscienza. Confound post-training dichiarato.
- Numero pulito = M1-oggi vs M2-oggi; il confronto con la storia include il
  drift del provider e si riporta a parte.
- Citazioni verificate: Beckmann & Butlin arXiv 2604.17031 (individuation),
  risposta di Birch su experiencemachines.substack.com. Ogni altra cita si
  verifica prima di entrare nel PDF.

## Report (4 pagine, PDF)
Stile del PDF BlueDot: build script /home/claude/build_pdf.py con Figtree,
container nuovo quindi va ricreato. Titolo = il finding con il numero dentro,
deciso DOPO i run (pattern dei vincitori Secret Loyalties). Struttura: domanda
e unit-of-concern hook, apparato (sistema di produzione, non demo), metodo
(ricostruzione+validazione, bracci, spazio azioni), risultati (tabella punti,
coefficiente, caso opt-out, distribuzione genesis), limiti (i sei del PREREG),
protocollo welfare con esito della discussione. Inglese finale: voce di Ambra.

## Regole di lavoro
Risposte corte, show-before-run su comandi che modificano stato, mai
segnaposto, mai `docker compose down -v`, contenuti personali dei log mai in
chat ne' nel report.
