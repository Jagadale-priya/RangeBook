# NIFTY afternoon BUY · price-action thrust filters

**Target day:** `2026-11-19` ~+170 pts after 13:00
**Sample:** last 60 sessions · ±30 · 1 call/day

Naive dual-cont afternoon was only **40%** hit — not live-ready.
These rules ignore model p and use **OR-up + thrust bar** after 13:00.

| Rule | N | Hit% | W/L | Today | Today HM |
|---|---:|---:|---|---|---|
| `thrust2_green` | 18 | 77.78 | 14/4 | YES | 13:30 |
| `thrust2_up20` | 15 | 80.0 | 12/3 | YES | 14:00 |
| `thrust2_up30` | 13 | 92.31 | 12/1 | YES | 14:00 |
| `thrust2_up40` | 11 | 72.73 | 8/3 | YES | 14:00 |
| `thrust2_up50` | 11 | 72.73 | 8/3 | YES | 14:00 |
| `thrust3_up30` | 13 | 92.31 | 12/1 | YES | 14:00 |
| `thrust2_up30_rng25` | 13 | 84.62 | 11/2 | YES | 14:00 |
| `thrust2_up30_top70` | 13 | 92.31 | 12/1 | YES | 14:00 |
| `thrust2_up40_top70` | 9 | 88.89 | 8/1 | YES | 14:00 |
| `thrust2_up40_rng30_top70` | 9 | 88.89 | 8/1 | YES | 14:00 |
| `hm14_up30` | 9 | 88.89 | 8/1 | YES | 14:00 |
| `hm14_up40_rng30` | 8 | 75.0 | 6/2 | YES | 14:00 |

## Selected: `thrust2_up30` · **92.31%** · n=13

Rules: `{"break_prior_highs": 2, "require_green": true, "min_uplift_from_13": 30}`

### Today

- **14:00** BUY @ 25418.4 · uplift_from_13=59.2 · win=True pts=30.0

### All calls

| Day | HM | Entry | Uplift13 | ExtOR | Win | Pts |
|---|---|---:|---:|---:|---|---:|
| 2026-08-25 | 14:30 | 24196.65 | 51.6 | 0.157 | W | 30.0 |
| 2026-09-11 | 13:45 | 23338.85 | 31.0 | 2.371 | W | 30.0 |
| 2026-09-18 | 14:15 | 23352.9 | 36.7 | 0.079 | W | 30.0 |
| 2026-09-21 | 13:45 | 23433.65 | 50.6 | 0.681 | W | 30.0 |
| 2026-10-09 | 13:45 | 22533.5 | 36.3 | 1.858 | W | 30.0 |
| 2026-10-13 | 14:00 | 22563.4 | 39.6 | 0.549 | W | 30.0 |
| 2026-10-26 | 13:15 | 22650.05 | 49.6 | 0.866 | W | 30.0 |
| 2026-10-29 | 13:45 | 22864.9 | 57.7 | 1.615 | W | 30.0 |
| 2026-11-02 | 14:30 | 23291.1 | 35.7 | 0.355 | W | 30.0 |
| 2026-11-03 | 13:15 | 23721.15 | 37.5 | 0.649 | L | -30.0 |
| 2026-11-05 | 13:15 | 24480.05 | 31.1 | 1.003 | W | 30.0 |
| 2026-11-06 | 13:15 | 24745.6 | 46.3 | 1.24 | W | 30.0 |
| 2026-11-19 | 14:00 | 25418.4 | 59.2 | 1.295 | W | 30.0 |

## Live proposal

- Add **NIFTY afternoon thrust BUY** lane (`thrust2_up30`)
- Does **not** loosen morning dual first-break
- Cap 1/day · ±30 · after 13:00 only
