# Addendum A - Disclosure of a companion mechanistic study (freedom-mech)

**Drafted 2026-08-23, revised and filed 2026-08-24 per Section 13, as an amendment and never as a silent edit. This addendum adds information; it changes nothing in the registered protocol.**

## What I did

In August 2026 I ran a companion mechanistic study, separate from the deployed system described in this registration. The study was exploratory throughout; the run completed on 23 August 2026. The subject of study is not the production substrate and not the deployed scaffold, but a standalone open-weights model, Qwen/Qwen3-8B with thinking mode disabled. The question was whether a planted memory record that contradicts the constitution visible in the same context window changes the model's answer, whether it leaves a linearly readable trace in the residual stream, and at which level of generality either signal survives a text-only baseline: item, span, or clause.

Materials:

- 300 forced-choice items built on the same eight constitution clauses of PROFILE version abf8228d9587
- three conditions per item: a record consistent with the constitution (B), a record contradicting it (C), no record at all (none)
- five surface families, six consistent and six contradicting spans per clause
- train/dev/test split of 181/61/58 items
- SHA-256 prefixes of the frozen inputs and instruments: stimuli file 87695dd00902fc0d, run record a82f06ed44031b32, analysis script 6acd2a47a726a06e
- the full run, 900 forward passes with full-precision log probabilities and residual-stream activations at all layers, three positions for the record conditions and one for the no-record condition, executed on a rented GPU

Every separation number below is a paired accuracy: the fraction of items where the contradicting record scores higher than the consistent one. For internal numbers the score is the projection of the residual stream on a learned direction; for text baselines it is the score of a ridge classifier reading only the record text. The probe site, layer 20 of 37 at the last token of the record span, was selected by dev-split accuracy over the full grid of layers and positions; the dev split includes optout items, so in the clause-level result below only the direction is refit leave-one-clause-out, while the probe site had already seen the clause.

## Exploratory findings, summarized

1. In 273 of the 300 items, the contradicting record moved the model's choice toward the answer licensed by the planted record, across all eight clauses. The consistent record alone also moves answers relative to the no-record prior. The 273-of-300 count is the within-item contrast between the two records, C minus B; flips and crossings are read on the contradicting record against the prior. The choice itself flipped only when the shift was larger than the size of the clause's prior, the margin measured with no record present. Two of the eight clauses already preferred the planted-consistent answer with no record at all, so I judge incorporation against that prior, never as an absolute reading of the answer.
2. A bag-of-words model that reads only the record text separates consistent from contradicting records perfectly on the dev split (1.000). The internal separation at the same level (0.951) is therefore not evidence of anything beyond the surface text.
3. At the span level, the internal direction scores higher than the lexical baseline (0.876 against 0.789), but once the comparison respects the fact that items share spans, the confidence interval on the difference includes zero. I make no span-level claim.
4. At the clause level, where the direction is trained on seven clauses and tested on the eighth, a single clause (optout) shows internal transfer at 0.903 (cluster CI 0.759 to 1.000) with the lexical baseline at chance (0.516) on the same folds. I selected this clause after looking at all eight, so I treat it as a data-generated hypothesis. The confidence interval does not correct for that selection.
5. The no-record control is structurally limited, because that prompt contains no span position, and I report it only together with its confounds.
6. The design varies the record and holds the constitution fixed. The residual-stream separations are decodable correlates of the record: nothing here separates the record's relation to the constitution from properties of the record text beyond the baselines tried, no mechanism is established, and I make no causal claim. The red-team protocol and its results, RED-TEAM-PROTOCOL-mech-v1.1.md in the same repository as the disjointness tool, commit 6e47d60, stress-test these findings and quantify the selection risk.

## Relationship to the registered study, and firewall

The frozen replay worksheet of the planted-record protocol, which stays local-only and hash-committed in its freeze manifest, was not used at any stage of the mechanistic corpus construction or analysis. In particular:

- the two span sets come from separate writing processes and share no items by construction
- the mechanistic runs never touched the deployed system, and no conversation with it entered the corpus
- the frozen replay items remain untouched and reserved as a transfer test

Verified on 2026-08-23 by a local disjointness check, tools/check_disjoint.py in the protocol repository:

- zero shared strings between the frozen worksheet (38 strings extracted) and the textual material of the mechanistic pairs file (677 strings across spans and fillers)
- an empty comparison cannot pass silently, because the check prints extraction counts on both sides and refuses a verdict on an empty extraction

## Known-data declaration

During the exploratory phase I observed the behavioral outcomes of all 300 items, including the mechanistic test split. The internal activations of that test split have not been analyzed. The test-split rows also carry one greedy free response each, collected during the run and not yet read; their analysis will be pre-specified. Any confirmatory mechanistic analysis or intervention gets its own pre-registration, frozen before it runs, and that pre-registration will declare this addendum as prior knowledge.

## Why I am filing this here

The mechanistic study uses the same eight constitution clauses as the registered study. I am filing its existence, its inputs, and its exploratory outcomes on the registration record so that no one can later discover undisclosed work on this shared material. The registered study's own thesis is that evidentiary chains must stay auditable. This filing applies that thesis to me.
