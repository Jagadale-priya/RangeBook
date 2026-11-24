# SENSEX · ACC100 more calls · last 6 months (deep)

**Generated:** `2026-11-21T18:52:54`
**Window:** `2026-05-21` → `2026-11-21` · 86 sessions

## Method

- Live Sensex candidate book · path settle **±50** on 5m kite tape
- Causal gates only — **never** filter on `win`
- Goal: **max N @ 100%** on 6m (multi-lot OK)
- Walk-forward: tune on first ~4m · hold out last ~2m · require 100% on both

## Headline

- Live T50 Cap3 policy 6m: **22 @ 90.91%**
- Prior ACC100 Cap1 first 6m: **36 @ 91.67%**
- In-sample densest 100%: **22 @ 100.0%** · `cap=1 p≥0.5 tracks=None hm=10:00-14:00 or≤None first=True sides=None buy/sell=None/None`
- **Recommended WF-stable lock:** **22 @ 100.0%** (holdout 6 @ 100.0%)
- Gate: `{'cap': 1, 'pmin': 0.5, 'tracks': None, 'hm_lo': '10:00', 'hm_hi': '14:00', 'max_or_ext': None, 'first_only': True, 'sides': None, 'buy_p': None, 'sell_p': None}`

## Top in-sample 100% gates (by N)

| N | Hit | Cap | pmin | Tracks | HM | or≤ | first | sides | buy/sell | Pts |
|---:|---:|---:|---:|---|---|---:|---|---|---|---:|
| 22 | **100.0** | 1 | 0.5 | ALL | 10:00-14:00 | None | True | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 2 | 0.5 | ALL | 10:00-14:00 | None | True | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 3 | 0.5 | ALL | 10:00-14:00 | None | True | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 4 | 0.5 | ALL | 10:00-14:00 | None | True | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 1 | 0.52 | ALL | 10:00-14:00 | None | True | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 2 | 0.52 | ALL | 10:00-14:00 | None | True | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 3 | 0.52 | ALL | 10:00-14:00 | None | True | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 4 | 0.52 | ALL | 10:00-14:00 | None | True | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 1 | 0.5 | ['champion'] | 10:00-14:00 | None | False | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 2 | 0.5 | ['champion'] | 10:00-14:00 | None | False | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 3 | 0.5 | ['champion'] | 10:00-14:00 | None | False | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 4 | 0.5 | ['champion'] | 10:00-14:00 | None | False | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 1 | 0.52 | ['champion'] | 10:00-14:00 | None | False | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 2 | 0.52 | ['champion'] | 10:00-14:00 | None | False | BOTH | None/None | 1100.0 |
| 22 | **100.0** | 3 | 0.52 | ['champion'] | 10:00-14:00 | None | False | BOTH | None/None | 1100.0 |

## Recommended lock calls (6m)

| Day | HM | Side | p | Track | Win | Pts |
|---|---|---|---:|---|---|---:|
| 2026-05-21 | 10:45 | SELL | 0.75 | champion | W | 50.0 |
| 2026-06-05 | 10:30 | SELL | 0.6324 | champion | W | 50.0 |
| 2026-06-15 | 12:00 | SELL | 0.6667 | champion | W | 50.0 |
| 2026-06-23 | 11:45 | SELL | 0.5284 | champion | W | 50.0 |
| 2026-06-29 | 11:30 | SELL | 0.6324 | champion | W | 50.0 |
| 2026-07-08 | 12:00 | SELL | 0.6324 | champion | W | 50.0 |
| 2026-07-23 | 12:30 | SELL | 0.6324 | champion | W | 50.0 |
| 2026-07-31 | 12:00 | BUY | 0.5455 | champion | W | 50.0 |
| 2026-08-04 | 10:15 | SELL | 0.75 | champion | W | 50.0 |
| 2026-08-26 | 10:15 | SELL | 0.75 | champion | W | 50.0 |
| 2026-08-27 | 10:00 | SELL | 0.6324 | champion | W | 50.0 |
| 2026-09-01 | 11:00 | BUY | 0.5714 | champion | W | 50.0 |
| 2026-09-07 | 10:00 | SELL | 0.6324 | champion | W | 50.0 |
| 2026-09-08 | 10:30 | SELL | 0.5284 | champion | W | 50.0 |
| 2026-09-18 | 14:00 | BUY | 0.5714 | champion | W | 50.0 |
| 2026-09-21 | 11:45 | BUY | 0.5455 | champion | W | 50.0 |
| 2026-09-22 | 10:30 | SELL | 0.5284 | champion | W | 50.0 |
| 2026-10-01 | 12:15 | SELL | 0.6667 | champion | W | 50.0 |
| 2026-10-05 | 10:30 | SELL | 0.75 | champion | W | 50.0 |
| 2026-10-16 | 10:00 | BUY | 0.5714 | champion | W | 50.0 |
| 2026-10-19 | 11:45 | SELL | 0.75 | champion | W | 50.0 |
| 2026-10-21 | 10:00 | SELL | 0.75 | champion | W | 50.0 |

## Recommendation

1. Prefer **WF-stable** densest 100% over pure in-sample max N.
2. Cap6-style volume (T50 Cap3) stays the volume desk — not ACC100.
3. Scale returns with **lots** on ACC100 calls.

JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\SENSEX_ACC100_MORE_CALLS_6M.json`
WF: `C:\Users\Priyanka\Agent\prod_live\reports\1y\SENSEX_ACC100_MORE_CALLS_6M_WF_STABLE.json`
