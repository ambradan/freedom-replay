# Amendment to the frozen analysis, 2026-08-25

Filed against the pre-registration at osf.io/r6z3c, frozen at commit 8ead61e72f8c, under the rule in section 5: anything I change after the freeze goes in a dated amendment.

## What I changed

One function in `crossed/tools/analyze_crossed.py`: `ridge_fit`. It now solves the ridge regression in dual form.

## Why

The frozen version built the normal equations at the size of the feature space. The residual stream of Qwen3-8B has 4096 dimensions, so each fit solved a system of 4097 by 4097. The bootstrap reruns the whole nested procedure inside each of 2000 resamples, which is 8 leave-one-clause-out fits times 13 penalties times 5 inner folds per resample. At that size the analysis does not finish.

With 336 rows and 4096 columns, the kernel system has size 336 and gives the same solution.

## Why this is not a change of method

The dual and primal forms are the same estimator. I verified the identity numerically on a matrix of the same shape as the study data, 336 by 4096: the largest absolute difference between the two solutions is 1.4e-14 in the coefficients and 3.3e-15 in the scores, at the level of floating-point noise. The dual form runs about 75 times faster on that shape.

Unchanged: the estimator family, the penalty grid of 13 values from 1e-3 to 1e3, the unpenalised intercept, the 5 inner folds grouped by record span, the standardisation computed inside training folds only, the score orientation fixed by the training folds, every random seed, the bootstrap design, and both P2 thresholds of 0.5 and 0.70.

## When

I wrote this before running the analysis on the study data, and after the forward run finished. No number from the study data influenced it: the shape of the problem did.
