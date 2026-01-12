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
    
    # Get current owner of the directory
    current_owner=$(stat -c '%U:%G' "$dir" 2>/dev/null || echo "unknown:unknown")
    
    # Fix permissions if owner is not correct
    if [ "$current_owner" != "$required_owner" ]; then
        echo "Fixing ownership for $dir (current: $current_owner, required: $required_owner)"
        chown -R "$required_owner" "$dir"
        # Set proper directory permissions for access
        chmod -R 755 "$dir"
    fi
}

# Always attempt to fix permissions automatically
echo "Checking and fixing directory permissions..."
fix_permissions "/app/config" "solaredge2mqtt:solaredge2mqtt" || true
fix_permissions "/app/cache" "solaredge2mqtt:solaredge2mqtt" || true

# Always switch to solaredge2mqtt user before executing the main command
echo "Switching to solaredge2mqtt user..."
exec gosu solaredge2mqtt "$@"
