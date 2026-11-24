# NIFTY — PA × **Opening RANGE** prove (OR15 / OR30)

> **RESEARCH ONLY.** Same prove gate as `NIFTY_1M_PA_PROVEN_LOGIC`.

Window **2025-12-26 → 2026-11-16** (220d). OOS from **2026-06-10**. Target **3.0R**, 1/day.

## 0) Why range

Transcript BOS/CHoCH/FVG alone was **NOT_PROVEN** on 1Y WF.
This repo already showed **OR30** is the best containment box (~65%) and **OR15/OR30 zones** are decisive on revisits.
Question: can a **causal entry** on that range clear PROVEN?

| Book family | Logic |
|---|---|
| R1 swing | Leave → retest OR edge zone → fade, SL beyond box |
| R2 break | Close beyond OR → extend → retest zone → continue |
| R3/R4 +FVG | Same triggers, entry at FVG mid |
| R5/R6 +HTF | Same with 15m bias aligned |

## 1) Walk-forward

| Book | Verdict | Full n/hit/expR | Train | OOS n/hit/expR/t |
|---|---|---|---|---|
| `R6_break_htf_OR30` | **PROVEN** | 119/44.54%/0.782 | 61/44.26%/0.77 | 58/44.83%/0.793/t=3.01 |
| `R6_break_htf_OR15` | **PROVEN** | 115/38.26%/0.53 | 57/35.09%/0.404 | 58/41.38%/0.655/t=2.51 |
| `R2_break_OR30` | **PROVEN** | 152/40.13%/0.605 | 77/40.26%/0.61 | 75/40.0%/0.6/t=2.63 |
| `R2_break_OR15` | **PROVEN** | 156/38.46%/0.538 | 81/38.27%/0.531 | 75/38.67%/0.547/t=2.41 |
| `R5_swing_htf_OR30` | **PROMISING** | 59/45.76%/0.831 | 28/42.86%/0.714 | 31/48.39%/0.935/t=2.56 |
| `R1_swing_OR30` | **NOT_PROVEN** | 203/24.63%/-0.015 | 101/21.78%/-0.129 | 102/27.45%/0.098/t=0.55 |
| `R4_break_fvg_OR30` | **NOT_PROVEN** | 122/26.23%/0.057 | 66/25.76%/0.03 | 56/26.79%/0.089/t=0.37 |
| `R4_break_fvg_OR15` | **NOT_PROVEN** | 117/25.64%/0.026 | 65/24.62%/-0.015 | 52/26.92%/0.077/t=0.31 |
| `R3_swing_fvg_OR15` | **NOT_PROVEN** | 141/24.11%/-0.035 | 77/22.08%/-0.117 | 64/26.56%/0.062/t=0.28 |
| `R3_swing_fvg_OR30` | **NOT_PROVEN** | 142/25.35%/0.014 | 77/24.68%/-0.013 | 65/26.15%/0.046/t=0.21 |
| `R5_swing_htf_OR15` | **NOT_PROVEN** | 63/38.1%/0.548 | 37/48.65%/0.987 | 26/23.08%/-0.077/t=-0.23 |
| `R1_swing_OR15` | **NOT_PROVEN** | 198/21.72%/-0.124 | 100/25.0%/0.015 | 98/18.37%/-0.265/t=-1.69 |

## 2) Verdict

### PROVEN books (ship candidates)

| Book | Train hit/exp | OOS hit/exp/t | Full hit/exp | Logic |
|---|---|---|---|---|
| `R6_break_htf_OR30` | 44.26% / 0.77R | 44.83% / 0.793R / t=3.01 | 44.54% / 0.782R | OR break→retest continue + 15m HTF align (OR30) |
| `R6_break_htf_OR15` | 35.09% / 0.404R | 41.38% / 0.655R / t=2.51 | 38.26% / 0.53R | OR break→retest continue + 15m HTF align (OR15) |
| `R2_break_OR30` | 40.26% / 0.61R | 40.0% / 0.6R / t=2.63 | 40.13% / 0.605R | OR break→retest continue (OR30) |
| `R2_break_OR15` | 38.27% / 0.531R | 38.67% / 0.547R / t=2.41 | 38.46% / 0.538R | OR break→retest continue (OR15) |

**Best PROVEN (OOS exp):** `R6_break_htf_OR30` · OOS hit **44.83%** · exp **0.793R** · n=58

PROMISING (not ship): `R5_swing_htf_OR30`

## 3) Proven logic (if any book passed)

```
1. Build OR15 (or OR30) high/low after first 15/30 minutes
2. UP zone = OR high ± 0.5×ATR14 · DOWN zone = OR low ± 0.5×ATR14
3. Wait for CLOSE beyond OR edge (break), then extension away from zone
4. Enter on retest of the broken edge zone in break direction
5. SL beyond far side of zone · TP 3R
6. Optional filter: 15m HTF bias must agree (R6 books)
```

- Fade/swing into the range (R1/R3/R5) did **not** reliably prove.
- Adding FVG mid on top of break (R4) **hurt** vs plain break retest.
- This is orthogonal to transcript CHoCH→FVG (which failed alone).

## 4) Ship call

- If PROVEN: research Scalper mode candidate = **best R6/R2 book** (range break+retest).
- Still research-only until explicitly wired; Oracle T15 clean can stay default.

_Generated in 10.7s._
