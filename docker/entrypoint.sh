#!/bin/sh
set -e

# Unraid passes PUID=99 / PGID=100; the image user is built at 1000:1000.
# Remap it so files on the mounted /config match the host's ownership.
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

if [ "$(id -g finalarr)" != "$PGID" ]; then
    groupmod -o -g "$PGID" finalarr
fi
if [ "$(id -u finalarr)" != "$PUID" ]; then
    usermod -o -u "$PUID" finalarr
fi

# A fresh appdata directory is often root-owned; SQLite needs to write here.
chown -R "$PUID:$PGID" /config

exec gosu "$PUID:$PGID" "$@"
