"""Desktop alert for new F&O / Intraday calls (Windows-friendly)."""

from __future__ import annotations

import subprocess
import sys
import threading
from typing import Any, Optional

import desk_notify_format as fmt


def _win_toast_async(title: str, message: str) -> None:
    # Toast is single-line; flatten newlines.
    safe_t = title.replace("'", "''")[:100]
    safe_m = message.replace("\n", " · ").replace("'", "''")[:240]
    ps = (
        f"$t='{safe_t}'; $m='{safe_m}'; "
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null; "
        "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "$n = $x.GetElementsByTagName('text'); "
        "$n.Item(0).AppendChild($x.CreateTextNode($t)) | Out-Null; "
        "$n.Item(1).AppendChild($x.CreateTextNode($m)) | Out-Null; "
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($x); "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Stock Agent').Show($toast)"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Sta", "-Command", ps],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception:
        pass


def notify(
    title: str,
    message: str,
    *,
    duration_sec: int = 12,
    stock: Optional[str] = None,
    kind: str = "alert",
    decision: Optional[str] = None,
    entry: Optional[float] = None,
    stop_loss: Optional[float] = None,
    target_1: Optional[float] = None,
    dedupe_key: Optional[str] = None,
    product: str = "fno",
    payload: Optional[dict] = None,
) -> bool:
    text = (message or "").strip()
    head = (title or "Trading alert").strip()
    if not text:
        return False
    # Overlay indication channel: never notify (main dual model_call still fires)
    k = str(kind or "").lower()
    if k.startswith("overlay") or "overlay indication" in text.lower():
        if not _overlay_notify_on():
            return False
    desk_ok = False
    try:
        import desk_notifications

        desk_notifications.record(
            title=head,
            message=text,
            stock=stock,
            product=product,
            kind=kind,
            decision=decision,
            entry=entry,
            stop_loss=stop_loss,
            target_1=target_1,
            dedupe_key=dedupe_key,
            payload=payload,
        )
        desk_ok = True
    except Exception as exc:
        print(f"[notify] desk record failed: {exc}")
    remote_ok = False
    try:
        import telegram_notify

        if telegram_notify.maybe_send(
            title=head,
            message=text,
            stock=stock,
            kind=kind,
            decision=decision,
            payload=payload,
        ):
            remote_ok = True
    except Exception as exc:
        print(f"[notify] telegram failed: {exc}")
    try:
        import whatsapp_notify

        if whatsapp_notify.maybe_send(
            title=head,
            message=text,
            stock=stock,
            kind=kind,
            decision=decision,
            payload=payload,
        ):
            remote_ok = True
    except Exception as exc:
        print(f"[notify] whatsapp failed: {exc}")
    # Toast is best-effort and must not alone mark overlay notify_sent.
    if sys.platform == "win32":
        threading.Thread(target=_win_toast_async, args=(head, text), daemon=True).start()
    else:
        print(f"[notify] {head}: {text}")
    return desk_ok or remote_ok


def _option_fields(option: Optional[dict], stock: Optional[str] = None) -> dict:
    if not isinstance(option, dict):
        return {}
    out = {}
    for key in (
        "tradingsymbol",
        "right",
        "strike",
        "expiry",
        "groww_url",
        "groww_chart",
        "entry",
        "stop_loss",
        "target",
        "lot_size",
        "delta",
    ):
        if option.get(key) is not None:
            out[key] = option.get(key)
    # Alias premium levels clearly for Telegram / UI
    if out.get("entry") is not None:
        out["premium_buy"] = out["entry"]
    if out.get("stop_loss") is not None:
        out["premium_sl"] = out["stop_loss"]
    if out.get("target") is not None:
        out["premium_target"] = out["target"]
        out["premium_exit_book"] = out["target"]
    if out.get("tradingsymbol") and not out.get("groww_url"):
        try:
            import groww_option_links

            url = groww_option_links.option_chart_url(stock or option.get("underlying"), out["tradingsymbol"])
            if url:
                out["groww_url"] = url
                out["groww_chart"] = url
        except Exception:
            pass
    return out


def _emit(
    pack: dict,
    *,
    kind: str,
    dedupe_key: Optional[str] = None,
    option: Optional[dict] = None,
) -> bool:
    payload = dict(pack.get("payload") or {})
    payload["kind"] = kind
    opt = _option_fields(option, pack.get("stock"))
    if opt:
        payload.update(opt)
        pack = dict(pack)
        pack["message"] = _message_with_option_levels(
            pack.get("message") or "",
            action=str(payload.get("action") or ""),
            option=opt,
        )
    return notify(
        pack["title"],
        pack["message"],
        stock=pack.get("stock"),
        kind=kind,
        decision=pack.get("decision"),
        entry=pack.get("entry"),
        stop_loss=pack.get("stop_loss"),
        target_1=pack.get("target_1"),
        dedupe_key=dedupe_key,
        payload=payload,
    )


def _fmt_px(v: Any) -> str:
    try:
        return f"₹{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def _message_with_option_levels(message: str, *, action: str, option: dict) -> str:
    """Append buy/SL (NEW) or exit premium (BOOK). DROP/CLOSE stay short."""
    act = str(action or "").upper()
    ts = option.get("tradingsymbol")
    right = str(option.get("right") or "").upper()
    leg = "CE call" if right == "CE" else ("PE put" if right == "PE" else right)
    lines = [str(message or "").rstrip()]
    if act == "DROP":
        if ts:
            lines.append(f"Exit now · {ts}" + (f" ({leg})" if leg else ""))
        return "\n".join(lines)
    if act == "CLOSE":
        if ts:
            lines.append(f"Contract was · {ts}" + (f" ({leg})" if leg else ""))
        return "\n".join(lines)
    if act == "BOOK":
        exit_px = option.get("premium_exit_book") or option.get("target") or option.get("premium_target")
        if ts:
            lines.append(f"Contract: {ts}" + (f" · {leg}" if leg else ""))
        if exit_px is not None:
            lines.append(f"BOOK / exit premium around {_fmt_px(exit_px)} (option target)")
        buy = option.get("premium_buy") or option.get("entry")
        if buy is not None:
            lines.append(f"(Bought guide {_fmt_px(buy)})")
        return "\n".join(lines)
    # NEW / default — where to buy + option SL
    if ts:
        lines.append(f"Contract: {ts}" + (f" · {leg}" if leg else ""))
    buy = option.get("premium_buy") or option.get("entry")
    sl = option.get("premium_sl") or option.get("stop_loss")
    tgt = option.get("premium_target") or option.get("target")
    if buy is not None:
        lines.append(f"BUY premium around {_fmt_px(buy)}")
    if sl is not None:
        lines.append(f"Option stop-loss {_fmt_px(sl)}")
    if tgt is not None:
        lines.append(f"Option target / book near {_fmt_px(tgt)}")
    return "\n".join(lines)


def notify_outcome(
    stock: str,
    decision: str,
    *,
    status: str,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    option: Optional[dict] = None,
) -> bool:
    side = str(decision or "").upper() or "CALL"
    st = str(status or "")
    if st == "t1_before_sl":
        pack = fmt.pack(
            action=fmt.ACTION_BOOK,
            title="BOOK PROFIT",
            stock=stock,
            decision=side,
            channel="Model call",
            detail="Hit first target — square off / book profit now.",
            entry=entry,
            stop=stop,
            target=target,
        )
        return _emit(pack, kind="model_book", option=option)
    if st in ("sl_before_t1", "same_bar_both"):
        pack = fmt.pack(
            action=fmt.ACTION_DROP,
            title="DROP TRADE",
            stock=stock,
            decision=side,
            channel="Model call",
            detail="Hit stop — exit this trade now.",
            entry=entry,
            stop=stop,
            target=target,
        )
        return _emit(pack, kind="model_drop", option=option)
    if st == "early_drop":
        pack = fmt.pack(
            action=fmt.ACTION_DROP,
            title="DROP TRADE",
            stock=stock,
            decision=side,
            channel="Model call",
            detail="Early drop — never ran, then turned against. Exit now.",
            entry=entry,
            stop=stop,
            target=target,
        )
        return _emit(pack, kind="model_drop", option=option)
    if st == "expired":
        pack = fmt.pack(
            action=fmt.ACTION_CLOSE,
            title="CALL CLOSED",
            stock=stock,
            decision=side,
            channel="Model call",
            detail="Expired without target or stop.",
            entry=entry,
        )
        return _emit(pack, kind="model_close", option=option)
    return False


def _overlay_notify_on() -> bool:
    try:
        import fno_overlay_indication as foi

        return bool(foi.overlay_notify_enabled())
    except Exception:
        return False


def notify_overlay_book(
    stock: str,
    decision: str,
    *,
    reason: str,
    entry: Optional[float] = None,
    favour_pts: Optional[float] = None,
    dedupe_key: Optional[str] = None,
) -> bool:
    """Desktop alert: overlay BOOK PROFIT — take money now."""
    if not _overlay_notify_on():
        return False
    pack = fmt.pack(
        action=fmt.ACTION_BOOK,
        title="BOOK PROFIT",
        stock=stock,
        decision=decision,
        channel="Overlay indication",
        detail=f"{reason or 'Book rule hit'} — square off / book now.",
        entry=entry,
        favour_pts=favour_pts,
    )
    return _emit(pack, kind="overlay_book", dedupe_key=dedupe_key)


def notify_overlay_drop(
    stock: str,
    decision: str,
    *,
    reason: str,
    entry: Optional[float] = None,
    favour_pts: Optional[float] = None,
    dedupe_key: Optional[str] = None,
) -> bool:
    """Desktop alert: overlay DROP / invalidate — exit now."""
    if not _overlay_notify_on():
        return False
    pack = fmt.pack(
        action=fmt.ACTION_DROP,
        title="DROP TRADE",
        stock=stock,
        decision=decision,
        channel="Overlay indication",
        detail=f"{reason or 'Stop rule hit'} — exit this trade now.",
        entry=entry,
        favour_pts=favour_pts,
    )
    return _emit(pack, kind="overlay_drop", dedupe_key=dedupe_key)


def notify_overlay_live_alert(
    stock: str,
    decision: str,
    *,
    level: str,
    detail: str,
    entry: Optional[float] = None,
    favour_pts: Optional[float] = None,
    row_id: Optional[int] = None,
) -> bool:
    """Live BOOK NOW / DROP NOW while overlay trade is still open (deduped per row+level)."""
    if not _overlay_notify_on():
        return False
    lv = str(level or "").lower()
    if lv == "book":
        pack = fmt.pack(
            action=fmt.ACTION_BOOK,
            title="BOOK PROFIT",
            stock=stock,
            decision=decision,
            channel="Overlay indication",
            detail=detail or "Favour floor hit — book profit now.",
            entry=entry,
            favour_pts=favour_pts,
        )
        kind = "overlay_book_live"
    elif lv == "drop":
        pack = fmt.pack(
            action=fmt.ACTION_DROP,
            title="DROP TRADE",
            stock=stock,
            decision=decision,
            channel="Overlay indication",
            detail=detail or "Drop alert — exit this trade now.",
            entry=entry,
            favour_pts=favour_pts,
        )
        kind = "overlay_drop_live"
    else:
        return False
    dedupe = None
    if row_id is not None:
        dedupe = f"overlay:live:{stock}:{int(row_id)}:{lv}"
    return _emit(pack, kind=kind, dedupe_key=dedupe)


def notify_ticket_change(stock: str, before: Optional[dict], after: Optional[dict]) -> None:
    """Desktop toast on a new call, a stop, or a target. Safe to call on every refresh."""
    try:
        import fno_session_rules as fsrules
        import knowledge_db
        import training_store
    except Exception:
        return
    db = knowledge_db.ensure_db_dir()
    prev_open = fsrules.open_ticket(before)
    next_open = fsrules.open_ticket(after)
    hist = list((after or {}).get("history") or [])
    if prev_open and not next_open and hist:
        last = hist[-1]
        st = str(last.get("status") or (after or {}).get("status") or "")
        key = f"{stock}:close:{last.get('taken_at')}:{st}"
        opt = (last.get("readings") or {}).get("option") or (prev_open.get("readings") or {}).get("option")
        if st and training_store.should_notify(db, key):
            if notify_outcome(
                stock,
                str(last.get("decision") or prev_open.get("decision") or ""),
                status=st,
                entry=last.get("entry"),
                stop=last.get("stop_loss"),
                target=last.get("target_1"),
                option=opt if isinstance(opt, dict) else None,
            ):
                training_store.mark_notified(db, key, stock=stock, decision=st, payload={"status": st})
    if next_open:
        taken = str(next_open.get("taken_at") or "")
        dec = str(next_open.get("decision") or "")
        key = f"{stock}:open:{taken}:{dec}"
        opt_key = f"{stock}:open:{taken}:{dec}:option"
        opt = (next_open.get("readings") or {}).get("option")
        opt_dict = opt if isinstance(opt, dict) else None
        if taken and training_store.should_notify(db, key):
            if notify_call(
                stock,
                dec,
                stop=next_open.get("stop_loss"),
                target=next_open.get("target_1"),
                entry=next_open.get("entry"),
                option=opt_dict,
            ):
                training_store.mark_notified(
                    db, key, stock=stock, decision=dec, payload={"entry": next_open.get("entry")}
                )
                if opt_dict and opt_dict.get("tradingsymbol"):
                    training_store.mark_notified(
                        db, opt_key, stock=stock, decision=dec, payload={"option": True}
                    )
        elif (
            taken
            and opt_dict
            and opt_dict.get("tradingsymbol")
            and training_store.should_notify(db, opt_key)
        ):
            # Open toast already fired without a contract; send Groww / premium once ready.
            if notify_call(
                stock,
                dec,
                stop=next_open.get("stop_loss"),
                target=next_open.get("target_1"),
                entry=next_open.get("entry"),
                option_line="Option guide ready — contract + buy / SL / book premiums.",
                option=opt_dict,
            ):
                training_store.mark_notified(
                    db, opt_key, stock=stock, decision=dec, payload={"option": True}
                )


def notify_5m_crown_call(
    stock: str,
    decision: str,
    *,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    accuracy_label: Optional[str] = None,
    row_id: Optional[int] = None,
) -> bool:
    """Desktop/Telegram toast for independent 5m crown channel (never replaces dual-track)."""
    side = str(decision or "").upper()
    if side not in ("BUY", "SELL"):
        return False
    pack = fmt.pack(
        action=fmt.ACTION_NEW,
        title="NEW CALL",
        stock=stock,
        decision=side,
        channel="5m crown",
        detail=accuracy_label or "5m crown research recipe (parallel channel)",
        entry=entry,
        stop=stop,
        target=target,
    )
    dedupe = f"crown5m:new:{stock}:{int(row_id)}" if row_id is not None else None
    return _emit(pack, kind="crown_5m", dedupe_key=dedupe)


def notify_15m_classic_call(
    stock: str,
    decision: str,
    *,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    accuracy_label: Optional[str] = None,
    row_id: Optional[int] = None,
) -> bool:
    """Toast for independent 15m classic (old single fno_model) — parallel to dual/crown."""
    side = str(decision or "").upper()
    if side not in ("BUY", "SELL"):
        return False
    pack = fmt.pack(
        action=fmt.ACTION_NEW,
        title="NEW CALL",
        stock=stock,
        decision=side,
        channel="15m classic",
        detail=accuracy_label or "Old single 15m production model (parallel channel)",
        entry=entry,
        stop=stop,
        target=target,
    )
    dedupe = f"classic15m:new:{stock}:{int(row_id)}" if row_id is not None else None
    return _emit(pack, kind="classic_15m", dedupe_key=dedupe)


def notify_daily_fill_call(
    stock: str,
    decision: str,
    *,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    accuracy_label: Optional[str] = None,
    track: Optional[str] = None,
    fill_used: bool = False,
    row_id: Optional[int] = None,
) -> bool:
    """Toast for independent 1-call/day waterfall fill channel."""
    side = str(decision or "").upper()
    if side not in ("BUY", "SELL"):
        return False
    detail = accuracy_label or "1 call/day waterfall (parallel channel)"
    if track:
        detail = f"{detail} · {track}"
    if fill_used:
        detail = f"{detail} · empty-day fill"
    pack = fmt.pack(
        action=fmt.ACTION_NEW,
        title="NEW CALL",
        stock=stock,
        decision=side,
        channel="daily fill",
        detail=detail,
        entry=entry,
        stop=stop,
        target=target,
    )
    dedupe = f"dailyfill:new:{stock}:{int(row_id)}" if row_id is not None else None
    return _emit(pack, kind="daily_fill", dedupe_key=dedupe)


def notify_overlay_indication(
    stock: str,
    decision: str,
    *,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    accuracy_label: Optional[str] = None,
    rules: Optional[list] = None,
    favour_bars: Optional[int] = None,
    favour_minutes: Optional[int] = None,
    med_favour_pts: Optional[float] = None,
    favour_label: Optional[str] = None,
    book_label: Optional[str] = None,
    stop_label: Optional[str] = None,
    row_id: Optional[int] = None,
) -> bool:
    """Desktop toast for curated 15m overlay indication (parallel channel)."""
    if not _overlay_notify_on():
        return False
    side = str(decision or "").upper()
    if side not in ("BUY", "SELL"):
        return False
    detail_bits = [accuracy_label or "Overlay indication"]
    if rules:
        rule_bit = ", ".join(str(x) for x in rules[:3])
        if len(rules) > 3:
            rule_bit += f" +{len(rules) - 3}"
        detail_bits.append(rule_bit)
    if favour_bars is not None:
        mins = favour_minutes if favour_minutes is not None else int(favour_bars) * 5
        fav = f"~{favour_bars}×5m (~{mins}m)"
        if med_favour_pts is not None:
            fav += f" · med ~{med_favour_pts} pts"
        detail_bits.append(fav)
    elif favour_label:
        detail_bits.append(str(favour_label))
    if book_label:
        detail_bits.append(f"Book: {book_label}")
    if stop_label:
        detail_bits.append(f"Stop: {stop_label}")
    pack = fmt.pack(
        action=fmt.ACTION_NEW,
        title="NEW CALL",
        stock=stock,
        decision=side,
        channel="Overlay indication",
        detail=" · ".join(detail_bits),
        entry=entry,
        stop=stop,
        target=target,
    )
    dedupe = f"overlay:new:{stock}:{int(row_id)}" if row_id is not None else None
    return _emit(pack, kind="overlay_indication", dedupe_key=dedupe)


def notify_call(
    stock: str,
    decision: str,
    *,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    entry: Optional[float] = None,
    option_line: Optional[str] = None,
    option: Optional[dict] = None,
) -> bool:
    side = str(decision or "HOLD").upper()
    if "BUY" not in side and "SELL" not in side:
        return False
    detail = option_line or "New listed model call — open F&O for levels / Groww contract."
    pack = fmt.pack(
        action=fmt.ACTION_NEW,
        title="NEW CALL",
        stock=stock,
        decision=side,
        channel="Model call",
        detail=detail,
        entry=entry,
        stop=stop,
        target=target,
    )
    return _emit(pack, kind="model_call", option=option)


def notify_suggestion(
    stock: str,
    suggestion: Optional[dict],
    *,
    kind: str = "suggestion",
) -> bool:
    """Suggestions / pattern watch stay silent — listed calls only."""
    return False


def notify_suggestion_change(
    stock: str,
    before: Optional[dict],
    after: Optional[dict],
    *,
    kind: str = "suggestion",
) -> None:
    """No toast for suggestions or pattern watch (UI + desktop)."""
    return
