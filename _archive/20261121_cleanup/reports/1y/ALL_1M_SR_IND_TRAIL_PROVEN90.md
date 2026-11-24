# ALL 1m — S/R + Indicators + EMA34 Trail · Hunt ≥90%

> **RESEARCH ONLY — not wired to live Scalper.**

## Locked trailing exit (this study)

```
Exit = EMA34 trail STRICT
  • WIN  = price hits T1 BEFORE close flips against EMA34
  • LOSS = close flips vs EMA34 before T1 (ma_sl) or expiry
Book = 1 call / day (first gated textbook event)
Session = 09:30–14:30 when gate requires sess
```

## Entry building blocks searched

| Layer | Rules |
|---|---|
| **HELD** | DI_ok ∧ hard34 ∧ VWAP_with |
| **S/R** | clear_path (≥1–2×ATR room) · bounce at support/resist · hold_break · not into session extreme |
| **Indications** | MACD turn · ADX≥22 · DI spread≥8 · control+sweep · ind_strict3 · Tier A/B |

Proven bar: **train hit ≥90.0% AND hold hit ≥90.0%** · n≥8 each.

NIFTY window `2025-11-17→2026-11-16` cut `2026-08-01` · BN window `2025-09-08→2026-11-02` cut `2026-05-03`.

## PROVEN ≥90.0% (train + hold)

**None** hit ≥90% on both train and hold with min n.

## Cross-symbol (NIFTY ∧ BN hold ≥85%)

No shared gate cleared ≥85% hold on **both** symbols in this sweep.

## NEAR (≥85 both splits or ALL≥90)

| Sym | T1 | Gate | Train | Hold | All | status |
|---|---:|---|---|---|---|---|
| BANKNIFTY | 12 | `HELD` | 86.16%/159 | 87.3%/126 | 86.67%/285 | NEAR85 |

## Best hold hit — NIFTY (top gates)

| T1 | Gate | Hold hit | n | cover | Train hit | All hit | status |
|---:|---|---:|---:|---:|---:|---:|---|
| 12 | `bounce+backed+ctrl_sweep+clear15+HELD` | **92.31** | 13 | 17.81 | 58.62 | 69.05 | — |
| 15 | `bounce+backed+ctrl_sweep+clear15+HELD` | **84.62** | 13 | 17.81 | 48.28 | 59.52 | — |
| 12 | `HELD+hold_break+clear15` | **82.35** | 17 | 23.29 | 61.11 | 67.92 | — |
| 12 | `TierA+clear15` | **82.35** | 17 | 23.29 | 61.11 | 67.92 | — |
| 15 | `HELD+hold_break+clear15` | **76.47** | 17 | 23.29 | 52.78 | 60.38 | — |
| 15 | `TierA+clear15` | **76.47** | 17 | 23.29 | 52.78 | 60.38 | — |
| 12 | `HELD+hold_break` | **73.68** | 19 | 26.03 | 60.98 | 65.0 | — |
| 12 | `HELD` | **73.61** | 72 | 98.63 | 65.14 | 67.61 | — |
| 12 | `HELD+clear_atr` | **73.61** | 72 | 98.63 | 62.86 | 65.99 | — |
| 15 | `HELD` | **72.22** | 72 | 98.63 | 60.0 | 63.56 | — |
| 15 | `HELD+clear_atr` | **72.22** | 72 | 98.63 | 58.86 | 62.75 | — |
| 12 | `HELD+clear15+adx22+di8` | **70.83** | 72 | 98.63 | 71.26 | 71.14 | — |
| 12 | `HELD+ctrl_sweep+clear15` | **70.0** | 60 | 82.19 | 58.94 | 62.09 | — |
| 12 | `TierAB+clear15` | **70.0** | 60 | 82.19 | 58.94 | 62.09 | — |
| 15 | `HELD+hold_break` | **68.42** | 19 | 26.03 | 53.66 | 58.33 | — |

## Best hold hit — BANKNIFTY (top gates)

| T1 | Gate | Hold hit | n | cover | Train hit | All hit | status |
|---:|---|---:|---:|---:|---:|---:|---|
| 12 | `HELD+bounce` | **88.89** | 126 | 100.0 | 84.28 | 86.32 | — |
| 12 | `HELD` | **87.3** | 126 | 100.0 | 86.16 | 86.67 | NEAR85 |
| 15 | `HELD` | **84.92** | 126 | 100.0 | 82.39 | 83.51 | — |
| 12 | `HELD+macd+di8+clear15` | **84.47** | 103 | 81.75 | 88.71 | 86.78 | — |
| 15 | `HELD+bounce` | **84.13** | 126 | 100.0 | 78.62 | 81.05 | — |
| 12 | `HELD+ctrl_sweep` | **84.0** | 125 | 99.21 | 83.02 | 83.45 | — |
| 12 | `HELD+macd+adx22+clear15` | **83.0** | 100 | 79.37 | 88.33 | 85.91 | — |
| 12 | `hold|bounce+ctrl+clear15+HELD` | **82.86** | 105 | 83.33 | 80.51 | 81.61 | — |
| 20 | `HELD` | **82.54** | 126 | 100.0 | 77.99 | 80.0 | — |
| 12 | `HELD+not_extreme+macd+clear_atr` | **82.4** | 125 | 99.21 | 85.33 | 84.0 | — |
| 12 | `HELD+macd+clear15` | **81.82** | 110 | 87.3 | 87.5 | 84.87 | — |
| 12 | `TierAB+clear15+macd` | **81.82** | 22 | 17.46 | 86.96 | 85.29 | — |
| 15 | `HELD+ctrl_sweep` | **81.6** | 125 | 99.21 | 77.99 | 79.58 | — |
| 20 | `HELD+bounce` | **80.95** | 126 | 100.0 | 75.47 | 77.89 | — |
| 12 | `HELD+ctrl_sweep+clear15` | **80.49** | 41 | 32.54 | 86.15 | 83.96 | — |

## Proposed locked logic (if PROVEN90 exists)

No ≥90% train+hold lock yet. Strongest near-gates listed above.
Next deepen: purified fingerprints (100% train cells) ∪ HELD+S/R, 2-bar confirm, ATR-scaled T1 for BN, ratchet trail after +12.

## Accuracy note

≥90% here means **trade hit-rate under EMA34 trail + T1**, not raw MFE Acc%.
MFE-only Acc% ceilings ~50–60% on HELD — trailing + target is required for 90% books.

Elapsed 350s

**Not live** until a PROVEN90 gate is explicitly approved for wiring.
