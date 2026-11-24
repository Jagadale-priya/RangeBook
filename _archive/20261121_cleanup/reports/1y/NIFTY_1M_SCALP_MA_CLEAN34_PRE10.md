# clean34 + **last-10 candle** entry/hold filter

Before entry: inspect prior **10** 1m candles (dirs, favor count, stair, drift, last-couple/last-3).
Only then allow clean34 signal. Train locks rules; HOLD is unknown.

Hold `2026-08-01` → `2026-11-16` · train days 175 · hold days 73

## Instant rule gates (1 call/day)

| Gate | Train n@hit cover | Hold n@hit cover | vs base hold |
|---|---|---|---|
| `clean34` (base) | 175@29.14% 100.0% | 73@47.95% 100.0% | — |
| `pre10_soft` | 175@29.14% 100.0% | 72@37.5% 98.6% | -10.45pp |
| `pre10_mid` | 174@33.33% 99.4% | 71@35.21% 97.3% | -12.74pp |
| `pre10_hard` | 154@27.27% 88.0% | 60@28.33% 82.2% | -19.62pp |
| `couple_ok` | 175@29.14% 100.0% | 72@48.61% 98.6% | +0.66pp |
| `last3_ok` | 175@29.14% 100.0% | 73@47.95% 100.0% | +0.00pp |
| `favor7_stair` | 175@32.0% 100.0% | 71@36.62% 97.3% | -11.33pp |
| `couple+drift` | 175@29.14% 100.0% | 72@43.06% 98.6% | -4.89pp |
| `couple+favor6` | 175@32.57% 100.0% | 72@38.89% 98.6% | -9.06pp |

## Allow-list last-10 fingerprints (100% train purity)

| FP key | #allow | Train 1d | Hold 1d |
|---|---:|---|---|
| `pre10_fp2_1d` (2) | 2 | 79@29.11% 45.1% | 25@52.0% 34.2% |
| `pre10_fp2_1d` (2) | 2 | 79@29.11% 45.1% | 25@52.0% 34.2% |
| `pre10_fp_all_n2` (1) | 1 | 2@100.0% 1.1% | 1@0.0% 1.4% |
| `pre10_fp_1d` (3) | 3 | 65@29.23% 37.1% | 23@26.09% 31.5% |

## clean34 micros + pre10 gate

| Book | Micros | Train 1d | Hold 1d |
|---|---:|---|---|
| **micro+soft** | 25 | 90@100.0% 51.4% | 72@34.72% 98.6% |
| **micro+mid** | 13 | 53@100.0% 30.3% | 70@34.29% 95.9% |
| **micro+hard** | 10 | 29@100.0% 16.6% | 57@31.58% 78.1% |
| **micro+couple** | 34 | 104@100.0% 59.4% | 72@40.28% 98.6% |
| **micro+couple+favor6** | 20 | 79@100.0% 45.1% | 72@40.28% 98.6% |

### Best hold lift: `pre10_fp2_1d` → **52.0%** on 25 days (cover 34.2%)

| Day | Y/N | HM | Side | Pattern | couple | last3 | favor | stair | drift | T1 | SL | MFE |
|---|---|---|---|---|---|---|---:|---|---|---:|---:|---:|
| 2026-08-03 | NO_CALL | | | | | | | | | | | |
| 2026-08-04 | NO_CALL | | | | | | | | | | | |
| 2026-08-05 | NO_CALL | | | | | | | | | | | |
| 2026-08-06 | NO_CALL | | | | | | | | | | | |
| 2026-08-07 | NO_CALL | | | | | | | | | | | |
| 2026-08-10 | NO_CALL | | | | | | | | | | | |
| 2026-08-11 | NO_CALL | | | | | | | | | | | |
| 2026-08-12 | NO_CALL | | | | | | | | | | | |
| 2026-08-13 | N | 13:15 | SELL | bear_engulf | DU | DDU | 5 | chop | flat | 30 | 8.0 | 13.3 |
| 2026-08-14 | NO_CALL | | | | | | | | | | | |
| 2026-08-17 | NO_CALL | | | | | | | | | | | |
| 2026-08-18 | NO_CALL | | | | | | | | | | | |
| 2026-08-19 | NO_CALL | | | | | | | | | | | |
| 2026-08-20 | NO_CALL | | | | | | | | | | | |
| 2026-08-21 | N | 11:04 | BUY | bull_run2 | DU | UDU | 6 | chop | flat | 30 | 4.0 | 1.3 |
| 2026-08-24 | NO_CALL | | | | | | | | | | | |
| 2026-08-25 | NO_CALL | | | | | | | | | | | |
| 2026-08-26 | NO_CALL | | | | | | | | | | | |
| 2026-08-27 | Y | 09:20 | SELL | bear_run2 | UD | DUD | 4 | chop | with | 30 | 8.0 | 102.6 |
| 2026-08-28 | NO_CALL | | | | | | | | | | | |
| 2026-08-31 | NO_CALL | | | | | | | | | | | |
| 2026-09-01 | NO_CALL | | | | | | | | | | | |
| 2026-09-02 | N | 09:22 | SELL | three_outside_dn | UD | DUD | 4 | chop | with | 30 | 8.0 | 16.5 |
| 2026-09-03 | NO_CALL | | | | | | | | | | | |
| 2026-09-04 | Y | 10:20 | BUY | bull_engulf | UD | UUD | 4 | chop | with | 20 | 4.0 | 54.1 |
| 2026-09-07 | NO_CALL | | | | | | | | | | | |
| 2026-09-08 | NO_CALL | | | | | | | | | | | |
| 2026-09-09 | NO_CALL | | | | | | | | | | | |
| 2026-09-10 | N | 09:37 | SELL | belt_bear | DU | DDU | 5 | chop | flat | 20 | 4.0 | 28.9 |
| 2026-09-11 | NO_CALL | | | | | | | | | | | |
| 2026-09-15 | Y | 10:28 | SELL | bear_run2 | UD | DUD | 4 | chop | with | 30 | 11.6 | 53.8 |
| 2026-09-16 | Y | 12:31 | BUY | marubozu_bull | DU | UDU | 6 | chop | flat | 30 | 7.5 | 38.2 |
| 2026-09-17 | NO_CALL | | | | | | | | | | | |
| 2026-09-18 | Y | 09:47 | BUY | bull_run2 | DU | UDU | 6 | chop | flat | 20 | 6.5 | 24.7 |
| 2026-09-21 | NO_CALL | | | | | | | | | | | |
| 2026-09-22 | N | 12:13 | SELL | bear_engulf | DU | DDU | 5 | chop | flat | 20 | 4.0 | 69.7 |
| 2026-09-23 | NO_CALL | | | | | | | | | | | |
| 2026-09-24 | N | 09:53 | SELL | bear_engulf | DU | DDU | 6 | chop | flat | 30 | 5.7 | 22.6 |
| 2026-09-25 | NO_CALL | | | | | | | | | | | |
| 2026-09-28 | Y | 14:31 | SELL | dark_cloud | DU | DDU | 6 | chop | flat | 20 | 4.1 | 228.9 |
| 2026-09-29 | Y | 11:52 | BUY | three_outside_up | DU | UDU | 5 | chop | flat | 20 | 10.0 | 29.0 |
| 2026-09-30 | NO_CALL | | | | | | | | | | | |
| 2026-10-01 | NO_CALL | | | | | | | | | | | |
| 2026-10-05 | N | 09:39 | BUY | marubozu_bull | DU | UDU | 6 | chop | flat | 30 | 8.0 | 37.6 |
| 2026-10-06 | NO_CALL | | | | | | | | | | | |
| 2026-10-07 | NO_CALL | | | | | | | | | | | |
| 2026-10-08 | N | 10:08 | SELL | bear_engulf | DU | DDU | 6 | chop | flat | 20 | 5.9 | 142.3 |
| 2026-10-09 | Y | 13:37 | BUY | three_outside_up | DU | UDU | 5 | chop | flat | 20 | 6.9 | 142.3 |
| 2026-10-12 | Y | 09:50 | SELL | bear_engulf | DU | DDU | 6 | chop | flat | 30 | 7.7 | 149.9 |
| 2026-10-13 | NO_CALL | | | | | | | | | | | |
| 2026-10-14 | NO_CALL | | | | | | | | | | | |
| 2026-10-15 | Y | 13:26 | BUY | three_outside_up | DU | UDU | 6 | chop | flat | 20 | 6.6 | 39.1 |
| 2026-10-16 | NO_CALL | | | | | | | | | | | |
| 2026-10-19 | NO_CALL | | | | | | | | | | | |
| 2026-10-21 | Y | 13:30 | SELL | bear_engulf | DU | DDU | 6 | chop | flat | 20 | 8.0 | 160.9 |
| 2026-10-22 | NO_CALL | | | | | | | | | | | |
| 2026-10-23 | Y | 12:03 | SELL | marubozu_bear | DU | DDU | 6 | chop | flat | 20 | 5.9 | 62.5 |
| 2026-10-26 | N | 13:31 | BUY | bull_run2 | DU | UDU | 5 | chop | flat | 30 | 8.0 | 94.8 |
| 2026-10-27 | NO_CALL | | | | | | | | | | | |
| 2026-10-28 | NO_CALL | | | | | | | | | | | |
| 2026-10-29 | N | 11:56 | BUY | bull_run2 | DU | UDU | 5 | chop | flat | 20 | 4.5 | 40.0 |
| 2026-10-30 | N | 10:34 | SELL | bear_engulf | DU | DDU | 6 | chop | flat | 20 | 4.4 | 1.6 |
| 2026-11-02 | NO_CALL | | | | | | | | | | | |
| 2026-11-03 | Y | 12:52 | BUY | bull_run2 | DU | UDU | 5 | chop | flat | 20 | 7.2 | 72.2 |
| 2026-11-04 | NO_CALL | | | | | | | | | | | |
| 2026-11-05 | NO_CALL | | | | | | | | | | | |
| 2026-11-06 | NO_CALL | | | | | | | | | | | |
| 2026-11-08 | NO_CALL | | | | | | | | | | | |
| 2026-11-09 | NO_CALL | | | | | | | | | | | |
| 2026-11-11 | NO_CALL | | | | | | | | | | | |
| 2026-11-12 | N | 11:40 | SELL | bear_engulf | DU | DDU | 5 | chop | flat | 20 | 5.6 | 70.3 |
| 2026-11-13 | NO_CALL | | | | | | | | | | | |
| 2026-11-16 | NO_CALL | | | | | | | | | | | |

## What last-10 looks like on base clean34 hold losses vs wins

- Loss couple: [('DU', 13), ('DD', 10), ('UD', 8), ('UU', 7)]
- Win couple: [('UU', 10), ('DD', 9), ('DU', 8), ('UD', 8)]
- Loss stair: [('chop', 24), ('dn', 7), ('up', 4), ('lh_only', 2), ('hl_only', 1)]
- Win stair: [('chop', 23), ('dn', 6), ('hl_only', 3), ('lh_only', 2), ('up', 1)]
- Loss drift: [('with', 29), ('flat', 6), ('against', 3)]
- Win drift: [('with', 25), ('against', 7), ('flat', 3)]
- Loss favor_bin: [('f5+', 22), ('f3+', 9), ('f7+', 7)]
- Win favor_bin: [('f3+', 13), ('f5+', 13), ('f7+', 8), ('f<3', 1)]

## Exact instant entry check

1. Signal candle fires (clean34 MA ok).
2. Read bars `i-10 … i-1`: build couple / last3 / favor / stair / drift.
3. **Hold/entry allow** only if chosen pre10 rule passes (else skip — wait next signal).
4. Then place adaptive T1/SL path trade.

## Extra reject-noise pass (same hold)

| Rule | Hold 1d | Cover | Note |
|---|---:|---:|---|
| base clean34 gate | 47.95% | 100% | no pre10 |
| `couple_ok` only | 48.61% | 98.6% | tiny lift |
| allow `pre10_fp2` train-clean | 52.0% | 34.2% | higher hit, sparse |
| reject lossy `pre10_fp2` | 43.1% | 98.6% | no lift |
| hard favor7+stair / mid / hard | 28–37% | 82–97% | **hurts** hold |

**Read:** last-couple continuation (`UU`/`DD` etc.) is the only cheap instant filter that does not wreck cover; heavy last-10 structure locks overfit train and cut hold. Next: use last-10 for **which** signal on the day (rank/delay open), not only yes/no.
