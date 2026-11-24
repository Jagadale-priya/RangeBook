# NIFTY 1m — Support / Resistance / Range from **where market actually moves**

> **RESEARCH ONLY.** No candle patterns. No textbook. Pure price-path ZigZag legs.

Window **2026-10-05 → 2026-11-16** (30 sessions).

## Method

1. Build a **ZigZag** on price: reverse only after ≥ max(25pts, 2.5×ATR).
2. Each leg ≥35pts is a **real move**.
3. **Origin** = trough that started an up-leg, or peak that started a down-leg.
4. Cluster origins within ~0.5×ATR, **max span 12pts** → **launch pads**.
5. **Prove** pads: after 2 launches, leave & revisit → role-matched ≥40pt move?
6. **Range** = band between strong opposite pads + time-at-price (POC / value).

Legs in window: **442** · Launch pads: **162** · ZigZag pivots: 778

## Top launch pads (real S/R candidates)

| Rank | Price | Role | Launches | Days | BUY origins | SELL origins | Avg move pts | Span |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | **22667.32** | SUPPORT | 12 | 8 | 8 | 4 | 68.83 | 12.0 |
| 2 | **22730.57** | RESISTANCE | 11 | 7 | 5 | 6 | 89.89 | 7.3 |
| 3 | **22678.57** | SUPPORT | 11 | 6 | 6 | 5 | 80.04 | 10.5 |
| 4 | **22497.97** | RESISTANCE | 9 | 7 | 4 | 5 | 69.39 | 11.6 |
| 5 | **22583.62** | SUPPORT | 8 | 6 | 5 | 3 | 81.29 | 7.8 |
| 6 | **22524.88** | RESISTANCE | 8 | 5 | 3 | 5 | 97.19 | 10.55 |
| 7 | **22612.3** | SUPPORT | 8 | 5 | 5 | 3 | 92.15 | 11.55 |
| 8 | **22572.15** | SUPPORT | 8 | 5 | 6 | 2 | 80.59 | 11.0 |
| 9 | **22449.68** | SUPPORT | 8 | 5 | 6 | 2 | 68.74 | 10.3 |
| 10 | **22460.29** | SUPPORT | 8 | 4 | 5 | 3 | 60.88 | 2.35 |
| 11 | **22781.14** | RESISTANCE | 7 | 5 | 0 | 7 | 80.12 | 7.3 |
| 12 | **22415.54** | SUPPORT | 7 | 5 | 5 | 2 | 78.78 | 11.7 |
| 13 | **22653.22** | RESISTANCE | 7 | 5 | 3 | 4 | 76.04 | 10.25 |
| 14 | **22716.79** | RESISTANCE | 7 | 5 | 2 | 5 | 73.98 | 8.7 |
| 15 | **22482.77** | SUPPORT | 7 | 3 | 5 | 2 | 52.57 | 5.75 |
| 16 | **22742.72** | RESISTANCE | 6 | 5 | 2 | 4 | 86.3 | 7.8 |
| 17 | **22537.92** | RESISTANCE | 6 | 5 | 2 | 4 | 85.67 | 9.05 |
| 18 | **22702.7** | BOTH | 6 | 5 | 3 | 3 | 75.7 | 7.6 |
| 19 | **22638.29** | SUPPORT | 6 | 3 | 4 | 2 | 60.75 | 8.05 |
| 20 | **22557.59** | SUPPORT | 5 | 5 | 4 | 1 | 60.12 | 8.55 |
| 21 | **22923.72** | SUPPORT | 5 | 4 | 5 | 0 | 82.79 | 3.3 |
| 22 | **22625.41** | RESISTANCE | 5 | 4 | 2 | 3 | 75.16 | 9.1 |
| 23 | **22403.42** | RESISTANCE | 5 | 4 | 2 | 3 | 74.86 | 11.55 |
| 24 | **23056.17** | RESISTANCE | 5 | 4 | 2 | 3 | 57.16 | 9.05 |
| 25 | **22472.59** | SUPPORT | 5 | 4 | 3 | 2 | 53.47 | 2.9 |

## Proven: does revisiting a pad launch again?

Pads with ≥2 historical launches, then leave & retest: **74** tests.
Launched another ≥40.0pt move within ~40–60 bars: **35** → **47.3%**
Avg launch size when it fires: **81.01** pts.

- **SUPPORT** pads retest→launch: n=42 rate=42.86% avg_pts=76.35
- **RESISTANCE** pads retest→launch: n=40 rate=60.0% avg_pts=84.71

## Where do big daily moves start?

| Day | Side | Origin | End | Pts | Time |
|---|---|---:|---:|---:|---|
| 2026-10-19 | BUY | **22845.25** | 23120.9 | 275.65 | 14:26 |
| 2026-10-21 | SELL | **22989.25** | 22702.85 | 286.4 | 11:05 |
| 2026-10-22 | SELL | **22785.0** | 22589.8 | 195.2 | 11:14 |
| 2026-10-23 | SELL | **22730.9** | 22459.25 | 271.65 | 09:43 |
| 2026-10-26 | BUY | **22413.25** | 22706.15 | 292.9 | 09:41 |
| 2026-10-27 | SELL | **22678.55** | 22540.7 | 137.85 | 14:28 |
| 2026-10-28 | SELL | **22661.45** | 22497.7 | 163.75 | 09:51 |
| 2026-10-29 | BUY | **22734.45** | 22874.15 | 139.7 | 09:57 |
| 2026-10-30 | BUY | **23000.25** | 23330.7 | 330.45 | 14:01 |
| 2026-11-02 | BUY | **23207.05** | 23632.05 | 425.0 | 13:40 |
| 2026-11-03 | BUY | **23671.1** | 23946.35 | 275.25 | 14:27 |
| 2026-11-04 | BUY | **23854.8** | 24350.0 | 495.2 | 14:08 |
| 2026-11-05 | BUY | **24422.1** | 24579.9 | 157.8 | 12:43 |
| 2026-11-06 | BUY | **24774.65** | 25107.8 | 333.15 | 14:09 |
| 2026-11-08 | SELL | **25131.85** | 24874.85 | 257.0 | 14:23 |
| 2026-11-09 | BUY | **24989.25** | 25424.35 | 435.1 | 14:26 |
| 2026-11-11 | BUY | **25193.85** | 25355.85 | 162.0 | 14:27 |
| 2026-11-12 | SELL | **25283.5** | 25117.35 | 166.15 | 13:51 |
| 2026-11-13 | BUY | **25054.4** | 25337.6 | 283.2 | 14:22 |
| 2026-11-16 | SELL | **25309.55** | 25190.25 | 119.3 | 10:18 |

## Origin location vs session so far

Among 440 legs:
- Started **near session extreme** (BUY near day-low / SELL near day-high): **21.6%**
- Started in **mid session range**: **37.0%**

## Acceptance / value area (time-at-price, 5pt bins)

- **POC** (most time): **22710** (1.13% of closes)
- **VAL–VAH** (~70% value): **22195 → 23655**

Top acceptance bins:

| Price bin | Closes | % |
|---:|---:|---:|
| 22710 | 98 | 1.13 |
| 22725 | 84 | 0.96 |
| 22685 | 80 | 0.92 |
| 22690 | 75 | 0.86 |
| 22695 | 75 | 0.86 |
| 22715 | 74 | 0.85 |
| 22625 | 71 | 0.82 |
| 22650 | 71 | 0.82 |
| 22705 | 71 | 0.82 |
| 22680 | 70 | 0.8 |
| 22495 | 68 | 0.78 |
| 22490 | 65 | 0.75 |

## Range from opposite launch pads

| Lo (support pad) | Hi (resist pad) | Width | Strength | Contain% |
|---:|---:|---:|---:|---:|
| 22667.32 | 22730.57 | 63.25 | 23 | **10.16** |
| 22678.57 | 22730.57 | 52.0 | 22 | **8.61** |
| 22667.32 | 22716.79 | 49.47 | 19 | **8.38** |
| 22667.32 | 22781.14 | 113.82 | 19 | **14.58** |
| 22612.3 | 22730.57 | 118.27 | 19 | **16.88** |
| 22583.62 | 22730.57 | 146.95 | 19 | **19.98** |
| 22572.15 | 22730.57 | 158.42 | 19 | **20.84** |
| 22460.29 | 22730.57 | 270.28 | 19 | **33.98** |
| 22449.68 | 22730.57 | 280.89 | 19 | **None** |
| 22667.32 | 22702.7 | 35.38 | 18 | **None** |

## Where moves DIE (end-of-leg clusters)

| Price | Role@end | Hits | Avg leg into it |
|---:|---|---:|---:|
| 22676.64 | SUPPORT | 11 | 77.97 |
| 22665.98 | RESISTANCE | 11 | 77.55 |
| 22729.39 | RESISTANCE | 10 | 76.62 |
| 22458.12 | SUPPORT | 10 | 69.97 |
| 22497.28 | RESISTANCE | 9 | 74.92 |
| 22611.66 | BOTH | 8 | 54.55 |
| 22701.88 | RESISTANCE | 8 | 119.76 |
| 22652.07 | RESISTANCE | 8 | 66.39 |
| 22525.88 | RESISTANCE | 8 | 61.06 |
| 22763.73 | RESISTANCE | 7 | 102.17 |
| 22539.62 | RESISTANCE | 7 | 74.25 |
| 22441.26 | SUPPORT | 7 | 84.57 |

## Accurate logic (proven from move origins)

```
SUPPORT  = price clusters where UP-legs repeatedly launch (BUY origins / troughs)
RESISTANCE = price clusters where DOWN-legs repeatedly launch (SELL origins / peaks)
RANGE    = band between a strong support pad and strong resistance pad
         + tighten with VAL–VAH (time-at-price acceptance)

Build:
  ZigZag reverse ≥ max(25pts, 2.5×ATR)
  Keep legs ≥ 35pts
  Cluster origins within 0.5×ATR, span ≤ 12pts → pads
  Trust pads with n≥5 launches across ≥3 days
  On retest: expect role-matched ≥40pt move (~47% proven; resistance pads ~60%)
  In a trend, prefer recent pads + session extremes over multi-week value area
```


### Strongest SUPPORT pads this window

- **22667.32** · 12 launches · 8 days · avg 68.83 pts
- **22678.57** · 11 launches · 6 days · avg 80.04 pts
- **22583.62** · 8 launches · 6 days · avg 81.29 pts
- **22612.3** · 8 launches · 5 days · avg 92.15 pts
- **22572.15** · 8 launches · 5 days · avg 80.59 pts

### Strongest RESISTANCE pads this window

- **22730.57** · 11 launches · 7 days · avg 89.89 pts
- **22497.97** · 9 launches · 7 days · avg 69.39 pts
- **22524.88** · 8 launches · 5 days · avg 97.19 pts
- **22781.14** · 7 launches · 5 days · avg 80.12 pts
- **22653.22** · 7 launches · 5 days · avg 76.04 pts

### Best range box: **22667.32 – 22730.57** (width 63.25, contain 10.16%)
### Value area: **22195 – 23655** · POC **22710**

No candle patterns used. Levels come only from **where real legs started**.

Elapsed 21s
