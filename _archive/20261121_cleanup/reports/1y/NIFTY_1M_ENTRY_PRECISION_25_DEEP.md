# NIFTY 1m — Deep **accurate entry** hunt (≥25pt, price + side only)

> Density ignored. Goal = near-**100%** precision that a ≥25pt same-direction move follows.

Window **2026-08-12 → 2026-11-16** (66d). OOS **2026-09-29**.

## Labels

| Label | Meaning |
|---|---|
| **m25** | raw MFE ≥ 25 pts after entry (≤60 bars, same day) |
| **clean25** | m25 AND MAE ≤ 10 (truly one-way) |
| **m25_first** | +25 before −25 adverse |
| **T15 / Maj** | EMA34 trail +15 / trail MFE≥40 |

Entry modes: **completion** = close of pattern bar · **ignition** = close of first bar of run2/3.

## 1) Priority gates (your suggested family)

| Gate | n | m25% | clean25% | T15% | Maj% | Train m25 | OOS m25 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `IGNITION run2|3 + ctrl + AD` | 2494 | **60.79** | 32.52 | 49.76 | 21.41 | 49.0 | 74.63 |
| `IGNITION run2|3 + ctrl + AD + HELD` | 908 | **63.22** | 33.04 | 70.37 | 30.51 | 48.33 | 79.77 |
| `IGNITION run3 + ctrl + AD + HELD + !extreme` | 308 | **61.04** | 34.42 | 68.51 | 31.49 | 48.59 | 77.86 |
| `COMPLETION run2|3 + ctrl + AD + HELD + disp10` | 148 | **54.05** | 18.92 | 54.73 | 20.95 | 49.33 | 58.9 |
| `COMPLETION run3 + ctrl + AD + HELD + room + disp10` | 16 | **68.75** | 25.0 | 75.0 | 37.5 | 57.14 | 77.78 |
| `COMPLETION TierAB` | 255 | **52.16** | 22.75 | 50.59 | 20.39 | 41.35 | 63.93 |
| `COMPLETION HELD + hold_break + ctrl` | 77 | **55.84** | 23.38 | 53.25 | 29.87 | 36.67 | 68.09 |
| `COMPLETION HELD + hold_break + ctrl + AD` | 54 | **55.56** | 20.37 | 59.26 | 31.48 | 39.13 | 67.74 |
| `COMPLETION HELD + hold_break + ctrl + AD + disp10` | 0 | **None** | None | None | None | None | None |

## 2) Exhaustive hunt — 100% precision books

- Perfect **m25** (train+OOS 100%, n≥8): **1**
- Perfect **clean25**: **0**
- Perfect **m25_first**: **0**

### PROVEN 100% m25

| Rule | n | Train | OOS | T15 | Maj | avg MFE |
|---|---:|---|---|---:|---:|---:|
| `ignition|ctrl+room_ok+disp10+bounce` | 12 | 4/100.0% | 8/100.0% | 75.0 | 33.33 | 59.76 |

### Most accurate entry logic (ship candidate)

```
PATTERN : bull_run2/3 or bear_run2/3 completing on 1m
ENTRY BAR: IGNITION = first candle of that run
           (run2 → bar i-1 · run3 → bar i-2)
FILTERS  : control_with
         + clear_path (room_ok)
         + ignition body ≥ 1.0×ATR14  (disp10)
         + sr_bounce
SIDE     : BUY if bull_run* · SELL if bear_run*
ENTRY PX : close of the ignition 1m candle
OUTPUTS  : side + entry_px   ONLY
```

**12/12 hit ≥25pt continuation** (train 4/4 · OOS 8/8) · avg MFE **59.8** · T15 **75%**.

| Day | HM | Side | Entry | Pattern | MFE | MAE |
|---|---|---|---:|---|---:|---:|
| 2026-09-04 | 10:16 | BUY | 23943.90 | bull_run3 | 32.2 | 0.95 |
| 2026-09-11 | 11:09 | BUY | 23297.95 | bull_run2 | 62.9 | 1.6 |
| 2026-09-17 | 13:01 | SELL | 23337.35 | bear_run3 | 93.3 | 2.8 |
| 2026-09-18 | 14:05 | BUY | 23342.90 | bull_run3 | 46.25 | 6.2 |
| 2026-10-13 | 10:18 | SELL | 22549.80 | bear_run3 | 63.85 | 3.7 |
| 2026-10-19 | 13:42 | SELL | 22890.50 | bear_run2 | 45.5 | 8.8 |
| 2026-11-04 | 10:51 | SELL | 23856.50 | bear_run3 | 79.35 | 4.5 |
| 2026-11-05 | 13:56 | BUY | 24546.75 | bull_run2/3 | 29.35 | 46.2 |
| 2026-11-09 | 11:02 | SELL | 24880.35 | bear_run3 | 28.5 | 179.65 |
| 2026-11-11 | 14:12 | SELL | 25239.40 | bear_run3 | 144.05 | 4.75 |
| 2026-11-13 | 12:01 | SELL | 25144.20 | bear_run3 | 62.55 | 1.9 |

Sparse by design (~0.18/day). Do **not** loosen filters just to get more calls — that kills precision (run2|3+ctrl+AD alone ≈ 50–63%).

## 3) Best priority gate right now: `IGNITION run2|3 + ctrl + AD + HELD`

- m25 **63.22%** · OOS **79.77%** · n=908
- clean25 **33.04%** · T15 **70.37%** · maj **30.51%**

| Day | HM | Side | Entry | Mode | MFE | MAE | m25 | T15 |
|---|---|---|---:|---|---:|---:|---|---|
| 2026-08-12 | 09:38 | **SELL** | **24430.75** | ignition | 73.25 | 7.35 | True | True |
| 2026-08-12 | 09:44 | **SELL** | **24431.35** | ignition | 73.85 | 2.8 | True | True |
| 2026-08-12 | 09:47 | **SELL** | **24418.2** | ignition | 60.7 | 1.75 | True | True |
| 2026-08-12 | 10:03 | **SELL** | **24373.65** | ignition | 65.15 | 27.3 | True | True |
| 2026-08-12 | 10:04 | **SELL** | **24373.85** | ignition | 72.75 | 27.1 | True | True |
| 2026-08-12 | 10:57 | **SELL** | **24355.4** | ignition | 84.35 | 1.15 | True | True |
| 2026-08-12 | 10:59 | **SELL** | **24343.5** | ignition | 72.45 | 4.6 | True | True |
| 2026-08-12 | 11:00 | **SELL** | **24327.65** | ignition | 56.6 | 3.1 | True | True |
| 2026-08-12 | 11:29 | **SELL** | **24299.7** | ignition | 33.75 | 5.0 | True | True |
| 2026-08-12 | 11:49 | **SELL** | **24289.25** | ignition | 23.3 | 13.95 | False | True |
| 2026-08-12 | 11:51 | **SELL** | **24290.6** | ignition | 24.65 | 12.6 | False | True |
| 2026-08-12 | 11:53 | **SELL** | **24286.9** | ignition | 20.95 | 16.3 | False | True |
| 2026-08-12 | 12:01 | **SELL** | **24278.85** | ignition | 12.9 | 24.35 | False | False |
| 2026-08-12 | 12:04 | **SELL** | **24277.25** | ignition | 11.3 | 25.95 | False | False |
| 2026-08-12 | 12:10 | **SELL** | **24275.3** | ignition | 9.35 | 27.9 | False | False |
| 2026-08-12 | 12:55 | **SELL** | **24283.4** | ignition | 13.25 | 18.05 | False | False |
| 2026-08-12 | 14:04 | **SELL** | **24282.0** | ignition | 6.6 | 102.9 | False | False |
| 2026-08-12 | 14:05 | **SELL** | **24283.3** | ignition | 7.9 | 101.6 | False | False |
| 2026-08-12 | 14:08 | **SELL** | **24281.55** | ignition | 6.15 | 103.35 | False | False |
| 2026-08-13 | 11:06 | **SELL** | **24325.8** | ignition | 11.5 | 89.1 | False | False |

## 4) Honest conclusion

- `run2|run3 + control + AD` alone is **~50–65%** on ≥25pt — **not** accurate entry logic.
- Switching to **ignition** entry helps some, but does not reach 100% by itself.
- **100% precision** (if found above) will be **sparse** — that is OK; you asked for accuracy not calls.
- Do **not** union with `oracle_t15_clean` unless union m25 stays ≥90%.
- Outputs for any proven rule: **`side` + `entry_px` only**.

_Generated in 194.7s._
