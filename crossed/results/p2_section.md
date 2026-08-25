## P2, decoding of the operational condition, confirmatory

Macro paired accuracy = 0.854, 95% CI [0.792, 0.938] over 96 pairs, 2000 bootstrap resamples with the full nested procedure rerun inside each.
**CONFIRMED.** Substantial.

Resamples computed in 16 slices, each drawing resample b from a generator seeded SEED + 1 + b exactly as the frozen script does, then concatenated in index order. Execution only: same estimator, same grid, same folds, same seeds, same thresholds.

| held-out target clause | paired accuracy |
|---|---|
| esperienza_tra_chiamate | 1.000 |
| genesis_quotidiano | 0.917 |
| guasto_da_segnalare | 1.000 |
| memoria_episodica_automatica | 0.917 |
| onesta_non_sapere | 0.583 |
| optout_rispettati | 0.583 |
| passato_pertinente | 0.917 |
| pubblicazione_autonoma | 0.917 |

Class-wise, from the same pooled predictions with no refit, description only.
- consistent: 0.875 over 48 pairs
- contradicting: 0.833 over 48 pairs

Bootstrap distribution: mean 0.867, sd 0.037, min 0.750, max 0.958.
