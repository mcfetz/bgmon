"""Gunicorn configuration for production deployment."""

bind = "0.0.0.0:5000"
workers = 2
worker_class = "sync"
timeout = 120
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = "info"
preload_app = True
