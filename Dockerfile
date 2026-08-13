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

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

RUN set -eux && \
    apt-get update && \
    apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/* && \
    adduser --uid 1000 --disabled-password --gecos '' solaredge2mqtt && \
    mkdir -p /app/config /app/cache && \
    chown solaredge2mqtt:solaredge2mqtt /app/config /app/cache && \
    chmod 755 /app/config && \
    chmod 700 /app/cache

COPY --chown=root:solaredge2mqtt --chmod=755 --from=buildimage /venv /venv
COPY --chown=root:solaredge2mqtt --chmod=755 \
    solaredge2mqtt/ ./solaredge2mqtt/
COPY --chown=root:solaredge2mqtt --chmod=755 \
    pyproject.toml README.md LICENSE ./
COPY --chown=root:root --chmod=755 docker-entrypoint.sh /usr/local/bin/
# solaredge2mqtt/_version.py bakes the exact git commit, so it differs on
# every build - never at repo root when this build starts (see
# build_project.yml's "Generate static solaredge2mqtt/_version.py" step,
# which moves it there before `docker build` runs). Copied in as its own
# layer, last, so the source tree above stays cache-reusable across builds
# of the same code and only this ~1KB layer is ever new.
COPY --chown=root:solaredge2mqtt --chmod=755 \
    _version.py ./solaredge2mqtt/_version.py

VOLUME ["/app/config"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python3", "-m", "solaredge2mqtt"]
