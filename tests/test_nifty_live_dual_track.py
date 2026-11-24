"""Tests for NIFTY champion→calls / baseline→suggestions dual-track live wiring."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import fno_session_rules as fsrules
import nifty_live_dual_track as dual
import session_calls


def _bars_first_up(day="2026-10-20", start=23000.0, break_at=1):
    """15m session: bar0 sets OR, bar break_at closes above OR high."""
    idx = pd.date_range(f"{day} 09:15", periods=8, freq="15min", tz="Asia/Kolkata")
    close = np.full(8, start, dtype=float)
    high = np.full(8, start + 5.0, dtype=float)
    low = np.full(8, start - 5.0, dtype=float)
    # First bar OR
    high[0], low[0], close[0] = start + 10.0, start - 10.0, start
    # Break up
    close[break_at] = start + 25.0
    high[break_at] = start + 30.0
    low[break_at] = start + 15.0
    for i in range(break_at + 1, 8):
        close[i] = start + 28.0
        high[i] = start + 32.0
        low[i] = start + 20.0
    return pd.DataFrame(
        {"Open": close - 1.0, "High": high, "Low": low, "Close": close, "Volume": 1000.0},
        index=idx,
    )


def _bars_first_dn(day="2026-10-20", start=23000.0, break_at=1, cont_ext=0.25):
    """Down break with mild continuation extension (champion cont window 0.15–0.40)."""
    idx = pd.date_range(f"{day} 09:15", periods=10, freq="15min", tz="Asia/Kolkata")
    or_hi, or_lo = start + 10.0, start - 10.0
    width = or_hi - or_lo
    # First break just under OR low; later bars extend by cont_ext * OR width.
    first_close = or_lo - 0.05 * width
    cont_close = or_lo - float(cont_ext) * width
    close = np.full(10, start, dtype=float)
    high = np.full(10, start + 5.0, dtype=float)
    low = np.full(10, start - 5.0, dtype=float)
    high[0], low[0], close[0] = or_hi, or_lo, start
    close[break_at] = first_close
    high[break_at] = or_lo + 1.0
    low[break_at] = first_close - 2.0
    for i in range(break_at + 1, 10):
        close[i] = cont_close
        high[i] = cont_close + 3.0
        low[i] = cont_close - 3.0
    return pd.DataFrame(
        {"Open": close + 1.0, "High": high, "Low": low, "Close": close, "Volume": 1000.0},
        index=idx,
    )


def _scored(decision="BUY", p_t1=0.72, regime="range", entry=23020.0):
    stop = entry - 40.0 if decision == "BUY" else entry + 40.0
    t1 = entry + 60.0 if decision == "BUY" else entry - 60.0
    return {
        "decision": decision,
        "entry": entry,
        "stop_loss": stop,
        "target_1": t1,
        "p_t1": p_t1,
        "p_sl": round(1.0 - p_t1, 4),
        "features": {f"regime_{regime}": 1.0},
        "regime": regime,
        "head": {"decision": decision, "p_t1": p_t1, "features": {f"regime_{regime}": 1.0}},
        "snap": {},
    }


class ChampionBaselineGatesTests(unittest.TestCase):
    def test_buy_champion_requires_first_break_and_range_or_mixed(self):
        self.assertTrue(
            dual.champion_ok(
                decision="BUY",
                first_break=True,
                regime="range",
                p_t1=0.55,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=False,
            )
        )
        self.assertTrue(
            dual.champion_ok(
                decision="BUY",
                first_break=True,
                regime="mixed",
                p_t1=0.55,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.champion_ok(
                decision="BUY",
                first_break=True,
                regime="trend",
                p_t1=0.90,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.champion_ok(
                decision="BUY",
                first_break=False,
                regime="range",
                p_t1=0.90,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=False,
            )
        )

    def test_buy_champion_min_p_is_0_55(self):
        # Live replace: BUY floor 0.50 → 0.55 (3y research toxic bucket).
        self.assertEqual(dual.CHAMPION_BUY_MIN_P, 0.55)
        self.assertFalse(
            dual.champion_ok(
                decision="BUY",
                first_break=True,
                regime="range",
                p_t1=0.54,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=False,
            )
        )
        self.assertTrue(
            dual.champion_ok(
                decision="BUY",
                first_break=True,
                regime="range",
                p_t1=0.55,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=False,
            )
        )

    def test_sell_champion_first_break_or_cont_window(self):
        # First break SELL always ok at p>=0.58
        self.assertTrue(
            dual.champion_ok(
                decision="SELL",
                first_break=True,
                regime="trend",
                p_t1=0.60,
                or_ext=0.9,
                mins=14 * 60,
                skip_after_sl=False,
            )
        )
        # Cont: or_ext in [0.15, 0.40] and before 12:30
        self.assertTrue(
            dual.champion_ok(
                decision="SELL",
                first_break=False,
                regime="trend",
                p_t1=0.60,
                or_ext=0.25,
                mins=11 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.champion_ok(
                decision="SELL",
                first_break=False,
                regime="trend",
                p_t1=0.60,
                or_ext=0.10,
                mins=11 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.champion_ok(
                decision="SELL",
                first_break=False,
                regime="trend",
                p_t1=0.60,
                or_ext=0.25,
                mins=13 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.champion_ok(
                decision="SELL",
                first_break=True,
                regime="trend",
                p_t1=0.50,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=False,
            )
        )

    def test_skip_after_sl_blocks_champion_only(self):
        self.assertFalse(
            dual.champion_ok(
                decision="BUY",
                first_break=True,
                regime="range",
                p_t1=0.80,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=True,
            )
        )
        # Baseline still allows BUY first break
        self.assertTrue(
            dual.baseline_ok(decision="BUY", first_break=True, p_t1=0.55)
        )

    def test_baseline_buy_needs_first_break_sell_needs_p(self):
        # Research gate: BUY first-break only (no live BUY continuation).
        self.assertTrue(dual.baseline_ok(decision="BUY", first_break=True, p_t1=0.50))
        self.assertFalse(
            dual.baseline_ok(decision="BUY", first_break=False, p_t1=0.90, or_ext=0.02)
        )
        self.assertFalse(
            dual.baseline_ok(
                decision="BUY", first_break=False, p_t1=0.90, or_ext=0.10, mins=11 * 60
            )
        )
        self.assertTrue(dual.baseline_ok(decision="SELL", first_break=False, p_t1=0.58))
        self.assertFalse(dual.baseline_ok(decision="SELL", first_break=True, p_t1=0.57))

    def test_last_closed_was_sl(self):
        self.assertTrue(
            dual._last_closed_was_sl({"history": [{"status": "sl_before_t1"}]})
        )
        self.assertTrue(
            dual._last_closed_was_sl({"status": "same_bar_both", "history": []})
        )
        self.assertFalse(
            dual._last_closed_was_sl({"history": [{"status": "hit_t1"}]})
        )
        self.assertFalse(dual._last_closed_was_sl(None))


class AccuracyTagsTests(unittest.TestCase):
    def test_champion_and_baseline_both_tagged(self):
        tags = dual.build_tags(proven_100=False, champion=True, baseline=True, decision="BUY")
        codes = [t["code"] for t in tags]
        self.assertIn("most_accurate", codes)
        self.assertIn("side_accuracy", codes)
        self.assertIn("lower_accuracy", codes)
        most = next(t for t in tags if t["code"] == "most_accurate")
        self.assertAlmostEqual(most["expected_hit_pct"], dual.CHAMPION_HIT_PCT)
        self.assertEqual(most["tone"], "champion")
        self.assertIn("Priority", most["label"])
        side = next(t for t in tags if t["code"] == "side_accuracy")
        self.assertIn("87", side["label"])

    def test_baseline_only_tags(self):
        tags = dual.build_tags(proven_100=False, champion=False, baseline=True, decision="SELL")
        codes = [t["code"] for t in tags]
        self.assertNotIn("most_accurate", codes)
        self.assertIn("lower_accuracy", codes)
        self.assertIn("baseline_accuracy", codes)
        self.assertTrue(
            any(
                "63%" in t["label"]
                or "62.7" in (t.get("detail") or "")
                or "About" in t["label"]
                for t in tags
            )
        )

    def test_proven_100_tag_is_confident(self):
        tags = dual.build_tags(proven_100=True, champion=True, baseline=True, decision="BUY")
        codes = [t["code"] for t in tags]
        self.assertEqual(codes[0], "proven_100")
        proven = tags[0]
        self.assertEqual(proven["label"], "Priority · Confident 100%")
        self.assertEqual(proven["tone"], "proven")
        self.assertEqual(proven["priority"], 10)
        self.assertAlmostEqual(proven["expected_hit_pct"], 100.0)


class Proven100GatesTests(unittest.TestCase):
    def test_buy_proven_needs_tight_ext_and_p(self):
        self.assertTrue(
            dual.proven_100_ok(
                decision="BUY",
                first_break=True,
                regime="range",
                p_t1=0.62,
                or_ext=0.10,
                mins=12 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.proven_100_ok(
                decision="BUY",
                first_break=True,
                regime="range",
                p_t1=0.62,
                or_ext=0.11,
                mins=12 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.proven_100_ok(
                decision="BUY",
                first_break=True,
                regime="trend",
                p_t1=0.90,
                or_ext=0.05,
                mins=12 * 60,
                skip_after_sl=False,
            )
        )

    def test_sell_proven_first_trend_only(self):
        self.assertTrue(
            dual.proven_100_ok(
                decision="SELL",
                first_break=True,
                regime="trend",
                p_t1=0.58,
                or_ext=0.9,
                mins=14 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.proven_100_ok(
                decision="SELL",
                first_break=False,
                regime="trend",
                p_t1=0.90,
                or_ext=0.25,
                mins=11 * 60,
                skip_after_sl=False,
            )
        )
        self.assertFalse(
            dual.proven_100_ok(
                decision="SELL",
                first_break=True,
                regime="range",
                p_t1=0.90,
                or_ext=0.2,
                mins=10 * 60,
                skip_after_sl=False,
            )
        )


class EvaluatePayloadTests(unittest.TestCase):
    def test_champion_buy_emits_call_and_suggestion(self):
        bars = _bars_first_up()
        asof = bars.index[1]
        scored = _scored("BUY", p_t1=0.70, regime="range", entry=23025.0)

        with patch.object(dual, "packs_available", return_value=True), patch.object(
            dual,
            "load_packs",
            return_value={"buy": {"model": object()}, "sell": {"model": object()}, "sell_cont": {"model": object()}},
        ), patch.object(dual, "_score_side", return_value=scored):
            ev = dual.evaluate(bars, asof=asof, price=23025.0)

        self.assertTrue(ev["available"])
        self.assertTrue(ev["champion"])
        self.assertFalse(ev["baseline"])
        self.assertEqual(ev["decision"], "BUY")
        self.assertIsNotNone(ev["call_payload"])
        # Wide first-up break is champion, not proven-100 (or_ext too large).
        self.assertFalse(ev.get("proven_100"))
        self.assertEqual(ev["call_payload"]["track"], "champion")
        self.assertIsNotNone(ev["suggestion_payload"])
        self.assertTrue(ev["suggestion_payload"]["dual_track"])
        self.assertEqual(ev["model_view"]["p_t1"], 0.70)
        self.assertAlmostEqual(ev["model_view"]["p_sl"], 0.30, places=3)
        self.assertIn("T1", ev["model_view"]["message"])
        codes = [t["code"] for t in ev["tags"]]
        self.assertIn("most_accurate", codes)

    def test_proven_100_buy_gets_confident_tag_and_priority(self):
        # Mild up-break so or_ext ≤ 0.10 for proven gate.
        bars = _bars_first_up()
        # Force tiny extension: OR width 20, close only +2 above OR high → ext=0.1
        start = 23000.0
        bars.loc[bars.index[1], "Close"] = start + 12.0  # or_hi=start+10 → ext=0.1
        bars.loc[bars.index[1], "High"] = start + 13.0
        bars.loc[bars.index[1], "Low"] = start + 8.0
        asof = bars.index[1]
        scored = _scored("BUY", p_t1=0.70, regime="range", entry=23012.0)

        with patch.object(dual, "packs_available", return_value=True), patch.object(
            dual,
            "load_packs",
            return_value={"buy": {"model": object()}, "sell": {"model": object()}, "sell_cont": None},
        ), patch.object(dual, "_score_side", return_value=scored):
            ev = dual.evaluate(bars, asof=asof, price=23012.0)

        self.assertTrue(ev["proven_100"])
        self.assertEqual(ev["call_payload"]["track"], "proven_100")
        self.assertEqual(ev["call_payload"]["list_priority"], 0)
        self.assertIn("Priority · Confident 100%", ev["call_payload"]["accuracy_label"])
        codes = [t["code"] for t in ev["tags"]]
        self.assertIn("proven_100", codes)
        proven = next(t for t in ev["tags"] if t["code"] == "proven_100")
        self.assertEqual(proven["label"], "Priority · Confident 100%")
        # Red risk leads when baseline also tags; else Priority green leads
        if any(str(c).startswith("sl_risk_") and c != "sl_risk_ok" for c in codes):
            self.assertTrue(str(ev["tags"][0]["code"]).startswith("sl_risk_"))
            self.assertEqual(ev["tags"][0]["tone"], "risk")
        else:
            self.assertEqual(ev["tags"][0]["code"], "proven_100")

    def test_trend_buy_first_break_baseline_retired_no_call(self):
        bars = _bars_first_up()
        asof = bars.index[1]
        scored = _scored("BUY", p_t1=0.66, regime="trend", entry=23025.0)

        with patch.object(dual, "packs_available", return_value=True), patch.object(
            dual,
            "load_packs",
            return_value={"buy": {"model": object()}, "sell": {"model": object()}, "sell_cont": None},
        ), patch.object(dual, "_score_side", return_value=scored):
            ev = dual.evaluate(bars, asof=asof, price=23025.0)

        # Baseline would have qualified historically; live desk no longer lists it.
        self.assertFalse(ev["available"])
        self.assertEqual(ev.get("reason"), "gates_fail")
        self.assertFalse(ev.get("baseline"))
        self.assertIsNone(ev.get("call_payload"))
        self.assertIsNone(ev.get("suggestion_payload"))

    def test_sell_cont_champion_uses_cont_pack_and_levels(self):
        bars = _bars_first_dn(break_at=1)
        # asof on later bar = continuation (not first break)
        asof = bars.index[3]
        scored = _scored("SELL", p_t1=0.65, regime="trend", entry=22970.0)

        with patch.object(dual, "packs_available", return_value=True), patch.object(
            dual,
            "load_packs",
            return_value={"buy": {"model": object()}, "sell": {"model": object()}, "sell_cont": {"model": object()}},
        ), patch.object(dual, "_score_side", return_value=scored) as score_mock:
            ev = dual.evaluate(bars, asof=asof, price=22970.0)

        self.assertTrue(ev["available"])
        self.assertTrue(ev["champion"], msg=ev)
        self.assertEqual(ev["model_view"]["head"], "SELL_CONT_Q")
        self.assertEqual(ev["call_payload"]["stop_loss"], scored["stop_loss"])
        self.assertEqual(ev["call_payload"]["target_1"], scored["target_1"])
        self.assertTrue(score_mock.called)

    def test_skip_after_sl_drops_champion_no_baseline_fallback(self):
        bars = _bars_first_up()
        asof = bars.index[1]
        scored = _scored("BUY", p_t1=0.70, regime="range")
        ticket = {"history": [{"status": "sl_before_t1"}]}

        with patch.object(dual, "packs_available", return_value=True), patch.object(
            dual,
            "load_packs",
            return_value={"buy": {"model": object()}, "sell": {"model": object()}, "sell_cont": None},
        ), patch.object(dual, "_score_side", return_value=scored):
            ev = dual.evaluate(bars, asof=asof, session_ticket=ticket, price=23025.0)

        self.assertFalse(ev["available"])
        self.assertEqual(ev.get("reason"), "gates_fail")
        self.assertFalse(ev.get("champion"))
        self.assertFalse(ev.get("baseline"))
        self.assertIsNone(ev.get("call_payload"))

    def test_no_or_break_unavailable(self):
        bars = _bars_first_up()
        # asof on OR bar — no break yet
        asof = bars.index[0]
        with patch.object(dual, "packs_available", return_value=True), patch.object(
            dual,
            "load_packs",
            return_value={"buy": {"model": object()}, "sell": {"model": object()}, "sell_cont": None},
        ):
            ev = dual.evaluate(bars, asof=asof)
        self.assertFalse(ev["available"])
        self.assertEqual(ev.get("reason"), "no_or_break")

    def test_gates_fail_when_p_too_low(self):
        bars = _bars_first_up()
        asof = bars.index[1]
        scored = _scored("BUY", p_t1=0.40, regime="range")
        with patch.object(dual, "packs_available", return_value=True), patch.object(
            dual,
            "load_packs",
            return_value={"buy": {"model": object()}, "sell": {"model": object()}, "sell_cont": None},
        ), patch.object(dual, "_score_side", return_value=scored):
            ev = dual.evaluate(bars, asof=asof)
        self.assertFalse(ev["available"])
        self.assertEqual(ev.get("reason"), "gates_fail")


class ApplyAndStampTests(unittest.TestCase):
    def test_apply_sets_suggestion_and_head_overlay(self):
        bars = _bars_first_up()
        asof = bars.index[1]
        scored = _scored("BUY", p_t1=0.71, regime="range")
        result = {"fno_analysis": {"decision": "HOLD"}, "fno_model": {"p_t1": 0.4}}

        with patch.object(dual, "packs_available", return_value=True), patch.object(
            dual,
            "load_packs",
            return_value={"buy": {"model": object()}, "sell": {"model": object()}, "sell_cont": None},
        ), patch.object(dual, "_score_side", return_value=scored):
            ev = dual.apply_to_analyze_result(
                result, bars=bars, asof=asof, session_ticket=None, price=23025.0
            )

        self.assertTrue(ev["champion"])
        self.assertTrue(result["suggestion"]["dual_track"])
        self.assertEqual(result["suggestion"]["decision"], "BUY")
        self.assertEqual(result["fno_model"]["source"], "nifty_dual_track")
        self.assertAlmostEqual(result["fno_model"]["p_t1"], 0.71)
        self.assertTrue(result["nifty_dual_track"]["champion"])

    def test_stamp_preserves_nifty_dual_track_suggestion(self):
        prior = {
            "dual_track": True,
            "decision": "SELL",
            "entry": 22900.0,
            "stop_loss": 22940.0,
            "target_1": 22840.0,
            "p_t1": 0.62,
            "p_sl": 0.38,
            "accuracy_tags": [{"code": "lower_accuracy", "label": "Lower accuracy · your risk"}],
            "model_view": {"message": "SELL via SELL: model T1 62% / SL 38%."},
            "track": "baseline",
        }
        result = {"suggestion": prior, "fno_analysis": {}}
        out = fsrules.stamp_call_suggestion(
            result,
            {"decision": "HOLD", "p_t1": 0.2},
            price=22900.0,
            symbol="NIFTY",
        )
        self.assertIs(out, prior)
        self.assertEqual(result["suggestion"]["decision"], "SELL")
        self.assertEqual(result["fno_analysis"]["suggestion"]["track"], "baseline")
        self.assertEqual(result["suggestion"]["model_view"]["message"].count("T1"), 1)

    def test_stamp_does_not_preserve_non_dual(self):
        result = {
            "suggestion": {"decision": "BUY", "dual_track": False, "entry": 1},
            "fno_analysis": {},
        }
        # Non-dual prior is replaced by live 5m path (None without bars).
        out = fsrules.stamp_call_suggestion(
            result,
            None,
            price=100.0,
            symbol="NIFTY",
        )
        self.assertIs(result["suggestion"], out)
        self.assertIsNone(out)


class SessionCallsNormalizeTests(unittest.TestCase):
    def test_normalize_exposes_tags_and_model_view(self):
        raw = {
            "decision": "BUY",
            "status": "open",
            "entry": 23000,
            "stop_loss": 22950,
            "target_1": 23080,
            "p_t1": 0.7,
            "taken_at": "2026-10-20T10:00:00+05:30",
            "readings": {
                "accuracy_tags": [{"code": "most_accurate", "label": "Most accurate"}],
                "model_view": {"p_t1": 0.7, "p_sl": 0.3, "message": "BUY"},
                "p_sl": 0.3,
                "dual_track": True,
                "accuracy_label": "Most accurate · ~83% T1",
            },
        }
        row = session_calls._normalize_row(raw, 1, "2026-10-20", closed=False)
        self.assertTrue(row["dual_track"])
        self.assertEqual(row["accuracy_tags"][0]["code"], "most_accurate")
        self.assertEqual(row["model_view"]["p_sl"], 0.3)
        self.assertEqual(row["p_sl"], 0.3)
        self.assertIn("83%", row["accuracy_label"])

    def test_row_from_db_promotes_readings_tags(self):
        payload = {
            "readings": {
                "accuracy_tags": [{"code": "lower_accuracy", "label": "Lower accuracy · your risk"}],
                "model_view": {"p_t1": 0.6, "p_sl": 0.4},
                "dual_track": True,
                "accuracy_label": "Lower accuracy · ~63% T1 · your risk",
            }
        }
        fake = {
            "ticket_n": 2,
            "status": "open",
            "taken_at": "2026-10-20T11:00:00+05:30",
            "closed_at": None,
            "payload_json": json.dumps(payload),
            "entry": 100.0,
            "stop_loss": 90.0,
            "target_1": 110.0,
            "p_t1": 0.6,
            "p_meta": 0.6,
            "regime": "range",
            "exit_price": None,
            "exit_source": None,
            "points": None,
            "status_plain": None,
        }
        row = session_calls._row_from_db(fake)
        self.assertEqual(row["accuracy_tags"][0]["code"], "lower_accuracy")
        self.assertTrue(row["dual_track"])
        self.assertEqual(row["model_view"]["p_sl"], 0.4)


class OrStateTests(unittest.TestCase):
    def test_or_state_detects_first_up_and_cont(self):
        bars = _bars_first_up()
        st1 = dual._or_state(bars, bars.index[1])
        self.assertTrue(st1["up"])
        self.assertTrue(st1["first_break"])
        st2 = dual._or_state(bars, bars.index[3])
        self.assertTrue(st2["up"])
        self.assertFalse(st2["first_break"])
        self.assertGreater(st2["or_ext"], 0)


class RegimeTests(unittest.TestCase):
    def test_regime_from_feat(self):
        self.assertEqual(dual.regime_from_feat({"regime_volatile": 1}), "volatile")
        self.assertEqual(dual.regime_from_feat({"regime_trend": 1}), "trend")
        self.assertEqual(dual.regime_from_feat({"regime_range": 1}), "range")
        self.assertEqual(dual.regime_from_feat({}), "mixed")


if __name__ == "__main__":
    unittest.main()
