# 15m dual × 5m dual — confirm-100 hunt

**Goal:** combine dual packs on **15m** and **5m**; take **5m entry** when they agree; hunt ~**100%** confirm book.

Research only. Final / holding desks unchanged.

## How it works

1. Same dual packs + proven/champion gates
2. Walk OR-break on **15m** → dual15 signals (gate)
3. Walk OR-break on **5m** → dual5 tickets (entry + P&L)
4. Confirm = same **day + side**; pick best `p_t1` **5m** row

## Baselines (3y)

| Book | N | Hit | Perfect | Day cov |
|---|---:|---:|---|---:|
| `dual15_proven` | 41 | **100.0%** | True | 5.5% |
| `dual15_any` | 150 | **84.67%** | False | 19.7% |
| `dual5_proven` | 18 | **50.0%** | False | 2.4% |
| `dual5_any` | 56 | **51.79%** | False | 7.1% |
| `agree_dual_any_5mentry` | 13 | **84.62%** | False | 1.7% |
| `agree_proven15_proven5` | 2 | **100.0%** | True | 0.3% |

## 3y board (hit-ranked, n≥5)

| Approach | N | Hit | Perfect | Day | Points |
|---|---:|---:|---|---:|---:|
| `dual15_proven` | 41 | **100.0%** | True | 5.5% | 1812.0 |
| `time_agree_dual_30m` | 11 | **100.0%** | True | 1.5% | 348.0 |
| `time_agree_dual_15m` | 10 | **100.0%** | True | 1.3% | 303.0 |
| `time_agree_dual_60m` | 12 | **91.67%** | False | 1.6% | 323.0 |
| `confirm_cap1_time60` | 12 | **91.67%** | False | 1.6% | 323.0 |
| `dual5_champ_if_dual15` | 8 | **87.5%** | False | 1.1% | 201.0 |
| `agree_dual_champ5_5mentry` | 8 | **87.5%** | False | 1.1% | 201.0 |
| `dual5_champ_if_dual15_champ` | 7 | **85.71%** | False | 0.9% | 171.0 |
| `dual15_any` | 150 | **84.67%** | False | 19.7% | 4302.0 |
| `dual5_any_if_dual15` | 13 | **84.62%** | False | 1.7% | 296.0 |
| `agree_dual_any_5mentry` | 13 | **84.62%** | False | 1.7% | 296.0 |
| `agree_dual_any_p57` | 13 | **84.62%** | False | 1.7% | 296.0 |
| `agree_dual_any_p60` | 13 | **84.62%** | False | 1.7% | 296.0 |
| `agree_dual_any_p62` | 13 | **84.62%** | False | 1.7% | 296.0 |
| `agree_dual_any_p65` | 13 | **84.62%** | False | 1.7% | 296.0 |
| `confirm_cap1_agree_any` | 13 | **84.62%** | False | 1.7% | 296.0 |
| `dual5_proven_if_dual15` | 5 | **80.0%** | False | 0.7% | 95.0 |
| `agree_dual_proven5_5mentry` | 5 | **80.0%** | False | 0.7% | 95.0 |
| `confirm_cap1_agree_proven5` | 5 | **80.0%** | False | 0.7% | 95.0 |
| `dual15_champ` | 109 | **78.9%** | False | 14.3% | 2490.0 |
| `dual5_champ` | 38 | **52.63%** | False | 4.7% | 93.0 |
| `dual5_champ_floored` | 38 | **52.63%** | False | 4.7% | 93.0 |
| `dual5_any` | 56 | **51.79%** | False | 7.1% | 70.0 |
| `dual5_proven` | 18 | **50.0%** | False | 2.4% | -23.0 |

## Perfect books 3y (n≥10)

| Book | N | Day | Points |
|---|---:|---:|---:|
| `dual15_proven` | 41 | 5.5% | 1812.0 |
| `time_agree_dual_30m` | 11 | 1.5% | 348.0 |
| `time_agree_dual_15m` | 10 | 1.3% | 303.0 |

## Both-year ≥95% (1y n≥5, 3y n≥8)

| Book | 1y | 3y |
|---|---|---|
| `dual15_proven` | 100.0% / n=24 / day=9.7% PERFECT | **100.0%** / n=41 / day=5.5% PERFECT |
| `time_agree_dual_30m` | 100.0% / n=7 / day=2.8% PERFECT | **100.0%** / n=11 / day=1.5% PERFECT |
| `time_agree_dual_15m` | 100.0% / n=7 / day=2.8% PERFECT | **100.0%** / n=10 / day=1.3% PERFECT |

## Nov 2026 overlay

| Book | N | Hit | Perfect |
|---|---:|---:|---|

## Recommended confirm logic (research tag)

**Best 100% on 5m entry:** `TIME_AGREE_DUAL_30m` → tag `CONFIRM_DUAL15_DUAL5_TIME30`  
(±15m also perfect; ±60m drops to 91.7% on 3y)

```
1. Score dual packs on 15m OR-break → dual15 (proven/champ)  [GATE]
2. Score dual packs on 5m OR-break  → dual5 (proven/champ)   [ENTRY]
3. IF same day + same side AND |hm15 − hm5| ≤ 30 min:
      emit CONFIRM = dual5 ticket with max p_t1
      accurate_tag = CONFIRM_DUAL15_DUAL5_TIME30
4. Do NOT use raw 5m dual alone (3y ~52% — packs are 15m-native)
5. Day+side agree without time clock = only ~85% (not 100%)
```

| Book | 3y | Role |
|---|---|---|
| `time_agree_dual_30m` | **11 @ 100%** | **confirm on 5m entry** |
| `time_agree_dual_15m` | **10 @ 100%** | tighter clock |
| `dual15_proven` | 41 @ 100% | 15m entry (not 5m confirm) |
| `agree_dual_any_5mentry` | 13 @ 84.6% | day+side only — not 100% |

Code sketch: `prod_live/logic/confirm_dual_tf.py` (research, not live)

## Verdict

- **Yes** — 15m dual × 5m dual can make **100% confirm calls on the 5m ticket** when clocks are within **±30m**.
- Coverage is **thin** (~1.5% of days / n=11 over 3y). Nov 1–13: **0** fires.
- Raw **5m dual alone fails** (~52%) — confirm must stay gated by 15m dual + time.
- Not wired to final / holding until you promote.

Elapsed 2042.1s · JSON `prod_live/reports/1y/DUAL15_DUAL5_CONFIRM100.json`
