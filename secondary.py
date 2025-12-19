# secondary.py - Bit-banged ST7735: 90° CCW rotation, fixed offsets/shift, better font, proxy on 9021
import time
import urequests
import machine

# === Pins ===
sck = machine.Pin(8, machine.Pin.OUT)
mosi = machine.Pin(20, machine.Pin.OUT)
dc = machine.Pin(9, machine.Pin.OUT)
rst = machine.Pin(19, machine.Pin.OUT)

# === Bit-bang ===
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

# === Init (GREENTAB80x160) ===
send_command(0x01)
time.sleep_ms(150)
send_command(0x11)
time.sleep_ms(255)
send_command(0x3A, bytes([0x05]))
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
send_command(0x21)  # INVON
send_command(0x36, bytes([0x60]))  # MADCTL: 90° clockwise (effective CCW with wiring + correct offsets)
send_command(0xE0, bytes([0x02,0x1C,0x07,0x12,0x37,0x32,0x29,0x2D,0x29,0x25,0x2B,0x39,0x00,0x01,0x03,0x10]))
send_command(0xE1, bytes([0x03,0x1D,0x07,0x06,0x2E,0x2C,0x29,0x2D,0x2E,0x2E,0x37,0x3F,0x00,0x00,0x02,0x10]))
send_command(0x13)
time.sleep_ms(10)
send_command(0x29)
time.sleep_ms(100)

# === Window (fixed offsets to eliminate shift/fuzz) ===
def set_window(x0, y0, x1, y1):
    send_command(0x2A, bytes([0, x0 + 2, 0, x1 + 2]))   # CASET +2 (eliminates left fuzz)
    send_command(0x2B, bytes([0, y0 + 24, 0, y1 + 24]))  # RASET +24 (eliminates bottom fuzz/shift)
    send_command(0x2C)

# === Fill black ===
set_window(0, 0, 159, 79)
for _ in range(160 * 80):
    send_byte(0x00, 1)
    send_byte(0x00, 1)

# === Improved font (fixed I thicker, L proper, A/E clearer, added V,U for VALUE/TIME) ===
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
    'M': [0xFE,0x40,0x30,0x40,0xFE],
    'A': [0x3E,0x48,0x48,0x48,0x3E],
    'C': [0x7C,0x82,0x82,0x82,0x44],
    'E': [0xFE,0x92,0x92,0x92,0x82],
    'I': [0x00,0x82,0xFE,0x82,0x00],
    'L': [0xFE,0x02,0x02,0x02,0x02],
    'V': [0xF8,0x04,0x02,0x04,0xF8],
    'U': [0xFC,0x02,0x02,0x02,0xFC],
    'T': [0x80,0x80,0xFE,0x80,0x80],
    'X': [0xC6,0x28,0x10,0x28,0xC6],
    'R': [0xFE,0x90,0x98,0x94,0x62],
    'P': [0xFE,0x90,0x90,0x90,0x60],
}

# === Draw text (shifted down/left for visibility) ===
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

# === Draw simple XRP logo (white circle with black X lines inside) ===
def draw_xrp_logo(center_x, center_y, radius):
    # Fill white circle (simple raster fill - good enough for small radius)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx*dx + dy*dy <= radius*radius:
                px = center_x + dx
                py = center_y + dy
                if 0 <= px < 160 and 0 <= py < 80:
                    set_window(px, py, px, py)
                    send_byte(0xFF, 1)  # White high
                    send_byte(0xFF, 1)  # White low

    # Draw three black curved lines (approximated as straight segments for speed)
    # Line 1: top-left to bottom-right curve
    points1 = [(center_x - radius//2, center_y - radius), (center_x, center_y - radius//3), (center_x + radius//2, center_y + radius)]
    # Line 2: top-right to bottom-left curve
    points2 = [(center_x + radius//2, center_y - radius), (center_x, center_y - radius//3), (center_x - radius//2, center_y + radius)]
    # Line 3: middle horizontal curve (slight arc)
    points3 = [(center_x - radius, center_y), (center_x, center_y + radius//4), (center_x + radius, center_y)]

    def draw_line(points):
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i+1]
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx - dy
            while True:
                if 0 <= x0 < 160 and 0 <= y0 < 80:
                    set_window(x0, y0, x0, y0)
                    send_byte(0x00, 1)  # Black high
                    send_byte(0x00, 1)  # Black low
                if x0 == x1 and y0 == y1: break
                e2 = 2 * err
                if e2 > -dy:
                    err -= dy
                    x0 += sx
                if e2 < dx:
                    err += dx
                    y0 += sy

    draw_line(points1)
    draw_line(points2)
    draw_line(points3)

# === Get MAC ===
mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes])

# === Proxy on port 9021 ===
try:
    proxy_ip = open('/server_ip.txt').read().strip()
except OSError:
    proxy_ip = '108.254.1.184'
proxy_port = '9021'
base_url = f'http://{proxy_ip}:{proxy_port}'

# === Initial display ===
draw_text(10, 8, "MAC: " + mac_str)
draw_text(10, 22, "XRP: ---")
draw_text(10, 36, "VAL: ---")
draw_text(10, 50, "TIME: --:--:-- CT")

# === Update loop ===
last_price = "---"
last_value = "---"
last_time = "--:--:--"

while True:
    # Fetch price
    try:
        r = urequests.get(f'{base_url}/xrp')
        price_text = r.text.strip()
        r.close()
        if price_text != "error" and price_text != "":
            price = float(price_text)
            last_price = f"${price:.4f}"
            value = price * 1.04225
            last_value = f"${value:.2f}"
    except:
        pass

    # Fetch time
    try:
        r = urequests.get(f'{base_url}/time')
        time_text = r.text.strip()
        r.close()
        if time_text != "error" and len(time_text) == 8:
            last_time = time_text
    except:
        pass

    # Redraw
    set_window(0, 0, 159, 79)
    for _ in range(160 * 80):
        send_byte(0x00, 1)
        send_byte(0x00, 1)

    draw_text(10, 8, "MAC: " + mac_str)
    draw_text(10, 22, "XRP: " + last_price)
    draw_text(10, 36, "VAL: " + last_value)
    draw_text(10, 50, "TIME: " + last_time + " CT")
    draw_xrp_logo(150, 50, 10)

    time.sleep(30)
