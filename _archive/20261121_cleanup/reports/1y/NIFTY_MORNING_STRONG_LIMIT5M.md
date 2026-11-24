# NIFTY morning strong BUY · 15m thrust → 5m OR+lim fill

Honest fills only (limit after signal). Brackets ±30.

**Live lock:** `L5_u50_b55_fg` · freeze 84@79.76% · holdout 10@90.0% · strong catch 42.9% · soft=True  
(Chosen over pure max-freeze `L5_u60_b65` for better strong-day catch at still ~80/90 accuracy.)

Params: `{"lim": 5, "min_up": 50, "body": 0.55, "fill_green": true, "hmin": "09:45", "hmax": "11:30", "prior": 2, "fill_max": "13:00"}`

Module: `app/fno/nifty_morning_strong_thrust.py` · flag `ENABLE_NIFTY_MORNING_STRONG_THRUST=1`

## Top gates

| gate | freeze | holdout | catch | pass | soft |
|---|---:|---:|---:|---|---|
| `L5_u60_b65_t0_11:30` | 63@79.37 | 7@100.0 | 28.6% | False | True |
| `L5_u60_b65_t70_11:30` | 62@79.03 | 7@100.0 | 28.6% | False | True |
| `L5_u55_b65_t0_11:30` | 66@78.79 | 7@100.0 | 28.6% | False | True |
| `L5_u50_b65_t0_11:30` | 70@78.57 | 8@100.0 | 35.7% | False | True |
| `L5_u55_b65_t70_11:30` | 65@78.46 | 7@100.0 | 28.6% | False | True |
| `L5_u60_b65_t0_12:00` | 65@78.46 | 7@100.0 | 28.6% | False | True |
| `L5_u50_b65_t70_11:30` | 69@78.26 | 8@100.0 | 35.7% | False | True |
| `L5_u50_b65_t70` | 69@78.26 | 8@100.0 | 35.7% | False | True |
| `L5_u60_b65_t70_12:00` | 64@78.12 | 7@100.0 | 28.6% | False | True |
| `L5_u50_b65_t0_12:00` | 73@78.08 | 8@100.0 | 35.7% | False | True |
| `L5_u55_b65_t0_12:00` | 68@77.94 | 7@100.0 | 28.6% | False | True |
| `L5_u50_b65_t70_12:00` | 72@77.78 | 8@100.0 | 35.7% | False | True |
| `L5_u55_b65_t70_12:00` | 67@77.61 | 7@100.0 | 28.6% | False | True |
| `L5_u50_b55_t70_12:00` | 89@77.53 | 9@100.0 | 42.9% | False | True |
| `L5_u60_b60_t0_11:30` | 70@77.14 | 8@100.0 | 35.7% | False | True |
| `L5_u50_b55_t70_11:30` | 83@77.11 | 9@100.0 | 42.9% | False | True |
| `L5_u60_b60_t70_11:30` | 69@76.81 | 8@100.0 | 35.7% | False | True |
| `L5_u55_b60_t0_11:30` | 73@76.71 | 8@100.0 | 35.7% | False | True |
| `L5_u60_b60_t0_12:00` | 73@76.71 | 8@100.0 | 35.7% | False | True |
| `L5_u55_b60` | 73@76.71 | 8@100.0 | 35.7% | False | True |

## Holdout calls (selected)

- 2026-09-23 sig 11:00 fill 11:05 @ 23419.55 · win · uplift 83.8
- 2026-09-30 sig 10:00 fill 10:05 @ 22741.65 · win · uplift 90.2
- 2026-10-13 sig 09:45 fill 11:25 @ 22483.2 · win · uplift 203.4
- 2026-10-16 sig 10:15 fill 10:50 @ 23081.55 · win · uplift 73.8
- 2026-10-26 sig 09:45 fill 09:50 @ 22529.4 · win · uplift 112.0
- 2026-11-02 sig 10:30 fill 11:45 @ 23297.55 · win · uplift 126.2
- 2026-11-03 sig 10:15 fill 11:05 @ 23633.3 · win · uplift 67.1

JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\NIFTY_MORNING_STRONG_LIMIT5M.json`
