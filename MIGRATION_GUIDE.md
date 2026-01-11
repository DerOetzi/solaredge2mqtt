# Migration Guide: Environment Variables to YAML Configuration

## Overview

**⚠️ Breaking Change in Version 2.3.0**

Starting with version 2.3.0, SolarEdge2MQTT uses YAML-based configuration files instead of environment variables. This guide will help you migrate your existing setup to the new configuration format.

## Why the Change?

The migration to YAML configuration provides several benefits:
- **Better organization**: Structured, hierarchical configuration
- **Secret management**: Separate sensitive data with `!secret` tags
- **Easier maintenance**: Edit configuration without rebuilding containers
- **Version control friendly**: Configuration can be tracked in git (excluding secrets.yml)
- **Type safety**: Automatic validation of configuration values

## Configuration Structure

The new configuration uses two files:
- **`configuration.yml`**: Main configuration file with all non-sensitive settings
- **`secrets.yml`**: Sensitive data (passwords, tokens, API keys) with restrictive 600 permissions

## Migration Paths

SolarEdge2MQTT provides multiple migration paths to suit different scenarios:

### 1. Automatic Migration (Recommended for Most Users)

The service automatically migrates your configuration on first startup:

**When you start the service with existing environment variables:**

1. The service detects that `configuration.yml` doesn't exist
2. Reads environment variables from:
   - Current environment variables
   - `.env` file (if present)
   - Docker secrets in `/run/secrets/` (if present)
3. Automatically creates `configuration.yml` and `secrets.yml`
4. Separates sensitive values into `secrets.yml`
5. Starts normally with your migrated configuration

**When no environment variables exist (new installation):**

1. Copies example files to your config directory
2. Exits with a message asking you to configure the files
3. You edit the configuration files
4. Restart the service

**Console/Python Installation:**
```bash
# First run with environment variables set
export SE2MQTT_MODBUS__HOST=192.168.1.100
export SE2MQTT_MQTT__BROKER=mqtt.example.com
solaredge2mqtt

# Service auto-migrates and creates config/configuration.yml and config/secrets.yml
# On next run, remove environment variables - service now uses YAML files
```

### 2. Manual Migration with CLI Tool

For more control over the migration process, use the `solaredge2mqtt-migrate` command-line tool:

```bash
# Basic migration from .env file
solaredge2mqtt-migrate --input .env --output-dir config

# Preview changes without writing files
solaredge2mqtt-migrate --input .env --output-dir config --dry-run

# Create backups before migration
solaredge2mqtt-migrate --input .env --output-dir config --backup
```

**Migration tool options:**
- `--input PATH`: Path to .env file (default: `.env`)
- `--output-dir PATH`: Output directory for YAML files (default: `config`)
- `--dry-run`: Preview changes without writing files
- `--backup`: Create timestamped backups (e.g., `configuration.yml.backup.20260111_120000`)

**Benefits of manual migration:**
- Full control over timing
- Preview changes before applying
- Create backups automatically
- Useful for CI/CD pipelines

### 3. Docker Migration

#### Option A: Auto-Migration on First Run

Keep your existing environment variables for the first run, then switch to YAML:

**With docker run:**
```bash
# First run: Service auto-migrates environment variables
docker run -d \
  -v $(pwd)/config:/app/config \
  -e SE2MQTT_MODBUS__HOST=192.168.1.100 \
  -e SE2MQTT_MQTT__BROKER=mqtt.example.com \
  ghcr.io/deroetzi/solaredge2mqtt:latest

# Check the generated configuration files
ls -la config/

# Second run: Remove -e flags, use YAML configuration
docker run -d \
  -v $(pwd)/config:/app/config \
  ghcr.io/deroetzi/solaredge2mqtt:latest
```

**With docker-compose.yml:**
```yaml
# First run - keep environment section
version: '3'
services:
  solaredge2mqtt:
    image: ghcr.io/deroetzi/solaredge2mqtt:latest
    volumes:
      - ./config:/app/config
    environment:
      - SE2MQTT_MODBUS__HOST=192.168.1.100
      - SE2MQTT_MQTT__BROKER=mqtt.example.com

# After successful auto-migration, update to:
version: '3'
services:
  solaredge2mqtt:
    image: ghcr.io/deroetzi/solaredge2mqtt:latest
    volumes:
      - ./config:/app/config
    # Remove environment section - now using YAML files
```

#### Option B: Use Migration Tool in Container

Run the migration tool explicitly before starting the service:

```bash
# Create a temporary .env file with your settings
cat > .env << EOF
SE2MQTT_MODBUS__HOST=192.168.1.100
SE2MQTT_MQTT__BROKER=mqtt.example.com
SE2MQTT_MQTT__PASSWORD=secret123
EOF

# Run migration tool in container
docker run --rm \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/config:/app/config \
  ghcr.io/deroetzi/solaredge2mqtt:latest \
  solaredge2mqtt-migrate --input .env --output-dir config --backup

# Remove temporary .env file
rm .env

# Start service with YAML configuration
docker run -d -v $(pwd)/config:/app/config \
  ghcr.io/deroetzi/solaredge2mqtt:latest
```

#### Option C: Manually Create Configuration

Download and edit example files:

```bash
# Create config directory
mkdir -p config

# Download example files
curl -o config/configuration.yml \
  https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example

curl -o config/secrets.yml \
  https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example

# Edit the files with your settings
nano config/configuration.yml
nano config/secrets.yml

# Set proper permissions on secrets file
chmod 600 config/secrets.yml

# Start the service
docker run -d -v $(pwd)/config:/app/config \
  ghcr.io/deroetzi/solaredge2mqtt:latest
```

## Environment Variable Mapping

Environment variables are converted to YAML using double underscores (`__`) as separators:

### Example: Basic Settings

```bash
# Environment variable format
SE2MQTT_INTERVAL=5
SE2MQTT_LOGGING_LEVEL=INFO
```

Converts to:

```yaml
# configuration.yml
interval: 5
logging_level: INFO
```

### Example: Nested Settings

```bash
# Environment variable format
SE2MQTT_MODBUS__HOST=192.168.1.100
SE2MQTT_MODBUS__PORT=1502
SE2MQTT_MODBUS__TIMEOUT=1
```

Converts to:

```yaml
# configuration.yml
modbus:
  host: 192.168.1.100
  port: 1502
  timeout: 1
```

### Example: Sensitive Data (Auto-Detected)

```bash
# Environment variable format
SE2MQTT_MQTT__BROKER=mqtt.example.com
SE2MQTT_MQTT__USERNAME=homeassistant
SE2MQTT_MQTT__PASSWORD=secret123
SE2MQTT_MONITORING__PASSWORD=api_secret
```

Converts to:

```yaml
# configuration.yml
mqtt:
  broker: mqtt.example.com
  username: homeassistant
  password: !secret mqtt_password

monitoring:
  password: !secret monitoring_password
```

```yaml
# secrets.yml (created with 600 permissions)
mqtt_password: "secret123"
monitoring_password: "api_secret"
```

### Auto-Detected Sensitive Fields

The migration tool automatically identifies and separates these field types:
- Fields containing "password", "token", "key", "secret"
- `serial` fields (wallbox, inverter serial numbers)
- `site_id` (monitoring site ID)
- Any field using `SecretStr` type in the codebase

## Configuration Directory Location

By default, configuration files are stored in `./config/`. You can customize this:

### Console/Python Usage

```bash
# Use default config directory (./config/)
solaredge2mqtt

# Use custom config directory
solaredge2mqtt --config-dir /etc/solaredge2mqtt

# Use custom directory in migration
solaredge2mqtt-migrate --output-dir /etc/solaredge2mqtt
```

### Docker Usage

```bash
# Mount config directory to /app/config in container
docker run -d \
  -v /my/custom/path:/app/config \
  ghcr.io/deroetzi/solaredge2mqtt:latest

# Container always looks in /app/config, but you control what's mounted there
```

### Docker Compose Usage

```yaml
version: '3'
services:
  solaredge2mqtt:
    image: ghcr.io/deroetzi/solaredge2mqtt:latest
    volumes:
      - /my/custom/path:/app/config  # Mount your config location
```

## Post-Migration Steps

After migrating your configuration, follow these steps to ensure everything works correctly:

### 1. Verify Generated Files

Check that both files were created with correct content:

```bash
# List files with permissions
ls -la config/

# Should show:
# -rw-r--r-- configuration.yml
# -rw------- secrets.yml (600 permissions)

# Review the content
cat config/configuration.yml
cat config/secrets.yml
```

### 2. Validate Configuration

Ensure all your settings were migrated correctly:

```bash
# Check for any obvious issues
grep -i "error\|warning" config/configuration.yml

# Verify secrets are properly referenced
grep "!secret" config/configuration.yml
```

### 3. Test the Service

Start the service and check the logs:

```bash
# Console mode
solaredge2mqtt

# Docker
docker logs <container_name>

# Docker Compose
docker compose logs solaredge2mqtt
```

Look for these log messages:
```
INFO | Loaded secrets from config/secrets.yml
INFO | Loaded configuration from config/configuration.yml
```

### 4. Clean Up Old Configuration

After confirming everything works:

**For console/Python installations:**
```bash
# Remove old .env file (after backing up if needed)
mv .env .env.backup.old
# Or delete it
rm .env
```

**For Docker installations:**
```bash
# Remove environment variables from docker-compose.yml
# Remove .env file
# Remove Docker secrets configuration
```

### 5. Backup New Configuration

Protect your new configuration files:

```bash
# Create a backup
tar -czf config-backup-$(date +%Y%m%d).tar.gz config/

# Or use git (exclude secrets.yml!)
cd config
echo "secrets.yml" >> .gitignore
git add configuration.yml .gitignore
git commit -m "Add YAML configuration"
```

## Troubleshooting

### Issue: Service Can't Find Configuration Files

**Symptoms:**
- Error: "Configuration file not found"
- Service exits immediately

**Solutions:**
1. Verify config directory exists and contains files:
   ```bash
   ls -la config/
   ```

2. Check file permissions:
   ```bash
   chmod 644 config/configuration.yml
   chmod 600 config/secrets.yml
   ```

3. For Docker, verify volume mount:
   ```bash
   docker inspect <container_name> | grep Mounts -A 10
   ```

### Issue: Secret References Not Working

**Symptoms:**
- Error: "Secret 'xyz' not found in secrets.yml"
- Authentication failures

**Solutions:**
1. Verify secrets.yml contains all referenced secrets:
   ```bash
   grep "!secret" config/configuration.yml
   cat config/secrets.yml
   ```

2. Check secrets.yml syntax (must be valid YAML):
   ```yaml
   # Correct
   mqtt_password: "secret123"
   
   # Incorrect (missing quotes for special characters)
   mqtt_password: secret@123!
   ```

3. Ensure secret names match exactly (case-sensitive):
   ```yaml
   # configuration.yml
   password: !secret mqtt_password  # Must match exactly
   
   # secrets.yml
   mqtt_password: "secret"  # Not MQTT_PASSWORD or mqtt_Password
   ```

### Issue: Migration Tool Fails

**Symptoms:**
- "ModuleNotFoundError" or import errors
- Migration doesn't create files

**Solutions:**
1. Ensure SolarEdge2MQTT is properly installed:
   ```bash
   pip install --upgrade solaredge2mqtt
   ```

2. Verify .env file format:
   ```bash
   # Each line should be: KEY=VALUE
   # No spaces around =
   # No quotes needed (added automatically)
   SE2MQTT_MODBUS__HOST=192.168.1.100
   ```

3. Check output directory permissions:
   ```bash
   mkdir -p config
   chmod 755 config
   ```

### Issue: Docker Container Can't Write Files

**Symptoms:**
- Permission denied errors
- Configuration files not created

**Solutions:**
1. Ensure volume directory exists and is writable:
   ```bash
   mkdir -p config
   chmod 755 config
   ```

2. Check container user permissions:
   ```bash
   # Container runs as specific user, may need ownership
   sudo chown -R 1000:1000 config/
   ```

3. On SELinux systems:
   ```bash
   chcon -Rt svirt_sandbox_file_t config/
   # Or add :Z to volume mount
   docker run -v $(pwd)/config:/app/config:Z ...
   ```

### Issue: Values Not Migrating Correctly

**Symptoms:**
- Boolean values as strings
- Numbers as strings
- Lists not recognized

**Solutions:**
1. Check data types in migrated YAML:
   ```yaml
   # Correct types
   port: 1502                    # number
   enable: true                  # boolean
   meter: [true, true, false]    # list
   
   # Incorrect (all strings)
   port: "1502"
   enable: "true"
   ```

2. Re-run migration with correct .env format:
   ```bash
   # In .env file, don't quote values
   SE2MQTT_MODBUS__PORT=1502              # Not "1502"
   SE2MQTT_MODBUS__METER__0=true          # Not "true"
   ```

## Advanced Topics

### Using Multiple Configuration Files

You can split configuration across multiple files:

```bash
# Use different config directories for different environments
solaredge2mqtt --config-dir /etc/solaredge2mqtt/production
solaredge2mqtt --config-dir /etc/solaredge2mqtt/testing
```

### Configuration in CI/CD Pipelines

For automated deployments:

```yaml
# Example GitLab CI
deploy:
  script:
    - solaredge2mqtt-migrate --input .env --output-dir /deploy/config --backup
    - docker compose up -d
```

### Secrets Management Integration

For production environments, consider using external secret management:

```yaml
# configuration.yml can reference environment variables for secrets
mqtt:
  broker: mqtt.example.com
  password: !secret mqtt_password

# secrets.yml can be generated from your secret manager
# e.g., Vault, AWS Secrets Manager, Azure Key Vault
```

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [GitHub Issues](https://github.com/DerOetzi/solaredge2mqtt/issues) page
2. Join our [Discord community](https://discord.gg/QXfghc93pY)
3. Review the main [README.md](README.md) for general configuration help
4. Enable debug logging for more information:
   ```yaml
   logging_level: DEBUG
   ```

## Summary

The migration from environment variables to YAML configuration provides a more robust and maintainable configuration system. Key takeaways:

- ✅ **Automatic migration** handles most scenarios seamlessly
- ✅ **Manual migration tool** provides control and preview capabilities
- ✅ **Multiple Docker migration options** to suit your workflow
- ✅ **Sensitive data separation** with `!secret` tags and 600 permissions
- ✅ **Configurable directory location** with `--config-dir`
- ✅ **Backward compatible** with automatic migration on first run

For most users, the automatic migration on first startup is the easiest path. Simply start the service with your existing environment variables, and it will create the new configuration files for you.
