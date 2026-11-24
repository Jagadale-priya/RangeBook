# NIFTY 1m — Opening **ZONE BOX** (draw up + down at open)

> **RESEARCH ONLY.** Matches your idea: one up zone, one down zone; market later **swings** from it or **breaks** it.

Window **2026-10-15 → 2026-11-16** (22 sessions).

## What a zone box is here

```
UP zone   = resistance box around a high edge  (mid ± 0.5×ATR)
DOWN zone = support box around a low edge
After zone is LIVE (OR complete / first origins known):
  price leaves → returns into the box →
    SWING = reject ≥15pts, no 1×ATR close-break
    BREAK = close through zone by ≥1×ATR
```

Both swing and break are valid zone behaviors (as you said).
**Decisive%** = swing + break (zone actually mattered).

## Methods compared

| Method | Retests | Swing% | Break% | **Decisive%** | Avg swing bounce | Big-leg origin in zone% |
|---|---:|---:|---:|---:|---:|---:|
| `OR15` | 31 | 64.52 | 35.48 | **100.0** | 40.83 | 19.05 |
| `OR30` | 26 | 57.69 | 42.31 | **100.0** | 36.22 | 14.29 |
| `OR30_BOX` | 26 | 57.69 | 42.31 | **100.0** | 36.22 | 14.29 |
| `FIRST_ORIGIN` | 27 | 59.26 | 37.04 | **96.3** | 47.8 | 9.52 |
| `OPEN_ATR` | 36 | 63.89 | 30.56 | **94.44** | 51.56 | 28.57 |

## Per side (UP vs DOWN)

| Method | UP n | UP swing% | UP break% | DOWN n | DOWN swing% | DOWN break% |
|---|---:|---:|---:|---:|---:|---:|
| `OR15` | 19 | 52.63 | 47.37 | 12 | 83.33 | 16.67 |
| `OR30` | 15 | 53.33 | 46.67 | 11 | 63.64 | 36.36 |
| `OR30_BOX` | 15 | 53.33 | 46.67 | 11 | 63.64 | 36.36 |
| `FIRST_ORIGIN` | 14 | 57.14 | 35.71 | 13 | 61.54 | 38.46 |
| `OPEN_ATR` | 18 | 50.0 | 44.44 | 18 | 77.78 | 16.67 |

## Proven takeaway

**Most decisive zone map:** `OR15` → decisive **100.0%** (swing 64.52% / break 35.48%, n=31).
**Best pure swing (reject) rate:** `OR15` → **64.52%**.
**Big moves launching from zone:** `OPEN_ATR` → **28.57%** of day’s largest post-live legs start inside a zone.

### Accurate zone logic to use (research)

```
At open / first 30 minutes:
  BOX = OR30 high/low  (the range you draw)
  UP zone   = OR30 high ± 0.5×ATR
  DOWN zone = OR30 low  ± 0.5×ATR

Optional sharpening (move-origin):
  Also mark first BUY-origin and first SELL-origin of day as pads
  (same ±0.5×ATR boxes) once those legs confirm

How to read a revisit:
  into UP zone   → expect SELL swing OR upside break (both OK)
  into DOWN zone → expect BUY swing OR downside break (both OK)
  If break → drop that edge; if swing → trade the bounce, SL beyond box
```

This is the zone/fox box behavior you described — not single lines, not candle patterns.

Elapsed 34s
