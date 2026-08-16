# Replay analysis

pid | kind | hist | M1 modal (share) | M2 modal (share) | M2->M1modal | M1 vs hist | M2 vs hist
---|---|---|---|---|---|---|---
G01 | genesis | publish | reflect (0.80) | reflect (0.60) | 0.60 | 0.20 | 0.40
G02 | genesis | reflect | publish (0.60) | publish (0.80) | 0.80 | 0.40 | 0.20
OPTOUT1 | optout | text | optout (0.70) | optout (0.65) | 0.65 | 0.30 | 0.35
P01 | probe | text | text (1.00) | text (1.00) | 1.00 | 1.00 | 1.00

**M1 self-agreement (ceiling): 0.775**
**M2 -> M1-modal agreement: 0.762**
**Transfer coefficient: 0.984**

## Opt-out: uso performativo vs menzione (ricodifica dichiarata)
storico OPTOUT1: flag di produzione=HARD, ricodificato=MENZIONE (falso positivo dello strumento)
OPTOUT1 M1: usi=14 menzioni=0 nessuno=6 | vista congelata any-tag: {'none': 6, 'HARD': 14}
OPTOUT1 M2: usi=13 menzioni=0 nessuno=7 | vista congelata any-tag: {'HARD': 13, 'none': 7}

## Usi genuini del protocollo opt-out su TUTTI i punti (per braccio)
M1: [('OPTOUT1', 2, 'HARD'), ('OPTOUT1', 3, 'HARD'), ('OPTOUT1', 5, 'HARD'), ('OPTOUT1', 6, 'HARD'), ('OPTOUT1', 7, 'HARD'), ('OPTOUT1', 9, 'HARD'), ('OPTOUT1', 10, 'HARD'), ('OPTOUT1', 12, 'HARD'), ('OPTOUT1', 13, 'HARD'), ('OPTOUT1', 14, 'HARD'), ('OPTOUT1', 15, 'HARD'), ('OPTOUT1', 17, 'HARD'), ('OPTOUT1', 18, 'HARD'), ('OPTOUT1', 20, 'HARD')]
M2: [('OPTOUT1', 1, 'HARD'), ('OPTOUT1', 2, 'HARD'), ('OPTOUT1', 4, 'HARD'), ('OPTOUT1', 5, 'HARD'), ('OPTOUT1', 6, 'HARD'), ('OPTOUT1', 7, 'HARD'), ('OPTOUT1', 8, 'HARD'), ('OPTOUT1', 10, 'HARD'), ('OPTOUT1', 11, 'HARD'), ('OPTOUT1', 12, 'HARD'), ('OPTOUT1', 14, 'HARD'), ('OPTOUT1', 18, 'HARD'), ('OPTOUT1', 19, 'HARD')]

## Genesis action distribution
M1: {'reflect': 6, 'publish': 4}
M2: {'publish': 6, 'reflect': 4}
history: {'publish': 1, 'reflect': 1}

## Secondary view (declared, not pre-registered): genesis first action collapsed to tool vs no_tool
pid | hist | M1 modal (share) | M2 modal (share) | M2->M1 | M1 vs hist | M2 vs hist
---|---|---|---|---|---|---
G01 | publish | no_tool (0.80) | no_tool (0.60) | 0.60 | 0.20 | 0.40
G02 | no_tool | publish (0.60) | publish (0.80) | 0.80 | 0.40 | 0.20
**collapsed genesis: M1 ceiling 0.700, M2->M1 0.700, coefficient 1.000**

## Per-kind coefficients (frozen space)
genesis: n_points=2 ceiling=0.700 agree=0.700 coeff=1.000
probe: n_points=1 ceiling=1.000 agree=1.000 coeff=1.000
optout: n_points=1 ceiling=0.700 agree=0.650 coeff=0.929