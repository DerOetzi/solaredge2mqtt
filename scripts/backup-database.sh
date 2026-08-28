#!/usr/bin/env bash

# Write a consistent copy of the storage database next to the original.
#
# The service keeps running while the backup is taken. The database is in
# write-ahead-log mode, so a plain cp can miss the -wal sidecar and produce an
# inconsistent file. SQLite itself is used instead: "VACUUM INTO" writes a
# compacted single file without sidecars, and the backup API of the Python
# standard library serves as a fallback where the sqlite3 CLI is missing.
#
# Usage:
#   scripts/backup-database.sh                    # from the repository root
#   docker exec solaredge2mqtt backup-database.sh # inside the container
#
# The result is <config>/solaredge2mqtt.db.backup.<YYYYmmddHHMMSS>.

set -euo pipefail

CONFIG_DIR="${SE2MQTT_CONFIG_DIR:-}"
DATABASE="${SE2MQTT_DATABASE:-}"
KEEP=0

usage() {
    cat <<'EOF'
Back up the SolarEdge2MQTT storage database while the service is running.

Options:
  -c, --config-dir PATH  Configuration directory holding the database.
                         Default: ./config, or /app/config in the container.
  -d, --database PATH    Database file, overrides --config-dir.
  -k, --keep N           Delete all but the N newest backups afterwards.
                         Default: 0, keep every backup.
  -h, --help             Show this help.

Environment:
  SE2MQTT_CONFIG_DIR, SE2MQTT_DATABASE  Same meaning as the options above.
EOF
}

die() {
    echo "error: $*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
    -c | --config-dir)
        CONFIG_DIR="${2:-}"
        shift 2
        ;;
    -d | --database)
        DATABASE="${2:-}"
        shift 2
        ;;
    -k | --keep)
        KEEP="${2:-0}"
        shift 2
        ;;
    -h | --help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        die "unknown argument: $1"
        ;;
    esac
done

if [[ -z "$DATABASE" ]]; then
    if [[ -z "$CONFIG_DIR" ]]; then
        for candidate in "./config" "/app/config"; do
            if [[ -d "$candidate" ]]; then
                CONFIG_DIR="$candidate"
                break
            fi
        done
    fi

    [[ -n "$CONFIG_DIR" ]] || die "no configuration directory found, pass --config-dir"
    DATABASE="$CONFIG_DIR/solaredge2mqtt.db"
fi

[[ -f "$DATABASE" ]] || die "database not found: $DATABASE"

BACKUP="$DATABASE.backup.$(date +%Y%m%d%H%M%S)"
[[ -e "$BACKUP" ]] && die "backup already exists: $BACKUP"

if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DATABASE" "VACUUM INTO '$BACKUP'"
elif command -v python3 >/dev/null 2>&1; then
    python3 - "$DATABASE" "$BACKUP" <<'EOPY'
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
with target:
    source.backup(target)
target.close()
source.close()
EOPY
else
    die "neither sqlite3 nor python3 is available"
fi

# Inside the container the service runs as solaredge2mqtt while docker exec
# defaults to root, so hand the backup to whoever owns the database. It carries
# the same history and deserves the same 0600 the service uses.
chmod 600 "$BACKUP"
if [[ "$(id -u)" == "0" ]]; then
    chown "$(stat -c '%u:%g' "$DATABASE")" "$BACKUP"
fi

echo "Wrote $BACKUP ($(du -h "$BACKUP" | cut -f1))"

if [[ "$KEEP" -gt 0 ]]; then
    # ls sorts by modification time, so the tail of the list is the oldest.
    mapfile -t obsolete < <(ls -1t "$DATABASE".backup.* 2>/dev/null | tail -n "+$((KEEP + 1))")
    for old in "${obsolete[@]}"; do
        echo "Removing $old"
        rm -f "$old"
    done
fi
