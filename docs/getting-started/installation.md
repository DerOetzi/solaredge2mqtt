# Installation

Pick the way you want to run the service. All three end up at the same place: a `config/`
directory holding `configuration.yml` and `secrets.yml`, which the
[configuration guide](configuration.md) walks you through filling in.

=== "Console"

    Requires Python 3.12 or 3.13.

    ```bash
    pip install -U solaredge2mqtt

    # Forecasting pulls in a machine learning stack, so it is optional
    pip install -U "solaredge2mqtt[forecast]"
    ```

    Start it once in the directory where the configuration should live:

    ```bash
    solaredge2mqtt
    ```

    The service writes example files into `config/` and exits, asking you to edit them.

=== "Docker"

    ```bash
    mkdir -p config

    docker run -d --name solaredge2mqtt \
        -v $(pwd)/config:/app/config \
        -e "TZ=Europe/Berlin" \
        --restart unless-stopped \
        ghcr.io/deroetzi/solaredge2mqtt:latest
    ```

    The container writes example files into `config/` and exits. Edit them, then
    `docker restart solaredge2mqtt`.

    More detail, including the permission handling for the mounted directory, is in
    [Docker deployment](../deployment/docker.md).

=== "Docker Compose"

    ```bash
    curl -o docker-compose.yml \
        https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/docker-compose.yml

    mkdir -p config
    docker compose up -d
    ```

    The service writes example files into `config/` and exits. Edit them, then
    `docker compose up -d` again.

    See [Docker Compose](../deployment/docker-compose.md), and
    [Grafana](../deployment/grafana.md) if you want dashboards alongside it.

## Downloading the examples yourself

The service copies these two files in on its first start, but you can fetch them up front:

```bash
mkdir -p config

curl -o config/configuration.yml \
    https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example
curl -o config/secrets.yml \
    https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example

chmod 600 config/secrets.yml
```

!!! warning "Protect the secrets file"

    `secrets.yml` holds your broker password and monitoring credentials in plain text. The
    service creates it with `600` permissions; if you download it yourself, set them.

## Which Python versions work

Python 3.12 and 3.13 are supported and tested. The published Docker images cover `linux/amd64`
and `linux/arm64`. 32-bit ARM images are no longer built, see
[decision 0004](../decisions/0004-drop-armv7-support.md) for the reasoning and a self-build
recipe.

## Next steps

1. [Write your configuration](configuration.md).
2. [Run the service](running.md), in the foreground or as a system service.
3. Work through the [configuration reference](../configuration/index.md) for the features you
   want.
