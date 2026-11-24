# Adapters — wire existing live code to `prod_live`

**Current state:** live still loads packs from `stock_signal_data/...` via `fno_stacked_calls.py`, `fno_dual_score.py`, `fno_5m_crown.py`.  
**This package** is the finalized copy + logic. Cut over is a deliberate step (does not happen by creating this folder alone).

## Recommended cutover order

1. Keep `ENABLE_STACKED_CALLS=1` (already matches volume desk).
2. Point crown pack path → `prod_live/models/nifty/crown/fno_NIFTY_crown_5m.pkl`.
3. Point prod2 pack path → `prod_live/models/nifty/prod2_15m/fno_NIFTY.pkl`.
4. Point dual research packs dir → `prod_live/models/nifty/dual/`.
5. Add accurate stamp after stack pick:
   - Import `prod_live.logic.agree_accurate` + `stamp_accurate`
   - When listing a Call, set `accurate_tag` if key matches agree entry
6. **P2F day + Cap2 LIVE accurate** (promoted):
   - `prod_live.logic.p2f_day_live` / `p2f_cap2_live`
   - Session annotate: `app/fno/fno_p2f_live.py` (`ENABLE_P2F_LIVE_ACCURATE=1`)
   - Do **not** merge into volume stack selection
   - Confirm day: `python -u prod_live/tests/confirm_p2f_day_live_1y.py`
   - Confirm Cap2: `python -u prod_live/tests/confirm_p2f_cap2_live_1y.py`
7. Re-run volume golden: `python -u prod_live/tests/confirm_final_hold_1y_match.py`

## Do not

- Retrain packs inside `prod_live/models` in place
- Enable daily fill / 15m classic / NSE mid without a new finalized tag
- Change champion floors without bumping `MANIFEST.json` version

## Mapping (today → prod_live)

| Live module | Model it needs | prod_live path |
|---|---|---|
| Pre-dual / good | `fno_NIFTY.pkl` | `models/nifty/prod2_15m/` |
| Dual proven/champ | `nifty_side_models/*.pkl` | `models/nifty/dual/` |
| 5m crown | `crown_5m_packs/fno_NIFTY_crown_5m.pkl` | `models/nifty/crown/` |
| Stack union | `fno_stacked_calls.py` | mirror rules in `logic/stack.py` |
