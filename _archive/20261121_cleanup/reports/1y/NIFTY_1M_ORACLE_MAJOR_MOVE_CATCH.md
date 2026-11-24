# NIFTY 1m — Oracle T15 clean · **major-move catch**

> **RESEARCH ONLY — not changing Scalper live / UI.**

Window **2026-10-15 → 2026-11-16** (22 sessions) · 09:30–14:30 · EMA34 trail.

**Primary major** = Oracle T15 path-win **and** trail MFE ≥ **40**. Impulse ≥40pts/≥4 bars is a secondary tag. Pool-wide MFE≥40 shown for context only.

## 1) Coverage vs Oracle T15 clean

| Book | Count | Coverage of Oracle-majors |
|---|---:|---:|
| Oracle-majors (T15 win ∩ MFE≥40) | 845 | 100% |
| Oracle T15 raw (all path-wins) | 1686 | 100.0% of Oracle-majors |
| **Oracle T15 clean (TierAB)** | 18 | **2.13%** |
| Setup TierAB alone | 18 | 2.13% |
| **Missed by clean** | 827 | 97.87% |
| All pool MFE≥40 (context) | 845 | clean covers 2.13% |
| Impulse runs | 119 | clean covers 0.0% of impulse bars |

## 2) Missed Oracle-major autopsy (features at entry)

n=827 · avg MFE=88.93

| Feature | % true on missed Oracle-majors |
|---|---:|
| held | 45.6 |
| ad_with | 83.2 |
| clear_path | 8.2 |
| runway_2atr | 14.9 |
| hold_break | 1.7 |
| bounce | 64.0 |
| control | 77.4 |
| into_extreme | 23.8 |
| prev_opposite | 21.5 |
| impulse tag | 4.5 |

Top patterns on missed Oracle-majors:

| Pattern | n |
|---|---:|
| `bull_run3` | 131 |
| `bear_run3` | 122 |
| `bull_run2` | 111 |
| `bear_engulf` | 79 |
| `belt_bear` | 61 |
| `bear_run2` | 53 |
| `three_outside_dn` | 51 |
| `marubozu_bear` | 45 |
| `bull_kicker` | 33 |
| `bull_engulf` | 26 |
| `marubozu_bull` | 26 |
| `belt_bull` | 21 |

## 3) Complementary gate grid (blind)

Recover% = share of **clean-missed Oracle-majors** that match the gate. gap15 = deployable multi-call book on full pool. Major prec = share of gap calls with MFE≥40.

| Gate | Recover% | n rec | gap n | cpd | T15 hit% | Major prec% | avg MFE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `AD + runway_2ATR` | 14.15 | 117 | 148 | 6.73 | 60.14 | 29.73 | 35.82 |
| `HELD + runway_2ATR` | 12.45 | 103 | 115 | 5.23 | 69.57 | 30.43 | 40.08 |
| `HELD + AD + runway_2ATR` | 11.73 | 97 | 112 | 5.09 | 68.75 | 30.36 | 40.56 |
| `Oracle-major proxy: AD + ctrl + runway2` | 11.73 | 97 | 139 | 6.32 | 61.87 | 28.78 | 35.87 |
| `into_extreme + AD + runway2` | 9.31 | 77 | 76 | 3.45 | 69.74 | 35.53 | 42.21 |
| `AD + clear_path` | 6.65 | 55 | 121 | 5.5 | 42.98 | 17.36 | 23.53 |
| `PROVEN3: hold_break|bounce + ctrl + runway2` | 5.8 | 48 | 90 | 4.09 | 62.22 | 31.11 | 39.71 |
| `clear_path + runway_2ATR` | 5.44 | 45 | 105 | 4.77 | 40.0 | 18.1 | 23.57 |
| `clear + runway2 + AD (no HELD)` | 4.84 | 40 | 85 | 3.86 | 47.06 | 20.0 | 27.22 |
| `AD + clear + runway2` | 4.84 | 40 | 85 | 3.86 | 47.06 | 20.0 | 27.22 |
| `HELD + clear_path` | 4.72 | 39 | 67 | 3.05 | 65.67 | 28.36 | 36.48 |
| `ctrl + runway2 + clear` | 4.11 | 34 | 91 | 4.14 | 43.96 | 16.48 | 24.79 |
| `HELD + AD + clear_path` | 3.63 | 30 | 53 | 2.41 | 66.04 | 26.42 | 36.63 |
| `HELD + AD + clear + !extreme` | 3.63 | 30 | 53 | 2.41 | 66.04 | 26.42 | 36.63 |
| `HELD + clear + runway_2ATR` | 3.26 | 27 | 48 | 2.18 | 66.67 | 25.0 | 35.05 |
| `prev_opp + clear + runway2` | 1.09 | 9 | 51 | 2.32 | 31.37 | 9.8 | 20.21 |
| `Impulse-pre: prev_opp + clear + AD` | 0.97 | 8 | 48 | 2.18 | 47.92 | 12.5 | 25.35 |
| `HELD + hold_break + runway_2ATR` | 0.85 | 7 | 22 | 1.0 | 63.64 | 31.82 | 46.93 |
| `Impulse-pre + HELD` | 0.6 | 5 | 27 | 1.23 | 62.96 | 14.81 | 33.54 |
| `TierAB + clear_path` | 0.0 | 0 | 12 | 0.55 | 50.0 | 16.67 | 47.02 |
| `TierAB + runway_2ATR` | 0.0 | 0 | 10 | 0.45 | 50.0 | 10.0 | 42.97 |

## 4) Winner

Rules: recover ≥40% of clean-missed majors; and (gap15 T15 hit ≥58% with n≥25 **or** major prec ≥45%).

**Recommended major gate:** `into_extreme + AD + runway2`

| Metric | Value |
|---|---:|
| Recovered missed majors | 77 (9.31%) |
| Gap15 calls | 76 |
| T15 hit% | 69.74 |
| Major precision | 35.53% |
| Avg MFE | 42.21 |

Note: best accurate complementary gate (T15≥58%, n≥25; ranked by major_prec + T15 hit + recover) — no gate recovered ≥40% of clean-missed Oracle-majors (TierAB is sparse vs MFE≥40 Oracle set)

## 5) Union book: clean ∪ major gate

| Book | n | cpd | T15 hit% | Majors cov% | Miss recovered% | Major prec% | avg MFE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `oracle_t15_clean gap15` | 35 | 1.59 | 100.0 | 1.78 | 0.0 | 42.86 | 59.75 |
| `into_extreme + AD + runway2` | 76 | 3.45 | 69.74 | 3.2 | 3.26 | 35.53 | 42.21 |
| `clean ∪ into_extreme + AD + runway2` | 101 | 4.59 | 79.21 | 4.26 | 2.78 | 35.64 | 46.29 |
| `clean peek gap15` | 35 | 1.59 | 100.0 | 1.78 | 0.0 | 42.86 | 59.75 |
| `clean peek ∪ into_extreme + AD + runway2` | 101 | 4.59 | 79.21 | 4.26 | 2.78 | 35.64 | 46.29 |

**Ship later (not this run):** Scalper mode `oracle_t15_clean_major` = `oracle_t15_clean` ∪ `into_extreme + AD + runway2` (gap15 dedupe).

## 6) Sample missed majors (highest MFE)

| Day | HM | Side | MFE | Pattern | held | AD | clear | runway2 | hold_break | impulse |
|---|---|---|---:|---|---|---|---|---|---|---|
| 2026-11-06 | 14:11 | BUY | 337.45 | `marubozu_bull` | False | False | True | False | False | False |
| 2026-11-06 | 14:14 | BUY | 326.2 | `bull_run2` | False | True | False | False | False | False |
| 2026-11-06 | 14:19 | BUY | 325.2 | `bull_run2` | False | True | False | False | False | False |
| 2026-11-06 | 14:23 | BUY | 316.65 | `bull_kicker` | True | True | False | False | False | False |
| 2026-11-06 | 14:26 | BUY | 310.35 | `bull_run2` | True | True | True | True | False | False |
| 2026-11-06 | 14:27 | BUY | 305.7 | `bull_run3` | True | True | True | False | False | False |
| 2026-11-06 | 14:28 | BUY | 302.0 | `bull_run3` | True | True | False | False | False | False |
| 2026-10-23 | 09:43 | SELL | 296.1 | `bear_engulf` | False | False | False | False | False | False |
| 2026-10-23 | 09:44 | SELL | 282.65 | `three_outside_dn` | False | True | False | False | False | False |
| 2026-10-23 | 09:47 | SELL | 276.4 | `dark_cloud` | False | True | False | False | False | False |
| 2026-10-23 | 09:45 | SELL | 272.45 | `bear_run3` | False | True | False | False | False | False |
| 2026-10-21 | 11:06 | SELL | 268.6 | `belt_bear` | False | False | False | False | False | False |
| 2026-10-23 | 09:48 | SELL | 265.75 | `belt_bear` | False | True | False | False | False | False |
| 2026-10-21 | 11:07 | SELL | 255.0 | `belt_bear` | False | True | False | False | False | False |
| 2026-10-23 | 09:49 | SELL | 254.65 | `belt_bear` | False | True | False | False | False | False |
| 2026-10-26 | 09:49 | BUY | 247.5 | `tweezer_bot` | False | False | False | False | False | True |
| 2026-10-21 | 11:08 | SELL | 244.3 | `belt_bear` | True | True | False | False | False | False |
| 2026-10-21 | 11:09 | SELL | 243.6 | `bear_run3` | True | True | False | False | False | False |
| 2026-10-21 | 11:13 | SELL | 243.3 | `bear_run2` | True | True | False | False | False | False |
| 2026-10-21 | 11:15 | SELL | 238.35 | `bear_engulf` | True | False | False | False | False | False |
| 2026-10-23 | 09:51 | SELL | 235.65 | `bear_engulf` | False | True | False | False | False | False |
| 2026-10-21 | 11:16 | SELL | 232.4 | `three_outside_dn` | True | True | False | False | False | False |
| 2026-10-21 | 11:10 | SELL | 232.2 | `marubozu_bear` | True | True | False | False | False | False |
| 2026-10-26 | 09:50 | BUY | 231.2 | `bull_run2` | False | False | False | False | False | False |
| 2026-10-23 | 09:54 | SELL | 230.9 | `bear_engulf` | False | True | False | False | False | False |

## 7) Takeaway

- Oracle T15 clean stays the **accurate core** (Tier A/B ∩ path-win).
- Major moves often ignite **without** Tier A/B — need a complementary runway/clear/impulse-pre gate.
- Union only if the major gate recovers enough misses without collapsing T15 hit / flooding calls.

_Generated in 99.6s._
