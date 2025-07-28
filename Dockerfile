FROM python:3.12 AS buildimage

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

COPY requirements.txt .

RUN python3 -m venv /venv && \
    . /venv/bin/activate && \
    pip install --upgrade pip && \
    pip install \
    --no-cache-dir \
    --extra-index-url https://www.piwheels.org/simple \
    -r requirements.txt

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

RUN adduser --uid 1000 --disabled-password --gecos '' --no-create-home solaredge2mqtt

COPY --chown=solaredge2mqtt:solaredge2mqtt --from=buildimage /venv /venv
COPY --chown=solaredge2mqtt:solaredge2mqtt . .

USER solaredge2mqtt

CMD ["python3", "-m", "solaredge2mqtt"]
