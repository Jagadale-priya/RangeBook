# Deep Nov 2026 · proven LIVE + 1-day empty-fill calls

**Window:** `2026-11-01` → `2026-11-15` · sessions **10** · stack source: `pool_fallback`

## Books

| Book | Role |
|---|---|
| `STACK_PLUS_CROWN_HTF_CAP2` | LIVE proven > good > champ > crown HTF · cap2 |
| `EMPTY_FILL_FADE1030_GAP055_T35` | **1-day call** on stack-silent + `|gap|≥0.55` · 10:30 fade T35 |
| `STACK_PLUS_EMPTY_FILL_GAP055_T35` | Holding desk = stack ∪ fill |
| `ACC100_MULTI_V11` / P2F | Holding accurate (high hit) — report overlay |

## Summary

| Book | N | W/L | Hit% | Points |
|---|---:|---|---:|---:|
| LIVE stack | 1 | 1/0 | 100.0 | 0.0 |
| 1-day empty-fill | 4 | 3/1 | 75.0 | 70.0 |
| **Holding desk (stack+fill)** | **5** | 4/1 | **80.0** | **70.0** |

## Day-by-day from 1 Nov

| Day | Gap% | LIVE | 1-day fill | Holding desk | ACC P2F |
|---|---:|---|---|---|---|
| 2026-11-02 | +0.73 | — | **10:30 SELL** gap=0.734 W 35.0 `EMPTY_FILL_FADE1030_GAP055_T35` | 10:30 SELL `EMPTY_FILL_FADE1030_GAP055_T35` W | — |
| 2026-11-03 | +0.60 | — | **10:30 SELL** gap=0.6034 W 35.0 `EMPTY_FILL_FADE1030_GAP055_T35` | 10:30 SELL `EMPTY_FILL_FADE1030_GAP055_T35` W | — |
| 2026-11-04 | -0.29 | — | no — abs(gap) 0.29 < 0.55 | — | — |
| 2026-11-05 | +1.74 | — | **10:30 BUY** gap=1.7422 W 35.0 `EMPTY_FILL_FADE1030_GAP055_T35` | 10:30 BUY `EMPTY_FILL_FADE1030_GAP055_T35` W | — |
| 2026-11-06 | +0.01 | 11:20 BUY `crown_5m` W 0.0 | (off — stack has call) | 11:20 BUY `crown_5m` W | 11:20 BUY `ACC100_CROWN_BUY_AM1130_T20`; 11:20 BUY `ACC100_CROWN_BUY_AM1130_T20`; 11:20 BUY `ACC100_CROWN_BUY_AM1130_T20` |
| 2026-11-08 | +0.16 | — | no — abs(gap) 0.16 < 0.55 | — | — |
| 2026-11-09 | +0.18 | — | no — abs(gap) 0.18 < 0.55 | — | — |
| 2026-11-11 | +1.17 | — | **10:30 SELL** gap=1.1705 L -35.0 `EMPTY_FILL_FADE1030_GAP055_T35` | 10:30 SELL `EMPTY_FILL_FADE1030_GAP055_T35` L | — |
| 2026-11-12 | -0.16 | — | no — abs(gap) 0.16 < 0.55 | — | — |
| 2026-11-13 | -0.35 | — | no — abs(gap) 0.35 < 0.55 | — | — |

### Non-sessions

- `2026-11-01` Sat · `2026-11-07` Sat · `2026-11-10` holiday · `2026-11-14` Sat · `2026-11-15` Sun
- Daily NSE file ends ~`2026-11-11`; later gaps filled from 5m open vs prior close when needed.

## All holding-desk calls (list)

| Day | HM | Side | Source tag | Win | Pts | Multi-tags |
|---|---|---|---|---|---:|---|
| 2026-11-02 | 10:30 | SELL | `EMPTY_FILL_FADE1030_GAP055_T35` | W | 35.0 | `EMPTY_FILL_FADE1030_GAP055_T35`, `LOGIC_EMPTY_FILL`, `ONE_DAY_CALL` |
| 2026-11-03 | 10:30 | SELL | `EMPTY_FILL_FADE1030_GAP055_T35` | W | 35.0 | `EMPTY_FILL_FADE1030_GAP055_T35`, `LOGIC_EMPTY_FILL`, `ONE_DAY_CALL` |
| 2026-11-05 | 10:30 | BUY | `EMPTY_FILL_FADE1030_GAP055_T35` | W | 35.0 | `EMPTY_FILL_FADE1030_GAP055_T35`, `LOGIC_EMPTY_FILL`, `ONE_DAY_CALL` |
| 2026-11-06 | 11:20 | BUY | `crown_5m` | W | 0.0 | `STACK_PLUS_CROWN_HTF_CAP2`, `crown_5m`, `LOGIC_LIVE`, `SOURCE_POOL` |
| 2026-11-11 | 10:30 | SELL | `EMPTY_FILL_FADE1030_GAP055_T35` | L | -35.0 | `EMPTY_FILL_FADE1030_GAP055_T35`, `LOGIC_EMPTY_FILL`, `ONE_DAY_CALL` |

## Logic notes

1. **Fresh LIVE OR-break walk** on Nov tapes → proven=0, good=0, champ=0, crown_htf walk=0 (gates_fail / side_score_miss). No new proven calls from 1 Nov.
2. **Pool fallback** still carries crown `2026-11-06` BUY 11:20 (ACC path T20 scored +20 on that day).
3. **1-day empty-fill** (`EMPTY_FILL_FADE1030_GAP055_T35`) is the held way to get calls on stack-silent days with abs(gap)≥0.55 → **4 fills** (3W/1L).
4. Days with abs(gap)<0.55 stay empty by design (04, 08, 09, 12, 13).
5. **ACC/P2F** remains selective — only 11-06 crown stream.

Full JSON: `NOV2026_DEEP_CALLS.json`
