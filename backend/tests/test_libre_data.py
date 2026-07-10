"""Tests for glucose data storage and retrieval."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from bgmon_api.models import GlucoseReading


def _make_reading(
    *,
    timestamp: datetime,
    sgv: int,
    trend: int | None = 1,
    direction: str | None = "Flat",
    source: str = "test",
) -> GlucoseReading:
    reading = GlucoseReading()
    reading.timestamp = timestamp
    reading.sgv = sgv
    reading.trend = trend
    reading.direction = direction
    reading.source = source
    return reading


def test_store_single_reading(db_session):
    timestamp = datetime.now(UTC)
    reading = _make_reading(timestamp=timestamp, sgv=123, trend=2, direction="SingleUp")

    db_session.add(reading)
    db_session.commit()

    stored = db_session.query(GlucoseReading).filter_by(timestamp=timestamp).one()

    assert stored.sgv == 123
    assert stored.trend == 2
    assert stored.direction == "SingleUp"
    assert stored.source == "test"



def test_store_multiple_readings(db_session):
    base_timestamp = datetime.now(UTC)
    readings = [
        _make_reading(timestamp=base_timestamp + timedelta(minutes=offset), sgv=100 + offset)
        for offset in range(3)
    ]

    for reading in readings:
        db_session.add(reading)
    db_session.commit()

    stored_count = db_session.query(GlucoseReading).count()

    assert stored_count == 3



def test_retrieve_latest_reading(db_session):
    base_timestamp = datetime.now(UTC)
    readings = [
        _make_reading(timestamp=base_timestamp - timedelta(minutes=10), sgv=110),
        _make_reading(timestamp=base_timestamp, sgv=120),
        _make_reading(timestamp=base_timestamp + timedelta(minutes=10), sgv=130),
    ]

    for reading in readings:
        db_session.add(reading)
    db_session.commit()

    latest = db_session.query(GlucoseReading).order_by(GlucoseReading.timestamp.desc()).first()

    assert latest is not None
    assert latest.sgv == 130
    assert latest.timestamp == base_timestamp + timedelta(minutes=10)



def test_duplicate_timestamp_rejected(db_session):
    timestamp = datetime.now(UTC)
    original = _make_reading(timestamp=timestamp, sgv=115)
    duplicate = _make_reading(timestamp=timestamp, sgv=140, source="backup")

    db_session.add(original)
    db_session.commit()
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()



def test_readings_ordered_by_timestamp(db_session):
    base_timestamp = datetime.now(UTC)
    out_of_order_readings = [
        _make_reading(timestamp=base_timestamp + timedelta(minutes=20), sgv=140),
        _make_reading(timestamp=base_timestamp, sgv=100),
        _make_reading(timestamp=base_timestamp + timedelta(minutes=10), sgv=120),
    ]

    for reading in out_of_order_readings:
        db_session.add(reading)
    db_session.commit()

    ordered = db_session.query(GlucoseReading).order_by(GlucoseReading.timestamp.asc()).all()

    assert [reading.sgv for reading in ordered] == [100, 120, 140]



def test_empty_readings_returns_empty(db_session):
    readings = db_session.query(GlucoseReading).all()

    assert readings == []



def test_bulk_insert_performance(db_session):
    base_timestamp = datetime.now(UTC)

    for offset in range(100):
        db_session.add(
            _make_reading(
                timestamp=base_timestamp + timedelta(minutes=offset),
                sgv=80 + offset,
                trend=(offset % 5) + 1,
                direction=f"trend-{offset}",
            )
        )
    db_session.commit()

    stored_count = db_session.query(GlucoseReading).count()

    assert stored_count == 100



def test_sgv_boundary_zero(db_session):
    timestamp = datetime.now(UTC)
    reading = _make_reading(timestamp=timestamp, sgv=0, trend=5, direction="DoubleDown")

    db_session.add(reading)
    db_session.commit()

    stored = db_session.query(GlucoseReading).filter_by(timestamp=timestamp).one()

    assert stored.sgv == 0



def test_sgv_boundary_high(db_session):
    timestamp = datetime.now(UTC)
    reading = _make_reading(timestamp=timestamp, sgv=500, trend=5, direction="DoubleUp")

    db_session.add(reading)
    db_session.commit()

    stored = db_session.query(GlucoseReading).filter_by(timestamp=timestamp).one()

    assert stored.sgv == 500



def test_trend_values(db_session):
    base_timestamp = datetime.now(UTC)

    for trend_value in range(1, 6):
        db_session.add(
            _make_reading(
                timestamp=base_timestamp + timedelta(minutes=trend_value),
                sgv=100 + trend_value,
                trend=trend_value,
                direction=f"trend-{trend_value}",
            )
        )
    db_session.commit()

    stored_trends = [
        reading.trend
        for reading in db_session.query(GlucoseReading)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    ]

    assert stored_trends == [1, 2, 3, 4, 5]



def test_source_field(db_session):
    base_timestamp = datetime.now(UTC)
    sources = ["librelinkup", "manual", "nightscout"]

    for offset, source in enumerate(sources):
        db_session.add(
            _make_reading(
                timestamp=base_timestamp + timedelta(minutes=offset),
                sgv=110 + offset,
                source=source,
            )
        )
    db_session.commit()

    stored_sources = [
        reading.source
        for reading in db_session.query(GlucoseReading)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    ]

    assert stored_sources == sources



def test_timestamps_with_timezone(db_session):
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    reading = _make_reading(timestamp=timestamp, sgv=150, source="utc-test")

    db_session.add(reading)
    db_session.commit()

    stored = db_session.query(GlucoseReading).filter_by(source="utc-test").one()

    assert stored.timestamp is not None
    assert stored.timestamp.tzinfo is not None
    assert stored.timestamp.utcoffset() == timedelta(0)
    assert stored.timestamp == timestamp
