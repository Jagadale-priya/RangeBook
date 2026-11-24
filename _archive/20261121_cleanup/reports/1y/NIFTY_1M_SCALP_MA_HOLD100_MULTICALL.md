# HELD multi-call vs 1/day — last 3m `2026-08-17`→`2026-11-16`

Same gates/exit (DI+hard34+VWAP · EMA34 trail · T1=12). Only pacing changes.

| Pace | Calls | Hit% | Days | Cover | cpd |
|---|---:|---:|---:|---:|---:|
| 1/day (first only) | 63 | 84.13% | 63 | 100.0% | 1.0 |
| multi gap≥15m | 814 | 60.44% | 63 | 100.0% | 12.921 |
| multi gap≥5m | 1726 | 59.21% | 63 | 100.0% | 27.397 |
| multi gap≥1m | 4332 | 59.97% | 63 | 100.0% | 68.762 |

## Read
- **Yes, multi-call works mechanically** — same gates fire many times/day.
- Hit% usually **falls** vs 1/day because extra signals add more MA-flip losses.
- Use a **time gap** (e.g. 15–30m) if you want more calls without stacking noise.
