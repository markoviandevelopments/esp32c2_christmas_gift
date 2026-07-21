#!/bin/bash
# Flash rectangular-screen boot SOURCE (MicroPython runs /boot.py as text, not .mpy)
set -e
PORT="${1:-/dev/ttyUSB0}"
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Putting $DIR/boot.py → $PORT:/boot.py"
ampy --port "$PORT" --baud 115200 put "$DIR/boot.py" /boot.py
echo "Done. Reset the board; it should advertise XH-C2X or join saved WiFi."
