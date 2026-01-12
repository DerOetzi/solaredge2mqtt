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

# Check if running as root with environment variable to allow permission fixes
if [ "${FIX_PERMISSIONS:-false}" = "true" ] && [ "$(id -u)" -eq 0 ]; then
    echo "FIX_PERMISSIONS enabled, attempting to fix directory permissions..."
    fix_permissions "/app/config" "solaredge2mqtt:solaredge2mqtt" || true
    fix_permissions "/app/cache" "solaredge2mqtt:solaredge2mqtt" || true
    
    # Switch to solaredge2mqtt user
    echo "Switching to solaredge2mqtt user..."
    exec su-exec solaredge2mqtt "$@"
fi

# If not root or FIX_PERMISSIONS not set, just check permissions
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

# Execute the main command
exec "$@"
