#!/bin/bash
# Flash rectangular-screen boot SOURCE onto ESP32-C2 MicroPython filesystem.
set -euo pipefail
PORT="${1:-/dev/ttyUSB0}"
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Port: $PORT"
echo "Putting boot.py (SOURCE) ..."
# Soft-reset into raw REPL if possible, then write
mpremote connect "$PORT" reset || true
sleep 1
mpremote connect "$PORT" fs cp "$DIR/boot.py" :boot.py
echo "Also ensuring secondary.mpy is available for offline first run (optional)..."
if [ -f "$DIR/secondary.mpy" ]; then
  mpremote connect "$PORT" fs cp "$DIR/secondary.mpy" :secondary.mpy || true
fi
echo "Resetting..."
mpremote connect "$PORT" reset || true
echo "Done. Watch serial: mpremote connect $PORT repl"
echo "Device should advertise XH-C2X or join saved WiFi and pull secondary.mpy"
