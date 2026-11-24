# Phase-2f — day desks PROMOTED to LIVE

**Day mode (1 call/day):** `PROMOTED` → `logic/p2f_day_live.py`.  
**Cap2 mode:** `PROMOTED` → `logic/p2f_cap2_live.py`.  
**Does not change Phase-1 recipes.** Volume stack golden unchanged.

## What is held / promoted

Seeds from Phase-2e. New axes: **micro-bands · weekday · mid pick · triple-CF**.  
Greedy union of path-true streams onto each Phase-1 desk while keeping that desk’s 3y hit floor (**hard gate**).

Recipes: `recipes_research.json` → `candidates[*].stream_tags_research`  
Accurate tags + stamps: `../DESKS.md` · `../desks_held.json` · `../LIVE_CHANNELS.md`

## Key accurate_tags

| accurate_tag | Floor | Mode | 3y | Live |
|---|---:|---|---|---|
| `ACC100_MULTI_V11` | 100% | day | 291 @ 100% | **PROMOTED** |
| `ACC_WIDE_P92_P2F` | 99.24% | day | 292 @ 99.66% | **PROMOTED** |
| `ACC_WIDE_P90_P2F` | 95.4% | day | 303 @ 96.70% | **PROMOTED** |
| `ACC_WIDE_P85_P2F` | 89.69% | day | 326 @ 89.88% | **PROMOTED** |
| `ACC_WIDE_P85B_P2F` | 88.4% | day | 342 @ 88.60% | **PROMOTED** |
| `ACC_WIDE_P80_P2F` | 84.72% | day | 375 @ 84.80% | **PROMOTED** |
| `ACC_WIDE_P75_P2F` | 82.71% | day | 386 @ 82.90% | **PROMOTED** |
| `ACC100_MULTI_V5_CAP2_P2F` | 100% | cap2 | 417 @ 100% | **PROMOTED** |
| `ACC_WIDE_P92_CAP2_P2F` | 99.24% | cap2 | 418 @ 99.76% | **PROMOTED** |
| `ACC_WIDE_P90_CAP2_P2F` | 95.4% | cap2 | 434 @ 97.24% | **PROMOTED** |
| `ACC_WIDE_P85_CAP2_P2F` | 89.69% | cap2 | 472 @ 89.83% | **PROMOTED** |

Report: `reports/1y/ACC_PHASE2F_KEEP_PUSHING.md`  
Live confirm day: `tests/confirm_p2f_day_live_1y.py` · Cap2: `tests/confirm_p2f_cap2_live_1y.py`
