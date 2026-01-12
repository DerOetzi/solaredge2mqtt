#!/bin/bash
set -e

# Function to check and fix directory permissions
fix_permissions() {
    local dir=$1
    local required_owner=$2
    
    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir"
    fi
    
    # Check if we can write to the directory
    if [ -w "$dir" ]; then
        return 0
    fi
    
    # Try to fix permissions (will only work if running as root)
    if [ "$(id -u)" -eq 0 ]; then
        echo "Fixing permissions for $dir"
        chown -R "$required_owner" "$dir"
        chmod -R 755 "$dir"
    else
        echo "WARNING: Cannot write to $dir and not running as root"
        echo "Please ensure the directory is writable by user ID $(id -u)"
        return 1
    fi
}

# Only run as root - if not root, something is wrong with the setup
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Entrypoint must run as root to manage permissions"
    echo "Remove 'USER' directive from Dockerfile or ensure container starts as root"
    exit 1
fi

# Check if FIX_PERMISSIONS is enabled
if [ "${FIX_PERMISSIONS:-false}" = "true" ]; then
    echo "FIX_PERMISSIONS enabled, attempting to fix directory permissions..."
    fix_permissions "/app/config" "solaredge2mqtt:solaredge2mqtt" || true
    fix_permissions "/app/cache" "solaredge2mqtt:solaredge2mqtt" || true
else
    # Just check permissions and warn if needed
    if [ ! -w "/app/config" ]; then
        echo "WARNING: /app/config is not writable."
        echo "This may cause issues during configuration migration."
        echo ""
        echo "To fix this, either:"
        echo "1. Set FIX_PERMISSIONS=true in your docker-compose.yml"
        echo "2. Manually fix permissions: chown -R 1000:1000 ./config"
        echo "3. Create config files manually before starting the container"
        echo ""
    fi
    
    if [ ! -w "/app/cache" ]; then
        echo "WARNING: /app/cache is not writable."
        echo "This may prevent forecast caching from working."
        echo ""
    fi
fi

# Always switch to solaredge2mqtt user before executing the main command
echo "Switching to solaredge2mqtt user..."
exec su-exec solaredge2mqtt "$@"
