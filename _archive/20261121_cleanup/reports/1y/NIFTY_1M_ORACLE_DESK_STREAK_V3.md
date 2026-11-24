# NIFTY 1m — Oracle×Desk×streak **v3** (accuracy improve)

> Goal: lift T15 entry accuracy above prior ~58–63% ceiling.
> Modes: **hit4/5/6** · **confirm+1** · **pullback-resume**.
> Filters: Desk core · held · HTF15 · AD · !chase · !extreme · session · ATR.
> Metric = EMA34 trail **T15** (Oracle exit). 1/day + walk-forward.

Window **2026-05-26 → 2026-11-16** (120d). OOS **2026-08-20**. Candidates **9300**.

## 0) Mode counts

| Mode | n |
|---|---:|
| `conf4` | 1348 |
| `conf5` | 768 |
| `conf6` | 424 |
| `hit4` | 2469 |
| `hit5` | 1348 |
| `hit6` | 768 |
| `pullback` | 2175 |

## 1) Lift on hit6+desk≥3 (winners vs losers)

| Mark | % Winners | % Losers | Lift pp |
|---|---:|---:|---:|
| `atr_hi` | 26.5 | 14.3 | 12.2 |
| `held` | 80.8 | 70.1 | 10.7 |
| `am` | 45.6 | 35.7 | 9.9 |
| `desk_ge4` | 80.8 | 71.1 | 9.7 |
| `big_body` | 36.9 | 28.6 | 8.4 |
| `htf_with` | 71.4 | 64.0 | 7.5 |
| `vwap_with` | 87.1 | 80.5 | 6.6 |
| `disp08` | 32.4 | 27.6 | 4.8 |
| `ema50_with` | 99.3 | 97.7 | 1.6 |
| `bb_mid_with` | 100.0 | 99.0 | 1.0 |
| `ctrl` | 70.4 | 69.8 | 0.6 |
| `ema_with` | 94.4 | 93.8 | 0.6 |
| `desk_ge3` | 100.0 | 100.0 | 0.0 |
| `prime` | 76.0 | 76.3 | -0.3 |
| `ad` | 98.3 | 99.0 | -0.8 |
| `close_strong` | 45.6 | 47.7 | -2.1 |
| `has_oracle` | 93.0 | 95.1 | -2.1 |
| `skip_open` | 93.4 | 96.8 | -3.4 |
| `not_extreme` | 64.8 | 72.1 | -7.3 |
| `near34` | 8.4 | 18.2 | -9.8 |

## 2) Curated + hunt gates (1/day · T15%)

| Gate | Verdict | n | T15% | Train | OOS | all n/prec | avg pts |
|---|---|---:|---:|---:|---:|---|---:|
| `hit6+atr_hi+desk≥3+held+htf` | **HIGH_75** | 38 | **81.58** | 87.5 | 77.27 | 68/73.53 | 7.27 |
| `HUNT:hit6|held+htf_with+atr_hi` | **HIGH_75** | 38 | **81.58** | 87.5 | 77.27 | 68/73.53 | 7.27 |
| `HUNT:hit6|desk_ge3+held+htf_with+atr_hi` | **HIGH_75** | 38 | **81.58** | 87.5 | 77.27 | 68/73.53 | 7.27 |
| `HUNT:hit6|held+htf_with+skip_open+atr_hi` | **HIGH_75** | 32 | **81.25** | 90.91 | 76.19 | 57/71.93 | 6.99 |
| `HUNT:hit6|desk_ge3+held+htf_with+skip_open+atr_hi` | **HIGH_75** | 32 | **81.25** | 90.91 | 76.19 | 57/71.93 | 6.99 |
| `HUNT:hit6|held+htf_with+ad+atr_hi` | **HIGH_75** | 37 | **81.08** | 87.5 | 76.19 | 67/73.13 | 7.07 |
| `HUNT:hit6|desk_ge3+held+htf_with+ad+atr_hi` | **HIGH_75** | 37 | **81.08** | 87.5 | 76.19 | 67/73.13 | 7.07 |
| `HUNT:hit6|held+htf_with+ad+skip_open+atr_hi` | **HIGH_75** | 31 | **80.65** | 90.91 | 75.0 | 56/71.43 | 6.73 |
| `HUNT:conf6|held+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 | 38/76.32 | 7.18 |
| `HUNT:conf6|desk_ge3+held+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 | 38/76.32 | 7.18 |
| `HUNT:conf6|held+ad+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 | 38/76.32 | 7.18 |
| `HUNT:conf6|held+skip_open+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 | 38/76.32 | 7.18 |
| `HUNT:conf6|desk_ge3+held+ad+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 | 38/76.32 | 7.18 |
| `HUNT:conf6|desk_ge3+held+skip_open+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 | 38/76.32 | 7.18 |
| `HUNT:conf6|held+ad+skip_open+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 | 38/76.32 | 7.18 |
| `HUNT:hit6|held+htf_with+atr_hi+prime` | **HIGH_75** | 28 | **78.57** | 88.89 | 73.68 | 48/72.92 | 5.84 |
| `HUNT:hit6|desk_ge3+held+htf_with+atr_hi+prime` | **HIGH_75** | 28 | **78.57** | 88.89 | 73.68 | 48/72.92 | 5.84 |
| `HUNT:hit6|held+htf_with+ad+atr_hi+prime` | **HIGH_75** | 28 | **78.57** | 88.89 | 73.68 | 48/72.92 | 5.84 |
| `HUNT:hit6|held+htf_with+skip_open+atr_hi+prime` | **HIGH_75** | 28 | **78.57** | 88.89 | 73.68 | 48/72.92 | 5.84 |
| `HUNT:hit6|held+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 | 36/69.44 | 6.43 |
| `HUNT:hit6|desk_ge3+held+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 | 36/69.44 | 6.43 |
| `HUNT:hit6|held+ad+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 | 36/69.44 | 6.43 |
| `HUNT:hit6|held+skip_open+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 | 36/69.44 | 6.43 |
| `HUNT:hit6|held+ctrl+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 | 36/69.44 | 6.43 |
| `HUNT:conf6|held+ctrl+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 | 32/71.88 | 6.5 |
| `HUNT:conf6|desk_ge3+held+ctrl+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 | 32/71.88 | 6.5 |
| `HUNT:conf6|held+ad+ctrl+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 | 32/71.88 | 6.5 |
| `HUNT:conf6|held+skip_open+ctrl+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 | 32/71.88 | 6.5 |
| `HUNT:hit6|held+skip_open+atr_hi` | **HIGH_75** | 41 | **78.05** | 80.0 | 76.92 | 84/67.86 | 6.48 |
| `HUNT:hit6|desk_ge3+held+skip_open+atr_hi` | **HIGH_75** | 41 | **78.05** | 80.0 | 76.92 | 84/67.86 | 6.48 |
| `HUNT:hit6|held+ad+skip_open+atr_hi` | **HIGH_75** | 40 | **77.5** | 80.0 | 76.0 | 82/67.07 | 6.27 |
| `HUNT:hit6|desk_ge3+held+ad+skip_open+atr_hi` | **HIGH_75** | 40 | **77.5** | 80.0 | 76.0 | 82/67.07 | 6.27 |
| `HUNT:hit6|held+skip_open+close_strong+atr_hi` | **HIGH_75** | 26 | **76.92** | 77.78 | 76.47 | 40/67.5 | 5.34 |
| `HUNT:hit6|desk_ge3+held+skip_open+close_strong+atr_hi` | **HIGH_75** | 26 | **76.92** | 77.78 | 76.47 | 40/67.5 | 5.34 |
| `HUNT:hit6|held+ad+skip_open+close_strong+atr_hi` | **HIGH_75** | 26 | **76.92** | 77.78 | 76.47 | 40/67.5 | 5.34 |
| `HUNT:hit6|held+skip_open+ctrl+close_strong+atr_hi` | **HIGH_75** | 26 | **76.92** | 77.78 | 76.47 | 40/67.5 | 5.34 |
| `HUNT:conf6|held+skip_open+ctrl+atr_hi` | **OK_70** | 26 | **76.92** | 66.67 | 82.35 | 38/71.05 | 4.52 |
| `HUNT:conf6|desk_ge3+held+skip_open+ctrl+atr_hi` | **OK_70** | 26 | **76.92** | 66.67 | 82.35 | 38/71.05 | 4.52 |
| `HUNT:conf6|held+ad+skip_open+ctrl+atr_hi` | **OK_70** | 26 | **76.92** | 66.67 | 82.35 | 38/71.05 | 4.52 |
| `HUNT:hit6|desk_ge3+htf_with+atr_hi` | **HIGH_75** | 43 | **76.74** | 82.35 | 73.08 | 77/71.43 | 5.79 |
| `HUNT:conf6|held+skip_open+atr_hi` | **HIGH_75** | 30 | **76.67** | 72.73 | 78.95 | 47/74.47 | 4.35 |
| `HUNT:conf6|desk_ge3+held+skip_open+atr_hi` | **HIGH_75** | 30 | **76.67** | 72.73 | 78.95 | 47/74.47 | 4.35 |
| `HUNT:conf6|held+ad+skip_open+atr_hi` | **HIGH_75** | 30 | **76.67** | 72.73 | 78.95 | 47/74.47 | 4.35 |
| `HUNT:conf6|desk_ge3+held+ad+skip_open+atr_hi` | **HIGH_75** | 30 | **76.67** | 72.73 | 78.95 | 47/74.47 | 4.35 |
| `HUNT:any_conf|held+htf_with+close_strong+atr_hi` | **HIGH_75** | 47 | **76.6** | 71.43 | 80.77 | 120/69.17 | 4.56 |
| `HUNT:any_conf|desk_ge3+held+htf_with+close_strong+atr_hi` | **HIGH_75** | 47 | **76.6** | 71.43 | 80.77 | 120/69.17 | 4.56 |
| `HUNT:any_conf|held+htf_with+ad+close_strong+atr_hi` | **HIGH_75** | 47 | **76.6** | 71.43 | 80.77 | 120/69.17 | 4.56 |
| `HUNT:any_conf|held+htf_with+ctrl+close_strong+atr_hi` | **HIGH_75** | 47 | **76.6** | 71.43 | 80.77 | 120/69.17 | 4.56 |
| `HUNT:conf6|held+htf_with+atr_hi+prime` | **THIN** | 17 | **76.47** | 66.67 | 81.82 | 23/78.26 | 5.7 |
| `HUNT:conf6|held+close_strong+atr_hi+prime` | **THIN** | 17 | **76.47** | 83.33 | 72.73 | 21/76.19 | 4.6 |
| `HUNT:conf6|desk_ge3+held+htf_with+atr_hi+prime` | **THIN** | 17 | **76.47** | 66.67 | 81.82 | 23/78.26 | 5.7 |
| `HUNT:conf6|desk_ge3+held+close_strong+atr_hi+prime` | **THIN** | 17 | **76.47** | 83.33 | 72.73 | 21/76.19 | 4.6 |
| `HUNT:conf6|held+htf_with+ad+atr_hi+prime` | **THIN** | 17 | **76.47** | 66.67 | 81.82 | 23/78.26 | 5.7 |
| `HUNT:conf6|held+htf_with+skip_open+atr_hi+prime` | **THIN** | 17 | **76.47** | 66.67 | 81.82 | 23/78.26 | 5.7 |
| `HUNT:conf6|held+ad+close_strong+atr_hi+prime` | **THIN** | 17 | **76.47** | 83.33 | 72.73 | 21/76.19 | 4.6 |
| `HUNT:conf6|held+skip_open+close_strong+atr_hi+prime` | **THIN** | 17 | **76.47** | 83.33 | 72.73 | 21/76.19 | 4.6 |
| `HUNT:conf6|held+ctrl+close_strong+atr_hi+prime` | **THIN** | 17 | **76.47** | 83.33 | 72.73 | 21/76.19 | 4.6 |
| `HUNT:hit6|desk_ge3+htf_with+ad+atr_hi` | **HIGH_75** | 42 | **76.19** | 82.35 | 72.0 | 76/71.05 | 5.57 |
| `HUNT:conf6|held+htf_with+skip_open+atr_hi` | **OK_65** | 21 | **76.19** | 62.5 | 84.62 | 29/79.31 | 3.8 |
| `HUNT:conf6|desk_ge3+held+htf_with+skip_open+atr_hi` | **OK_65** | 21 | **76.19** | 62.5 | 84.62 | 29/79.31 | 3.8 |

## 3) Hunt ≥70% T15 (1/day, n≥15, OOS≥65)

| Pool | Combo | Verdict | n | T15% | Train | OOS |
|---|---|---|---:|---:|---:|---:|
| `hit6` | `held+htf_with+atr_hi` | **HIGH_75** | 38 | **81.58** | 87.5 | 77.27 |
| `hit6` | `desk_ge3+held+htf_with+atr_hi` | **HIGH_75** | 38 | **81.58** | 87.5 | 77.27 |
| `hit6` | `held+htf_with+skip_open+atr_hi` | **HIGH_75** | 32 | **81.25** | 90.91 | 76.19 |
| `hit6` | `desk_ge3+held+htf_with+skip_open+atr_hi` | **HIGH_75** | 32 | **81.25** | 90.91 | 76.19 |
| `hit6` | `held+htf_with+ad+atr_hi` | **HIGH_75** | 37 | **81.08** | 87.5 | 76.19 |
| `hit6` | `desk_ge3+held+htf_with+ad+atr_hi` | **HIGH_75** | 37 | **81.08** | 87.5 | 76.19 |
| `hit6` | `held+htf_with+ad+skip_open+atr_hi` | **HIGH_75** | 31 | **80.65** | 90.91 | 75.0 |
| `conf6` | `held+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 |
| `conf6` | `desk_ge3+held+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 |
| `conf6` | `held+ad+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 |
| `conf6` | `held+skip_open+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 |
| `conf6` | `desk_ge3+held+ad+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 |
| `conf6` | `desk_ge3+held+skip_open+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 |
| `conf6` | `held+ad+skip_open+atr_hi+prime` | **HIGH_75** | 25 | **80.0** | 77.78 | 81.25 |
| `hit6` | `held+htf_with+atr_hi+prime` | **HIGH_75** | 28 | **78.57** | 88.89 | 73.68 |
| `hit6` | `desk_ge3+held+htf_with+atr_hi+prime` | **HIGH_75** | 28 | **78.57** | 88.89 | 73.68 |
| `hit6` | `held+htf_with+ad+atr_hi+prime` | **HIGH_75** | 28 | **78.57** | 88.89 | 73.68 |
| `hit6` | `held+htf_with+skip_open+atr_hi+prime` | **HIGH_75** | 28 | **78.57** | 88.89 | 73.68 |
| `hit6` | `held+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 |
| `hit6` | `desk_ge3+held+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 |
| `hit6` | `held+ad+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 |
| `hit6` | `held+skip_open+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 |
| `hit6` | `held+ctrl+close_strong+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 71.43 | 81.25 |
| `conf6` | `held+ctrl+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 |
| `conf6` | `desk_ge3+held+ctrl+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 |
| `conf6` | `held+ad+ctrl+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 |
| `conf6` | `held+skip_open+ctrl+atr_hi+prime` | **HIGH_75** | 23 | **78.26** | 75.0 | 80.0 |
| `hit6` | `held+skip_open+atr_hi` | **HIGH_75** | 41 | **78.05** | 80.0 | 76.92 |
| `hit6` | `desk_ge3+held+skip_open+atr_hi` | **HIGH_75** | 41 | **78.05** | 80.0 | 76.92 |
| `hit6` | `held+ad+skip_open+atr_hi` | **HIGH_75** | 40 | **77.5** | 80.0 | 76.0 |

## 4) Best accurate entry (this pass)

**HIGH (≥75%):** `hit6+atr_hi+desk≥3+held+htf` · **HIGH_75**
- 1/day T15 **81.58%** · TRAIN **87.5%** · OOS **77.27%** · n=38
- avg pts **7.27**

### Recipe

```
1) Wait 4–6 same-color 1m bars (direction)
2) Entry mode = hit / confirm+1 / pullback-resume (see gate name)
3) Desk core: VWAP + EMA stack + EMA50 / BBmid (≥3)
4) Quality: held (DI+EMA34+VWAP) · HTF15 with · not chase EMA34
5) Optional: skip open <09:45 · not session extreme · AD with
6) Exit: EMA34 trail · T15 (Oracle geometry)
```

### Samples

| Day | HM | Side | Entry | mode | streak | desk | T15 |
|---|---|---|---:|---|---:|---:|---|
| 2026-06-02 | 13:34 | **BUY** | **23529.85** | hit6 | 6 | 4 | True |
| 2026-06-03 | 12:31 | **BUY** | **23275.1** | hit6 | 6 | 4 | True |
| 2026-06-04 | 09:49 | **BUY** | **23388.35** | hit6 | 6 | 4 | True |
| 2026-06-05 | 10:39 | **SELL** | **23364.15** | hit6 | 6 | 4 | True |
| 2026-06-11 | 09:58 | **SELL** | **23114.7** | hit6 | 6 | 4 | False |
| 2026-06-12 | 13:31 | **BUY** | **23404.9** | hit6 | 6 | 4 | True |
| 2026-06-17 | 09:30 | **BUY** | **24024.5** | hit6 | 6 | 4 | True |
| 2026-06-18 | 09:42 | **BUY** | **24118.25** | hit6 | 6 | 4 | True |
| 2026-06-23 | 11:57 | **SELL** | **23989.2** | hit6 | 6 | 4 | True |
| 2026-06-29 | 09:33 | **SELL** | **24035.15** | hit6 | 6 | 4 | True |

## 5) vs prior

- v1 (oracle event + streak present): best ~**63%** T15
- v2 (enter at streak hit): best ~**59%** T15
- v3 (this): best **81.58%** · verdict **HIGH_75**

## 6) Live takeaway

- If ≥75% OOS-stable: wire that gate into Oracle T15 notify.
- If only ~65–70%: still better than raw Oracle; not “mostly accurate”.
- Target research only after entry gate holds walk-forward.

_Generated in 51.5s._
