# NIFTY CHAMP_PLUS · more calls at same accuracy?

**Window:** `2025-11-20` → `2026-11-20`
**Held live Cap4:** **343 @ 99.42%** (W/L 341/2)

## Verdict

- At **≥99.42%** (exact held): best **Cap6 → 433 @ 99.54%** (Δn **+90**).

- Quiet days with unused win-cands: **10** (naive Cap4 add → 353 @ 99.43% — check before live).

## Grid (cap × floor)

| Cap | Floor | N | Hit% | ΔN | Meets floor | ≥ held hit |
|---:|---:|---:|---:|---:|---|---|
| 4 | 99.42 | 415 | 99.52% | +72 | Y | Y |
| 5 | 99.42 | 429 | 99.53% | +86 | Y | Y |
| 6 | 99.42 | 433 | 99.54% | +90 | Y | Y |
| 8 | 99.42 | 433 | 99.54% | +90 | Y | Y |
| 4 | 99.0 | 417 | 99.04% | +74 | Y | N |
| 5 | 99.0 | 431 | 99.07% | +88 | Y | N |
| 6 | 99.0 | 435 | 99.08% | +92 | Y | N |
| 8 | 99.0 | 435 | 99.08% | +92 | Y | N |
| 4 | 98.0 | 421 | 98.1% | +78 | Y | N |
| 5 | 98.0 | 435 | 98.16% | +92 | Y | N |
| 6 | 98.0 | 439 | 98.18% | +96 | Y | N |
| 8 | 98.0 | 439 | 98.18% | +96 | Y | N |
| 4 | 97.0 | 425 | 97.18% | +82 | Y | N |
| 5 | 97.0 | 440 | 97.05% | +97 | Y | N |
| 6 | 97.0 | 444 | 97.07% | +101 | Y | N |
| 8 | 97.0 | 444 | 97.07% | +101 | Y | N |

## Notes

- Method matches held CHAMP_PLUS ticket-fill (prefer settled wins, then any; same-side day cap; ±30).
- **Best same-acc lift:** Cap**6** → **433 @ 99.54%** (+90 vs live Cap4 343). Cap8 adds nothing more.
- Even **Cap4** can rise to **415 @ 99.52%** (+72) by taking unused pool tickets (book not fully exhausted).
- Morning L5_u70_b80 is separate (~14/yr) and already additive.
- SL20 “more calls” books (~80% hit) are **not** same-acc — avoid for accuracy desk.
- Not promoted to live yet — say if you want Cap6 locked into the live engine.

JSON: `C:\Users\Priyanka\Agent\prod_live\reports\1y\NIFTY_CHAMP_MORE_SAME_ACC.json`
