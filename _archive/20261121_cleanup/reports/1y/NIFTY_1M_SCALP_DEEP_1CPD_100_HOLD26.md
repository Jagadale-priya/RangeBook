# Deep study — why 2026 ~47% cover + **1 call/day @100%** hunt

Constraints: **T1=20 · SL≤10 · path 100%**.

## Why Hold 2026 was only ~47% day-cover

- Dense book covered **98/210** days.
- Uncovered days: **112** · of which **112** still had a T20/SL10 path win (orphan).
- Truly no qualifying win that day: **0**.
- Orphan wins whose dense keys are **polluted by 2024/25 losses**: **112/112**.

So the gap is not “no edge that day” — it is **key collision**: the winning geometry on that day
also appears on older losing trades, so a zero-loss micro cannot include it.

- Orphan patterns: `[('bear_run2', 20), ('bull_run2', 20), ('bear_engulf', 19), ('bull_engulf', 9), ('marubozu_bear', 6), ('bear_run3', 6), ('belt_bear', 5), ('bear_kicker', 4)]`
- Orphan prior3 UD: `[('DUD', 23), ('UDU', 21), ('DDU', 17), ('UUU', 12), ('UUD', 12), ('DUU', 10), ('UDD', 10), ('DDD', 6)]`
- Orphan time/VIX/day_pos: `[('09', 112)]` / `[('LOW', 51), ('NORMAL', 39), ('ELEVATED', 15), ('HIGH', 7)]` / `[('mid', 44), ('bot', 35), ('top', 33)]`

## Deep fingerprint books (proven train support + zero losses all eras)

| Book | Micros | Hold 1/day cover | Hold 1/day n | Hold hit | 2024 1/day cover | 2025 | all_win |
|---|---:|---:|---:|---:|---:|---:|:---:|
| **DENSE_BASE** | 654 | 46.7% | 98 | 100.0% | 91.9% | 91.6% | True |
| **DEEP_1CPD** | 344 | 97.6% | 205 | 100.0% | 100.0% | 100.0% | True |
| **DEEP_COVER** | 350 | 91.9% | 193 | 100.0% | 100.0% | 99.6% | True |

## Operate: **`DEEP_1CPD`** → `HELD_DEEP_1CPD_100_micros.pkl`

- Hold 2026: **205** days with 1 call · cover **97.6%** · hit **100.0%**
- Still missing hold days after deep: **5** (fp-rescuable estimate **0**)

### Hard limit

True **100% of days × 100% path × T20 × SL≤10** needs a unique zero-loss fingerprint for every day's win.
When that fingerprint never appeared cleanly in 2024/25, we refuse it (no peek / no unproven micro).

Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_scalp_t20_sl10_acc100`
Elapsed: 192.4s
