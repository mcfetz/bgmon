"""Runtime prediction service with safe disabled/unavailable behaviour.

Loads trained model artifacts once per process, accepts a feature context,
and returns structured outcomes: *disabled*, *unavailable*,
*insufficient_context*, or *ready* with persisted ``PredictionRun`` and
``PredictionPoint`` rows.

Never raises expected failure paths into HTTP callers.  Same-context calls
reuse a recent stored run rather than generating new rows on every
dashboard refresh.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING, Final

from bgmon_api.config import Config, MlRuntimeState
from bgmon_api.services.feature_builder import (
    FeatureBuilder,
    FeatureContext,
    InsufficientContextError,
)
from bgmon_api.services.feature_builder import (
    feature_names as canonical_feature_names,
)

if TYPE_CHECKING:
    import sklearn.linear_model

    from bgmon_api.models import PredictionRun


# ── typed outcome dataclasses ────────────────────────────────────────────


class PredictorOutcomeKind:
    """Namespace for outcome discriminator constants."""

    DISABLED: Final = "disabled"
    UNAVAILABLE: Final = "unavailable"
    INSUFFICIENT_CONTEXT: Final = "insufficient_context"
    READY: Final = "ready"


@dataclass(frozen=True, slots=True)
class DisabledOutcome:
    """ML is disabled by configuration."""

    kind: str = PredictorOutcomeKind.DISABLED
    reason: str = "ml_disabled"


@dataclass(frozen=True, slots=True)
class UnavailableOutcome:
    """ML is enabled but model artifacts are missing or invalid."""

    kind: str = PredictorOutcomeKind.UNAVAILABLE
    reason: str = "missing_artifacts"


@dataclass(frozen=True, slots=True)
class InsufficientContextOutcome:
    """Context does not meet minimum requirements for prediction."""

    kind: str = PredictorOutcomeKind.INSUFFICIENT_CONTEXT
    reason: str = "insufficient_context"


@dataclass(frozen=True, slots=True)
class ReadyOutcome:
    """Prediction run was generated (new or reused from cache)."""

    kind: str = PredictorOutcomeKind.READY
    reason: str = "ready"
    run_id: int = -1
    reused: bool = False


PredictorOutcome = (
    DisabledOutcome
    | UnavailableOutcome
    | InsufficientContextOutcome
    | ReadyOutcome
)

# ── internal cache ────────────────────────────────────────────────────────

_CACHE_TTL_MINUTES: Final = 15
_REUSE_WINDOW_MINUTES: Final = 10
_REQUIRED_MANIFEST_KEYS: Final = frozenset(
    {
        "model_version",
        "feature_version",
        "horizons",
        "feature_names",
        "feature_count",
        "model_files",
    }
)

# Process-local lazy cache (populated on first successful load)
_loaded_models: _ModelCache | None = None
_load_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class _ModelCache:
    """Immutable snapshot of loaded model artifacts.

    Created once when ``_load_artifacts`` succeeds; never mutated.
    """

    models: dict[int, sklearn.linear_model.LinearRegression]
    manifest: dict
    model_version: str
    feature_version: str
    model_dir: Path
    horizons: tuple[int, ...]

    @classmethod
    def empty(cls) -> _ModelCache:
        """Return an unusable default for guard clauses (never returned to callers)."""
        return cls(
            models={},
            manifest={},
            model_version="",
            feature_version="",
            model_dir=Path(),
            horizons=(),
        )


class _ManifestContractError(RuntimeError):
    """Raised when manifest.json does not match the predictor contract."""


# ── artifact loading ──────────────────────────────────────────────────────


def _load_artifacts(state: MlRuntimeState) -> _ModelCache | None:
    """Load trained models and manifest.

    Thread-safety: uses ``_load_lock`` + double-checked init to ensure
    artifacts are loaded at most once per process lifetime.
    """
    global _loaded_models  # noqa: PLW0603

    if _loaded_models is not None:
        return _loaded_models

    with _load_lock:
        if _loaded_models is not None:
            return _loaded_models

        if not state.artifacts_available:
            return None

        try:
            _loaded_models = _do_load(state)
        except (
            JSONDecodeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
            _ManifestContractError,
        ):
            _loaded_models = None
            return None

    return _loaded_models


def _do_load(state: MlRuntimeState) -> _ModelCache:
    """Perform the actual I/O: read manifest, load joblib models."""
    import joblib  # noqa: PLC0415 — lazy import keeps predictor lightweight

    manifest_text = state.manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    _validate_manifest_contract(manifest, state)

    models: dict[int, sklearn.linear_model.LinearRegression] = {}
    for horizon in state.horizons:
        model_path = state.model_dir / manifest["model_files"][f"{horizon}m"]
        models[horizon] = joblib.load(model_path)

    return _ModelCache(
        models=models,
        manifest=manifest,
        model_version=manifest["model_version"],
        feature_version=manifest["feature_version"],
        model_dir=state.model_dir,
        horizons=state.horizons,
    )


def _validate_manifest_contract(manifest: dict, state: MlRuntimeState) -> None:
    """Raise when manifest.json is incomplete or incompatible with the code."""
    missing_keys = _REQUIRED_MANIFEST_KEYS.difference(manifest)
    if missing_keys:
        raise _ManifestContractError(f"missing_manifest_keys:{sorted(missing_keys)}")

    manifest_horizons = tuple(int(h) for h in manifest["horizons"])
    if manifest_horizons != state.horizons:
        raise _ManifestContractError(
            f"manifest_horizons_mismatch:{manifest_horizons}!={state.horizons}"
        )

    expected_feature_names = canonical_feature_names()
    if manifest["feature_names"] != expected_feature_names:
        raise _ManifestContractError("feature_names_mismatch")

    if int(manifest["feature_count"]) != len(expected_feature_names):
        raise _ManifestContractError("feature_count_mismatch")

    model_files = manifest["model_files"]
    for horizon in state.horizons:
        key = f"{horizon}m"
        if key not in model_files:
            raise _ManifestContractError(f"missing_model_file_key:{key}")
        model_path = state.model_dir / model_files[key]
        if not model_path.is_file():
            raise _ManifestContractError(f"missing_model_file:{model_path.name}")


# ── context-tuple reuse ───────────────────────────────────────────────────


def _find_cached_run(
    user_id: int,
    horizon_minutes: int,
    context_end_at: datetime,
    model_version: str,
    feature_version: str | None,
) -> PredictionRun | None:
    """Return a recent persisted run whose context tuple matches.

    Matching semantics — all must match exactly:
      - ``user_id``
      - ``horizon_minutes``
      - ``context_end_at`` (within ±1 s)
      - ``model_version``
      - ``feature_version`` (NULL-safe)

    Only runs generated within the last ``_REUSE_WINDOW_MINUTES`` are
    eligible.  This prevents recycling a stale run that happened to share
    the same context tuple hours ago.
    """
    from bgmon_api.extensions import db
    from bgmon_api.models import PredictionRun

    cutoff = datetime.now(UTC) - timedelta(minutes=_REUSE_WINDOW_MINUTES)
    delta = timedelta(seconds=1)

    query = (
        db.session.query(PredictionRun)
        .filter(PredictionRun.user_id == user_id)
        .filter(PredictionRun.horizon_minutes == horizon_minutes)
        .filter(PredictionRun.context_end_at >= context_end_at - delta)
        .filter(PredictionRun.context_end_at <= context_end_at + delta)
        .filter(PredictionRun.model_version == model_version)
        .filter(PredictionRun.generated_at >= cutoff)
        .order_by(PredictionRun.generated_at.desc())
    )

    if feature_version is not None:
        query = query.filter(PredictionRun.feature_version == feature_version)
    else:
        query = query.filter(PredictionRun.feature_version.is_(None))

    return query.first()


def _context_cache_key(
    user_id: int,
    horizon_minutes: int,
    context_end_at: datetime,
    model_version: str,
    feature_version: str,
) -> tuple[int, int, str, str, str]:
    """Return a non-DB cache key for this prediction context."""
    ts_key = context_end_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return (user_id, horizon_minutes, ts_key, model_version, feature_version)


# ── public API ────────────────────────────────────────────────────────────

_UPCOMING_REUSE_CACHE: dict[tuple, ReadyOutcome] = {}


def predict(
    *,
    user_id: int,
    feature_context: FeatureContext,
    horizon_minutes: int,
) -> PredictorOutcome:
    """Attempt to produce a blood-glucose forecast for *horizon_minutes*.

    Returns one of four structured outcomes:

    - **DisabledOutcome** — ``BGMON_ML_ENABLED`` is false
    - **UnavailableOutcome** — model artifacts cannot be loaded
    - **InsufficientContextOutcome** — ``FeatureBuilder`` rejects the context
    - **ReadyOutcome** — prediction was generated (or reused from cache)

    **Never raises** for expected failure paths (disabled, missing artifacts,
    insufficient data).  Only raises for truly unexpected internal errors.
    """
    # 1. Check configuration
    state = Config.ml_runtime_state()
    if not state.enabled:
        return DisabledOutcome()

    # 2. Load artifacts (lazy, once per process)
    model_cache = _load_artifacts(state)
    if model_cache is None:
        return UnavailableOutcome()

    # 3. Verify requested horizon is supported
    if horizon_minutes not in model_cache.horizons:
        return UnavailableOutcome(reason=f"unsupported_horizon_{horizon_minutes}m")

    # 4. Build features (can raise InsufficientContextError — we catch it)
    try:
        feature_vec = FeatureBuilder().build_features(
            feature_context,
            horizon_minutes=horizon_minutes,
        ).to_feature_vector()
    except InsufficientContextError as e:
        return InsufficientContextOutcome(reason=e.reason)

    # 5. Check for same-context reuse (in-memory)
    cache_key = _context_cache_key(
        user_id,
        horizon_minutes,
        feature_context.reference_time,
        model_cache.model_version,
        model_cache.feature_version,
    )
    recent = _UPCOMING_REUSE_CACHE.get(cache_key)
    if recent is not None:
        return recent

    # 6. Check for same-context reuse (persisted DB)
    existing = _find_cached_run(
        user_id=user_id,
        horizon_minutes=horizon_minutes,
        context_end_at=feature_context.reference_time,
        model_version=model_cache.model_version,
        feature_version=model_cache.feature_version,
    )
    if existing is not None:
        outcome = ReadyOutcome(reason="reused", run_id=existing.id, reused=True)
        _UPCOMING_REUSE_CACHE[cache_key] = outcome
        return outcome

    # 7. Generate forecast + persist
    run_id = _generate_and_persist(
        user_id=user_id,
        feature_vec=feature_vec,
        horizon_minutes=horizon_minutes,
        context_end_at=feature_context.reference_time,
        model_cache=model_cache,
    )

    if run_id is None:
        return UnavailableOutcome(reason="prediction_rejected")

    outcome = ReadyOutcome(reason="ready", run_id=run_id, reused=False)
    _UPCOMING_REUSE_CACHE[cache_key] = outcome
    return outcome


def _logger() -> logging.Logger:
    """Lazy-initialised module-level logger."""
    return logging.getLogger("bgmon.predict")


# ── internal forecast generation ──────────────────────────────────────────


def _generate_and_persist(
    *,
    user_id: int,
    feature_vec: list[float],
    horizon_minutes: int,
    context_end_at: datetime,
    model_cache: _ModelCache,
) -> int | None:
    """Run inference with the loaded model and persist run + points.

    Returns the ``PredictionRun.id`` of the newly created row, or None if
    the model prediction was rejected (y_mean ≤ 0).
    """
    import numpy as np  # noqa: PLC0415

    from bgmon_api.extensions import db
    from bgmon_api.models import PredictionPoint, PredictionRun

    model = model_cache.models[horizon_minutes]

    step_minutes = 5
    n_points = horizon_minutes // step_minutes

    X = np.array([feature_vec], dtype=np.float64)  # noqa: N806
    y_mean = model.predict(X)[0]  # scalar

    y_mean_raw = round(float(y_mean), 1)

    # Reject garbage predictions: LinearRegression can predict ≤ 0 when BG
    # is in steep decline.  Clamping to 20 still creates visible chart spikes
    # next to healthy values (100+).  Skip persistence entirely.
    if y_mean_raw <= 0:
        _logger().warning(
            "skipping garbage prediction for user=%d horizon=%d: y_mean=%.1f",
            user_id, horizon_minutes, y_mean_raw,
        )
        return None

    run = PredictionRun()
    run.user_id = user_id
    run.context_end_at = context_end_at
    run.horizon_minutes = horizon_minutes
    run.model_version = model_cache.model_version
    run.feature_version = model_cache.feature_version

    db.session.add(run)
    db.session.flush()  # get run.id

    clamped_sgv = max(20.0, y_mean_raw)
    for i in range(n_points):
        point_ts = context_end_at + timedelta(minutes=step_minutes * (i + 1))
        point = PredictionPoint()
        point.run_id = run.id
        point.timestamp = point_ts
        point.predicted_sgv = clamped_sgv
        point.lower_bound = max(0.0, y_mean_raw - 15.0)
        point.upper_bound = max(20.0, y_mean_raw + 15.0)
        db.session.add(point)

    db.session.commit()
    return run.id


# ── manual cache invalidation (for testing) ──────────────────────────────


def _clear_cache() -> None:
    """Reset process-local caches.  Only exposed for test isolation."""
    global _loaded_models, _UPCOMING_REUSE_CACHE  # noqa: PLW0603
    _loaded_models = None
    _UPCOMING_REUSE_CACHE = {}


# ── scheduler-driven background prediction ────────────────────────────────


def predict_current(
    *,
    user_id: int,
    reference_time: datetime | None = None,
) -> None:
    """Build FeatureContext from current DB state and generate predictions.

    Fetches glucose readings (last 6 h), log entries (last 4 h),
    basal rate, and global settings from the database, then calls
    ``predict()`` for each configured ``BGMON_ML_HORIZONS`` value.

    Designed for scheduler-driven background prediction.  Errors are
    caught and logged — never raised to the scheduler.
    """
    logger = logging.getLogger("bgmon.predict")

    now = reference_time or datetime.now(UTC)
    try:
        from bgmon_api.models import (  # noqa: PLC0415
            BasalRateHistory,
            GlobalSettings,
            GlucoseReading,
            LogEntry,
        )
        from bgmon_api.services.feature_builder import (  # noqa: PLC0415
            FeatureContext,
        )

        # Fetch glucose readings (last 6 h for feature window)
        window_start = now - timedelta(hours=6)
        glucose_readings = (
            GlucoseReading.query
            .filter(GlucoseReading.timestamp >= window_start)
            .order_by(GlucoseReading.timestamp.asc())
            .all()
        )

        # Fetch log entries (last 4 h for carb/insulin windows)
        log_window_start = now - timedelta(hours=4)
        log_entries = (
            LogEntry.query
            .filter_by(user_id=user_id)
            .filter(LogEntry.created_at >= log_window_start)
            .order_by(LogEntry.created_at.asc())
            .all()
        )

        basal_rate = (
            BasalRateHistory.query
            .filter_by(user_id=user_id)
            .order_by(BasalRateHistory.changed_at.desc())
            .first()
        )

        global_settings = GlobalSettings.query.first()

        context = FeatureContext(
            glucose_readings=glucose_readings,
            log_entries=log_entries,
            basal_rate=basal_rate,
            global_settings=global_settings,
            reference_time=now,
        )

        for horizon in Config.ML_HORIZONS:
            predict(
                user_id=user_id,
                feature_context=context,
                horizon_minutes=horizon,
            )

    except Exception:
        logger.exception(
            "background prediction failed for user=%d", user_id,
        )
