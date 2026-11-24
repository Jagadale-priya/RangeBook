# prod_live — NIFTY desk (two separate lanes)

**Master map:** [`ALL_LOGIC.md`](ALL_LOGIC.md)

| Lane | Status | Doc |
|---|---|---|
| **A LIVE** | FINALIZED — live sessions | `FINAL_LOGIC.md` |
| **B HOLDING** | HOLDING — not live | `HOLDING_LOGIC.md` |

Keep both. Do not merge into one session book until you promote.

Research / experiments stay in `FINAL LOGIC/`. **Prod truth lives here.**

## Structure

```
prod_live/
  ALL_LOGIC.md              ← both lanes index
  FINAL_LOGIC.md            ← Lane A LIVE
  HOLDING_LOGIC.md          ← Lane B HOLDING
  MANIFEST.json             ← lanes + stats
  config/tags.json          ← every tag has lane=LIVE|HOLDING
  logic/
    stack.py / agree_accurate.py / htf_active.py   ← LIVE
    empty_fill.py / confirm_dual_tf.py / acc100_streams.py  ← HOLDING
  models/nifty/…
  reports/1y/
```

## Lane A — what live sessions use

| Tag | Role | 1y hit |
|---|---|---:|
| `STACK_PLUS_CROWN_HTF_CAP2` | Volume calls | 75.11% |
| `AGREE_15M_ANY5` | Accurate stamp (+ rare extras) | 90.74% on stack |
| `STACK_PLUS_AGREE_15M_ANY5` | Desk = stack + agree | combo |

## Quick start

1. Read `DESIGN.md` and `FINAL_LOGIC.md`.
2. Confirm models under `models/nifty/` (`models/README_MODELS.md`).
3. Check 1y monthly: `reports/1y/LIVE_FINAL_1Y_MONTHS_ACCURATE.md`.
4. Cut over when ready: `adapters/README.md` + `config/live.env.example`.

## Lane B — holding (separate)

Empty fill · ACC100 V1–V5 · wide / cap2 — see `HOLDING_LOGIC.md` / `ALL_LOGIC.md`.  
**Not wired to live sessions.**

## Live book notes

- NSE mid gate — OFF
- Standalone 15m classic channel — OFF (15m enters only as `GOOD_PROD2` inside stack / agree)
