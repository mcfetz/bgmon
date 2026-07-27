"""Compression low detection tests."""

from datetime import UTC, datetime, timedelta

from bgmon_api.models import GlucoseReading, GlobalSettings, LogEntry, LogEntryType
from bgmon_api.services.compression_detector import detect_compression_low


def _seed_readings(db_session, sgvs: list[int], *, start_minutes_ago: int = 14) -> None:
    """Insert a series of glucose readings, 1 per minute."""
    for i, sgv in enumerate(sgvs):
        db_session.add(
            GlucoseReading(
                timestamp=(
                    datetime.now(UTC)
                    - timedelta(minutes=start_minutes_ago - i)
                ),
                sgv=sgv,
                trend=4,
                direction="Flat",
                source="test",
            )
        )
    db_session.commit()


def _seed_bolus(db_session, user_id: int, minutes_ago: int = 5) -> None:
    """Insert a recent insulin bolus entry."""
    db_session.add(
        LogEntry(
            user_id=user_id,
            entry_type=LogEntryType.INSULIN,
            value=3,
            unit="U",
            created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )
    )
    db_session.commit()


def _enable_detection(db_session, enabled: bool = True, *, confidence: int = 60) -> None:
    """Configure GlobalSettings for compression detection."""
    settings = GlobalSettings.query.first()
    if settings is None:
        settings = GlobalSettings(
            compression_low_enabled=enabled,
            compression_low_confidence_threshold=confidence,
        )
        db_session.add(settings)
    else:
        settings.compression_low_enabled = enabled
        settings.compression_low_confidence_threshold = confidence
    db_session.commit()


class TestDetectionDisabled:
    """Detection returns None when disabled."""

    def test_disabled_returns_none(self, db_session):
        _enable_detection(db_session, enabled=False)
        _seed_readings(db_session, [100, 100, 100, 100, 100])
        assert detect_compression_low() is None


class TestStickyValues:
    """Rule A: >=3 consecutive identical SGV values."""

    def test_three_identical_triggers(self, db_session):
        _enable_detection(db_session, confidence=30)
        _seed_readings(db_session, [120, 120, 120, 121, 122])
        result = detect_compression_low()
        assert result is not None
        assert "KONSTANTE_WERTE" in result["rules"]
        assert result["confidence"] >= 30

    def test_two_identical_not_enough(self, db_session):
        _enable_detection(db_session)
        _seed_readings(db_session, [120, 120, 121, 122, 123])
        result = detect_compression_low()
        # May not reach confidence 60 with just 2 sticky
        if result is not None:
            assert "KONSTANTE_WERTE" not in result["rules"]

    def test_sticky_values_confidence(self, db_session):
        _enable_detection(db_session, confidence=30)
        _seed_readings(db_session, [120, 120, 120, 121, 122])
        result = detect_compression_low()
        assert result is not None
        assert 30 in result["confidence_components"]


class TestSteepDrop:
    """Rule B: >15 mg/dL drop in <=5 minutes without recent IOB."""

    def test_steep_drop_no_iob_detected(self, db_session):
        _enable_detection(db_session, confidence=40)
        readings_data = [150, 149, 148, 133, 132]
        _seed_readings(db_session, readings_data, start_minutes_ago=4)
        result = detect_compression_low()
        assert result is not None
        assert "STARKER_ABFALL" in result["rules"]
        assert result["confidence"] >= 40

    def test_steep_drop_with_iob_not_detected(self, db_session, patient_user):
        _enable_detection(db_session, confidence=40)
        readings_data = [150, 149, 148, 133, 132]
        _seed_readings(db_session, readings_data, start_minutes_ago=4)
        _seed_bolus(db_session, patient_user.id, minutes_ago=5)
        result = detect_compression_low()
        if result is not None:
            assert "STARKER_ABFALL" not in result["rules"]

    def test_gradual_drop_not_steep_drop(self, db_session):
        _enable_detection(db_session)
        _seed_readings(db_session, [150, 149, 148, 147, 146])
        result = detect_compression_low()
        if result is not None:
            assert "STARKER_ABFALL" not in result["rules"]


class TestFloorPlateau:
    """Rule C: >=5 readings within ±2 at SGV < 80."""

    def test_floor_plateau_detected(self, db_session):
        _enable_detection(db_session, confidence=30)
        _seed_readings(db_session, [78, 79, 78, 79, 78, 79, 78])
        result = detect_compression_low()
        assert result is not None
        assert "BODEN_PLATEAU" in result["rules"]
        assert result["confidence"] >= 30

    def test_floor_plateau_above_80_not_detected(self, db_session):
        _enable_detection(db_session)
        _seed_readings(db_session, [81, 81, 82, 81, 80, 81, 82])
        result = detect_compression_low()
        if result is not None:
            assert "BODEN_PLATEAU" not in result["rules"]

    def test_floor_plateau_short_run_not_detected(self, db_session):
        _enable_detection(db_session)
        _seed_readings(db_session, [79, 79, 80, 81, 82, 83, 84])
        result = detect_compression_low()
        if result is not None:
            assert "BODEN_PLATEAU" not in result["rules"]


class TestCombinedRules:
    """Multiple rules combined."""

    def test_all_rules_combined(self, db_session):
        _enable_detection(db_session, confidence=60)
        sgvs = [150, 140, 132, 78, 78, 78, 78, 78]
        _seed_readings(db_session, sgvs, start_minutes_ago=7)
        result = detect_compression_low()
        assert result is not None
        assert result["confidence"] >= 60

    def test_normal_glucose_not_detected(self, db_session):
        _enable_detection(db_session)
        _seed_readings(db_session, [110, 112, 109, 111, 110, 113, 111])
        assert detect_compression_low() is None

    def test_below_confidence_threshold(self, db_session):
        _enable_detection(db_session, confidence=90)
        _seed_readings(db_session, [120, 120, 120, 121, 122])
        result = detect_compression_low()
        # Only STICKY_VALUES (30), below threshold of 90
        assert result is None
