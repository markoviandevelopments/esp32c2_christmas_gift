import time
import urequests
import machine
import network
import gc
import ujson
import usocket
import random
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
    send_command(0x2B, bytes([0, y0 + 24, 0, y1 + 24]))
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
# Simple 10x14 bold digits
digit_patterns = {
    '0': [14, 14, 17, 17, 25, 25, 21, 21, 19, 19, 17, 17, 14, 14, 0, 0],
    '1': [4, 4, 12, 12, 4, 4, 4, 4, 4, 4, 4, 4, 14, 14, 0, 0],
    '2': [14, 14, 17, 17, 1, 1, 2, 2, 4, 4, 8, 8, 31, 31, 0, 0],
    '3': [31, 31, 2, 2, 4, 4, 2, 2, 1, 1, 17, 17, 14, 14, 0, 0],
    '4': [2, 2, 6, 6, 10, 10, 18, 18, 31, 31, 2, 2, 2, 2, 0, 0],
    '5': [31, 31, 16, 16, 30, 30, 1, 1, 1, 1, 17, 17, 14, 14, 0, 0],
    '6': [6, 6, 8, 8, 16, 16, 30, 30, 17, 17, 17, 17, 14, 14, 0, 0],
    '7': [31, 31, 1, 1, 2, 2, 4, 4, 8, 8, 8, 8, 8, 8, 0, 0],
    '8': [14, 14, 17, 17, 17, 17, 14, 14, 17, 17, 17, 17, 14, 14, 0, 0],
    '9': [14, 14, 17, 17, 17, 17, 15, 15, 1, 1, 2, 2, 12, 12, 0, 0],
}


abbr_dict = {
    '34:98:7A:07:13:B4': "SYD",
    '34:98:7A:07:14:D0': "ALY",
    '34:98:7A:06:FC:A0': "PAT",
    '34:98:7A:06:FB:D0': "BRN",
    '34:98:7A:07:11:24': "MOM",
    '34:98:7A:07:12:B8': "TES",
    '34:98:7A:07:06:B4': "DAD",
}

last_current_rank = 99
rank_dict = {}
last_rank_dict = {}     # Persistent full dict from last success

# === Draw text ===
def draw_text(x_start, y_start, text):
    x = x_start
    for char in text.upper():
        if char not in font:
            x += 12
            continue
        bitmap = font[char]
        for row in range(8):
            y0 = y_start + row * 2
            y1 = y0 + 1
            # Build list of x positions that need pixels this row
            active_cols = []
            for col in range(5):
                if bitmap[col] & (1 << (7 - row)):
                    active_cols.append(col)
            if not active_cols:
                continue
            # Find contiguous runs to minimize window sets
            start_col = active_cols[0]
            prev_col = active_cols[0]
            for col in active_cols[1:]:
                if col != prev_col + 1:
                    # End current run
                    draw_scaled_hline(x + start_col*2, y0, x + prev_col*2 + 1, y1)
                    start_col = col
                prev_col = col
            # Last run
            draw_scaled_hline(x + start_col*2, y0, x + prev_col*2 + 1, y1)
        x += 12

# === Draw colored pixel (for rank number) ===
def draw_pixel(x, y, color565):
    if 0 <= x < 160 and 0 <= y < 80:
        set_window(x, y, x, y)
        send_byte(color565 >> 8, 1)
        send_byte(color565 & 0xFF, 1)

def draw_filled_circle(xc, yc, r, color):
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                px = xc + dx
                py = yc + dy
                if 0 <= px < 160 and 0 <= py < 80:
                    draw_pixel(px, py, color)

def draw_circle_outline(xc, yc, r, color, thickness=1):
    outer = (r + thickness) * (r + thickness)
    inner = r * r
    for dy in range(-r - thickness - 1, r + thickness + 2):
        for dx in range(-r - thickness - 1, r + thickness + 2):
            dist = dx * dx + dy * dy
            if inner < dist <= outer:
                px = xc + dx
                py = yc + dy
                if 0 <= px < 160 and 0 <= py < 80:
                    draw_pixel(px, py, color)

def draw_rank(rank_str, rank_num):
    # Bright medal colors (RGB565)
    colors = {
        1: 0xFFE0,  # Gold
        2: 0xC618,  # Silver
        3: 0xCD72,  # Bronze
    }
    # Dark fill versions
    dark_colors = {
        1: 0x83E0,  # Darker gold
        2: 0x630C,  # Darker silver/gray
        3: 0x0000,  # Darker bronze
    }
    bright = colors.get(rank_num, 0xFFFF)      # White for 4+
    dark = dark_colors.get(rank_num, 0x3186)   # Dark gray for 4+

    # Medal position and size (fits nicely beside/below logo)
    cx = 147   # Center X - adjust ±10 if needed for your logo placement
    cy = 64    # Center Y - lower to avoid logo overlap
    r = 10     # Larger radius for visible medal

    # Draw medal: dark fill first
    draw_filled_circle(cx, cy, r, dark)
    # Then thick bright rim on top
    draw_circle_outline(cx, cy, r, bright, thickness=1)

    # Draw the upscaled number centered on the medal (bright color)
    digit_width = 10  # 5 columns * 2 pixels
    total_width = len(rank_str) * digit_width + (len(rank_str) - 1) * 3  # spacing
    x_base = cx - total_width // 2
    y_base = cy - 8   # Center vertically (16 rows tall)

    for i, ch in enumerate(rank_str):
        pattern = digit_patterns.get(ch, digit_patterns['0'])
        x = x_base + i * (digit_width + 3)  # small gap between multi-digit
        for row in range(16):
            bits = pattern[row]
            for col in range(5):
                if bits & (1 << (4 - col)):  # Leftmost bit = col 0
                    draw_pixel(x + col * 2, y_base + row, bright)
                    draw_pixel(x + col * 2 + 1, y_base + row, bright)

def draw_scaled_hline(x0, y0, x1, y1):
    if x0 > x1:
        return
    set_window(x0, y0, x1, y0)
    for _ in range(x1 - x0 + 1):
        send_byte(0xFF, 1)
        send_byte(0xFF, 1)
    set_window(x0, y1, x1, y1)
    for _ in range(x1 - x0 + 1):
        send_byte(0xFF, 1)
        send_byte(0xFF, 1)
        
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
    if cached_logo_pixels and len(cached_logo_pixels) == 400:
        idx = 0
        for py in range(20):
            for px in range(20):
                color = cached_logo_pixels[idx]
                idx += 1
                set_window(x + px, y + py, x + px, y + py)
                send_byte(color >> 8, 1) # High byte
                send_byte(color & 0xFF, 1) # Low byte
    else:
        # Fallback placeholder circle if no logo
        draw_xrp_logo(x + 10, y + 10, 10)

def draw_big_coin_logo():
    # Always start with fresh black screen for big logo mode
    set_window(0, 0, 159, 79)
    # for _ in range(160 * 80):
    #     send_byte(0x00, 1)
    #     send_byte(0x00, 1)
    for _ in range(160 * 80):
        # Very dark random color (adjust the upper limits for darker/brighter noise)
        red   = random.randint(0, 3)   # 0-3   (max 31 for red)
        green = random.randint(0, 6)   # 0-6   (max 63 for green – slightly higher range OK since eye is more sensitive)
        blue  = random.randint(0, 3)   # 0-3   (max 31 for blue)
        
        color = (red << 11) | (green << 5) | blue
        
        send_byte(color >> 8, 1)
        send_byte(color & 0xFF, 1)
    
    
    total_chunks = 0
    try:
        r = urequests.get(f'{data_proxy_url}/biglogo_chunks/{coin_endpoint}', timeout=25)
        text = r.text.strip()
        r.close()
        if text.isdigit():
            total_chunks = int(text)
    except:
        pass
    
    if total_chunks == 0:
        draw_coin_logo(70, 30)  # Fallback immediately if no big logo available
        return
    
    pixel_idx = 0
    chunks_drawn = 0
    for chunk_id in range(total_chunks):
        try:
            r = urequests.get(f'{data_proxy_url}/biglogo/{coin_endpoint}/{chunk_id}', timeout=30)
            data = r.content  # binary bytes
            r.close()
            
            if len(data) == 0 or len(data) % 2 != 0:
                break
            
            chunks_drawn += 1
            for i in range(0, len(data), 2):
                if pixel_idx >= 12800:
                    break
                high = data[i]
                low = data[i + 1]
                px = pixel_idx % 160
                py = pixel_idx // 160
                set_window(px, py, px, py)
                send_byte(high, 1)
                send_byte(low, 1)
                pixel_idx += 1
            
            time.sleep_ms(50)  # Small pause between chunks for stability
        except:
            break
    
    # Only fallback if literally nothing was drawn
    if chunks_drawn == 0:
        draw_coin_logo(70, 30)
    # Otherwise keep partial or full big logo (looks good even if incomplete)

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
    '34:98:7A:07:12:B8': {'coin': 'PEPE', 'amount': 1291895, 'endpoint': 'pepe'}, # Testing Chip
    '34:98:7A:07:06:B4': {'coin': 'BTC', 'amount': 0.0000566, 'endpoint': 'btc'},
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
current_rank = 99  # large default

name_for_mac = {
    '34:98:7A:07:13:B4': "Sydney's",
    '34:98:7A:07:14:D0': "Alyssa's",
    '34:98:7A:06:FC:A0': "Patrick's",
    '34:98:7A:06:FB:D0': "Braden's",
    '34:98:7A:07:11:24': "Pattie's",
    '34:98:7A:07:12:B8': "Test's",
    '34:98:7A:07:06:B4': "Chris's",
}
display_name = name_for_mac.get(mac_str, "Chris's")

# === Data fetch ===
def fetch_data():
    global last_price, last_value, last_time, current_rank, last_current_rank, rank_dict, last_rank_dict
    try:
        r = urequests.get(f'{data_proxy_url}/{coin_endpoint}', timeout=10)
        price_text = r.text.strip()
        r.close()
        if price_text != "error":
            price = float(price_text)
            if coin == 'BTC':
                last_price = f"${round(price)}"
            else:
                last_price = f"${price}"
            last_value = price * amount  # Keep as float
    except:
        pass

    try:
        r = urequests.get(f'{data_proxy_url}/time', timeout=10)
        t = r.text.strip()
        r.close()
        if t != "error" and len(t) == 8:
            hh = (int(t[:2]) + 1) % 24
            last_time = f"{hh:02d}:{t[3:5]}"
    except:
        pass

    try:
        r = urequests.get(f'{data_proxy_url}/rank', timeout=10)
        rank_json = ujson.loads(r.text)
        r.close()
        last_rank_dict = rank_json  # Save full good dict
        rank_dict = rank_json       # Use for this cycle
        new_rank = rank_json.get(mac_str, 99)
        current_rank = new_rank
        last_current_rank = new_rank
    except:
        current_rank = last_current_rank
        rank_dict = last_rank_dict  # Fall back to last good full dict


# Ping server with MAC once
try:
    sock = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
    sock.connect((server_ip, 9022))
    sock.send(mac_str.encode())
    sock.close()
except Exception as e:
    pass

# === Main loop ===
it_C = 0
while True:
    current_time = time.ticks_ms()
    # Reboot every 30 minutes
    if it_C > 0 and it_C % 30 == 0:
        print("Rebooting for updates...")
        time.sleep(1)
        machine.reset()
        it_C = 0
    
    fetch_data()

    # Redraw
    set_window(0, 0, 159, 79)
    # for _ in range(160 * 80):
    #     send_byte(0x00, 1)
    #     send_byte(0x00, 1)
    for _ in range(160 * 80):
        # Very dark random color (adjust the upper limits for darker/brighter noise)
        red   = random.randint(0, 3)   # 0-3   (max 31 for red)
        green = random.randint(0, 6)   # 0-6   (max 63 for green – slightly higher range OK since eye is more sensitive)
        blue  = random.randint(0, 3)   # 0-3   (max 31 for blue)
        
        color = (red << 11) | (green << 5) | blue
        
        send_byte(color >> 8, 1)
        send_byte(color & 0xFF, 1)
    draw_text(8, 4, display_name + " " + coin)
    draw_text(8, 22, f"{coin}:" + last_price)
    draw_text(8, 42, f"VAL:${last_value:.2f}")
    
    string = "ERROR XD"  # Fallback
    r = random.randint(1, 2)
    # Identify if this device is Chris or Pattie for privacy rules
    is_chris = mac_str == '34:98:7A:07:06:B4'
    is_pattie = mac_str == '34:98:7A:07:11:24'

    if r == 1:  # Random other device's rank + abbr
        if rank_dict and len(rank_dict) > 1:
            candidates = [m for m in rank_dict if m != mac_str]
            
            if is_chris:
                candidates = [m for m in candidates if m != '34:98:7A:07:11:24']
            if is_pattie:
                candidates = [m for m in candidates if m != '34:98:7A:07:06:B4']
            
            if candidates:
                # Fixed syntax + safe indexing
                idx = random.randint(0, len(candidates) - 1)
                rand_mac = candidates[idx]
                abbr = abbr_dict.get(rand_mac, "??")
                o_rank = rank_dict.get(rand_mac, 99)
                if o_rank < 99:
                    string = f"{abbr} AT {o_rank}"
    elif r == 2:
        if random.randint(0, 3):
            string = f"LUK N:{random.randint(0, 99)}"
        else:
            string = f"LUK N:{67}"
        
    draw_text(8, 62, string)
    
    draw_coin_logo(110, 55)
    
    if current_rank < 99:
        draw_rank(str(current_rank), current_rank)

    if random.randint(1,3) > 0:
        while time.ticks_diff(time.ticks_ms(), current_time) < 60000:
            machine.idle()  # Yields to WiFi/tasks - prevents network blockage
        draw_big_coin_logo()  # Full-screen every update (covers text/rank—good for splash)
        draw_text(30, 4, f"VAL:${last_value:.2f}")
    
    # Accurate 60-second delay with idle (WiFi-friendly)
    current_time = time.ticks_ms()
    it_C += 1
    while time.ticks_diff(time.ticks_ms(), current_time) < 60000:
        machine.idle()  # Yields to WiFi/tasks - prevents network blockage
