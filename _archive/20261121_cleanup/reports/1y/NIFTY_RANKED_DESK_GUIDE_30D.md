# NIFTY ranked desk guide · last 30D

**Source:** `csv+kite` 1m + 15m dual packs · cost 1.0
**Window:** 2026-10-19 → 2026-11-18 (22 sessions)
**Module:** `prod_live/logic/nifty_ranked_desk_guide.py`

## Logic (frozen)

1. **proven_100** — buy: range/mixed · p≥0.62 · or_ext≤0.10 · <13:00 · sell: trend · p≥0.58 · ±30
2. **champion** — if proven silent · buy p≥0.55 · sell p≥0.58 · SL20/T30
3. **ORB accurate** — if dual silent · width 40–100 · 5m close within 5 of OR + VWAP · SL12 thru / T20 · flat 14:45

One ticket/session · no reverse · P2F/P2G not a second entry.

Dual columns: stamped from 15m `live.evaluate` OR-breaks onto 1m in that 15m bucket
(18 breaks · 15 days).

## Variant comparison

| Variant | Closed | Hit | Net | Called | Silent |
|---|---:|---:|---:|---:|---:|
| **ranked** (proven→champ→ORB) | 10 | 60.0% | 80.00 | 10 | 12 |
| proven+ORB only (skip champion) | 5 | 80.0% | 89.45 | 5 | 17 |
| orb_only | 2 | 50.0% | 2.45 | 2 | 20 |
| ranked + trend_accurate fill | 10 | 60.0% | 80.00 | 10 | 12 |
| ranked + trend_baseline fill | 10 | 60.0% | 80.00 | 10 | 12 |
| ranked + state_accurate fill | 12 | 58.3% | 86.40 | 11 | 11 |

## Ranked · by desk

| Desk | N | Hit | Net |
|---|---:|---:|---:|
| champion | 6 | 33.3% | -26.00 |
| orb_accurate | 1 | 100.0% | 19.00 |
| proven_100 | 3 | 100.0% | 87.00 |

### Exit reasons (ranked)

```
{'target': 6, 'stop': 4}
```

### Add-on desks (when used)

| Variant | Desks |
|---|---|
| + trend_accurate | `{'proven_100': {'n': 3, 'wins': 3, 'net': 87.0, 'hit_rate': 1.0}, 'champion': {'n': 6, 'wins': 2, 'net': -26.0, 'hit_rate': 0.3333333333333333}, 'orb_accurate': {'n': 1, 'wins': 1, 'net': 19.0, 'hit_rate': 1.0}}` |
| + trend_baseline | `{'proven_100': {'n': 3, 'wins': 3, 'net': 87.0, 'hit_rate': 1.0}, 'champion': {'n': 6, 'wins': 2, 'net': -26.0, 'hit_rate': 0.3333333333333333}, 'orb_accurate': {'n': 1, 'wins': 1, 'net': 19.0, 'hit_rate': 1.0}}` |
| + state_accurate | `{'proven_100': {'n': 3, 'wins': 3, 'net': 87.0, 'hit_rate': 1.0}, 'champion': {'n': 6, 'wins': 2, 'net': -26.0, 'hit_rate': 0.3333333333333333}, 'state_accurate': {'n': 2, 'wins': 1, 'net': 6.399999999999999, 'hit_rate': 0.5}, 'orb_accurate': {'n': 1, 'wins': 1, 'net': 19.0, 'hit_rate': 1.0}}` |
| proven+ORB | `{'proven_100': {'n': 3, 'wins': 3, 'net': 87.0, 'hit_rate': 1.0}, 'orb_accurate': {'n': 2, 'wins': 1, 'net': 2.4499999999999993, 'hit_rate': 0.5}}` |

## Trade log (ranked)

| Date | Desk | Side | Entry t | Entry | Stop | Target | Exit | Reason | Pts | Net |
|---|---|---|---|---:|---:|---:|---|---|---:|---:|
| 2026-10-21 | proven_100 | sell | 10:05 | 22989.05 | 23019.05 | 22959.05 | 10:08 | target | 30.00 | 29.00 |
| 2026-10-23 | champion | sell | 09:35 | 22683.70 | 22703.70 | 22653.70 | 09:40 | stop | -20.00 | -21.00 |
| 2026-10-27 | champion | buy | 09:35 | 22717.50 | 22697.50 | 22747.50 | 09:40 | target | 30.00 | 29.00 |
| 2026-10-28 | proven_100 | buy | 12:35 | 22665.75 | 22635.75 | 22695.75 | 12:44 | target | 30.00 | 29.00 |
| 2026-10-29 | proven_100 | buy | 09:50 | 22733.15 | 22703.15 | 22763.15 | 09:53 | target | 30.00 | 29.00 |
| 2026-10-30 | champion | buy | 11:05 | 22990.30 | 22970.30 | 23020.30 | 11:13 | target | 30.00 | 29.00 |
| 2026-11-05 | champion | buy | 09:50 | 24413.05 | 24393.05 | 24443.05 | 10:02 | stop | -20.00 | -21.00 |
| 2026-11-13 | champion | buy | 10:35 | 25228.05 | 25208.05 | 25258.05 | 10:36 | stop | -20.00 | -21.00 |
| 2026-11-16 | champion | buy | 09:50 | 25315.20 | 25295.20 | 25345.20 | 10:02 | stop | -20.00 | -21.00 |
| 2026-11-17 | orb_accurate | buy | 09:50 | 25361.80 | 25346.05 | 25381.80 | 09:55 | target | 20.00 | 19.00 |

## Readout

- Ranked book is the live priority stack in one ticket/day.
- Champion was the drag on this window; **proven+ORB** is the accuracy lift to check.
- Desk-4 fills (trend / state) only help if they fire on silent days without wrecking hit rate.
- Artifacts: `NIFTY_RANKED_DESK_GUIDE_30D_CALLS.csv` · `NIFTY_RANKED_DESK_GUIDE_30D.json`
