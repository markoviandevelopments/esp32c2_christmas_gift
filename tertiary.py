from machine import Pin, SPI
import gc9a01
import urequests
import network
import time
import os
import gc

# === Hardware SPI setup (same pins that worked for you) ===
spi = SPI(1, baudrate=60000000, sck=Pin(8), mosi=Pin(20))

# === Display object ===
tft = gc9a01.GC9A01(
    spi,
    240,
    240,
    reset=Pin(19, Pin.OUT),
    dc=Pin(9, Pin.OUT),
    rotation=0)  # Change 0-7 if orientation is wrong

tft.init()
tft.fill(gc9a01.BLACK)

# === Simple text function using built-in font ===
def draw_centered_text(text, y, color=gc9a01.WHITE):
    # Rough centering: text is ~8px high, width approx len(text)*8
    x = 120 - (len(text) * 4)  # Adjust multiplier if needed
    tft.text(text, x, y, color)

# === Startup message ===
draw_centered_text("Loading...", 100)
draw_centered_text("XH-C2X Display", 140)

# === Server config - photo server on port 9025 ===
try:
    server_ip = open('/server_ip.txt').read().strip()
except OSError:
    server_ip = '192.168.1.198'  # Update to your desktop IP if different

PHOTO_URL = f'http://{server_ip}:9025/image.raw'

# === Main photo slideshow loop ===
while True:
    gc.collect()
    tft.fill(gc9a01.BLACK)
    draw_centered_text("Fetching Photo...", 100)
    
    success = False
    try:
        print("Fetching photo from:", PHOTO_URL)
        r = urequests.get(PHOTO_URL, timeout=20)
        if r.status_code == 200 and len(r.content) == 115200:  # 240*240*2 bytes
            tft.jpeg(r.content, 0, 0, gc9a01.SLOW)  # Not JPEG — use raw bitmap
            # Actually use bitmap for raw RGB565 data
            tft.bitmap(r.content, 0, 0, 240, 240)
            success = True
            draw_centered_text("Hello Preston", 80, gc9a01.WHITE)
            draw_centered_text("& Willoh!", 120, gc9a01.YELLOW)
            time.sleep(8)
        r.close()
    except Exception as e:
        print("Photo fetch error:", e)
    
    if not success:
        tft.fill(gc9a01.BLACK)
        draw_centered_text("No Photo", 80)
        draw_centered_text("Check Server", 120)
    
    time.sleep(52)  # Total ~60 second cycle
