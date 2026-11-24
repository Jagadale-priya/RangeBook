# 5m dual model — more calls, last year held out

**Status:** RESEARCH · not live
**Select:** `2023-11-16` → `2025-11-14` · **Test:** `2025-11-15` → `2026-11-15`
Universe is the 5-minute dual-train tickets only. One or two calls a day, highest model score.

| Pre floor | Rule | Pre N@hit | Test N@hit |
|---:|---|---|---|
| 55 | `BOTH_all_p0_all_any_any_day1` | 460@55.22 | 235@54.47 |
| 60 | `BOTH_all_p52_all_any_any_day1` | 210@63.81 | 97@49.48 |
| 65 | `BOTH_all_p52_all_htf_any_day1` | 132@68.94 | 69@52.17 |
| 70 | `BOTH_all_p52_all_htf_gup_day1` | 92@70.65 | 42@59.52 |
| 75 | `BOTH_mid_p52_all_any_gup_day1` | 79@75.95 | 24@50.0 |
| 80 | `BUY_pm_p0_all_htf_any_day1` | 22@81.82 | 19@52.63 |
| 85 | `BOTH_pm_p52_all_htf_any_day1` | 18@88.89 | 17@52.94 |
| 90 | `BOTH_mid_p57_all_any_g030_day1` | 12@91.67 | 1@0.0 |

## If the test year is allowed to pick the rule (not a frozen test)

| Test bar | Rule | Test N@hit | Pre N@hit |
|---:|---|---|---|
| 70 | `BOTH_pm_p0_all_htf_gup_day1` | 27@70.37 | 33@54.55 |
| 80 | `BOTH_all_p57_all_any_gup_day1` | 1@100.0 | 18@72.22 |
| 90 | `BOTH_all_p57_all_any_gup_day1` | 1@100.0 | 18@72.22 |

## Verdict

No frozen 5m-dual rule holds 90% on the last year. The fullest frozen book is 235 calls @ 54.47% (BOTH_all_p0_all_any_any_day1).

