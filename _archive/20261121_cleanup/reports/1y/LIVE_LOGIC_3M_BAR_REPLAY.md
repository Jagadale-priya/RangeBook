# LIVE logic · 3m bar-by-bar replay

**Window:** `2026-08-15` → `2026-11-15` (~3 months)
**Bars replayed:** 4542 (every 5m candle 09:15–15:30)
**Code path:** `ensure_session_calls` + `annotate_analyze_result` (same as live)
**CHAMP fire events:** 2 · annotate_ok=141
**Combine UI:** raw=643 · ui=127 · multi=65 · **blocked=0**

## P2F research Target / SL

P2F (and P2G) path tickets use **risk = 30.0** → Target **+30** · SL **−30** (symmetric).
`good_by_risk['30.0']` points are ±30. Crown also has 20/35/40 buckets; main accurate desks score on **30**.

## CHAMP_PLUS 3m

| Slice | N | Hit% |
|---|---:|---:|
| Held book | 97 | 97.94 |
| Held ∪ live engine | 113 | 93.69 |

## Validation

- PASS `blocked_distinct_0` — blocked=0
- PASS `no_missing_ui_keys` — missing=0 ui=127 raw_keys=127
- PASS `champ_held_preserved` — held_3m=97 full_3m=113 missing=0
- PASS `champ_brackets_t30_sl30` — bad_levels=0
- PASS `champ_tags` — bad_tag=0
- PASS `p2f_day_1y_golden` — ACC100_MULTI_V11:86@100.0; ACC_WIDE_P92_P2F:86@100.0; ACC_WIDE_P90_P2F:98@100.0…
- PASS `p2f_cap2_1y_golden` — all cap2 desks match EXPECTED_1Y
- PASS `p2f_research_risk_30` — good_by_risk[30] n=879 · points ±30 (target/SL)

## Verdict: **PASS**

Fails: 0 · Elapsed 30430.1s

