#!/bin/bash
set -e

# Take ownership of a mounted directory so the service can write in it.
#
# Ownership is fixed recursively, because the service rewrites files that are
# already there. The mode is not: a recursive chmod would strip secrets.yml of
# its 0600 and hand it to every other user of the host directory, and it would
# widen /app/cache from the 0700 the image sets. Only the owner bits of the
# directory itself are ensured, with X so that a plain file never becomes
# executable.
fix_permissions() {
    local dir=$1
    local required_owner=$2

    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir"
    fi

    current_owner=$(stat -c '%U:%G' "$dir" 2>/dev/null || echo "stat-failed:stat-failed")

    if [ "$current_owner" != "$required_owner" ]; then
        echo "Fixing ownership for $dir (current: $current_owner, required: $required_owner)"
        if ! chown -R "$required_owner" "$dir"; then
            echo "WARNING: Failed to change ownership of $dir" >&2
            return 1
        fi
    fi

    if ! chmod u+rwX "$dir"; then
        echo "WARNING: Failed to set permissions on $dir" >&2
        return 1
    fi
}

# Put secrets.yml back to 0600.
#
# Earlier images ran a recursive chmod 755 over the configuration directory,
# which left the secrets of every affected deployment readable by anyone with
# access to the host directory. Tightening it here repairs that on upgrade, and
# matches the mode the service uses when it writes the file itself.
harden_secrets() {
    local secrets="$1/secrets.yml"

    [ -f "$secrets" ] || return 0

    current_mode=$(stat -c '%a' "$secrets" 2>/dev/null || echo "")

    if [ -n "$current_mode" ] && [ "$current_mode" != "600" ]; then
        echo "Restricting $secrets to 0600 (was 0$current_mode)"
        if ! chmod 600 "$secrets"; then
            echo "WARNING: Failed to restrict permissions on $secrets" >&2
            return 1
        fi
    fi
}

echo "Checking and fixing directory permissions..."
fix_permissions "/app/config" "solaredge2mqtt:solaredge2mqtt" || true
fix_permissions "/app/cache" "solaredge2mqtt:solaredge2mqtt" || true
harden_secrets "/app/config" || true

# Always switch to solaredge2mqtt user before executing the main command
echo "Switching to solaredge2mqtt user..."
exec gosu solaredge2mqtt "$@"
