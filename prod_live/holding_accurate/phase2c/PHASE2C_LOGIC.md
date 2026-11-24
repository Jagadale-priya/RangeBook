# Phase-2c — HELD candidates (same accuracy, more calls)

**Status:** `HELD` / `HOLDING` / `not_live`  
**Does not change Phase-1.** Live unchanged.

## What is held

For each Phase-1 expand target, Phase-2c greedily unions mined path-true streams that keep the Phase-1 3y hit floor (100% desks stay perfect on 3y+5y+1y).

Recipes live in `../recipes.json` → `candidates[*].stream_tags_held` (P2 + P2b + P2c-new, ordered).

Replay: `builders.py` → remine by tag → union onto Phase-1 desk.

## Held numbers (3y, end 2026-11-13)

| Candidate | Floor | N | Hit | Streams held |
|---|---:|---:|---:|---:|
| `ACC100_MULTI_V8` | 100% | 199 | 100% | 52 |
| `ACC_WIDE_P92_P2C` | 99.24% | 203 | 99.51% | 52 |
| `ACC_WIDE_P90_P2C` | 95.4% | 237 | 95.78% | 49 |
| `ACC_WIDE_P85_P2C` | 89.69% | 293 | 89.76% | 48 |
| `ACC_WIDE_P85B_P2C` | 88.4% | 303 | 88.45% | 40 |
| `ACC_WIDE_P80_P2C` | 84.72% | 341 | 84.75% | 26 |
| `ACC_WIDE_P75_P2C` | 82.71% | 372 | 82.80% | 21 |
| `ACC100_MULTI_V5_CAP2_P2C` | 100% | 256 | 100% | 51 |
| `ACC_WIDE_P92_CAP2_P2C` | 99.24% | 261 | 99.62% | 51 |
| `ACC_WIDE_P90_CAP2_P2C` | 95.4% | 309 | 96.12% | 47 |

## Source reports

- `reports/1y/ACC_PHASE2_SAME_ACC_MORE.md`
- `reports/1y/ACC_PHASE2B_DEEPER_MORE.md`
- `reports/1y/ACC_PHASE2C_EVEN_MORE.md`

## Promote

Only when asked: package into `logic/acc100_streams.py` + `DESK_REGISTRY`, extend 3y confirm, keep Phase-1 nested.
