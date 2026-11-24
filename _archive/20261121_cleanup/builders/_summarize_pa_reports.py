from pathlib import Path
import re

p = Path("prod_live/reports/1y")
files = sorted(p.glob("PA_*.md"), key=lambda f: f.stat().st_mtime)
for f in files:
    text = f.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().splitlines()
    title = lines[0] if lines else f.name
    print("=" * 70)
    print(f.name)
    print(title[:140])
    # key lines
    keys = (
        "BASE",
        "Wire",
        "Wired",
        "BEST",
        "Recommendation",
        "Live lock",
        "Locked",
        "hit=",
        "hit=",
    )
    shown = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if any(k.lower() in s.lower() for k in ("base", "wire", "best", "lock", "recommend", "**BASE**", "hit=")):
            if s.startswith("|") and "hit" not in s.lower() and "BASE" not in s and "Wire" not in s:
                continue
            print(" ", s[:160])
            shown += 1
            if shown >= 12:
                break
    print()
