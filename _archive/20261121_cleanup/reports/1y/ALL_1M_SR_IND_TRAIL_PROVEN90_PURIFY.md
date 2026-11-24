# ALL 1m — Purify + S/R/Ind + EMA34 Trail · ≥90% hunt (phase 2)

> **RESEARCH ONLY — not live.**

## Exit

EMA34 trail strict · 1 call/day · WIN = T1 before MA flip

## Methods

1. **HELD** / HELD+sess — DI∧hard34∧VWAP
2. **PURIFY** — fingerprints 100% on train (incl. S/R+ind keys), first match
3. **UNION** — PURIFY else HELD
4. **SR_*** — tight support/resistance + indication stacks

NIFTY cut `2026-08-01` · BN cut `2026-05-03` · proven = train∧hold ≥90.0% n≥8

## PROVEN ≥90.0%

| Sym | T1 | Book | Train | Hold | Cover | avgPts |
|---|---:|---|---|---|---:|---:|
| BANKNIFTY | 12 | `HELD` | **90.57%**/159 | **90.48%**/126 | 100.0% | 0.59 |
| BANKNIFTY | 12 | `SR_held_bounce` | **90.57%**/159 | **90.48%**/126 | 100.0% | 1.52 |

## Hold ≥88% candidates (near / pass)

| Sym | T1 | Book | Train hit/n | Hold hit/n | cover | All hit |
|---|---:|---|---|---|---:|---:|
| NIFTY | 12 | `SR_bounce_backed_ctrl_clear` | 61.29%/31 | **92.31%**/13 | 17.81 | 70.45%/44 |
| BANKNIFTY | 12 | `HELD` | 90.57%/159 | **90.48%**/126 | 100.0 | 90.53%/285 |
| BANKNIFTY | 12 | `SR_held_bounce` | 90.57%/159 | **90.48%**/126 | 100.0 | 90.53%/285 |

## HELD baseline (no session) — the ≥90 path for BN historically

| Sym | T1 | Train | Hold | All |
|---|---:|---|---|---|
| NIFTY | 12 | 74.86%/175 | 78.08%/73 | 75.81%/248 |
| NIFTY | 15 | 70.29%/175 | 75.34%/73 | 71.77%/248 |
| NIFTY | 20 | 62.29%/175 | 69.86%/73 | 64.52%/248 |
| BANKNIFTY | 12 | 90.57%/159 | 90.48%/126 | 90.53%/285 |
| BANKNIFTY | 15 | 88.05%/159 | 87.3%/126 | 87.72%/285 |
| BANKNIFTY | 20 | 83.65%/159 | 83.33%/126 | 83.51%/285 |

## Cross-symbol status (honest)

| Symbol | ≥90% train+hold? | Best locked candidate | Notes |
|---|---|---|---|
| **BANKNIFTY** | **YES** | HELD · T1=12 · EMA34 trail · 1/day | Train 90.57% · Hold 90.48% · All 90.53% · cover 100% |
| **NIFTY** | **NOT YET** | HELD · T1=12 · EMA34 trail · 1/day | Hold only ~78% — same recipe does **not** clear 90% |
| Shared gate for both @90% | **NO** | — | Do not force one gate on both until NIFTY also clears |

NIFTY hold spike: `SR_bounce_backed_ctrl_clear` @ **92.31%** (n=13) but train only **61%** → **not proven** (overfit risk).

## Proven logic (BANKNIFTY only — research lock)

```
ENTRY (1m textbook):
  HELD = DI_ok ∧ hard34 ∧ VWAP_with
  (optional same-day bounce tag — identical stats on this sample)
  NO 09:30–14:30 session cut for this 90% book
  1 call/day = first HELD event

EXIT:
  T1 = 12 pts
  Trail = EMA34 STRICT (close flip vs EMA34 = stop)
  WIN only if T1 before MA flip
```

## Locked recipe shape (target for ALL — not met on NIFTY yet)

```
ENTRY:
  textbook candle
  + (PURIFY fingerprint match  OR  HELD=DI∧hard34∧VWAP)
  + optional S/R clear / bounce / hold_break filters
EXIT:
  T1 = 12 (NIFTY) / 12 (BN proven)
  trail = EMA34 close flip = stop
  1 call/day first match
```

Next for NIFTY ≥90%: denser purify cells, 2-bar confirm, or symbol-specific fingerprint book (not copy BN HELD blindly).

Elapsed 658s

**Not wired live.**
