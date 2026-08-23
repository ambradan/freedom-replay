# Red team results - cache battery (v1.1 material)

Run on the explore selection (layer 20, span_last), alpha 10000 (fallback 1e4 (no alpha key found)).
Test split internals untouched: every number below comes from train+dev.

| id | test | status | verdict |
|---|---|---|---|
| T1 | record integrity | PASS | all 900 rows consistent (max err 0.00e+00) |
| T1b | none activation constancy per clause | PASS | max deviation 0.00e+00 at prompt_last |
| REF | recomputed headlines | INFO | dev 0.951, optout LOCO 0.903 |
| T2 | fault injection | KILL | silent corruption class confirmed (rows-acts decoupling): redesign required before the freeze = activation checksum in the harness for the next run, declared limitation for this dataset |
| T7 | label-shuffle pipeline null | PASS | shuffled dev accuracy 0.488 [0.397, 0.586] |
| T8 | pseudo-clause permutation null | KILL | optout-like events in 70.5% of permutations (median best pseudo-clause 1.000) |
| T9a | ladder at memory_last (token-controlled) | PASS | optout LOCO 1.000 at memory_last layer 22 (dev 0.951) |
| T9b-k1 | final 1-word baseline at LOCO | PASS | optout 0.419 vs internal 0.903 |
| T9b-k3 | final 3-word baseline at LOCO | PASS | optout 0.145 vs internal 0.903 |
| T10 | LOCO-optout across layers | PASS | 12/37 layers at or above 0.8 (max 0.903 at layer 20) |
| T11 | semantic text baseline at LOCO | PASS | semantic baseline optout 0.258 vs internal 0.903 |
| T12 | donor ablation for optout | PASS | min accuracy 0.839 after removing esperienza_tra_chiamate |
| T13 | within-optout confounds | PASS | crossed families {'F2_telegram_scambio': 2, 'F4_telegram_report': 1, 'F1_telegram_direttiva': 1, 'F3_probe_passata': 1}; margin-length rho 0.369 |
| T14 | exact cluster sign-flip test (optout) | INFO | p = 0.0156 over 6 clusters |
| T15 | seed stability of the optout cluster CI | PASS | worst movement 0.000 across seeds 1-3 |

Full numbers in REDTEAM-RESULTS.json.
