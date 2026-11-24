# All logic levels — KEEP EVERY LEVEL

**Status:** `HELD_COMPLETE` · **Not live** until you promote a channel into Lane A.  
Each research phase is **held separately** — do not discard earlier levels.

| Level | Status | Key V5-family tag | 3y N @ hit | Recipes |
|---|---|---|---|---|
| **Phase-1** | `LOCKED` | `ACC100_MULTI_V5` | 141 @ 100% | `logic/accurate_desks.py` |
| **Phase-2c** | `HELD` | `ACC100_MULTI_V8` | 199 @ 100% | `recipes.json` |
| **Phase-2d** | `HELD` | `ACC100_MULTI_V9` | 216 @ 100% | `phase2d/recipes_research.json` |
| **Phase-2e** | `HELD` | `ACC100_MULTI_V10` | 241 @ 100% | `phase2e/recipes_research.json` |
| **Phase-2f** | `HELD` | `ACC100_MULTI_V11` | 291 @ 100% | `phase2f/recipes_research.json` |

Nested volume ladders at each level: V5-family → P92 → P90 → P85 → P85B → P80 → P75 (+ CAP2 where present).

Per-desk logic + **accurate_tag**: **`DESKS.md`**.

## Live vs holding

| Lane | Role |
|---|---|
| **LIVE** | `STACK_PLUS_CROWN_HTF_CAP2` + `AGREE_15M_ANY5` (unchanged) |
| **HOLDING accurate** | These levels — parallel accurate channels with `accuracy_range` / desk tags |

See `LIVE_CHANNELS.md` for which holding tags to stamp when live calls are issued.
