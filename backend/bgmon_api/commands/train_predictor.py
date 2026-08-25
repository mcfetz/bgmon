"""Flask CLI commands for ML prediction v1."""

from __future__ import annotations

import json
import logging
from datetime import UTC, timedelta
from pathlib import Path

import click
from flask import Flask

from bgmon_api.services.model_trainer import (
    TrainingInput,  # noqa: TCH001 — used in _collect_training_data
)
from bgmon_api.services.prediction_evaluator import evaluate_saved_predictions


def register_commands(app: Flask) -> None:
    """Register ML CLI commands on the Flask application."""
    app.cli.add_command(predictor_group)


@click.group("predictor", short_help="Prediction model commands")
def predictor_group() -> None:
    """Prediction v1 model management."""


@predictor_group.command("train", short_help="Train and publish prediction models")
@click.option(
    "--model-dir",
    default=None,
    help="Override model artifact directory (default: $BGMON_ML_MODEL_PATH)",
)
@click.pass_context
def train(_ctx: click.Context, model_dir: str | None) -> None:
    """Train 60m and 120m BG forecast regressors from persisted data.

    Walks historical glucose readings and log entries to build feature
    matrices, trains separate LinearRegression models per horizon with
    walk-forward cross-validation, and publishes ``joblib`` artifacts
    plus ``manifest.json`` to the configured model directory.

    Exits with code 1 and a clear message when training data is insufficient.
    """
    from bgmon_api.config import Config
    from bgmon_api.services.model_publisher import publish_model
    from bgmon_api.services.model_trainer import (
        ModelTrainer,
        TrainingInsufficientError,
    )

    target_dir = Path(Config.model_dir()) if model_dir is None else Path(model_dir)

    # Collect training data from DB (app context already active)
    training_input = _collect_training_data()

    trainer = ModelTrainer(cv_splits=min(5, max(2, training_input.sample_count - 1)))
    try:
        result = trainer.train(training_input)
    except TrainingInsufficientError:
        click.secho(
            "Error: insufficient training data. "
            "Need at least 3 valid (non-null-target) samples with both horizons.",
            fg="red",
        )
        raise SystemExit(1) from None

    manifest_path = publish_model(result, target_dir)
    click.secho(f"✓ Published models to {target_dir}", fg="green")
    click.secho(f"  manifest: {manifest_path}", fg="green")
    click.secho(f"  samples:  {training_input.sample_count}", fg="green")
    for m in result.metrics:
        click.secho(
            f"  {m.horizon_minutes}m: "
            f"baseline_mae={m.baseline_mae:.1f}  "
            f"model_mae={m.model_mae:.1f}  "
            f"(n_splits={m.n_splits})",
            fg="cyan",
        )

    _create_training_log_entry(result, training_input.sample_count)


@predictor_group.command("evaluate", short_help="Evaluate saved prediction runs")
@click.option(
    "--tolerance-minutes",
    default=5,
    show_default=True,
    type=click.IntRange(min=0),
    help="Maximum timestamp delta when matching actual glucose readings.",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Emit a machine-readable JSON report instead of human-readable lines.",
)
def evaluate(tolerance_minutes: int, json_output: bool) -> None:
    """Compare saved prediction runs against later actual glucose readings."""
    report = evaluate_saved_predictions(tolerance_minutes=tolerance_minutes)
    if json_output:
        click.echo(json.dumps(report.to_dict(), indent=2))
        return

    click.secho("Prediction evaluation summary", fg="green")
    if not report.aggregate_summaries:
        click.echo("No saved prediction runs found.")
        return

    for summary in report.aggregate_summaries:
        mae_text = "n/a" if summary.mae is None else f"{summary.mae:.1f}"
        click.echo(
            f"- {summary.horizon_minutes}m {summary.model_version}: "
            f"mae={mae_text} matched_points={summary.matched_points} "
            f"completed_runs={summary.completed_runs}/{summary.run_count}"
        )


def _create_training_log_entry(
    result: TrainingResult,  # noqa: F821 — forward ref
    sample_count: int,
) -> None:
    """Create a logbook note documenting the completed ML training run."""
    from datetime import UTC, datetime

    from bgmon_api.extensions import db
    from bgmon_api.models import LogEntry, LogEntryType, User, UserRole

    patient = User.query.filter_by(role=UserRole.PATIENT).first()
    if patient is None:
        logging.getLogger("bgmon.train").warning("No patient user found — skipping logbook entry")
        return

    metrics_lines = []
    for m in result.metrics:
        metrics_lines.append(
            f"{m.horizon_minutes}m: MAE {m.model_mae:.1f} "
            f"(baseline {m.baseline_mae:.1f}, {m.n_splits} splits)"
        )

    now = datetime.now(UTC)
    version = now.strftime("bgpred-%Y%m%dT%H%M%SZ")
    notes = (
        f"🤖 ML-Training abgeschlossen\n"
        f"Version: {version}\n"
        f"Samples: {sample_count}\n"
        + "\n".join(metrics_lines)
    )

    entry = LogEntry(
        user_id=patient.id,
        entry_type=LogEntryType.NOTE,
        value=0,
        unit="",
        notes=notes,
        created_by_id=patient.id,
    )
    db.session.add(entry)
    db.session.commit()

    _log = logging.getLogger("bgmon.train")
    _log.info("ML training logbook note created: id=%d, samples=%d", entry.id, sample_count)


def _collect_training_data():
    """Collect training samples from the database (near-linear throughput).

    Strategy: For each GlucoseReading that has a future reading at exactly
    the configured horizon offsets (±5 min), build a feature row at the
    reading's timestamp and record the future SGV as the target.  Persisted
    GlobalSettings and the most recent BasalRateHistory at or before each
    reference time are included for richer context.

    Context is computed from a *bounded rolling window* (6h) instead of the
    full history.  All features only look back ≤4h, so this produces
    identical vectors while keeping the runtime linear in the number of
    readings (previously the whole history was rescanned and re-sorted per
    row, which made training unusably slow once the dataset grew).
    """
    from collections import deque  # noqa: PLC0415

    from bgmon_api.config import Config
    from bgmon_api.models import (
        BasalRateHistory,
        GlobalSettings,
        GlucoseReading,
        LogEntry,
    )

    horizons = Config.ML_HORIZONS
    context_window = timedelta(hours=6)

    # Fetch all readings ordered by timestamp
    readings: list[GlucoseReading] = (
        GlucoseReading.query
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )

    # Build index: timestamp → sgv
    ts_to_sgv: dict[int, int] = {}
    for r in readings:
        if r.timestamp is not None and r.sgv is not None:
            ts_to_sgv[int(r.timestamp.timestamp())] = r.sgv

    # Fetch log entries
    log_entries: list[LogEntry] = (
        LogEntry.query
        .order_by(LogEntry.created_at.asc())
        .all()
    )

    # Persisted settings context
    global_settings: GlobalSettings | None = GlobalSettings.query.first()

    # Pre-load basal rate history (sorted ascending by changed_at)
    basal_rates: list[BasalRateHistory] = (
        BasalRateHistory.query
        .order_by(BasalRateHistory.changed_at.asc())
        .all()
    )

    if not readings:
        return TrainingInput()

    # Real sampling cadence (median gap) — drives leakage-safe CV gaps
    from statistics import median  # noqa: PLC0415

    ts_list = [
        r.timestamp for r in readings
        if r.timestamp is not None and r.sgv is not None
    ]
    sample_interval_s: float | None = None
    if len(ts_list) >= 2:
        diffs = [
            (t2 - t1).total_seconds()
            for t1, t2 in zip(ts_list, ts_list[1:], strict=False)
            if t2 > t1
        ]
        if diffs:
            sample_interval_s = float(median(diffs))

    training_input = TrainingInput(sample_interval_s=sample_interval_s)

    bg_window: deque[GlucoseReading] = deque()
    log_window: deque[LogEntry] = deque()
    log_idx = 0
    basal_idx = 0
    basal_rate: BasalRateHistory | None = None

    for r in readings:
        if r.timestamp is None or r.sgv is None:
            continue

        ref_time = r.timestamp
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=UTC)

        cutoff = ref_time - context_window

        # Advance basal-rate pointer to the entry active at/before ref_time
        while basal_idx < len(basal_rates):
            br = basal_rates[basal_idx]
            if br.changed_at is not None and br.changed_at <= ref_time:
                basal_rate = br
                basal_idx += 1
            else:
                break

        # Feed log entries up to ref_time, pruning anything outside the window
        while log_idx < len(log_entries):
            le = log_entries[log_idx]
            if le.created_at is not None and le.created_at <= ref_time:
                log_window.append(le)
                log_idx += 1
            else:
                break
        while log_window and (
            log_window[0].created_at is None
            or log_window[0].created_at <= cutoff
        ):
            log_window.popleft()

        # Rolling BG window: keep readings within the context window
        while bg_window and (
            bg_window[0].timestamp is None or bg_window[0].timestamp <= cutoff
        ):
            bg_window.popleft()
        bg_window.append(r)

        # Look up future targets for all configured horizons
        target_vals: dict[int, float | None] = {}
        all_none = True
        for h in horizons:
            t_epoch = int((ref_time + timedelta(minutes=h)).timestamp())
            val = ts_to_sgv.get(t_epoch)

            # ±5 min tolerance
            if val is None:
                for delta_sec in range(-5 * 60, 6 * 60, 60):
                    val = ts_to_sgv.get(t_epoch + delta_sec)
                    if val is not None:
                        break

            target_vals[h] = float(val) if val is not None else None
            if val is not None:
                all_none = False

        # Skip rows where no horizon has a target
        if all_none:
            continue

        training_input.add_context(
            ref_time=ref_time,
            targets=target_vals,
            glucose_readings=list(bg_window),
            log_entries=list(log_window),
            basal_rate=basal_rate,
            global_settings=global_settings,
        )

    training_input.sample_count  # noqa: B018 — property call for verification
    return training_input
