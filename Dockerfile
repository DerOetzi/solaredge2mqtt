FROM python:3.12-slim AS buildimage

ARG TARGETARCH

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

COPY requirements*.txt .

RUN set -eux && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /venv && \
    . /venv/bin/activate && \
    pip install --upgrade pip && \
    if [ "$TARGETARCH" = "arm" ]; then \
    pip install \
    --prefer-binary \
    --no-cache-dir \
    --extra-index-url https://www.piwheels.org/simple \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements-armv7.txt; \
    else  \
    pip install \
    --prefer-binary \
    --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt; \
    fi 

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

RUN set -eux && \
    apt-get update && \
    apt-get install -y --no-install-recommends su-exec && \
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

USER solaredge2mqtt

VOLUME ["/app/config"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python3", "-m", "solaredge2mqtt"]
