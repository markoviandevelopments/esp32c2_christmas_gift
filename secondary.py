# secondary.py - Minimal bit-banged ST7735 display + server ping (no st7735.py driver, only machine)
import time
import urequests
import machine

# === Pin setup (your wiring) ===
sck = machine.Pin(8, machine.Pin.OUT)   # SCL
mosi = machine.Pin(20, machine.Pin.OUT)  # SDA/MOSI
dc = machine.Pin(9, machine.Pin.OUT)    # DC
rst = machine.Pin(19, machine.Pin.OUT)  # RES

# No CS pin in your setup - we keep it "active" by not using one

# === Simple bit-bang SPI send byte (slow but low RAM) ===
def send_byte(byte, is_data):
    dc.value(is_data)  # 0 = command, 1 = data
    for _ in range(8):
        sck.value(0)
        mosi.value((byte & 0x80) >> 7)
        byte <<= 1
        sck.value(1)
    sck.value(0)  # Idle low

def send_command(cmd, data=b''):
    send_byte(cmd, 0)
    for b in data:
        send_byte(b, 1)

# === Display reset ===
rst.value(1)
time.sleep_ms(50)
rst.value(0)
time.sleep_ms(50)
rst.value(1)
time.sleep_ms(150)

# === Minimal init sequence for your GREENTAB80x160 variant (from working driver) ===
send_command(0x01)  # SWRESET
time.sleep_ms(150)
send_command(0x11)  # SLPOUT
time.sleep_ms(255)
send_command(0x3A, bytes([0x05]))  # COLMOD: 16-bit color
send_command(0xB1, bytes([0x01, 0x2C, 0x2D]))  # FRMCTR1
send_command(0xB2, bytes([0x01, 0x2C, 0x2D]))
send_command(0xB3, bytes([0x01, 0x2C, 0x2D, 0x01, 0x2C, 0x2D]))
send_command(0xB4, bytes([0x07]))  # INVCTR
send_command(0xC0, bytes([0xA2, 0x02, 0x84]))  # PWCTR1
send_command(0xC1, bytes([0xC5]))
send_command(0xC2, bytes([0x0A, 0x00]))
send_command(0xC3, bytes([0x8A, 0x2A]))
send_command(0xC4, bytes([0x8A, 0xEE]))
send_command(0xC5, bytes([0x0E]))  # VMCTR1
send_command(0x36, bytes([0xC8]))  # MADCTL (rotation 1 equivalent)
send_command(0x21)  # INVON (required for your variant)
send_command(0xE0, bytes([0x02, 0x1C, 0x07, 0x12, 0x37, 0x32, 0x29, 0x2D, 0x29, 0x25, 0x2B, 0x39, 0x00, 0x01, 0x03, 0x10]))  # GMCTRP1
send_command(0xE1, bytes([0x03, 0x1D, 0x07, 0x06, 0x2E, 0x2C, 0x29, 0x2D, 0x2E, 0x2E, 0x37, 0x3F, 0x00, 0x00, 0x02, 0x10]))  # GMCTRN1
send_command(0x13)  # NORON
time.sleep_ms(10)
send_command(0x29)  # DISPON
time.sleep_ms(100)

# === Set window for full screen (80x160 with offsets for GREENTAB80x160) ===
def set_window(x0, y0, x1, y1):
    send_command(0x2A, bytes([0, x0 + 26, 0, x1 + 26]))  # CASET (col offset 26)
    send_command(0x2B, bytes([0, y0 + 1, 0, y1 + 1]))   # RASET (row offset 1)
    send_command(0x2C)  # RAMWR

# === Fill screen black ===
set_window(0, 0, 79, 159)
for _ in range(80 * 160):
    send_byte(0x00, 1)  # High byte black
    send_byte(0x00, 1)  # Low byte black

# === Minimal 5x8 font (only letters/numbers needed for "PING OK/FAIL") ===
font = {
    ' ': [0x00,0x00,0x00,0x00,0x00],
    'P': [0xF8,0x24,0x24,0x24,0x18],
    'I': [0x00,0x44,0xFE,0x44,0x00],
    'N': [0xFE,0x10,0x08,0x04,0xFE],
    'G': [0x7C,0x82,0x92,0x92,0x5C],
    'O': [0x7C,0x82,0x82,0x82,0x7C],
    'K': [0xFE,0x10,0x28,0x44,0x82],
    'F': [0xFE,0x90,0x90,0x90,0x80],
    'A': [0x7C,0x12,0x12,0x12,0x7C],
    'L': [0xFE,0x02,0x02,0x02,0x02],
    ':': [0x00,0x36,0x36,0x00,0x00],
}

# === Simple text draw (white, at position) ===
def draw_text(x, y, text):
    for char in text:
        if char in font:
            bitmap = font[char]
            for col in range(5):
                bits = bitmap[col]
                for row in range(8):
                    if bits & (1 << (7 - row)):
                        # Set pixel (white 0xFFFF)
                        set_window(x + col, y + row, x + col, y + row)
                        send_byte(0xFF, 1)
                        send_byte(0xFF, 1)
        x += 6  # Spacing

# Initial message
draw_text(5, 30, "PING LOOP")
draw_text(5, 60, "Starting...")

# === Load server IP/port ===
try:
    server_ip = open('/server_ip.txt').read().strip()
except OSError:
    server_ip = '108.254.1.184'

try:
    server_port = open('/server_port.txt').read().strip()
except OSError:
    server_port = '9019'

ping_url = f'http://{server_ip}:{server_port}/'

# === Ping loop ===
while True:
    try:
        r = urequests.get(ping_url, timeout=10)
        if r.status_code == 200:
            draw_text(5, 90, "PING OK ")
        else:
            draw_text(5, 90, "PING FAIL")
        r.close()
    except:
        draw_text(5, 90, "PING ERROR")

    time.sleep(10)
