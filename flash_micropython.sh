#!/bin/bash
esptool.py --chip esp32c2 --port /dev/ttyUSB* erase_flash
esptool.py --chip esp32c2 --port /dev/ttyUSB* --baud 460800 write_flash -z 0x0 ESP32_GENERIC_C2-FLASH_2M-20251209-v1.27.0.bin
