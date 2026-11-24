# NIFTY 1m dual CLEAN train — RESEARCH ONLY

**Not live. Does not list Calls.**

- Window: `2021-01-01` → `2025-12-30`
- Freeze (train through): `2024-09-10`
- Brackets: ±30 · OR bars: 15 (1m)
- Clean gates: decisive T1/SL only · thin-OR / noisy-bar / chase / clock filters

## Data

- bars: **461926** · days: **1235**
- coverage: `2021-01-01 09:15:00+05:30` → `2025-12-30 15:29:00+05:30`
- download note: ok
- raw candidates → clean kept: **1759** → **1701**
- drop reasons: `{"ok": 1701, "drop_entry_clock": 48, "drop_chase_ext": 2, "drop_noisy_bar": 7, "drop_outcome:same_bar_both": 1}`

## Dual heads

- **BUY**: n_train=615 · fit_auc=0.696 · calib_auc=0.574 · flipped=False
- **SELL**: n_train=646 · fit_auc=0.683 · calib_auc=0.535 · flipped=False

## OOS research books (after freeze, day-unique)

| Book | N | Hit% |
|---|---:|---:|
| `CHAMP_FB_P52` | 102 | 52.94 |
| `CHAMP_FB_P55` | 67 | 52.24 |
| `CHAMP_FB_P58` | 55 | 50.91 |
| `CHAMP_FB_P60` | 34 | 50.0 |
| `BUY_FB_P55` | 56 | 51.79 |
| `SELL_FB_P55` | 11 | 54.55 |
| `PROVEN_CLEAN_P62` | 6 | 100.0 |

OOS scored tickets: **440** · hit 55.0%

## Policy

- Pack dir: `stock_signal_data/fno_validate/research/nifty_1m_dual_clean_research/`
- Flags: `research_only=true` · `not_live=true`
- Do not import into live_session / fno_ws_rescore without a separate promote plan.
