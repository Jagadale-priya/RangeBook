# NIFTY 1m — try **2025 full-year OOS** (train = 2024 only)

Train: cal `2024-01-02→2024-09-30` · l3m `2024-10-01→2024-12-31`
OOS: `2025-01-01→2025-12-31` · **249** trading days

## Why Nov FWD looked empty

- Nov9–16 is only ~5 sessions — rare micro geometries often **do not appear**.
- That is **not** missing OOS data; bars were present. Filters simply did not match.
- Live session: a call fires **only when** the locked micro (pattern+geometry+SL style) prints. Not every day.

## 2025 OOS results (availability check)

| Book | Variant | Micros | 2025 calls | Hit% | Calls/day (all) | Days with call |
|---|---|---:|---:|---:|---:|---:|
| T10 | DENSE | 230 | 851 | 44.65% | 3.42 | 242 |
| T10 | ROLL_m2 honest | 48 | 228 | 42.98% | 0.92 | 149 |
| T10 | PEEK_2025_100 | 2 | 1 | 100.0% | 0.0 | 1 |
| T15 | DENSE | 196 | 717 | 37.66% | 2.88 | 230 |
| T15 | ROLL_m2 honest | 35 | 148 | 37.16% | 0.59 | 105 |
| T15 | PEEK_2025_100 | 2 | 4 | 100.0% | 0.02 | 4 |
| T20 | DENSE | 121 | 441 | 34.47% | 1.77 | 203 |
| T20 | ROLL_m2 honest | 21 | 94 | 35.11% | 0.38 | 81 |
| T20 | PEEK_2025_100 | 1 | 3 | 100.0% | 0.01 | 3 |

### Monthly ROLL_m2 fire rate

**T10**

| Month | Calls | Hit% |
|---|---:|---:|
| 2025-01 | 20 | 25.0% |
| 2025-02 | 19 | 31.6% |
| 2025-03 | 28 | 50.0% |
| 2025-04 | 21 | 19.0% |
| 2025-05 | 21 | 42.9% |
| 2025-06 | 14 | 50.0% |
| 2025-07 | 20 | 60.0% |
| 2025-08 | 13 | 23.1% |
| 2025-09 | 11 | 63.6% |
| 2025-10 | 26 | 53.8% |
| 2025-11 | 18 | 38.9% |
| 2025-12 | 17 | 58.8% |

**T15**

| Month | Calls | Hit% |
|---|---:|---:|
| 2025-01 | 12 | 25.0% |
| 2025-02 | 12 | 41.7% |
| 2025-03 | 17 | 29.4% |
| 2025-04 | 12 | 33.3% |
| 2025-05 | 14 | 50.0% |
| 2025-06 | 11 | 27.3% |
| 2025-07 | 8 | 50.0% |
| 2025-08 | 9 | 55.6% |
| 2025-09 | 8 | 25.0% |
| 2025-10 | 23 | 43.5% |
| 2025-11 | 11 | 27.3% |
| 2025-12 | 11 | 36.4% |

**T20**

| Month | Calls | Hit% |
|---|---:|---:|
| 2025-01 | 6 | 0.0% |
| 2025-02 | 10 | 50.0% |
| 2025-03 | 6 | 16.7% |
| 2025-04 | 7 | 28.6% |
| 2025-05 | 7 | 57.1% |
| 2025-06 | 9 | 33.3% |
| 2025-07 | 4 | 50.0% |
| 2025-08 | 7 | 42.9% |
| 2025-09 | 8 | 25.0% |
| 2025-10 | 14 | 42.9% |
| 2025-11 | 8 | 25.0% |
| 2025-12 | 8 | 37.5% |

## Live takeaway

- **Yes, available live** when micro matches — 2025 shows year-long fire count, not a guarantee of daily calls.
- Honest `ROLL_m2` hit% on 2025 is the deployable estimate (no peek).
- `PEEK_2025_100` is an oracle ceiling only — not usable for live without future labels.

Elapsed: 121.7s · pack `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_oos_2025`
