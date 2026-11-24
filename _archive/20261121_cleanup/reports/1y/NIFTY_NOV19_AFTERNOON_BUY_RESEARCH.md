# NIFTY · why we missed 2026-11-19 afternoon BUY · research probes

**Move after 13:00:** low 25344.55 → high 25514.3 · **+169.8 pts** (from 13:00 open to high **+137.0**)

## Why live dual did not list

- `proven_100` BUY hard-stops at **13:00** (`PROVEN_BUY_MAX_MINS`).
- `champion` BUY needs **first_break** + regime ∈ {range, mixed} + p≥**0.55** — afternoon continuation after OR already broken usually fails `first_break`.
- `SUPPRESS_DUAL_LIST=1` anyway; CHAMP_PLUS fill still needs a seed call from dual/stack.

### Dual walk · after 13:00 reason counts

| Reason | Bars |
|---|---:|
| `side_score_miss` | 8 |
| `gates_fail` | 2 |

### Full dual walk today

| HM | Close | Call? | Reason | p_t1 | FB | Regime | Up |
|---|---:|---|---|---:|---|---|---|
| 09:15 | 25115.9 | — | no_or_break | None | None | None | None |
| 09:30 | 25224.8 | — | no_or_break | None | None | None | None |
| 09:45 | 25279.6 | — | side_score_miss | None | None | None | None |
| 10:00 | 25280.5 | — | side_score_miss | None | None | None | None |
| 10:15 | 25248.5 | — | no_or_break | None | None | None | None |
| 10:30 | 25282.0 | — | side_score_miss | None | None | None | None |
| 10:45 | 25292.9 | — | side_score_miss | None | None | None | None |
| 11:00 | 25303.1 | — | side_score_miss | None | None | None | None |
| 11:15 | 25317.0 | — | gates_fail | 0.6829 | False | trend | None |
| 11:30 | 25330.5 | — | side_score_miss | None | None | None | None |
| 11:45 | 25369.3 | — | side_score_miss | None | None | None | None |
| 12:00 | 25356.1 | — | gates_fail | 0.6829 | False | trend | None |
| 12:15 | 25358.3 | — | gates_fail | 0.6829 | False | mixed | None |
| 12:30 | 25362.7 | — | gates_fail | 0.6829 | False | mixed | None |
| 12:45 | 25374.2 | — | side_score_miss | None | None | None | None |
| 13:00 | 25356.5 | — | side_score_miss | None | None | None | None |
| 13:15 | 25370.2 | — | side_score_miss | None | None | None | None |
| 13:30 | 25386.5 | — | side_score_miss | None | None | None | None |
| 13:45 | 25390.0 | — | gates_fail | 0.6829 | False | trend | None |
| 14:00 | 25436.5 | — | side_score_miss | None | None | None | None |
| 14:15 | 25468.6 | — | gates_fail | 0.6829 | False | trend | None |
| 14:30 | 25460.4 | — | side_score_miss | None | None | None | None |
| 14:45 | 25457.3 | — | side_score_miss | None | None | None | None |
| 15:00 | 25503.7 | — | side_score_miss | None | None | None | None |
| 15:15 | 25514.3 | — | side_score_miss | None | None | None | None |

## Afternoon BUY probes (last 60 sessions, entry ≥13:00, ±30 on 5m)

| Probe | N | Hit% | W/L | Days | Fired today? |
|---|---:|---:|---|---:|---|
| `live_champ_p55_fb_only` | 0 | None | 0/0 | 0 | **no** |
| `p55_cont_range_mixed` | 3 | 33.33 | 1/2 | 2 | **no** |
| `p55_cont_all_regimes` | 14 | 50.0 | 7/7 | 7 | **YES** |
| `p50_cont_all_regimes` | 14 | 50.0 | 7/7 | 7 | **YES** |
| `p50_fb_all_regimes` | 0 | None | 0/0 | 0 | **no** |
| `p58_cont_trend_vol` | 14 | 50.0 | 7/7 | 7 | **YES** |

### Today fires · `p55_cont_all_regimes`

| HM | Track | p_t1 | Win | Pts |
|---|---|---:|---|---:|
| 13:45 | champion | 0.6829 | W | 30.0 |
| 14:15 | champion | 0.6829 | W | 30.0 |

### Today fires · `p50_cont_all_regimes`

| HM | Track | p_t1 | Win | Pts |
|---|---|---:|---|---:|
| 13:45 | champion | 0.6829 | W | 30.0 |
| 14:15 | champion | 0.6829 | W | 30.0 |

### Today fires · `p58_cont_trend_vol`

| HM | Track | p_t1 | Win | Pts |
|---|---|---:|---|---:|
| 13:45 | champion | 0.6829 | W | 30.0 |
| 14:15 | champion | 0.6829 | W | 30.0 |

## Recommendation

Add a **separate afternoon BUY continuation lane** (not loosening morning first-break champ):
- Window **13:00–14:45**
- OR already broken up · close > OR high · p≥0.55 (or 0.50 if hit holds)
- Allow **continuation** (not first_break-only)
- Regime allow trend/volatile
- Cap 1 afternoon BUY/day · ±30

Only promote a probe that both **fires today** and keeps probe hit ≥ ~70% on the 60d sample.
