# NIFTY — Price Action **BOS / CHoCH / FVG** (transcript model)

> **RESEARCH ONLY — not live Scalper yet.**

Window **2026-09-11 → 2026-11-16** (44 sessions).

## 0) Accurate definitions (Google / ICT cross-checked)

| Term | Accurate definition | Key rule |
|---|---|---|
| **BOS** | Body **close** beyond last swing **with** the trend | Continuation. Wick-only = liquidity sweep, **not** BOS ([ICT BOS](https://www.ictkillzone.com/ict-bos), [Velotrade](https://velotrade.com/blog/break-of-structure)) |
| **CHoCH** | First body close beyond last swing **against** the trend | Flip *warning*, not a guaranteed reversal ([ICT CHoCH](https://www.ictkillzone.com/ict-choch)) |
| **FVG** | 3 candles; bullish if `low[3] > high[1]`; bearish if `high[3] < low[1]` | Wick-to-wick gap; mid = CE; body close beyond far edge invalidates ([IC Trading](https://ictradingconcepts.com/ict/fair-value-gap/)) |
| **Break+retest** | Close beyond level → polarity flip → return/test → continue | Enter on retest reaction; stop beyond retest extreme ([Right Trader](https://therighttrader.com/learn/trend-analysis/breakout-retest)) |
| **HTF / LTF** | 15m = map · 1m = turn-by-turn entry | Exact transcript framing |
| **Session open** | NSE **09:15–10:00** IST | Analogue of transcript NY open volume window |

**Transcript core (3 keys):** Direction (HH/HL or LH/LL + BOS + trendline) → Confirmation (response / FVG, not knife-catch) → Invalidation (break+retest + CHoCH).

Simple ≠ risk-free. We measure **repeatable R-multiple hit rate** and **expectancy in R**.

## 1) Structure density (44d)

- 15m: BOS **97** · CHoCH **50**
- 1m: BOS **1491** · CHoCH **952** · FVG **4128**

## 2) Entry books (1/day, TP 3R / 4R, hold ≤90m)

| Book | What it encodes | n | 3R Hit% | exp R | HTF-al n | HTF-al 3R% | HTF-al expR |
|---|---|---:|---:|---:|---:|---:|---:|
| A · Transcript CHoCH→FVG mid | — | 43 | 30.23 | 0.209 | 12 | 41.67 | 0.667 |
| B · ICT CHoCH+BOS→FVG | — | 43 | 23.26 | -0.07 | 19 | 26.32 | 0.053 |
| C · BOS continuation→FVG (trend friend) | — | 42 | 28.57 | 0.143 | 42 | 28.57 | 0.143 |
| D · CHoCH break+retest | — | 43 | 20.93 | -0.163 | 15 | 33.33 | 0.333 |

**Best HTF-aligned 3R (n≥8):** `transcript_choch_fvg` · hit **41.67%** · exp **0.667R** · n=12

### Expectancy note

At 3R, breakeven hit ≈ **25%**. Above that → positive expectancy if costs ≈0.
At 4R, breakeven hit ≈ **20%**.

## 3) Sample trades — best book (HTF-aligned preferred)

| Day | HM | Side | Entry | SL | Risk | 3R | 4R | HTF | Book |
|---|---|---|---:|---:|---:|---|---|---|---|
| 2026-09-16 | 09:34 | SELL | 23210.4 | 23223.05 | 12.65 | WIN | WIN | down | transcript_choch_fvg |
| 2026-09-17 | 09:27 | SELL | 23244.0 | 23256.95 | 12.95 | sl | sl | down | transcript_choch_fvg |
| 2026-09-23 | 10:00 | SELL | 23377.97 | 23389.3 | 11.33 | sl | sl | down | transcript_choch_fvg |
| 2026-10-06 | 11:01 | BUY | 22659.85 | 22651.9 | 7.95 | WIN | WIN | up | transcript_choch_fvg |
| 2026-10-13 | 10:46 | BUY | 22506.62 | 22494.65 | 11.97 | sl | sl | up | transcript_choch_fvg |
| 2026-10-19 | 09:35 | SELL | 23114.62 | 23127.4 | 12.78 | sl | sl | down | transcript_choch_fvg |
| 2026-10-22 | 10:07 | SELL | 22615.97 | 22626.7 | 10.73 | sl | sl | down | transcript_choch_fvg |
| 2026-10-26 | 09:48 | BUY | 22450.72 | 22440.8 | 9.92 | WIN | WIN | up | transcript_choch_fvg |
| 2026-10-27 | 09:33 | BUY | 22709.12 | 22699.45 | 9.67 | WIN | WIN | up | transcript_choch_fvg |
| 2026-11-06 | 09:38 | BUY | 24531.5 | 24522.4 | 9.1 | WIN | WIN | up | transcript_choch_fvg |
| 2026-11-09 | 09:47 | BUY | 24933.42 | 24925.25 | 8.17 | sl | sl | up | transcript_choch_fvg |
| 2026-11-13 | 10:05 | SELL | 25207.92 | 25212.45 | 4.53 | sl | sl | down | transcript_choch_fvg |

### Transcript book A samples

| Day | HM | Side | Entry | SL | 3R | HTF |
|---|---|---|---:|---:|---|---|
| 2026-09-11 | 09:34 | SELL | 23253.57 | 23259.3 | sl | None |
| 2026-09-15 | 09:24 | SELL | 23491.4 | 23502.05 | WIN | up |
| 2026-09-16 | 09:34 | SELL | 23210.4 | 23223.05 | WIN | down |
| 2026-09-17 | 09:27 | SELL | 23244.0 | 23256.95 | sl | down |
| 2026-09-18 | 10:29 | SELL | 23313.95 | 23316.25 | sl | up |
| 2026-09-21 | 10:11 | SELL | 23389.8 | 23392.8 | sl | up |
| 2026-09-22 | 10:17 | SELL | 23460.3 | 23466.45 | WIN | up |
| 2026-09-23 | 10:00 | SELL | 23377.97 | 23389.3 | sl | down |
| 2026-09-24 | 09:51 | BUY | 23228.62 | 23223.65 | sl | down |
| 2026-09-25 | 09:37 | BUY | 23090.0 | 23083.35 | sl | down |
| 2026-09-28 | 10:15 | BUY | 22857.53 | 22853.6 | sl | down |
| 2026-09-29 | 09:57 | BUY | 22602.68 | 22592.3 | sl | down |
| 2026-09-30 | 09:22 | BUY | 22710.18 | 22700.75 | sl | down |
| 2026-10-01 | 10:10 | BUY | 22576.85 | 22567.1 | sl | down |
| 2026-10-05 | 11:06 | BUY | 22492.3 | 22484.25 | sl | down |

## 4) vs Oracle T15 clean (not apples-to-apples)

| Model | Nature | Density | Accuracy framing |
|---|---|---|---|
| **Oracle T15 ∩ TierAB clean** | Hindsight path-wins then filter | ~1.6 cpd (35/22d prior) | High by construction on T15 path |
| **PA BOS/CHoCH/FVG** | Live-causal structure + imbalance | ~0.3–1.0 cpd | True out-of-sample path R-hit |

- Oracle clean answers: *among textbook T15 winners, which filters keep quality?*
- PA answers: *can we enter from structure alone without path-win peek?*
- Misses on major `run2/run3` often look like **displacement + FVG** — this PA book targets that language.
- If a PA book holds **>35% @ 3R with HTF align**, it is expectancy-positive and worth a Scalper research mode `pa_fvg_1m`.

## 5) Practical reading (what the transcript got right)

1. **Strip indicators** — BOS/CHoCH/FVG are pure OHLC structure.
2. **Direction first** — zoom out (15m) before 1m entries.
3. **Confirm, don't predict** — FVG pullback / retest > knife-catch at a line.
4. **Invalidation** — CHoCH + break/retest is the flip language; ICT adds: wait for confirming BOS after CHoCH.
5. **Simple ≠ easy** — losses are opportunity cost; size for the model, not for zero losses.
6. **NSE adaptation** — use 09:15–10:00 IST, not NY open.

_Generated in 9.5s._
