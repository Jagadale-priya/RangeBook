"""F&O guidance (candles) and adverse-move alerts — do not flip decision on each candle."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _decision_bullish(decision: str) -> Optional[bool]:
    if "BUY" in (decision or "").upper():
        return True
    if "SELL" in (decision or "").upper():
        return False
    return None


def build_candle_guidance(candlestick: Dict[str, Any]) -> Dict[str, Any]:
    patterns = candlestick.get("patterns") or []
    bias = candlestick.get("bias") or "NEUTRAL"
    return {
        "bias": bias,
        "patterns": patterns,
        "score_delta": candlestick.get("score_delta"),
        "summary": (
            "; ".join(patterns[:3])
            if patterns
            else "No strong daily candle pattern — F&O leans on live tape + swing stack."
        ),
        "role": "guidance_only",
        "note": "Candlesticks guide and alert only; they do not alone change the F&O decision.",
    }


def build_adverse_alerts(
    decision: str,
    *,
    live_p: float,
    live_context: Optional[Dict[str, Any]] = None,
    candlestick: Optional[Dict[str, Any]] = None,
    current_price: Optional[float] = None,
    fno_trade_risk: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Alerts when fresh data is not favoring the anchored F&O direction."""
    if decision == "HOLD":
        return []

    side = _decision_bullish(decision)
    if side is None:
        return []

    alerts: List[Dict[str, Any]] = []
    ctx = live_context or {}
    session = ctx.get("session") or {}
    micro = ctx.get("microstructure") or {}

    if side and live_p < 0.46:
        alerts.append({
            "code": "LIVE_TAPE_WEAK",
            "severity": "warning",
            "message": f"Live probability up {live_p * 100:.1f}% — below comfort for a long F&O bias.",
        })
    elif not side and live_p > 0.54:
        alerts.append({
            "code": "LIVE_TAPE_WEAK",
            "severity": "warning",
            "message": f"Live probability up {live_p * 100:.1f}% — tape not supporting short F&O bias.",
        })

    if ctx.get("live_core_conflict"):
        alerts.append({
            "code": "SWING_LIVE_CONFLICT",
            "severity": "warning",
            "message": "Live session disagrees with swing model — review size or wait for full re-analyze.",
        })

    if session.get("available"):
        chg = float(session.get("change_from_open_pct") or 0)
        if side and chg < -0.25:
            alerts.append({
                "code": "SESSION_AGAINST",
                "severity": "critical",
                "message": f"Session {chg:+.2f}% from open — working against long F&O idea.",
            })
        elif not side and chg > 0.25:
            alerts.append({
                "code": "SESSION_AGAINST",
                "severity": "critical",
                "message": f"Session {chg:+.2f}% from open — working against short F&O idea.",
            })

    cs = candlestick or {}
    cb = cs.get("bias") or "NEUTRAL"
    patterns = cs.get("patterns") or []
    if side and cb == "BEARISH" and patterns:
        alerts.append({
            "code": "CANDLE_GUIDE_AGAINST",
            "severity": "info",
            "message": "Daily candle bias bearish — guidance only: " + patterns[0],
        })
    elif not side and cb == "BULLISH" and patterns:
        alerts.append({
            "code": "CANDLE_GUIDE_AGAINST",
            "severity": "info",
            "message": "Daily candle bias bullish — guidance only: " + patterns[0],
        })

    mb = micro.get("micro_bias") or "NEUTRAL"
    if micro.get("available"):
        if side and mb == "BEARISH":
            alerts.append({
                "code": "MICRO_5M_AGAINST",
                "severity": "warning",
                "message": f"5m micro bias bearish (score {micro.get('micro_score')}) — not favoring long.",
            })
        elif not side and mb == "BULLISH":
            alerts.append({
                "code": "MICRO_5M_AGAINST",
                "severity": "warning",
                "message": f"5m micro bias bullish (score {micro.get('micro_score')}) — not favoring short.",
            })

    trade = (fno_trade_risk or {}).get("fno_trade") or fno_trade_risk or {}
    sl = trade.get("stop_loss")
    if sl is not None and current_price is not None:
        sl_f = float(sl)
        cp = float(current_price)
        atr = float(trade.get("atr_14") or cp * 0.005)
        if side and cp <= sl_f + atr * 0.25:
            alerts.append({
                "code": "NEAR_FNO_STOP",
                "severity": "critical",
                "message": f"Price ₹{cp} near F&O stop ₹{sl_f} — consider exit or hedge.",
            })
        elif not side and cp >= sl_f - atr * 0.25:
            alerts.append({
                "code": "NEAR_FNO_STOP",
                "severity": "critical",
                "message": f"Price ₹{cp} near F&O stop ₹{sl_f} — consider exit or hedge.",
            })

    return alerts


FIVE_MIN_DROP_USED = 0.35
ALERT_BAR_MINUTES = 5
# Path-health auto-close: GIVEBACK + NEVER + DEEP (sl_each_deep_save_report).
# DEEP = bars≥4, peak<30% reward, against≥85% risk, signed≤−25 (≈94% loss prec).
# WARN_NEG_WEAK = alert-only. Favor<8 never-ran = WARN only. Classic two-against
# 5m drop still auto-closes. Early exit price clamped to hard stop.
NEVER_RAN_FAVOR_MAX = 8.0
NEVER_RAN_USED = 0.30
PATH_HEALTH_AUTO_CLOSE_STATES = frozenset(
    {"WARN_GIVEBACK", "WARN_NEG_NEVER", "WARN_NEG_DEEP"}
)
# A pullback that has already paid, and is only a few points back inside the
# opening range with VWAP still close, is not a drop. On the July–October 2026
# NIFTY calls this kept both winners the plain drop would have cut, and still
# caught the same 11 stops. Both halves of that window agreed.
STAY_FAV_POINTS = 15.0
STAY_INSIDE_POINTS = 8.0
STAY_VWAP_POINTS = 8.0


def _ist(ts):
    import pandas as pd

    stamp = pd.Timestamp.now(tz="Asia/Kolkata") if ts is None else pd.Timestamp(ts)
    if stamp.tzinfo is None:
        return stamp.tz_localize("Asia/Kolkata")
    return stamp.tz_convert("Asia/Kolkata")


def finished_five_minute(bars, asof=None, minutes: int = 5):
    """Rows whose candle has ended. The last row Kite returns can still be filling."""
    import pandas as pd

    if bars is None or not len(bars):
        return None
    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is None:
        idx = idx.tz_localize("Asia/Kolkata")
    else:
        idx = idx.tz_convert("Asia/Kolkata")
    now = _ist(asof)
    done = [i for i, start in enumerate(idx) if start + pd.Timedelta(minutes=int(minutes)) <= now]
    if not done:
        return None
    out = bars.iloc[done].copy()
    out.index = idx[done]
    return out


def _field(bar, name: str) -> float:
    if name in bar:
        return float(bar[name])
    return float(bar[name.lower()])


def _closed_against(bar, bull: bool) -> bool:
    try:
        close = _field(bar, "Close")
        opened = _field(bar, "Open")
    except (TypeError, ValueError, KeyError):
        return False
    return close < opened if bull else close > opened


def five_minute_drop(ticket, bars, asof=None) -> Optional[str]:
    """Ask to drop when two finished 5-minute candles have closed against the call
    and 35% of the stop is already used. Checked on the 5-minute close, not the
    15-minute close. On the July-October 2026 NIFTY calls this caught 11 of 16
    stops and cut 2 of 30 winners.
    """
    if not ticket:
        return None
    decision = str(ticket.get("decision") or "")
    bull = "BUY" in decision
    if not bull and "SELL" not in decision:
        return None
    try:
        entry = float(ticket["entry"])
        stop = float(ticket["stop_loss"])
    except (TypeError, ValueError, KeyError):
        return None
    risk = abs(entry - stop)
    if risk <= 0 or entry == 0:
        return None
    done = finished_five_minute(bars, asof)
    if done is None or len(done) < 2:
        return None
    last, prev = done.iloc[-1], done.iloc[-2]
    if not (_closed_against(last, bull) and _closed_against(prev, bull)):
        return None
    close = _field(last, "Close")
    lost = (entry - close) if bull else (close - entry)
    if lost / risk < FIVE_MIN_DROP_USED:
        return None
    pct = lost / entry * 100.0
    return (
        f"This {decision} is {lost:.0f} points against "
        f"({pct:.2f}% of price, {lost / risk:.0%} of the stop). "
        "The last two 5-minute candles closed against it. Drop this call."
    )


def _column(frame, name):
    return frame[name] if name in frame.columns else frame[name.lower()]


def _pnl(bull: bool, entry: float, price: float) -> float:
    return (price - entry) if bull else (entry - price)


def _opening_range(bars, day):
    import pandas as pd

    if bars is None or not len(bars):
        return None, None
    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is None:
        work = bars.copy()
        work.index = idx.tz_localize("Asia/Kolkata")
    else:
        work = bars.copy()
        work.index = idx.tz_convert("Asia/Kolkata")
    work = work[work.index.map(lambda t: t.date() == day)]
    box = work.between_time("09:15", "09:25")
    if not len(box):
        return None, None
    return float(_column(box, "High").max()), float(_column(box, "Low").min())


def _session_vwap(done) -> float:
    typical = (_column(done, "High") + _column(done, "Low") + _column(done, "Close")) / 3.0
    volume = _column(done, "Volume") if "Volume" in done.columns or "volume" in done.columns else None
    if volume is not None and float(volume.sum()) > 0:
        return float((typical * volume).sum() / float(volume.sum()))
    return float(typical.mean())


def _prior_favorable(done, bull: bool, entry: float, taken, minutes: int = ALERT_BAR_MINUTES) -> float:
    """Best points in favor on finished bars before the latest one."""
    import pandas as pd

    if taken is not None:
        start = _ist(taken)
        prior = done[(done.index + pd.Timedelta(minutes=int(minutes)) > start)]
    else:
        prior = done
    prior = prior.iloc[:-1] if len(prior) else prior
    if not len(prior):
        return 0.0
    if bull:
        return max(0.0, float(_column(prior, "High").max()) - entry)
    return max(0.0, entry - float(_column(prior, "Low").min()))


def _inside_depth(bull: bool, close: float, or_hi, or_lo):
    if or_hi is None or or_lo is None:
        return None, None
    inside = or_lo <= close <= or_hi
    if bull:
        depth = 0.0 if close >= or_hi else (or_hi - close)
    else:
        depth = 0.0 if close <= or_lo else (close - or_lo)
    return inside, depth


def _two_closes(done, bull: bool):
    if done is None or len(done) < 2:
        return False, False
    last, prev = done.iloc[-1], done.iloc[-2]
    last_against = _closed_against(last, bull)
    prev_against = _closed_against(prev, bull)
    return last_against and prev_against, (not last_against) and (not prev_against)


def call_stance(ticket, price, bars_5m=None, asof=None) -> Optional[Dict[str, Any]]:
    """One alert for the open call, ready to repeat on every refresh.

    The points follow the live price. Drop, stay, book, and keep change only
    when a 5-minute candle finishes, which is as fast as the saved tape can
    confirm them.
    """
    if not ticket or price is None:
        return None
    decision = str(ticket.get("decision") or "")
    bull = "BUY" in decision
    if not bull and "SELL" not in decision:
        return None
    try:
        entry = float(ticket["entry"])
        stop = float(ticket["stop_loss"])
        target = float(ticket["target_1"])
        px = float(price)
    except (TypeError, ValueError, KeyError):
        return None
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0 or reward <= 0 or entry == 0:
        return None
    live_profit = _pnl(bull, entry, px)
    done = finished_five_minute(bars_5m, asof, minutes=ALERT_BAR_MINUTES)
    if done is None or len(done) < 2:
        return _plain_stay(decision, live_profit, risk, reward)
    session_day = done.index[-1].date()
    done = done[done.index.map(lambda stamp: stamp.date() == session_day)]
    if len(done) < 2:
        return _plain_stay(decision, live_profit, risk, reward)
    last = done.iloc[-1]
    close = _field(last, "Close")
    close_profit = _pnl(bull, entry, close)
    vwap = _session_vwap(done)
    vwap_against = (vwap - close) if bull else (close - vwap)
    against2, _with2 = _two_closes(done, bull)
    or_hi, or_lo = _opening_range(done, done.index[-1].date())
    _inside, depth = _inside_depth(bull, close, or_hi, or_lo)
    favored = _prior_favorable(done, bull, entry, ticket.get("taken_at") or ticket.get("decision_at"), ALERT_BAR_MINUTES)
    pullback = (
        favored >= STAY_FAV_POINTS
        and _inside
        and depth is not None
        and depth <= STAY_INSIDE_POINTS
        and vwap_against <= STAY_VWAP_POINTS
    )
    import pandas as pd

    decided_at = done.index[-1] + pd.Timedelta(minutes=ALERT_BAR_MINUTES)
    at_target = live_profit >= reward - 0.05 or close_profit >= reward - 0.05
    runner = bool(ticket.get("runner"))
    if runner:
        return _runner_stance(decision, live_profit, reward, against2)
    if at_target:
        held = close_profit >= reward - 0.5
        if held and vwap_against <= 0:
            runner_px = entry + 2.0 * reward if bull else entry - 2.0 * reward
            return {
                "action": "keep",
                "decided_at": decided_at.isoformat(),
                "message": (
                    f"First target hit. Keep this {decision}. The 5-minute close is still "
                    f"beyond it and VWAP is in favor. The stop moves to the first target. "
                    f"The next target is {runner_px:.1f}."
                ),
            }
        if live_profit >= reward - 0.05 and not held:
            return {
                "action": "target_wait",
                "decided_at": decided_at.isoformat(),
                "message": (
                    f"First target touched. Stay with this {decision} until this 5-minute "
                    "candle closes. If it closes beyond the target and VWAP is still in "
                    "favor, keep the call. If it closes back through the target, book it."
                ),
            }
        return {
            "action": "book",
            "decided_at": decided_at.isoformat(),
            "message": (
                f"First target hit. Book this {decision}. The 5-minute close did not "
                "hold beyond the target with VWAP in favor."
            ),
        }
    used = max(-close_profit, 0.0) / risk
    last_against = _closed_against(last, bull)
    # Never-ran: red warn only (12y: auto-close on favor<8 destroyed ~3.3k pts).
    never_ran_warn = (
        favored < NEVER_RAN_FAVOR_MAX
        and last_against
        and close_profit < 0
        and used >= NEVER_RAN_USED
        and not pullback
    )
    # Two finished 5m closes against + ≥35% stop → still auto-close.
    classic_drop = against2 and used >= FIVE_MIN_DROP_USED and not pullback and close_profit < 0
    if classic_drop:
        lost = -close_profit
        return {
            "action": "drop",
            "auto_close": True,
            "decided_at": decided_at.isoformat(),
            "message": (
                f"Drop this {decision} before the stop. The last 5-minute close is "
                f"{lost:.0f} points against ({lost / entry * 100:.2f}% of price, "
                f"{lost / risk:.0%} of the stop) — the last two 5-minute candles "
                "closed against it."
            ),
        }
    if never_ran_warn:
        lost = -close_profit
        return {
            "action": "drop",
            "auto_close": False,
            "decided_at": decided_at.isoformat(),
            "message": (
                f"WARN — this {decision} never ran more than {favored:.0f} points in "
                f"favor, then closed against ({lost:.0f} pts / {lost / risk:.0%} of "
                f"stop). Path-health GIVEBACK/NEVER still auto-exits; this warn does not."
            ),
        }
    if pullback and close_profit < 0:
        return {
            "action": "stay",
            "decided_at": decided_at.isoformat(),
            "message": (
                f"Stay in this {decision}. It was {favored:.0f} points in favor, and this "
                f"pullback is {depth:.0f} points back inside the opening range with VWAP "
                f"{abs(vwap_against):.0f} points away. That is not enough to drop."
            ),
        }
    return _plain_stay(decision, live_profit, risk, reward, decided_at=decided_at.isoformat())


def _plain_stay(decision, live_profit, risk, reward, decided_at=None) -> Dict[str, Any]:
    if live_profit >= 0:
        text = (
            f"Stay in this {decision}. It is {live_profit:.0f} points in profit, "
            f"{live_profit / reward:.0%} of the first target."
        )
    else:
        lost = -live_profit
        text = (
            f"Stay for now. This {decision} is {lost:.0f} points against, "
            f"{lost / risk:.0%} of the stop. Auto-drop waits for path-health "
            f"GIVEBACK/NEVER, or two finished 5-minute candles against it and "
            f"{FIVE_MIN_DROP_USED:.0%} of the stop."
        )
    return {"action": "stay", "decided_at": decided_at, "message": text}


def _runner_stance(decision, live_profit, reward, against2) -> Dict[str, Any]:
    extra = live_profit - reward
    if against2 and extra > 0:
        return {
            "action": "book",
            "message": (
                f"Book this {decision} runner. The last two 5-minute candles closed against it. "
                f"That locks about {extra:.0f} points past the first target."
            ),
        }
    if extra >= reward:
        return {
            "action": "book",
            "message": f"The runner target is hit. Book this {decision}. It is {live_profit:.0f} points in profit.",
        }
    return {
        "action": "stay",
        "message": (
            f"Stay in this {decision}. The first target is locked"
            + (f", and it is {extra:.0f} points past that target." if extra > 0 else ".")
        ),
    }


def arm_runner(ticket: Dict[str, Any], asof) -> Dict[str, Any]:
    """Lock the first target and aim one target further. The arming bar is not a stop."""
    entry = float(ticket["entry"])
    target = float(ticket["target_1"])
    reward = abs(target - entry)
    bull = "BUY" in str(ticket.get("decision") or "")
    runner = entry + 2.0 * reward if bull else entry - 2.0 * reward
    out = dict(ticket)
    out["runner"] = True
    out["runner_since"] = _ist(asof).isoformat()
    out["original_stop"] = ticket.get("stop_loss")
    out["original_target"] = target
    out["stop_loss"] = target
    out["target_1"] = round(runner, 2)
    out["target_2"] = round(runner, 2)
    return out


def latest_alert_bar(bars, asof):
    """Identity of the last finished 5-minute candle. The alert is unchanged until this moves."""
    done = finished_five_minute(bars, asof, minutes=ALERT_BAR_MINUTES)
    if done is None or not len(done):
        return None
    return done.index[-1].isoformat()


def _remember_alert(ticket, bar, message, skip_mark):
    if isinstance(ticket, dict) and bar and message:
        ticket["alert_bar"] = bar
        ticket["alert_message"] = message
        ticket["alert_skip_mark"] = bool(skip_mark)
    return ticket


def settle_open_call(ticket, price, bars_5m, asof, bars_15m=None):
    """Arm a runner, or hold the ticket open while the target candle is still filling.

    The stance is computed once per finished 5-minute candle. Later refreshes
    reuse it. A stop that is already through still gets marked.

    Also auto-closes on path-health GIVEBACK / NEVER / DEEP
    (WEAK + favor<8 never-ran are warn-only; classic two-against 5m still auto-closes).
    """
    import fno_path_health
    import fno_session_rules as rules

    live = rules.open_ticket(ticket)
    if not live or price is None:
        return ticket, False
    bar = latest_alert_bar(bars_5m, asof)
    if bar and live.get("alert_bar") == bar and live.get("alert_message"):
        skip = bool(live.get("alert_skip_mark"))
        if skip:
            bull = "BUY" in str(live.get("decision") or "")
            try:
                through_stop = float(price) <= float(live["stop_loss"]) if bull else float(price) >= float(live["stop_loss"])
            except (TypeError, ValueError):
                through_stop = False
            if through_stop:
                skip = False
        return ticket, skip

    bull = "BUY" in str(live.get("decision") or "")
    try:
        stop_px = float(live["stop_loss"])
        through_stop = float(price) <= stop_px if bull else float(price) >= stop_px
    except (TypeError, ValueError):
        stop_px = None
        through_stop = False

    def _exit_px(raw: float) -> float:
        """Never early-drop worse than the hard stop."""
        if stop_px is None:
            return float(raw)
        return max(float(raw), stop_px) if bull else min(float(raw), stop_px)

    # Path-health strict auto-drop (GIVEBACK / NEVER) — uses 15m tape when present.
    path_bars = bars_15m if bars_15m is not None else bars_5m
    try:
        hi, lo = rules.path_extremes(path_bars, live.get("taken_at"), float(price))
    except Exception:
        hi = lo = float(price)
    assessment = fno_path_health.assess_open_ticket(
        live,
        last=float(price),
        path_high=hi,
        path_low=lo,
        bars=path_bars,
    )
    if (
        assessment
        and assessment.get("state") in PATH_HEALTH_AUTO_CLOSE_STATES
        and assessment.get("message")
        and not through_stop
    ):
        closed = rules.close_early_drop(
            ticket,
            exit_price=_exit_px(float(price)),
            closed_at=asof,
            reason=assessment["message"],
        )
        if isinstance(closed, dict):
            closed["alert_bar"] = bar
            closed["alert_message"] = assessment["message"]
            closed["alert_skip_mark"] = False
            closed["path_health"] = assessment
        return closed, rules.open_ticket(closed) is None

    stance = call_stance(live, price, bars_5m, asof=asof)
    if not stance:
        return ticket, False
    # Classic two-against 5m auto-close (never-ran is warn-only above).
    if stance.get("action") == "drop" and stance.get("auto_close") and not through_stop:
        closed = rules.close_early_drop(
            ticket,
            exit_price=_exit_px(float(price)),
            closed_at=stance.get("decided_at") or asof,
            reason=stance.get("message"),
        )
        live_closed = rules.open_ticket(closed)
        # Stamp alert on the closed history row via ticket root for UI once.
        if isinstance(closed, dict):
            closed["alert_bar"] = bar
            closed["alert_message"] = stance.get("message")
            closed["alert_skip_mark"] = False
        return closed, live_closed is None
    if stance["action"] == "target_wait" and not through_stop:
        _remember_alert(live, bar, stance["message"], True)
        return ticket, True
    if stance["action"] == "keep" and not live.get("runner"):
        armed = arm_runner(live, stance.get("decided_at") or asof)
        merged = dict(ticket or {})
        merged.update(armed)
        _remember_alert(merged, bar, stance["message"], False)
        return merged, False
    _remember_alert(live, bar, stance["message"], False)
    return ticket, False


def open_call_review(
    ticket: Optional[Dict[str, Any]],
    price: Optional[float],
    head: Optional[Dict[str, Any]] = None,
    bars_5m: Any = None,
    asof: Any = None,
) -> Optional[str]:
    """One sentence for the open call. Reused until the next 5-minute candle finishes."""
    if bars_5m is not None and len(getattr(bars_5m, "index", [])) >= 2:
        bar = latest_alert_bar(bars_5m, asof)
        if bar and isinstance(ticket, dict) and ticket.get("alert_bar") == bar and ticket.get("alert_message"):
            return ticket["alert_message"]
        stance = call_stance(ticket, price, bars_5m, asof=asof)
        if stance is None:
            return None
        _remember_alert(ticket, bar, stance.get("message"), False)
        return stance.get("message")
    if not ticket or price is None:
        return None
    decision = str(ticket.get("decision") or "")
    bull = "BUY" in decision
    if not bull and "SELL" not in decision:
        return None
    try:
        entry = float(ticket["entry"])
        stop = float(ticket["stop_loss"])
        px = float(price)
    except (TypeError, ValueError, KeyError):
        return None
    adverse = (entry - px) if bull else (px - entry)
    risk = abs(entry - stop)
    if adverse <= 0 or risk <= 0 or entry == 0:
        fast = five_minute_drop(ticket, bars_5m, asof=asof)
        if fast:
            return fast
        if adverse < 0 and risk > 0 and entry:
            return f"Stay in this {decision}. It is {-adverse:.0f} points in profit."
        return None
    fast = five_minute_drop(ticket, bars_5m, asof=asof)
    if fast:
        return fast
    used = adverse / risk
    pct = adverse / entry * 100.0
    info = head or {}
    reasons: List[str] = []
    if info.get("bar_note"):
        reasons.append("the last 15m bar closed against the call")
    want = 1 if bull else -1
    try:
        side = int(info["side"]) if info.get("side") is not None else None
    except (TypeError, ValueError):
        side = None
    if side == 0:
        reasons.append("price is back inside the opening range")
    elif side not in (None, want):
        reasons.append("price has closed through the other side of the opening range")
    try:
        score = float(info["p_t1"]) if info.get("p_t1") is not None else None
    except (TypeError, ValueError):
        score = None
    if score is not None and score < 0.48:
        reasons.append(f"the model score is now {score:.0%}")
    try:
        vwap = float((info.get("features") or {}).get("vwap_sess") or 0.0)
    except (TypeError, ValueError):
        vwap = 0.0
    if vwap and want * vwap < 0:
        reasons.append("price is on the wrong side of session VWAP")
    why = "; ".join(reasons) if reasons else "the tape has not given a fresh reason yet"
    text = (
        f"This {decision} is {adverse:.0f} points against "
        f"({pct:.2f}% of price, {used:.0%} of the stop). {why[0].upper()}{why[1:]}."
    )
    if used >= 0.45 and len(reasons) >= 2 and (score is None or score < 0.52) and bars_5m is None:
        return text + " Drop this call."
    if used >= 0.20 or reasons:
        return text
    return None


def alerts_summary(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    critical = sum(1 for a in alerts if a.get("severity") == "critical")
    warning = sum(1 for a in alerts if a.get("severity") == "warning")
    positive = sum(1 for a in alerts if a.get("severity") == "positive")
    path_warn = any(
        str(a.get("code") or "").startswith("PATH_WARN") for a in alerts
    )
    return {
        "count": len(alerts),
        "critical": critical,
        "warning": warning,
        "positive": positive,
        "path_warn": path_warn,
        "should_notify": critical > 0 or warning >= 2 or path_warn,
        "recommend_review": critical > 0 or path_warn,
    }
