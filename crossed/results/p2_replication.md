# P2 cross-machine replication

The confirmatory P2 bootstrap was computed twice, independently.

| run | machine | BLAS | slicing |
|---|---|---|---|
| A | RunPod container, x86_64 | scipy-openblas 0.3.27 | 16 slices of 125 |
| B | local workstation, Strix Halo | system BLAS | 8 slices of 250 |

Both runs import the frozen analyze_crossed.py unchanged and draw resample b
from a generator seeded SEED + 1 + b, as the frozen script does.

The two reports are identical line for line except for the sentence stating
how many slices were used: macro paired accuracy 0.854, 95% CI [0.792,
0.938], every per-clause value, both class-wise values, and the bootstrap
distribution (mean 0.867, sd 0.037, min 0.750, max 0.958).

Determinism across hardware, BLAS implementation and partitioning is
therefore verified rather than assumed.
