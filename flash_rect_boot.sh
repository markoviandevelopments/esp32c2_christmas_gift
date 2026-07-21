#!/bin/bash
set -euo pipefail
PORT="${1:-/dev/ttyUSB0}"
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Port: $PORT"
mpremote connect "$PORT" fs cp "$DIR/boot.py" :boot.py
[ -f "$DIR/secondary.mpy" ] && mpremote connect "$PORT" fs cp "$DIR/secondary.mpy" :secondary.mpy || true
echo "Power-cycle the board (recommended after brownouts)."
