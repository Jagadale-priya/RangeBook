# Causal gates toward 99% live accuracy

**Window:** `2025-11-20` → `2026-11-20` · ±30 · **no win hindsight**

## Can we get 99% on live?

**YES with tight gates:** Cap1 · p≥0.55 · tracks=['champion', 'proven_research'] · hm=10:00-14:00 → **27 @ 100.0%**

Tradeoff: much fewer calls than open Cap6.

- Best ≥98%: Cap1 p≥0.55 tracks=['champion', 'proven_research'] hm=10:00-14:00 → **27@100.0%**
- Best ≥95%: Cap2 p≥0.55 tracks=['champion', 'good_prod2', 'proven_research'] hm=09:45-13:30 → **54@96.3%**
- Best ≥90%: Cap2 p≥0.55 tracks=['champion', 'good_prod2', 'proven_research'] hm=*-* → **76@93.42%**

Open Cap6 baseline: **467 @ 75.16%**

## Live-safe levers (real hacks)

1. **Raise p_t1 floor** (strongest)
2. **Lower day cap** (Cap1–2)
3. **Whitelist tracks** (champion / proven / dual10m)
4. **Time window** (skip weak open/late)

## Not live-safe (fake 99%)

- Filter on historical `win`
- Year accuracy floor after seeing outcomes
- Measure Cap6 while crown/scalper notify

## Top (N≥20) by hit%

| Cap | pmin | Tracks | HM | N | Hit% | W/L |
|---:|---|---|---|---:|---:|---|
| 1 | 0.55 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 1 | 0.6 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 1 | 0.6 | ['champion', 'good_prod2', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 2 | 0.55 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 2 | 0.6 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 2 | 0.6 | ['champion', 'good_prod2', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 3 | 0.55 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 3 | 0.6 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 3 | 0.6 | ['champion', 'good_prod2', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 4 | 0.55 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 4 | 0.6 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 4 | 0.6 | ['champion', 'good_prod2', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 6 | 0.55 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 6 | 0.6 | ['champion', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 6 | 0.6 | ['champion', 'good_prod2', 'proven_research'] | 10:00-14:00 | 27 | **100.0%** | 27/0 |
| 1 | 0.65 | ['champion', 'dual10m', 'proven_research'] | 10:00-14:00 | 26 | **100.0%** | 26/0 |
| 1 | 0.65 | ['champion', 'proven_research'] | 10:00-14:00 | 26 | **100.0%** | 26/0 |
| 1 | 0.65 | ['champion', 'good_prod2', 'proven_research'] | 10:00-14:00 | 26 | **100.0%** | 26/0 |
| 2 | 0.65 | ['champion', 'dual10m', 'proven_research'] | 10:00-14:00 | 26 | **100.0%** | 26/0 |
| 2 | 0.65 | ['champion', 'proven_research'] | 10:00-14:00 | 26 | **100.0%** | 26/0 |

## Top (N≥50) by hit%

| Cap | pmin | Tracks | HM | N | Hit% | W/L |
|---:|---|---|---|---:|---:|---|
| 2 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:45-13:30 | 54 | **96.3%** | 52/2 |
| 3 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:45-13:30 | 54 | **96.3%** | 52/2 |
| 4 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:45-13:30 | 54 | **96.3%** | 52/2 |
| 6 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:45-13:30 | 54 | **96.3%** | 52/2 |
| 2 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | *-* | 76 | **93.42%** | 71/5 |
| 3 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | *-* | 76 | **93.42%** | 71/5 |
| 4 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | *-* | 76 | **93.42%** | 71/5 |
| 6 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | *-* | 76 | **93.42%** | 71/5 |
| 2 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:30-14:30 | 74 | **93.24%** | 69/5 |
| 3 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:30-14:30 | 74 | **93.24%** | 69/5 |
| 4 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:30-14:30 | 74 | **93.24%** | 69/5 |
| 6 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:30-14:30 | 74 | **93.24%** | 69/5 |
| 1 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | *-* | 68 | **92.65%** | 63/5 |
| 1 | 0.55 | ['champion', 'good_prod2', 'proven_research'] | 09:30-14:30 | 66 | **92.42%** | 61/5 |
| 1 | 0.55 | ['champion', 'proven_research'] | *-* | 61 | **91.8%** | 56/5 |

JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\NIFTY_CAUSAL_GATES_TO_99.json`
