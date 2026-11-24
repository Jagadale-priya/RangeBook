# Phase-1 — LOCKED accurate desks

**Status:** `LOCKED` / `HOLDING` / `not_live`  
**Do not mutate** without `confirm_accurate_desks_3y_match.py` PASS.

## Canonical code (unchanged)

| Item | Path |
|---|---|
| Combined desks API | `prod_live/logic/accurate_desks.py` |
| Stream recipes V1–V5 + wide | `prod_live/logic/acc100_streams.py` |
| Confirm dual TF | `prod_live/logic/confirm_dual_tf.py` |
| 3y match | `prod_live/tests/confirm_accurate_desks_3y_match.py` |
| Research lock | `prod_live/reports/1y/ACC_ALL_DESKS_10Y.md` |
| Tags | `prod_live/config/tags.json` (`ACC_RANGE_*`, `ACC_BAND_*`) |

## Held desks

Nested 100%: `V1 ⊂ V2 ⊂ V3 ⊂ V4 ⊂ V5` — keep all.

Wide ladder: `P92 → P90 → P85 → P85B → P80 → P75` (+ `P80_CAP2`, `P75_CAP2`).

Research window end: `2026-11-13`.

## Relation to this folder

Phase-1 source of truth stays in `logic/`. This folder only **indexes** it next to Phase-2c so both are findable in one place.
