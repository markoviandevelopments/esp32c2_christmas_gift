#!/bin/bash
# Flash rectangular boot SOURCE. Hold BOOT button if "could not enter raw repl".
set -euo pipefail
PORT="${1:-/dev/ttyUSB0}"
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Flashing $DIR/boot.py → $PORT:/boot.py"
echo "If this fails: hold BOOT, press RESET, release RESET, keep holding BOOT, run again."
# Soft interrupt then copy (do not soft-reset into a brownout loop mid-transfer)
mpremote connect "$PORT" eval "print('ok')" 2>/dev/null || true
mpremote connect "$PORT" fs cp "$DIR/boot.py" :boot.py
# Optional: pre-seed secondary so first boot works even if OTA fails
if [ -f "$DIR/secondary.mpy" ]; then
  echo "Also putting secondary.mpy ..."
  mpremote connect "$PORT" fs cp "$DIR/secondary.mpy" :secondary.mpy || true
fi
echo "Reset the board (power cycle recommended if BOD was firing)."
echo "With saved WiFi it should SKIP BLE and pull secondary.mpy."
