# Finalarr — multi-stage build: React bundle, then Python runtime.

FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npx vite build && node scripts/collect-licenses.mjs

FROM python:3.12-slim

ARG VERSION=
LABEL org.opencontainers.image.title="Finalarr" \
      org.opencontainers.image.description="Season-finale and season-complete notifier for Sonarr" \
      org.opencontainers.image.licenses="GPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/Abrechen2/Finalarr" \
      org.opencontainers.image.version="${VERSION}"
ENV FINALARR_VERSION="${VERSION}" \
    FINALARR_DATA=/config \
    FINALARR_PORT=5790 \
    PYTHONDONTWRITEBYTECODE=1 \
    MALLOC_ARENA_MAX=2 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 finalarr \
    && useradd -u 1000 -g finalarr -d /app -s /usr/sbin/nologin finalarr

WORKDIR /app
# Exact, hashed versions: the release candidate and the final build get the same
# libraries (backend/requirements.txt, see docs/RELEASING.md).
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY backend/pyproject.toml backend/VERSION backend/gunicorn.conf.py ./
COPY backend/finalarr ./finalarr
RUN pip install --no-cache-dir --no-deps . && pip check && rm -rf build *.egg-info requirements.txt
COPY --from=frontend /build/dist /app/static
COPY LICENSE THIRD_PARTY_NOTICES.md /app/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh && mkdir -p /config

VOLUME /config
EXPOSE 5790
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"FINALARR_PORT\",\"5790\")}/health', timeout=4)"

ENTRYPOINT ["/entrypoint.sh"]
# One worker on purpose: the scheduler must exist exactly once.
CMD ["gunicorn", "-c", "/app/gunicorn.conf.py", "finalarr.app:create_app()"]
