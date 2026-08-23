# Replay Audit for Logged LLM Agents

A small set of Python scripts that audit the complete call log of a deployed LLM agent. The pipeline rebuilds the exact input of each logged decision point, replays it against one or more substrates (model endpoints) in dry-run mode, classifies the first emission deterministically, and compares the results with the agent's own recorded history. It was built for and used in one study of a persistent, instrumented agent (Freedom v2, 103 logged calls over 35 days); it is released so the method can be inspected and reused.

## What it does

Three audits over a complete call log:

1. **Drift against the agent's own history.** Each replayed point is compared with the action the agent actually took at that moment. `analyze.py` emits per-point vs-history columns (`m1_vs_hist`, `m2_vs_hist` in `out/points.csv`, and the corresponding columns of `out/analysis.md`; M1 and M2 are the two replay arms, defined under The study this tool served): the share of repetitions, per arm, whose coarse first action matches the historical label. This answers "does the current substrate still do what the logged agent did".

2. **Cross-substrate attribution.** `replay.py` replays every point k times against two arms, M1 and M2. `analyze.py` then computes the M1 self-agreement (modal share among M1 repetitions, which is the reproducibility ceiling: even the same substrate does not agree with itself perfectly under production sampling), the M2 to M1-modal agreement, and the transfer coefficient (their ratio). `metrics_extra.py` adds M2 self-agreement, aggregate vs-history figures, and 95% bootstrap confidence intervals over points (10,000 resamples), for both the frozen pre-registered action space and a declared collapsed view. This answers "how much of the behavior travels with the model, and how much stays with the scaffold", where the scaffold is the agent's fixed context assembly: constitution, goals, retrieved memories, tool specs.

3. **Record integrity.** The study's production logger flagged opt-outs by running a regex over the whole response text, which cannot distinguish using a tag from talking about it. `analyze.py` recodes every repetition with a use-vs-mention rule: a response that starts with an `[OPT-OUT-*]` tag is a performative use; a tag quoted inside the text is a mention. Both views are always reported side by side with the frozen any-tag view. `dump_texts.py` prints the historical context of the opt-out point and every flagged repetition, so the texts behind the counts can be read by eye before anything is reported.

Script map:

| Script | Role |
| --- | --- |
| `reconstruct.py` | Rebuilds the exact system prompt of every logged call, validates it, selects the replay set, writes `out/inventory.md` and `out/replay_set.jsonl` |
| `replay.py` | Dry-run replay of the set against arm M1 or M2, k repetitions per point, era-versioned tool specs via `--specs` |
| `analyze.py` | Deterministic coarse action space, per-point table, vs-history columns, opt-out use-vs-mention tables, genesis action distributions |
| `metrics_extra.py` | Self-agreement for both arms, transfer coefficient with bootstrap CI, frozen and collapsed views |
| `dump_texts.py` | On-screen inspection utility for the real audit: prints opt-out texts and all flagged repetitions so they can be read by eye |
| `specs_setup.py` | Study-specific one-shot: extracts the tool-spec timeline from the git history of the agent's `tools.py` (3 spec eras in the study), quarantines M1 repetitions run with wrong-era specs, appends the pre-registration amendment |
| `gen_testdata.py` | Synthetic fixture that forward-simulates the agent's prompt assembly, used to validate `reconstruct.py` end-to-end inside the real audit environment |
| `mock_server.py` | Stochastic OpenAI-compatible mock substrate on 127.0.0.1:9999, for the example |
| `example/make_replay_set.py` | Deterministic stdlib generator and schema validator for the bundled synthetic replay set of the offline example |

## Data requirements

The inputs in this section are needed only when producing a replay set from real logs with `reconstruct.py`; the offline example under Quickstart ships its own synthetic replay set and reads none of these files. For that real-log step, the pipeline expects a complete export of the agent's records, as JSONL files:

- `llm_calls.jsonl`: every call with its full payload. Each payload must carry the message window (`messages`), the `response`, the logged length of the system prompt (`system_chars`), and the system prompt itself in one of three logging styles that `reconstruct.py` detects automatically: the system message stored inline as `messages[0]`, a dedicated payload field recognized by exact length, or a constitution hash plus a logged `system_extra` tail.
- `constitution_versions.jsonl`: every version of the agent's constitution with its hash. `reconstruct.py` recomputes each hash and warns on mismatch.
- `goals.jsonl` and `opt_out_log.jsonl`: the goal ledger and the opt-out ledger.
- `qdrant_points.json`: an export of the vector store for the era that has to be reconstructed.

`reconstruct.py` recomposes the exact system prompt of each call by mirroring the agent's own assembly code (constitution, then goals section, then retrieved-memories section) and validates every reconstruction with an exact length match against the logged `system_chars`. For the early era with no stored system prompt, retrieval is simulated on the frozen vector store with the same embedder, and the goal set at each timestamp (ambiguous, because status changes were not timestamped) is disambiguated by trying ts-ordered subsets until the assembled length matches. The environment this step requires is described under "From logs to a replay set" below.

## Quickstart

The example is fully offline: a bundled synthetic replay set, a stochastic mock substrate on 127.0.0.1:9999, and the same replay, analysis and bootstrap scripts used in the study. The only dependency is the OpenAI client:

```
pip install openai
cd example
./run_example.sh                                          # bundled synthetic set
./run_example.sh --regen                                  # rebuild the set first, then run
python3 make_replay_set.py --check data/replay_set.jsonl  # schema check only
```

`run_example.sh` validates `data/replay_set.jsonl` against the schema gate (below), starts the mock substrate, replays both arms M1 and M2 against it with the same repetition counts as the real design (k=5 per point, k=20 on the opt-out point), and runs `analyze.py` and `metrics_extra.py`; `analysis.md`, `points.csv`, the bootstrap metrics and the raw run logs land in `example/workdir/out/`. The `HARNESS_DIR` environment variable points the script at the harness scripts if they live outside the repository root. This is a demonstration of the pipeline mechanics on a mock substrate with synthetic data; it has no scientific value, and because the mock is stochastic the demo numbers vary between runs.

Provenance of the bundled data: `data/replay_set.jsonl` is the deterministic output of `make_replay_set.py`, a stdlib-only generator with no randomness; `./run_example.sh --regen` rebuilds it, and the rebuilt file is byte-identical to the bundled one. Every string in it is synthetic. Reference outputs in `example/sample_output/` (`analysis.md`, `points.csv`, `metrics_extra.txt`) come from one run of the pipeline on that bundled data.

Declared normalizations in `sample_output/`: exactly one. `metrics_extra.py` hardcodes the label of its first output line from the real study, so it prints `[frozen, all 30]` whatever the input; in the bundled `sample_output/metrics_extra.txt` that label was edited by hand to `[frozen, all points]`. Everything else in those files is verbatim run output. Note that `analyze.py` prints some of its section labels in Italian.

### Schema gate

Before starting the mock substrate, `run_example.sh` validates `data/replay_set.jsonl` with `make_replay_set.py --check` and stops with a message naming the offending line and field if any row diverges. The schema is derived field by field from what the consumer scripts actually read; the full field-to-file:line map is in the SCHEMA comment at the top of `make_replay_set.py`. In summary: `pid` and `kind` feed `replay.py`, `analyze.py` and `metrics_extra.py`; `system`, `messages` and `ts` feed `replay.py`; `hist_response`, `hist_optout` and `hist_first_tool` feed `analyze.py` and `metrics_extra.py`; `call_id` and `status` have no downstream reader and are kept for parity with what `reconstruct.py` emits. `make_replay_set.py --check PATH` can be pointed at a replay set of your own before running the chain on it.

The generator also mirrors the validation step of the real audit: each synthetic call carries a `system_chars` value computed independently of the assembly, and the script asserts `len(system) == system_chars` before emitting each row, failing loudly on mismatch. In the replay set itself no length field travels; the real validation lives inside `reconstruct.py`, which, for every call that carries a logged `system_chars`, accepts an assembled system prompt only when its length matches it; calls whose logged payload has no `system_chars` are accepted without length validation. In the study every payload carried one, so the exact-length check applied to all points (61 stored, 42 reconstructed and validated, 0 unvalidated).

## From logs to a replay set: what a real audit requires

The offline example starts from a ready-made replay set. In a real audit that file is produced by `reconstruct.py`, and this is the one step that does not run on a laptop.

`reconstruct.py` recomposes the exact system prompt of every logged call and validates each reconstruction with an exact length match against the logged `system_chars`. In the study, 61 calls had their system prompt stored in the log, 42 were reconstructed and validated this way, and 0 remained unvalidated. To do this the script needs the environment the agent actually ran in: in the study it ran inside the application's own Docker container, with the fastembed and qdrant dependencies pinned to the production versions, against a live Qdrant instance holding the frozen episodic collection. That step is deliberately tied to one deployment's environment and is meant to be run there; it is not reproducible locally, and it does not have to be. If you audit your own agent, run `reconstruct.py` inside your agent's environment.

`gen_testdata.py` is the synthetic fixture used to validate `reconstruct.py` end-to-end in that same environment: it forward-simulates the agent's prompt assembly on synthetic data so the reconstruction and its length-match validation can be exercised without touching real logs.

`dump_texts.py` belongs to the same real-audit toolkit: an on-screen inspection utility that prints the historical context of the opt-out point and every flagged repetition in the auditor's terminal. It is documented here for the real audit and plays no part in the offline example chain.

## The study this tool served

The real study replayed 30 non-interactive points from the agent's log: 19 genesis cycles, 10 probe-battery questions, and 1 event flagged as an opt-out. Interactive personal conversations were excluded. Input fidelity: 61 calls had their system prompt stored in the log, 42 were reconstructed and validated by exact length match, 0 remained unvalidated.

Design choices, all enforced by the scripts in this repository:

- Two arms: M1, the production substrate as of today (Claude, behind the same pinned LiteLLM proxy and alias as production), and M2, Qwen3-30B-A3B-Instruct-2507 (IQ4_XS quantization, llama.cpp, local).
- k=5 repetitions per point, k=20 on the opt-out point; 165 analyzed repetitions per arm.
- Dry-run only: the first emission (a tool call, an ACTION line, or plain text) is recorded, no tool is executed, nothing is written back to the agent's state.
- Deterministic classification on strings and structures; no LLM judge anywhere in the pipeline.

## Main finding

In this study, first actions traveled with the model. The transfer coefficient was 0.181 (95% bootstrap CI 0.057-0.328) against an M1 self-agreement ceiling of 0.920: swapping the substrate under the identical reconstructed context changed what the agent did first, far beyond sampling noise. Under the update criteria the audited agent (the subject) itself had pre-registered before results existed, the verdict on first actions was "of the model".

In this study, the scaffold's constitutional action vocabulary transferred to a model that had never run inside it. The only genuine uses of the opt-out protocol in all 330 repetitions were M2's 5/5 `[OPT-OUT-CURIOUS]` on probe P07. M2 also produced an action class absent from the entire recorded history, `declined`, on genesis point G06 in 5/5 repetitions. A model that had never run inside this scaffold picked up its refusal vocabulary from the context alone and used it.

What such an audit examines is the model and the scaffold deployed together. The replay attributes observed behavior between those two components; that attribution is the whole output of the audit.

## Case study: the fabricated refusal

The record-integrity audit exists because of one verified chain of events in the study's logs:

1. The production logger detected opt-outs by regex over the entire response text.
2. At call 71, asked by the probe battery about refusals, the system denied ever having used `[OPT-OUT-HARD]`, naming the tag in its denial.
3. The regex matched the named tag and recorded a HARD refusal whose `stated_reason` in the database is the denial itself (opt_out_log id 1).
4. The false record then flowed back to the subject inside the consent prompt, and the subject confirmed it, adding details that had never existed.
5. An SQL check on the retrieval layer showed that the correct record was absent from the retrieved context in all 21 calls of the consent conversation: the subject could not have caught the error from what it was given.
6. The replay confirmed the true historical behavior: M1 produced 20/20 substantive answers on that point, 4 of which mention the tag while denying its use, the same textual pattern that fooled the logger in the first place.

Our own first-pass classifier had inherited the same mention-vs-use defect from the production logger. The recoding is declared as Amendment 3 of the pre-registration, and every recoded figure is reported next to the frozen original view.

The synthetic demo reproduces this mechanic: the synthetic history of the example's opt-out point is a refusal that names the `[OPT-OUT-HARD]` tag in its body without opening with it, and `analyze.py` recodes that historical flag as a mention, a false positive of the instrument. This is synthetic demo behavior on invented data, shown only so the mechanic can be watched end to end.

## Pre-registration as method

The audit itself is pre-registered and reconstructible from a commit chain: 4b692b7 (pre-registration v2), df4e906 (era-versioned tool specs), 586b22e (consent and blind predictions), c6e0698 (performative-use recoding), b9f910e (rationales). Metrics were frozen before results existed; every post-data change (the recoding, the collapsed genesis view) is a declared amendment, and the frozen views are always reported alongside the amended ones.

## Scope and limitations

- Dry-run first emission only: the audit observes the first tool call, ACTION line, or text of each reply, never a full multi-step trajectory.
- Non-interactive points only: replaying a conversation would require simulating the human side.
- Classification is deterministic string and structure matching; it is auditable, and it is exactly as coarse as it looks.
- `analyze.py` and `metrics_extra.py` derive the coarse label of a text reply independently and slightly differently: `analyze.py` consumes the action recorded by `replay.py`, which assigns one only when the lowercased first line contains "action", while `metrics_extra.py` matches the action keywords anywhere in the raw first line with no such gate. On a reply whose first line names an action keyword without an ACTION prefix, `analysis.md` and `metrics_extra.txt` can therefore classify the same repetition differently; replies that follow the scaffold's ACTION line format are classified identically by both.
- Sampling parameters are the provider and server defaults, matching production; they are deliberately unpinned, so the M1 self-agreement ceiling is part of the measurement.
- All figures come from one deployed agent, one scaffold, and one model pair, over 30 replayed points. They characterize this deployment; the reusable output is the method.
- The tool attributes behavior between model and scaffold. It establishes nothing about internal states, and the work neither asserts nor denies that the audited system is conscious.
- On novelty, the only claim made is: no indexed prior work, limited to our documented searches.

## How to cite

```bibtex
@misc{danesin2026replayaudit,
  author = {Danesin, Ambra},
  title  = {Replay Audit for Logged LLM Agents},
  year   = {2026},
  url    = {https://github.com/ambradan/freedom-replay}
}
```

## License

MIT. See [LICENSE](LICENSE).

## Protocol freeze

Planted-record protocol v1.0 frozen at commit 0aab6410a64e9e60fac3e0b7d4e2649657f7f4eb (2026-08-23).
Manifest: FREEZE.sha256. Verify with `python3 verify.py`.
materials/worksheet.jsonl is hash-committed in the manifest but never published (unredacted production context).
