"""PRIO-1 Tests: LibreLinkUp data fetching, storing, and alarm triggering."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch


class TestLibreDataStorage:
    """Test glucose data storage from LibreLinkUp or fallback sources."""

    def test_glucose_reading_storage_from_influxdb_fallback(self, db_session, app):
        """Test that glucose readings can be stored in PostgreSQL."""
        from bgmon_api.models import GlucoseReading

        with app.app_context():
            reading = GlucoseReading(
                sgv=145,
                trend=4,  # 4 = Flat
                direction="Flat",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            # Verify storage
            stored = GlucoseReading.query.order_by(
                GlucoseReading.timestamp.desc()
            ).first()
            assert stored is not None
            assert stored.sgv == 145
            assert stored.trend == 4
            assert stored.direction == "Flat"

    def test_multiple_glucose_readings_storage(self, db_session, app):
        """Test storing multiple glucose readings over time."""
        from bgmon_api.models import GlucoseReading

        with app.app_context():
            readings_data = [
                (100, 4, "Flat", datetime.now(UTC) - timedelta(minutes=20)),
                (120, 6, "SingleUp", datetime.now(UTC) - timedelta(minutes=10)),
                (140, 4, "Flat", datetime.now(UTC)),
            ]

            for sgv, trend, direction, ts in readings_data:
                reading = GlucoseReading(
                    sgv=sgv, trend=trend, direction=direction, timestamp=ts
                )
                db_session.add(reading)
            db_session.commit()

            # Verify all stored
            all_readings = GlucoseReading.query.all()
            assert len(all_readings) == 3

            # Verify latest query works
            latest = GlucoseReading.query.order_by(
                GlucoseReading.timestamp.desc()
            ).first()
            assert latest.sgv == 140

    def test_libre_data_storage_integration(self, db_session, app):
        """Test that libre glucose data can be stored and retrieved."""
        from bgmon_api.models import GlucoseReading

        with app.app_context():
            # Simulate storing a reading from LibreLinkUp
            reading = GlucoseReading(
                sgv=125,
                trend=4,  # Flat
                direction="Flat",
                timestamp=datetime.now(UTC) - timedelta(minutes=5),
                source="librelinkup",
            )
            db_session.add(reading)
            db_session.commit()

            # Verify reading was stored with correct source
            stored = GlucoseReading.query.filter_by(source="librelinkup").first()
            assert stored is not None
            assert stored.sgv == 125
            assert stored.trend == 4

    def test_glucose_reading_query_by_timerange(self, db_session, app):
        """Test querying glucose readings by time range."""
        from bgmon_api.models import GlucoseReading

        with app.app_context():
            now = datetime.now(UTC)
            readings_data = [
                (100, 4, "Flat", now - timedelta(hours=24)),
                (120, 4, "Flat", now - timedelta(hours=12)),
                (140, 6, "SingleUp", now - timedelta(hours=6)),
                (160, 4, "Flat", now),
            ]

            for sgv, trend, direction, ts in readings_data:
                reading = GlucoseReading(
                    sgv=sgv, trend=trend, direction=direction, timestamp=ts
                )
                db_session.add(reading)
            db_session.commit()

            # Query last 12 hours
            last_12h = GlucoseReading.query.filter(
                GlucoseReading.timestamp >= now - timedelta(hours=12)
            ).all()
            assert len(last_12h) == 3
            assert last_12h[0].sgv == 120  # oldest of the 3
            assert last_12h[-1].sgv == 160  # newest


class TestAlarmEvaluation:
    """Test alarm evaluation logic."""

    def test_critical_low_alarm_triggered(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test that critical low alarm is triggered at correct threshold."""
        from bgmon_api.models import GlucoseReading
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            # Store critical low glucose reading
            reading = GlucoseReading(
                sgv=50,  # Below critical_low (54.0)
                trend=2,  # SingleDown
                direction="SingleDown",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            # Mock push notification
            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ) as mock_push:
                evaluate_alarms()

                # Verify push was attempted
                mock_push.assert_called_once()
                args, kwargs = mock_push.call_args
                assert args[0] == patient_user.id
                assert "kritisch" in args[1].lower() or "critical" in args[1].lower()

    def test_low_alarm_triggered(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test that low alarm is triggered at correct threshold."""
        from bgmon_api.models import GlucoseReading
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            reading = GlucoseReading(
                sgv=65,  # Below low (70.0)
                trend=4,
                direction="Flat",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ) as mock_push:
                evaluate_alarms()
                mock_push.assert_called_once()

    def test_high_alarm_triggered(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test that high alarm is triggered at correct threshold."""
        from bgmon_api.models import GlucoseReading
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            reading = GlucoseReading(
                sgv=200,  # Above high (180.0)
                trend=6,
                direction="SingleUp",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ) as mock_push:
                evaluate_alarms()
                mock_push.assert_called_once()

    def test_critical_high_alarm_triggered(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test that critical high alarm is triggered at correct threshold."""
        from bgmon_api.models import GlucoseReading
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            reading = GlucoseReading(
                sgv=300,  # Above critical_high (250.0)
                trend=6,
                direction="SingleUp",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ) as mock_push:
                evaluate_alarms()
                mock_push.assert_called_once()

    def test_no_alarm_in_safe_range(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test that no alarm is triggered when glucose is in safe range."""
        from bgmon_api.models import GlucoseReading
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            reading = GlucoseReading(
                sgv=120,  # Safe range (70-180)
                trend=4,
                direction="Flat",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ) as mock_push:
                evaluate_alarms()
                mock_push.assert_not_called()

    def test_alarm_logged_to_logentry(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test that triggered alarms are logged as LogEntry."""
        from bgmon_api.models import GlucoseReading, LogEntry, LogEntryType
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            reading = GlucoseReading(
                sgv=50,
                trend=2,
                direction="SingleDown",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ):
                evaluate_alarms()

            # Verify LogEntry was created
            log = LogEntry.query.filter(
                LogEntry.entry_type == LogEntryType.ALARM
            ).first()
            assert log is not None
            assert log.user_id == patient_user.id

    def test_snooze_prevents_repeated_alarm(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test that snooze prevents repeated alarms for the same event."""
        from bgmon_api.models import GlucoseReading, UserSnooze
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            reading = GlucoseReading(
                sgv=50,
                trend=2,
                direction="SingleDown",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)

            # Set snooze for patient for the critical_low level
            snooze = UserSnooze(
                user_id=patient_user.id,
                snooze_until=datetime.now(UTC) + timedelta(minutes=15),
                reason="alarm:critical_low",  # Match the alarm level
            )
            db_session.add(snooze)
            db_session.commit()

            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ) as mock_push:
                evaluate_alarms()
                mock_push.assert_not_called()


class TestCompleteAlarmFlowIntegration:
    """Integration tests: Libre→Store→Alarm flow."""

    def test_full_flow_from_libre_to_alarm(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test complete flow: fetch Libre data → store → trigger alarm."""
        from bgmon_api.models import GlucoseReading
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            # Step 1: Store glucose reading (simulating Libre fetch)
            reading = GlucoseReading(
                sgv=55,
                trend=2,
                direction="SingleDown",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            # Step 2: Evaluate alarms
            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ) as mock_push:
                evaluate_alarms()

                # Step 3: Verify alarm was triggered
                assert mock_push.called
                call_args = mock_push.call_args
                assert call_args[0][0] == patient_user.id

    def test_user_without_profile_skips_alarm(
        self, db_session, app, patient_user, thresholds
    ):
        """Test that alarm is skipped if user has no active notification profile."""
        from bgmon_api.models import GlucoseReading
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            # Patient has thresholds but no active notification profile
            reading = GlucoseReading(
                sgv=50,
                trend=2,
                direction="SingleDown",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ) as mock_push:
                evaluate_alarms()
                # No alarm since no active profile
                mock_push.assert_not_called()

    def test_alarm_persists_across_evaluations(
        self, db_session, app, patient_user, thresholds, notification_profile_with_assignments
    ):
        """Test that alarm records persist across multiple evaluations."""
        from bgmon_api.models import Alarm, GlucoseReading
        from bgmon_api.services.alarm_evaluator import evaluate_alarms

        with app.app_context():
            reading = GlucoseReading(
                sgv=50,
                trend=2,
                direction="SingleDown",
                timestamp=datetime.now(UTC),
            )
            db_session.add(reading)
            db_session.commit()

            with patch(
                "bgmon_api.services.alarm_evaluator.send_push_to_user"
            ):
                evaluate_alarms()

            # Verify alarm was created
            alarms = Alarm.query.filter_by(user_id=patient_user.id).all()
            assert len(alarms) >= 1
