# NIFTY + SENSEX · ACC100 locks · 1y / 3y / 5y confirm

**Generated:** `2026-11-21T18:55:45` · end `2026-11-21`

Re-settled on 5m tape (first touch SL vs T1). Gates from `acc100_last20_locks.json`.

## NIFTY (±30)

ACC100 desk: `NIFTY_ACC100_DENSE_WF`
Gate: `{'cap': 1, 'pmin': 0.55, 'tracks': ['champion', 'good_prod2', 'proven_research'], 'hm_lo': '10:00', 'hm_hi': '14:00', 'max_or_ext': None, 'first_only': False, 'sides': None, 'buy_p': None, 'sell_p': None}`

| Window | ACC100 N | Hit | W/L | Pts | Cap6 N | Cap6 Hit |
|---|---:|---:|---|---:|---:|---:|
| 6m | 19 | **100.0** | 19/0 | 570.0 | 236 | 75.42 |
| 1y | 37 | **100.0** | 37/0 | 1110.0 | 466 | 75.97 |
| 3y | 94 | **97.87** | 92/2 | 2700.0 | 1369 | 79.11 |
| 5y | 138 | **93.48** | 129/9 | 3600.0 | 2099 | 79.18 |

## SENSEX (±50)

ACC100 desk: `SENSEX_ACC100_DENSE_WF`
Gate: `{'cap': 1, 'pmin': 0.5, 'tracks': None, 'hm_lo': '10:00', 'hm_hi': '14:00', 'max_or_ext': None, 'first_only': True, 'sides': None, 'buy_p': None, 'sell_p': None}`

| Window | ACC100 N | Hit | W/L | Pts | T50 N | T50 Hit |
|---|---:|---:|---|---:|---:|---:|
| 6m | 22 | **100.0** | 22/0 | 1100.0 | 42 | 71.43 |
| 1y | 48 | **93.75** | 45/3 | 2100.0 | 61 | 68.85 |
| 3y | 116 | **86.21** | 100/16 | 4200.0 | 164 | 54.27 |
| 5y | 116 | **86.21** | 100/16 | 4200.0 | 164 | 54.27 |

## Read

- If ACC100 stays **100%** on 1y/3y/5y → lock is robust for live.
- If it slips on longer windows → keep as 6m-accurate sparse desk; do not claim multi-year 100%.
- Volume desks (Cap6 / T50) remain the denser lower-accuracy book.

JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\NIFTY_SENSEX_ACC100_1_3_5Y.json`
