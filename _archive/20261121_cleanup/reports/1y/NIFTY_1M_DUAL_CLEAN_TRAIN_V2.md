# NIFTY 1m dual CLEAN train — RESEARCH ONLY

**Not live. Does not list Calls.**

- Window: `2021-01-01` → `2025-12-30`
- Freeze (train through): `2024-09-10`
- Brackets: ±30 · OR bars: 15 (1m)
- Gate profile: **V2_STRICT**
- Clean gates: `{"min_or_width": 20.0, "max_noise_vs_sl": 1.25, "min_future_bars": 5, "min_entry_mins": 600, "max_entry_mins": 870, "max_or_ext": 0.2, "require_first_break": true, "require_body_align": true, "forbid_both_sides": true}`

## Data

- bars: **461926** · days: **1235**
- coverage: `2021-01-01 09:15:00+05:30` → `2025-12-30 15:29:00+05:30`
- download note: ok
- raw candidates → clean kept: **1759** → **208**
- drop reasons: `{"drop_entry_clock": 1016, "drop_not_first_break": 351, "ok": 208, "drop_chase_ext": 117, "drop_noisy_bar": 65, "drop_body_against": 1, "drop_outcome:same_bar_both": 1}`
- pre drops: `{}`

## Dual heads

- **BUY**: n_train=88 · fit_auc=0.67 · calib_auc=0.5 · flipped=False
- **SELL**: n_train=80 · fit_auc=0.692 · calib_auc=0.5 · flipped=False

## OOS research books (after freeze, day-unique)

| Book | N | Hit% |
|---|---:|---:|
| `CHAMP_FB_P52` | 20 | 55.0 |
| `CHAMP_FB_P55` | 19 | 57.89 |
| `CHAMP_FB_P58` | 16 | 62.5 |
| `CHAMP_FB_P60` | 15 | 60.0 |
| `CHAMP_FB_P62` | 2 | 0.0 |
| `CHAMP_FB_P66` | 1 | 0.0 |
| `BUY_FB_P55` | 10 | 50.0 |
| `SELL_FB_P55` | 9 | 66.67 |
| `ALL_DAY_UNIQUE` | 40 | 67.5 |
| `PROVEN_CLEAN_P58` | 10 | 100.0 |
| `PROVEN_CLEAN_P62` | 2 | 0.0 |
| `PROVEN_CLEAN_P66` | 1 | 0.0 |

OOS scored tickets: **40** · hit 67.5%

## vs V1 (noise removed)

| | V1 | V2 strict |
|---|---:|---:|
| Clean tickets | 1701 | 208 |
| OOS day-unique hit | 55.0% (n=440) | **67.5%** (n=40) |
| Best champ FB | P52 ~53% | P58 **62.5%** (n=16) |
| Proven book | P62 n=6 @100% | P58 **n=10 @100%** |

Noise cuts that moved the needle (no look-ahead): entry after 10:00, first_break only, or_ext≤0.20, body aligned, forbid both-sides, wider OR (≥20), quieter bars (noise_vs_sl≤1.25).

Tradeoff: fewer OOS samples (40 vs 440) — accuracy up, coverage down. Still research-only; not live.

## Policy

- Pack dir: `fno_validate/research/nifty_1m_dual_clean_research_v2`
- Flags: `research_only=true` · `not_live=true`
- Do not import into live_session / fno_ws_rescore without a separate promote plan.
