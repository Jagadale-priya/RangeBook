# NIFTY 1m — pattern **behavior** → clean 100% calls (SL≤20)

**Not live.** Research order: understand how patterns form and how price moves after, then extract clean multi-call books at 100%.

- Calibrate `2025-07-02`→`2026-08-05`
- Last3m `2026-08-06`→`2026-11-06`
- Events: cal **63364** · last3m **15158**

## Phase A — How patterns behave

For each completion we measure:

1. **Before** — 5/15-bar drift, continuation vs reversal vs signal side, session align, RSI
2. **At** — body/wicks/range, candle stop distance
3. **After** — MAE/MFE, who hits ±5 first, win-rate with **SL≤20 / T1 8–10**

### Pattern leaderboard (calibrate, sorted by clean SL20/T1=8 win%)

| Pattern | N | Fav5% | Adv5% | Win SL20/T8 | Clean N | Clean Win% | Med MAE/MFE |
|---|---:|---:|---:|---:|---:|---:|---|
| morning_star | 187 | 54.0 | 41.7 | 76.5 | 13 | 84.6 | 42.5/51.65 |
| evening_star | 179 | 50.3 | 44.1 | 73.7 | 6 | 83.3 | 41.45/50.05 |
| falling_3_methods | 221 | 51.6 | 45.2 | 73.8 | 55 | 81.8 | 36.0/49.15 |
| three_crows | 419 | 47.7 | 45.8 | 75.7 | 201 | 78.6 | 42.4/56.25 |
| three_soldiers | 221 | 53.8 | 40.3 | 72.9 | 82 | 78.0 | 51.8/42.2 |
| three_outside_dn | 2813 | 48.3 | 48.2 | 71.0 | 472 | 74.4 | 43.0/48.35 |
| bull_kicker | 1042 | 49.5 | 47.8 | 68.8 | 98 | 73.5 | 47.05/37.33 |
| belt_bull | 2359 | 50.6 | 45.4 | 70.8 | 590 | 73.4 | 47.3/48.15 |
| bull_engulf | 4482 | 50.8 | 45.5 | 69.9 | 570 | 73.3 | 45.05/44.23 |
| bear_run2 | 6554 | 48.1 | 48.5 | 71.1 | 638 | 73.2 | 41.98/46.35 |
| three_outside_up | 2290 | 51.0 | 45.2 | 71.4 | 360 | 72.5 | 44.23/45.23 |
| marubozu_bull | 2145 | 53.5 | 40.3 | 70.9 | 384 | 72.1 | 48.6/50.4 |
| marubozu_bear | 2455 | 50.3 | 43.5 | 70.7 | 497 | 72.0 | 47.05/51.55 |
| bear_engulf | 5423 | 50.6 | 45.5 | 72.9 | 699 | 71.8 | 43.05/49.4 |
| bear_kicker | 659 | 51.7 | 45.1 | 71.5 | 77 | 71.4 | 38.6/43.85 |
| bear_run3 | 8958 | 47.5 | 48.3 | 70.8 | 1795 | 71.0 | 42.0/45.75 |
| belt_bear | 2604 | 48.6 | 47.5 | 70.4 | 751 | 70.2 | 40.5/48.2 |
| bull_run3 | 8849 | 49.0 | 47.3 | 68.9 | 1693 | 70.1 | 45.25/41.6 |
| bull_run2 | 7022 | 48.4 | 48.2 | 68.4 | 648 | 69.0 | 46.38/41.67 |
| rising_3_methods | 212 | 46.7 | 49.1 | 70.3 | 38 | 68.4 | 51.0/46.72 |

### What “clean” means (non-lookahead)

- Pre-regime = **continuation** (last 5 bars already moved with signal side)
- Session open→entry aligned with side
- Candle stop distance ≤ 15 pts, body_frac ≥ 0.45

## Phase B — 100% books (SL≤20, T1≥8)

### Champion: `day_unique` / `atr0.8_8.0`

- Filter: `{'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'align': 1, 'clocks': ['early'], 'max_sl_candle': 20.0}`
- Calibrate: **5 @ 100.0%** · SL/T1 10.66/8.0 · maxSL 19.41
- Last3m: **4 @ 100.0%** · SL/T1 11.76/8.0 · maxSL 17.58

**ACHIEVED 100% both windows** under SL≤20.

| Day | HM | Side | Primary | SL | T1 | Win |
|---|---|---|---|---:|---:|:---:|
| 2026-09-25 | 09:20 | BUY | hammer | 9.59 | 8.0 | Y |
| 2026-10-05 | 09:44 | BUY | hammer | 10.29 | 8.0 | Y |
| 2026-11-02 | 09:33 | BUY | hammer | 9.6 | 8.0 | Y |
| 2026-11-06 | 09:40 | BUY | inv_hammer | 17.58 | 8.0 | Y |

### Perfect day-unique (1st call/day)

- `atr0.8_8.0` · {'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'align': 1, 'clocks': ['early'], 'max_sl_candle': 20.0} · cal 5@100% · l3m 4@100% · SL/T1 11.76/8.0
- `atr1.0_8.0` · {'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'align': 1, 'clocks': ['early'], 'max_sl_candle': 20.0} · cal 5@100% · l3m 4@100% · SL/T1 14.21/8.0
- `fix15.0_8.0` · {'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'align': 1, 'clocks': ['early'], 'max_sl_candle': 20.0} · cal 5@100% · l3m 4@100% · SL/T1 15.0/8.0
- `atr1.2_8.0` · {'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'align': 1, 'clocks': ['early'], 'max_sl_candle': 20.0} · cal 5@100% · l3m 4@100% · SL/T1 16.06/8.0
- `fix20.0_8.0` · {'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'align': 1, 'clocks': ['early'], 'max_sl_candle': 20.0} · cal 5@100% · l3m 4@100% · SL/T1 20.0/8.0

### Perfect multi-call (gap ≥20m)

- none

### Near

- `day_unique` `fix20.0_8.0` · cal 10@90.0% · l3m 6@100.0% · filter={'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'clocks': ['early'], 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 80}
- `multi` `fix20.0_8.0` · cal 10@90.0% · l3m 6@100.0% · filter={'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'clocks': ['early'], 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 80}
- `day_unique` `fix20.0_10.0` · cal 10@90.0% · l3m 6@100.0% · filter={'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'clocks': ['early'], 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 80}
- `multi` `fix20.0_10.0` · cal 10@90.0% · l3m 6@100.0% · filter={'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'clocks': ['early'], 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 80}
- `day_unique` `fix15.0_8.0` · cal 10@90.0% · l3m 6@100.0% · filter={'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'clocks': ['early'], 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 80}
- `multi` `fix15.0_8.0` · cal 10@90.0% · l3m 6@100.0% · filter={'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'clocks': ['early'], 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 80}
- `day_unique` `fix15.0_10.0` · cal 10@90.0% · l3m 6@100.0% · filter={'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'clocks': ['early'], 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 80}
- `multi` `fix15.0_10.0` · cal 10@90.0% · l3m 6@100.0% · filter={'primaries': ['hanging_man', 'shooting_star', 'hammer', 'inv_hammer'], 'side': 'BUY', 'regime': 'continuation', 'clocks': ['early'], 'max_sl_candle': 20.0, 'rsi_lo': 40, 'rsi_hi': 80}

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_pattern_behavior_100`
- research_only · not_live · behavior-first · SL≤20 · no OR-break
