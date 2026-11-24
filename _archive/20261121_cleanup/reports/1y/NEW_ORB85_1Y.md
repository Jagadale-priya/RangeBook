# New opening-range logic — last year held out

**Status:** RESEARCH · not live
**Select:** `2023-11-16` → `2025-11-14` · **Test:** `2025-11-15` → `2026-11-15`
Three new entries, chosen only on the earlier years: first close outside the opening range, second close in a row, and a retest that comes back to the range and closes out again.
Existing desks were not used.

## Stop 25 / target 30

First-break base rate: earlier 434 @ 46.54%, last year 224 @ 39.29%.

| Floor | Rule | Earlier N@hit | Last year N@hit |
|---:|---|---|---|
| 85 | — | none | — |
| 88 | — | none | — |
| 90 | — | none | — |

Best earlier-year rule with at least 20 calls: `confirm2_BUY_am_aligned30_any_any_any` 36 @ 63.89%, last year 16 @ 62.5%.

## Stop 30 / target 30

First-break base rate: earlier 429 @ 51.28%, last year 224 @ 47.77%.

| Floor | Rule | Earlier N@hit | Last year N@hit |
|---:|---|---|---|
| 85 | — | none | — |
| 88 | — | none | — |
| 90 | — | none | — |

Best earlier-year rule with at least 20 calls: `reclaim_BUY_open_aligned_mid_fast_any` 32 @ 68.75%, last year 21 @ 47.62%.

## Verdict

No frozen new rule holds 85% on the last year. The strongest earlier-year rule with at least 20 calls was 32 @ 68.75% and scored 21 @ 47.62% on the last year (reclaim_BUY_open_aligned_mid_fast_any).

