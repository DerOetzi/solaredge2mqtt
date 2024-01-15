FROM python:3.10 AS buildimage

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/venv/bin:$PATH"

RUN set -eux; \
    python3 -m venv /venv;

COPY requirements.txt .

RUN set -eux; \
    pip3 install \
    --no-cache-dir \
    --extra-index-url https://www.piwheels.org/simple \
    -r requirements.txt; 

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

RUN adduser --uid 1000 --disabled-password --gecos '' --no-create-home solaredge2mqtt

COPY --chown=solaredge2mqtt:solaredge2mqtt --from=buildimage /venv /venv
COPY --chown=solaredge2mqtt:solaredge2mqtt . .

USER solaredge2mqtt                                                                      
CMD ["python3", "-m", "solaredge2mqtt"]
