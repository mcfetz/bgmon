"""Model artifact publisher with manifest-last atomic write.

Writes ``joblib`` model blobs + a ``manifest.json`` into the configured
model directory.  Temporary files are written first; ``manifest.json`` is
written last as the atomic "publish" signal that downstream consumers
(runtime predictor, evaluator) use to discover complete artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import joblib
import sklearn

from bgmon_api.services.model_trainer import TrainerResult

_MANIFEST_FILENAME: Final = "manifest.json"


def publish_model(
    result: TrainerResult,
    model_dir: Path,
    *,
    manifest_filename: str = _MANIFEST_FILENAME,
) -> Path:
    """Persist model artifacts and return path to the published manifest.

    1. Create *model_dir* if it does not exist.
    2. Write ``model_60m.joblib`` and ``model_120m.joblib`` as temp files,
       then atomically rename them into place.
    3. Write *manifest_filename* last as the atomic "ready" signal.

    Returns:
        Absolute path to the written manifest file.
    """
    model_dir = model_dir.resolve()
    model_dir.mkdir(parents=True, exist_ok=True)

    # Write model artifacts (temp → rename)
    _write_joblib(result.model_60m, model_dir, "model_60m.joblib")
    _write_joblib(result.model_120m, model_dir, "model_120m.joblib")

    # Build manifest
    manifest = {
        "model_version": result.model_version,
        "feature_version": result.feature_version,
        "horizons": result.horizons,
        "feature_names": result.feature_names,
        "feature_count": len(result.feature_names),
        "sklearn_version": sklearn.__version__,
        "trained_at": (
            result.trained_at.isoformat() if result.trained_at else None
        ),
        "train_window": {
            "start": (
                result.train_window_start.isoformat()
                if result.train_window_start
                else None
            ),
            "end": (
                result.train_window_end.isoformat()
                if result.train_window_end
                else None
            ),
        },
        "metrics": [
            {
                "horizon_minutes": m.horizon_minutes,
                "baseline_mae": m.baseline_mae,
                "model_mae": m.model_mae,
                "n_splits": m.n_splits,
                "n_samples": m.n_samples,
            }
            for m in result.metrics
        ],
        "model_files": {
            "60m": "model_60m.joblib",
            "120m": "model_120m.joblib",
        },
    }

    manifest_path = model_dir / manifest_filename

    # Write manifest last (atomic: write temp, then rename)
    tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        tmp.rename(manifest_path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)

    return manifest_path


def _write_joblib(obj: object, model_dir: Path, filename: str) -> None:
    """Write *obj* to a temp file, then rename to *filename*.

    This protects consumers from reading a partially-written blob.
    """
    dest = model_dir / filename
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        joblib.dump(obj, tmp)
        tmp.rename(dest)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
