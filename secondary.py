# secondary.py - Tracking ping + display "h" on TFT
import network
import urequests
import time
import machine
import ubinascii
from st7735 import TFT

# Display setup (your working config)
sck_pin = machine.Pin(8)
mosi_pin = machine.Pin(20)
dc_pin = machine.Pin(9)
rst_pin = machine.Pin(19)

spi = machine.SPI(1, baudrate=4000000, polarity=0, phase=0, sck=sck_pin, mosi=mosi_pin)

tft = TFT(spi, dc_pin, rst_pin, None)
tft.init_7735(TFT.GREENTAB80x160)
tft.rotation(1)

# STA interface and MAC
sta = network.WLAN(network.STA_IF)
mac = ubinascii.hexlify(sta.config('mac'), ':').decode().upper()

# Server from files (fallback defaults)
try:
    server_ip = open('/server_ip.txt').read().strip()
    server_port = open('/server_port.txt').read().strip()
except:
    server_ip = '108.254.1.184'
    server_port = '9019'

url = f'http://{server_ip}:{server_port}/ping'

# Display "h" centered (large-ish)
def show_h():
    tft.fill(TFT.BLACK)  # White background
    w, h = tft.size()
    text = "h"
    text_width = len(text) * 6
    x = (w - text_width) // 2
    y = (h - 8) // 2
    tft.draw_small_text((x, y), text, TFT.WHITE, mirror=False)

show_h()  # Initial display

# Ping loop
while True:
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        uptime = time.ticks_ms() // 1000
        payload = '{"mac":"' + mac + '","ip":"' + ip + '","uptime":' + str(uptime) + '}'
        try:
            urequests.post(url, data=payload, headers={'Content-Type': 'application/json'})
        except:
            pass
        show_h()  # Refresh "h" after each ping (keeps screen alive)
    time.sleep(300)  # 5 minutes
