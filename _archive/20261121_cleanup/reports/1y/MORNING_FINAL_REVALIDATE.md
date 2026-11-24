# Morning FINAL revalidation

**Promote:** `False`
**Bias held (≥70%):** `True` rule `fuse_us_asia abs>=6.5`
**Gap held:** `False`
**Walk:** min=0.5217 mean=0.686 ok=False
**Rolling mean:** 0.6758 ok=False

## Bias tests

- 1y: spoken **75.0%** cov 6.3% n=16
- 3y: spoken **71.7%** cov 6.1% n=46
- 5y: spoken **72.3%** cov 8.0% n=101

## Gap lean (not held)

- 1y: spoken **40.5%** cov 29.4% n=74
- 3y: spoken **38.6%** cov 27.4% n=207
- 5y: spoken **45.1%** cov 30.1% n=379

## Range

- 1y: containment **96.4%**
- 3y: containment **96.6%**
- 5y: containment **97.2%**

## Product guarantee

- **expected_high_low:** GUARANTEED ~96% containment
- **bias:** GUARANTEED >=70% when speaking (US+Asia fuse |s|>=6.5); else NEUTRAL
- **gap:** NOT guaranteed — emit gap_lean from same fuse at lower th, labeled lean
- **news:** Always analyze India+global headlines; veto bias if strong opposite news
- **confidence:** HIGH when bias held fires; LOW for gap_lean; ABSTAIN otherwise