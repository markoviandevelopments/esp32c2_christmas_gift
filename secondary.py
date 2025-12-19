# secondary.py - Bit-banged ST7735: 90 deg CCW rotation, MAC + XRP price + value + Central Time
import time
import urequests
import machine

# === Pins ===
sck = machine.Pin(8, machine.Pin.OUT)
mosi = machine.Pin(20, machine.Pin.OUT)
dc = machine.Pin(9, machine.Pin.OUT)
rst = machine.Pin(19, machine.Pin.OUT)

# === Bit-bang send ===
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

# === Reset ===
rst.value(1)
time.sleep_ms(50)
rst.value(0)
time.sleep_ms(50)
rst.value(1)
time.sleep_ms(150)

# === Init sequence (GREENTAB80x160) ===
send_command(0x01)  # SWRESET
time.sleep_ms(150)
send_command(0x11)  # SLPOUT
time.sleep_ms(255)
send_command(0x3A, bytes([0x05]))  # 16-bit color
send_command(0xB1, bytes([0x01, 0x2C, 0x2D]))
send_command(0xB2, bytes([0x01, 0x2C, 0x2D]))
send_command(0xB3, bytes([0x01, 0x2C, 0x2D, 0x01, 0x2C, 0x2D]))
send_command(0xB4, bytes([0x07]))
send_command(0xC0, bytes([0xA2, 0x02, 0x84]))
send_command(0xC1, bytes([0xC5]))
send_command(0xC2, bytes([0x0A, 0x00]))
send_command(0xC3, bytes([0x8A, 0x2A]))
send_command(0xC4, bytes([0x8A, 0xEE]))
send_command(0xC5, bytes([0x0E]))
send_command(0x21)  # INVON (needed for your display)
send_command(0x36, bytes([0xA0]))  # MADCTL: 90° counterclockwise rotation
send_command(0xE0, bytes([0x02,0x1C,0x07,0x12,0x37,0x32,0x29,0x2D,0x29,0x25,0x2B,0x39,0x00,0x01,0x03,0x10]))
send_command(0xE1, bytes([0x03,0x1D,0x07,0x06,0x2E,0x2C,0x29,0x2D,0x2E,0x2E,0x37,0x3F,0x00,0x00,0x02,0x10]))
send_command(0x13)  # NORON
time.sleep_ms(10)
send_command(0x29)  # DISPON
time.sleep_ms(100)

# === Window for rotated screen (now 160 wide x 80 tall, offsets swapped/adjusted) ===
def set_window(x0, y0, x1, y1):
    # After 90° CCW rotation, column offset ≈1, row offset ≈26 (empirical for GREENTAB80x160)
    send_command(0x2A, bytes([0, x0 + 1, 0, x1 + 1]))  # CASET
    send_command(0x2B, bytes([0, y0 + 26, 0, y1 + 26]))  # RASET
    send_command(0x2C)  # RAMWR

# === Fill black ===
set_window(0, 0, 159, 79)
for _ in range(160 * 80):
    send_byte(0x00, 1)
    send_byte(0x00, 1)

# === Simple 5x8 font (added digits, letters, symbols needed) ===
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
    'A': [0x7C,0x12,0x12,0x12,0x7C],
    'C': [0x7C,0x82,0x82,0x82,0x44],
    'E': [0xFE,0x92,0x92,0x92,0x82],
    'M': [0xFE,0x40,0x30,0x40,0xFE],
    'P': [0xFE,0x90,0x90,0x90,0x60],
    'R': [0xFE,0x90,0x98,0x94,0x62],
    'T': [0x80,0x80,0xFE,0x80,0x80],
    'V': [0xF8,0x04,0x02,0x04,0xF8],
    'X': [0xC6,0x28,0x10,0x28,0xC6],
}

# === Draw text (white pixels) ===
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
                        send_byte(0xFF, 1)  # White high
                        send_byte(0xFF, 1)  # White low
        x += 6  # Spacing

# === Get MAC ===
mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes])

# === Initial display ===
draw_text(5, 5, "MAC: " + mac_str)
draw_text(5, 20, "XRP Price: ---")
draw_text(5, 35, "Value (1.04225): ---")
draw_text(5, 50, "Time: --:--:--")

# === Main update loop (every 30 seconds) ===
while True:
    price = "---"
    value = "---"
    ctime = "--:--:--"

    try:
        # Fetch XRP price
        r = urequests.get("https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd")
        price = r.json()['ripple']['usd']
        value = round(price * 1.04225, 2)
        r.close()
    except:
        pass

    try:
        # Fetch Central Time
        r = urequests.get("http://worldtimeapi.org/api/timezone/America/Chicago")
        dt = r.json()['datetime']
        ctime = dt[11:19]  # HH:MM:SS (24h)
        r.close()
    except:
        pass

    # Clear and redraw
    set_window(0, 0, 159, 79)
    for _ in range(160 * 80):
        send_byte(0x00, 1)
        send_byte(0x00, 1)

    draw_text(5, 5, "MAC: " + mac_str)
    draw_text(5, 20, f"XRP: ${price}")
    draw_text(5, 35, f"Value: ${value}")
    draw_text(5, 50, f"Time: {ctime} CT")

    time.sleep(30)
