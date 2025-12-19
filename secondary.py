# secondary.py - Display MAC address + heartbeat ping to server
import machine
import network
import time
import urequests
from st7735 import TFT

# === TFT Setup ===
sck_pin = machine.Pin(8)   # SCL
mosi_pin = machine.Pin(20) # SDA
dc_pin = machine.Pin(9)    # DC
rst_pin = machine.Pin(19)  # RES

spi = machine.SPI(1, baudrate=4000000, polarity=0, phase=0,
                  sck=sck_pin, mosi=mosi_pin)

tft = TFT(spi, dc_pin, rst_pin, None)
tft.init_7735(TFT.GREENTAB80x160)
tft.rotation(1)            # Adjust if needed for your wiring
tft.fill(TFT.BLACK)

# === Get MAC address ===
mac = network.WLAN(network.STA_IF).config('mac')
mac_str = ':'.join(['{:02x}'.format(b) for b in mac]).upper()

# === Server URL (from provisioned values stored by boot.py) ===
try:
    server_ip = open('/server_ip.txt').read().strip()
except OSError:
    server_ip = '108.254.1.184'
try:
    server_port = open('/server_port.txt').read().strip()
except OSError:
    server_port = '9019'

ping_url = f'http://{server_ip}:{server_port}/'

# === Display MAC address ===
tft.draw_small_text((5, 20), 'MAC:', TFT.WHITE)
tft.draw_small_text((5, 40), mac_str, TFT.CYAN)

tft.draw_small_text((5, 70), 'Pinging server', TFT.YELLOW)
tft.draw_small_text((5, 90), ping_url, TFT.GREEN)

# === Main loop - heartbeat ping every 10 seconds ===
while True:
    try:
        resp = urequests.get(ping_url, timeout=5)
        status = resp.status_code
        resp.close()
        color = TFT.GREEN if status == 200 else TFT.RED
        tft.draw_small_text((5, 120), f'Ping: {status}', color)
    except Exception as e:
        tft.draw_small_text((5, 120), 'Ping: FAIL', TFT.RED)

    time.sleep(10)
