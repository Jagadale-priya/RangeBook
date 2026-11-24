# Morning session context — FINAL held logic

**Tag:** `MORNING_CALIBRATED_V1`  
**Job:** before **9:15 IST** · **no BUY/SELL calls**

## Inputs (realtime morning)
1. **News** — India MARKET + symbol headlines (scored; strong opposite can veto bias)
2. **Globals** — SPX, Nasdaq, Dow, Nikkei, Hang Seng, VIX, INR, crude, India VIX
3. **Yesterday** — prior close, structure/trend, ATR, candle
4. **Not used** — today’s cash open/high/low

## Outputs + guarantee

| Output | Rule | Guarantee |
|---|---|---|
| **Expected high/low** | ATR×**3.5**, more room downside, center = prior close | **YES ~96–97%** full containment (1y/3y/5y) |
| **Bias** BULLISH/BEARISH/NEUTRAL | **HIGH:** US+Asia agree **and** \|SPX\|≥**1.5%** · **MED:** \|fuse_us_asia\|≥**5.5** · else NEUTRAL · news veto if strong opposite | **YES ≥70% when HIGH speaks** (1y 83% · 3y 71% · 5y 73%). Walk-fold min ~63% — not every regime. |
| **Gap** GAP_UP/DOWN/NATURAL | Same HIGH gate as **lean only** | **NO** hard guarantee (best ~54–59%). Shown with `gap_confidence=LOW` when lean fires. |
| **Drivers** | SPX / US / Asia / agree / fuse / news / trend | Always shown |
| **soft_lean** | Overnight/trend/news when not speaking | Display only |

## What “guarantee” means
- **Range:** we guarantee the box math held on 1y+3y+5y at ≥95%.
- **Bias:** we guarantee spoken accuracy ≥70% on 1y+3y+5y **only on HIGH days** (rare, ~5–15% of sessions). Other days stay NEUTRAL.
- **Gap:** we do **not** guarantee. Deep hunts could not clear ≥70% stably for premarket gap.
- **News history** in DB for MARKET is short (~weeks); live scoring still runs every morning and is logged for future proof.

## Research trail
- `reports/1y/MORNING_DEEP_FUSION.md`
- `reports/1y/MORNING_CALIBRATED_GUARANTEE.md`
- `reports/1y/MORNING_FINAL_REVALIDATE.md`
- `reports/1y/MORNING_BIAS_STABILITY_SCAN.md`

## Code
- `app/legacy/morning_session_context.py` — `decide_pre915_gap_bias`, `compute_overnight_fusion`
- `app/legacy/morning_job.py` — `morning_pre915_context`
