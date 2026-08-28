# Docker Compose

The single-service setup. For dashboards alongside it, see [Grafana](grafana.md).

## The compose file

The one shipped in the repository is deliberately minimal:

```yaml
--8<-- "docker-compose.yml"
```

Download it:

```bash
curl -o docker-compose.yml \
    https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/docker-compose.yml
```

## Configure

```bash
mkdir -p config
docker compose up -d
```

The service copies the example files into `config/` and exits on the first start. Edit them,
then bring it up again:

```bash
nano config/configuration.yml
nano config/secrets.yml
chmod 600 config/secrets.yml

docker compose up -d
```

What belongs in those files is covered in
[First Configuration](../getting-started/configuration.md).

If you would rather have the files before the first start, the `curl` commands are on the
[Docker page](docker.md#3-create-the-configuration).

## Day to day

```bash
docker compose logs solaredge2mqtt -f
docker compose pull && docker compose up -d   # upgrade
docker compose down
```

## Permissions

The container fixes the ownership of the mounted directory itself, with the one caveat about
file modes described under
[Permissions on the mounted directory](docker.md#permissions-on-the-mounted-directory).
