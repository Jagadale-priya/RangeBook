# Phase-2f — keep pushing @ same accuracy

**Phase-1 LOCKED · Phase-2c HELD.** Seeds from salvaged Phase-2e partial.
New axes: micro-bands · weekday · mid pick · triple-CF.

Tags=255020 · perfect=111194 · elapsed 16064.6s

## Day-dedupe vs held / P2e

| Desk | Floor | P1 | P2c* | P2e | **P2f** | ΔP2e | Hit | Candidate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5` | 100 | 141 | 199 | 241 | **291** | +50 | 100.0 | `ACC100_MULTI_V11` |
| `ACC_WIDE_P92` | 99.24 | 131 | 203 | 243 | **292** | +49 | 99.6575 | `ACC_WIDE_P92_P2F` |
| `ACC_WIDE_P90` | 95.4 | 174 | 237 | 274 | **303** | +29 | 96.6997 | `ACC_WIDE_P90_P2F` |
| `ACC_WIDE_P85` | 89.69 | 223 | 293 | 317 | **326** | +9 | 89.8773 | `ACC_WIDE_P85_P2F` |
| `ACC_WIDE_P85B` | 88.4 | 250 | 303 | 329 | **342** | +13 | 88.5965 | `ACC_WIDE_P85B_P2F` |
| `ACC_WIDE_P80` | 84.72 | 301 | 341 | 360 | **375** | +15 | 84.8 | `ACC_WIDE_P80_P2F` |
| `ACC_WIDE_P75` | 82.71 | 347 | 372 | 382 | **386** | +4 | 82.9016 | `ACC_WIDE_P75_P2F` |

## Cap2

| Desk | P1 | P2e | **P2f** | ΔP2e | Hit | Candidate |
|---|---:|---:|---:|---:|---:|---|
| `ACC100_MULTI_V5_CAP2` | 141 | 325 | **417** | +92 | 100.0 | `ACC100_MULTI_V5_CAP2_P2F` |
| `ACC_WIDE_P92_CAP2` | 131 | 327 | **418** | +91 | 99.7608 | `ACC_WIDE_P92_CAP2_P2F` |
| `ACC_WIDE_P90_CAP2` | 174 | 370 | **434** | +64 | 97.235 | `ACC_WIDE_P90_CAP2_P2F` |
| `ACC_WIDE_P85_CAP2` | 223 | 447 | **472** | +25 | 89.8305 | `ACC_WIDE_P85_CAP2_P2F` |

*P2c = held in `holding_accurate/recipes.json`

JSON: `ACC_PHASE2F_KEEP_PUSHING.json`
