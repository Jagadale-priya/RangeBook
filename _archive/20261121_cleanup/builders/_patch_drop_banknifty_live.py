"""One-shot: drop BANKNIFTY from live index tuples in hot paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

REPLACES = [
    (
        ROOT / "app" / "fno" / "fno_ws_rescore.py",
        [
            (
                'key in ("NIFTY", "BANKNIFTY", "SENSEX")',
                "fno_live_config.is_fno_live_index(key)",
            ),
            (
                'key not in ("NIFTY", "BANKNIFTY", "SENSEX")',
                "not fno_live_config.is_fno_live_index(key)",
            ),
            (
                "The 90-second refresh is for NIFTY, BANKNIFTY, and SENSEX. Press Analyze for a stock.",
                "The 90-second refresh is for NIFTY and SENSEX. Press Analyze for a stock.",
            ),
        ],
    ),
    (
        ROOT / "app" / "api" / "stock_signal_ml.py",
        [
            (
                'stock_key in ("NIFTY", "BANKNIFTY", "SENSEX")',
                "fno_live_config.is_fno_live_index(stock_key)",
            ),
            (
                'stock_key not in ("NIFTY", "BANKNIFTY", "SENSEX")',
                "not fno_live_config.is_fno_live_index(stock_key)",
            ),
            (
                'key not in ("NIFTY", "BANKNIFTY", "SENSEX")',
                "not fno_live_config.is_fno_live_index(key)",
            ),
            (
                'return jsonify({"error": "NIFTY, BANKNIFTY, or SENSEX only"}), 400',
                'return jsonify({"error": "NIFTY or SENSEX only"}), 400',
            ),
            (
                'print("  F&O live watch: NIFTY + BANKNIFTY + SENSEX every 30s (fast) + full Analyze every 15m.")',
                'print("  F&O live watch: NIFTY + SENSEX every 30s (fast) + full Analyze every 15m.")',
            ),
            (
                '    {"symbol": "BANKNIFTY", "name": "Bank Nifty Index", "sector": "Index"},\n',
                "",
            ),
        ],
    ),
]


def main() -> None:
    for path, pairs in REPLACES:
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            n = text.count(old)
            print(f"{path.name}: {n} × {old[:60]!r}")
            if n:
                text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
