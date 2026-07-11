"""Flask CLI commands for ML prediction v1."""

from __future__ import annotations

import json
from datetime import timedelta
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


def _collect_training_data():
    """Collect training samples from the database.

    Strategy: For each GlucoseReading that has a future reading at exactly
    the horizon offset (±5 min), build a feature row at the reading's
    timestamp and record the future SGV as the target.  Persisted
    GlobalSettings and the most recent BasalRateHistory at or before each
    reference time are included for richer context.
    """
    from bgmon_api.models import (
        BasalRateHistory,
        GlobalSettings,
        GlucoseReading,
        LogEntry,
    )

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

    training_input = TrainingInput()

    for _idx in range(len(readings)):
        r = readings[_idx]
        if r.timestamp is None or r.sgv is None:
            continue

        ref_time = r.timestamp.replace(tzinfo=r.timestamp.tzinfo)

        # Look up future targets
        t60_epoch = int((ref_time + timedelta(minutes=60)).timestamp())
        t120_epoch = int((ref_time + timedelta(minutes=120)).timestamp())

        target_60 = ts_to_sgv.get(t60_epoch)
        target_120 = ts_to_sgv.get(t120_epoch)

        # Also allow ±5 min tolerance
        if target_60 is None:
            for delta_sec in range(-5 * 60, 6 * 60, 60):
                target_60 = ts_to_sgv.get(t60_epoch + delta_sec)
                if target_60 is not None:
                    break

        if target_120 is None:
            for delta_sec in range(-5 * 60, 6 * 60, 60):
                target_120 = ts_to_sgv.get(t120_epoch + delta_sec)
                if target_120 is not None:
                    break

        # Skip rows where neither target is available
        if target_60 is None and target_120 is None:
            continue

        # Build context: readings up to and including ref_time
        context_readings = [
            cr for cr in readings
            if cr.timestamp is not None and cr.timestamp <= ref_time
        ]

        # Filter log entries up to ref_time
        context_logs = [
            le for le in log_entries
            if le.created_at is not None and le.created_at <= ref_time
        ]

        # Most recent basal rate at or before ref_time
        basal_rate: BasalRateHistory | None = None
        for br in reversed(basal_rates):
            if br.changed_at is not None and br.changed_at <= ref_time:
                basal_rate = br
                break

        training_input.add_context(
            ref_time=ref_time,
            target_60m_val=float(target_60) if target_60 is not None else None,
            target_120m_val=float(target_120) if target_120 is not None else None,
            glucose_readings=context_readings,
            log_entries=context_logs,
            basal_rate=basal_rate,
            global_settings=global_settings,
        )

    training_input.sample_count  # noqa: B018 — property call for verification
    return training_input
