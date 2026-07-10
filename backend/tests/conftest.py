"""pytest configuration — uses existing bgmon-postgres Docker container."""

import os
from datetime import UTC, datetime, timedelta

import pytest
from http import HTTPStatus

os.environ["BGMON_DISABLE_SCHEDULER"] = "true"
os.environ["VAPID_PUBLIC_KEY"] = "test-public-key"
os.environ["VAPID_PRIVATE_KEY"] = "test-private-key"
os.environ["VAPID_SUBJECT"] = "mailto:test@example.com"
os.environ["BGMON_SECRET_KEY"] = "test-secret-key"

# Use BGMON_DATABASE_URL from environment (CI sets bgmon_test, local uses test_bgmon)
_TEST_DB_URL = os.environ.get(
    "BGMON_DATABASE_URL",
    "postgresql://bgmon:bgmon@localhost:5432/test_bgmon",
)
os.environ["BGMON_DATABASE_URL"] = _TEST_DB_URL


_app_instance = None


def _get_app():
    global _app_instance
    if _app_instance is None:
        from bgmon_api.app import create_app
        from bgmon_api.extensions import db as _db

        _app_instance = create_app()
        _app_instance.config.update({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": _TEST_DB_URL,
        })
        with _app_instance.app_context():
            _db.create_all()
    return _app_instance


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    _get_app()
    yield
    from bgmon_api.extensions import db as _db
    app = _get_app()
    with app.app_context():
        _db.drop_all()
        _db.engine.dispose()


@pytest.fixture
def app():
    return _get_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Provide a clean DB state for each test by recreating all tables before and after.

    Simpler and more robust than nested transactions for this test suite: drop/create ensures
    no leftover rows, avoids FK ordering issues and detached ORM problems.
    """
    from bgmon_api.extensions import db as _db

    with app.app_context():
        # Recreate schema
        _db.session.remove()
        _db.drop_all()
        _db.create_all()

        yield _db.session

        # Recreate schema again to ensure next test starts clean
        _db.session.remove()
        _db.drop_all()
        _db.create_all()



def _create_user(db_session, email, display_name, role, **kwargs):
    from bgmon_api.models import Session, User
    from types import SimpleNamespace

    user = User(
        email=email, display_name=display_name, role=role,
        is_active=kwargs.get("is_active", True),
        phone_number=kwargs.get("phone_number"),
    )
    user.set_password(kwargs.get("password", "test_password"))
    db_session.add(user)
    db_session.flush()

    session = Session(user_id=user.id, expires_at=datetime.now(UTC) + timedelta(days=30))
    db_session.add(session)
    db_session.commit()
    # return lightweight object to avoid ORM-detached issues in tests
    user_ns = SimpleNamespace(id=user.id, email=user.email, display_name=user.display_name, role=user.role.value)
    user_ns._session_token = session.token
    return user_ns, session



@pytest.fixture
def patient_user(db_session):
    from bgmon_api.models import UserRole
    user, session = _create_user(db_session, "patient@example.com", "Test Patient", UserRole.PATIENT)
    return user


@pytest.fixture
def observer_user(db_session):
    from bgmon_api.models import UserRole
    user, session = _create_user(db_session, "observer@example.com", "Test Parent", UserRole.OBSERVER, phone_number="+1234567890")
    return user


@pytest.fixture
def admin_user(db_session):
    from bgmon_api.models import UserRole
    user, session = _create_user(db_session, "admin@example.com", "Test Admin", UserRole.ADMIN)
    return user


@pytest.fixture
def inactive_user(db_session):
    from bgmon_api.models import UserRole
    user, session = _create_user(db_session, "inactive@example.com", "Inactive", UserRole.OBSERVER, is_active=False)
    return user


@pytest.fixture
def patient_session(patient_user):
    from bgmon_api.models import Session
    from bgmon_api.extensions import db as _db
    # ensure session row exists and return a Session object
    token = getattr(patient_user, "_session_token", None)
    if not token:
        sess = Session(user_id=patient_user.id, expires_at=datetime.now(UTC) + timedelta(days=30))
        _db.session.add(sess)
        _db.session.commit()
        token = sess.token
    return Session.query.filter_by(token=token).first()


@pytest.fixture
def auth_headers():
    """Return callable that ensures a server-side session row exists and returns auth headers.

    We create a committed session row directly in the DB (fast, avoids rate-limits and keeps
    tests independent of the login endpoint). The created token is returned in the Authorization header.
    """
    from bgmon_api.extensions import db as _db
    import secrets

    def _headers(user):
        token = secrets.token_hex(32)
        expires = datetime.now(UTC) + timedelta(days=30)
        # Insert a session row visible to the app immediately
        _db.session.execute(
            "INSERT INTO sessions (user_id, token, expires_at, created_at) VALUES (:uid, :tok, :exp, now())",
            {"uid": user.id, "tok": token, "exp": expires},
        )
        _db.session.commit()
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def thresholds(db_session, patient_user):
    from bgmon_api.models import Threshold
    t = Threshold(user_id=patient_user.id, critical_low=54.0, low=70.0, high=180.0, critical_high=250.0)
    db_session.add(t)
    db_session.commit()
    return t


@pytest.fixture
def notification_profile_with_assignments(db_session, patient_user):
    from bgmon_api.models import NotificationArea, NotificationAssignment, NotificationProfile, NotificationThreshold, UserActiveProfile
    profile = NotificationProfile(user_id=patient_user.id, name="Default", icon="bell", is_active=True)
    db_session.add(profile)
    db_session.flush()
    for th in ["critical_low", "low", "high", "critical_high"]:
        db_session.add(NotificationAssignment(profile_id=profile.id, threshold=NotificationThreshold(th), area=NotificationArea.PUSH))
    db_session.add(UserActiveProfile(user_id=patient_user.id, profile_id=profile.id))
    db_session.commit()
    return profile


@pytest.fixture
def notification_profile_with_call(db_session, patient_user):
    from bgmon_api.models import NotificationArea, NotificationAssignment, NotificationProfile, NotificationThreshold, UserActiveProfile
    profile = NotificationProfile(user_id=patient_user.id, name="Call Profile", icon="phone", is_active=True)
    db_session.add(profile)
    db_session.flush()
    for th, area in [("critical_low", "CALL"), ("low", "PUSH"), ("high", "PUSH"), ("critical_high", "CALL")]:
        db_session.add(NotificationAssignment(profile_id=profile.id, threshold=NotificationThreshold(th), area=NotificationArea(area)))
    db_session.add(UserActiveProfile(user_id=patient_user.id, profile_id=profile.id))
    db_session.commit()
    return profile


@pytest.fixture
def glucose_readings(db_session):
    from bgmon_api.models import GlucoseReading
    readings = []
    base = datetime.now(UTC) - timedelta(hours=4)
    vals = [(120,1,"Flat"),(118,1,"FortyFiveDown"),(115,2,"SingleDown"),(110,2,"SingleDown"),(105,3,"DoubleDown"),
            (95,3,"DoubleDown"),(85,4,"SingleDown"),(72,4,"FortyFiveDown"),(65,5,"SingleDown"),(58,5,"DoubleDown"),
            (52,5,"DoubleDown"),(55,5,"DoubleDown"),(70,4,"FortyFiveUp"),(85,3,"SingleUp"),(100,2,"FortyFiveUp"),
            (120,1,"Flat"),(140,1,"FortyFiveUp"),(160,2,"SingleUp"),(175,2,"SingleUp"),(185,3,"SingleUp"),
            (200,3,"DoubleUp"),(230,4,"DoubleUp"),(260,5,"DoubleUp"),(240,4,"SingleUp")]
    for i, (sgv, trend, direction) in enumerate(vals):
        r = GlucoseReading(timestamp=base + timedelta(minutes=i * 10), sgv=sgv, trend=trend, direction=direction, source="test")
        db_session.add(r)
        readings.append(r)
    db_session.commit()
    return readings


@pytest.fixture
def glucose_reading_normal(db_session):
    from bgmon_api.models import GlucoseReading
    r = GlucoseReading(timestamp=datetime.now(UTC) - timedelta(minutes=2), sgv=120, trend=1, direction="Flat", source="test")
    db_session.add(r)
    db_session.commit()
    return r


@pytest.fixture
def glucose_reading_critical_low(db_session):
    from bgmon_api.models import GlucoseReading
    r = GlucoseReading(timestamp=datetime.now(UTC) - timedelta(minutes=2), sgv=50, trend=5, direction="DoubleDown", source="test")
    db_session.add(r)
    db_session.commit()
    return r


@pytest.fixture
def night_profile(db_session, patient_user):
    from bgmon_api.models import NightProfile
    p = NightProfile(user_id=patient_user.id, enabled=True, start_time="22:00", end_time="06:00")
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture
def snooze_presets(db_session, patient_user):
    from bgmon_api.models import SnoozePreset
    presets = [SnoozePreset(user_id=patient_user.id, label=l, duration_minutes=m) for l, m in [("5 min",5),("15 min",15),("30 min",30)]]
    for p in presets: db_session.add(p)
    db_session.commit()
    return presets


@pytest.fixture
def family_token(db_session):
    from bgmon_api.models import FamilyDashboardToken
    t = FamilyDashboardToken()
    db_session.add(t)
    db_session.commit()
    return t


@pytest.fixture
def global_settings(db_session):
    from bgmon_api.models import GlobalSettings
    s = GlobalSettings(insulin_action_hours=4.0, correction_factor=50.0)
    db_session.add(s)
    db_session.commit()
    return s
