# NIFTY accurate profiles · baseline vs accurate

**Source:** `kite` 5m · cost 1.0

## Profiles

- ORB `accurate`: width 40–100 · entry within **5** pts of ORH/ORL
- Trend `accurate`: **SELL only** · signal before 12:00 · risk≤30 · entry_ext≤15 · chase≤20

| Family | Profile | Window | N | Hit | AvgW | AvgL | Ratio | Net |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| orb | baseline | 10 | 0 | n/a | n/a | n/a | n/a | 0.00 |
| orb | accurate | 10 | 2 | 50.0% | 19.00 | -16.55 | 1.15 | 2.45 |
| trend | baseline | 10 | 2 | 50.0% | 86.00 | -28.85 | 2.98 | 57.15 |
| trend | accurate | 10 | 0 | n/a | n/a | n/a | n/a | 0.00 |
| orb | baseline | 40 | 9 | 66.7% | 19.00 | -20.77 | 0.91 | 51.70 |
| orb | accurate | 40 | 9 | 66.7% | 19.00 | -15.15 | 1.25 | 68.55 |
| trend | baseline | 40 | 9 | 55.6% | 35.05 | -20.19 | 1.74 | 94.50 |
| trend | accurate | 40 | 2 | 100.0% | 37.00 | n/a | n/a | 74.00 |
| orb | baseline | 60 | 21 | 52.4% | 17.44 | -18.25 | 0.96 | 9.35 |
| orb | accurate | 60 | 24 | 58.3% | 17.77 | -14.95 | 1.19 | 99.40 |
| trend | baseline | 60 | 20 | 40.0% | 27.49 | -12.55 | 2.19 | 81.90 |
| trend | accurate | 60 | 8 | 62.5% | 23.73 | -7.23 | 3.28 | 96.95 |
| orb | baseline | 80 | 31 | 51.6% | 16.99 | -17.07 | 0.99 | 15.70 |
| orb | accurate | 80 | 33 | 54.5% | 18.05 | -14.03 | 1.29 | 114.40 |
| trend | baseline | 80 | 27 | 37.0% | 27.57 | -9.92 | 2.78 | 117.00 |
| trend | accurate | 80 | 11 | 45.5% | 23.73 | -5.45 | 4.35 | 85.95 |

## Verdict

- Prefer **ORB accurate** when you want higher hit rate (~60% band on 80d pool with entry_ext≤5).
- Prefer **trend baseline** (or accurate SELL) when you want larger winners; hit stays ~40%.

Reports: `NIFTY_ACCURATE_LOGIC_CANDIDATES.md` · `NIFTY_TREND_ORB_ACCURACY_SEARCH.md`
