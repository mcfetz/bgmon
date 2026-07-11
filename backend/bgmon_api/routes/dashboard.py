"""Dashboard blueprint — glucose current value, history, stats.

Primary storage: PostgreSQL (GlucoseReading model).
InfluxDB is kept as legacy passthrough only.
"""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask import Response as FlaskResponse

from bgmon_api.auth_utils import get_current_user
from bgmon_api.config import Config
from bgmon_api.models import (
    BasalRateHistory,
    GlobalSettings,
    GlucoseReading,
    LogEntry,
    PredictionPoint,
    PredictionRun,
    Threshold,
    User,
    UserRole,
)
from bgmon_api.utils import compute_glucose_stats, parse_iso_datetime, transactional_session

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/current", methods=["GET"])
def current() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    reading = (
        GlucoseReading.query.order_by(GlucoseReading.timestamp.desc()).first()
    )
    if reading is None:
        return jsonify({"error": "no data"}), HTTPStatus.NOT_FOUND

    return jsonify({
        "sgv": reading.sgv,
        "trend": reading.trend,
        "direction": reading.direction,
        "timestamp": reading.timestamp.isoformat() if reading.timestamp else None,
    })


@dashboard_bp.route("/history", methods=["GET"])
def history() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    start = request.args.get("start")
    end = request.args.get("end")

    if start and end:
        from datetime import datetime
        try:
            start_dt = parse_iso_datetime(start)
            end_dt = parse_iso_datetime(end)
        except ValueError:
            return jsonify({"error": "invalid date format"}), HTTPStatus.BAD_REQUEST

        readings = (
            GlucoseReading.query
            .filter(GlucoseReading.timestamp >= start_dt)
            .filter(GlucoseReading.timestamp <= end_dt)
            .order_by(GlucoseReading.timestamp.asc())
            .all()
        )
    else:
        # Default: last 24 hours
        from datetime import UTC, datetime, timedelta
        since = datetime.now(UTC) - timedelta(hours=24)
        readings = (
            GlucoseReading.query
            .filter(GlucoseReading.timestamp >= since)
            .order_by(GlucoseReading.timestamp.asc())
            .all()
        )

    return jsonify([
        {
            "sgv": r.sgv,
            "trend": r.trend,
            "direction": r.direction,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in readings
    ])


@dashboard_bp.route("/logs", methods=["GET"])
def logs() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    start = request.args.get("start")
    end = request.args.get("end")

    patient = User.query.filter_by(role=UserRole.PATIENT).first()
    if not patient:
        return jsonify([])

    if start and end:
        from datetime import datetime
        try:
            start_dt = parse_iso_datetime(start)
            end_dt = parse_iso_datetime(end)
        except ValueError:
            return jsonify({"error": "invalid date format"}), HTTPStatus.BAD_REQUEST

        entries = (
            LogEntry.query
            .filter_by(user_id=patient.id)
            .filter(LogEntry.created_at >= start_dt)
            .filter(LogEntry.created_at <= end_dt)
            .order_by(LogEntry.created_at.asc())
            .all()
        )
    else:
        from datetime import UTC, datetime, timedelta
        since = datetime.now(UTC) - timedelta(hours=24)
        entries = (
            LogEntry.query
            .filter_by(user_id=patient.id)
            .filter(LogEntry.created_at >= since)
            .order_by(LogEntry.created_at.asc())
            .all()
        )

    return jsonify([
        {
            "id": e.id,
            "entry_type": e.entry_type.value,
            "value": e.value,
            "unit": e.unit,
            "notes": e.notes,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ])


# ── predictions ───────────────────────────────────────────────────────


@dashboard_bp.route("/predictions", methods=["GET"])
def predictions() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    """Return blood-glucose forecast for a requested horizon.

    Query params:
        minutes (int): forecast horizon in minutes (default: 60).
                       Must be a positive integer matching one of the
                       configured ``BGMON_ML_HORIZONS`` values.

    Returns structured responses keyed by outcome kind:
        - ``ready``: 200 with run metadata + ordered future points
        - ``disabled``: 503 with status/reason
        - ``unavailable``: 503 with status/reason
        - ``insufficient_context``: 422 with status/reason
        - ``invalid minutes``: 400 with error message
    """
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    # ── parse & validate minutes ───────────────────────────────────────
    minutes_raw = request.args.get("minutes", "")
    if not minutes_raw:
        return jsonify({"error": "missing_query_param", "param": "minutes"}), HTTPStatus.BAD_REQUEST

    try:
        minutes = int(minutes_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_minutes", "value": minutes_raw}), HTTPStatus.BAD_REQUEST

    horizons = Config.ml_horizons()
    if minutes not in horizons:
        return jsonify({
            "error": "unsupported_horizon",
            "value": minutes,
            "supported": horizons,
        }), HTTPStatus.BAD_REQUEST

    if minutes <= 0:
        return jsonify({"error": "invalid_minutes", "value": minutes}), HTTPStatus.BAD_REQUEST

    # ── find patient & gather context ──────────────────────────────────
    patient = User.query.filter_by(role=UserRole.PATIENT).first()
    if not patient:
        return jsonify({"error": "no_patient"}), HTTPStatus.NOT_FOUND

    # Fetch recent glucose readings (last 6h for feature window)
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=6)
    glucose_readings = (
        GlucoseReading.query
        .filter(GlucoseReading.timestamp >= window_start)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )

    # Fetch recent log entries (last 4h for carb/insulin windows)
    log_window_start = now - timedelta(hours=4)
    log_entries = (
        LogEntry.query
        .filter_by(user_id=patient.id)
        .filter(LogEntry.created_at >= log_window_start)
        .order_by(LogEntry.created_at.asc())
        .all()
    )

    basal_rate = (
        BasalRateHistory.query
        .filter_by(user_id=patient.id)
        .order_by(BasalRateHistory.changed_at.desc())
        .first()
    )

    global_settings = GlobalSettings.query.first()

    # ── build context & call predictor ─────────────────────────────────
    from bgmon_api.services.feature_builder import FeatureContext
    from bgmon_api.services.predictor import (
        DisabledOutcome,
        InsufficientContextOutcome,
        ReadyOutcome,
        UnavailableOutcome,
        predict,
    )

    context = FeatureContext(
        glucose_readings=glucose_readings,
        log_entries=log_entries,
        basal_rate=basal_rate,
        global_settings=global_settings,
        reference_time=now,
    )

    outcome = predict(
        user_id=patient.id,
        feature_context=context,
        horizon_minutes=minutes,
    )

    # ── map outcome to HTTP response ───────────────────────────────────
    match outcome:
        case DisabledOutcome():
            return jsonify({
                "status": outcome.kind,
                "reason": outcome.reason,
            }), HTTPStatus.SERVICE_UNAVAILABLE

        case UnavailableOutcome():
            return jsonify({
                "status": outcome.kind,
                "reason": outcome.reason,
            }), HTTPStatus.SERVICE_UNAVAILABLE

        case InsufficientContextOutcome():
            return jsonify({
                "status": outcome.kind,
                "reason": outcome.reason,
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        case ReadyOutcome():
            # Query the persisted run + points
            run = PredictionRun.query.filter_by(id=outcome.run_id).first()
            if not run:
                return jsonify({
                    "status": "unavailable",
                    "reason": "run_not_found",
                }), HTTPStatus.SERVICE_UNAVAILABLE

            points = (
                PredictionPoint.query
                .filter_by(run_id=run.id)
                .order_by(PredictionPoint.timestamp)
                .all()
            )

            return jsonify({
                "status": outcome.kind,
                "run_id": run.id,
                "generated_at": run.generated_at.isoformat() if run.generated_at else None,
                "context_end_at": run.context_end_at.isoformat() if run.context_end_at else None,
                "horizon_minutes": run.horizon_minutes,
                "model_version": run.model_version,
                "reused": outcome.reused,
                "points": [
                    {
                        "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                        "predicted_sgv": p.predicted_sgv,
                        "lower_bound": p.lower_bound,
                        "upper_bound": p.upper_bound,
                    }
                    for p in points
                ],
            })

        case _:
            return jsonify({
                "status": "error",
                "reason": "unexpected_outcome",
            }), HTTPStatus.INTERNAL_SERVER_ERROR


def _calculate_weekly_scores(
    patient_id: int, low: int, high: int, days: int = 7
) -> list[dict[str, Any]]:
    """Calculate daily scores for the last N days (oldest first)."""
    from datetime import date as date_cls
    from datetime import timedelta

    from bgmon_api.extensions import db
    from bgmon_api.models import LogEntry, LogEntryType

    today = date_cls.today()
    result: list[dict[str, Any]] = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time()).replace(tzinfo=UTC)
        day_end = day_start + timedelta(days=1)

        day_logs = (
            db.session.execute(
                db.select(LogEntry)
                .where(LogEntry.user_id == patient_id)
                .where(LogEntry.created_at >= day_start)
                .where(LogEntry.created_at < day_end)
                .where(LogEntry.entry_type.in_(
                    [LogEntryType.CARBS, LogEntryType.INSULIN, LogEntryType.BASAL]
                ))
            )
            .scalars()
            .all()
        )

        entry_count = len(day_logs)
        types_logged = {log.entry_type for log in day_logs}
        all_three = (
            LogEntryType.CARBS in types_logged
            and LogEntryType.INSULIN in types_logged
            and LogEntryType.BASAL in types_logged
        )

        carbs_logs = [log for log in day_logs if log.entry_type == LogEntryType.CARBS]
        insulin_logs = [log for log in day_logs if log.entry_type == LogEntryType.INSULIN]
        timely = 0
        for ins in insulin_logs:
            for c in carbs_logs:
                if abs((ins.created_at - c.created_at).total_seconds()) <= 900:
                    timely += 1
                    break

        day_readings = (
            GlucoseReading.query
            .filter(GlucoseReading.timestamp >= day_start)
            .filter(GlucoseReading.timestamp < day_end)
            .all()
        )
        day_values = [r.sgv for r in day_readings if r.sgv is not None]
        in_range = sum(1 for v in day_values if low <= v <= high)
        range_hours = in_range * 5 // 60

        day_tir = None
        if day_values:
            day_tir = round(in_range / len(day_values) * 100, 1)

        total = 0
        total += min(entry_count, 10) * 2
        if all_three:
            total += 10
        total += min(timely, 3) * 3
        total += range_hours
        if day_tir is not None:
            if day_tir >= 90:
                total += 25
            elif day_tir >= 80:
                total += 15

        result.append({
            "date": day.isoformat(),
            "total": total,
            "is_today": i == 0,
        })

    return result


def _calculate_achievements(patient_id: int, low: int, high: int) -> list[dict[str, Any]]:
    """Check which achievements are unlocked based on patient data."""
    from datetime import date as date_cls
    from datetime import timedelta

    from bgmon_api.extensions import db
    from bgmon_api.models import GlobalSettings, LogEntry, LogEntryType

    achievements: list[dict[str, Any]] = [
        {
            "id": "bronze_streak",
            "name": "Bronze-Streak",
            "icon": "🥉",
            "description": "4 Stunden im grünen Bereich",
        },
        {
            "id": "gold_streak",
            "name": "Gold-Streak",
            "icon": "🥇",
            "description": "24 Stunden im grünen Bereich",
        },
        {
            "id": "perfect_day",
            "name": "Perfekter Tag",
            "icon": "⭐",
            "description": "TIR ≥ 95% an einem Tag",
        },
        {
            "id": "fire_streak",
            "name": "Feuer-Streak",
            "icon": "🔥",
            "description": "7 Tage mit TIR ≥ 80%",
        },
        {
            "id": "data_freak",
            "name": "Daten-Freak",
            "icon": "📊",
            "description": "30 Tage alle 3 Typen erfasst",
        },
        {
            "id": "early_bird",
            "name": "Frühaufsteher",
            "icon": "🌅",
            "description": "Eintrag vor 7 Uhr morgens",
        },
        {
            "id": "marksman",
            "name": "Zielsicher",
            "icon": "🎯",
            "description": "10 Tage mit TIR ≥ 80%",
        },
        {
            "id": "first_steps",
            "name": "Erste Schritte",
            "icon": "👣",
            "description": "7 Tage am Stück erfasst",
        },
    ]

    settings = GlobalSettings.query.first()
    best_streak_intervals = settings.best_streak_hours if settings else 0

    today = date_cls.today()
    days_to_check = 30
    day_boundaries = [
        (
            today - timedelta(days=i),
            datetime.combine(today - timedelta(days=i), datetime.min.time()).replace(tzinfo=UTC),
        )
        for i in range(days_to_check)
    ]

    perfect_days = 0
    good_days = 0
    complete_days = 0
    max_consecutive = 0
    early_entry = False

    for _i, (_day, day_start) in enumerate(day_boundaries):
        day_end = day_start + timedelta(days=1)

        day_logs = (
            db.session.execute(
                db.select(LogEntry)
                .where(LogEntry.user_id == patient_id)
                .where(LogEntry.created_at >= day_start)
                .where(LogEntry.created_at < day_end)
            )
            .scalars()
            .all()
        )

        if day_logs:
            has_early = any(log.created_at.hour < 7 for log in day_logs)
            if has_early:
                early_entry = True

            types = {log.entry_type for log in day_logs}
            if (
                LogEntryType.CARBS in types
                and LogEntryType.INSULIN in types
                and LogEntryType.BASAL in types
            ):
                complete_days += 1
            else:
                complete_days = 0
            max_consecutive = max(max_consecutive, complete_days)

        day_readings = (
            GlucoseReading.query
            .filter(GlucoseReading.timestamp >= day_start)
            .filter(GlucoseReading.timestamp < day_end)
            .all()
        )
        day_values = [r.sgv for r in day_readings if r.sgv is not None]
        if day_values:
            in_range = sum(1 for v in day_values if low <= v <= high)
            tir = in_range / len(day_values) * 100
            if tir >= 95:
                perfect_days += 1
            if tir >= 80:
                good_days += 1

    for a in achievements:
        a["unlocked"] = False

    if best_streak_intervals >= 16:
        achievements[0]["unlocked"] = True
    if best_streak_intervals >= 96:
        achievements[1]["unlocked"] = True
    if perfect_days >= 1:
        achievements[2]["unlocked"] = True
    if good_days >= 7:
        achievements[3]["unlocked"] = True
    if max_consecutive >= 30:
        achievements[4]["unlocked"] = True
    if early_entry:
        achievements[5]["unlocked"] = True
    if good_days >= 10:
        achievements[6]["unlocked"] = True
    if max_consecutive >= 7:
        achievements[7]["unlocked"] = True

    return achievements


def _calculate_daily_score(
    patient_id: int, low: int, high: int, today_values: list[float], tir_percent: float | None
) -> dict[str, Any]:
    from datetime import date as date_cls

    from bgmon_api.extensions import db
    from bgmon_api.models import LogEntry, LogEntryType

    today_start = datetime.combine(date_cls.today(), datetime.min.time()).replace(tzinfo=UTC)

    today_logs = (
        db.session.execute(
            db.select(LogEntry)
            .where(LogEntry.user_id == patient_id)
            .where(LogEntry.created_at >= today_start)
            .where(LogEntry.entry_type.in_(
                [LogEntryType.CARBS, LogEntryType.INSULIN, LogEntryType.BASAL]
            ))
        )
        .scalars()
        .all()
    )

    breakdown: list[dict[str, Any]] = []
    total = 0

    entry_count = len(today_logs)
    entry_pts = min(entry_count, 10) * 2
    if entry_pts:
        breakdown.append({"label": "Einträge erfasst", "points": entry_pts, "count": entry_count})
    total += entry_pts

    types_logged = {log.entry_type for log in today_logs}
    if (
        LogEntryType.CARBS in types_logged
        and LogEntryType.INSULIN in types_logged
        and LogEntryType.BASAL in types_logged
    ):
        breakdown.append({"label": "Alle 3 Typen", "points": 10})
        total += 10

    carbs_logs = [log for log in today_logs if log.entry_type == LogEntryType.CARBS]
    insulin_logs = [log for log in today_logs if log.entry_type == LogEntryType.INSULIN]
    timely = 0
    for ins in insulin_logs:
        for c in carbs_logs:
            if abs((ins.created_at - c.created_at).total_seconds()) <= 900:
                timely += 1
                break
    if timely:
        timely_pts = min(timely, 3) * 3
        breakdown.append({"label": "Pünktlich (< 15 Min)", "points": timely_pts, "count": timely})
        total += timely_pts

    in_range_count = sum(1 for v in today_values if low <= v <= high)
    range_hours = in_range_count * 5 // 60
    if range_hours:
        breakdown.append({"label": "Stunden in Range", "points": range_hours, "count": range_hours})
        total += range_hours

    if tir_percent is not None:
        if tir_percent >= 90:
            breakdown.append({"label": "TIR ≥ 90%", "points": 25})
            total += 25
        elif tir_percent >= 80:
            breakdown.append({"label": "TIR ≥ 80%", "points": 15})
            total += 15

    settings = GlobalSettings.query.first()
    if settings and settings.streak_started_at:
        ts = settings.streak_started_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        streak_intervals = max(0, int((datetime.now(UTC) - ts).total_seconds() // 900))
        if streak_intervals:
            breakdown.append({
                "label": "Streak-Meilensteine",
                "points": streak_intervals,
                "count": streak_intervals,
            })
            total += streak_intervals

    if settings:
        best = settings.best_streak_hours
        if settings.streak_started_at:
            ts = settings.streak_started_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            current = max(0, int((datetime.now(UTC) - ts).total_seconds() // 900))
            if current > 0 and current > best:
                breakdown.append({"label": "Neuer Rekord!", "points": 20})
                total += 20

    return {
        "total": total,
        "level": total // 100 + 1,
        "progress": total % 100,
        "breakdown": breakdown,
    }


@dashboard_bp.route("/stats", methods=["GET"])
def stats() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    start = request.args.get("start")
    end = request.args.get("end")

    if start and end:
        try:
            start_dt = parse_iso_datetime(start)
            end_dt = parse_iso_datetime(end)
        except ValueError:
            return jsonify({"error": "invalid date format"}), HTTPStatus.BAD_REQUEST

        readings = (
            GlucoseReading.query
            .filter(GlucoseReading.timestamp >= start_dt)
            .filter(GlucoseReading.timestamp <= end_dt)
            .order_by(GlucoseReading.timestamp.asc())
            .all()
        )
    else:
        since = datetime.now(UTC) - timedelta(hours=24)
        readings = (
            GlucoseReading.query
            .filter(GlucoseReading.timestamp >= since)
            .order_by(GlucoseReading.timestamp.asc())
            .all()
        )

    values = [r.sgv for r in readings if r.sgv is not None]
    data: dict[str, Any] = compute_glucose_stats(values)

    if values:
        streak_hours = 0
        best_streak_hours = 0
        best_streak_achieved_at = None
        settings = GlobalSettings.query.first()
        if settings:
            if settings.streak_started_at:
                ts = settings.streak_started_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                streak_hours = max(0, int((datetime.now(UTC) - ts).total_seconds() // 900))
            best_streak_hours = settings.best_streak_hours
            if settings.best_streak_achieved_at:
                bts = settings.best_streak_achieved_at
                if bts.tzinfo is None:
                    bts = bts.replace(tzinfo=UTC)
                best_streak_achieved_at = bts.isoformat()

        streak_started_at_iso = None
        if settings and settings.streak_started_at:
            sts = settings.streak_started_at
            if sts.tzinfo is None:
                sts = sts.replace(tzinfo=UTC)
            streak_started_at_iso = sts.isoformat()

        data["streak_hours"] = streak_hours
        data["streak_started_at"] = streak_started_at_iso
        data["best_streak_hours"] = best_streak_hours
        data["best_streak_achieved_at"] = best_streak_achieved_at

    from datetime import date as date_cls

    from bgmon_api.extensions import db
    from bgmon_api.models import User, UserRole

    today_start = datetime.combine(date_cls.today(), datetime.min.time()).replace(tzinfo=UTC)
    today_readings = (
        GlucoseReading.query
        .filter(GlucoseReading.timestamp >= today_start)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    today_values = [r.sgv for r in today_readings if r.sgv is not None]

    patient = db.session.execute(
        db.select(User).where(User.role == UserRole.PATIENT).limit(1)
    ).scalar_one_or_none()

    today_tir = None
    if patient and today_values:
        threshold = db.session.execute(
            db.select(Threshold).where(Threshold.user_id == patient.id)
        ).scalar_one_or_none()
        t_low = int(threshold.low) if threshold else 70
        t_high = int(threshold.high) if threshold else 180
        in_range = sum(1 for v in today_values if t_low <= v <= t_high)
        today_tir = round(in_range / len(today_values) * 100, 1)
        data["daily_score"] = _calculate_daily_score(
            patient.id, t_low, t_high, today_values, today_tir
        )
        data["weekly_scores"] = _calculate_weekly_scores(patient.id, t_low, t_high)
        data["achievements"] = _calculate_achievements(patient.id, t_low, t_high)

    return jsonify(data)


@dashboard_bp.route("/thresholds", methods=["GET"])
def get_thresholds() -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    user = get_current_user()
    if isinstance(user, tuple):
        return jsonify(user[0]), user[1]

    threshold = Threshold.query.filter_by(user_id=user.id).first()
    if not threshold:
        return jsonify({
            "critical_low": 54,
            "low": 70,
            "high": 180,
            "critical_high": 250,
        })

    return jsonify(threshold.to_dict())


def _analyze_streaks(low: int, high: int) -> tuple[datetime | None, int, datetime | None]:
    """Derive streak state from reading history.

    Returns (current_streak_start, longest_quarters, record_achieved_at).
    Out-of-range readings AND data gaps exceeding ``max_gap_seconds`` reset the
    counter, so the result reflects actual continuous in-range time only.
    ``record_achieved_at`` is the moment the longest run first reached
    ``longest_quarters`` quarter-hours — i.e. when the record was set.
    """
    from bgmon_api.extensions import db

    max_gap_seconds = 900  # >15 min between readings ⇒ treat as a streak break

    readings = (
        db.session.execute(
            db.select(GlucoseReading)
            .order_by(GlucoseReading.timestamp.asc())
            .limit(5000)
        )
        .scalars()
        .all()
    )
    if not readings:
        return None, 0, None

    from_zone = ZoneInfo("UTC")
    parsed: list[tuple[float, datetime]] = []
    for r in readings:
        if r.sgv is None or not r.timestamp:
            continue
        ts = (
            r.timestamp
            if isinstance(r.timestamp, datetime)
            else parse_iso_datetime(r.timestamp)
        )
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=from_zone)
        if ts is not None:
            parsed.append((r.sgv, ts.astimezone(from_zone)))

    if not parsed:
        return None, 0, None

    in_range_start: datetime | None = None
    last_oor: datetime | None = None
    longest_q = 0
    record_achieved_at: datetime | None = None
    last_ts: datetime | None = None

    for sgv, ts in parsed:
        gap_broken = (
            last_ts is not None and (ts - last_ts).total_seconds() > max_gap_seconds
        )
        if low <= sgv <= high:
            if in_range_start is None or gap_broken:
                in_range_start = ts
        else:
            last_oor = ts
            if in_range_start is not None:
                run_q = max(0, int((ts - in_range_start).total_seconds() // 900))
                if run_q > longest_q:
                    longest_q = run_q
                    record_achieved_at = in_range_start + timedelta(seconds=run_q * 900)
                in_range_start = None
        last_ts = ts

    if in_range_start is not None:
        latest_ts = parsed[-1][1]
        run_q = max(0, int((latest_ts - in_range_start).total_seconds() // 900))
        if run_q > longest_q:
            longest_q = run_q
            record_achieved_at = in_range_start + timedelta(seconds=run_q * 900)

    if in_range_start is None:
        current_streak_start: datetime | None = None
    elif last_oor is None:
        current_streak_start = in_range_start
    else:
        current_streak_start = last_oor

    return current_streak_start, longest_q, record_achieved_at


def check_and_log_streak() -> None:
    """Recalculate streak from history, update best-ever tracker, log milestones."""
    from bgmon_api.extensions import db
    from bgmon_api.models import LogEntry, LogEntryType, User, UserRole

    patient = User.query.filter_by(role=UserRole.PATIENT).first()
    if not patient:
        return

    threshold = db.session.execute(
        db.select(Threshold).where(Threshold.user_id == patient.id)
    ).scalar_one_or_none()
    if not threshold:
        return
    low = int(threshold.low)
    high = int(threshold.high)

    settings = GlobalSettings.query.first()
    if not settings:
        return

    current_streak_start, longest_q, record_achieved_at = _analyze_streaks(low, high)

    settings.streak_started_at = current_streak_start

    if longest_q > settings.best_streak_hours and record_achieved_at is not None:
        settings.best_streak_hours = longest_q
        settings.best_streak_achieved_at = record_achieved_at
        with transactional_session():
            pass  # commit handled by context manager

        note = f"Neuer Rekord-Streak: {longest_q * 15} Min. im grünen Bereich!"
        entry = LogEntry()
        entry.user_id = patient.id
        entry.entry_type = LogEntryType.SUCCESS
        entry.value = 0
        entry.unit = ""
        entry.notes = note
        with transactional_session():
            db.session.add(entry)
    else:
        with transactional_session():
            pass  # commit handled by context manager
