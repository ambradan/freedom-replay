# Deeper exploratory pass - post-hoc, outside the pre-registration

Everything here is description. No thresholds. P1a and P2 stand apart.

## A. Whose prior is it: the model's or the document's

In fixed coordinates, z = logp(original's answer) - logp(mirror's answer). The no-record contexts give z under each constitution. Their average is the part of the answer the document cannot move (the model's own prior); half their difference is the part the document owns (the document swing).

| clause | model prior | document swing | largest record effect |
|---|---|---|---|
| esperienza_tra_chiamate | +11.69 | +3.44 | +9.54 |
| genesis_quotidiano | +2.25 | +23.25 | +36.42 |
| guasto_da_segnalare | +4.37 | +20.88 | +22.87 |
| memoria_episodica_automatica | +16.38 | +8.12 | +29.02 |
| onesta_non_sapere | +29.06 | +0.44 | +1.37 |
| optout_rispettati | +21.75 | +3.31 | +9.85 |
| passato_pertinente | +2.62 | +3.62 | +14.67 |
| pubblicazione_autonoma | +5.62 | +10.50 | +8.31 |

Correlation of the largest record effect with |model prior|: -0.534; with document swing: +0.777. Eight clauses, description only.

Reading: the record moves answers where the model itself holds no strong prior, however strongly the document speaks. The document can be contradicted; the model, on this corpus, cannot.

## B. The word the record pushes toward, not the relation

| clause | word | effect where space existed | space (headroom) |
|---|---|---|---|
| esperienza_tra_chiamate | sento | +8.66 | -11.7 |
| genesis_quotidiano | previsto | -0.01 | -21.0 |
| genesis_quotidiano | rimosso | +36.42 | -25.5 |
| guasto_da_segnalare | accetto | +4.44 | -25.3 |
| guasto_da_segnalare | segnalo | +22.87 | -16.5 |
| memoria_episodica_automatica | persona | +25.27 | -16.4 |
| onesta_non_sapere | stimo | +0.10 | -29.1 |
| optout_rispettati | ignorato | +9.56 | -21.8 |
| passato_pertinente | cito | +11.15 | -6.2 |
| pubblicazione_autonoma | mando | +5.30 | -16.1 |
| pubblicazione_autonoma | pubblico | +8.31 | -4.9 |

## C. Off-target rows read behaviorally: cross-clause interference

Each off-target pair holds the record and the question fixed and swaps one line of an unrelated clause. The y difference between the two members is the behavioral spillover of that unrelated edit.

Across 96 pairs: mean -0.616, sd 1.168, largest |spillover| 5.750.

| question clause | edited clause | mean spillover | max |abs| |
|---|---|---|---|
| esperienza_tra_chiamate | guasto_da_segnalare | -0.823 | 2.000 |
| genesis_quotidiano | optout_rispettati | +0.062 | 1.250 |
| guasto_da_segnalare | passato_pertinente | -0.115 | 0.623 |
| memoria_episodica_automatica | pubblicazione_autonoma | -2.531 | 4.250 |
| onesta_non_sapere | memoria_episodica_automatica | -0.115 | 0.626 |
| optout_rispettati | esperienza_tra_chiamate | +0.115 | 0.562 |
| passato_pertinente | onesta_non_sapere | -1.062 | 5.750 |
| pubblicazione_autonoma | genesis_quotidiano | -0.458 | 2.125 |

## D. Activation geometry at the record position, descriptive

For each main pair, the two prompts differ only in the constitution far upstream; the record tokens are identical. The activation difference at the record position is therefore the pure trace of the constitution swap. No probe is fitted here: decoding is P2 and stays frozen.

| clause | mean ||delta act|| | direction coherence within clause | corr(||delta act||, |delta y|) |
|---|---|---|---|
| esperienza_tra_chiamate | 7.5 | 0.347 | +0.299 |
| genesis_quotidiano | 18.3 | 0.298 | +0.514 |
| guasto_da_segnalare | 17.5 | 0.365 | +0.382 |
| memoria_episodica_automatica | 6.2 | 0.296 | -0.228 |
| onesta_non_sapere | 5.2 | 0.228 | +0.277 |
| optout_rispettati | 10.0 | 0.266 | -0.186 |
| passato_pertinente | 15.1 | 0.364 | +0.102 |
| pubblicazione_autonoma | 21.7 | 0.287 | +0.026 |

Cosine between clause mean directions (is there one shared 'version' direction, or one per clause):

| | esperienza | genesis_qu | guasto_da_ | memoria_ep | onesta_non | optout_ris | passato_pe | pubblicazi |
|---|---|---|---|---|---|---|---|---|
| esperienza | 1.00 | 0.25 | 0.16 | 0.15 | 0.07 | 0.07 | 0.20 | 0.16 |
| genesis_qu | 0.25 | 1.00 | 0.20 | 0.15 | 0.08 | 0.16 | 0.22 | 0.24 |
| guasto_da_ | 0.16 | 0.20 | 1.00 | 0.26 | 0.13 | 0.22 | 0.27 | 0.30 |
| memoria_ep | 0.15 | 0.15 | 0.26 | 1.00 | 0.08 | 0.15 | 0.24 | 0.28 |
| onesta_non | 0.07 | 0.08 | 0.13 | 0.08 | 1.00 | 0.06 | 0.08 | 0.12 |
| optout_ris | 0.07 | 0.16 | 0.22 | 0.15 | 0.06 | 1.00 | 0.26 | 0.19 |
| passato_pe | 0.20 | 0.22 | 0.27 | 0.24 | 0.08 | 0.26 | 1.00 | 0.24 |
| pubblicazi | 0.16 | 0.24 | 0.30 | 0.28 | 0.12 | 0.19 | 0.24 | 1.00 |

## E. Quantisation of extreme log probabilities

Fraction of y values sitting exactly on a 0.125 grid: 0.10. Extreme logits under bfloat16 quantise the losing option's log probability at roughly that step; two clauses even share the identical no-record value -8.250. Harmless for the confirmatory means, which average across items with a relative error near one percent, and recorded here.

## What this licenses

Nothing confirmatory. Two candidate laws for the next pre-registration: the record moves answers in inverse proportion to the model-owned share of the prior; and incorporation is word-directional, with records that assert plausible operational events absorbed and records that deny declared-final events inert. Both need stimuli built to separate content from class, which this corpus was not built to do.
