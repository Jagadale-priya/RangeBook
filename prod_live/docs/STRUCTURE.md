# Folder structure

```
prod_live/
├── ALL_LOGIC.md           # BOTH lanes index (LIVE + HOLDING, kept separate)
├── FINAL_LOGIC.md         # Lane A — LIVE
├── HOLDING_LOGIC.md       # Lane B overview
├── ACCURATE_LOGIC.md      # Lane B accurate desks + ACC_RANGE_* tags
├── HOLDING_DESIGN.md
├── DESIGN.md
├── MANIFEST.json
├── README.md
├── holding_accurate/      # Phase-1 + Phase-2c HELD together (not live)
│   ├── LOGIC.md / recipes.json / registry.py
│   ├── phase1/  PHASE1_LOGIC.md
│   └── phase2c/ PHASE2C_LOGIC.md + builders.py
├── config/
│   ├── tags.json          # lane + ACC_RANGE_* + ACC_BAND_*
│   └── live.env.example
├── logic/
│   ├── stack.py / agree_accurate.py / htf_active.py   # LIVE
│   ├── accurate_desks.py  # HOLDING combined accurate desks API
│   ├── acc100_streams.py / confirm_dual_tf.py / empty_fill.py
├── models/nifty/…
├── reports/1y/            # confirmation + ACC reports
├── adapters/
└── docs/
    └── STRUCTURE.md
```

- **LIVE sessions** → Lane A only (`FINAL_LOGIC.md`)
- **Holding research** → Lane B only (`HOLDING_LOGIC.md`)
- **Phase-1 + Phase-2c held** → `holding_accurate/`
- Master map → **`ALL_LOGIC.md`**
