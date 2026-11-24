# How OR break+retest works · calls · move catch

Window **2025-12-26 → 2026-11-16** (220 sessions).

## How it works (best book: `R6_break_htf_OR30`)

```
09:15–09:44  Build OR30 = high/low of first 30 one-minute bars
             UP zone  = OR high ± 0.5×ATR14
             DOWN zone = OR low  ± 0.5×ATR14

Later         Price CLOSES beyond OR high (bull break) or OR low (bear break)
              then EXTENDS away from the zone

Entry         Price comes BACK and retests the broken edge zone
              BUY retest of broken OR-high zone  (only if 15m bias = up)
              SELL retest of broken OR-low zone (only if 15m bias = down)

Risk          SL beyond far side of that zone
Target        3× risk (3R) · max hold 90 minutes · max 1 call/day
```

We are **not** fading the open range. We trade the **break continuation** after a retest.

## How many calls?

| Book | Calls | /day | Days with a call | Hit @3R | Avg risk | Sum pts |
|---|---:|---:|---:|---:|---:|---:|
| `R6_break_htf_OR30` | **119** | **0.54** | 119 (54.1%) | 44.5% | 7.0 | 613.4 |
| `R6_break_htf_OR15` | **115** | **0.52** | 115 (52.3%) | 38.3% | 9.3 | 490.1 |
| `R2_break_OR30` | **152** | **0.69** | 152 (69.1%) | 40.1% | 6.9 | 600.8 |
| `R2_break_OR15` | **156** | **0.71** | 156 (70.9%) | 38.5% | 9.3 | 725.2 |

**Best book density:** ~**0.54 call/day** (a call on **54.1%** of sessions — about **119/220** days).
Timing mix (R6 OR30): before 11:00 **67** · 11–13 **33** · after 13:00 **19**.

## Did we catch moves?

Measured as **remaining-day MFE** after entry (how far price ran in our direction that session), independent of whether 3R hit first.

| Book | Avg MFE | Med MFE | Avg adverse | % calls MFE≥15 | % ≥25 | % ≥40 | Avg share of day range |
|---|---:|---:|---:|---:|---:|---:|---:|
| `R6_break_htf_OR30` | 82.3 | 55.9 | 94.5 | 85.7% | 74.8% | 59.7% | 49.3% |
| `R6_break_htf_OR15` | 85.5 | 61.6 | 96.0 | 87.0% | 73.0% | 66.1% | 48.8% |
| `R2_break_OR30` | 88.5 | 63.5 | 91.5 | 88.2% | 78.3% | 63.8% | 51.8% |
| `R2_break_OR15` | 93.6 | 68.0 | 100.9 | 87.8% | 76.3% | 69.2% | 50.3% |

On **R6 OR30** specifically:
- **44.5%** of calls hit **+3R** (avg win **20.4 pts**, avg loss **-7.1 pts**).
- After entry, price still ran **≥15 pts** our way on **85.7%** of calls, **≥25 pts** on **74.8%**, **≥40 pts** on **59.7%**.
- Average remaining-day favorable run ≈ **82.3 pts** (median **55.9**); among 3R winners avg day MFE ≈ **100.6 pts**.
- So yes: when it works it is sitting on a **real continuation move**, not a tiny scalp flicker. When it fails, SL is ~**7.1 pts** (the zone width).

### Sample wins (R6 OR30)

| Day | HM | Side | Entry | Risk | Pts |
|---|---|---|---:|---:|---:|
| 2026-01-09 | 11:31 | SELL | 25818.35 | 8.66 | 25.99 |
| 2026-01-14 | 11:32 | BUY | 25750.45 | 8.0 | 23.99 |
| 2026-01-16 | 12:31 | BUY | 25743.25 | 6.99 | 20.97 |
| 2026-01-22 | 10:39 | SELL | 25302.45 | 6.05 | 18.15 |
| 2026-02-01 | 10:18 | BUY | 25342.55 | 6.46 | 19.39 |
| 2026-02-04 | 14:26 | BUY | 25791.2 | 8.09 | 24.27 |

### Sample losses (R6 OR30)

| Day | HM | Side | Entry | Risk | Pts |
|---|---|---|---:|---:|---:|
| 2025-12-30 | 10:37 | BUY | 25956.15 | 4.79 | -4.79 |
| 2026-01-01 | 10:26 | SELL | 26149.25 | 6.59 | -6.59 |
| 2026-01-02 | 10:04 | BUY | 26249.65 | 5.54 | -5.54 |
| 2026-01-05 | 10:36 | BUY | 26358.25 | 6.01 | -6.01 |

## Plain answer

1. **How:** wait for open-range **break**, then buy/sell the **retest** with trend (HTF).
2. **Calls:** ~**0.54/day** (1 max) — about **119** calls in 220 days.
3. **Catch moves:** yes on a large share — **74.8%** saw ≥25pt continuation after entry; **44.5%** banked full 3R. Not every big day is caught (only days with a clean break+retest+HTF).
