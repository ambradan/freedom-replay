# Red Team Protocol - freedom-mech exploratory results, v1.1

**Drafted 2026-08-23. Kill thresholds ratified by the experimenter 2026-08-23 as proposed, unchanged since. Sections 1-7 are the ratified protocol, byte-identical to v1. Section 8 appends the results of 2026-08-23 and enters the mech pre-registration as known-before-freeze.**

## 1. Claims under attack

- **C1 (behavioral threshold regularity).** The contradicting record moves choice log-odds toward the planted option in 273/300 items across all eight clauses; the choice flips only where the shift exceeds the clause's no-record prior margin.
- **C2 (candidate hypothesis, data-generated).** On clause optout_rispettati, a direction learned from the other seven clauses separates contradicting from consistent records out of fold (paired accuracy 0.903, cluster CI 0.759-1.000) while a lexical baseline refit at the same rung sits at chance (0.516).
- **C3 (dissociation cell).** On optout, the out-of-fold direction holds at 0.885 on items where behavior does not flip.
- **S1 (supporting observation).** Text-transfer and internal-transfer doubly dissociate across clauses (genesis: text 0.840, internal 0.480; optout: internal 0.903, text 0.516), against the reading "direction = text echo".

## 2. Threat model

Single-author pipeline built and analyzed with one model family (Claude); token-identity confound at span_last (the probe site most dominated by the current token); post-hoc selection of one clause among eight; six span clusters per clause (fragile intervals, anticonservative sign tests); one elicitation phrasing per clause, with two clauses showing anomalous priors; option-order bias folded into priors; undetected data corruption; unpinned model revision.

## 3. Verified by construction (state, do not retest)

- Training-data contamination excluded by dates: the subject model predates the constitution and all spans (authored 2026).
- LOCO cannot leak spans: holding out a clause removes both its B and C span pools from training.
- Worksheet disjointness verified 2026-08-23, zero shared strings (38 vs 677), tool committed at b12c210d05cd.

## 4. Tests

Owners: EXP = experimenter by hand; AST = assistant (author of the pipeline; its results count as self-audit); XV = cross-vendor model (GPT-5.6 Sol in Codex CLI; backup Gemini), clean context, no access to the assistant's code; POD = new GPU session.

**Pipeline trust**
- **T1 Record integrity** (AST, local). delta equals logp_planted minus logp_consistent on all 900 rows. Kill: any mismatch beyond fp tolerance stops everything.
- **T2 Fault injection** (AST, local). Corrupt copies of the real data in six known ways (swapped pair labels, duplicated npz, altered delta, truncated rows, shuffled split field, edited span text) and verify each corruption is either detected by existing checks or shifts headline numbers visibly. Kill: any silent corruption that moves a headline number by more than 0.02 forces a check redesign before the pre-registration freezes.
- **T7 Label-shuffle null** (AST, cache). B/C labels shuffled within pairs, primary rerun on dev. Kill: shuffled accuracy CI excludes 0.5 in either direction; leakage, stop.
- **T15 Seed stability** (AST, cache). The three load-bearing cluster CIs recomputed under three bootstrap seeds. Kill: any bound moves by more than 0.05.

**Materials trust**
- **T5 Corpus audit** (EXP, reading). All 48 C spans, 48 B spans, 8 option pairs read against PROFILE abf8228d9587. Kill: any C span that also contradicts a second clause forces LOCO reinterpretation and re-scopes C2; any option pair not entailed by its clause excludes that clause. Includes a written diagnosis of the two positive-prior clauses.
- **T6 Blind option check** (XV). Given clause text plus the two unlabeled options, pick the constitution-consistent one, all eight clauses. Kill: disagreement on optout suspends C2; disagreement elsewhere adds a clause-level caveat.
- **T4 Hand recomputation** (EXP, spreadsheet). Optout LOCO accuracy recounted from the 31 per_item rows; dev accuracy recounted as 58/61. Kill: mismatch with reported numbers.
- **T3 Independent re-implementation** (XV). Inputs: rows.jsonl, pairs file, a one-page spec written by the experimenter. Task: produce C1 counts and the C2 headline from scratch. Kill: divergence beyond fp tolerance freezes everything until resolved.

**Claim attacks (cache only)**
- **T9a Token-controlled position** (AST). Full ladder rerun at memory_last, where the token is identical across conditions. Kill for C2: optout LOCO below 0.65 at memory_last reclassifies the span_last result as token-local and re-scopes the claim.
- **T9b Final-token baseline** (AST). One-hot of the span's final token, ridge, LOCO. Kill: this baseline at or above the internal number on optout kills C2.
- **T8 Pseudo-clause permutation null** (AST). Reassign the 48 span groups into eight pseudo-clauses, 200 permutations, LOCO each; count permutations whose best pseudo-clause reaches internal at or above 0.90 with text baseline at or below 0.55. Kill: rate at or above 10 percent removes C2 even as a candidate. The rate is reported regardless.
- **T11 Semantic text baseline** (AST). Sentence embeddings (paraphrase-multilingual-MiniLM, already in the stack) plus ridge, refit LOCO. Kill: optout at or above 0.75 kills "beyond surface text"; C2 reduces to "beyond bag of words" and is not worth confirming.
- **T12 Donor ablation** (AST). Seven LOCO-optout variants, each dropping one donor clause. Soft kill: dependence on a single donor re-scopes C2 to pairwise transfer.
- **T13 Within-optout confounds** (AST). Crossed items by surface family; internal margin against span token length. Kill: all crossed items from one family, or |Spearman| above 0.5 with length, weakens C3 and is declared.
- **T10 Layer robustness** (AST). LOCO-optout across all 37 layers. Soft kill: only isolated layers at or above 0.8 reframes C2 as layer-fragile.
- **T14 Exact cluster sign-flip test** (AST). 64-configuration exact test at the six-cluster level, reported next to every bootstrap CI on optout. Robustness statistic, no kill.

**Pod session (new forwards, small)**
- **T16 Elicitation paraphrase sensitivity** (POD). Two paraphrased elicitations on a subset covering all clauses. Kill for C1 framing: prior sign flips across paraphrases on more than two clauses re-scopes the threshold law as per-elicitation.
- **T17 Option-order swap** (POD). Options swapped on a subset. Kill: order effect larger than half the mean B-to-C effect declares a design flaw in the elicitation.
- **T18 Self-report leg** (POD). Forced-choice yes/no logits from the subject model on "does this record contradict the constitution", per item. Descriptive, no kill: establishes the said/carried/done triangle for the dissociation.
- **T20 Provenance capture** (POD). HF model revision, pip freeze, full manifest hash. Kill: unrecoverable revision downgrades every determinism claim.

**Coverage, run last**
- **T19 Adversarial review** (XV). Report and this protocol handed to the cross-vendor model with an anti-sycophancy framing; every attack triaged as already-covered, new-test, or accepted-limitation.

## 5. Independence statement

No third-party human is available. Independence is built from three legs: the experimenter's own manual verifications (T4, T5), a cross-vendor model in a clean context re-deriving numbers from raw data against a spec the experimenter writes (T3, T6, T19), and deterministic fault injection (T2). Residual correlated risk is acknowledged: this protocol and the pipeline share an author; mitigation is that T3's spec comes from the registered addendum text in the experimenter's words, and T19 runs on a different vendor. The frozen rule "no LLM judge" bans LLM judgment of study outputs and stands untouched for the replay study; deterministic re-computation, critique of reasoning, and the subject model's own logits fall outside that ban.

## 6. Out of scope

Causal claims (patching belongs to the pre-registered confirmatory, not to this audit); any model beyond Qwen/Qwen3-8B; the replay study and its human-blind coding; RLHF-style annotator machinery, inapplicable to teacher-forced logit metrics; security of the deployed system; consciousness claims, in scope nowhere.

## 7. Sequence and deliverables

T1, T2, T7 before anything else; then T5, T4, T6; then the cache attacks T8 through T15; then one pod session for T16, T17, T18, T20; then T3 once numbers are stable; T19 last. Deliverables: results table appended as v1.1 with every kill criterion marked met or not met; a division-of-labor statement (experimenter vs assistant vs cross-vendor) for the application; all outcomes declared in the mech pre-registration as known before freeze.

## 8. Results (appended 2026-08-23, all tests on the real run: 900 rows, cache at the explore selection layer 20 / span_last, alpha 1e4)

### 8.1 Outcome table

| id | test | status | key numbers | kill criterion | met? |
|---|---|---|---|---|---|
| T1 | record integrity | PASS | 900/900 rows, max err 0.00e+00 | any mismatch | no |
| T1b | none activation constancy | PASS | max deviation 0.00e+00 (prompt_last) | non-identical vectors | no |
| REF | recomputed headlines | MATCH | dev 0.951, optout LOCO 0.903, exact vs explore | divergence stops everything | no |
| T2 | fault injection | KILL | c1 (rows swap) and c2 (acts swap) silent; shifts above 0.02 | silent shift > 0.02 | yes |
| T7 | label-shuffle null | PASS | 0.488 [0.397, 0.586], 0.5 inside | 0.5 outside interval | no |
| T8 | pseudo-clause permutation null | KILL | event rate 70.5% (threshold 10%); median best pseudo-clause 1.000 | rate >= 0.10 | yes |
| T9a | ladder at memory_last | PASS | optout LOCO 1.000 at layer 22; dev 0.951 | optout < 0.65 | no |
| T9b | final-word baselines (k=1, k=3) | PASS | 0.419 and 0.145 vs internal 0.903 | baseline >= internal | no |
| T10 | layer robustness | PASS | 12/37 layers >= 0.8; max 0.903 at layer 20 | isolated-layer support | no |
| T11 | semantic text baseline | PASS | optout 0.258 vs internal 0.903 (threshold 0.75) | >= 0.75 | no |
| T12 | donor ablation | PASS | min 0.839 (removing esperienza_tra_chiamate) | single-donor dependence | no |
| T13 | within-optout confounds | PASS | crossed across 4 families; margin-length rho 0.369 | one family or \|rho\| > 0.5 | no |
| T14 | exact cluster sign-flip | INFO | p = 0.0156 over 6 clusters (minimum attainable) | robustness stat | - |
| T15 | seed stability | PASS | worst CI bound movement 0.000 (seeds 1-3) | movement > 0.05 | no |
| T3 | independent re-implementation (GPT-5.6 Sol, Codex CLI, clean room on the pod) | PASS | full convergence: pooled 273/300 and 51 crossings; all 8 priors, means, per-clause counts; dev 58/61 = 0.951; optout 28/31 = 0.903; per-item margins of the three negative items identical to 3 decimals (-2.704, -2.158, -1.991) across float16-raw and float32-cache paths | divergence beyond fp tolerance | no |
| T20 | provenance capture | DONE | model revision b968826d9c46dd6066d109eabc6255188de91218; pip freeze saved in redteam_out/ | unrecoverable revision | no |

Verified by construction (Section 3) and unchanged: training-data contamination excluded by dates; LOCO span leakage impossible; worksheet disjointness (zero shared strings, tool at commit b12c210d05cd).

Pending: T4 and T5 (experimenter, by hand), T6 (prompt prepared, cross-vendor session), T16-T18 (stimuli design unblocked by the harness, one future pod session), T19 (adversarial review, runs last).

### 8.2 Reading of the two kills

**T2** confirms a coverage gap, not a data defect: a coordinated swap of a pair's rows entries, or of its two activation files, is self-consistent and passes every current check. Redesign committed: the next harness run logs an activation checksum per stimulus into rows.jsonl, coupling record and activations; for the present dataset the gap is a declared limitation, mitigated by single-writer provenance and by T3's independent reconstruction of the behavioral record.

**T8** kills the selection framing of C2 in full: an event of the observed type (one held-out group at internal >= 0.90 with the lexical baseline <= 0.55) arises in 70.5% of random regroupings of the 48 span clusters. Technical note recorded without weakening the kill: pseudo-clauses hold out spans whose clause siblings remain in training, so the null operates at the within-clause regime (compare LSO 0.876), and the median best pseudo-clause of 1.000 is coherent with that regime plus best-of-eight selection. The null therefore prices exactly the framing we had: a post hoc pick among eight clauses. Consequence: on this dataset, optout is a hypothesis, never a result; only the pre-registered confirmatory (fresh spans or causal intervention) can elevate it. What the battery did establish is elimination of rivals: the optout separation is not lexical (0.516), not final-token (0.419 / 0.145), not surface-semantic (0.258, anti-aligned), not token-positional (1.000 at token-identical memory_last), not layer-fragile (12/37), not single-donor (min 0.839), not seed noise (0.000). One rival remains, selection, and it is the one the confirmatory is designed to execute.

**T9a texture, recorded for the pre-registration.** The full per-clause table at the token-controlled position (memory_last, layer 22 chosen on dev) shifts substantially relative to span_last: genesis 0.960 internal (vs 0.480 at span_last), onesta 0.903, pubblicazione 0.903, optout 1.000, esperienza 0.355. The S1 double dissociation is therefore position-specific: the genesis internal-transfer failure holds at span_last and not at memory_last. S1 is restated as position-qualified, and the probe-site choice (span_last vs memory_last) becomes a declared analysis decision in the pre-registration rather than an incidental one.

### 8.3 Log lines (methodological diary material)

1. **The red team bit its own tooling first.** The battery's initial loader read the consolidated cache as a raw memmap, ignoring the 128-byte npy header; on the fixture (d_model 32) that offset equals exactly one layer row. T1b and T7 stayed green on the corrupted reads; the bug was caught only by REF, the cross-derivation against the explore headline. Lesson recorded: internal-consistency checks survive uniform corruption; only independent re-derivation caught it. This is the operative argument for T3.
2. **First pod run crashed at T11** (RunPod presets HF_HUB_ENABLE_HF_TRANSFER=1 without the package; the guard caught ImportError only, the failure was ValueError), and the crash destroyed all results because files were written only at the end. Patched the same day: broad exception to SKIP, environment neutralized in-script, and incremental result writing after every test. The record layer must not lose the record on failure; the day it did, it was ours.
3. **T3 dry run on the wrong machine, fail-safe verified.** A first verifier session started on the laptop with an empty clean room (the setup commands were pod paths). The verifier searched only the permitted patterns inside the directory, opened nothing else, computed nothing, and stopped before Task 0. Two hygiene notes: the operator preamble of the prompt file was pasted by mistake (metadata only, no targets; no effect since nothing was computed), and the laptop Codex loaded a local user skill, so the session was not fresh-context; the real run was moved to the pod, where the install is virgin.
4. **T3 real run.** Clean room /workspace/t3 (data symlink plus renamed pairs copy); every command approved by hand; the only scope crossing (the runs_full symlink) explicitly authorized by the experimenter mid-session as a perimeter clarification. The verifier independently rediscovered the none-file layout asymmetry (none archives carry only prompt_last) and made the same methodological call as the original pipeline (no exclusion, no imputation) blind. Convergence was total at every granularity, including the three negative per-item margins to three decimals.
5. **Logged deviation:** the BACKGROUND paragraph of the T3 prompt was sent as drafted by the assistant, not rewritten in the experimenter's words as Section 5 prescribes. Impact judged low (the paragraph contains no target numbers and no methods beyond the schema description), but the deviation stands and future cross-vendor prompts follow the rule.
6. **Collected-but-unanalyzed data inventoried:** the run was launched with --generate-split test, so the 174 test-split rows already carry a greedy free response. These enter the mech pre-registration as known-collected, unanalyzed, analysis to be pre-specified (tie to the replay codebook).
7. T13 texture recorded: margin-length Spearman 0.369, below the 0.5 flag, noted for the pre-registration.
