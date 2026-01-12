# Docker Deployment Guide

This guide covers deploying SolarEdge2MQTT using Docker and Docker Compose.

## Table of Contents

- [With Docker](#with-docker)
- [With Docker Compose](#with-docker-compose)
- [Permission Issues](#docker-permission-issues)
- [Migration from Environment Variables](#migrating-from-environment-variables)

## With Docker

Docker provides an isolated deployment approach with persistent configuration storage.

### 1. Pull the Image

```bash
docker pull ghcr.io/deroetzi/solaredge2mqtt:latest
```

### 2. Prepare Configuration Directory

```bash
mkdir -p config
```

### 3. Running with YAML Configuration (Recommended)

#### First Time Setup

```bash
# Download example files
curl -o config/configuration.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example
curl -o config/secrets.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example

# Edit the files with your settings
nano config/configuration.yml
nano config/secrets.yml

# Run the container
docker run -d --name solaredge2mqtt \
    -v $(pwd)/config:/app/config \
    -e "TZ=Europe/Berlin" \
    --restart unless-stopped \
    ghcr.io/deroetzi/solaredge2mqtt:latest
```

#### Alternative - Auto-Setup on First Run

```bash
# Run without configuration files
docker run -d --name solaredge2mqtt \
    -v $(pwd)/config:/app/config \
    -e "TZ=Europe/Berlin" \
    --restart unless-stopped \
    ghcr.io/deroetzi/solaredge2mqtt:latest

# The service will create example files in config/ and exit
# Edit the files, then restart:
docker restart solaredge2mqtt
```

### 4. View Logs

```bash
docker logs solaredge2mqtt -f
```

### 5. Stop Service

```bash
docker stop solaredge2mqtt
docker rm solaredge2mqtt
```

## With Docker Compose

For multi-container deployments with persistent configuration.

### 1. Download Files

Get the docker-compose.yml and example configuration files:

```bash
# Download docker-compose.yml
curl -o docker-compose.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/docker-compose.yml

# Create config directory and download examples
mkdir -p config
curl -o config/configuration.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example
curl -o config/secrets.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example
```

### 2. Configure

Edit your configuration files:

```bash
nano config/configuration.yml
nano config/secrets.yml
```

### 3. Start Service

```bash
docker compose up -d
```

### 4. View Logs

```bash
docker compose logs solaredge2mqtt -f
```

### 5. Stop Service

```bash
docker compose down
```

### New Installation

The `docker-compose.yml` file uses a volume mount for the config directory (`./config:/app/config`). On first run without configuration files, the service will create example files and exit. Edit them and restart with `docker compose up -d`.

## Docker Permission Issues

When using Docker volumes to mount the `config/` directory, you may encounter permission errors during configuration migration or when the service tries to write configuration files.

### Understanding the Issue

The container runs as user ID 1000 (`solaredge2mqtt`), but mounted directories from the host may be owned by a different user. The container automatically attempts to fix permissions at startup.

### Symptoms

- `[Errno 13] Permission denied` when writing configuration files
- Configuration migration fails with permission errors
- Service cannot create or update configuration files

### How It Works

The container **automatically fixes permissions** at startup:

1. Container starts as root
2. Entrypoint script checks `/app/config` and `/app/cache` directories
3. If directories are not writable, ownership is changed to `solaredge2mqtt:solaredge2mqtt` (UID 1000)
4. Container switches to `solaredge2mqtt` user before running the application

**No manual configuration is required** - the container handles permissions automatically.

### Alternative: Manual Permission Fix

If you prefer to set permissions manually on the host:

```bash
# Change ownership of the config directory to UID 1000
sudo chown -R 1000:1000 ./config
```

### Troubleshooting

If you still encounter permission issues:

1. **Check directory ownership on the host:**
   ```bash
   ls -la ./config
   ```

2. **Ensure the config directory exists before starting:**
   ```bash
   mkdir -p ./config
   ```

3. **Check container logs:**
   ```bash
   docker logs solaredge2mqtt
   ```
   
   You should see: "Checking and fixing directory permissions..."

4. **Create configuration files manually** before starting:
   ```bash
   mkdir -p config
   curl -o config/configuration.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example
   curl -o config/secrets.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example
   
   # Edit the files
   nano config/configuration.yml
   nano config/secrets.yml
   
   # Fix permissions
   sudo chown -R 1000:1000 ./config
   ```

## Migrating from Environment Variables

If you're upgrading from an older version that used environment variables, `.env` files, or Docker secrets, follow these steps:

### Option 1: Automatic Migration (Recommended)

Keep your environment variables for the first run, and the service will create YAML files automatically:

```bash
docker run -d --name solaredge2mqtt \
    -v $(pwd)/config:/app/config \
    -e "SE2MQTT_MODBUS__HOST=<INVERTER_IP>" \
    -e "SE2MQTT_MQTT__BROKER=<BROKER_IP>" \
    -e "SE2MQTT_MQTT__PASSWORD=<PASSWORD>" \
    -e "TZ=Europe/Berlin" \
    --restart unless-stopped \
    ghcr.io/deroetzi/solaredge2mqtt:latest
```

The service will detect environment variables and create YAML files in `config/`. After verifying:

```bash
docker stop solaredge2mqtt
docker rm solaredge2mqtt
docker run -d --name solaredge2mqtt \
    -v $(pwd)/config:/app/config \
    -e "TZ=Europe/Berlin" \
    --restart unless-stopped \
    ghcr.io/deroetzi/solaredge2mqtt:latest
```

### Option 2: Manual Migration Tool

Use the migration CLI tool:

```bash
docker run --rm \
    -v $(pwd)/config:/app/config \
    -v $(pwd)/.env:/app/.env:ro \
    ghcr.io/deroetzi/solaredge2mqtt:latest \
    solaredge2mqtt-migrate --input .env --output-dir config --backup
```

### With Docker Compose

If you're using Docker Compose:

**Automatic Migration**: Keep your `.env` file or environment variables in `docker-compose.yml` for the first run. The service will detect them and create YAML configuration files in the `config/` directory. After verifying the migration works, remove the environment variables from `docker-compose.yml` and restart.

**Manual Migration**:
```bash
docker compose run --rm solaredge2mqtt solaredge2mqtt-migrate --input .env --output-dir config --backup
docker compose up -d
```

For detailed migration instructions, see the [Migration Guide](MIGRATION_GUIDE.md).

## Security Note

The container starts as root to manage permissions but **immediately drops privileges** to the `solaredge2mqtt` user (UID 1000) before running the application. This follows the standard Docker security pattern for containers that need to perform privileged setup operations while running the application securely as a non-root user.

## Support

For issues or questions:
- [GitHub Issues](https://github.com/DerOetzi/solaredge2mqtt/issues)
- [Discord Community](https://discord.gg/QXfghc93pY)
