# NIFTY F&O — accuracy research book

Isolated from live `prod_live/logic` and the Calls board. Goal: **accurate** NIFTY futures calls only.

## Primary book (accurate)

| Priority | Source | Track | Brackets |
|---:|---|---|---|
| 1 | **15m** dual packs | `proven_100` only | ±30 |
| 2 | **10m** dual packs (same live packs on 10m OR-breaks) | `proven_100` only | ±30 |

- **One ticket per session** (15m proven wins; 10m proven only if 15m silent that day).
- **Excluded from primary book:** champion (15m/10m/5m), baseline, ORB fill, P2F/P2G tags.

## Champion improve (separate)

5m and 10m champion hit rates were poor on last-1y caches (~33–42%).  
Research gates live under `logic/champion_improve.py` and `run_champion_improve_1y.py` — **not** merged into the accurate book until freeze/holdout clears.

## Run

```bash
python -u prod_live/research/nifty_fno/run_proven_1y.py
python -u prod_live/research/nifty_fno/run_champion_improve_1y.py
```

Reports: `prod_live/research/nifty_fno/reports/`
