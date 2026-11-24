# LIVE today `2026-11-17` — MACD indication hunt → 100%

Data through `2026-11-17 10:29:00+05:30` · bars today **75** · events **47**
Exit check: EMA34 trail · T1=**12** (completed = t1 or ma_sl)

## A) Filters on TODAY (completed paths only)

| Filter | 1st call | Completed n@hit | all_win | Pending |
|---|---|---:|:---:|---:|
| `OLD_held DI+hard34+VWAP` | 09:39 BUY bull_run3 | 13@100.0% | True | 3 |
| `MACD_live (hist with side)` | 09:29 SELL belt_bear | 21@28.57% | False | 4 |
| `MACD+DI` | 09:33 SELL marubozu_bear | 10@60.0% | False | 3 |
| `MACD+DI+VWAP` | 09:33 SELL marubozu_bear | 9@66.67% | False | 3 |
| `MACD+DI+VWAP+hard34` | 09:44 BUY bull_run2 | 6@100.0% | True | 3 |
| `MACD+DI+hard34+BBmid` | 09:44 BUY bull_run2 | 6@100.0% | True | 3 |
| `MACD+hard34+mom+close` | 09:44 BUY bull_run2 | 5@100.0% | True | 2 |
| `MACD+DI+VWAP+hard34+close+!fail` | 09:45 BUY bull_run3 | 2@100.0% | True | 1 |
| `MACD cross-up only BUY hist>0 & hard34` | 09:44 BUY bull_run2 | 6@100.0% | True | 3 |
| `MACD hist accelerating` | 09:33 SELL marubozu_bear | 9@55.56% | False | 3 |

## B) Live timeline — every event with MACD / gates / path

| HM | Side | Pat | px | MACD hist | macd_live | DI | hard34 | VWAP | OLD | path |
|---|---|---|---:|---:|:---:|:---:|:---:|:---:|:---:|---|
| 09:20 | SELL | bear_run3 | 25341.7 | 12.36 | 0 | 0 | 0 | 0 | 0 | Y/t1 |
| 09:21 | SELL | bear_run3 | 25325.1 | 9.443 | 0 | 0 | 0 | 1 | 0 | N/ma_sl |
| 09:22 | SELL | bear_run3 | 25326.15 | 6.975 | 0 | 0 | 0 | 1 | 0 | N/ma_sl |
| 09:27 | BUY | bull_run2 | 25330.4 | -0.915 | 0 | 1 | 1 | 0 | 0 | Y/t1 |
| 09:29 | SELL | belt_bear | 25321.85 | -2.689 | 1 | 0 | 0 | 1 | 0 | N/ma_sl |
| 09:31 | BUY | bull_run2 | 25325.45 | -3.672 | 0 | 0 | 1 | 0 | 0 | Y/t1 |
| 09:33 | SELL | marubozu_bear | 25305.65 | -5.351 | 1 | 1 | 0 | 1 | 0 | N/ma_sl |
| 09:34 | SELL | bear_run3 | 25303.95 | -6.274 | 1 | 1 | 0 | 1 | 0 | N/ma_sl |
| 09:36 | SELL | bear_engulf | 25297.45 | -6.923 | 1 | 1 | 0 | 1 | 0 | N/ma_sl |
| 09:38 | BUY | bull_run2 | 25317.85 | -5.538 | 0 | 0 | 1 | 0 | 0 | Y/t1 |
| 09:39 | BUY | bull_run3 | 25328.35 | -3.958 | 0 | 1 | 1 | 1 | 1 | Y/t1 |
| 09:40 | BUY | bull_run3 | 25338.35 | -2.24 | 0 | 1 | 1 | 1 | 1 | Y/t1 |
| 09:42 | SELL | bear_run2 | 25328.05 | -1.252 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 09:43 | BUY | marubozu_bull | 25340.7 | -0.479 | 0 | 1 | 1 | 1 | 1 | Y/t1 |
| 09:44 | BUY | bull_run2 | 25347.35 | 0.348 | 1 | 1 | 1 | 1 | 1 | Y/t1 |
| 09:45 | BUY | bull_run3 | 25360.2 | 1.56 | 1 | 1 | 1 | 1 | 1 | Y/t1 |
| 09:46 | SELL | bear_engulf | 25348.85 | 1.402 | 0 | 0 | 0 | 0 | 0 | N/ma_sl |
| 09:48 | BUY | bull_run2 | 25363.7 | 1.968 | 1 | 1 | 1 | 1 | 1 | Y/t1 |
| 09:49 | SELL | dark_cloud | 25359.8 | 1.742 | 0 | 0 | 0 | 0 | 0 | N/ma_sl |
| 09:51 | BUY | bull_run2 | 25372.75 | 2.092 | 1 | 1 | 1 | 1 | 1 | Y/t1 |
| 09:52 | SELL | bear_engulf | 25361.6 | 1.238 | 0 | 0 | 0 | 0 | 0 | N/ma_sl |
| 09:54 | BUY | bull_kicker | 25381.0 | 1.129 | 1 | 1 | 1 | 1 | 1 | Y/t1 |
| 09:57 | SELL | bear_engulf | 25371.3 | 0.151 | 0 | 0 | 0 | 0 | 0 | N/ma_sl |
| 09:58 | SELL | three_outside_dn | 25367.1 | -0.74 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 09:59 | BUY | inv_hammer | 25372.45 | -1.064 | 0 | 1 | 1 | 1 | 1 | Y/t1 |
| 10:00 | SELL | bear_engulf | 25369.65 | -1.532 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:01 | SELL | three_outside_dn | 25367.1 | -2.048 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:02 | SELL | bear_run3 | 25365.95 | -2.472 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:03 | SELL | bear_run3 | 25363.25 | -2.909 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:05 | BUY | bull_run2 | 25373.7 | -2.498 | 0 | 1 | 1 | 1 | 1 | Y/t1 |
| 10:06 | BUY | bull_run3 | 25378.8 | -1.841 | 0 | 1 | 1 | 1 | 1 | Y/t1 |
| 10:07 | SELL | bear_engulf | 25373.0 | -1.809 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:09 | SELL | bear_engulf | 25360.65 | -2.518 | 1 | 1 | 0 | 0 | 0 | N/ma_sl |
| 10:11 | BUY | bull_run2 | 25367.95 | -2.694 | 0 | 0 | 1 | 1 | 0 | Y/t1 |
| 10:12 | BUY | bull_run3 | 25372.1 | -2.249 | 0 | 0 | 1 | 1 | 0 | Y/t1 |
| 10:13 | BUY | bull_run3 | 25378.5 | -1.518 | 0 | 1 | 1 | 1 | 1 | Y/t1 |
| 10:15 | SELL | bear_run2 | 25379.95 | -0.653 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:16 | SELL | bear_run3 | 25381.8 | -0.347 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:17 | BUY | bull_kicker | 25396.0 | 0.704 | 1 | 1 | 1 | 1 | 1 | Y/t1 |
| 10:18 | BUY | bull_run2 | 25409.15 | 2.097 | 1 | 1 | 1 | 1 | 1 | …/exp |
| 10:19 | SELL | belt_bear | 25398.75 | 2.123 | 0 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:21 | BUY | bull_run2 | 25411.15 | 2.5 | 1 | 1 | 1 | 1 | 1 | …/exp |
| 10:22 | BUY | bull_run3 | 25415.0 | 2.817 | 1 | 1 | 1 | 1 | 1 | …/exp |
| 10:23 | SELL | bear_engulf | 25409.1 | 2.398 | 0 | 0 | 0 | 0 | 0 | Y/t1 |
| 10:24 | SELL | three_outside_dn | 25397.1 | 1.143 | 0 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:26 | SELL | bear_engulf | 25393.9 | -0.596 | 1 | 0 | 0 | 0 | 0 | N/ma_sl |
| 10:29 | SELL | bear_run2 | 25404.5 | -0.782 | 1 | 0 | 0 | 0 | 0 | …/exp |

## C) Same MACD filters on last-3m history (`2026-08-18`→ before today) — 1/day first

| Filter | n@hit cover | all_win |
|---|---|:---:|
| `OLD_held DI+hard34+VWAP` | 62@83.87% 100.0% | False |
| `MACD_live (hist with side)` | 62@72.58% 100.0% | False |
| `MACD+DI` | 62@74.19% 100.0% | False |
| `MACD+DI+VWAP` | 62@69.35% 100.0% | False |
| `MACD+DI+VWAP+hard34` | 61@80.33% 98.4% | False |
| `MACD+DI+hard34+BBmid` | 61@83.61% 98.4% | False |
| `MACD+hard34+mom+close` | 61@83.61% 98.4% | False |
| `MACD+DI+VWAP+hard34+close+!fail` | 61@80.33% 98.4% | False |
| `MACD cross-up only BUY hist>0 & hard34` | 55@81.82% 88.7% | False |
| `MACD hist accelerating` | 62@74.19% 100.0% | False |

## Live indication (what to use now)

On **completed** paths today, **`OLD_held DI+hard34+VWAP`** is **100%** (13 done).
- First live fire: **09:39** BUY bull_run3 px=25328.35 MACD_hist=-3.958
- Still verify on history (section C) — today-only 100% can overfit.


## Today call comparison

- OLD held first: **09:39 BUY bull_run3** path=t1
- MACD+DI+VWAP+hard34 first: **09:44 BUY bull_run2** path=t1 hist=0.348

### Exact MACD live rule under test
1. Candle signal fires
2. **MACD histogram with trade** (BUY hist>0 / SELL hist<0) = `macd_live`
3. Plus DI align + VWAP with + EMA34 hard (preferred stack)
4. Hold EMA34 trail · T1=12
