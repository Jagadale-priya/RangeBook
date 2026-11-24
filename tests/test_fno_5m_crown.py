"""Unit tests for independent 5m crown channel."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

import crown_5m_store as store
import fno_5m_crown as crown


def _toy_5m(n: int = 80) -> pd.DataFrame:
    idx = pd.date_range("2026-10-01 09:15", periods=n, freq="5min", tz="Asia/Kolkata")
    # session-only-ish: keep consecutive for toy
    px = 22000.0
    rows = []
    for i, ts in enumerate(idx):
        o = px
        c = px + (2 if i > 5 else -1)
        rows.append({"Open": o, "High": max(o, c) + 5, "Low": min(o, c) - 5, "Close": c, "Volume": 1000})
        px = c
    return pd.DataFrame(rows, index=idx)


def test_enabled_default():
    assert crown.enabled() is True


def test_crown_tag():
    t = crown.crown_tag()
    assert t["code"] == "5m_crown"
    assert t["label"] == "5m crown"


def test_soft_sr_optional():
    assert crown.soft_sr_ok("BUY", None) is True
    assert crown.soft_sr_ok("BUY", 0.15) is True
    assert crown.soft_sr_ok("BUY", 0.01) is False
    assert crown.soft_sr_ok("SELL", -0.15) is True
    assert crown.soft_sr_ok("SELL", 0.01) is False


def test_store_upsert_and_claim(tmp_path: Path):
    db = str(tmp_path / "t.db")
    sig = {
        "symbol": "NIFTY",
        "bar_time": "2026-11-06T11:20:00+05:30",
        "decision": "BUY",
        "entry": 24600.0,
        "stop_loss": 24550.0,
        "target_1": 24680.0,
        "p_t1": 0.6,
        "accuracy_label": "5m crown",
        "accuracy_tags": [crown.crown_tag()],
        "session_date": "2026-11-06",
    }
    a = store.upsert_signal(sig, db_path=db)
    assert a["ok"] and a["created"]
    b = store.upsert_signal(sig, db_path=db)
    assert b["ok"] and not b["created"]
    rid = int(a["id"])
    assert store.claim_notify(rid, db_path=db) is True
    assert store.claim_notify(rid, db_path=db) is False
    assert store.count_today("NIFTY", "2026-11-06", side="BUY", db_path=db) == 1


def test_evaluate_bad_symbol_returns_none():
    assert crown.evaluate_latest("RELIANCE", _toy_5m()) is None


def test_evaluate_handles_empty_bars():
    assert crown.evaluate_latest("NIFTY", None) is None
    assert crown.evaluate_latest("NIFTY", pd.DataFrame()) is None


def test_attach_never_raises():
    result: dict = {}
    out = crown.attach_to_result(result, "NIFTY", None)
    assert "ok" in out


def test_packs_dir_points_to_extratrees():
    assert "crown_5m_packs" in str(crown.PACK_DIR)
    assert crown.EXPECTED_HIT_PCT >= 70.0


def test_evaluate_without_packs_returns_none(monkeypatch):
    monkeypatch.setattr(crown, "load_pack", lambda *_a, **_k: None)
    assert crown.evaluate_latest("NIFTY", _toy_5m()) is None
