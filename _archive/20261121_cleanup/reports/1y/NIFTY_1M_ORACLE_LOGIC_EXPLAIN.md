# What is ORACLE T12 / T15?

## Short answer

**ORACLE is not a live entry system.** It answers: *“Did at least one textbook candle that day win under the exit rules?”* and picks the **first** such winning event (hindsight).

| | ORACLE T12 | ORACLE T15 | HELD T12 (live-style) |
|---|---|---|---|
| **Entry filter** | none (any textbook pattern) | same | **DI_ok ∧ hard34 ∧ VWAP** |
| **Which call** | first event that **will win** (peek) | same | first that passes gates (blind) |
| **Exit** | EMA34 trail · **T1=12** | EMA34 trail · **T1=15** | EMA34 trail · **T1=12** |
| **Live usable?** | **No** | **No** | Yes (research desk) |

## Exit parameters (same for Oracle & HELD)

| Parameter | Value | Meaning |
|---|---|---|
| Trail MA | **EMA34** | exit when **close** flips against side vs EMA34 |
| Target T1 | **12** or **15** pts | BUY: high ≥ entry+T1 · SELL: low ≤ entry−T1 |
| Win rule | T1 **before** MA flip | else loss (`ma_sl`) even if green |
| Max hold | ~120 bars (~2h) | else expire = loss |
| Side | from candle pattern | bull patterns → BUY, bear → SELL |

## What you need to “run” Oracle (research only)

1. NIFTY **1m OHLC** for the day (+ ~100 bars warm-up for EMA34)
2. Textbook candle detector (same catalog as scalp research)
3. Simulate every candidate forward with EMA34 trail + T1
4. Pick **first winner** chronologically → that is the oracle call

**No** DI / VWAP / hard34 parameters — those are only for **HELD**.

## Why 100% every day?

Because oracle **searches** until it finds a path that already worked. It proves the **exit geometry** can pay T1 that day — not that you know which entry live.

## Chart (last 5 days)

- PNG: `prod_live/reports/1y/charts/NIFTY_1M_ORACLE_T12_LAST5D.png`
- Gold ★ = ORACLE T12 entry → exit
- Blue ▲/▼ = HELD T12 when different from oracle

| Day | Oracle T12 | HELD T12 | Same? |
|---|---|---|---|
| 2026-11-09 | 09:21 SELL bear_run3 | 09:24 SELL evening_star (W) | no |
| 2026-11-11 | 09:22 SELL belt_bear | 09:28 BUY bull_run2 (W) | no |
| 2026-11-12 | 09:24 BUY hammer | 09:24 BUY hammer (W) | YES |
| 2026-11-13 | 09:20 SELL three_outside_dn | 09:20 SELL three_outside_dn (W) | YES |
| 2026-11-16 | 09:21 BUY bull_run2 | 09:21 BUY bull_run2 (W) | YES |

### Oracle T15 first-win (same days)

| Day | Oracle T15 |
|---|---|
| 2026-11-09 | 09:21 SELL bear_run3
| 2026-11-11 | 09:22 SELL belt_bear
| 2026-11-12 | 09:24 BUY hammer
| 2026-11-13 | 09:20 SELL three_outside_dn
| 2026-11-16 | 09:21 BUY bull_run2