"""Flask application factory for bgmon."""

import logging
import signal
import sys
from typing import cast

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, jsonify, send_from_directory

from bgmon_api.config import Config
from bgmon_api.extensions import db, migrate

logger = logging.getLogger(__name__)

leader = None
scheduler = None
_app: Flask | None = None


def _libre_job() -> None:
    """Fetch Libre data (runs in scheduler)."""
    global leader
    if leader is not None and leader.is_leader and _app is not None:
        with _app.app_context():
            try:
                from bgmon_api.services.libre_fetcher import fetch_and_store
                fetch_and_store()
            finally:
                db.session.remove()


def _leader_heartbeat() -> None:
    """Renew leader lease (runs in scheduler)."""
    global leader
    if leader is not None and _app is not None:
        with _app.app_context():
            try:
                leader.daemon_renew_loop()
            finally:
                db.session.remove()


def _alarm_job() -> None:
    """Evaluate alarms (runs in scheduler)."""
    if _app is not None:
        with _app.app_context():
            try:
                from bgmon_api.services.alarm_evaluator import evaluate_alarms
                evaluate_alarms()
            finally:
                db.session.remove()


def _profile_schedule_job() -> None:
    """Check profile schedules (runs in scheduler)."""
    if _app is not None:
        with _app.app_context():
            try:
                from bgmon_api.services.alarm_evaluator import check_profile_schedules
                check_profile_schedules()
            finally:
                db.session.remove()


def _streak_job() -> None:
    """Check and log streak (runs in scheduler)."""
    if _app is not None:
        with _app.app_context():
            try:
                from bgmon_api.routes.dashboard import check_and_log_streak
                check_and_log_streak()
            finally:
                db.session.remove()


def create_app(config_class: type[Config] = Config) -> Flask:
    """Create and configure the Flask application."""
    global leader, scheduler, _app
    if _app is not None:
        return _app

    app = Flask(__name__, static_folder="static/dist", static_url_path="/static")
    app.config.from_object(config_class)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db.init_app(app)
    migrate.init_app(app, db)

    import bgmon_api.models  # noqa: F401
    from bgmon_api.routes.alarms import alarms_bp
    from bgmon_api.routes.auth import auth_bp
    from bgmon_api.routes.dashboard import dashboard_bp
    from bgmon_api.routes.family import family_bp
    from bgmon_api.routes.log import log_bp
    from bgmon_api.routes.night import night_bp
    from bgmon_api.routes.notifications import notifications_bp
    from bgmon_api.routes.settings import settings_bp
    from bgmon_api.routes.shifts import shifts_bp
    from bgmon_api.routes.users import users_bp

    app.register_blueprint(alarms_bp, url_prefix="/api/alarms")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(family_bp, url_prefix="/api/family")
    app.register_blueprint(log_bp, url_prefix="/api/log")
    app.register_blueprint(night_bp, url_prefix="/api/night")
    app.register_blueprint(notifications_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(shifts_bp, url_prefix="/api/shifts")
    app.register_blueprint(users_bp, url_prefix="/api/users")

    from bgmon_api.seed import bootstrap_admin

    with app.app_context():
        bootstrap_admin()

    from bgmon_api.routes.dashboard import check_and_log_streak
    from bgmon_api.services.alarm_evaluator import check_profile_schedules, evaluate_alarms
    from bgmon_api.services.leader import RowLeaseLeader
    from bgmon_api.services.libre_fetcher import fetch_and_store, get_last_fetch_info

    leader = RowLeaseLeader()

    from apscheduler.executors.pool import ThreadPoolExecutor
    executors = {
        'default': ThreadPoolExecutor(max_workers=2)
    }
    job_defaults = {
        'coalesce': True,
        'max_instances': 1,
        'misfire_grace_time': 120,
        'executor': 'default'
    }
    scheduler = BackgroundScheduler(
        daemon=True,
        executors=executors,
        job_defaults=job_defaults
    )

    scheduler.add_job(
        _leader_heartbeat,
        "interval",
        seconds=Config.LEADER_RENEW_S,
        id="leader_heartbeat",
        max_instances=1,
    )
    scheduler.add_job(
        _libre_job,
        "interval",
        seconds=60,
        id="libre_fetch",
        max_instances=1,
    )
    scheduler.add_job(
        _alarm_job,
        "interval",
        seconds=30,
        id="alarm_eval",
        max_instances=1,
    )
    scheduler.add_job(
        _profile_schedule_job,
        "interval",
        seconds=60,
        id="profile_schedule",
        max_instances=1,
    )
    scheduler.add_job(
        _streak_job,
        "interval",
        seconds=900,
        id="streak_check",
        max_instances=1,
    )

    if Config.SCHEDULER_ENABLED:
        import os
        if os.environ.get('GUNICORN_WORKER') != '1':
            scheduler.start()
            with app.app_context():
                try:
                    check_and_log_streak()
                except Exception:
                    logger.exception("Initial streak recalc failed")

    @app.get("/health")
    def health() -> Response:
        info = get_last_fetch_info()

        from bgmon_api.services.influx_reader import query_current_glucose

        influx_ok = False
        try:
            influx_data = query_current_glucose()
            influx_ok = influx_data is not None and influx_data.get("sgv") is not None
        except Exception:
            pass

        return cast(
            Response,
            jsonify(
                {
                    "status": "ok",
                    "is_leader": leader.is_leader if leader else False,
                    "instance_id": leader.instance_id[:8] if leader else None,
                    "influxdb_connected": influx_ok,
                    **info,
                }
            ),
        )

    @app.get("/")
    def index() -> Response:
        return send_from_directory(app.static_folder or "static/dist", "index.html")

    _app = app
    return app


def _shutdown(signum: int, _frame: object) -> None:
    logging.info("Received signal %s, shutting down...", signum)
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    sys.exit(0)


signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
