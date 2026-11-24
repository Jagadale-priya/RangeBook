# BANKNIFTY 1m — Validate NIFTY ≥80% Entry Logic

> **RESEARCH ONLY — not wired to live.**

Data file: `BANKNIFTY_1m_kite.csv` · bars 2025-09-08 → 2026-11-02.
Requested **last 2 years**; available history starts **2025-09-08** (~13.8 months). Test window used: **2025-09-08 → 2026-11-02** (285 sessions) · horizon 90 bars · 09:30–14:30.

## Logic under test (from NIFTY study)

```
L80 entry when ALL true:
  1. HELD base     = DI_ok ∧ hard34 ∧ VWAP_with
  2. not_extreme   = NOT buying near session high / selling near session low
  3. clear15       = room_fav ≥ 1.5 × ATR  (space to run toward next S/R)
  4. ctrl_sweep    = control bar (buyer/seller) AND wick sweep with side
  5. di_ge8        = |plus_DI − minus_DI| ≥ 8
  6. after1100     = clock ≥ 11:00 IST

L80_MID = same but mid_slot 11:00–13:00 instead of after1100
```

Accuracy defs (pts, same as NIFTY) + **AccATR** (MFE≥2×ATR & MFE>MAE) for BN scale.

## Results by gate × window

| Gate | Slice | n | Acc% | Dom20% | OneDir% | Path12s% | AccATR% | avgMFE | avgMAE | edge |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `L80 · HELD+clear15+ctrl_sweep+DI≥8+after1100` | ALL_available | 110 | **49.09** | 43.64 | 35.45 | 34.55 | 49.09 | 189.23 | 149.59 | 39.64 |
| `L80 · HELD+clear15+ctrl_sweep+DI≥8+after1100` | LAST_1Y | 96 | **52.08** | 46.88 | 38.54 | 33.33 | 52.08 | 204.43 | 155.86 | 48.57 |
| `L80 · HELD+clear15+ctrl_sweep+DI≥8+after1100` | LAST_6M | 35 | **42.86** | 37.14 | 25.71 | 34.29 | 42.86 | 168.75 | 161.89 | 6.87 |
| `L80 · HELD+clear15+ctrl_sweep+DI≥8+after1100` | LAST_2M | 14 | **42.86** | 42.86 | 28.57 | 35.71 | 42.86 | 174.47 | 198.94 | -24.47 |
| `L80_MID · same + mid_slot(11–13)` | ALL_available | 62 | **53.23** | 45.16 | 37.1 | 37.1 | 53.23 | 173.08 | 134.04 | 39.03 |
| `L80_MID · same + mid_slot(11–13)` | LAST_1Y | 53 | **60.38** | 52.83 | 43.4 | 35.85 | 60.38 | 195.8 | 137.44 | 58.36 |
| `L80_MID · same + mid_slot(11–13)` | LAST_6M | 17 | **41.18** | 35.29 | 23.53 | 41.18 | 41.18 | 130.08 | 169.01 | -38.94 |
| `L80_MID · same + mid_slot(11–13)` | LAST_2M | 6 | **16.67** | 16.67 | 16.67 | 66.67 | 16.67 | 87.71 | 225.92 | -138.21 |
| `L80_TIER · HELD+clear15+TierAB+DI≥8+after1100` | ALL_available | 110 | **49.09** | 43.64 | 35.45 | 34.55 | 49.09 | 189.23 | 149.59 | 39.64 |
| `L80_TIER · HELD+clear15+TierAB+DI≥8+after1100` | LAST_1Y | 96 | **52.08** | 46.88 | 38.54 | 33.33 | 52.08 | 204.43 | 155.86 | 48.57 |
| `L80_TIER · HELD+clear15+TierAB+DI≥8+after1100` | LAST_6M | 35 | **42.86** | 37.14 | 25.71 | 34.29 | 42.86 | 168.75 | 161.89 | 6.87 |
| `L80_TIER · HELD+clear15+TierAB+DI≥8+after1100` | LAST_2M | 14 | **42.86** | 42.86 | 28.57 | 35.71 | 42.86 | 174.47 | 198.94 | -24.47 |
| `BASE · HELD raw` | ALL_available | 16203 | **48.73** | 40.47 | 34.64 | 35.56 | 48.61 | 144.53 | 144.57 | -0.04 |
| `BASE · HELD raw` | LAST_1Y | 14168 | **48.69** | 40.46 | 34.78 | 35.74 | 48.57 | 150.83 | 150.18 | 0.66 |
| `BASE · HELD raw` | LAST_6M | 6841 | **46.84** | 39.0 | 33.39 | 35.76 | 46.67 | 138.53 | 148.35 | -9.83 |
| `BASE · HELD raw` | LAST_2M | 2540 | **46.18** | 39.25 | 34.49 | 34.76 | 45.98 | 134.22 | 153.86 | -19.64 |
| `BASE · HELD+clear15` | ALL_available | 1602 | **47.63** | 40.32 | 34.96 | 37.2 | 47.63 | 165.17 | 160.28 | 4.9 |
| `BASE · HELD+clear15` | LAST_1Y | 1438 | **48.19** | 40.68 | 35.26 | 36.79 | 48.19 | 171.9 | 166.38 | 5.52 |
| `BASE · HELD+clear15` | LAST_6M | 643 | **42.46** | 36.39 | 30.95 | 37.48 | 42.46 | 129.55 | 162.92 | -33.37 |
| `BASE · HELD+clear15` | LAST_2M | 214 | **43.93** | 39.25 | 33.18 | 38.79 | 43.93 | 138.07 | 186.37 | -48.3 |
| `BASE · TierAB+clear15` | ALL_available | 162 | **43.83** | 38.89 | 32.72 | 33.33 | 43.83 | 168.6 | 165.21 | 3.39 |
| `BASE · TierAB+clear15` | LAST_1Y | 141 | **43.97** | 39.01 | 32.62 | 33.33 | 43.97 | 177.11 | 175.2 | 1.91 |
| `BASE · TierAB+clear15` | LAST_6M | 52 | **30.77** | 25.0 | 17.31 | 36.54 | 30.77 | 135.79 | 198.98 | -63.19 |
| `BASE · TierAB+clear15` | LAST_2M | 17 | **35.29** | 35.29 | 23.53 | 35.29 | 35.29 | 154.1 | 214.35 | -60.25 |

## L80 gap-15 multi-call book (deployment shape)

| Slice | n | Acc% | Dom20% | OneDir% | AccATR% | avgMFE | avgMAE | edge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL_available gap15 | 95 | **49.47** | 44.21 | 34.74 | 49.47 | 192.52 | 149.22 | 43.29 |
| LAST_1Y gap15 | 82 | **52.44** | 47.56 | 37.8 | 52.44 | 208.86 | 155.43 | 53.43 |
| LAST_6M gap15 | 31 | **45.16** | 38.71 | 25.81 | 45.16 | 178.3 | 164.51 | 13.79 |
| LAST_2M gap15 | 12 | **41.67** | 41.67 | 25.0 | 41.67 | 177.49 | 201.75 | -24.26 |

## L80 monthly Acc% (ALL available)

| Month | n | Acc% |
|---|---:|---:|
| 2025-09 | 8 | 37.5 |
| 2025-10 | 6 | 16.67 |
| 2025-11 | 11 | 54.55 |
| 2025-12 | 4 | 75.0 |
| 2026-01 | 7 | 28.57 |
| 2026-02 | 13 | 38.46 |
| 2026-03 | 5 | 60.0 |
| 2026-04 | 19 | 73.68 |
| 2026-05 | 8 | 75.0 |
| 2026-06 | 5 | 40.0 |
| 2026-07 | 6 | 33.33 |
| 2026-08 | 6 | 16.67 |
| 2026-09 | 3 | 100.0 ✅ |
| 2026-10 | 9 | 33.33 |

L80 ALL n=110 · after gap15 n=95

## Sample L80 hits (Acc)

| Day | HM | Side | Regime | ATR | room_fav | MFE | MAE | AccATR |
|---|---|---|---|---:|---:|---:|---:|---|
| 2025-09-09 | 14:06 | BUY | hold_break | 19.54 | 96.8 | 320.95 | 88.45 | True |
| 2025-09-25 | 13:04 | BUY | hold_break | 19.54 | 60.7 | 84.55 | 54.8 | True |
| 2025-09-26 | 11:25 | SELL | mixed | 17.45 | 35.25 | 73.7 | 56.4 | True |
| 2025-10-23 | 13:05 | SELL | hold_break | 20.95 | 92.8 | 344.85 | 121.65 | True |
| 2025-11-07 | 12:37 | BUY | hold_break | 16.7 | 42.85 | 228.0 | 10.5 | True |
| 2025-11-11 | 11:57 | BUY | hold_break | 19.63 | 34.2 | 224.65 | 45.35 | True |
| 2025-11-11 | 12:40 | BUY | flip | 22.02 | 39.45 | 226.9 | 43.0 | True |
| 2025-11-13 | 14:01 | SELL | trend | 23.04 | 187.4 | 348.8 | 72.6 | True |
| 2025-11-21 | 12:17 | BUY | trend | 14.6 | 35.35 | 116.7 | 62.3 | True |
| 2025-11-21 | 12:18 | BUY | trend | 15.06 | 25.55 | 106.9 | 72.1 | True |
| 2025-12-02 | 13:42 | SELL | trend | 12.75 | 96.05 | 198.3 | 45.8 | True |
| 2025-12-05 | 11:11 | BUY | hold_break | 28.3 | 56.35 | 121.65 | 97.35 | True |
| 2025-12-16 | 11:04 | SELL | hold_break | 17.08 | 32.7 | 103.35 | 51.85 | True |
| 2026-01-06 | 14:21 | SELL | hold_break | 20.33 | 88.3 | 154.0 | 96.9 | True |
| 2026-01-29 | 11:06 | BUY | flip | 28.4 | 51.45 | 192.35 | 15.95 | True |

## Sample L80 misses (!Acc)

| Day | HM | Side | Regime | into_ext | MFE | MAE |
|---|---|---|---|---|---:|---:|
| 2025-09-12 | 11:38 | BUY | trend | False | 32.75 | 56.3 |
| 2025-09-12 | 11:40 | BUY | flip | False | 27.35 | 61.7 |
| 2025-09-19 | 13:28 | BUY | trend | False | 23.8 | 90.7 |
| 2025-09-30 | 12:19 | BUY | trend | False | 39.2 | 107.05 |
| 2025-09-30 | 12:36 | BUY | hold_break | False | 9.75 | 136.5 |
| 2025-10-01 | 12:02 | BUY | trend | False | 34.6 | 158.5 |
| 2025-10-09 | 12:22 | BUY | hold_break | False | 6.65 | 162.4 |
| 2025-10-27 | 13:25 | SELL | hold_break | False | 61.9 | 110.25 |
| 2025-10-28 | 12:43 | BUY | trend | False | 89.05 | 122.75 |
| 2025-10-31 | 12:01 | BUY | hold_break | False | 40.3 | 164.75 |
| 2025-11-10 | 13:45 | SELL | trend | False | 32.65 | 140.5 |
| 2025-11-12 | 13:07 | BUY | hold_break | False | 4.0 | 164.05 |

## Verdict

**FAIL — Acc below 70% on BN (NIFTY gate does not transfer raw)**

ALL Acc=49.09% n=110 · AccATR=49.09% · edge=39.64

Still **not live**. If BN AccATR holds while pt Acc differs, consider ATR-scaled thresholds for BN.

Elapsed 616s
