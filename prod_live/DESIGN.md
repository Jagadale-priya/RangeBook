# Final desk — design diagram

**Package:** `prod_live` · **Status:** FINALIZED · **Symbol:** NIFTY

## 1. Session call flow

```mermaid
flowchart TD
  A[Session bars 5m + 15m] --> B[Channel scorers]
  B --> C1[PROVEN_100<br/>dual packs]
  B --> C2[GOOD_PROD2<br/>fno_NIFTY.pkl issued]
  B --> C3[CHAMPION<br/>floors BUY 0.55 / SELL 0.58]
  B --> C4[CROWN_DUAL_HTF<br/>crown pack + HTF_ACTIVE_DAY]

  C1 --> D[Stack union]
  C2 --> D
  C3 --> D
  C4 --> D

  D --> E{Priority sort<br/>proven > good > champ > crown}
  E --> F{Day cap 2<br/>same side only}
  F --> G[STACK_PLUS_CROWN_HTF_CAP2<br/>live volume calls]

  C2 --> H[Agree matcher]
  C1 --> H
  C3 --> H
  C4 --> H
  H --> I{Same day + side<br/>15m issued ∩ any 5m?}
  I -->|yes| J[Take best p_t1 5m entry]
  J --> K[AGREE_15M_ANY5]
  K --> L[Stamp accurate_tag on stack row<br/>if exact day+side+hm match]
  K --> M[Add as extra if not already in stack]

  G --> L
  L --> N[Desk output]
  M --> N
  N --> O[STACK_PLUS_AGREE_15M_ANY5]
```

## 2. Channel roles

```mermaid
flowchart LR
  subgraph Volume["Volume desk"]
    S[STACK_PLUS_CROWN_HTF_CAP2]
  end
  subgraph Accuracy["Accuracy channel"]
    A[AGREE_15M_ANY5]
  end
  S -->|stamp accurate_tag| T[Tagged calls ~91% 1y]
  A -->|rare extras| S
  S --> D[Live listing]
  T --> D
```

## 3. Model map

```mermaid
flowchart TB
  subgraph M15["15m model"]
    P[fno_NIFTY.pkl]
  end
  subgraph M5["5m models"]
    D1[dual BUY / SELL packs]
    CR[fno_NIFTY_crown_5m.pkl]
  end
  P --> GOOD[GOOD_PROD2]
  D1 --> PR[PROVEN_100]
  D1 --> CH[CHAMPION]
  CR --> CW[CROWN_DUAL_HTF]
  HTF[HTF_ACTIVE_DAY] --> CW
  GOOD --> STACK
  PR --> STACK
  CH --> STACK
  CW --> STACK[Stack cap2]
  GOOD --> AG[Agree]
  PR --> AG
  CH --> AG
  CW --> AG
```

## 4. Decision rules (short)

| Step | Rule |
|---|---|
| 1 | Score all four channels on the session |
| 2 | Drop crown unless `HTF_ACTIVE_DAY` |
| 3 | Sort by priority → higher `p_t1` → earlier time |
| 4 | Keep max **2** calls; lock **same side** after first pick |
| 5 | If issued 15m and any 5m share day+side → agree entry = best 5m `p_t1` |
| 6 | Stamp `accurate_tag=AGREE_15M_ANY5` when stack row equals that entry |
| 7 | NSE mid / daily fill / 15m classic standalone stay **OFF** |

## 5. Confirmed 1y snapshot

| Book | N | Hit |
|---|---:|---:|
| Live stack | 229 | 75.11% |
| Accurate tagged | 54 | 90.74% |
| Agree alone | 55 | 90.91% |

Detail: `reports/1y/LIVE_FINAL_1Y_MONTHS_ACCURATE.md`

---

## Holding (not finalized)

Stack + empty fill T35 is packaged separately — see **`HOLDING_DESIGN.md`** / **`HOLDING_LOGIC.md`**.  
Live cutover stays on this FINALIZED diagram until promote.
