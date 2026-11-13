"""Gunicorn settings (PLAN.md 4.5): one worker, the scheduler starts after fork."""

import os

bind = f"0.0.0.0:{os.environ.get('FINALARR_PORT', '5790')}"
workers = 1
worker_class = "gthread"
threads = 8
graceful_timeout = 60
timeout = 120
# No access log: the webhook URL path contains its token.
accesslog = None
errorlog = "-"


def post_worker_init(worker):
    worker.wsgi.extensions["finalarr.scheduler"].start()


def worker_exit(server, worker):
    scheduler = getattr(worker, "wsgi", None)
    if scheduler is not None:
        scheduler.extensions["finalarr.scheduler"].shutdown()
