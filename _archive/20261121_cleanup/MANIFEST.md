# Archive · 2026-11-21 cleanup

Moved unused research / analysis / mockups / research-only logic.
Live runtime kept in place (app, dashboard/index.html, adapters, live logic, live held books).


## Mockups + reports

MOVED dashboard\ui-mock.html -> dashboard_mock/
MOVED dashboard\design-options.html -> dashboard_mock/
MOVED dashboard\scalper-call-display-mockup.html -> dashboard_mock/
MOVED prod_live/reports/* (626 files) -> reports/ (now 626)


## Builders + tests

MOVED prod_live/tests/builders/* (351 py; 435 files total) -> builders/
MOVED prod_live/tests/confirm_accurate_desks_3y_match.py -> tests_root/
MOVED prod_live/tests/confirm_champ_plus_live_engine.py -> tests_root/
MOVED prod_live/tests/confirm_final_bn_3books.py -> tests_root/
MOVED prod_live/tests/confirm_final_hold_1y_match.py -> tests_root/
MOVED prod_live/tests/confirm_final_nifty_3books.py -> tests_root/
MOVED prod_live/tests/confirm_final_sensex_3books.py -> tests_root/
MOVED prod_live/tests/confirm_morning_context_1y_match.py -> tests_root/
MOVED prod_live/tests/confirm_p2f_cap2_live_1y.py -> tests_root/
MOVED prod_live/tests/confirm_p2f_day_live_1y.py -> tests_root/
MOVED prod_live/tests/__init__.py -> tests_root/
WROTE prod_live/tests/builders/README.md


## Research-only logic

MOVED prod_live/logic/nifty_state_conditional.py
MOVED prod_live/logic/nifty_orb30_vwap_fut.py
MOVED prod_live/logic/nifty_trend_stay.py
MOVED prod_live/logic/nifty_minute_guide.py
MOVED prod_live/logic/nifty_ranked_desk_guide.py
MOVED prod_live/logic/pa_cbrt_live.py
MOVED prod_live/logic/agree_accurate.py
MOVED prod_live/logic/htf_active.py
MOVED prod_live/logic/stack.py
MOVED prod_live/logic/confirm_dual_tf.py
MOVED prod_live/logic/acc100_streams.py
MOVED prod_live/logic/empty_fill.py
MOVED prod_live/logic/accurate_desks.py
MOVED prod_live/logic/combined_live_book_bn.py
MOVED prod_live/logic/combined_live_book_sensex.py


## Holdings junk

MOVED holding_accurate/acc100_last20_locks.json
MOVED holding_accurate/DESKS.md
MOVED holding_accurate/LEVELS.md
MOVED holding_accurate/LIVE_CHANNELS.md
MOVED holding_accurate/LOGIC.md
MOVED holding_accurate/OVERLAY_100.md
MOVED holding_accurate/README.md
MOVED holding_accurate/desks_held.json
MOVED holding_accurate/_analyze_nov2026.py
MOVED holding_accurate/_build_held_desks.py
MOVED holding_accurate/_dump_desks.py
MOVED holding_accurate/_extract_phase2d_recipes.py
MOVED holding_accurate/_extract_phase2f_recipes.py
MOVED holding_accurate/_extract_recipes.py
MOVED holding_accurate/_nov_deep_from_tapes.py
MOVED holding_accurate/_promote_p2f_cap2_live.py
MOVED holding_accurate/_promote_p2f_day_live.py
MOVED holding_accurate/_salvage_phase2e.py
MOVED holding_accurate/_show_oct_nov_calls.py
MOVED holding_accurate/_sync_tags_json.py
MOVED holding_accurate/phase1
MOVED holding_accurate/phase2d
MOVED holding_accurate/phase2e
MOVED holding_accurate/reports
MOVED champion_plus/live_session_calls.json.bak_1m_cap6_replay
MOVED champion_plus/live_session_calls.json.bak_causal_cap6
MOVED champion_plus/live_session_calls.json.bak_kite_monday_replay
MOVED champion_plus/monthly_todate_calls.json
MOVED champion_plus/push4_calls_1y.json
MOVED champion_plus/push5_calls_1y.json
MOVED champion_plus/recipes_research.json
MOVED champion_plus/t30_sl20_calls.json
MOVED champion_plus/t30_sl20_more_calls.json
MOVED champion_plus/t30_sl30_3y_calls.json
MOVED champion_plus/t30_sl30_5y_calls_cap4_backup.json
MOVED champion_plus/t30_sl30_5y_calls_pre_causal_cap6.json
MOVED sensex_final/champ_plus_t100_sl100_calls.json
MOVED sensex_final/champ_plus_t100_sl100_calls.json.bak_pre_t50
MOVED sensex_final/champ_plus_t100_sl100_calls.json.bak_pre_v2
MOVED sensex_final/champ_plus_t120_sl120_calls.json
MOVED sensex_final/champ_plus_t120_sl120_calls.json.bak_pre_t50
MOVED sensex_final/champ_plus_t50_sl50_volume_research_calls.json
MOVED sensex_final/champ_plus_t80_sl80_calls.json
MOVED sensex_final/champ_plus_t80_sl80_calls.json.bak_pre_t50
MOVED sensex_final/live_session_calls.json.bak_2m_replay


## Summary counts

- `builders/`: **435** files
- `reports/`: **626** files
- `dashboard_mock/`: **3** files
- `logic/`: **15** files
- `holding_accurate/`: **60** files
- `tests_root/`: **10** files

## Smoke

`python -u prod_live/tests/_smoke_live_after_archive.py` → 8/8 OK (champ 2105, sensex 2293, bn 38, p2f/p2g recipes load).

## Restore

Move any path back from this folder to its original location under the repo root.
