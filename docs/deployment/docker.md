# Docker

Images are published to `ghcr.io/deroetzi/solaredge2mqtt` for `linux/amd64` and `linux/arm64`.
32-bit ARM is no longer built, see
[decision 0004](../decisions/0004-drop-armv7-support.md) for why, and for a self-build recipe.

For a multi-container setup, see [Docker Compose](docker-compose.md).

## 1. Pull the image

```bash
docker pull ghcr.io/deroetzi/solaredge2mqtt:latest
```

## 2. Prepare the configuration directory

The container reads `/app/config`. Mount a host directory there. The SQLite history is written
to the same place, so it has to survive container restarts.

```bash
mkdir -p config
```

## 3. Create the configuration

=== "Let the container do it"

    Started against an empty directory, the service copies the examples in and exits:

    ```bash
    docker run -d --name solaredge2mqtt \
        -v $(pwd)/config:/app/config \
        -e "TZ=Europe/Berlin" \
        --restart unless-stopped \
        ghcr.io/deroetzi/solaredge2mqtt:latest

    # Edit what it created, then start again
    nano config/configuration.yml
    nano config/secrets.yml
    docker restart solaredge2mqtt
    ```

=== "Download them yourself"

    ```bash
    curl -o config/configuration.yml \
        https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example
    curl -o config/secrets.yml \
        https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example

    chmod 600 config/secrets.yml

    nano config/configuration.yml
    nano config/secrets.yml
    ```

What goes in those files is covered in
[First Configuration](../getting-started/configuration.md).

## 4. Run it

```bash
docker run -d --name solaredge2mqtt \
    -v $(pwd)/config:/app/config \
    -e "TZ=Europe/Berlin" \
    --restart unless-stopped \
    ghcr.io/deroetzi/solaredge2mqtt:latest
```

`TZ` is the only environment variable the service still needs. Everything else belongs in
`configuration.yml`.

## 5. Logs and stopping

```bash
docker logs solaredge2mqtt -f

docker stop solaredge2mqtt
docker rm solaredge2mqtt
```

## Permissions on the mounted directory

The service runs as UID 1000 inside the container, but a directory created on the host is owned
by whoever created it. Without a fix the service could not write its configuration or its
database.

### The container handles this itself

No manual setup is needed. At startup the entrypoint runs as root and, for both `/app/config`
and `/app/cache`:

1. creates the directory if it is missing,
2. compares the owner against `solaredge2mqtt:solaredge2mqtt`,
3. takes ownership recursively if it differs,
4. drops to the `solaredge2mqtt` user with `gosu` before the service starts.

The log line `Checking and fixing directory permissions...` marks that step.

File modes are left alone. Only ownership is transferred, so `secrets.yml` keeps its `600` and
`configuration.yml` keeps its `644`.

!!! note "Older images widened the secrets file"

    Images before 3.0.0 ran a recursive `chmod 755` over the configuration directory,
    which left `secrets.yml` readable by anyone with access to the host directory. On startup the
    entrypoint now puts it back to `600` and logs that it did:

    ```
    Restricting /app/config/secrets.yml to 0600 (was 0755)
    ```

    If you ran an affected image, treat the credentials in that file as having been exposed to
    other users of that host and rotate them.

### If it still fails

Symptoms are `[Errno 13] Permission denied` while writing, or a service that cannot create
`configuration.yml`, `secrets.yml` or the database.

```bash
sudo chown -R 1000:1000 ./config
```

If that does not settle it:

1. Check the ownership on the host with `ls -la ./config`.
2. Make sure the directory exists before the first start, `mkdir -p ./config`.
3. Look for the permission line in `docker logs solaredge2mqtt`.
4. On SELinux systems, add `:Z` to the mount: `-v $(pwd)/config:/app/config:Z`.

## Security note

The container starts as root only to fix the permissions described above, then drops privileges
with `gosu` to the `solaredge2mqtt` user before the application runs. The service itself never
runs as root.
