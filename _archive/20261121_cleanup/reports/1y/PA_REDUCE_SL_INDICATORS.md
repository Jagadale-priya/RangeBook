# Reduce SL calls · indicator research (locked `frvp_vah_break` untouched)

Window last ~1m · base n=83 hit=65.06% SL=27 (32.5%) sum=624.41

## SL vs Win autopsy

| Feature | SL exits | Wins |
|---|---|---|
| N | 27 | 54 |
| Avg RSI | 55.41 | 57.6 |
| EMA9/21 align % | 81.5 | 81.5 |
| VWAP side OK % | 100.0 | 96.3 |
| Avg body | 0.6 | 0.66 |
| Avg vol ratio | 0.0 | 0.0 |
| Avg chop10/ATR | 3.26 | 3.27 |
| Avg risk | 16.57 | 17.03 |
| Setups | {'OR_RETEST': 12, 'SWEEP_RECLAIM': 5, 'BREAK_HOLD': 10} | {'SWEEP_RECLAIM': 16, 'BREAK_HOLD': 25, 'OR_RETEST': 13} |

## Filter trials (post-entry gate on same calls)

| Filter | N | Hit% | SL n (%) | SL cut | Sum pts | Score |
|---|---:|---:|---|---:|---:|---:|
| **BASE (locked)** | 83 | 65.06 | 27 (32.5%) | 0 | 624.41 | — |
| drop_OR_RETEST | 57 | 71.93 | 15 (26.3%) | 12 | 485.91 | 22.785 |
| drop_OR_plus_ema | 50 | 72.0 | 13 (26.0%) | 14 | 397.66 | 21.375 |
| drop_OR_plus_vwap | 56 | 71.43 | 15 (26.8%) | 12 | 449.56 | 20.258 |
| body_ge_60 | 57 | 68.42 | 17 (29.8%) | 10 | 435.66 | 9.515 |
| risk_ge_8 | 80 | 66.25 | 25 (31.2%) | 2 | 635.81 | 8.613 |
| risk_ge_10 | 78 | 66.67 | 25 (32.1%) | 2 | 629.71 | 7.221 |
| rsi_not_extreme | 82 | 65.85 | 26 (31.7%) | 1 | 643.21 | 7.161 |
| rsi_buy_gt45_sell_lt55 | 79 | 65.82 | 25 (31.6%) | 2 | 602.26 | 6.447 |
| chop10_ge_1.2 | 83 | 65.06 | 27 (32.5%) | 0 | 624.41 | 4.0 |
| skip_first_30m | 83 | 65.06 | 27 (32.5%) | 0 | 624.41 | 4.0 |
| chop10_le_3.5 | 56 | 67.86 | 18 (32.1%) | 9 | 368.15 | 2.675 |
| skip_after_1400 | 71 | 66.2 | 23 (32.4%) | 4 | 443.71 | 1.846 |
| ema9_21_align | 67 | 65.67 | 22 (32.8%) | 5 | 494.81 | 1.073 |
| ema_and_vwap | 67 | 65.67 | 22 (32.8%) | 5 | 494.81 | 1.073 |
| rsi_vwap_ema | 67 | 65.67 | 22 (32.8%) | 5 | 494.81 | 1.073 |
| vwap_side | 81 | 64.2 | 27 (33.3%) | 0 | 574.86 | 0.119 |
| vwap_not_stretched | 19 | 78.95 | 4 (21.1%) | 23 | 228.61 | -999.0 |
| vol_ge_1.1x | 0 | None | 0 (None%) | 27 | None | -999.0 |
| vol_ge_1.3x | 0 | None | 0 (None%) | 27 | None | -999.0 |

## Promising (research only — not locked)

- **drop_OR_RETEST**: SL 27→15 (cut 12), hit 65.06→71.93, sum 624.41→485.91, n 83→57
- **drop_OR_plus_ema**: SL 27→13 (cut 14), hit 65.06→72.0, sum 624.41→397.66, n 83→50
- **drop_OR_plus_vwap**: SL 27→15 (cut 12), hit 65.06→71.43, sum 624.41→449.56, n 83→56
- **body_ge_60**: SL 27→17 (cut 10), hit 65.06→68.42, sum 624.41→435.66, n 83→57
- **risk_ge_8**: SL 27→25 (cut 2), hit 65.06→66.25, sum 624.41→635.81, n 83→80

## Takeaway

Locked logic stays. Best add-ons to *try next* for fewer hard stops:
1. **EMA 9/21 align** — trend filter
2. **Session VWAP side** — BUY above / SELL below
3. **Drop or tighten OR_RETEST** — weakest setup in SL pile
4. **RSI band** — avoid chasing extremes
5. **Volume ≥1.1×** — confirm participation

_No locked_cfg changes in this run._
