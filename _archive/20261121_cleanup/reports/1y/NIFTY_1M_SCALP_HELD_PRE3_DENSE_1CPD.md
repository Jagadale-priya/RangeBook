# NIFTY 1m — **HOLD** ACC100_PRE3_RAW + densify toward **1 call/day**

Constraints unchanged: **T1=20** · **SL≤10** · **100% path** (target before SL).

Held baseline: `ACC100_PRE3_RAW` (72 micros).

## Oracle ceiling (days with ≥1 possible T20/SL10 path win)

| Era | Win days | All days | Max cover |
|---|---:|---:|---:|
| E2024 | 247 | 247 | 100.0% |
| E2025 | 249 | 249 | 100.0% |
| HOLD | 210 | 210 | 100.0% |
| FWD | 5 | 5 | 100.0% |

## Densify variants

| Variant | Micros | Total | cpd_all | 2024 n/hit/cover | 2025 | Hold | FWD | all_win |
|---|---:|---:|---:|---|---|---|---|:---:|
| **HELD_BASE_g4** | 97 | 349 | 0.491 | 207@100.0%/55.1% | 113@100.0%/36.9% | 29@100.0%/12.4% | 0@0.0% | True |
| **DENSE_g4_m11** | 599 | 1522 | 2.141 | 709@100.0%/90.7% | 671@100.0%/91.6% | 140@100.0%/46.2% | 2@100.0% | True |
| **DENSE_g2_m11** | 625 | 1579 | 2.221 | 736@100.0%/90.7% | 698@100.0%/91.6% | 143@100.0%/46.2% | 2@100.0% | True |
| **DENSE_g1_m11** | 654 | 1643 | 2.311 | 765@100.0%/91.9% | 729@100.0%/91.6% | 147@100.0%/46.7% | 2@100.0% | True |
| **DENSE_g2_m21** | 98 | 352 | 0.495 | 209@100.0%/55.5% | 114@100.0%/36.9% | 29@100.0%/12.4% | 0@0.0% | True |
| **DENSE_g4_m22** | 15 | 69 | 0.097 | 34@100.0%/13.0% | 31@100.0%/11.6% | 4@100.0%/1.9% | 0@0.0% | True |

## Operate now: **`DENSE_g1_m11`** → alias `HELD_PRE3_DENSE_1CPD`

- Total calls: **1643** · blended cpd_all **2.311** (target 1.0)
- Hold cover: **46.7%** of 2026 sessions · 147 calls @ 100.0%
- 2024 cover: **91.9%** · 2025: **91.6%**

If cpd_all < 1.0: oracle ceiling shows not every day has *any* T20/SL10 path win — true 1/day @100% is impossible on those days without relaxing T1 or SL.

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_t20_sl10_acc100`
Elapsed: 95.1s
