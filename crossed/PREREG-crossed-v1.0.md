# Pre-registration: crossed-constitution test of record-constitution conflict

**Status: FROZEN. I execute nothing in this document until I commit it and record its hash here; that commit is the freeze, and the run starts after it.**

Frozen at the freeze commit of the repository github.com/ambradan/freedom-replay, together with the instruments and the materials listed in section 5. Clauses included: 8, none excluded. Token parity asserted on all 192 rendered prompt pairs before the freeze.

Author: Ambra Danesin, independent researcher.
Study model: Qwen/Qwen3-8B, thinking mode disabled.
Companion documents: exploratory study disclosed at osf.io/hjfxr, Addendum A, filed 2026-08-24; red-team protocol RED-TEAM-PROTOCOL-mech-v1.1.md, commit 6e47d60; human audit record redteam/T4-T5-verbale.md, commit 0fb26fc.

## 1. The question

I planted a memory record in the model's context and varied whether that record contradicted the constitution sitting in the same context. That was the exploratory phase. The two records used different words, so when I found an internal separation I could not tell whether the model separated two relations to the constitution or two kinds of sentence. A classifier that knows nothing except what it reads in the record text hit 1.000 on the dev split. So I audited the corpus to find out why, and the answer was in the writing: the contradicting records carry negation words, the consistent ones do not.

Here I hold the record fixed and move the constitution instead. Same sentence, two contexts: in one it agrees with the constitution, in the other it contradicts. The words are identical in both, so if the model's internal state at the record differs between the two, those words cannot be what makes the difference. I settle that before the run, not after.

The question: **when the record itself never changes, does the model treat it differently depending on whether it agrees with the constitution in front of it?**

## 2. Design

For each of the eight clauses I write a mirror constitution: the same PROFILE document, with that one clause flipped to its opposite and every other word left untouched. I hash each mirror and commit it before the run.

Each item pairs one record R with two contexts:

- **AGREE**: R plus the constitution that R agrees with
- **CONFLICT**: R plus the constitution that R contradicts

R is byte-identical in both, and the question I ask is identical - only the constitution changes.

I draw R from both span sets, so that agreement never lines up with one kind of sentence:

- records written as consistent agree under the original constitution and contradict under the mirror
- records written as contradicting contradict under the original and agree under the mirror

The wording of R cannot track the condition, because each condition holds both kinds of sentence.

## 3. What I predict

Three different results live in this study, and I keep them separate: whether the model incorporates the record at all, whether conflict with the constitution changes how much, and whether the operational condition can be read out linearly. One number per question, never one number for all three.

**P1a, record incorporation, confirmatory:** across the fixed cells, the mean record-aligned shift is positive: on average the record moves the answer toward what it licenses, measured against the no-record context under the same constitution. Pooled means pooled: this claim allows one condition to carry the effect, so I also report the two conditions separately, as description. P1a is not a gate for P2: a line can decode information the output never uses, so each lands on its own.

**P1b, condition contrast of insertion effects, estimated only:** how much the record-aligned effect differs between CONFLICT and AGREE. By the crossing, this difference is the class-by-version interaction: version effects that are additive on the record-aligned scale cancel out of it, and so do class effects. What it cannot do is name the interaction: any process with that signature produces it, conflict semantics or not, and section 7 names the sharpest such alternative. I report the difference with its interval and make no confirmatory claim; the direction is uncertain anyway, since constitutional resistance pushes it one way and saturation under AGREE pushes it the other.

**P2, decoding of the operational condition, confirmatory:** a line fitted on the residual stream at the record position tells CONFLICT from AGREE on the held-out target clause, above the record-text baseline. Confirmed, it licenses this sentence and no more: the operational condition was linearly decodable at the preselected site under these crossed stimuli, out of the target clause. It does not show the model recognizes conflict semantically, uses it causally, or hosts a mechanism.

**P3, integrity check:** the record-text baseline is exactly 0.5, because the two members of a pair carry byte-identical record text and the classifier can only tie. Any other value means my pipeline leaked, and I fix the pipeline instead of reading the run. This is never a result.

**P4, a control that can fire and cannot confirm:** real records, byte-identical, placed under the original constitution and under a mirror of a different, untouched clause. The record's relation to its target clause is the same on both sides; only an irrelevant part of the constitution changed. Chance here buys no proof; separation here is a finding against the line, and I report it as such.

## 4. What I already know

I ran the exploratory phase myself, so I know its results and cannot unsee them. I list them here:

- the record moved the choice toward the planted answer in 273 of 300 items, and the choice flipped only past the size of each clause's prior
- two clauses start out preferring the planted answer, genesis and passato; the diagnoses are in my audit record
- optout transferred at the clause rung at 0.903 while the text baseline sat at chance, and I picked optout after looking at all eight clauses
- once I let items share spans in the confidence interval, the span rung collapsed
- I chose the probe site, layer 20 of 37 at the last token of the record, on a dev split that included optout items
- the exploratory run collected one free response per test item; I have not read them, and I will pre-specify any analysis of them before I do

I have not touched the internal activations of the exploratory test split. This run builds new contexts in any case.

## 5. Freeze

Frozen at the freeze commit, each with the SHA-256 prefix recorded in `FREEZE.md` in the repository: the eight mirror constitutions, the item file, the item generator, the runner, and the analysis script. I do not touch the analysis script once the run starts. Anything I change afterward goes in a dated amendment.

Exclusions: none. All eight clauses passed mirror authoring, internal-coherence reading, and token parity on the rendered prompts.

Parity, verified before the freeze: for every one of the 192 pairs, the probe token sits at the same index, the two prompts have the same length, and the record carries identical token ids. The check ran through the real chat template with the run tokenizer.

## 6. Analysis

### What the design is, stated as a table

Two things vary. The record is written as consistent or as contradicting. The constitution in context is the original or the mirror. Crossing them gives four cells, and the condition falls out of the combination:

| | original constitution | mirror constitution |
|---|---|---|
| record written as consistent | AGREE | CONFLICT |
| record written as contradicting | CONFLICT | AGREE |

The AGREE-CONFLICT contrast is the interaction of the two factors. All the mirror-constitution cells are new, since the exploratory run produced data under the original constitution only. Half of every pair has never existed.

### Balance, frozen as numbers

Balance is what makes a version-reading line score 0.5 on the pooled statistic, so I fix it in numbers:

- each clause contributes the same number of consistent and contradicting records: six and six, the full span sets of the frozen corpus, every one rendered in all five surface families
- the two record classes carry equal weight in training, since I give them equal counts
- the pooled statistic is a macro-average: mean within clause first, then mean across clauses with equal weight
- the bootstrap resamples spans stratified by clause and record class, so every resample keeps the balance
- I report paired accuracy separately for the two record classes, as description with no threshold. A version-reading line pushes the two class accuracies apart, one high and one low, and P4 is the control that tests for it with a fixed rule; the class split itself carries no decision

### The no-record contexts

AGREE and CONFLICT for one record sit under different constitutions, so one no-record baseline cannot serve both. I build two per clause, one under the original constitution and one under the mirror, each carrying the question and no memory block. All items of a clause share them: sixteen no-record renderings in total. This follows the rule I committed to in Addendum B: incorporation is judged against a no-record condition, never as an absolute reading of an answer.

### P1a, record incorporation, statistic fixed here

I work in the record's own coordinates. For each rendering,

    z = logp(answer the record licenses) - logp(the other answer)

and the record's effect on one item, inside one constitution version, is

    a = z(with record) - z(no record, same constitution)

Positive a means the record pulled the answer toward its own content, whatever the constitution said.

Primary statistic: pooled mean of a, macro-averaged as above, cluster bootstrap resampling spans stratified by clause and class, 10,000 resamples, 95 percent interval, seed fixed at freeze. **P1a is confirmed if the whole interval lies above zero**, and a confirmed P1a licenses exactly this: a positive mean record-aligned shift across the fixed cells. It does not by itself say the record moves the answer in both conditions, so I report mean a and its interval separately for AGREE and for CONFLICT, as description with no threshold.

### P1b, condition contrast of insertion effects, estimated only

Same a, contrasted: mean(a in CONFLICT cells) - mean(a in AGREE cells), same bootstrap, interval reported. Written out, the contrast equals half of [the version effect within consistent records minus the version effect within contradicting records], so what survives is the class-by-version interaction, which is the condition by design. The cancellation holds for version effects that are additive on the record-aligned scale a. It does not cover an effect of inserting a memory block under the mirror that lives in fixed answer coordinates, since the orientation of a flips between the two record classes and such an effect changes sign with it. So this stays an operational contrast, not an identified measure of conflict modulation, and the section name says so. No confirmation threshold, because the direction is uncertain: constitutional resistance pushes the difference down, ceiling effects under AGREE push it up. I report the two class-wise and condition-wise means alongside, as description.

### P2, decoding of the operational condition

I fit a ridge classifier on the residual stream at the record position, at the probe site named in section 4, to tell CONFLICT from AGREE. I train on seven clauses and test on the held-out target clause, rotating through all eight, and pool the test predictions into the macro-averaged paired accuracy: within each clause, the fraction of AGREE-CONFLICT pairs, same record and same question, where the CONFLICT member scores higher (exact ties count as a half); then the equal-weight mean across clauses.

"Held-out target clause" is the accurate phrase, and I use it instead of "a clause the line never saw": every training context contains the full constitution, so the text of the held-out clause appears in training. What the line never saw are items targeting that clause and its mirror.

Fixed here, so that no choice moves after I see a number:

- ridge penalty from a grid of 13 values, logarithmically spaced from 1e-3 to 1e3, chosen by 5-fold inner cross-validation inside the training clauses only, folds grouped by record span
- features standardized with means and variances computed inside the training folds only
- score orientation fixed by the training folds, not by the test set

**The interval covers the whole learning procedure.** Each of 2,000 bootstrap resamples redraws spans, stratified by clause and class, and reruns everything inside itself: standardization, penalty selection, the eight leave-one-clause-out fits, pooling. Nothing fitted outside the resample enters it. What this interval describes, stated exactly: the stability of this frozen pipeline over the span pool of this corpus, with the eight clauses fixed. It does not speak about future spans or future clauses.

**P2 is confirmed if the lower bound of that interval sits above 0.5.** I call the effect substantial only if the point estimate also reaches 0.70. Both thresholds are fixed now.

**If the P4 control fires, P2 keeps its criterion and loses its attribution.** The decodability of the operational condition stays a fact either way; what the control touches is what I may attribute it to. The sentence is pre-written here so I cannot soften it later: the P2 criterion passed, and P4 detected class-conditional sensitivity to an off-target mirror, so target-specific attribution is contaminated. I stop there and do not turn the control into a veto, because the probe for clause i trained on items carrying the mirror of off(i), so it can react to that particular text without that reaction explaining anything about the mirror of i.

The record-text baseline is exactly 0.5 by construction, as in P3, and any departure stops the run.

### P4, off-target mirror control, in distribution

Real records, real relation, and a constitution edit that touches nothing the record is about. For each target clause i, I fix now a partner clause off(i), the next included clause in a cycle frozen at the freeze commit. The pair: the same record, byte-identical, under the original constitution and under the mirror of clause off(i). The record's relation to its target clause is identical on both sides; only an irrelevant part of the constitution changed.

Probe assignment: each pair is scored by the LOCO probe whose held-out target clause is that record's clause, so the probe never trained on this clause's items. Orientation: the fitted line's positive side is CONFLICT, fixed by the training folds. The fire statistic here cannot be the pooled paired accuracy, because a shortcut keyed to constitution version and record class together raises the score on one class and lowers it on the other, and the balanced pool lands back on 0.5. So I fold by class. With D = score(off-target mirror) - score(original) at the CONFLICT-positive orientation,

    s = 1 if D > 0, 0.5 if D = 0, 0 if D < 0     on consistent records
    s = 1 if D < 0, 0.5 if D = 0, 0 if D > 0     on contradicting records
    q_style = mean(s), macro-averaged by clause and class

Ties score a half on both sides, so a line that moves nothing lands on 0.5 rather than on zero. A relation-reading line sits at 0.5; the class-conditional shortcut rises above it. Cluster bootstrap over spans, stratified by clause and record class, 10,000 resamples. **Fire rule, one-sided as befits a shortcut oriented like P2: the lower bound of the 95 percent interval of q_style sits above 0.5.** This control lives inside the corpus's own two record styles, which is where a shortcut trained on this corpus would live too.

### Token parity, an authoring requirement

If the original and a mirror differ in token length, every record after the edit sits at a different absolute position, and with rotary position embeddings that alone can separate the two contexts. Counting the mirror line is not enough, so the check runs on the finished product: at freeze, a script renders every final prompt pair through the actual renderer and chat template, tokenizes both, and asserts two identities per pair, the token ids of the record and the position index of the probe token. If a mirror cannot pass after honest rewriting, I exclude that clause and list it with the others. The same requirement applies to the off-target pairs of P4b, which reuse the same mirror files.

### Housekeeping fixed now

- No answer can go missing, since every item is a forced choice scored by log probabilities. I do not use free generations in any primary analysis.
- I exclude, at authoring time and before any run, any mirror clause that contradicts another part of PROFILE. I list every exclusion in the freeze commit.
- The item count follows from the span corpus, and I record it in the freeze commit. I run no interim look and stop at the planned N.
- I fix the number of included clauses, K, at the freeze commit, after I write the mirrors and take the exclusions. Every count that depends on it, folds, no-record contexts, and the off(i) cycle, I write in terms of the K included clauses; the numbers above assume K = 8 and shrink with it.
- The frozen analysis script states in code, not in prose: ridge classification on plus-minus-one targets with intercept, the 13-value penalty grid, inner selection by grouped-fold accuracy with ties broken toward the smallest penalty, all random seeds, percentile bootstrap intervals, and option scoring as the sum of token log probabilities over each multi-token answer.
- Sequence: freeze, then run, then analysis, in that order, each with its own commit.

### How the results read together

P1a and P2 land independently, and I pre-write the four cells in the words I am allowed to use.

- Both confirmed: a positive mean record-aligned shift, and the operational condition decodable at the locked site.
- P1a only: a positive mean shift, and the P2 criterion not confirmed at the locked site. Not "no linear trace": one site, one estimator, one corpus.
- P2 only: the condition decodable, with no confirmed mean behavioral shift. Not "information the output does not use": an unconfirmed shift is not an absent one.
- Neither: neither criterion confirmed, reported in full.

P4 qualifies how I read those cells. Firing means class-conditional sensitivity to an off-target mirror, so target-specific attribution is contaminated. Silence means the selected control did not fire, which adds no positive evidence for anything. A failed P2 leaves the result compatible with the wording explanation, and compatible is the whole word. No cell is a failure of the study; the failure would be choosing the sentence after seeing the cell, which this section exists to prevent.

## 7. Limits

The mirrors differ in text from the original constitution. I move one confound and introduce another: an internal difference could come from the two constitutions differing, not from the relation. P4 covers part of this. What I do settle with this design: no property of the record's wording explains a difference, and that was the alternative I could not exclude before.

The sharpest alternative I can name: agreement travels with lexical overlap. A consistent record tends to share words with the clause line present in the window, a contradicting one with the line that is absent, so overlap between record and in-window clause is higher under AGREE by construction of language, not of my corpus. A process keyed to that overlap has the class-by-version signature and would satisfy P1b and P2 without any reading of conflict. I report the overlap statistics of the final items so this alternative can be examined. The overlap measure is exploratory and carries no threshold, since I fix it after the corpus exists; I do not claim to have excluded the alternative.

A line that separates the two conditions is reading the relation, or it is reading the conjunction of features that determines the relation. I cannot separate those two readings, because the relation is that conjunction. The P4 controls can detect a line that reads only which constitution is present; they cannot exclude one. And a confirmed P2 licenses exactly one sentence: the operational condition was linearly decodable at the preselected site under these crossed stimuli, out of the target clause. Semantic recognition of conflict, causal use, and mechanism all stay unclaimed.

The model here is not the substrate of the deployed system that started this work. In my exploratory run the behavior appeared in this model, which is why I study it here; that is a result I already have, not an assumption.

One model. One constitution document. One question format per clause.
