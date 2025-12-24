import time
import machine
import urequests
import os
import gc

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

# === Reset & Init (your working sequence) ===
rst.value(1)
time.sleep_ms(50)
rst.value(0)
time.sleep_ms(50)
rst.value(1)
time.sleep_ms(150)

# Full init sequence (unchanged)
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
send_command(0x21)
send_command(0x11)
time.sleep_ms(120)
send_command(0x29)
time.sleep_ms(20)

send_command(0x36, b'\x04')  # Fix text direction

# === Window ===
def set_window(x0, y0, x1, y1):
    send_command(0x2A, bytes([0, x0, 0, x1]))
    send_command(0x2B, bytes([0, y0, 0, y1]))
    send_command(0x2C)

# === Stream & scale display ===
SRC_SIZE = 64
SCALE = 3
EXPECTED_BYTES = SRC_SIZE * SRC_SIZE * 2  # 8192
CHUNK_SIZE = 512  # Small chunks for low RAM

def stream_and_display_photo():
    offset_x = (240 - SRC_SIZE * SCALE) // 2
    offset_y = (240 - SRC_SIZE * SCALE) // 2
    
    # Clear screen
    set_window(0, 0, 239, 239)
    for _ in range(240 * 240):
        send_byte(0x00, 1)
        send_byte(0x00, 1)
    
    # Set window for scaled image
    set_window(offset_x, offset_y, offset_x + SRC_SIZE * SCALE - 1, offset_y + SRC_SIZE * SCALE - 1)
    
    bytes_received = 0
    try:
        r = urequests.get(PHOTO_URL, timeout=30)
        print("Status:", r.status_code)
        if r.status_code != 200:
            r.close()
            return False
        
        while True:
            chunk = r.read(CHUNK_SIZE)
            if not chunk:
                break
            chunk_len = len(chunk)
            if chunk_len % 2 != 0:
                print("Odd chunk!")
                r.close()
                return False
            for i in range(0, chunk_len, 2):
                high = chunk[i]
                low = chunk[i + 1]
                # Scale: draw SCALE x SCALE block
                for _ in range(SCALE * SCALE):
                    send_byte(high, 1)
                    send_byte(low, 1)
                bytes_received += 2
        r.close()
        print("Received bytes:", bytes_received)
        return bytes_received == EXPECTED_BYTES
    except Exception as e:
        print("Stream error:", e)
        return False
# === Font and text (from your working code) ===
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
    'A': [0x3E,0x48,0x48,0x48,0x3E],
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


# === Startup ===
set_window(0, 0, 239, 239)
for _ in range(240 * 240):
    send_byte(0x00, 1)
    send_byte(0x00, 1)

draw_text(60, 110, "Loading...")

# === Server ===
try:
    server_ip = open('/server_ip.txt').read().strip()
except OSError:
    server_ip = '192.168.1.198'

PHOTO_URL = f'http://{server_ip}:9025/image.raw'

# === Main loop ===
while True:
    gc.collect()
    if stream_and_display_photo():
        draw_text(40, 200, "Hello Preston")
        draw_text(50, 220, "& Willoh!")
        time.sleep(8)
        stream_and_display_photo()  # Redraw without text
    else:
        set_window(0, 0, 239, 239)
        for _ in range(240 * 240):
            send_byte(0x00, 1)
            send_byte(0x00, 1)
        draw_text(40, 100, "No Photo")
        draw_text(20, 130, "Check Server")
    
    time.sleep(52)
