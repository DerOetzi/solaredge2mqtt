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
    
    # Fix permissions
    echo "Fixing permissions for $dir"
    chown -R "$required_owner" "$dir"
    chmod -R 755 "$dir"
}

# Always attempt to fix permissions automatically
echo "Checking and fixing directory permissions..."
fix_permissions "/app/config" "solaredge2mqtt:solaredge2mqtt" || true
fix_permissions "/app/cache" "solaredge2mqtt:solaredge2mqtt" || true

# Always switch to solaredge2mqtt user before executing the main command
echo "Switching to solaredge2mqtt user..."
exec gosu solaredge2mqtt "$@"
