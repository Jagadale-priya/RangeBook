# NIFTY morning strong BUY · accuracy research

Honest path only: **15m thrust → 5m fill at OR+lim · ±30**.
Close-chase OR breaks remain ~30% — excluded.

Gates tested: **660** · hard pass (≥85.0/80.0): **154** · soft pass (≥80.0/80.0): **348**

## Live baseline

- `LIVE_L5_u50_b55_fg` · freeze 84@79.76% · holdout 10@90.0% · catch 42.9% · hard=False soft=False

## Best accurate

- **`L5_u60_b65_t0_11:00_fg1_fb1_mb12`** · freeze 40@90.0% · holdout 5@100.0% · catch 14.3% · hard=True soft=True
- params: `{"lim": 5, "min_up": 60, "body": 0.65, "top": 0.0, "hmin": "09:45", "hmax": "11:00", "prior": 2, "fill_green": true, "forbid_both_sides": true, "max_fill_bars": 12}`

## Best catch among pass gates

- **`L5_u50_b60_t0_11:00_fg1_fb1_mb24`** · catch 42.9% · fz 54@83.33% · ho 9@100.0%
- params: `{"lim": 5, "min_up": 50, "body": 0.6, "top": 0.0, "hmin": "09:45", "hmax": "11:00", "prior": 2, "fill_green": true, "forbid_both_sides": true, "max_fill_bars": 24}`

## Ranking

| gate | freeze | holdout | catch | hard | soft |
|---|---:|---:|---:|---|---|
| `L5_u60_b65_t0_11:00_fg1_fb1_mb12` | 40@90.0 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b65_t70_11:00_fg1_fb1_mb12` | 39@89.74 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b65_t0_11:30_fg1_fb1_mb12` | 47@89.36 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b65_t70_11:30_fg1_fb1_mb12` | 46@89.13 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b60_t0_11:00_fg1_fb1_mb12` | 45@88.89 | 6@100.0 | 21.4% | True | True |
| `L5_u70_b60_t0_11:00_fg1_fb1_mb12` | 36@88.89 | 5@100.0 | 14.3% | True | True |
| `L5_u70_b60_t70_11:00_fg1_fb1_mb12` | 36@88.89 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b60_t70_11:00_fg1_fb1_mb12` | 44@88.64 | 6@100.0 | 21.4% | True | True |
| `L5_u60_b65_t0_11:00_fg1_fb0_mb12` | 43@88.37 | 5@100.0 | 14.3% | True | True |
| `L5_u70_b60_t0_11:30_fg1_fb1_mb12` | 43@88.37 | 5@100.0 | 14.3% | True | True |
| `L5_u70_b60_t70_11:30_fg1_fb1_mb12` | 43@88.37 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b65_t0_11:30_fg1_fb0_mb12` | 51@88.24 | 5@100.0 | 14.3% | True | True |
| `acc_L5_u60_b65_fg_mb12` | 51@88.24 | 5@100.0 | 14.3% | True | True |
| `L5_u55_b65_t0_11:00_fg1_fb1_mb12` | 42@88.1 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b65_t70_11:00_fg1_fb0_mb12` | 42@88.1 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b65_t70_11:30_fg1_fb0_mb12` | 50@88.0 | 5@100.0 | 14.3% | True | True |
| `L5_u55_b65_t70_11:00_fg1_fb1_mb12` | 41@87.8 | 5@100.0 | 14.3% | True | True |
| `acc_L5_u55_b65_fg_fb_t70_mb12` | 41@87.8 | 5@100.0 | 14.3% | True | True |
| `L5_u55_b65_t0_11:30_fg1_fb1_mb12` | 49@87.76 | 5@100.0 | 14.3% | True | True |
| `L5_u60_b55_t70_11:00_fg1_fb1_mb12` | 48@87.5 | 6@100.0 | 21.4% | True | True |
| `L5_u60_b60_t0_11:00_fg1_fb0_mb12` | 48@87.5 | 6@100.0 | 21.4% | True | True |
| `L5_u55_b65_t70_11:30_fg1_fb1_mb12` | 48@87.5 | 5@100.0 | 14.3% | True | True |
| `L5_u70_b55_t70_11:00_fg1_fb1_mb12` | 40@87.5 | 5@100.0 | 14.3% | True | True |
| `L5_u70_b55_t70_11:30_fg1_fb1_mb12` | 48@87.5 | 5@100.0 | 14.3% | True | True |
| `L5_u55_b60_t0_11:00_fg1_fb1_mb12` | 47@87.23 | 6@100.0 | 21.4% | True | True |
| `L5_u60_b60_t70_11:00_fg1_fb0_mb12` | 47@87.23 | 6@100.0 | 21.4% | True | True |
| `L5_u55_b65_t0_11:30_fg1_fb0_mb12` | 54@87.04 | 5@100.0 | 14.3% | True | True |
| `L5_u55_b60_t70_11:00_fg1_fb1_mb12` | 46@86.96 | 6@100.0 | 21.4% | True | True |
| `acc_L5_u60_b65_fg_fb_w60_200_rng25` | 46@86.96 | 6@100.0 | 21.4% | True | True |
| `L5_u50_b70_t0_11:30_fg1_fb1_mb12` | 46@86.96 | 5@100.0 | 14.3% | True | True |

## Holdout calls (best accurate)

- 2026-09-23 sig 11:00 fill 11:05 @ 23419.55 · win · uplift 83.8
- 2026-09-30 sig 10:00 fill 10:05 @ 22741.65 · win · uplift 90.2
- 2026-10-16 sig 10:15 fill 11:10 @ 23081.55 · win · uplift 73.8
- 2026-10-26 sig 09:45 fill 09:50 @ 22529.4 · win · uplift 112.0
- 2026-11-03 sig 10:15 fill 11:15 @ 23633.3 · win · uplift 67.1

## Verdict

- Hard-pass gate exists: prefer **`L5_u60_b65_t0_11:00_fg1_fb1_mb12`** for accuracy before any live retune.

JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\NIFTY_MORNING_STRONG_ACCURATE.json`
