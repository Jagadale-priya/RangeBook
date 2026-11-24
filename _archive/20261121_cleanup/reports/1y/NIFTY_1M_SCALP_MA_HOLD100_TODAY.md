# HELD logic — **today `2026-11-17`**

Gate: `DI_ok` + `EMA34 hard` + `VWAP_with` · Hold: EMA34 trail · **T1=12** · 1/day first
Data: `2026-11-02 09:15:00+05:30` → `2026-11-17 10:17:00+05:30` · today bars **63** · events **39** · gated **13**

## Call (first gated today)

| Field | Value |
|---|---|
| **Time** | **09:39** |
| **Side** | **BUY** |
| **Pattern** | **bull_run3** |
| Entry ~close | 25328.35 |
| Target T1 | **+12 pts** → 25340.35 |
| Stop | close flips vs EMA34 (trail) |
| Path so far | WIN path so far · MFE=71.5 |
| Gates | DI=1 hard34=1 VWAP=1 |

## All gated candidates today (in order)

| # | HM | Side | Pattern | DI | hard34 | VWAP | path | reason | MFE |
|---:|---|---|---|---:|---:|---:|---|---|---:|
| 1 ← CALL | 09:39 | BUY | bull_run3 | 1 | 1 | 1 | Y | t1 | 71.5 |
| 2 | 09:40 | BUY | bull_run3 | 1 | 1 | 1 | Y | t1 | 61.5 |
| 3 | 09:43 | BUY | marubozu_bull | 1 | 1 | 1 | Y | t1 | 59.1 |
| 4 | 09:44 | BUY | bull_run2 | 1 | 1 | 1 | Y | t1 | 52.5 |
| 5 | 09:45 | BUY | bull_run3 | 1 | 1 | 1 | Y | t1 | 39.6 |
| 6 | 09:48 | BUY | bull_run2 | 1 | 1 | 1 | Y | t1 | 36.1 |
| 7 | 09:51 | BUY | bull_run2 | 1 | 1 | 1 | Y | t1 | 27.0 |
| 8 | 09:54 | BUY | bull_kicker | 1 | 1 | 1 | Y | t1 | 18.8 |
| 9 | 09:59 | BUY | inv_hammer | 1 | 1 | 1 | Y | t1 | 27.3 |
| 10 | 10:05 | BUY | bull_run2 | 1 | 1 | 1 | Y | t1 | 26.1 |
| 11 | 10:06 | BUY | bull_run3 | 1 | 1 | 1 | Y | t1 | 21.0 |
| 12 | 10:13 | BUY | bull_run3 | 1 | 1 | 1 | Y | t1 | 21.3 |
| 13 | 10:17 | BUY | bull_kicker | 1 | 1 | 1 | N | exp | 0.0 |

## Early events gate check (first 20)

| HM | Side | Pattern | DI | hard34 | VWAP | pass? |
|---|---|---|---:|---:|---:|---|
| 09:20 | SELL | bear_run3 | 0 | 0 | 0 | no |
| 09:21 | SELL | bear_run3 | 0 | 0 | 1 | no |
| 09:22 | SELL | bear_run3 | 0 | 0 | 1 | no |
| 09:27 | BUY | bull_run2 | 1 | 1 | 0 | no |
| 09:29 | SELL | belt_bear | 0 | 0 | 1 | no |
| 09:31 | BUY | bull_run2 | 0 | 1 | 0 | no |
| 09:33 | SELL | marubozu_bear | 1 | 0 | 1 | no |
| 09:34 | SELL | bear_run3 | 1 | 0 | 1 | no |
| 09:36 | SELL | bear_engulf | 1 | 0 | 1 | no |
| 09:38 | BUY | bull_run2 | 0 | 1 | 0 | no |
| 09:39 | BUY | bull_run3 | 1 | 1 | 1 | YES |
| 09:40 | BUY | bull_run3 | 1 | 1 | 1 | YES |
| 09:42 | SELL | bear_run2 | 0 | 0 | 0 | no |
| 09:43 | BUY | marubozu_bull | 1 | 1 | 1 | YES |
| 09:44 | BUY | bull_run2 | 1 | 1 | 1 | YES |
| 09:45 | BUY | bull_run3 | 1 | 1 | 1 | YES |
| 09:46 | SELL | bear_engulf | 0 | 0 | 0 | no |
| 09:48 | BUY | bull_run2 | 1 | 1 | 1 | YES |
| 09:49 | SELL | dark_cloud | 0 | 0 | 0 | no |
| 09:51 | BUY | bull_run2 | 1 | 1 | 1 | YES |