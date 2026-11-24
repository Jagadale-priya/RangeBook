# NIFTY 1m — Oracle T15 · **clean filters + higher target**

> **RESEARCH ONLY — not changing Scalper live Setup A/B.**

Window **2026-10-15 → 2026-11-16** (22 sessions) · 09:30–14:30 · exit **EMA34 trail**.

Same entry logic as Scalper **Oracle T15** (textbook path-wins). This report finds gates that **drop unnecessary calls** and keep / lift **T20–T25** path quality.

## 1) Oracle baseline (gap15)

| Metric | Value |
|---|---:|
| Oracle T15 all path-wins | 1686 |
| Oracle gap15 calls | 314 |
| Calls / day | 14.27 |
| Also path-win T20 | 78.03% |
| Also path-win T25 | 67.83% |
| Avg MFE (trail) | 51.87 |

## 2) Clean filters on Oracle T15 (peek — same entries, fewer calls)

Applied on top of Oracle T15 path-wins, then re-spaced gap15.

| Gate | n | cut% | cpd | T20% | T25% | ΔT20 | avg MFE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `Oracle T15 raw (gap15)` | 314 | 0.0 | 14.27 | 78.03 | 67.83 | 0.0 | 51.87 |
| `+ HELD` | 162 | 48.41 | 7.36 | 82.72 | 75.31 | 4.69 | 57.88 |
| `+ AD_with` | 288 | 8.28 | 13.09 | 77.08 | 67.01 | -0.95 | 53.75 |
| `+ ctrl` | 300 | 4.46 | 13.64 | 81.0 | 68.67 | 2.97 | 53.03 |
| `+ !extreme` | 278 | 11.46 | 12.64 | 75.54 | 62.95 | -2.49 | 48.31 |
| `+ clear_path` | 76 | 75.8 | 3.45 | 72.37 | 60.53 | -5.66 | 48.87 |
| `+ TierAB` | 35 | 88.85 | 1.59 | 88.57 | 71.43 | 10.54 | 59.75 |
| `+ TierA` | 11 | 96.5 | 0.5 | 81.82 | 63.64 | 3.79 | 68.74 |
| `+ HELD + AD` | 150 | 52.23 | 6.82 | 80.67 | 72.67 | 2.64 | 57.92 |
| `+ HELD + !extreme` | 124 | 60.51 | 5.64 | 83.06 | 75.0 | 5.03 | 57.19 |
| `+ HELD + AD + !extreme` | 102 | 67.52 | 4.64 | 78.43 | 72.55 | 0.4 | 55.56 |
| `+ HELD + AD + ctrl` | 140 | 55.41 | 6.36 | 82.86 | 72.86 | 4.83 | 57.79 |
| `+ HELD + AD + !extreme + ctrl` | 93 | 70.38 | 4.23 | 80.65 | 73.12 | 2.62 | 54.87 |
| `+ HELD + clear` | 45 | 85.67 | 2.05 | 82.22 | 68.89 | 4.19 | 51.68 |
| `+ HELD + !extreme + clear` | 45 | 85.67 | 2.05 | 82.22 | 68.89 | 4.19 | 51.68 |
| `+ HELD + AD + clear` | 35 | 88.85 | 1.59 | 88.57 | 71.43 | 10.54 | 51.61 |
| `+ HELD + AD + !extreme + clear` | 35 | 88.85 | 1.59 | 88.57 | 71.43 | 10.54 | 51.61 |
| `+ TierAB + !extreme` | 35 | 88.85 | 1.59 | 88.57 | 71.43 | 10.54 | 59.75 |
| `+ TierAB + AD` | 25 | 92.04 | 1.14 | 88.0 | 72.0 | 9.97 | 59.94 |
| `+ TierA + AD` | 6 | 98.09 | 0.27 | 83.33 | 50.0 | 5.3 | 71.3 |
| `+ into_extreme + AD` | 86 | 72.61 | 3.91 | 83.72 | 72.09 | 5.69 | 61.21 |
| `+ HELD + into_extreme + AD` | 76 | 75.8 | 3.45 | 82.89 | 72.37 | 4.86 | 58.71 |

## 3) Blind gates (deployable — no peek)

Same EMA34 trail · T15 scored after the gate. Among T15 winners, report T20/T25 share.

| Gate | gap15 Hit% | n | cpd | 1cpd Hit% | n | T20% of T15 wins | T25% | avg MFE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `TierA + AD` | 75.0 | 8 | 0.36 | 83.33 | 6 | 83.33 | 50.0 | 71.3 |
| `HELD + into_extreme + AD` | 69.44 | 108 | 4.91 | 76.19 | 21 | 82.67 | 72.0 | 57.45 |
| `TierA` | 68.75 | 16 | 0.73 | 70.0 | 10 | 81.82 | 63.64 | 68.74 |
| `HELD + AD + clear` | 66.04 | 53 | 2.41 | 78.95 | 19 | 88.57 | 71.43 | 51.61 |
| `HELD + AD + !extreme + clear` | 66.04 | 53 | 2.41 | 78.95 | 19 | 88.57 | 71.43 | 51.61 |
| `HELD + clear` | 65.67 | 67 | 3.05 | 71.43 | 21 | 81.82 | 68.18 | 51.95 |
| `HELD + !extreme + clear` | 65.67 | 67 | 3.05 | 71.43 | 21 | 81.82 | 68.18 | 51.95 |
| `HELD + AD + ctrl` | 64.9 | 208 | 9.45 | 85.71 | 21 | 84.44 | 74.81 | 57.73 |
| `HELD + AD` | 63.88 | 227 | 10.32 | 80.95 | 21 | 81.38 | 73.79 | 57.74 |
| `HELD + AD + !extreme + ctrl` | 62.5 | 144 | 6.55 | 85.71 | 21 | 83.33 | 75.56 | 55.66 |
| `TierAB + AD` | 62.5 | 40 | 1.82 | 66.67 | 18 | 88.0 | 72.0 | 59.94 |
| `HELD` | 61.6 | 250 | 11.36 | 80.95 | 21 | 82.47 | 75.97 | 58.14 |
| `HELD + AD + !extreme` | 61.25 | 160 | 7.27 | 85.71 | 21 | 79.59 | 73.47 | 55.83 |
| `TierAB` | 60.34 | 58 | 2.64 | 63.16 | 19 | 88.57 | 71.43 | 59.75 |
| `TierAB + !extreme` | 60.34 | 58 | 2.64 | 63.16 | 19 | 88.57 | 71.43 | 59.75 |
| `HELD + !extreme` | 56.5 | 200 | 9.09 | 76.19 | 21 | 84.96 | 76.99 | 58.93 |
| `ALL textbook sess` | 36.9 | 420 | 19.09 | 54.55 | 22 | 87.1 | 74.84 | 56.28 |

## 4) Winner (plan rules)

Rules: cut Oracle gap15 **≥30%**, T20 share **≥ baseline**, blind gap15 hit **≥60%** when n≥30 (if blind twin exists).

**Recommended clean gate:** `+ TierAB`

| Metric | Value |
|---|---:|
| Calls after clean | 35 |
| Cut vs Oracle gap15 | 88.85% |
| T20 share | 88.57% |
| T25 share | 71.43% |
| ΔT20 vs baseline | 10.54 |
| Avg MFE | 59.75 |
| Blind twin | `TierAB` |
| Blind gap15 hit | 60.34% (n=58) |

**Ship later (not this run):** Scalper mode `oracle_t15_clean` = Oracle T15 path-wins ∩ `+ TierAB` (or blind twin `TierAB` for live/deployable).

### Best blind (gap15 hit, n≥30)

- Gate: `HELD + into_extreme + AD`
- gap15 Hit% **69.44** · n=108 · cpd=4.91
- Among its T15 wins: T20 **82.67%** · T25 **72.0%** · avg MFE 57.45

## 5) Takeaway

- Oracle T15 remains the **hindsight ceiling** (100% by selecting path-wins).
- Cleaning = drop Oracle calls that lack structure (HELD / AD / Tier / extreme rules).
- Higher target quality = among survivors, share that also path-win **T20/T25** under the same trail.
- Do **not** change Setup A/B until a clean gate is wired as an explicit Scalper mode.

_Generated in 75.3s._
