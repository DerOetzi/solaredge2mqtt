#!/bin/bash -x

set -euo pipefail

NEW_USER_ID=${USER_ID}
NEW_GROUP_ID=${GROUP_ID:-$NEW_USER_ID}

echo "Starting with solaredge2mqtt user id: $NEW_USER_ID and group id: $NEW_GROUP_ID"
if ! id -u solaredge2mqtt >/dev/null 2>&1; then
  if [ -z "$(getent group $NEW_GROUP_ID)" ]; then
    echo "Create group solaredge2mqtt with id ${NEW_GROUP_ID}"
    groupadd -g $NEW_GROUP_ID solaredge2mqtt
  else
    group_name=$(getent group $NEW_GROUP_ID | cut -d: -f1)
    echo "Rename group $group_name to solaredge2mqtt"
    groupmod --new-name solaredge2mqtt $group_name
  fi
  echo "Create user solaredge2mqtt with id ${NEW_USER_ID}"
  adduser -u $NEW_USER_ID --disabled-password --gecos '' --home "${SE2MQTT_HOME}" --gid $NEW_GROUP_ID solaredge2mqtt
fi

chown -R solaredge2mqtt:solaredge2mqtt "${SE2MQTT_HOME}"
sync

exec "$@"