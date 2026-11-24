# Holding accurate — complete logic (P1 → P2F)

**Not live.** Live sessions stay on Lane A (`FINAL_LOGIC.md`).

**Status:** `HELD_COMPLETE` · every level kept · latest expand = **Phase-2f**.

| Doc | Role |
|---|---|
| **`DESKS.md`** | Logic + **accurate_tag** for each desk |
| **`desks_held.json`** | Machine registry (60 desks) |
| **`LIVE_CHANNELS.md`** | Stamp guide for live sessions |
| **`LOGIC.md` / `LEVELS.md`** | Level index |
| **`registry.py`** | `DESKS_HELD` · `stamp_fields_for()` · stream tags |

```
holding_accurate/
├── DESKS.md / desks_held.json / registry.py
├── LOGIC.md · LEVELS.md · LIVE_CHANNELS.md · README.md
├── recipes.json                 ← P2c held
├── phase1/PHASE1_LOGIC.md
├── phase2c/ … phase2f/          ← expand recipes (all HELD)
└── reports/                     ← 1y / priority reports
```

## Rule

- **Keep every level** (P1 → P2f). Do not discard earlier logic when a new phase lands.
- Phase-1 expected 3y numbers do **not** change without confirm PASS.
- Accurate tags live in `config/tags.json` (synced from `desks_held.json`).
- Rebuild desks doc: `python -u prod_live/holding_accurate/_build_held_desks.py`
