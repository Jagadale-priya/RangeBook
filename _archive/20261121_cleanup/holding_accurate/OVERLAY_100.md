# Overlay indication — REMOVED

The overlay indication / Overlay 100% call channel was retired (inaccurate live fires).

**Desk calls for NIFTY / BANKNIFTY / SENSEX = dual proven → champion only.**

Related stubs (no-op):
- `app/fno/fno_overlay_indication.py` → `evaluate_bar` returns `None`
- `app/fno/fno_ws_rescore.py` → `attach_overlay_indication` empty
- `app/legacy/overlay_indication_store.py` → `upsert_signal` disabled
- Scalper `overlay_100` mode redirects to Setup A/B
