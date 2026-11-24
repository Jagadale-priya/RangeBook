# NIFTY 1m — Deep entry accuracy research (final)

Goal: **side + entry price only**, favour-first ≥25pt (`m25_first`), near-**100%** precision.

## What was tested

| Pass | Idea | Best m25_first |
|---|---|---|
| v2 | Truth-aligned ignition (drop room/disp10) | ~**52%** (1/day) |
| v3 | Join-in-progress after already ≥8–15 | ~**54%** |
| v4 | Feature lift + pullback + OR retest | lead ~**80%** (thin) |
| v5 | Pullback compress+engulf (+ HTF fix) | **85.7%** on 120d |
| v5b | Same rule on 180/240d + folds | drops to **~71%** overall |
| v6 | Fold-stable hunt (240d / 4 folds) | **~71%** overall, min_fold ~**78%** (sparse early fold) |

## Most accurate causal rule found

```
PATTERN : bull_run2/3 or bear_run2/3 on 1m
WAIT    : ≤8 bars for opposite-color pullback touching ignition bar range
ENTRY   : close of next same-color continuation bar
FILTERS : ATR14 ≥ 10
        + compress (prior range ≤0.7×ATR AND body ≥0.8×ATR)
        + engulf prior bar
        + control close
        + NOT at session extreme
SIDE    : run direction
PRICE   : continuation close
```

### Numbers (honest)

| Window | n | m25_first | Train | OOS | Notes |
|---|---:|---:|---:|---:|---|
| 120d all | 21 | **85.7%** | 100% | 80% | HIGH_85 — **recent regime** |
| 180d all | 57 | **71.9%** | 68% | 81% | degrades |
| 240d all | 65 | **70.8%** | 64% | 86% | early folds ~62–64% |
| 240d folds | 8/36/6/15 | 62.5 / 63.9 / 100 / 80 | — | — | not stable at 85 |

## Fold-stable alternative (less flashy, more honest)

`pb ctrl+held+room_ok+disp08+atr_hi` on 240d: overall **~71%**, usable folds ~**78–80%** (early fold thin).

Still far from 95–100%.

## Hard ceiling (this research)

- **No PROVEN_100** and **no PROMISING_95** on `m25_first` with n≥15 train+OOS.
- Old IGN100 was **100% raw m25** on n=12, but only ~**40–50%** favour-first (`m25_first`) / fat MAE on several days.
- Ignition / join / OR-retest alone top out ~**50–55%** m25_first when sample is large.
- Best **recent** accuracy ~**85%** on a **sparse** pullback pattern; **not** durable on full-year folds.

## Live action

- Do **not** claim near-100% one-way entries.
- Keep `run_ignition_100` as **research mode** only.
- If shipping a “most accurate” research mode next: use the **pullback compress+engulf** rule above, labeled clearly as ~70–85% favour-first (regime-dependent), **not** 100%.

### Reports

- `NIFTY_1M_ENTRY_ACCURACY_V2.md`
- `NIFTY_1M_ENTRY_ACCURACY_V3_JOIN.md`
- `NIFTY_1M_ENTRY_ACCURACY_V4_DISC.md`
- `NIFTY_1M_ENTRY_ACCURACY_V5_FOCUS.md`
- `NIFTY_1M_ENTRY_ACCURACY_V5B_VALIDATE.md`
- `NIFTY_1M_ENTRY_ACCURACY_V6_STABLE.md`
