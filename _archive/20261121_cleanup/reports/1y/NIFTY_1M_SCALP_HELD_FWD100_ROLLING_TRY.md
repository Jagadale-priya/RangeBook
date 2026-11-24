# NIFTY 1m — try rolling-OOS densify + check Nov9+

Forward: **2026-11-09 → 2026-11-16** · days: 2026-11-09, 2026-11-11, 2026-11-12, 2026-11-13, 2026-11-16

Selection uses **calibrate + last3m rolling ISO-week holdouts only** (no FWD peek).
`ROLL∩FWD100` additionally drops any cell with a Nov9+ path loss.

## Results

| Book | Variant | Micros | Train l3m | FWD calls | FWD hit% | all_win |
|---|---|---:|---:|---:|---:|:---:|
| T10 | ROLL_m1 | 293 | 346/63d | 26 | 42.31% | False |
| T10 | ROLL_m2 | 44 | 98/45d | 2 | 0.0% | False |
| T10 | ROLL_m3 | 8 | 26/18d | 1 | 0.0% | False |
| T10 | PEEK_FWD100 | 25 | — | 0 | 0% | — |
| T10 | **ROLL∩FWD100** | 42 | — | 1 | 100.0% | True |
| T15 | ROLL_m1 | 207 | 251/62d | 27 | 44.44% | False |
| T15 | ROLL_m2 | 39 | 84/44d | 4 | 25.0% | False |
| T15 | ROLL_m3 | 5 | 16/11d | 1 | 0.0% | False |
| T15 | PEEK_FWD100 | 21 | — | 1 | 100.0% | — |
| T15 | **ROLL∩FWD100** | 39 | — | 2 | 100.0% | True |
| T20 | ROLL_m1 | 127 | 146/56d | 20 | 40.0% | False |
| T20 | ROLL_m2 | 18 | 38/28d | 3 | 33.33% | False |
| T20 | ROLL_m3 | 2 | 6/5d | 1 | 0.0% | False |
| T20 | PEEK_FWD100 | 10 | — | 1 | 100.0% | — |
| T20 | **ROLL∩FWD100** | 18 | — | 2 | 100.0% | True |

## Takeaway

- Honest `ROLL_m*` = deployable without peeking at Nov9+; hit% is the real OOS check.
- `ROLL∩FWD100` = operate when you require 100% including this forward week.
- Packs written under `nifty_1m_scalp_fwd_nov9_hold/*_ROLL*_micros.pkl`.
