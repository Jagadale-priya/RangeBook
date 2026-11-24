# NIFTY 1m — **ACC100 ALL ERAS** (accuracy-first)

Find micros that stay **100% target-before-SL on every era** (2024 → Nov2026 FWD).

Eras:
- **E2024**: `2024-01-02 → 2024-12-31` · events=57298
- **E2025**: `2025-01-01 → 2025-12-31` · events=57546
- **E2026A**: `2026-01-01 → 2026-08-05` · events=34646
- **E2026B**: `2026-08-06 → 2026-11-06` · events=15158
- **FWD**: `2026-11-09 → 2026-11-16` · events=1157

| Book | Variant | Micros | Calls | E2024 | E2025 | E2026A | E2026B | FWD | Verify all_win |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| T10 | **ACC100_ALL** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T10 | **ACC100_SOFT** | 9 | 61 | 32 | 17 | 11 | 0 | 1 | True |
| T10 | **ACC100_Y25Y26** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T10 | **ACC100_FWD1** | 1 | 7 | 3 | 2 | 1 | 0 | 1 | True |
| T10 | **ACC100_Q** | 6 | 40 | 21 | 10 | 8 | 0 | 1 | True |
| T10 | **ACC100_CORE** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T15 | **ACC100_ALL** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T15 | **ACC100_SOFT** | 7 | 47 | 25 | 11 | 10 | 1 | 0 | True |
| T15 | **ACC100_Y25Y26** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T15 | **ACC100_FWD1** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T15 | **ACC100_Q** | 1 | 6 | 3 | 2 | 1 | 0 | 0 | True |
| T15 | **ACC100_CORE** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T20 | **ACC100_ALL** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T20 | **ACC100_SOFT** | 2 | 10 | 6 | 2 | 2 | 0 | 0 | True |
| T20 | **ACC100_Y25Y26** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T20 | **ACC100_FWD1** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T20 | **ACC100_Q** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |
| T20 | **ACC100_CORE** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |

## Operate these for 100% accuracy-first

- **Winner: ACC100_SOFT** — verified **100% path on every era it fires** (2024 + 2025 + 2026A; T15 also 1× in 2026B).
- No cell survived requiring **both** E2026B **and** multi-year mins (`ACC100_ALL` / `CORE` = 0). That is the accuracy vs coverage wall.
- **T10 ACC100_FWD1**: only micro that also printed in Nov9+ FWD at 100%.
- Dense HELD packs optimize call count — **not** all-era accuracy.

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_acc100_all`
Elapsed: 310.4s

### T10 ACC100_ALL (0 micros)

_none_

### T10 ACC100_SOFT (9 micros)

| SL | Total | E24 | E25 | 26A | 26B | FWD | key |
|---|---:|---:|---:|---:|---:|---:|---|
| cap12 | 9 | 4 | 4 | 1 | 0 | 0 | `('GEOM', 'SELL', 'balanced', 1, 'early', 'b<45', 'sl12-16', 'lo', 'adv_hi', 'ba<0.5'` |
| p75 | 8 | 4 | 2 | 2 | 0 | 0 | `('dark_cloud', 'SELL', 1, 'morning', 'adv_lo', 'ba>0.8', 'sl8-12', 'mid')` |
| cap10 | 8 | 4 | 2 | 2 | 0 | 0 | `('three_outside_dn', 'SELL', 'reversal', 1, 'midday', 'b70+', 'sl12-16', 'adv_mid')` |
| sig | 7 | 3 | 2 | 1 | 0 | 1 | `('bear_run2', 'SELL', 'continuation', 1, 'midday', 'b70+', 'sl16-20', 'lo', 'adv_lo'` |
| p75 | 6 | 3 | 2 | 1 | 0 | 0 | `('bull_engulf', 'BUY', 1, 'late', 'adv_lo', 'ba<0.5', 'sl4-8', 'lo')` |
| sig | 6 | 3 | 2 | 1 | 0 | 0 | `('GEOM', 'SELL', 'reversal', 0, 'morning', 'b70+', 'sl12-16', 'mid', 'adv_lo', 'ba>0` |
| p75 | 6 | 4 | 1 | 1 | 0 | 0 | `('GEOM', 'BUY', 'reversal', 1, 'early', 'b70+', 'sl8-12', 'mid', 'adv_mid', 'ba<0.5'` |
| cap8 | 6 | 4 | 1 | 1 | 0 | 0 | `('bull_run2', 'BUY', 'reversal', 1, 'morning', 'b55+', 'sl16-20', 'adv_mid')` |
| sig | 5 | 3 | 1 | 1 | 0 | 0 | `('bull_engulf', 'BUY', 'reversal', 1, 'early', 'b70+', 'sl12-16', 'mid', 'adv_lo', '` |

### T10 ACC100_FWD1 (1 micros)

| SL | Total | E24 | E25 | 26A | 26B | FWD | key |
|---|---:|---:|---:|---:|---:|---:|---|
| sig | 7 | 3 | 2 | 1 | 0 | 1 | `('bear_run2', 'SELL', 'continuation', 1, 'midday', 'b70+', 'sl16-20', 'lo', 'adv_lo'` |

### T15 ACC100_ALL (0 micros)

_none_

### T15 ACC100_SOFT (7 micros)

| SL | Total | E24 | E25 | 26A | 26B | FWD | key |
|---|---:|---:|---:|---:|---:|---:|---|
| cap12 | 9 | 4 | 4 | 1 | 0 | 0 | `('GEOM', 'SELL', 'balanced', 1, 'early', 'b<45', 'sl12-16', 'lo', 'adv_hi', 'ba<0.5'` |
| prev | 9 | 5 | 1 | 2 | 1 | 0 | `('bull_run2', 'BUY', 'balanced', 'early', 'b45+', 'sl12-16', 'adv_hi')` |
| prev | 8 | 4 | 1 | 3 | 0 | 0 | `('belt_maru', 'BUY', 1, 'close', 'b55+', 'sl12-16', 'adv_hi', 'st1')` |
| prev | 6 | 3 | 2 | 1 | 0 | 0 | `('GEOM', 'SELL', 'reversal', 0, 'morning', 'b70+', 'sl12-16', 'mid', 'adv_lo', 'ba>0` |
| p60 | 5 | 3 | 1 | 1 | 0 | 0 | `('GEOM', 'BUY', 'continuation', 0, 'morning', 'b<45', 'sl16-20', 'mid', 'adv_lo', 'b` |
| sig | 5 | 3 | 1 | 1 | 0 | 0 | `('GEOM', 'BUY', 'reversal', 1, 'early', 'b70+', 'sl12-16', 'mid', 'adv_mid', 'ba>0.8` |
| prev | 5 | 3 | 1 | 1 | 0 | 0 | `('GEOM', 'SELL', 'continuation', 1, 'early', 'b55+', 'sl12-16', 'mid', 'adv_mid', 'b` |

### T15 ACC100_FWD1 (0 micros)

_none_

### T20 ACC100_ALL (0 micros)

_none_

### T20 ACC100_SOFT (2 micros)

| SL | Total | E24 | E25 | 26A | 26B | FWD | key |
|---|---:|---:|---:|---:|---:|---:|---|
| p75 | 5 | 3 | 1 | 1 | 0 | 0 | `('GEOM', 'BUY', 'continuation', 0, 'morning', 'b<45', 'sl16-20', 'mid', 'adv_lo', 'b` |
| prev | 5 | 3 | 1 | 1 | 0 | 0 | `('three', 'BUY', 'continuation', 0, 'am', 'b55+', 'sl16-20', 'adv_mid')` |

### T20 ACC100_FWD1 (0 micros)

_none_
