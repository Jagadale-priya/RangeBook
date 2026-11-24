# Why blind DEEP failed + **walk-forward 100%** study (2021→today)

Data: **2021-01-01 → 2026-11-16** · T1=20.0 · SL≤10.0 · path win = target before SL

## Why ~30% on unknown 2026 (not bad luck)

- Blind book on 2026: **400** calls @ **30.5%**
- Losses with MFE≥20 (SL-first): **188/278 (67.6%)**
- MAE win/loss: 60.89 / 81.07 · MFE win/loss: 103.86 / 64.31

### Failure feature tilt (loss% − win%)

| Feature | Loss% | Win% | Δ |
|---|---:|---:|---:|
| vix_LOW | 34.9 | 27.9 | 7.0 |
| NOT close_ok | 34.2 | 32.8 | 1.4 |
| hm09 | 20.9 | 21.3 | -0.4 |
| adv_hi | 24.1 | 27.0 | -2.9 |
| pre3_opp>=2 | 47.8 | 52.5 | -4.7 |
| day_mid | 43.2 | 48.4 | -5.2 |

- Loss patterns: `[('bear_engulf', 42), ('bear_run3', 37), ('bear_run2', 34), ('bull_run2', 20), ('bull_run3', 20), ('bull_engulf', 19)]`
- Loss prior3: `[('DDU', 39), ('DDD', 39), ('DUU', 38), ('UUD', 38), ('DUD', 36), ('UDD', 33)]`
- Loss VIX: `[('LOW', 97), ('NORMAL', 94), ('ELEVATED', 63), ('HIGH', 22), ('UNK', 2)]`

### Root causes

- Train-locked fingerprints are rare geometries that were path-perfect in 2024-25 only.
- On 2026 the same fingerprint reappears in a different tape; SL often prints first even when MFE later ≥20.
- Fine keys overfit local history → high in-sample 100%, weak blind OOS.
- Peeked DEEP looked 100% on 2026 because 2026 was used in the lock filter (not unknown).

## Walk-forward proof (only honest unknown test)

Each row: micros locked on **all prior years only**, then scored on test year.

| Test year | Train | Dense micros | OOS hit% | OOS n | 1/day hit% | 1/day cover | Strict hit% | Strict n |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 | [2021, 2022] | 248 | 23.44% | 418 | 22.28% | 82.4% | 22.77% | 404 |
| 2024 | [2021, 2022, 2023] | 382 | 30.62% | 467 | 31.13% | 85.5% | 28.6% | 472 |
| 2025 | [2021, 2022, 2023, 2024] | 529 | 30.18% | 434 | 33.82% | 83.1% | 30.24% | 420 |
| 2026 | [2021, 2022, 2023, 2024, 2025] | 658 | 30.45% | 335 | 30.64% | 80.1% | 30.77% | 338 |

## Historical ACC100 atlases (100% on included years — not a future guarantee)

- **ACC100_MULTIYEAR_ATLAS** (≥4 years present, zero losses all years): 140 micros
- **ACC100_EVERY_YEAR** (present every year 2021–2026): 1 micros

| Year | Atlas full n@hit | Atlas 1/day cover | Every-year full n@hit | Every-year 1/day cover |
|---:|---|---:|---|---:|
| 2021 | 119@100.0% | 36.0% | 1@100.0% | 0.4% |
| 2022 | 107@100.0% | 34.4% | 1@100.0% | 0.4% |
| 2023 | 98@100.0% | 32.2% | 1@100.0% | 0.4% |
| 2024 | 116@100.0% | 36.3% | 1@100.0% | 0.4% |
| 2025 | 106@100.0% | 35.3% | 1@100.0% | 0.4% |
| 2026 | 91@100.0% | 35.6% | 1@100.0% | 0.5% |

## What “most accurate 100% logic” can honestly be

1. **Walk-forward OOS** rarely stays 100% at high volume under T20/SL≤10 — that is the real bar.
2. **Multi-year atlas / every-year** books are the safest *historical* 100% sets (few calls).
3. Peeking the test year (old DEEP_1CPD) invents fake 100% — do not deploy as proof.
4. Next accuracy gains: stricter fingerprints that survive WF, or relax T1/SL only if needed for coverage.

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_wf100_2021`
Elapsed: 4091.6s
