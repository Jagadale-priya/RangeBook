# Continuous candle research · locked `frvp_vah_break` + `no_exhaust`

Window 2026-10-22 → 2026-11-20 (22 sessions). Candles read **before / at / during** every call.

## Autopsy — candles before entry (5-bar story)

| Feature | Wins | Hard SL |
|---|---|---|
| N | 51 | 23 |
| Close OK % | 98.0 | 95.7 |
| Expand (range+body) % | 74.5 | 60.9 |
| Pullback-resume % | 31.4 | 17.4 |
| Momentum stack % | 84.3 | 82.6 |
| Clean window % | 13.7 | 30.4 |
| Noisy window % | 43.1 | 39.1 |
| Squeeze into entry % | 2.0 | 8.7 |
| Prior reject % | 29.4 | 26.1 |
| Avg impulse (ATR) | 0.54 | 0.485 |
| Avg with / opp bars | 2.549 / 2.451 | 2.913 / 2.087 |
| Avg entry body | 0.667 | 0.595 |

## Autopsy — candles during the move

| Feature | Wins | Hard SL |
|---|---|---|
| Fast to 1R (≤8 bars) % | 64.7 | 0.0 |
| Stall (no 0.5R soon) % | 3.9 | 60.9 |
| Messy path % | 49.0 | 60.9 |
| Avg bars to 0.5R / 1R | 4.118 / 8.804 | 3.9 / None |
| Avg with / opp on path | 6.039 / 6.098 | 3.087 / 6.087 |
| Avg pin-against | 0.843 | 0.478 |
| Avg max opp streak | 2.667 | 3.13 |
| Avg giveback after 1R (R) | 0.652 | 0.0 |

## Ablation (extra entry read × trail read) on locked book

Locked base: n=76 hit=67.11% avgR=0.466 sum=631.06

| Variant | N | Hit% | AvgR | Sum |
|---|---:|---:|---:|---:|
| **LOCKED BASE** | 76 | 67.11 | 0.466 | 631.06 |
| read_v3+pin_protect | 46 | 80.43 | 0.602 | 479.46 |
| pb_resume+base | 20 | 80.0 | 0.793 | 268.2 |
| read_v3+base | 46 | 78.26 | 0.6 | 470.61 |
| reject_ctx+base | 19 | 73.68 | 0.68 | 266.51 |
| read_v3+stall_cut | 46 | 71.74 | 0.383 | 323.31 |
| expand+base | 53 | 71.7 | 0.478 | 443.11 |
| impulse_pos+pin_protect | 57 | 70.18 | 0.508 | 533.06 |
| impulse_pos+base | 57 | 70.18 | 0.498 | 519.16 |
| read_v3+with_only | 46 | 69.57 | 0.476 | 405.1 |
| close_ok+pin_protect | 74 | 68.92 | 0.464 | 619.11 |
| **none+pin_protect** | 76 | 68.42 | 0.467 | 639.91 |
| close_ok+base | 74 | 67.57 | 0.463 | 610.26 |
| not_noisy+pin_protect | 43 | 67.44 | 0.539 | 398.36 |
| not_noisy+base | 43 | 67.44 | 0.528 | 389.31 |
| mom+base | 43 | 67.44 | 0.528 | 389.31 |
| read_v1+base | 43 | 67.44 | 0.528 | 389.31 |
| none+base | 76 | 67.11 | 0.466 | 631.06 |
| none+opp2_protect | 76 | 67.11 | 0.44 | 600.51 |
| read_v2+pin_protect | 41 | 65.85 | 0.492 | 356.01 |
| read_v2+base | 41 | 65.85 | 0.48 | 346.96 |
| impulse_pos+with_only | 57 | 63.16 | 0.543 | 567.9 |
| none+read_full | 76 | 63.16 | 0.295 | 406.26 |
| impulse_pos+stall_cut | 57 | 63.16 | 0.248 | 256.91 |
| not_noisy+with_only | 43 | 62.79 | 0.672 | 484.66 |
| read_v2+with_only | 41 | 60.98 | 0.612 | 434.76 |
| close_ok+stall_cut | 74 | 60.81 | 0.262 | 305.96 |
| none+stall_cut | 76 | 60.53 | 0.278 | 335.16 |
| not_noisy+stall_cut | 43 | 60.47 | 0.238 | 159.16 |
| read_v2+stall_cut | 41 | 58.54 | 0.178 | 121.61 |
| close_ok+with_only | 74 | 58.11 | 0.411 | 574.1 |
| none+with_only | 76 | 57.89 | 0.419 | 598.1 |
| clean+base | 14 | 50.0 | -0.057 | -14.8 |

## Recommendation

**Live lock (accuracy):** `read_v3+pin_protect` — n=46 hit=**80.43%** avgR=0.602 sum=479
**Volume-kept alt:** `none+pin_protect` — n=76 hit=68.42 avgR=0.467 sum=640

Wired as logic **v2h**: `candle_entry_mode=read_v3`, `candle_trail_mode=pin_protect`.

### Continuous candle rules that matter

1. **Pre-entry 5-bar window:** require directional close, avg body ≥0.40, **zero pin-against** in the window (read_v3).
2. **Still skip prior exhaust / weak entry** (nested inside read_v3).
3. **During move:** wins hit 1R fast (65% ≤8 bars); hard SLs **never** — path with-candles matter more than entry fluff.
4. **Trail:** structure ratchet + **pin_protect** (tighten on opposing pin / strong opposing body after 1R). stall_cut / with_only / opp2 cut expectancy — not used.
