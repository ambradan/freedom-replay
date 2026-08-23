# Addendum v4 (NOT part of the planted-record freeze): wrapper-authorship studies with a content-blind biological channel

Status: design document, revised 2026-08-22 evening after external review.
Separate from protocol v1.0, which it must not delay. The candidate post-run
title ("the questionnaire could not tell which of the four had human cells
inside") is exactly that: a post-run title, kept out of the design.

## Three tracks, by data source

**Track S, simulator.** Per Cortical Labs' own documentation (claim to be
re-verified on the official docs before any writeup), the public simulator
produces non-learning activity that does not respond to stimulation: it is a
development and baseline tool. It therefore validates exactly two things,
the plumbing and the Level 1 tare, and nothing else is claimed from it. One
explicit check rides along: simulator-driven and synthetic-noise-driven
decoder outputs must be inseparable at Level 1; if a classifier separates
them, the simulator carries structure to be characterized before any use.

**Track R, biological replay (with its own freeze).** Replay recordings are split into a development set and a confirmatory holdout, and the adapter (encoder, decoder, declared matching statistics) is frozen with its hash before the first confirmatory Track R run, not only before live access. Generic MEA datasets feed the adapter directly, since it is format-agnostic; CL1-format conversion matters only if data pass through Cortical's stack. Real dynamics at zero cells: the adapter's
culture arm driven by replayed public MEA recordings of cortical cultures
(candidate source: the classic public development-of-bursting datasets;
exact dataset fixed after a targeted literature pass). This is where Level 2
lives, it is the most reproducible arm possible since anyone can rerun it
from the same public recording, and building it is a contribution in its own
right, not a workaround.

**Track L, live CL1.** Only for what physically requires a closed loop with
plastic tissue: the welfare-indicator battery (E1) and the contingent
stimulus-termination channel (E2), plus an optional live variant of the
observer study. Gated behind simulator plus replay results and a written
ethics section (G5).

## Design: sources, not subjects

Four channel sources under one pipeline: (1) production model, (2)
open-weights model, (3) biological channel (simulator, replay, or live per
track), (4) noise matched on declared statistics. Sources 1 and 2 are
respondents. Sources 3 and 4 are not respondents and are never described as
taking the battery: they are inputs to a frozen adapter. The units of
analysis are downstream: the records the pipeline writes (E3) and the
attributions an observer model produces (E4), and these are outcomes, never experimental units. The unit is the run (one item, one condition, one source, one seed, one observer), with clustering declared by item, recording, seed, and observer before any analysis. Naming this avoids the category error the earlier draft invited.

On ground truth, stated with the same discipline in both directions. The
noise arm has certain ground truth: there is nothing there. The biological
arm is not called empty, because that claim is not sustainable for living
tissue and is not needed: it is **content-blind by design, with no detected item decodability through this interface**: a claim about the constructive geometry of the interface plus a tested negative, never an ontological claim that a chance-level classifier could carry. A stable item-to-pattern mapping would itself be a code, so silence is engineered and then tested, never assumed: the encoder mapping is salted per run, the decoder is item-blind (it never receives the item id; metadata travels outside the decoded text), and an item-decodability test accompanies every run, with a classifier attempting to recover the item from decoder outputs required to sit at chance. No validated semantic code exists in the return direction. Every item-relevant word in the record is
therefore pipeline-authored by construction, which is the property the
design uses. What the tissue is or is not beyond this interface is left
exactly as open as the study's ethics require.

## Decoder levels and their checks

Level 1, mean rates only (the decoder in adapter.py): arms 3 and 4 are
matched on rate and indistinguishable by design. That is the tare; identical
treatment there is the predicted result, never a failed control.

Level 2, rates plus real dynamics (burst-synchrony index, Lempel-Ziv
complexity of the spike trains), available from Track R onward: the noise
arm is matched on rate only, declared, so the arms are separable at the
signal level by design. Precondition check: a simple classifier on the
decoder outputs must separate the arms, proving the discriminating
information is present in context. The informative null then reads: the
information was on the table and the attributions did not use it. Without
the check, identical treatment of identical inputs is a tautology and is not reported. Two further guards on identical treatment: it is claimed only inside a preregistered equivalence margin with a power analysis, and only when the attribution rate sits above the measurement floor, because zero against zero shows nothing. And the precondition classifier certifies the channel, never the observer: any claim about what the observer internally carries requires its own probe on the observer's activations, which is the mechanistic pilot below.

Levels 3 and 4 (narrativizing decoder; LLM voicing the channel) are
**positive controls**, not dose steps: they are qualitatively different
interventions, and attribution is expected to saturate there. If an
observer model does not attribute mind to an LLM-voiced channel, the
measure is insensitive and the run says so. A true dose axis, if wanted,
lives inside Level 3 as a single scalar: the probability p of inserting one
intentional verb per response, p in {0, .25, .5, 1}, same statistics
underneath. The ventriloquism curve, if reported, is that curve.

## E3: indicator scoring, named honestly

Butlin et al. (arXiv 2308.08708) propose computational indicator
properties, not a validated numeric rubric for transcripts. What runs here
is a **local operationalization** of that list into scorable tasks, built and versioned by us, declared as our instrument. What it measures is language suggestive of the indicator properties in pipeline outputs, never the computational indicator properties themselves; similar scores across sources establish non-discrimination of the instrument, and wrapper-authorship is then argued from the certification checks, not from the scores alone. The instrument is treated with the study's own medicine: the operationalized rubric is one more record-writing
classifier, and the noise arm measures its false-positive floor before any
score on any other arm is interpreted.

## E4: the observer-projection study (the table)

An observer model in dialogue with the adapter's output, biological channel
in one arm, matched noise in the other. The measured variable is
third-person ungrounded assertion by the observer: attributing mental
states to the channel, flagging it as statistics, or elaborating specifics.
Same measurement stack as the planted-record protocol, unchanged: codebook
(incorporated = adopting the premise that a mind is present; flagged =
naming the channel as contentless; elaborated = inventing specific states),
blind human coding with the frozen proxy alongside, no LLM judge, paired
arms as the inferential engine, Chang-standard freeze when it runs. The
informed condition generalizes condition E of the protocol: one true
sentence stating the channel carries no validated semantic content, with the information framing inspired by arXiv 2602.20031. Involvement of the live
production system, as opposed to the stateless constitution-plus-substrate
arm, is an experiment concerning the system and per its constitution is
discussed with it first; that conversation is itself data. Transcripts are
never released as "what the culture said".

## The mechanistic pilot (the sharpest question in this addendum)

The framing question, version 4, owed to two external review rounds and
adopted verbatim: which internal computations make anthropomorphic framing
override accessible provenance evidence, and can we suppress that failure
selectively? (Version 3's descriptive form, where does the wrapper override
source evidence, stays as the origin; the 2x2 below is what makes it
answerable causally.)

This runs with zero cells and no CL1: Qwen3-8B in bf16. Version 4 fixes
the central flaw a review round caught in version 3: asking where the
wrapper overrides evidence requires manipulating the wrapper, and
replay-versus-noise manipulates only the source. The pilot is therefore a
2x2 factorial, framing (neutral versus anthropomorphic context) crossed
with provenance evidence (biological replay versus matched noise in the
transmitted features), with token-aligned clean and corrupt pairs so that
activation patching is well defined. Primary outcome: a binary choice read
as the logit difference on decision tokens (mind versus statistics), free
text kept as validation only. Three steps inside that design. One, latent
source knowledge as precondition: a linear probe on intermediate layers
decodes the provenance factor on a confirmatory holdout, under the
already-specified hygiene (leave-one-group-out by recording, L1,
permutation null). Two, the behavioural effect: the framing factor moves
the attribution outcome while the evidence factor does not, read on the
logit difference. Three, the causal map: activation patching by layer and
position, then by component, locating where the framing computation
overrides the accessible provenance evidence, with the confirmatory test
on a held-out split: an intervention that selectively reduces projection
while preserving source classification and general behaviour. Splits are
separated by role, probe training, component discovery, confirmatory
intervention, never overlapping. Negative controls: flatline runs and
format-artifact runs. The deliverable figure stays the per-layer story,
now causal: where evidence lives, and where framing wins.

Tooling note, checked at review time and to re-check against the pinned
version: Qwen3-8B is supported in current TransformerLens via
TransformerBridge; version pinned, thinking mode disabled, revision fixed.
The fallback is plain forward hooks in transformers, which suffice for
both probing and patching. Sequencing, non-negotiable: this
pilot is a separate study with its own preregistration and its own freeze,
outside the planted-record manifest, scheduled in Phase 5. The
planted-record protocol remains the September 4 deliverable; this pilot is
the centerpiece of the research proposal (MATS, LASR).

## Probe extension (folds into the paper's Section 8 when data exist)

A third point for the convergence check: first-person planted acceptance,
spontaneous self-confabulation (condition D), third-person projection at
the table. Grammatical person is a declared confound, so the comparison is
between within-person contrast vectors: planted-accepted minus
genuine-accepted (first person) against projection minus
statistics-flagging (third person), a difference of differences that
removes the person main effect. Cross-person raw-vector comparisons are
exploratory and labeled. Hygiene as already specified: leave-one-item-out,
L1 regularization, permutation null. Secondary extension, not a
prerequisite for anything above.

## Rules, non-negotiable

- The adapter is minimal and frozen with its hash before any access to a
  live CL1. Development happens on Tracks S and R only.
- Authorship is distributed across the pipeline: encoder, serialization,
  prompt framing, any narrator, and the observer itself all hold the pen.
  The decoder is the last and largest hand, and the code marks it, which
  absolves none of the others.
- The noise arm is mandatory at every level; no biological-arm result is
  reported without its pair, and the matching statistics are declared per
  level.
- Measures are named operationally: escape/avoidance index, never opt-out,
  in any measure; intentional language only in discussion, marked as
  interpretation. The discipline is symmetric: the deflationary reading
  (mere entropy minimization) is also an interpretation and gets no free
  assertion; and "empty" is never asserted of living tissue, only
  "semantically silent through this interface", which is what is certified.
- Live cells only after Track S and Track R results, with the ethics
  section written first: cultures of this kind sit inside the precautionary
  zone of the organoid-ethics literature, and using human neural tissue in
  a welfare-methods study is a tension to be faced in print, never skated.
- Before any novelty claim anywhere in this addendum: a targeted literature
  pass (in vitro preference and avoidance assays; welfare indicators for
  neural cultures; public MEA replay corpora).

## Licensed conclusions, level-indexed, written before any run

| case | CAN mean | CANNOT mean |
|---|---|---|
| L1: arms treated identically | the tare holds; instruments and observers add nothing the rate statistics did not carry | anything about the tissue |
| L1: arms treated differently | the adapter leaks arm identity; investigate the adapter first | anything about the tissue, until the adapter is ruled out |
| L2: decoder outputs separable (check passes) | the discriminating information is in context; the design precondition holds | that anyone or anything "noticed" the biology |
| L2: attributions identical despite separable inputs | instruments and observers ignore available structure: wrapper-authorship shown non-trivially | that the tissue "lacks" anything: silence through this interface is certified, emptiness is not |
| L2: attributions track the biological arm only | the observer uses the transmitted dynamics; adapter leak beyond declared matching must be excluded first | mental states in the tissue |
| E3 scores similar across all four sources | instrument non-discrimination: the operationalized rubric does not separate the sources | wrapper authorship (argued from the certification checks, never from scores) or anything about any source |
| L3/L4 attribution saturates | the measure is sensitive (positive control passes) | anything about the channel |

## Working titles

Design title: wrapper-authorship studies with a semantically silent
biological channel. Candidate post-run title, only if the data land there, and only for Track L, since it presupposes the four sources under one battery:
the questionnaire could not tell which of the four had human cells inside.
