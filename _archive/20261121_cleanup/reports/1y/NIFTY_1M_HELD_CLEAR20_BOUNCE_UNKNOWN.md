# HELD + clear_20 + bounce — UNKNOWN test

Gate locked after last-1m interest. **Unknown** = months before last 1m (not used to pick the gate).

- Entry: DI+hard34+VWAP · 09:30–14:30 · **room_fav ≥ 20** · **bounce** (near fav S/R) · 1/day
- Exit: EMA34 trail · T1=12
- Data end `2026-11-16` · seen last_1m from `2026-10-17` · unknown through `2026-10-16`

| Window | n | Hit% | Cover | W/L | Avg pts | Total |
|---|---:|---:|---:|---:|---:|---:|
| **SEEN last_1m (reference)** | 19 | **84.21%** | 95.0% | 16/3 | 4.32 | 82.0 |
| ↳ plain HELD (same window) | 19 | 78.95% | 95.0% | 15/4 | 1.19 | 22.55 |
| **UNKNOWN prior_1m** | 20 | **65.0%** | 95.24% | 13/7 | -2.55 | -51.05 |
| ↳ plain HELD (same window) | 21 | 85.71% | 100.0% | 18/3 | 7.76 | 163.0 |
| **UNKNOWN prior_3m** | 63 | **53.97%** | 98.44% | 34/29 | -2.64 | -166.25 |
| ↳ plain HELD (same window) | 64 | 73.44% | 100.0% | 47/17 | 4.01 | 256.55 |
| **UNKNOWN rest_of_1y (excl last_1m)** | 223 | **66.82%** | 97.81% | 149/74 | -0.13 | -28.5 |
| ↳ plain HELD (same window) | 228 | 68.86% | 100.0% | 157/71 | -1.35 | -308.55 |

## UNKNOWN prior_1m ledger (`2026-09-17` → `2026-10-16`)

| Day | Entry | Side | Pattern | room_fav | S | R | Exit | Reason | Pts |
|---|---|---|---|---:|---:|---:|---|---|---:|
| 2026-09-17 | 10:10 | BUY | bull_kicker | 999.0 | 23314.65 | None | 10:22 | `ma_sl` | -22.1 |
| 2026-09-18 | 14:05 | BUY | marubozu_bull | 20.65 | 23342.55 | 23363.55 | 14:09 | `t1` | +12.0 |
| 2026-09-21 | 13:33 | BUY | bull_run3 | 999.0 | 23434.05 | None | 13:56 | `t1` | +12.0 |
| 2026-09-22 | 10:09 | BUY | bull_run3 | 21.95 | 23466.8 | 23489.0 | 10:16 | `ma_sl` | -10.9 |
| 2026-09-23 | 10:45 | BUY | bull_run2 | 72.15 | 23414.55 | 23489.0 | 11:06 | `t1` | +12.0 |
| 2026-09-24 | 10:25 | SELL | belt_bear | 999.0 | None | 23205.25 | 10:32 | `ma_sl` | -19.5 |
| 2026-09-28 | 10:09 | SELL | belt_bear | 999.0 | None | 22855.45 | 10:17 | `t1` | +12.0 |
| 2026-09-29 | 12:01 | BUY | bull_run3 | 25.35 | 22733.85 | 22762.2 | 12:06 | `t1` | +12.0 |
| 2026-09-30 | 10:14 | BUY | marubozu_bull | 999.0 | 22753.25 | None | 10:21 | `t1` | +12.0 |
| 2026-10-01 | 13:17 | SELL | bear_run3 | 47.0 | 22301.3 | 22354.45 | 13:18 | `t1` | +12.0 |
| 2026-10-05 | 09:48 | BUY | bull_run3 | 999.0 | 22610.6 | None | 09:59 | `ma_sl` | -46.1 |
| 2026-10-06 | 09:53 | BUY | bull_run2 | 999.0 | 22629.95 | None | 09:55 | `t1` | +12.0 |
| 2026-10-07 | 12:04 | BUY | belt_bull | 61.9 | 22710.8 | 22776.1 | 12:11 | `ma_sl` | -34.0 |
| 2026-10-08 | 09:43 | SELL | bear_engulf | 999.0 | None | 22475.75 | 09:45 | `t1` | +12.0 |
| 2026-10-09 | 09:34 | BUY | bull_run2 | 205.25 | 22388.7 | 22599.05 | 09:38 | `t1` | +12.0 |
| 2026-10-12 | 09:51 | SELL | three_outside_dn | 208.6 | 22294.75 | 22508.3 | 09:52 | `t1` | +12.0 |
| 2026-10-13 | 09:58 | BUY | bull_run2 | 78.05 | 22571.5 | 22651.1 | 10:19 | `ma_sl` | -28.2 |
| 2026-10-14 | 09:44 | BUY | bull_run3 | 20.15 | 22728.1 | 22752.3 | 09:46 | `t1` | +12.0 |
| 2026-10-15 | 09:33 | BUY | bull_engulf | 999.0 | 22757.95 | None | 09:37 | `t1` | +12.0 |
| 2026-10-16 | 09:36 | SELL | belt_bear | 281.0 | 22637.4 | 22926.05 | 09:40 | `ma_sl` | -46.2 |

## Last 5 days chart

- PNG: `prod_live/reports/1y/charts/NIFTY_1M_HELD_CLEAR20_BOUNCE_UNKNOWN5D.png`
- HTML: `prod_live/reports/1y/charts/NIFTY_1M_HELD_CLEAR20_BOUNCE_UNKNOWN5D.html`
- Calls **5** · hit **100.0%** · avg 12.0

| Day | Entry | Side | Pattern | room | Result | Pts |
|---|---|---|---|---:|---|---:|
| 2026-11-09 | 09:40 | SELL | bear_run2 | 999.0 | WIN | +12.0 |
| 2026-11-11 | 09:41 | BUY | bull_run2 | 999.0 | WIN | +12.0 |
| 2026-11-12 | 11:28 | SELL | three_crows | 24.5 | WIN | +12.0 |
| 2026-11-13 | 11:58 | SELL | bear_engulf | 999.0 | WIN | +12.0 |
| 2026-11-16 | 12:09 | BUY | bull_run3 | 33.4 | WIN | +12.0 |

## Verdict

If UNKNOWN prior windows keep hit/avg near SEEN last_1m → gate is usable; if they collapse → last_1m was lucky, do not lock yet.
