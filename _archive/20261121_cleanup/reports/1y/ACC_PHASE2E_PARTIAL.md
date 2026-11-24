# Phase-2e — PARTIAL (stopped mid-run)

**Status:** research incomplete — process stopped during `P75 CAP2` (before day_side / JSON write).  
**Phase-1 LOCKED · Phase-2c HELD** unchanged in `holding_accurate/`.

Mined: alt ~1.6M eval → 19 003 unique · +293 P2d seeds rebuilt (0 fail) · combined tags 19 296.

## Day-dedupe (completed) vs held

| Desk | Floor | **P1 held** | **P2c held** | P2d | **P2e partial** | Hit P2e | Δ vs P1 | Δ vs P2c | Δ vs P2d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V5 → V10 | 100% | 141 | 199 | 216 | **241** | **100%** | +100 | +42 | +25 |
| P92 | 99.24% | 131 | 203 | 220 | **243** | 99.59% | +112 | +40 | +23 |
| P90 | 95.4% | 174 | 237 | 253 | **274** | 96.35% | +100 | +37 | +21 |
| P85 | 89.69% | 223 | 293 | 305 | **317** | 89.91% | +94 | +24 | +12 |
| P85B | 88.4% | 250 | 303 | 314 | **329** | 88.45% | +79 | +26 | +15 |
| P80 | 84.72% | 301 | 341 | 350 | **360** | 84.72% | +59 | +19 | +10 |
| P75 | 82.71% | 347 | 372 | 376 | **382** | 82.72% | +35 | +10 | +6 |

All day desks finished and **stay at/above Phase-1 floors**.

## Cap2 (partial) vs held

| Desk | Floor | P1 | P2c held | P2d | **P2e partial** | Hit | Δ vs P2c | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| V5 CAP2 | 100% | 141 | 256 | 281 | **325** | **100%** | +69 | done |
| P92 CAP2 | 99.24% | 131 | 261 | 286 | **327** | 99.69% | +66 | done |
| P90 CAP2 | 95.4% | 174 | 309 | 334 | **370** | 96.76% | +61 | done |
| P85 CAP2 | 89.69% | 223 | — | 424 | **447** | 89.71% | — | done |
| P85B CAP2 | 88.4% | 250 | — | 435 | **459** | 88.45% | — | done |
| P80 CAP2 | 84.72% | 301 | — | — | **521** | 84.84% | — | done (new) |
| P75 CAP2 | 82.71% | 347 | — | — | **~554** | ~82.85% | — | **STOPPED mid-greedy** |

## Not run

- Day-side desks (V5 / P92 / P90)
- Final JSON/MD write (this file is the salvage report)

## vs held logic (headline)

| Layer | V5 day @ 100% | V5 cap2 @ 100% |
|---|---:|---:|
| Phase-1 **LOCKED** | 141 | — |
| Phase-2c **HELD** | 199 | 256 |
| Phase-2d research | 216 | 281 |
| Phase-2e **partial** | **241** | **325** |

Held recipes in `holding_accurate/` are **not** updated — P2e stays research-only until you promote or re-run to finish.
