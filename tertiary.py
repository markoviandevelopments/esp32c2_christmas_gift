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

font = {
    ' ': [0x00,0x00,0x00,0x00,0x00],
    '0': [0x7C,0xA2,0x92,0x8A,0x7C],
    '1': [0x00,0x42,0xFE,0x02,0x00],
    '2': [0x42,0x86,0x8A,0x92,0x62],
    '3': [0x84,0x82,0xA2,0xD2,0x8C],
    '4': [0x18,0x28,0x48,0xFE,0x08],
    '5': [0xE4,0xA2,0xA2,0xA2,0x9C],
    '6': [0x3C,0x52,0x92,0x92,0x0C],
    '7': [0x80,0x8E,0x90,0xA0,0xC0],
    '8': [0x6C,0x92,0x92,0x92,0x6C],
    '9': [0x60,0x92,0x92,0x94,0x78],
    ':': [0x00,0x36,0x36,0x00,0x00],
    '.': [0x00,0x00,0x00,0x06,0x06],
    '$': [0x24,0x54,0xFE,0x54,0x48],
    '-': [0x08,0x08,0x08,0x08,0x08],
    'A': [0x7E,0x90,0x90,0x90,0x7E],
    'B': [0xFE,0x92,0x92,0x92,0x6C],
    'C': [0x7C,0x82,0x82,0x82,0x44],
    'D': [0xFE,0x82,0x82,0x82,0x7C],
    'E': [0xFE,0x92,0x92,0x92,0x82],
    'F': [0xFE,0x90,0x90,0x90,0x80],
    'G': [0x7C,0x82,0x92,0x92,0x5C],
    'H': [0xFE,0x10,0x10,0x10,0xFE],
    'I': [0x00,0x82,0xFE,0x82,0x00],
    'J': [0x04,0x02,0x82,0xFC,0x80],
    'K': [0xFE,0x10,0x28,0x44,0x82],
    'L': [0xFE,0x02,0x02,0x02,0x02],
    'M': [0xFE,0x40,0x30,0x40,0xFE],
    'N': [0xFE,0x20,0x10,0x08,0xFE],
    'O': [0x7C,0x82,0x82,0x82,0x7C],
    'P': [0xFE,0x90,0x90,0x90,0x60],
    'Q': [0x7C,0x82,0x8A,0x84,0x7A],
    'R': [0xFE,0x90,0x98,0x94,0x62],
    'S': [0x62,0x92,0x92,0x92,0x8C],
    'T': [0x80,0x80,0xFE,0x80,0x80],
    'U': [0xFC,0x02,0x02,0x02,0xFC],
    'V': [0xF8,0x04,0x02,0x04,0xF8],
    'W': [0xFC,0x02,0x1C,0x02,0xFC],
    'X': [0xC6,0x28,0x10,0x28,0xC6],
    'Y': [0xE0,0x10,0x0E,0x10,0xE0],
    'Z': [0x86,0x8A,0x92,0xA2,0xC2],
}
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
