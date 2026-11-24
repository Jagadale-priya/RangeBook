# BANKNIFTY + SENSEX FINAL — Phase 0 inventory

**Date:** 2026-11-16  
**Rule:** Research → confirm → live. NIFTY FINAL untouched.

## Tape / caches

| Symbol | 5m | 15m | Dual packs |
|--------|----|-----|------------|
| BANKNIFTY | `BANKNIFTY_5m_kite.csv` | `BANKNIFTY_15m_12y.csv` | `research/banknifty_side_models/*.pkl` |
| SENSEX | `SENSEX_5m_kite.csv` | `SENSEX_15m_12y.csv` / `SENSEX_15m_5y.csv` | `research/sensex_side_models/*.pkl` |

## Dual-track baselines (freeze-OOS research)

### BANKNIFTY (`banknifty_proven_100_final.json`)

| Track | N | Hit% | Notes |
|-------|--:|-----:|-------|
| Proven BUY | 12 | 100.0 | first break · or_ext≤0.15 |
| Champion BUY | 29 | 93.1 | BUY first any regime · SELL blocked |
| Baseline | 523 | 52.8 | volume · not FINAL |

**Desk clips (start):** SL **60** / T **75**

### SENSEX (`sensex_proven_100_final.json`)

| Track | N | Hit% | Notes |
|-------|--:|-----:|-------|
| Proven BUY | 18 | 100.0 | first · or_ext≤0.15 · p≥0.55 |
| Champion | 68 | 89.7 | BUY p≥0.55 + SELL first p≥0.70 |
| Baseline | 769 | 58.0 | volume · not FINAL |

**Desk clips (start):** SL **80** / T **100**

## Candidate pools

- BN: `banknifty_full_live_candidates.json` (~5468 rows)
- Sensex: `sensex_full_live_candidates.json` (~7479 rows)

Fields: `day`, `when`, `decision`, `p_t1`, `outcome`, `points`, `first_break`, `regime`, `or_ext`, `mins`

## Gaps

- No existing P2F / P2G / CHAMP_PLUS BN or Sensex FINAL books (NIFTY-only).
- Promote only desks that clear dual proven/champ floors under **native** brackets after 5m path re-score.
- Drop weak desks rather than force three books.
