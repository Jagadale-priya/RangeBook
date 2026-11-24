# NIFTY 1m — **More accurate** ≥25pt entry (deep)

> Precision over calls. Metric = **one-direction** quality, not raw MFE touch.

Window **2026-05-26 → 2026-11-16** (120d). OOS from **2026-08-20**.

## Accuracy metrics (stricter than raw m25)

| Metric | Meaning | Why |
|---|---|---|
| **m25_first** | +25 pts before −25 adverse | True directional capture |
| **clean15** | MFE≥25 and MAE≤15 | Move is mostly one-way |
| raw m25 | MFE≥25 anytime | Old IGN100 metric (can have huge MAE) |

Ground-truth ≥25pt impulses in window: **1149**.

### What is usually true at real impulse ignition

| Feature | % of true ≥25 ignitions |
|---|---:|
| `prev_opposite` | 99.0 |
| `not_extreme` | 86.2 |
| `ctrl` | 83.7 |
| `bounce` | 58.7 |
| `ad_with` | 55.7 |
| `big_body` | 35.8 |
| `held` | 27.9 |
| `disp10` | 24.0 |
| `room_ok` | 11.0 |
| `runway2` | 9.9 |
| `disp15` | 6.9 |
| `hold_break` | 0.8 |

## 1) Priority gates (ranked internally; table by m25_first)

| Gate | Verdict | n | **m25_first%** | OOS | clean15% | raw m25% | T25% |
|---|---|---:|---:|---:|---:|---:|---:|
| `IGN run3 + ctrl+room+disp10+bounce+ad+held` | **THIN** | 3 | **100.0** | 100.0 | 66.67 | 100.0 | 100.0 |
| `IGN + ctrl+room+disp10+bounce+ad` | **WEAK** | 15 | **66.67** | 100.0 | 53.33 | 73.33 | 53.33 |
| `IGN + ctrl+room+disp15+bounce` | **THIN** | 3 | **66.67** | 100.0 | 66.67 | 66.67 | 33.33 |
| `OLD IGN100 ignition ctrl+room+disp10+bounce` | **WEAK** | 22 | **63.64** | 83.33 | 50.0 | 77.27 | 45.45 |
| `IGN + prev_opp+ctrl+ad+disp10+room` | **WEAK** | 24 | **62.5** | 63.64 | 58.33 | 70.83 | 41.67 |
| `IGN + prev_opp+ctrl+ad+disp10+bounce` | **WEAK** | 192 | **56.25** | 63.92 | 34.9 | 62.5 | 32.29 |
| `OLD IGN100 → clean15` | **WEAK** | 22 | **50.0** | 75.0 | 50.0 | 77.27 | 45.45 |
| `IGN + ctrl+room+disp10+bounce+held` | **THIN** | 6 | **50.0** | 60.0 | 33.33 | 83.33 | 50.0 |
| `IGN + ctrl+room+disp10+bounce+!extreme+held` | **THIN** | 6 | **50.0** | 60.0 | 33.33 | 83.33 | 50.0 |
| `COMP engulf/maru + ctrl+ad+held+bounce+room` | **WEAK** | 77 | **48.05** | 44.74 | 28.57 | 58.44 | 40.26 |
| `COMP strong+ctrl+ad+held+room+disp10` | **WEAK** | 155 | **47.1** | 42.86 | 27.74 | 59.35 | 41.94 |
| `IGN + prev_opp+held+ad+disp10+room+bounce` | **THIN** | 3 | **33.33** | 50.0 | 33.33 | 33.33 | 33.33 |
| `COMP hold_break+ctrl+ad+disp10+room` | **THIN** | 0 | **None** | None | None | None | None |
| `COMP hold_break+ctrl+held+bounce+disp10` | **THIN** | 0 | **None** | None | None | None | None |

## 2) Exhaustive hunt (ignition runs)

### Best m25_first (≥90%)

_None ≥90% with n≥10._

### Best clean15 (≥85%)

_None ≥85% with n≥8._

## 3) Greedy tighten (from ctrl+AD+disp10 ignition)

- **m25_first path:** `base → runway2 → hold_break → run3 → held → bounce → big_body`
  - final n=8 prec=87.5% OOS=100.0%
- **clean15 path:** `base → room_ok → bounce → prev_opposite → not_extreme → big_body`
  - final n=8 prec=50.0% OOS=100.0%

## 4) Most accurate rule now

**Best effort (not proven):** `IGN run3 + ctrl+room+disp10+bounce+ad+held` · THIN
- m25_first 100.0% OOS 100.0% · clean15 66.67%

## 5) vs old IGN100 (raw m25 100%)

- Old IGN100 optimized **raw MFE≥25** — can still chop hard (MAE 40–180 on some hits).
- This pass requires **m25_first / clean15** — harder, more honest “one direction”.
- If a new PROVEN_100 appears above, **replace** live `run_ignition_100` with it.
- If not, keep IGN100 but treat it as sparse raw-25, not clean one-way.

_Generated in 361.1s._
