# NIFTY F&O — Live vs Research complete comparison

**Purpose:** end the naming confusion. Same words (`champion`, `proven`, `CHAMP_PLUS`) mean different layers.

**As of:** 2026-11-19

---

## 1 · One-line truth

| Layer | What actually puts a BUY/SELL on the **Calls board** today |
|---|---|
| **Primary live listing** | **CHAMP_PLUS / crown fill** (`SUPPRESS_DUAL_LIST=1` default) |
| **Dual proven/champion** | Still **scored + annotated** (`USE_DUAL_TRACK=1`); **not listed** unless `SUPPRESS_DUAL_LIST=0` |
| **FINAL P2F / P2G / CHAMP_PLUS** | Tags / annotate (+ CHAMP_PLUS ticket-fill when board empty) |
| **Research folder `nifty_fno`** | **Not wired to live** — proven15+proven10 accuracy book only |

See `reports/1y/NIFTY_NO_DUAL_FIRST_1Y.md` for the no-dual-first 1y ranking.

---

## 2 · Current live Calls path (code order)

```
fno_ws_rescore
  1) Score 15m dual packs → proven_100 or champion (annotate/debug)
  2) SUPPRESS_DUAL_LIST=1 → do NOT list dual on Calls
  3) ENABLE_P2F_LIVE_ACCURATE → annotate P2F + P2G + run CHAMP_PLUS engine
  4) If no open call → fno_dual_modal_list.fill_from_channels
        → CHAMP_PLUS newly added fires
        → else 5m crown (if enabled)
```

| Flag | Default | Role |
|---|---|---|
| `USE_DUAL_TRACK` | **ON** | Evaluate dual proven/champion |
| `SUPPRESS_DUAL_LIST` | **ON** | Block dual from Calls; fill path primary |
| `ENABLE_P2F_LIVE_ACCURATE` | **ON** | Annotate FINAL + CHAMP_PLUS engine |
| `ENABLE_STACKED_CALLS` | OFF | Research stack union |
| `ENABLE_PRE_DUAL_SINGLE` | OFF | Pre-dual “good” single |
| `ENABLE_EXTRA_TREES_SINGLE` | **OFF** | ExtraTrees list |

---

## 3 · Master comparison table

| Logic | Research report / result | On live Calls today? | How live uses it | Extra vs research |
|---|---|---|---|---|
| **Dual `proven_100`** (15m) | Dual caches · 1y ~24 @ **100%** (proven book) | **No (suppressed)** | Annotate/debug only unless `SUPPRESS_DUAL_LIST=0` | Restore with flag=0 |
| **Dual `champion`** (15m) | `CHAMPION_ONLY_1Y` ~41 @ **92.5%**; dual cache ~39 @ 92% | **No (suppressed)** | Annotate/debug only unless `SUPPRESS_DUAL_LIST=0` | Live clip SL20/T30 if restored |
| **CHAMP_PLUS** T30SL30 Cap4 | **374 @ 99.47%** 1y · 1028 @ 99.61% 3y · 1689 @ 93.19% 5y | **YES — primary fill** | Annotate always; **lists when board empty** + new live_fire | Held 1y clip ~351 @ 99.43% |
| **P2F** desks | FINAL confirm PASS · high floors V11…P75 | **Tags only** | Annotate / UI merge | Does not replace dual ticket |
| **P2G 10m** desks | FINAL measured Lo–Hi ranges | **Tags only** | Annotate / UI merge | Does not replace dual ticket |
| **5m dual champion** | Research cache ~35% 1y | **No** (as list track) | Not primary | — |
| **10m dual champion** | Packs-on-10m ~36% 1y | Fill channel only via CHAMP engine streams | Silent fill possible | Mixed into CHAMP_PLUS streams, not dual board name |
| **Accurate proven book** (15m+10m proven) | `research/nifty_fno` **29 @ 96.6%** 1y | **No** | Research folder only | Not wired |
| **Ranked desk** proven→champ→ORB | 30d ranked 10 @ 60% | **No** | Research only | Not wired |
| **ORB / trend / state / minute guide** | Various 1m reports | **No** | Research only | Not wired |
| **STACK / AGREE / ExtraTrees** | Explicitly excluded from FINAL | **OFF** | Flags default off | — |

---

## 4 · Research logics & reports (the “tested” ones)

### A · CHAMP_PLUS (the high one people mean by “champion research”)

| | |
|---|---|
| **Logic** | Champion seed + ticket-fill streams · ±30 · cap 4 same-side |
| **Tag** | `CHAMP_PLUS_T30SL30_CAP4` · `ACC_RANGE_93_100` |
| **1y** | **374 @ 99.47%** |
| **3y** | **1028 @ 99.61%** |
| **5y** | **1689 @ 93.19%** |
| **Reports** | `reports/5y/CHAMPION_PLUS_T30_SL30_5Y.md` · `reports/3y/...` · `reports/1y/CHAMP_PLUS_LIVE_ENGINE_CONFIRM.md` |
| **Code** | `logic/champ_plus_live.py` · `champ_plus_engine.py` |
| **Live gap** | Not the default list track; dual `champion` usually occupies the board |

### B · Dual champion seed only

| | |
|---|---|
| **Logic** | 15m dual pack champion floors only |
| **1y** | ~40–41 @ **~92.5%** |
| **Report** | `reports/1y/CHAMPION_ONLY_1Y.md` |
| **Live** | This family **does** list (as track=`champion`) |

### C · Accurate proven research book (new folder)

| | |
|---|---|
| **Logic** | 15m proven → 10m proven fill · **no champion** |
| **1y** | **29 @ 96.6%** (+1204) |
| **Report** | `research/nifty_fno/reports/PROVEN_ACCURATE_1Y.md` |
| **Live** | **Not wired** |

### D · FINAL 3-book confirm (annotate registry)

| | |
|---|---|
| **Books** | P2F · P2G · CHAMP_PLUS |
| **Report** | `reports/1y/FINAL_NIFTY_3BOOKS_CONFIRM.md` · Verdict **PASS** |
| **Live** | Annotate path ON; listing still dual-first |

### E · Dual champion ≠ 5m/10m champion

| TF | 1y dual-cache hit (approx) |
|---|---|
| 15m champion | ~92% |
| 5m champion | ~35% |
| 10m champion | ~36% |

Report: `research/nifty_fno/reports/CHAMPION_VS_CHAMP_PLUS.md`

---

## 5 · Live test / confirm reports

| Report | What it tested | Result |
|---|---|---|
| `FINAL_NIFTY_3BOOKS_CONFIRM.md` | P2F+P2G+CHAMP_PLUS registry / stamps | **PASS** |
| `CHAMP_PLUS_LIVE_ENGINE_CONFIRM.md` | Live ticket-fill can fire a day | **PASS** (e.g. 2026-11-13) |
| `NIFTY_LIVE_LOGIC_2M.md` | Live session logic snapshot (2m) | Exists under reports/1y |
| Dual live 1y CSVs | `nifty_live_dual_1y_calls.csv` | Dual board path history |
| Ranked desk 30d | Dual+ORB ranked guide | Research only · 10 @ 60% |

---

## 6 · Extra logic on live (beyond a single research book)

These run in production **in addition to** dual listing:

1. **FINAL annotate** — P2F / P2G / CHAMP tags on the session payload  
2. **CHAMP_PLUS live engine** — can append fires to a ledger; lists only if Calls empty  
3. **Dual modal fill** — CHAMP_PLUS added → else crown_5m  
4. **Champion live clip** — SL20/T30 on dual champion (research CHAMP_PLUS is ±30)  
5. **UI combine** — same (day,side,hm) merge tags accuracy-first  
6. **Morning context** — bias/H-L · no BUY/SELL  
7. Optional (OFF): stacked calls, pre-dual good, ExtraTrees, NSE mid gate  

---

## 7 · Why it feels like “research not on live”

You tested / locked **CHAMP_PLUS @ ~99%** and **proven @ ~100%**.  
Live Calls usually show **dual `champion` @ ~92%** because:

1. Dual fires first and **opens the ticket**  
2. CHAMP_PLUS fill **refuses to list** while a call is open  
3. Docs for FINAL books sound like “only these emit,” but **ws_rescore listing is dual**

So research CHAMP_PLUS **is present in code**, but **not the primary live listing logic**.

---

## 8 · If goal = “only tested research on live listing”

Candidate accurate list stack (research-backed):

| Priority | Logic | 1y research |
|---:|---|---|
| 1 | Dual **proven_100** 15m | ~24 @ 100% |
| 2 | **CHAMP_PLUS** (not raw dual champion) | 374 @ 99.47% |
| 3 | Optional: proven **10m** fill | 5 @ 80% |

**Remove / demote from listing:** raw dual `champion`, 5m/10m champion, ORB/minute/state unless separately promoted.

That wiring change is **not done yet** — this file is the map only.

---

## 9 · File map

| Need | Path |
|---|---|
| This comparison | `prod_live/research/nifty_fno/reports/LIVE_VS_RESEARCH_COMPLETE.md` |
| CHAMP_PLUS vs dual champion | `.../CHAMPION_VS_CHAMP_PLUS.md` |
| Accurate proven 1y | `.../PROVEN_ACCURATE_1Y.md` |
| CHAMP_PLUS 5y research | `prod_live/reports/5y/CHAMPION_PLUS_T30_SL30_5Y.md` |
| FINAL confirm | `prod_live/reports/1y/FINAL_NIFTY_3BOOKS_CONFIRM.md` |
| Live list code | `app/fno/fno_ws_rescore.py` · `nifty_live_dual_track.py` · `fno_dual_modal_list.py` |
| FINAL annotate | `app/fno/fno_p2f_live.py` · `prod_live/adapters/live_session_final.py` |
