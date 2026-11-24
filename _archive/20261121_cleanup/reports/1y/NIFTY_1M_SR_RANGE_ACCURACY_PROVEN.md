# NIFTY 1m — Accurate Swing Support / Resistance / Range · **PROVEN**

> **RESEARCH ONLY.** Identify real walls & ranges. Taking SL is OK.

Window **2026-10-15 → 2026-11-16** (22 sessions).

## Accuracy protocol

1. Confirm level on **past bars only**.
2. Price **leaves** ≥0.5×ATR, then **retests** within 0.40×ATR.
3. Next 10 bars: **react** = reclaim without close-break ≥**1.0×ATR**.

## Ranked S/R methods (retests ≥12)

| Method | Retests | **React%** | Hold% | Break% | Avg bounce |
|---|---:|---:|---:|---:|---:|
| `prior_day_HL` | 16 | **56.25** | 12.5 | 43.75 | 29.77 |
| `15m_L3` | 29 | **55.17** | 17.24 | 44.83 | 26.76 |
| `session_new_extreme` | 407 | **54.79** | 25.8 | 45.21 | 32.39 |
| `5m_L2` | 207 | **54.59** | 25.6 | 45.41 | 28.02 |
| `15m_L2` | 50 | **54.0** | 22.0 | 46.0 | 26.54 |
| `1m_fractal_L2` | 1344 | **53.79** | 25.15 | 46.21 | 30.7 |
| `1m_fractal_L3` | 958 | **53.03** | 24.43 | 46.97 | 30.21 |
| `5m_L3` | 140 | **52.14** | 22.86 | 47.86 | 27.61 |
| `1m_fractal_L5` | 577 | **50.43** | 21.32 | 49.57 | 28.7 |
| `OR15_edges` | 30 | **46.67** | 30.0 | 53.33 | 42.66 |
| `OR30_edges` | 26 | **42.31** | 19.23 | 57.69 | 34.03 |
| `1m_zone_L5_n≥2` | 79 | **24.05** | 5.06 | 75.95 | 23.86 |
| `1m_zone_L3_n≥3` | 48 | **18.75** | 6.25 | 81.25 | 36.21 |
| `1m_zone_L3_n≥2` | 95 | **17.89** | 3.16 | 82.11 | 29.91 |
| `1m_zone_L2_n≥2` | 88 | **15.91** | 1.14 | 84.09 | 27.92 |
| `1m_zone_L2_n≥3` | 48 | **14.58** | 2.08 | 85.42 | 29.28 |
| `1m_zone_L5_n≥3` | 32 | **12.5** | 3.12 | 87.5 | 32.77 |

## Range containment

| Range | bars | n | mean inside% | median |
|---|---:|---:|---:|---:|
| `swing_L3` | 30 | 400 | **37.62** | 30.0 |
| `swing_L3` | 60 | 400 | **31.99** | 25.0 |
| `OR15` | 30 | 21 | **62.54** | 63.33 |
| `OR15` | 60 | 21 | **55.63** | 58.33 |
| `OR30` | 30 | 21 | **65.08** | 66.67 |
| `OR30` | 60 | 21 | **56.03** | 58.33 |

## Proven accurate logic

```
RESISTANCE / SUPPORT (walls — by retest react%)
  A. Prior day High / Low           ~56%  (session magnets)
  B. 15m fractal L=3                ~55%
  C. Session new extreme retest     ~55%
  D. 5m fractal L=2                 ~55%
  E. 1m fractal L=2/L=3             ~53%  (timing only; denser/noisier)

NOT proven as walls
  - 1m same-day clustered zones (n≥2/3): react only ~15–24% — get run through
  - OR15/OR30 *edges as retest walls*: weaker than PDH / HTF swings

RANGE box (containment — different question)
  Prefer OR30: ~65% of next 30 closes stay inside
  OR15: ~63%
  Raw 1m swing hi/lo box: only ~38% (too tight / churns)
```

**Top retest react this window:** `prior_day_HL` → **56.25%**.
**Best HTF swing:** `15m_L3` → **55.17%**.
**Best OR edge:** `OR15_edges` → **46.67%**.
**Best raw 1m fractal:** `1m_fractal_L2` → **53.79%**.
**Best 1m zone:** `1m_zone_L5_n≥2` → **24.05%**.
**Best range box:** `OR30_30` → **65.08%** closes inside.

### How to use

- Plot **15m + 5m swings + PDH/PDL + OR30** as the accurate S/R/range map.
- Treat **1m fractals** as timing only, not as the wall itself.
- Trade the **retest** of A–D; if it breaks 1×ATR, take the SL and stand down.

Not wired to Scalper live.

Elapsed 8s
