import time
import machine
import urequests
import gc
import network
import os

# === Pins ===
sck = machine.Pin(8, machine.Pin.OUT)
mosi = machine.Pin(20, machine.Pin.OUT)
dc = machine.Pin(9, machine.Pin.OUT)
rst = machine.Pin(19, machine.Pin.OUT)

# === Bit-bang SPI ===
def send_byte(byte, is_data):
    dc.value(is_data)
    for _ in range(8):
        sck.value(0)
        mosi.value(byte & 0x80)
        byte <<= 1
        sck.value(1)
    sck.value(0)

def send_command(cmd, data=b''):
    send_byte(cmd, 0)
    for b in data:
        send_byte(b, 1)

# === Reset & Init ===
rst.value(1)
time.sleep_ms(50)
rst.value(0)
time.sleep_ms(50)
rst.value(1)
time.sleep_ms(150)

# GC9A01 init sequence
send_command(0xEF)
send_command(0xEB, b'\x14')
send_command(0xFE)
send_command(0xEF)
send_command(0xEB, b'\x14')
send_command(0x84, b'\x40')
send_command(0x85, b'\xFF')
send_command(0x86, b'\xFF')
send_command(0x87, b'\xFF')
send_command(0x88, b'\x0A')
send_command(0x89, b'\x21')
send_command(0x8A, b'\x00')
send_command(0x8B, b'\x80')
send_command(0x8C, b'\x01')
send_command(0x8D, b'\x01')
send_command(0x8E, b'\xFF')
send_command(0x8F, b'\xFF')
send_command(0xB6, b'\x00\x00')
send_command(0x3A, b'\x55')
send_command(0x90, b'\x08\x08\x08\x08')
send_command(0xBD, b'\x06')
send_command(0xBC, b'\x00')
send_command(0xFF, b'\x60\x01\x04')
send_command(0xC3, b'\x13')
send_command(0xC4, b'\x13')
send_command(0xC9, b'\x22')
send_command(0xBE, b'\x11')
send_command(0xE1, b'\x10\x0E')
send_command(0xDF, b'\x21\x0c\x02')
send_command(0xF0, b'\x45\x09\x08\x08\x26\x2A')
send_command(0xF1, b'\x43\x70\x72\x36\x37\x6F')
send_command(0xF2, b'\x45\x09\x08\x08\x26\x2A')
send_command(0xF3, b'\x43\x70\x72\x36\x37\x6F')
send_command(0xED, b'\x1B\x0B')
send_command(0xAE, b'\x77')
send_command(0xCD, b'\x63')
send_command(0x70, b'\x07\x07\x04\x0E\x0F\x09\x07\x08\x03')
send_command(0xE8, b'\x34')
send_command(0x62, b'\x18\x0D\x71\xED\x70\x70\x18\x0F\x71\xEF\x70\x70')
send_command(0x63, b'\x18\x11\x71\xF1\x70\x70\x18\x13\x71\xF3\x70\x70')
send_command(0x64, b'\x28\x29\xF1\x01\xF1\x00\x07')
send_command(0x66, b'\x3C\x00\xCD\x67\x45\x45\x10\x00\x00\x00')
send_command(0x67, b'\x00\x3C\x00\x00\x00\x01\x54\x10\x32\x98')
send_command(0x74, b'\x10\x85\x80\x00\x00\x4E\x00')
send_command(0x98, b'\x3e\x07')
send_command(0x35)
# REMOVED send_command(0x21)  <-- This was likely making everything black!
send_command(0x11)
time.sleep_ms(120)
send_command(0x29)
time.sleep_ms(20)

# === Window helpers ===
def set_window(x0, y0, x1, y1):
    send_command(0x2A, bytes([0, x0, 0, x1]))
    send_command(0x2B, bytes([0, y0, 0, y1]))
    send_command(0x2C)

def set_full_window():
    send_command(0x2A, bytes([0, 0, 0, 239]))
    send_command(0x2B, bytes([0, 0, 0, 239]))
    send_command(0x2C)

def display_raw_rgb565(data):
    set_full_window()
    i = 0
    while i < len(data):
        send_byte(data[i], 1)
        i += 1
        if i < len(data):
            send_byte(data[i], 1)
            i += 1

def draw_text(x_start, y_start, text):
    x = x_start
    for char in text.upper():
        if char in font:
            bitmap = font[char]
            for col in range(5):
                bits = bitmap[col]
                for row in range(8):
                    if bits & (1 << (7 - row)):
                        set_window(x + col, y_start + row, x + col, y_start + row)
                        send_byte(0xFF, 1)
                        send_byte(0xFF, 1)
            x += 6


# === TEST PATTERN - Checkerboard to prove display works ===
set_full_window()
for y in range(240):
    for x in range(240):
        color = 0xFF if (x // 20 + y // 20) % 2 else 0x00
        send_byte(color, 1)
        send_byte(0xFF if color else 0x00, 1)
time.sleep(3)

# Clear to black
set_full_window()
for _ in range(240 * 240):
    send_byte(0x00, 1)
    send_byte(0x00, 1)

draw_text(70, 110, "Loading...")

# === Wait for WiFi with feedback ===
def wait_for_wifi():
    sta = network.WLAN(network.STA_IF)
    if sta.isconnected():
        draw_text(70, 140, "WiFi OK")
        time.sleep(2)
        return True
    draw_text(50, 140, "Connecting.")
    for i in range(40):
        if sta.isconnected():
            draw_text(60, 140, "WiFi OK!")
            time.sleep(2)
            return True
        time.sleep(1)
        # Animate dots
        dots = "." * ((i // 5) % 4 + 1)
        draw_text(110, 140, dots.ljust(4))
    draw_text(50, 140, "No WiFi  ")
    return False

wait_for_wifi()

# === Server config - port 9025 hardcoded ===
try:
    server_ip = open('/server_ip.txt').read().strip()
except OSError:
    server_ip = '108.254.1.184'  # Update this to your actual desktop IP if needed

PHOTO_URL = f'http://{server_ip}:9025/image.raw'

# === Main loop ===
while True:
    gc.collect()
    success = False
    try:
        print("Fetching:", PHOTO_URL)
        r = urequests.get(PHOTO_URL, timeout=20)
        if r.status_code == 200 and len(r.content) == 115200:
            display_raw_rgb565(r.content)
            draw_text(60, 110, "Photo OK!")
            time.sleep(8)
            display_raw_rgb565(r.content)  # Clear text
            success = True
        r.close()
    except Exception as e:
        print("Error:", e)

    if not success:
        set_full_window()
        for _ in range(240 * 240):
            send_byte(0x00, 1)
            send_byte(0x00, 1)
        draw_text(40, 100, "Fetch Fail")
        draw_text(30, 130, "Check IP")

    time.sleep(52)
