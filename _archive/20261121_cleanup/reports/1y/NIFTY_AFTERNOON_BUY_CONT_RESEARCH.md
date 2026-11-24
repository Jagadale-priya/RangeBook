# NIFTY afternoon BUY continuation research

**Problem day:** `2026-11-19` after 13:00 · ~**+170 pts** (25345 → 25514)

## Why live missed it

Dual walk today showed **BUY want** with **p≈0.68** at 11:15, 12:00–12:30, **13:45**, **14:15** but `gates_fail` because:

1. `first_break=False` (OR already broken earlier) — champion BUY is first-break only
2. afternoon bars often `regime=trend` — champion BUY only allows `{range, mixed}`
3. `proven_100` BUY hard cutoff at **13:00**

So the big afternoon push was invisible to the live dual gates.

## Probes · last 45 sessions · entry in ('13:00', '13:15', '13:30', '13:45', '14:00', '14:15', '14:30') · 1 BUY/day · ±30

| Probe | N | Hit% | W/L | Days | Today? |
|---|---:|---:|---|---:|---|
| `aft_p55_cont_trend+` | 15 | 40.0 | 6/9 | 15 | **YES** |
| `aft_p55_cont_range_mixed` | 5 | 40.0 | 2/3 | 5 | **no** |
| `aft_p50_cont_trend+` | 15 | 40.0 | 6/9 | 15 | **YES** |
| `aft_p58_cont_trend+` | 15 | 40.0 | 6/9 | 15 | **YES** |
| `aft_p55_fb_only_trend+` | 2 | 50.0 | 1/1 | 2 | **no** |

## Best that also fires today: `aft_p55_cont_trend+`

**15** calls · **40.0%** · 6/9 · 15 days

### Today

| HM | Track | Regime | p_t1 | FB | Win | Pts |
|---|---|---|---:|---|---|---:|
| 13:45 | champion | trend | 0.6829 | False | W | 30.0 |

### All calls

| Day | HM | Regime | p | FB | Win | Pts |
|---|---|---|---:|---|---|---:|
| 2026-09-17 | 13:00 | trend | 0.6829 | False | L | -30.0 |
| 2026-09-18 | 14:15 | trend | 0.6829 | True | W | 30.0 |
| 2026-09-21 | 14:00 | trend | 0.6829 | False | L | -30.0 |
| 2026-09-23 | 13:00 | trend | 0.6829 | False | L | -30.0 |
| 2026-09-25 | 14:15 | mixed | 0.6829 | True | L | -30.0 |
| 2026-09-30 | 13:00 | range | 0.6829 | False | L | -30.0 |
| 2026-10-06 | 13:00 | trend | 0.6829 | False | W | 30.0 |
| 2026-10-09 | 13:00 | trend | 0.6829 | False | W | 30.0 |
| 2026-10-13 | 13:30 | range | 0.6829 | False | W | 30.0 |
| 2026-10-16 | 13:30 | trend | 0.6829 | False | L | -30.0 |
| 2026-10-28 | 13:00 | range | 0.6829 | False | L | -30.0 |
| 2026-10-29 | 13:30 | trend | 0.6829 | False | W | 30.0 |
| 2026-11-03 | 13:45 | trend | 0.6829 | False | L | -30.0 |
| 2026-11-05 | 13:45 | trend | 0.6829 | False | L | -30.0 |
| 2026-11-19 | 13:45 | trend | 0.6829 | False | W | 30.0 |

## Proposed live add-on (NIFTY only · does not change Sensex)

- Lane: **afternoon BUY cont** · `aft_p55_cont_trend+`
- Time: **13:00–14:45**
- OR broken up · allow continuation · regimes include **trend/volatile**
- p_t1 ≥ **0.55**
- Cap **1** afternoon BUY/day · brackets **±30**
- Keep morning first-break champion unchanged
