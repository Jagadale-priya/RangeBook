# Stack sources alone — last 1y

**Window (live golden):** `2025-10-24` → `2026-10-23`
**Book rule when alone:** same day-cap2 · same-side (as stack, but one track only)

## What each is

- **`PROVEN_100`** — Dual-15m **proven** tickets — historically perfect / locked OR-break + model lane. Highest stack priority (0).
- **`GOOD_PROD2`** — Prod2 **15m good** tickets from live session scoring. Volume backbone. Priority 1.
- **`CHAMPION`** — Dual-15m **champion** tickets after champ floor filter. Priority 2.
- **`CROWN_DUAL_HTF`** — 5m **crown** tickets, only on `HTF_ACTIVE_DAY`. Lowest priority (3); fill when higher tracks quiet.

## Alone (cap2) vs raw pool

| Source | Raw N@hit | Alone cap2 N@hit | In full stack* |
|---|---|---|---|
| `PROVEN_100` | 24@100.0 | **24@100.0** | 24@100.0 |
| `GOOD_PROD2` | 127@68.5 | **126@69.05** | 75@62.67 |
| `CHAMPION` | 41@92.68 | **40@92.5** | 40@92.5 |
| `CROWN_DUAL_HTF` | 126@73.81 | **106@70.75** | 90@71.11 |

\* *In full stack* = calls that survived merge priority inside `STACK_PLUS_CROWN_HTF_CAP2` (229@75.11%).

## Full stack track mix

| Track | N in stack | Share |
|---|---:|---:|
| `crown_5m` | 90 | 39.3% |
| `good_prod2` | 75 | 32.8% |
| `champion` | 40 | 17.5% |
| `proven_100` | 24 | 10.5% |

**Full stack:** N=229 · hit **75.11%**

## Monthly alone cap2 — `PROVEN_100`

| Month | N | Hit% | W |
|---|---:|---:|---:|
| 2025-11 | 2 | 100.0 | 2 |
| 2025-12 | 3 | 100.0 | 3 |
| 2026-01 | 1 | 100.0 | 1 |
| 2026-02 | 2 | 100.0 | 2 |
| 2026-04 | 1 | 100.0 | 1 |
| 2026-06 | 2 | 100.0 | 2 |
| 2026-07 | 1 | 100.0 | 1 |
| 2026-08 | 3 | 100.0 | 3 |
| 2026-09 | 4 | 100.0 | 4 |
| 2026-10 | 5 | 100.0 | 5 |

## Monthly alone cap2 — `GOOD_PROD2`

| Month | N | Hit% | W |
|---|---:|---:|---:|
| 2025-10 | 6 | 50.0 | 3 |
| 2025-11 | 10 | 70.0 | 7 |
| 2025-12 | 16 | 68.75 | 11 |
| 2026-01 | 8 | 100.0 | 8 |
| 2026-02 | 9 | 55.56 | 5 |
| 2026-03 | 6 | 83.33 | 5 |
| 2026-04 | 8 | 50.0 | 4 |
| 2026-05 | 8 | 75.0 | 6 |
| 2026-06 | 11 | 72.73 | 8 |
| 2026-07 | 9 | 55.56 | 5 |
| 2026-08 | 11 | 54.55 | 6 |
| 2026-09 | 14 | 64.29 | 9 |
| 2026-10 | 10 | 100.0 | 10 |

## Monthly alone cap2 — `CHAMPION`

| Month | N | Hit% | W |
|---|---:|---:|---:|
| 2025-10 | 1 | 100.0 | 1 |
| 2025-11 | 3 | 66.67 | 2 |
| 2025-12 | 4 | 100.0 | 4 |
| 2026-01 | 4 | 100.0 | 4 |
| 2026-02 | 4 | 100.0 | 4 |
| 2026-03 | 1 | 100.0 | 1 |
| 2026-04 | 2 | 100.0 | 2 |
| 2026-05 | 5 | 100.0 | 5 |
| 2026-06 | 2 | 50.0 | 1 |
| 2026-07 | 5 | 100.0 | 5 |
| 2026-08 | 3 | 100.0 | 3 |
| 2026-09 | 4 | 75.0 | 3 |
| 2026-10 | 2 | 100.0 | 2 |

## Monthly alone cap2 — `CROWN_DUAL_HTF`

| Month | N | Hit% | W |
|---|---:|---:|---:|
| 2025-10 | 5 | 80.0 | 4 |
| 2025-11 | 3 | 100.0 | 3 |
| 2025-12 | 3 | 66.67 | 2 |
| 2026-01 | 14 | 64.29 | 9 |
| 2026-02 | 18 | 61.11 | 11 |
| 2026-03 | 7 | 71.43 | 5 |
| 2026-04 | 7 | 57.14 | 4 |
| 2026-05 | 8 | 75.0 | 6 |
| 2026-06 | 12 | 58.33 | 7 |
| 2026-07 | 8 | 87.5 | 7 |
| 2026-08 | 4 | 100.0 | 4 |
| 2026-09 | 5 | 40.0 | 2 |
| 2026-10 | 12 | 91.67 | 11 |

## How they combine (live)

1. Score all four pools on the session.
2. Merge with priority **proven > good > champ > crown**.
3. Cap **2 calls/day**, **same side** only.
4. Crown only if day is HTF-active.

That merge = `STACK_PLUS_CROWN_HTF_CAP2` (volume live).

