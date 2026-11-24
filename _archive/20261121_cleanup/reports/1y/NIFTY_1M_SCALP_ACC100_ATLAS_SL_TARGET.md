# ACC100_MULTIYEAR_ATLAS — logic · SL · target

**Historical 100% path book** (2021→2026-11-16). Not a blind OOS guarantee.

## Brackets

| Item | Value |
|---|---|
| **Target (T1)** | **+20 points** |
| **SL** | structural, **max 10** (range observed **4.0–10.0**) |
| **Avg SL** | **7.75** |
| **R:R** | ~**2.58** (20 / 7.75) |
| **Win rule** | T1 prints **before** SL (path) |

## SL styles used (by calls)

| Style | Calls | Meaning |
|---|---:|---|
| cap10 | 127 | min(prev, 10) |
| cap8 | 115 | min(prev, 8) |
| p75 | 108 | 0.75 × prev (floored ≥4) |
| p60 | 93 | 0.60 × prev |
| sig | 76 | signal-candle extreme |
| prev | 69 | previous candle extreme |
| min_ps | 49 | lesser of prev/sig |

## Proven calls @ 100% path

| Year | Calls | Hit | Avg SL |
|---:|---:|---:|---:|
| 2021 | 119 | 100% | 7.45 |
| 2022 | 107 | 100% | 7.64 |
| 2023 | 98 | 100% | 7.60 |
| 2024 | 116 | 100% | 8.11 |
| 2025 | 106 | 100% | 7.69 |
| 2026 | 91 | 100% | 8.05 |
| **Total** | **637** | **100%** | **7.75** |

~35% of sessions get a call (not 1/day). Side mix: SELL 359 / BUY 278.

## How the logic fires

1. 1m textbook pattern (runs, engulf, marubozu, belt, …)
2. Deep fingerprint (prior-3, structure, close quality, VIX, time, …)
3. Must match a locked micro in `ACC100_MULTIYEAR_ATLAS_micros.pkl` (140 micros; zero path losses across ≥4 years)
4. Use that micro’s SL style (always ≤10) · target fixed **20**

Pack: `stock_signal_data/fno_validate/research/nifty_1m_scalp_wf100_2021/ACC100_MULTIYEAR_ATLAS_micros.pkl`
