# secondary.py - Simple server ping loop with display feedback
import time
import urequests
from st7735 import TFT
import machine
import network

# === Display init (your working settings) ===
sck_pin = machine.Pin(8)
mosi_pin = machine.Pin(20)
dc_pin = machine.Pin(9)
rst_pin = machine.Pin(19)

spi = machine.SPI(1, baudrate=4000000, polarity=0, phase=0,
                  sck=sck_pin, mosi=mosi_pin)

tft = TFT(spi, dc_pin, rst_pin, None)
tft.init_7735(TFT.GREENTAB80x160)
tft.rotation(1)
tft.fill(TFT.BLACK)

def display_status(line1, line2="", line3="", color=TFT.WHITE):
    tft.fill(TFT.BLACK)
    tft.draw_small_text((5, 15), line1, color)
    if line2:
        tft.draw_small_text((5, 40), line2, color)
    if line3:
        tft.draw_small_text((5, 65), line3, color)

display_status("Secondary Running", "Pinging server...", "", TFT.CYAN)

# === Load server IP/port from files (saved by boot.py) ===
try:
    server_ip = open('/server_ip.txt').read().strip()
except OSError:
    server_ip = '108.254.1.184'  # default

try:
    server_port = open('/server_port.txt').read().strip()
except OSError:
    server_port = '9019'  # default

ping_url = f'http://{server_ip}:{server_port}/'

display_status("Ping URL:", ping_url, "Starting loop...", TFT.YELLOW)

# === Main ping loop ===
while True:
    try:
        resp = urequests.get(ping_url, timeout=10)
        status = resp.status_code
        resp.close()
        if status == 200:
            display_status("Ping SUCCESS", ping_url, f"Code: {status}", TFT.GREEN)
        else:
            display_status("Ping FAILED", ping_url, f"Code: {status}", TFT.RED)
    except Exception as e:
        display_status("Ping ERROR", ping_url, "No response", TFT.RED)

    time.sleep(10)
