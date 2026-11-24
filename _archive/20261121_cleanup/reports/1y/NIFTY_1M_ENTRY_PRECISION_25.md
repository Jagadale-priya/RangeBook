# NIFTY 1m — **Accurate ENTRY** (price + BUY/SELL) · ≥25pt moves

> **RESEARCH ONLY.** Density ignored. Precision is the only score that matters.

Window **2026-08-12 → 2026-11-16** (66d). OOS from **2026-09-29**.

## What we want

```
INPUT  : 1m candle pattern completes
OUTPUT : entry_price = close of that bar
         side        = BUY or SELL
SUCCESS: price then runs ≥25 pts in that direction (raw MFE)
GOAL   : precision → 100% (every call is a real ≥25pt move)
```

Suggested core from major-move autopsy: **`run2|run3 + control + AD`** (± HELD / !extreme).

## 1) Gate precision table (ranked by m25%)

| Gate | Verdict | n | **m25%** | m25-first% | T15% | Maj% | avg MFE | OOS m25% |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `run2|3 + ctrl + AD + HELD + room` | **NOT_PROVEN** | 100 | **57.0** | 48.0 | 54.0 | 28.0 | 41.85 | 72.22 |
| `run2|3 + ctrl + AD + HELD + room + !extreme` | **NOT_PROVEN** | 100 | **57.0** | 48.0 | 54.0 | 28.0 | 41.85 | 72.22 |
| `run3 + ctrl + AD + HELD + room + !extreme` | **NOT_PROVEN** | 72 | **56.94** | 51.39 | 58.33 | 27.78 | 39.06 | 67.57 |
| `HELD + hold_break + ctrl` | **NOT_PROVEN** | 77 | **55.84** | 46.75 | 53.25 | 29.87 | 41.42 | 68.09 |
| `run2|3 + ctrl + AD + HELD + runway2` | **NOT_PROVEN** | 255 | **55.69** | 44.71 | 56.86 | 24.71 | 36.07 | 62.89 |
| `HELD + ctrl + AD` | **NOT_PROVEN** | 2466 | **54.3** | 46.43 | 55.52 | 23.64 | 37.54 | 68.72 |
| `run2 + ctrl + AD + HELD` | **NOT_PROVEN** | 345 | **54.2** | 46.67 | 51.88 | 21.45 | 37.96 | 65.57 |
| `HELD + ctrl + AD + !extreme` | **NOT_PROVEN** | 1270 | **53.15** | 47.24 | 53.86 | 23.39 | 37.09 | 67.25 |
| `ctrl + AD` | **NOT_PROVEN** | 7484 | **52.7** | 45.63 | 37.56 | 16.45 | 37.29 | 63.65 |
| `run2|3 + ctrl + AD + HELD` | **NOT_PROVEN** | 1123 | **52.45** | 44.97 | 52.63 | 22.08 | 36.63 | 66.3 |
| `run2|3 + ctrl + AD + HELD + hold_break` | **NOT_PROVEN** | 42 | **52.38** | 42.86 | 57.14 | 30.95 | 38.82 | 68.0 |
| `TierAB (oracle_t15_clean twin)` | **NOT_PROVEN** | 255 | **52.16** | 47.45 | 50.59 | 20.39 | 38.23 | 63.93 |
| `run3 + ctrl + AD` | **NOT_PROVEN** | 2219 | **51.69** | 45.38 | 38.31 | 16.22 | 36.15 | 62.77 |
| `run3 + ctrl + AD + HELD` | **NOT_PROVEN** | 778 | **51.67** | 44.22 | 52.96 | 22.37 | 36.04 | 66.67 |
| `run2|3 + ctrl + AD` | **NOT_PROVEN** | 3532 | **51.08** | 44.73 | 36.44 | 15.35 | 36.13 | 62.46 |
| `run2|3 alone` | **NOT_PROVEN** | 6821 | **50.81** | 44.19 | 32.24 | 13.5 | 35.87 | 62.52 |
| `run3 + ctrl + AD + !extreme` | **NOT_PROVEN** | 1762 | **50.57** | 45.23 | 33.37 | 14.42 | 35.33 | 61.07 |
| `run2|3 + ctrl + AD + hold_break` | **NOT_PROVEN** | 99 | **50.51** | 42.42 | 42.42 | 20.2 | 37.92 | 63.27 |
| `run2 + ctrl + AD` | **NOT_PROVEN** | 1313 | **50.04** | 43.64 | 33.28 | 13.86 | 36.09 | 61.97 |
| `run2|3 + ctrl + AD + !extreme` | **NOT_PROVEN** | 2898 | **49.65** | 44.03 | 31.78 | 13.73 | 35.33 | 61.01 |
| `run3 + ctrl + AD + HELD + !extreme` | **NOT_PROVEN** | 386 | **49.48** | 44.3 | 50.26 | 23.06 | 36.14 | 66.48 |
| `run2|3 + ctrl + AD + HELD + !extreme` | **NOT_PROVEN** | 578 | **48.44** | 42.73 | 48.44 | 22.32 | 35.75 | 64.75 |
| `run2|3 + ctrl + AD + prev_opp + HELD` | **NOT_PROVEN** | 0 | **None** | None | None | None | None | None |

## 2) Auto-search on run2|3 (feature combos ≥90% m25, n≥8)

_No run2|3 combo cleared 90% m25 with n≥8._

## 3) Verdict — most accurate entry logic

**No 100% book.** Highest precision: `run2|3 + ctrl + AD + HELD + room` · m25=**57.0%** · n=100 · OOS 72.22% · T15 54.0% · maj 28.0%

100% on ≥25pt raw moves is extremely hard once n is meaningful — report the tightest stable gate, not a fake perfect.

## 5) Sample entries — `run2|3 + ctrl + AD + HELD + room`

| Day | HM | Side | **Entry** | Pattern | MFE | m25 | T15 | Maj |
|---|---|---|---:|---|---:|---|---|---|
| 2026-08-12 | 09:38 | **SELL** | **24424.25** | `bear_run2` | 66.75 | True | True | True |
| 2026-08-12 | 09:47 | **SELL** | **24406.8** | `bear_run3` | 49.3 | True | True | True |
| 2026-08-13 | 11:57 | **BUY** | **24371.2** | `bull_run2` | 43.7 | True | True | True |
| 2026-08-13 | 11:58 | **BUY** | **24376.85** | `bull_run3` | 38.05 | True | True | False |
| 2026-08-13 | 11:59 | **BUY** | **24386.45** | `bull_run3` | 28.45 | True | True | False |
| 2026-08-13 | 12:00 | **BUY** | **24403.4** | `bull_run3` | 11.5 | False | False | False |
| 2026-08-13 | 12:03 | **BUY** | **24412.95** | `bull_run2` | 1.95 | False | False | False |
| 2026-08-14 | 10:25 | **SELL** | **24334.7** | `bear_run3` | 37.9 | True | True | False |
| 2026-08-17 | 09:56 | **SELL** | **24292.2** | `bear_run3` | 64.05 | True | True | True |
| 2026-08-17 | 10:55 | **SELL** | **24239.9** | `bear_run2` | 12.95 | False | False | False |
| 2026-08-17 | 12:46 | **BUY** | **24325.4** | `bull_run3` | 34.2 | True | True | False |
| 2026-08-19 | 10:17 | **SELL** | **24080.25** | `bear_run3` | 52.35 | True | True | False |
| 2026-08-19 | 10:18 | **SELL** | **24075.2** | `bear_run3` | 47.3 | True | True | False |
| 2026-08-20 | 09:45 | **BUY** | **24214.15** | `bull_run3` | 12.7 | False | False | False |
| 2026-08-20 | 10:10 | **BUY** | **24216.3** | `bull_run2` | 10.55 | False | False | False |
| 2026-08-24 | 11:44 | **SELL** | **24187.15** | `bear_run2` | 11.5 | False | False | False |
| 2026-08-24 | 13:35 | **SELL** | **24165.9** | `bear_run3` | 21.6 | False | False | False |
| 2026-08-24 | 13:36 | **SELL** | **24164.45** | `bear_run3` | 20.15 | False | False | False |
| 2026-08-25 | 11:55 | **BUY** | **24184.3** | `bull_run3` | 5.65 | False | False | False |
| 2026-08-28 | 10:24 | **BUY** | **24170.2** | `bull_run3` | 2.15 | False | False | False |
| 2026-08-31 | 11:56 | **BUY** | **24083.75** | `bull_run3` | 1.4 | False | False | False |
| 2026-08-31 | 14:24 | **SELL** | **24024.75** | `bear_run3` | 4.25 | False | False | False |
| 2026-08-31 | 14:25 | **SELL** | **24024.55** | `bear_run3` | 4.05 | False | False | False |
| 2026-09-01 | 12:10 | **BUY** | **24129.95** | `bull_run2` | 2.25 | False | False | False |
| 2026-09-01 | 13:16 | **SELL** | **24043.65** | `bear_run3` | 90.1 | True | True | True |

Failures in sample (m25=False): **26** — these are why precision < 100%.

## 6) Bottom line

- We are **not** optimizing call count.
- Entry = **pattern close** + **side from bull/bear run**.
- Ship only a gate that is **PROVEN_100** or at least **PROMISING_95** on TRAIN and OOS.
- If union with TierAB drops m25 below 90%, keep books separate.

_Generated in 58.1s._
