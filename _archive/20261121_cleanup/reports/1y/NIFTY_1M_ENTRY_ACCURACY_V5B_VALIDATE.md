# NIFTY 1m — Validate **HIGH_85** entry rule (v5b)

## Rule (side + entry price only)

```
PATTERN : bull_run2/3 or bear_run2/3 on 1m
WAIT    : ≤8 bars for opposite-color pullback touching ignition bar range
ENTRY   : close of next same-color continuation bar
FILTERS : ATR14 ≥ 10
        + compress (prior range ≤0.7×ATR AND body ≥0.8×ATR)
        + engulf prior bar
        + control close (BUY loc≥0.65 / SELL loc≤0.35)
        + NOT at session extreme (≤ max(8,ATR) of sess high/low)
SIDE    : run direction
PRICE   : continuation close
```

## Stability across windows

| Window | Book | n | m25_first% | Train | OOS | raw m25% | clean15% | avg MFE | avg MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 120d | all | 21 | **85.71** | 100.0 | 80.0 | 85.71 | 38.1 | 73.31 | 22.45 |
| 120d | 1/day | 14 | **85.71** | 100.0 | 80.0 | 85.71 | 35.71 | 67.46 | 21.34 |
| 180d | all | 57 | **71.93** | 68.29 | 81.25 | 87.72 | 36.84 | 73.39 | 31.66 |
| 180d | 1/day | 33 | **72.73** | 68.18 | 81.82 | 84.85 | 36.36 | 66.79 | 31.45 |
| 240d | all | 65 | **70.77** | 63.64 | 85.71 | 84.62 | 32.31 | 68.81 | 32.97 |
| 240d | 1/day | 40 | **70.0** | 61.54 | 85.71 | 80.0 | 30.0 | 60.97 | 33.78 |

## Walk-forward folds (240d / 4)

| Fold | n | m25_first% | raw m25% | clean15% |
|---|---:|---:|---:|---:|
| fold1:2025-11-27→2026-02-20 | 8 | **62.5** | 62.5 | 0.0 |
| fold2:2026-02-23→2026-05-25 | 36 | **63.89** | 88.89 | 36.11 |
| fold3:2026-05-26→2026-08-19 | 6 | **100.0** | 100.0 | 50.0 |
| fold4:2026-08-20→2026-11-16 | 15 | **80.0** | 80.0 | 33.33 |

## Every trade — 120d window (all signals)

| Day | HM | Side | Entry | ATR | MFE | MAE | m25_first | clean15 |
|---|---|---|---:|---:|---:|---:|---|---|
| 2026-06-04 | 13:26 | **BUY** | **23364.4** | 15.72 | 69.35 | 18.25 | True | False |
| 2026-06-29 | 09:49 | **SELL** | **24082.7** | 12.5 | 30.95 | 37.3 | True | False |
| 2026-06-29 | 10:34 | **SELL** | **24105.35** | 11.01 | 86.7 | 11.1 | True | True |
| 2026-06-29 | 10:34 | **SELL** | **24105.35** | 11.01 | 86.7 | 11.1 | True | True |
| 2026-07-07 | 10:48 | **BUY** | **24488.7** | 10.0 | 37.05 | 18.85 | True | False |
| 2026-07-24 | 09:34 | **SELL** | **23688.6** | 12.72 | 82.3 | 7.6 | True | True |
| 2026-08-31 | 09:38 | **SELL** | **24050.1** | 10.83 | 52.15 | 1.8 | True | True |
| 2026-09-29 | 09:54 | **BUY** | **22605.55** | 11.29 | 13.7 | 34.0 | False | False |
| 2026-10-05 | 10:14 | **SELL** | **22543.75** | 12.82 | 82.95 | 16.75 | True | False |
| 2026-10-05 | 10:14 | **SELL** | **22543.75** | 12.82 | 82.95 | 16.75 | True | False |
| 2026-10-12 | 10:14 | **SELL** | **22486.0** | 11.98 | 109.75 | 17.4 | True | False |
| 2026-10-12 | 10:14 | **SELL** | **22486.0** | 11.98 | 109.75 | 17.4 | True | False |
| 2026-10-14 | 10:00 | **BUY** | **22727.0** | 15.01 | 20.2 | 52.2 | False | False |
| 2026-10-14 | 10:07 | **SELL** | **22693.7** | 11.09 | 18.9 | 53.5 | False | False |
| 2026-10-21 | 10:50 | **SELL** | **22976.75** | 11.46 | 162.75 | 12.5 | True | True |
| 2026-10-21 | 10:50 | **SELL** | **22976.75** | 11.46 | 162.75 | 12.5 | True | True |
| 2026-10-22 | 13:47 | **BUY** | **22629.35** | 11.53 | 77.45 | 17.9 | True | False |
| 2026-11-04 | 11:49 | **SELL** | **23784.65** | 10.07 | 47.2 | 50.3 | True | False |
| 2026-11-04 | 11:49 | **SELL** | **23784.65** | 10.07 | 47.2 | 50.3 | True | False |
| 2026-11-11 | 09:49 | **SELL** | **25402.35** | 13.53 | 74.4 | 4.5 | True | True |
| 2026-11-12 | 11:25 | **SELL** | **25294.3** | 11.96 | 84.3 | 9.4 | True | True |

## Verdict

- 120d all-signals: **85.71%** m25_first (OOS 80.0%) → HIGH_85 — best accurate rule so far; **not** 100%
- Longer windows: 120d=85.71%, 180d=71.93%, 240d=70.77%
- Still **no** PROVEN_100 / PROMISING_95 on ≥15 trades for favour-first ≥25.
- Live IGN100 remains research-only; this pullback rule is the **most accurate** causal entry found.

_Generated in 79.1s._
