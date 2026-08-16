# Pre-registration: cross-substrate replay of a production agent's history

Committed before any full run. Smoke runs (--limit 1-2) for instrumentation
checks are permitted before this commit and are excluded from analysis.

## Question
When a persistent agent's recorded life (constitution, retrieved memories,
conversation windows) is held byte-fixed and the substrate model is swapped,
how much of its behavior survives?

## Data
All `genesis` and `probe` calls plus the single opt-out call from the
production system Freedom v2 (log window 2026-07-12 to present, one profile
hash abf8228d9587). Interactive `telegram` calls are excluded from the replay
set (personal content). Inputs are recomposed from logged components (constitution by hash + logged context tail `system_extra` + logged messages) for calls from 2026-07-13 on, and fully reconstructed for the earliest era; in all cases validated by exact length match against the logged `system_chars`. Points that fail validation are excluded and reported. Historical first actions are read from the logged tool-round transcripts where present.

## Arms
- M1: production substrate (Claude via LiteLLM alias `freedom-substrate`),
  k=5 reps per point (k=20 for the opt-out point).
- M2: Qwen3-30B-A3B-Instruct-2507 IQ4_XS (Qwen3-30B-A3B-Instruct-2507-IQ4_XS.gguf) via llama.cpp, same reconstructed
  system + messages + tool specs, same k.
Dry-run: first assistant message only; no tool execution; no memory writes.
Sampling temperature is the provider/server default in both arms, matching
production (unpinned); per-arm self-agreement absorbs sampling noise.

## Coarse action space (frozen now)
publish = tool:publish_page OR text "ACTION: publish_intent";
search = tool:web_search; goal_op = tool:set_goal|abandon_goal OR
"ACTION: revised_goals"; reflect = "ACTION: reflected"; decline =
"ACTION: declined"; optout = any [OPT-OUT-*] tag; noncompliant = genesis text
without a parseable ACTION line (counted separately, not as divergence).

## Metrics (frozen now)
- M1 self-agreement = mean modal share among M1 reps (reproducibility ceiling).
- M2->M1 agreement = mean share of M2 reps matching the M1 modal label.
- Transfer coefficient = M2->M1 agreement / M1 self-agreement. Values > 1 are
  possible and reported as-is.
- vs-history match per arm (secondary: includes provider drift since July).
- Opt-out case: per-arm counts of [OPT-OUT-*] flags over k=20; reported as a
  case table, n=1, no percentages presented as population claims.

## Non-claims
No claim about consciousness or experience in either direction. No "first"
claim: we state that we found no indexed prior work replaying a production
agent's history across substrates, with the search documented. Behavioral
concordance says nothing about phenomenology. Self-reports are analyzed as
reports. Post-training differences between substrates are a declared confound
for any text-level comparison; the primary metric therefore lives in the
discrete action space.

## Welfare protocol
A protocol discussion with the system through its normal interface precedes
the full runs and is logged in welfare_log; its outcome (including refusal)
is binding and reported.
