# Phase-2H RESEARCH — 5m dual train · last 1 year held out

**Status:** RESEARCH · **not live**
**Model:** 5m dual-train HGB. Train through 2024-09-10. Holdout base hit about 53% BUY / 52% SELL.
**Selection:** filters frozen on 2023-11-16 → 2025-11-14. One call per day.
**Test:** `2025-11-15` → `2026-11-15`. The test year was not used to accept a stream.

| Floor used to build | Pre-year N@hit | Test year N@hit | Streams |
|---:|---|---|---:|
| 90.0 | 65@93.85 | 45@66.67 | 9 |
| 92.0 | 27@96.3 | 16@68.75 | 3 |
| 95.0 | 18@100.0 | 9@100.0 | 2 |

## Verdict

The 5-minute model on its own does not clear 90% on the test year. One call per day at p≥0.60 is 9 calls at 55.56%. The unfiltered 5-minute tickets are 290 calls at 50.69%.

The only frozen book that stayed at or above 90% is the floor-95 path mix (crown 20 and good 40, not the 5-minute head): 9 calls at 100% on 2025-11-15 → 2026-11-15. The larger books fell apart on that year: 45 calls at 66.67% (floor 90) and 16 calls at 68.75% (floor 92). RESEARCH only. Not live.

## Test-year calls — floor 95.0

| Day | HM | Side | Win | p |
|---|---|---|---|---:|
| 2025-12-01 | 11:30 | SELL | W | 0.5608 |
| 2026-02-16 | 11:30 | BUY | W | 0.5545 |
| 2026-03-13 | 11:45 | SELL | W | 0.5542 |
| 2026-05-12 | 12:15 | SELL | W | 0.5685 |
| 2026-06-02 | 11:00 | BUY | W | 0.5574 |
| 2026-06-04 | 11:05 | BUY | W | 0.6151 |
| 2026-06-09 | 11:00 | SELL | W | 0.5746 |
| 2026-09-24 | 11:45 | SELL | W | 0.5657 |
| 2026-11-06 | 11:20 | BUY | W | 0.5551 |

Elapsed 9.1s
