#!/bin/bash
set -e
PORT="${1:-/dev/ttyUSB0}"
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Flash rect boot SOURCE → $PORT"
mpremote connect "$PORT" fs cp "$DIR/boot.py" :boot.py
mpremote connect "$PORT" reset || true
echo "OK"
