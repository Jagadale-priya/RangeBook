# November 2026 — why holding accurate desks barely fired

**Window:** `2026-11-01` → `2026-11-15` (today) · held logic P1→P2F  
**Data:** research caches end `2026-11-13` (`_cache_path_trusted_10y` / `_cache_dual15_dual5_10y`)

## Verdict

Only **one** Nov day produced a holding-accurate call: **2026-11-06**.  
All other Nov session days are silent because the path-true inputs those desks need (**good / crown / champ / dual proven·champion**) are **absent** in the research cache — not because day-dedupe dropped them.

## The one call

| Field | Value |
|---|---|
| Day | `2026-11-06` |
| HM / side | `11:20` · BUY |
| Stream | `ACC100_CROWN_BUY_AM1130_T20` |
| Path | crown T20 · `p_t1=0.5551` · +20 pts · win |
| Desks | Every nested desk P1→P2F (V1…V11, P92…P75, Cap2) — same day, nested |
| accuracy_tag | `ACC_RANGE_98_100` (V11 family) |

**Why it matched Phase-1 crown recipe:** BUY · hm in `[09:15, 11:30]` · path-scored @ T20.

## Day-by-day (Nov session calendar in cache)

Sessions present: `11-02, 03, 04, 05, 06, 08, 09, 11, 12, 13`  
(Off: `11-01` Sat · `11-07` Sat · `11-10` holiday · `11-14` Sat · `11-15` Sun)

| Day | Session | good path | crown path | champ | dual15 | dual5 | Holding call? | Why |
|---|---|---:|---:|---:|---:|---:|---|---|
| 11-02 | yes | 0 | 0 | 0 | 0 | 0 | **No** | No path/dual rows → no stream can rebuild |
| 11-03 | yes | 0 | 0 | 0 | 0 | 0 | **No** | same |
| 11-04 | yes | 0 | 0 | 0 | 0 | 0 | **No** | same |
| 11-05 | yes | 0 | 0 | 0 | 0 | 0 | **No** | same |
| **11-06** | yes | 0 | **8** | 0 | 0 | 0 | **Yes** | Crown BUY 11:20 passes `ACC100_CROWN_BUY_AM1130_T20` |
| 11-08 | yes | 0 | 0 | 0 | 0 | 0 | **No** | No path/dual rows |
| 11-09 | yes | 0 | 0 | 0 | 0 | 0 | **No** | same |
| 11-11 | yes | 0 | 0 | 0 | 0 | 0 | **No** | same |
| 11-12 | yes | 0 | 0 | 0 | 0 | 0 | **No** | same |
| 11-13 | yes | 0 | 0 | 0 | 0 | 0 | **No** | same |
| 11-14/15 | weekend | — | — | — | — | — | — | Market closed |

## Logic checklist (why silence is correct under held rules)

A holding desk fires on day D only if:

1. Phase-1 recipe row exists that day, **or** a P2c–P2f **stream tag** rebuilds a path-true row on D  
2. Filters pass (side · `p_t1` · session window · gap · HTF · pick)  
3. Day-dedupe keeps 1 call (cap2 ≤2)

For silent Nov days, step **1 never happens** — there is nothing in `good_by_risk` / `crown_by_risk` / `champ_native` / dual proven·champion for that day. Extra P2F streams (micro-band / weekday / mid / triple-CF) cannot invent calls without base path rows.

Widening to P75 or Cap2 does **not** unlock those days: Cap2 only adds a second call on days that already match.

## Context vs October

| Month | P2F P100 call-days | P2F P75 call-days |
|---|---:|---:|
| Oct 2026 | 11 | 15 |
| Nov 1–13 | **1** | **1** |

Oct had many days with crown (and some dual) path rows. Nov cache so far has crown on **one** day only.

## Not a LIVE-coverage issue

LIVE stack (`STACK_PLUS_CROWN_HTF_CAP2` + `AGREE_15M_ANY5`) is a different lane and can still print volume when holding accurate stays quiet. Holding desks optimize **hit rate**, not daily coverage.

## If you want more Nov visibility later

1. Refresh path/dual research caches through today (confirm Nov silence isn’t a stale-cache artifact for good/champ).  
2. Keep LIVE for coverage; treat holding accurate as high-conviction subset.  
3. Only if refreshed cache shows real path rows that still miss recipes → then research a new phase (do not mutate held P2F without confirm).
