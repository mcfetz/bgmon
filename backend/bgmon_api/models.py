"""SQLAlchemy models for bgmon."""

# ── Enums ──────────────────────────────────────────────────────────────
import enum
import secrets
from datetime import UTC, datetime
from datetime import time as time_cls

import bcrypt
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bgmon_api.extensions import db


class UserRole(enum.StrEnum):
    """User roles: patient, observer, admin."""

    PATIENT = "patient"
    OBSERVER = "observer"
    ADMIN = "admin"


class AlarmType(enum.StrEnum):
    """Types of glucose alarms."""

    CRITICAL_LOW = "critical_low"
    LOW = "low"
    HIGH = "high"
    CRITICAL_HIGH = "critical_high"
    NO_DATA = "no_data"


class LogEntryType(enum.StrEnum):
    """Types of patient-logged entries."""

    CARBS = "carbs"
    INSULIN = "insulin"
    BASAL = "basal"
    NOTE = "note"
    ALARM = "alarm"
    SUCCESS = "success"


# ── Users ──────────────────────────────────────────────────────────────


class User(db.Model):
    """Users: patient, observers, admins."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.OBSERVER, nullable=False
    )
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    twilio_from_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    snooze_default_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    color_mode: Mapped[str] = mapped_column(String(10), default="auto", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    thresholds: Mapped[list["Threshold"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    night_profile: Mapped["NightProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    snooze_presets: Mapped[list["SnoozePreset"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alarms: Mapped[list["Alarm"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    log_entries: Mapped[list["LogEntry"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", foreign_keys="LogEntry.user_id"
    )
    shifts: Mapped[list["Shift"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notification_profiles: Mapped[list["NotificationProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "phone_number": self.phone_number,
            "twilio_from_number": self.twilio_from_number,
            "role": self.role.value,
            "is_active": self.is_active,
            "snooze_default_minutes": self.snooze_default_minutes,
            "color_mode": self.color_mode,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Sessions ────────────────────────────────────────────────────────────


class Session(db.Model):
    """Server-side session store (stateless tokens)."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship()


# ── Thresholds ──────────────────────────────────────────────────────────


class Threshold(db.Model):
    """Per-user glucose thresholds for alarming."""

    __tablename__ = "thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    critical_low: Mapped[float] = mapped_column(Float, default=54.0, nullable=False)
    low: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    high: Mapped[float] = mapped_column(Float, default=180.0, nullable=False)
    critical_high: Mapped[float] = mapped_column(Float, default=250.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="thresholds")

    def to_dict(self) -> dict:
        return {
            "critical_low": self.critical_low,
            "low": self.low,
            "high": self.high,
            "critical_high": self.critical_high,
        }


# ── Night Profiles ─────────────────────────────────────────────────────


class NightProfile(db.Model):
    """Per-user day/night profile configuration."""

    __tablename__ = "night_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), default="22:30", nullable=False)  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5), default="06:30", nullable=False)  # HH:MM
    webhook_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="night_profile")

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "webhook_token": self.webhook_token,
        }


# ── Shifts ─────────────────────────────────────────────────────────────


class Shift(db.Model):
    """Observer shift tracking — only one active shift at a time."""

    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="shifts")


# ── Snooze Presets ─────────────────────────────────────────────────────


class SnoozePreset(db.Model):
    """Per-user configurable snooze durations."""

    __tablename__ = "snooze_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="snooze_presets")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "duration_minutes": self.duration_minutes,
        }


# ── Push Subscriptions ─────────────────────────────────────────────────


class PushSubscription(db.Model):
    """Web Push subscription per user/browser."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh_key: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="push_subscriptions")


# ── Alarms ─────────────────────────────────────────────────────────────


class Alarm(db.Model):
    """Generated alarm events."""

    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    alarm_type: Mapped[AlarmType] = mapped_column(
        Enum(AlarmType, name="alarm_type"), nullable=False
    )
    sgv: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="alarms")
    twilio_calls: Mapped[list["TwilioCallLog"]] = relationship(
        back_populates="alarm", cascade="all, delete-orphan"
    )


# ── Twilio Call Log ────────────────────────────────────────────────────


class TwilioCallLog(db.Model):
    """Log of Twilio phone calls made for alarms."""

    __tablename__ = "twilio_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alarm_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("alarms.id", ondelete="SET NULL"), nullable=True
    )
    to_number: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    twilio_sid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    alarm: Mapped[Alarm] = relationship(back_populates="twilio_calls")


# ── Shift Audit Log ────────────────────────────────────────────────────


class ShiftAudit(db.Model):
    """Audit trail for alarm/shift actions."""

    __tablename__ = "shift_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Log Entries (carbs/insulin/basal) ──────────────────────────────────


class LogEntry(db.Model):
    """Patient-logged entries: carbs, insulin, basal."""

    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entry_type: Mapped[LogEntryType] = mapped_column(
        Enum(LogEntryType, name="log_entry_type"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="log_entries", foreign_keys=[user_id])
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entry_type": self.entry_type.value,
            "value": self.value,
            "unit": self.unit,
            "notes": self.notes,
            "created_by": self.created_by.display_name if self.created_by else None,
            "created_at": self.created_at.isoformat(),
        }


# ── Basal Rate History ─────────────────────────────────────────────────


class BasalRateHistory(db.Model):
    """Versioned history of basal rate changes."""

    __tablename__ = "basal_rate_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="U/h", nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


# ── Carb Factor History ────────────────────────────────────────────────


class CarbFactorHistory(db.Model):
    """Versioned history of carb factor changes."""

    __tablename__ = "carb_factor_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    factor: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="g/IE", nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


# ── Global Settings ────────────────────────────────────────────────────


class GlobalSettings(db.Model):
    """Global patient-specific settings (not user-specific)."""

    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    insulin_action_hours: Mapped[float] = mapped_column(Float, default=4.0, nullable=False)
    correction_factor: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    streak_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    best_streak_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_streak_achieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "insulin_action_hours": self.insulin_action_hours,
            "correction_factor": self.correction_factor,
            "best_streak_hours": self.best_streak_hours,
            "best_streak_achieved_at": (
                self.best_streak_achieved_at.isoformat() if self.best_streak_achieved_at else None
            ),
        }


# ── Family Dashboard Token ─────────────────────────────────────────────


class FamilyDashboardToken(db.Model):
    """Access token for the read-only family dashboard."""

    __tablename__ = "family_dashboard_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32)
    )
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def set_pin(self, pin: str) -> None:
        self.pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()
        self.pin_enabled = True

    def check_pin(self, pin: str) -> bool:
        if not self.pin_hash:
            return True
        return bool(bcrypt.checkpw(pin.encode(), self.pin_hash.encode()))


# ── Glucose Readings ───────────────────────────────────────────────────


class GlucoseReading(db.Model):
    """Glucose readings from LibreLinkUp (primary storage)."""

    __tablename__ = "glucose_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, unique=True
    )
    sgv: Mapped[int] = mapped_column(Integer, nullable=False)
    trend: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="librelinkup", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Scheduler Leader (row-lease lock) ──────────────────────────────────


class SchedulerLeader(db.Model):
    """Row-lease lock for leader election among Swarm replicas."""

    __tablename__ = "scheduler_leader"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default=lambda: secrets.token_hex(16)
    )
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ── Notification Profiles ──────────────────────────────────────────────


class NotificationArea(enum.StrEnum):
    """Notification delivery area."""

    PUSH = "push"
    CALL = "call"


class NotificationThreshold(enum.StrEnum):
    """Glucose threshold that triggers notification."""

    CRITICAL_LOW = "critical_low"
    LOW = "low"
    HIGH = "high"
    CRITICAL_HIGH = "critical_high"


class NotificationProfile(db.Model):
    """User-defined notification profile mapping thresholds to areas."""

    __tablename__ = "notification_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), default="🔔", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    start_time: Mapped[time_cls | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    webhook_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )

    user: Mapped[User] = relationship(back_populates="notification_profiles")
    assignments: Mapped[list["NotificationAssignment"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "is_active": self.is_active,
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "assignments": [a.to_dict() for a in self.assignments],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "webhook_token": self.webhook_token,
        }

    def generate_webhook_token(self) -> str:
        import secrets
        token = secrets.token_urlsafe(16)
        self.webhook_token = token
        return token


class NotificationAssignment(db.Model):
    """Maps a single threshold to a single area within a profile.

    UNIQUE(profile_id, threshold) ensures each threshold is assigned
    to exactly one area per profile.
    """

    __tablename__ = "notification_assignments"
    __table_args__ = (UniqueConstraint("profile_id", "threshold", name="uq_profile_threshold"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("notification_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    area: Mapped[NotificationArea] = mapped_column(
        Enum(NotificationArea, name="notification_area"), nullable=False
    )
    threshold: Mapped[NotificationThreshold] = mapped_column(
        Enum(NotificationThreshold, name="notification_threshold"), nullable=False
    )

    profile: Mapped[NotificationProfile] = relationship(back_populates="assignments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "area": self.area.value,
            "threshold": self.threshold.value,
        }


# ── User Active Profile & Snooze ────────────────────────────────────────


class UserActiveProfile(db.Model):
    """Stores the currently active notification profile per user (only one)."""

    __tablename__ = "user_active_profiles"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("notification_profiles.id", ondelete="CASCADE"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    profile: Mapped[NotificationProfile] = relationship()

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserSnooze(db.Model):
    """Per-user snooze state to suppress duplicate notifications."""

    __tablename__ = "user_snoozes"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    snooze_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "snooze_until": self.snooze_until.isoformat() if self.snooze_until else None,
            "reason": self.reason,
        }

    @property
    def is_active(self) -> bool:
        return self.snooze_until > datetime.now(UTC)


# ── Prediction Models ────────────────────────────────────────────────────


class PredictionRun(db.Model):
    """A single forecast generation run with metadata.

    Each run covers one or more forecast horizons and produces a set of
    ``PredictionPoint`` rows.  Runs are immutable after creation — a new
    run is generated each time the predictor executes.
    """

    __tablename__ = "prediction_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    context_end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    points: Mapped[list["PredictionPoint"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="PredictionPoint.timestamp"
    )

    __table_args__ = (
        # Fast lookup of recent runs for a given horizon.
        {"sqlite_autoincrement": True},
    )


class PredictionPoint(db.Model):
    """A single predicted glucose value at a future timestamp.

    Each point belongs to exactly one ``PredictionRun``.  Duplicate
    points within a run (same run_id + timestamp) are prevented by a
    unique constraint.
    """

    __tablename__ = "prediction_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prediction_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    predicted_sgv: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Float, nullable=True)

    run: Mapped["PredictionRun"] = relationship(back_populates="points")

    __table_args__ = (
        UniqueConstraint("run_id", "timestamp", name="uq_prediction_point_run_ts"),
        {"sqlite_autoincrement": True},
    )
