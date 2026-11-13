# Finalarr — multi-stage build: React bundle, then Python runtime.

FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npx vite build

FROM python:3.12-slim

ARG VERSION=
LABEL org.opencontainers.image.title="Finalarr" \
      org.opencontainers.image.description="Season-finale and season-complete notifier for Sonarr" \
      org.opencontainers.image.licenses="GPL-3.0" \
      org.opencontainers.image.version="${VERSION}"
ENV FINALARR_VERSION="${VERSION}" \
    FINALARR_DATA=/config \
    FINALARR_PORT=5790 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 finalarr \
    && useradd -u 1000 -g finalarr -d /app -s /usr/sbin/nologin finalarr

WORKDIR /app
COPY backend/pyproject.toml backend/VERSION ./
COPY backend/finalarr ./finalarr
RUN pip install --no-cache-dir . && rm -rf build *.egg-info
COPY --from=frontend /build/dist /app/static
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh && mkdir -p /config

VOLUME /config
EXPOSE 5790
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"FINALARR_PORT\",\"5790\")}/health', timeout=4)"

ENTRYPOINT ["/entrypoint.sh"]
# One worker on purpose: the scheduler must exist exactly once (PLAN.md 4.5).
CMD ["sh", "-c", "exec gunicorn --workers 1 --worker-class gthread --threads 8 --bind 0.0.0.0:${FINALARR_PORT} --graceful-timeout 60 --access-logfile - 'finalarr.app:create_app()'"]
