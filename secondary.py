import time
import urequests
import machine
import network
import gc
import ujson
# === Print free memory before anything else ===
print("Free memory at secondary start:", gc.mem_free())
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
send_command(0x20) # INVOFF
send_command(0x36, bytes([0x68])) # MADCTL for rotation + BGR
send_command(0xE0, bytes([0x02,0x1C,0x07,0x12,0x37,0x32,0x29,0x2D,0x29,0x25,0x2B,0x39,0x00,0x01,0x03,0x10]))
send_command(0xE1, bytes([0x03,0x1D,0x07,0x06,0x2E,0x2C,0x29,0x2D,0x2E,0x2E,0x37,0x3F,0x00,0x00,0x02,0x10]))
send_command(0x13)
time.sleep_ms(10)
send_command(0x29)
time.sleep_ms(100)
# === Window ===
def set_window(x0, y0, x1, y1):
    send_command(0x2A, bytes([0, x0, 0, x1]))
    send_command(0x2B, bytes([0, y0 + 26, 0, y1 + 26]))
    send_command(0x2C)
# === Fill black ===
set_window(0, 0, 159, 79)
for _ in range(160 * 80):
    send_byte(0x00, 1)
    send_byte(0x00, 1)
# === Full uppercase font (A-Z complete + digits + symbols) ===
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
    "'": [0x20,0x60,0x40,0x00,0x00],
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
# === Draw text ===
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
# === Coin logo cache ===
cached_logo_pixels = None
# === Draw coin logo from cached RGB565 array (20x20) ===
def draw_coin_logo(x, y):
    global cached_logo_pixels
    if cached_logo_pixels is None:
        try:
            r = urequests.get(f'{data_proxy_url}/logo/{coin_endpoint}')
            if r.status_code == 200:
                text = r.text.strip()
                if text != "error":
                    cached_logo_pixels = [int(p, 16) for p in text.split(',')]
            r.close()
        except:
            cached_logo_pixels = [] # Failed
    if cached_logo_pixels and len(cached_logo_pixels) == 1024:
        idx = 0
        for py in range(32):
            for px in range(32):
                color = cached_logo_pixels[idx]
                idx += 1
                set_window(x + px, y + py, x + px, y + py)
                send_byte(color >> 8, 1) # High byte
                send_byte(color & 0xFF, 1) # Low byte
    else:
        # Fallback placeholder circle if no logo
        draw_xrp_logo(x + 10, y + 10, 10)
# === XRP logo function (unchanged from your version) ===
def draw_xrp_logo(center_x, center_y, radius):
    # Fill white circle
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx*dx + dy*dy <= radius*radius:
                px = center_x + dx
                py = center_y + dy
                if 0 <= px < 160 and 0 <= py < 80:
                    set_window(px, py, px, py)
                    send_byte(0xFF, 1)
                    send_byte(0xFF, 1)
    # Black X lines
    points1 = [(center_x - radius//2, center_y - radius), (center_x, center_y - radius//3), (center_x + radius//2, center_y + radius)]
    points2 = [(center_x + radius//2, center_y - radius), (center_x, center_y - radius//3), (center_x - radius//2, center_y + radius)]
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
                    send_byte(0x00, 1)
                    send_byte(0x00, 1)
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
# === Get MAC and WiFi interface ===
mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes]).upper()
# === Check which device ===
device_config = {
    '34:98:7A:07:13:B4': {'coin': 'XRP', 'amount': 2.76412, 'endpoint': 'xrp'},
    '34:98:7A:07:14:D0': {'coin': 'SOL', 'amount': 0.042486, 'endpoint': 'sol'},
    '34:98:7A:06:FC:A0': {'coin': 'DOGE', 'amount': 40.7874, 'endpoint': 'doge'},
    '34:98:7A:06:FB:D0': {'coin': 'PEPE', 'amount': 1291895, 'endpoint': 'pepe'},
    '34:98:7A:07:11:24': {'coin': 'LTC', 'amount': 0.067632, 'endpoint': 'ltc'},
}
config = device_config.get(mac_str, {'coin': 'BTC', 'amount': 0.0000566, 'endpoint': 'btc'})
coin = config['coin']
amount = config['amount']
coin_endpoint = config['endpoint']
sta = network.WLAN(network.STA_IF)
start_time = time.ticks_ms()
# === Proxy ===
try:
    server_ip = open('/server_ip.txt').read().strip()
except OSError:
    server_ip = '108.254.1.184'
data_proxy_url = f'http://{server_ip}:9021'
tracking_url = f'http://{server_ip}:9020/ping'
# === Initial fetch ===
last_price = "---"
last_value = "---"
last_time = "--:--:--"

name_for_mac = {
    '34:98:7A:07:13:B4': "Sydney's",
    '34:98:7A:07:14:D0': "Alyssa's",
    '34:98:7A:06:FC:A0': "Patrick's",
    '34:98:7A:06:FB:D0': "Braden's",
    '34:98:7A:07:11:24': "Pattie's",
}
display_name = name_for_mac.get(mac_str, "Preston's")

def fetch_info():
    global last_price, last_value, last_time
    try:
        r = urequests.get(f'{data_proxy_url}/{coin_endpoint}', timeout=10)
        price_text = r.text.strip()
        r.close()
        if price_text != "error":
            price = float(price_text)
            last_price = f"${price}"
            value = price * amount
            last_value = f"${value:.8f}" if coin == 'BTC' else f"${value:.2f}" if coin in ['SOL', 'LTC'] else f"${value:.6f}" if coin == 'DOGE' else f"${value}"
    except:
        pass
    try:
        r = urequests.get(f'{data_proxy_url}/time', timeout=10)
        time_text = r.text.strip()
        r.close()
        if time_text != "error" and len(time_text) == 8:
            last_time = time_text
    except:
        pass


# === Main loop ===
it_C = 0
while True:
    current_time = time.ticks_ms()
    # Reboot every 30 minutes
    if it_C % 30 == 10:
        print("Rebooting for updates...")
        time.sleep(1)
        machine.reset()
        it_C = 0
    
    fetch_info()

    # Redraw
    set_window(0, 0, 159, 79)
    for _ in range(160 * 80):
        send_byte(0x00, 1)
        send_byte(0x00, 1)
    draw_text(10, 8, display_name + " " + coin)
    draw_text(10, 22, f"{coin}: " + last_price)
    draw_text(10, 36, "VAL: " + last_value)
    draw_text(10, 50, "TIME: " + last_time + " CT")
    draw_coin_logo(120, 30)
    # Accurate 60-second delay with idle (WiFi-friendly)
    current_time = time.ticks_ms()
    it_C += 1
    while time.ticks_diff(time.ticks_ms(), current_time) < 60000:
        machine.idle()  # Yields to WiFi/tasks - prevents network blockage
