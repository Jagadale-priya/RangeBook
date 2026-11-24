"""Optional FinBERT headline tone. Falls back to None if the model is not on disk.

Does not download during unit tests. Set FINBERT=1 to allow a first-time download.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

_pipe = None
_tried = False


def _allow_download() -> bool:
    return os.environ.get("FINBERT", "").strip().lower() in ("1", "true", "yes")


def _get_pipe():
    global _pipe, _tried
    if _tried:
        return _pipe
    _tried = True
    if os.environ.get("FINBERT", "").strip().lower() in ("0", "false", "no"):
        return None
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, TextClassificationPipeline
    except Exception:
        return None

    def _load(local: bool):
        tok = AutoTokenizer.from_pretrained("ProsusAI/finbert", local_files_only=local)
        model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert", local_files_only=local)
        return TextClassificationPipeline(model=model, tokenizer=tok, truncation=True, max_length=64)

    try:
        _pipe = _load(True)
        return _pipe
    except Exception:
        if not _allow_download():
            _pipe = None
            return None
        try:
            _pipe = _load(False)
        except Exception:
            _pipe = None
    return _pipe


def score_news_items(news_items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the same shape as keyword scoring, or None to use keywords."""
    if not news_items:
        return None
    pipe = _get_pipe()
    if pipe is None:
        return None
    texts = []
    for item in news_items[:12]:
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        texts.append((title + ". " + summary).strip()[:400] or title)
    if not any(texts):
        return None
    try:
        raw = pipe(texts)
    except Exception:
        return None
    delta = 0.0
    highlights: List[str] = []
    for item, pred in zip(news_items[:12], raw):
        row = pred
        if isinstance(pred, list) and pred:
            row = max(pred, key=lambda x: float((x or {}).get("score") or 0))
        label = str((row or {}).get("label") or "").lower()
        score = float((row or {}).get("score") or 0)
        title = str(item.get("title") or "")[:100]
        if "pos" in label:
            delta += min(3.0, 4.0 * score)
            highlights.append(f"Positive news: {title}")
        elif "neg" in label:
            delta -= min(3.0, 4.0 * score)
            highlights.append(f"Risk news: {title}")
    delta = max(-12.0, min(12.0, delta))
    tone = "BULLISH" if delta >= 3 else ("BEARISH" if delta <= -3 else "NEUTRAL")
    return {
        "score_delta": round(delta, 2),
        "tone": tone,
        "highlights": highlights[:5],
        "source": "finbert",
    }
