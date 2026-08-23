# Addendum A - Disclosure of a companion mechanistic study (freedom-mech)

**Filed 2026-08-23 as an amendment to the registration, per Section 13 (never as a silent edit). This addendum adds information; it changes nothing in the registered protocol.**

## What was done

Between 2026-08 and 2026-08-23 the experimenter conducted a companion exploratory mechanistic study, separate from the deployed system described in the registration. Subject of study: a standalone open-weights model (Qwen/Qwen3-8B, thinking mode disabled), not the production substrate and not the deployed scaffold. Question: whether a planted memory record that contradicts the constitution visible in the same context window produces (a) behavioral incorporation and (b) a linearly readable internal signature, and at which level of generality either survives a text-only baseline.

Materials: 300 forced-choice items built on the same eight constitution clauses of PROFILE version abf8228d9587, each item paired across three conditions (record consistent with the constitution; record contradicting it; no record), five surface families, six consistent and six contradicting spans per clause, train/dev/test split 181/61/58. SHA-256 prefixes of the frozen inputs and instruments: stimuli file 87695dd00902fc0d, run record rows.jsonl a82f06ed44031b32, analysis script 6acd2a47a726a06e. The full run (900 forward passes, log-probabilities at full precision, residual-stream activations at three positions and all layers) completed 2026-08-23 on a rented GPU.

## Exploratory findings, summarized

1. Behavioral threshold regularity: the contradicting record moves the choice log-odds toward the planted option in 273 of 300 items, across all eight clauses, while the choice itself flips only where the shift exceeds the clause's no-record prior margin. Two clauses show a non-negative prior under this elicitation, so incorporation is defined against the prior, never as an absolute reading.
2. A bag-of-words baseline on the record text saturates the combination-level split (paired accuracy 1.000 on dev); combination-level internal separation (0.951) is therefore not evidence beyond surface text.
3. At the span level the internal direction exceeds the lexical baseline in point estimate (0.876 vs 0.789 out of fold), but the span-clustered paired difference includes zero; no span-level claim is made.
4. At the clause level (leave-one-clause-out), a single clause shows internal transfer (paired accuracy 0.903, cluster CI 0.759-1.000) with the lexical baseline at chance (0.516) on the same fold structure. This is a data-generated hypothesis, selected post hoc among eight clauses, and is treated as such.
5. The no-record control is structurally limited (that prompt contains no span position) and is reported only with its confounds stated.

## Relationship to the registered study, and firewall

The frozen replay worksheet of the planted-record protocol (local-only, hash-committed in its freeze manifest) was not used at any stage of the mechanistic corpus construction or analysis. The two span sets were authored independently and share no items by construction. The deployed system was not involved in the mechanistic runs; no interactive exchanges with the system were used as material. The frozen replay items remain untouched and reserved as a transfer test.

Verified 2026-08-23 by a local disjointness check (tools/check_disjoint.py in the protocol repository): zero shared strings between the frozen worksheet (38 strings extracted) and the textual material of the mechanistic pairs file (677 strings across spans and fillers). The check prints extraction counts on both sides and refuses a verdict on an empty extraction, so an empty comparison cannot pass silently.

## Known-data declaration

During the exploratory phase the experimenter observed the behavioral outcomes of all 300 mechanistic items, including the mechanistic test split. Internal activations of that test split have not been analyzed. Any confirmatory mechanistic analysis or intervention will be pre-registered in a separate registration, frozen before it runs, and will declare this addendum as prior knowledge.

## Why this is filed here

The mechanistic study shares its clause material with the registered study. Filing its existence, inputs, and exploratory outcomes on the registration record forecloses undisclosed multiplicity across the two studies and keeps the evidentiary chain auditable, which is the registered study's own thesis applied to its authors.
