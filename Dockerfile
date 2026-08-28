# syntax=docker/dockerfile:1
FROM python:3.13-slim AS buildimage

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-install-project --extra forecast

# The wheel carries the actual package -- including the version setuptools-scm
# resolved from git at build time in build-check -- and installs on top of the
# dependencies synced above with --no-deps. Replaces the old
# freeze_version.py + raw source copy: a real uv build already writes
# solaredge2mqtt/_version.py as a side effect (version_file in
# pyproject.toml), the way --no-install-project deliberately skips.
COPY dist/*.whl /app/dist/
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv pip install --no-deps /app/dist/*.whl

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

RUN set -eux && \
    apt-get update && \
    apt-get install -y --no-install-recommends gosu sqlite3 && \
    rm -rf /var/lib/apt/lists/* && \
    adduser --uid 1000 --disabled-password --gecos '' solaredge2mqtt && \
    mkdir -p /app/config /app/cache && \
    chown solaredge2mqtt:solaredge2mqtt /app/config /app/cache && \
    chmod 755 /app/config && \
    chmod 700 /app/cache

COPY --chown=root:solaredge2mqtt --chmod=755 --from=buildimage /venv /venv
COPY --chown=root:root --chmod=755 docker-entrypoint.sh /usr/local/bin/

# On PATH so a running container can back its database up with
# docker exec solaredge2mqtt backup-database.sh
COPY --chown=root:root --chmod=755 scripts/backup-database.sh /usr/local/bin/

VOLUME ["/app/config"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python3", "-m", "solaredge2mqtt"]
