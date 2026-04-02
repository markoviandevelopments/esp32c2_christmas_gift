import time
import machine
import urequests
import os
import gc

machine.freq(120000000)

# === Pins & SPI (unchanged) ===
sck = machine.Pin(8, machine.Pin.OUT)
mosi = machine.Pin(20, machine.Pin.OUT)
dc = machine.Pin(9, machine.Pin.OUT)
rst = machine.Pin(19, machine.Pin.OUT)

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

# === Reset & Init (unchanged) ===
rst.value(1); time.sleep_ms(50)
rst.value(0); time.sleep_ms(50)
rst.value(1); time.sleep_ms(150)
# [your full init sequence - copy from your working version]

# === Window ===
def set_window(x0, y0, x1, y1):
    send_command(0x2A, bytes([0, x0, 0, x1]))
    send_command(0x2B, bytes([0, y0, 0, y1]))
    send_command(0x2C)

# === DNS-only proxy ===
mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes]).upper()

def get_base_url():
    try:
        server_ip = open('/server_ip.txt').read().strip()
        print("Loaded hostname from file:", server_ip)
    except OSError:
        server_ip = 'mosquitofish.immenseaccumulationonline.online'
        print("Using default hostname")
    return f'http://{server_ip}'

# === Photo constants ===
SRC_SIZE = 240
SCALE = 1
CHUNKS = 225
TOTAL_PIXELS = SRC_SIZE * SRC_SIZE

def update_photo():
    base_url = get_base_url()
    print("Base URL:", base_url)
    offset_x = (240 - SRC_SIZE * SCALE) // 2
    offset_y = (240 - SRC_SIZE * SCALE) // 2
    set_window(0, 0, 239, 239)
    pixel_index = 0
    for chunk_n in range(CHUNKS):
        try:
            url = f"{base_url}/pixel?n={chunk_n}&mac={mac_str}"
            print(f"Fetching chunk {chunk_n} → {url}")
            r = urequests.get(url, timeout=15)
            print(f"Status: {r.status_code} | Content length: {len(r.content)}")
            if r.status_code == 200 and len(r.content) == 512:
                data = r.content
                for i in range(0, 512, 2):
                    high = data[i]
                    low = data[i + 1]
                    sx = pixel_index % SRC_SIZE
                    sy = pixel_index // SRC_SIZE
                    x = offset_x + sx * SCALE
                    y = offset_y + sy * SCALE
                    for _ in range(SCALE * SCALE):
                        send_byte(high, 1)
                        send_byte(low, 1)
                    pixel_index += 1
                r.close()
            else:
                print("BAD RESPONSE")
                r.close()
                return False
        except Exception as e:
            print("EXCEPTION in chunk", chunk_n, ":", e)
            import sys
            sys.print_exception(e)
            return False
    print("All chunks succeeded!")
    return pixel_index == TOTAL_PIXELS

# === Font & draw_text (your full font dict) ===
# [paste your full font dictionary here exactly as before]

# === Main loop ===
it_C = 0
while True:
    if it_C > 0 and it_C % 30 == 0:
        machine.reset()
        it_C = 0
    set_window(0, 0, 239, 239)
    draw_text(90, 110, "LOADING...")
    print("=== Starting photo update ===")
    if update_photo():
        print("Photo update SUCCESS")
        draw_text(80, 100, "ENJOY!!!")
        draw_text(80, 120, " ")
        draw_text(80, 140, "-PRESTON AND WILLOH")
    else:
        print("Photo update FAILED")
        draw_text(40, 100, "NO PHOTO")
        draw_text(20, 130, "CHECK SERVER")
    current_time = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), current_time) < 6000:
        machine.idle()
    it_C += 1
