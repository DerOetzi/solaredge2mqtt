FROM python:3.10-slim AS buildimage

COPY container/requirements.txt requirements.txt

RUN set -eux; \
    pip3 wheel \
    --wheel-dir=/root/wheels \
    --extra-index-url https://www.piwheels.org/simple \
    -r requirements.txt

FROM python:3.10-slim

ENV SE2MQTT_HOME=/solaredge2mqtt \
    USER_ID=9002 \
    GROUP_ID=9002

COPY --from=buildimage /root/wheels /root/wheels
COPY container/*.whl /root/wheels
COPY entrypoint.sh /

RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
    gosu \
    tini; \
    ln -s -f $(which gosu) /usr/local/bin/gosu; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p ${SE2MQTT_HOME}/brains; \
    cd ${SE2MQTT_HOME}; \
    pip3 install \
    --no-index \
    --find-links=/root/wheels \
    solaredge2mqtt; \
    chmod +x /entrypoint.sh; \
    rm -rf /root/wheels;

WORKDIR ${SE2MQTT_HOME}
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gosu", "solaredge2mqtt", "tini", "-s", "solaredge2mqtt"]
