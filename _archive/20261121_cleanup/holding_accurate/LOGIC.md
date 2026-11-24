# Holding accurate logic — ALL LEVELS (P2F day → LIVE)

**Folder:** `prod_live/holding_accurate/`  
**Status:** `HELD_COMPLETE` · **Latest:** Phase-2f · **P2F day desks PROMOTED to LIVE**.  
Cap2 / empty-fill / earlier expand copies remain HOLDING.  
Live map: `FINAL_LOGIC.md` · `LIVE_CHANNELS.md` · `logic/p2f_day_live.py`.

| Doc | Role |
|---|---|
| **`DESKS.md`** | Logic + **multi-tags** (accurate_tag + accuracy_tag) |
| **`desks_held.json`** | Machine registry |
| **`LIVE_CHANNELS.md`** | What to stamp on live calls |
| **`LEVELS.md`** | Keep-all index |
| **`registry.py`** | Load desks / stamp helpers |

## Keep every level

| Level | Status | V5-family tag | 3y @ hit | Recipes |
|---|---|---|---|---|
| Phase-1 | `LOCKED` | `ACC100_MULTI_V5` | 141 @ 100% | `../logic/accurate_desks.py` |
| Phase-2c | `HELD` | `ACC100_MULTI_V8` | 199 @ 100% | `recipes.json` |
| Phase-2d | `HELD` | `ACC100_MULTI_V9` | 216 @ 100% | `phase2d/recipes_research.json` |
| Phase-2e | `HELD` | `ACC100_MULTI_V10` | 241 @ 100% | `phase2e/recipes_research.json` |
| Phase-2f | `HELD` | `ACC100_MULTI_V11` | 291 @ 100% | `phase2f/recipes_research.json` |

Each later level = earlier desk ∪ more stream tags at the **same accuracy floor**.

## Cap2 @ 100% (V5 family)

| Level | Tag | 3y N |
|---|---|---:|
| P2c | `ACC100_MULTI_V5_CAP2_P2C` | 256 |
| P2d | `…_P2D` | 281 |
| P2e | `…_P2E` | 325 |
| **P2f** | `ACC100_MULTI_V5_CAP2_P2F` | **417** |

## Code

| Module | Role |
|---|---|
| `rebuild_streams.py` | Rebuild path rows from stream tags |
| `replay.py` | Union recipes onto Phase-1 desks |
| `phase2c/builders.py` | Cap2 / day merge helpers |
| `registry.py` | Full held desk + accurate_tag API |
