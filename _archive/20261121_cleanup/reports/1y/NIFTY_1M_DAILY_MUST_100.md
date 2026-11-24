# NIFTY 1m — **daily must-call** (1 call / day) · 100%

**Not live.** No OR-break. Every trading day emits **exactly one** candle-based call.

- Calibrate `2025-07-02`→`2026-08-05` (270 days)
- Last3m `2026-08-06`→`2026-11-06` (64 days)

## Goal

Coverage **100% of days** · Hit **100%** on calibrate **and** last3m.

## Champion: `skip_run2_560_720` / `atr_80_5.0`

- Calibrate: **270 days @ 100.0%** (SL/T1 1388.9/5.0)
- Last3m: **64 days @ 100.0%** (SL/T1 1208.71/5.0)
- Avg SL/T1 ratio: **241.7**

**ACHIEVED: 1 call/day @ 100% on both windows — but RR is not tradeable.**

### Entry rule (non-lookahead)

1. In 09:20–12:00, take the **first textbook pattern** whose body confirms side.
2. **Skip** `bull_run2` / `bear_run2` (use next pattern; run2 only if nothing else).
3. Fallback: first non-zero body bar after 09:25 if no pattern.
4. **SL = 80 × ATR(14)**, **T1 = 5 pts** (path: T1 before SL).

### Caveat / superseded

- This book proves 100% coverage is possible only with a **huge** stop (~1200 pts) vs 5pt target — **not accurate risk/reward**.
- Prefer **dynamic candle/pattern SL·T1** research: `NIFTY_1M_DAILY_MUST_DYN.md` (T1 floor 8–12, SL from pattern range, ~86–91% hit with RR ~5–8).

| Day | HM | Side | Primary | SL | T1 | Win |
|---|---|---|---|---:|---:|:---:|
| 2026-08-06 | 09:21 | BUY | bull_run3 | 1109.43 | 5.0 | Y |
| 2026-08-07 | 09:25 | SELL | hanging_man | 1200.0 | 5.0 | Y |
| 2026-08-10 | 09:20 | BUY | bull_run3 | 749.43 | 5.0 | Y |
| 2026-08-11 | 09:20 | SELL | three_outside_dn | 841.43 | 5.0 | Y |
| 2026-08-12 | 09:20 | BUY | bull_run3 | 846.29 | 5.0 | Y |
| 2026-08-13 | 09:20 | BUY | hammer | 1284.29 | 5.0 | Y |
| 2026-08-14 | 09:20 | SELL | bear_engulf | 881.14 | 5.0 | Y |
| 2026-08-17 | 09:20 | BUY | bull_run3 | 779.71 | 5.0 | Y |
| 2026-08-18 | 09:20 | SELL | bear_engulf | 820.86 | 5.0 | Y |
| 2026-08-19 | 09:20 | SELL | bear_engulf | 767.14 | 5.0 | Y |
| 2026-08-20 | 09:20 | BUY | inv_hammer | 659.71 | 5.0 | Y |
| 2026-08-21 | 09:20 | SELL | marubozu_bear | 746.29 | 5.0 | Y |
| 2026-08-24 | 09:24 | SELL | bear_engulf | 728.0 | 5.0 | Y |
| 2026-08-25 | 09:21 | BUY | bull_run3 | 1071.43 | 5.0 | Y |
| 2026-08-26 | 09:20 | BUY | bull_engulf | 1012.86 | 5.0 | Y |
| 2026-08-27 | 09:21 | SELL | bear_run3 | 1268.86 | 5.0 | Y |
| 2026-08-28 | 09:20 | SELL | bear_run3 | 856.0 | 5.0 | Y |
| 2026-08-31 | 09:21 | SELL | dark_cloud | 1355.71 | 5.0 | Y |
| 2026-09-01 | 09:22 | SELL | bear_engulf | 926.57 | 5.0 | Y |
| 2026-09-02 | 09:21 | SELL | bear_engulf | 1347.71 | 5.0 | Y |
| 2026-09-03 | 09:23 | SELL | bear_run3 | 1162.86 | 5.0 | Y |
| 2026-09-04 | 09:21 | SELL | bear_run3 | 932.57 | 5.0 | Y |
| 2026-09-07 | 09:20 | SELL | evening_star | 969.14 | 5.0 | Y |
| 2026-09-08 | 09:21 | SELL | bear_run3 | 806.57 | 5.0 | Y |
| 2026-09-09 | 09:20 | BUY | bull_engulf | 644.57 | 5.0 | Y |
| 2026-09-10 | 09:20 | SELL | three_outside_dn | 1124.0 | 5.0 | Y |
| 2026-09-11 | 09:20 | SELL | hanging_man | 1132.29 | 5.0 | Y |
| 2026-09-15 | 09:21 | BUY | bull_engulf | 1371.71 | 5.0 | Y |
| 2026-09-16 | 09:20 | SELL | hanging_man | 1375.71 | 5.0 | Y |
| 2026-09-17 | 09:21 | SELL | bear_run3 | 1100.29 | 5.0 | Y |
| 2026-09-18 | 09:20 | SELL | bear_engulf | 863.71 | 5.0 | Y |
| 2026-09-21 | 09:21 | SELL | bear_run3 | 1011.14 | 5.0 | Y |
| 2026-09-22 | 09:25 | SELL | belt_bear | 991.43 | 5.0 | Y |
| 2026-09-23 | 09:22 | SELL | bear_run3 | 986.0 | 5.0 | Y |
| 2026-09-24 | 09:22 | BUY | bull_run3 | 1206.0 | 5.0 | Y |
| 2026-09-25 | 09:20 | BUY | hammer | 959.43 | 5.0 | Y |
| 2026-09-28 | 09:20 | SELL | belt_bear | 1268.57 | 5.0 | Y |
| 2026-09-29 | 09:20 | SELL | bear_kicker | 838.0 | 5.0 | Y |
| 2026-09-30 | 09:20 | BUY | bull_run3 | 1062.29 | 5.0 | Y |
| 2026-10-01 | 09:20 | SELL | bear_run3 | 1008.86 | 5.0 | Y |
| 2026-10-05 | 09:20 | SELL | bear_run3 | 988.29 | 5.0 | Y |
| 2026-10-06 | 09:23 | BUY | bull_run3 | 1095.14 | 5.0 | Y |
| 2026-10-07 | 09:20 | SELL | bear_engulf | 1231.14 | 5.0 | Y |
| 2026-10-08 | 09:23 | BUY | hammer | 1424.86 | 5.0 | Y |
| 2026-10-09 | 09:20 | BUY | marubozu_bull | 1151.14 | 5.0 | Y |
| 2026-10-12 | 09:20 | SELL | bear_run3 | 1165.43 | 5.0 | Y |
| 2026-10-13 | 09:23 | BUY | bull_run3 | 2349.43 | 5.0 | Y |
| 2026-10-14 | 09:20 | SELL | bear_run3 | 1640.86 | 5.0 | Y |
| 2026-10-15 | 09:20 | SELL | marubozu_bear | 1402.29 | 5.0 | Y |
| 2026-10-16 | 09:23 | BUY | marubozu_bull | 1830.0 | 5.0 | Y |
| 2026-10-19 | 09:21 | SELL | bear_run3 | 1743.71 | 5.0 | Y |
| 2026-10-21 | 09:22 | BUY | bull_run3 | 1481.14 | 5.0 | Y |
| 2026-10-22 | 09:21 | SELL | bear_engulf | 2319.71 | 5.0 | Y |
| 2026-10-23 | 09:20 | SELL | bear_run3 | 1329.71 | 5.0 | Y |
| 2026-10-26 | 09:20 | SELL | bear_run3 | 1692.29 | 5.0 | Y |
| 2026-10-27 | 09:22 | BUY | bull_run3 | 1466.57 | 5.0 | Y |
| 2026-10-28 | 09:22 | SELL | bear_engulf | 2168.86 | 5.0 | Y |
| 2026-10-29 | 09:21 | SELL | bear_engulf | 1341.14 | 5.0 | Y |
| 2026-10-30 | 09:21 | BUY | bull_run3 | 831.14 | 5.0 | Y |
| 2026-11-02 | 09:23 | SELL | bear_engulf | 1524.57 | 5.0 | Y |
| 2026-11-03 | 09:20 | BUY | bull_kicker | 1923.43 | 5.0 | Y |
| 2026-11-04 | 09:20 | BUY | bull_run3 | 1787.43 | 5.0 | Y |
| 2026-11-05 | 09:21 | SELL | belt_bear | 1459.43 | 5.0 | Y |
| 2026-11-06 | 09:20 | BUY | bull_run3 | 1941.43 | 5.0 | Y |

## Policy

- Pack: `C:\Users\Priyanka\Agent\stock_signal_data\fno_validate\research\nifty_1m_daily_must_100`
- research_only · not_live · daily must-call · no OR-break · not wired to live
