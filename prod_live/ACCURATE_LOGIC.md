# Accurate logic (Lane B) — combined file

**Separate from LIVE.** Live sessions stay on `FINAL_LOGIC.md` (`AGREE_15M_ANY5`).

## All levels held — dedicated folder

**`holding_accurate/`** keeps **every** level (not live) · status `HELD_COMPLETE`:

| Path | Role |
|---|---|
| `holding_accurate/DESKS.md` | **Logic + accurate_tag per desk** |
| `holding_accurate/desks_held.json` | Machine registry (60 desks) |
| `holding_accurate/LEVELS.md` | P1→P2f keep-all index |
| `holding_accurate/LOGIC.md` | Combined held logic |
| `holding_accurate/LIVE_CHANNELS.md` | What to stamp on live calls |
| `holding_accurate/recipes.json` | P2c held |
| `holding_accurate/phase2d|2e|2f/` | Later levels **HELD** |
| `reports/1y/ACC_ALL_LEVELS_1Y_TODAY.md` | Full 1y→today comparison |

## Phase-1 — **HELD / LOCKED**

Do not change recipes or expected 3y numbers without a new confirm PASS.

| Item | Path |
|---|---|
| Combined logic | `logic/accurate_desks.py` |
| Stream recipes | `logic/acc100_streams.py` |
| Confirm dual | `logic/confirm_dual_tf.py` |
| 3y match test | `tests/confirm_accurate_desks_3y_match.py` → **PASS** |
| Report | `reports/1y/ACC_ACCURATE_3Y_MATCH.md` |
| Research lock | `reports/1y/ACC_ALL_DESKS_10Y.md` |

## Phase-2c — **HELD** (same accuracy, more calls)

Held in `holding_accurate/` (recipes + docs). Not promoted into `logic/` yet.

| Base | Floor | P1 | P2b | **P2c held** | Δ vs P1 | Candidate |
|---|---:|---:|---:|---:|---:|---|
| V5 | 100% | 141 | 163 | **199 @ 100%** | **+58** | `ACC100_MULTI_V8` |
| P92 | 99.24% | 131 | 171 | **203 @ 99.51%** | **+72** | `P92_P2C` |
| P90 | 95.4% | 174 | 213 | **237 @ 95.78%** | **+63** | `P90_P2C` |
| P85 | 89.69% | 223 | 275 | **293 @ 89.76%** | **+70** | `P85_P2C` |
| P85B | 88.4% | 250 | 281 | **303 @ 88.45%** | **+53** | `P85B_P2C` |
| P80 | 84.72% | 301 | 323 | **341 @ 84.75%** | **+40** | `P80_P2C` |
| P75 | 82.71% | 347 | 360 | **372 @ 82.80%** | **+25** | `P75_P2C` |

Cap2 held: V5 **256 @ 100%** · P92 **261 @ 99.62%** · P90 **309 @ 96.12%**

## Phase-2d — research (more calls, same accuracy)

Continues from held P2c seeds + denser mine. Candidates only (not promoted).  
Builder: `tests/builders/research_acc_phase2d_keep_going.py`  
Report: `reports/1y/ACC_PHASE2D_KEEP_GOING.md` · snapshot `holding_accurate/phase2d/`

| Base | Floor | P1 | P2c | **P2d** | ΔP2c | Candidate |
|---|---:|---:|---:|---:|---:|---|
| V5 | 100% | 141 | 199 | **216 @ 100%** | +17 | `ACC100_MULTI_V9` |
| P92 | 99.24% | 131 | 203 | **220 @ 99.55%** | +17 | `P92_P2D` |
| P90 | 95.4% | 174 | 237 | **253 @ 96.05%** | +16 | `P90_P2D` |
| P85 | 89.69% | 223 | 293 | **305 @ 89.84%** | +12 | `P85_P2D` |
| P85B | 88.4% | 250 | 303 | **314 @ 88.54%** | +11 | `P85B_P2D` |
| P80 | 84.72% | 301 | 341 | **350 @ 84.86%** | +9 | `P80_P2D` |
| P75 | 82.71% | 347 | 372 | **376 @ 82.71%** | +4 | `P75_P2D` |

Cap2 P2d: V5 **281 @ 100%** · P92 **286** · P90 **334** · P85 **424** · P85B **435**

### Phase-2e (partial) → Phase-2f (complete)

| Base | P2c held | P2e | **P2f** | Hit |
|---|---:|---:|---:|---:|
| V5 → **V11** | 199 | 241 | **291 @ 100%** | 100% |
| P92 | 203 | 243 | **292** | 99.66% |
| P90 | 237 | 274 | **303** | 96.70% |
| Cap2 V5 | 256 | 325 | **417 @ 100%** | 100% |

Reports: `ACC_PHASE2E_PARTIAL.md` · **`ACC_PHASE2F_KEEP_PUSHING.md`**  
Snapshots: `holding_accurate/phase2e/` · `holding_accurate/phase2f/`

Prior: `ACC_PHASE2_SAME_ACC_MORE.md` · `ACC_PHASE2B_DEEPER_MORE.md` · `ACC_PHASE2C_EVEN_MORE.md`

## Accuracy-range tags (from 3y → 10y research)

Each desk gets `accuracy_range_tag` = lo–hi hit% across 3y/5y/10y:

| Range tag | Lo–Hi (research) | Desks |
|---|---|---|
| `ACC_RANGE_100_100` | 100–100 | `PROVEN15_PLUS_CONFIRM_T30` |
| `ACC_RANGE_96_100` | 96.62–100 | `ACC100_MULTI_V1` |
| `ACC_RANGE_97_100` | 97.8–100 | V2, V3, V4 |
| `ACC_RANGE_98_100` | 98.17–100 | `ACC100_MULTI_V5` |
| `ACC_RANGE_91_100` | 91.1–99.24 | `ACC_WIDE_P92` |
| `ACC_RANGE_89_96` | 89.88–95.4 | `ACC_WIDE_P90` |
| `ACC_RANGE_84_90` | 84–89.88 | `ACC_WIDE_P85` |
| `ACC_RANGE_81_89` | 81.1–88.4 | `ACC_WIDE_P85B` |
| `ACC_RANGE_76_85` | 76.63–84.72 | `ACC_WIDE_P80` |
| `ACC_RANGE_77_87` | 77.7–86.29 | `ACC_WIDE_P80_CAP2` |
| `ACC_RANGE_75_83` | 75.15–82.71 | `ACC_WIDE_P75` |
| `ACC_RANGE_75_84` | 75.5–83.39 | `ACC_WIDE_P75_CAP2` |

### Bands (filter groups)

| Band | Meaning |
|---|---|
| `A_PERFECT_3Y5Y` | 100% on 3y+5y (V1–V5 + confirm) |
| `B_HIGH_90` | High 90s on 3y (P92, P90) |
| `C_MID_85` | Mid 80s (P85, P85B) |
| `D_VOL_80` | Volume ~80 floor (P80, P80_CAP2) |
| `E_VOL_75` | Widest ~75 floor (P75, P75_CAP2) |

## Row stamps

Every row from `build_all_accurate_desks()` carries:

- `desk_tag` — e.g. `ACC100_MULTI_V5`
- `accuracy_range_tag` — e.g. `ACC_RANGE_98_100`
- `accuracy_band` — e.g. `A_PERFECT_3Y5Y`
- `lane` = `HOLDING`
- `accurate_tag` / `holding_tag` — stream-level tag when present

## Confirm

```bash
python -u prod_live/tests/confirm_accurate_desks_3y_match.py
```

Must **PASS** vs locked 3y N/hit in `ACC_ALL_DESKS_10Y.md`.
