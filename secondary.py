# secondary.py - Bit-banged ST7735 + XRP data + tracking ping to port 9020
import time
import urequests
import machine
import network
import gc

# === Print free memory at start ===
print("Free memory at secondary start:", gc.mem_free())

# === Pins ===
sck = machine.Pin(8, machine.Pin.OUT)
mosi = machine.Pin(20, machine.Pin.OUT)
dc = machine.Pin(9, machine.Pin.OUT)
rst = machine.Pin(19, machine.Pin.OUT)

# === Bit-bang functions (same as before) ===
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

# === Reset and Init (unchanged - your working sequence) ===
rst.value(1)
time.sleep_ms(50)
rst.value(0)
time.sleep_ms(50)
rst.value(1)
time.sleep_ms(150)

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
send_command(0x21)
send_command(0x36, bytes([0x60]))
send_command(0xE0, bytes([0x02,0x1C,0x07,0x12,0x37,0x32,0x29,0x2D,0x29,0x25,0x2B,0x39,0x00,0x01,0x03,0x10]))
send_command(0xE1, bytes([0x03,0x1D,0x07,0x06,0x2E,0x2C,0x29,0x2D,0x2E,0x2E,0x37,0x3F,0x00,0x00,0x02,0x10]))
send_command(0x13)
time.sleep_ms(10)
send_command(0x29)
time.sleep_ms(100)

# === Window ===
def set_window(x0, y0, x1, y1):
    send_command(0x2A, bytes([0, x0 + 2, 0, x1 + 2]))
    send_command(0x2B, bytes([0, y0 + 24, 0, y1 + 24]))
    send_command(0x2C)

# === Fill black ===
set_window(0, 0, 159, 79)
for _ in range(160 * 80):
    send_byte(0x00, 1)
    send_byte(0x00, 1)

# === Font (full uppercase from previous version) ===
font = { ... }  # Keep your full A-Z font here (same as last working version)

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

# === XRP logo (unchanged) ===
def draw_xrp_logo(center_x, center_y, radius):
    # ... (keep your full draw_xrp_logo function from before)

# === Get MAC and network info ===
mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes])

sta = network.WLAN(network.STA_IF)
start_time = time.ticks_ms()  # For uptime calculation

# === Servers (same IP, different ports) ===
try:
    server_ip = open('/server_ip.txt').read().strip()
except OSError:
    server_ip = '108.254.1.184'

data_proxy_url = f'http://{server_ip}:9021'      # XRP + time
tracking_url = f'http://{server_ip}:9020/ping'    # Tracking ping

# === Initial display ===
draw_text(10, 8, "MAC: " + mac_str)
draw_text(10, 22, "XRP: ---")
draw_text(10, 36, "VAL: ---")
draw_text(10, 50, "TIME: --:--:-- CT")
draw_xrp_logo(140, 40, 10)

# === Update loop ===
last_price = "---"
last_value = "---"
last_time = "--:--:--"

while True:
    # === 1. Ping tracking server ===
    try:
        current_ip = sta.ifconfig()[0]
        uptime_sec = time.ticks_diff(time.ticks_ms(), start_time) // 1000
        payload = {
            'mac': mac_str,
            'ip': current_ip,
            'uptime': uptime_sec
        }
        urequests.post(tracking_url, json=payload, timeout=5)
    except:
        pass  # Silent fail - tracking is non-critical

    # === 2. Fetch XRP price ===
    try:
        r = urequests.get(f'{data_proxy_url}/xrp')
        price_text = r.text.strip()
        r.close()
        if price_text != "error" and price_text != "":
            price = float(price_text)
            last_price = f"${price:.4f}"
            value = price * 1.04225
            last_value = f"${value:.2f}"
    except:
        pass

    # === 3. Fetch time ===
    try:
        r = urequests.get(f'{data_proxy_url}/time')
        time_text = r.text.strip()
        r.close()
        if time_text != "error" and len(time_text) == 8:
            last_time = time_text
    except:
        pass

    # === 4. Redraw display ===
    set_window(0, 0, 159, 79)
    for _ in range(160 * 80):
        send_byte(0x00, 1)
        send_byte(0x00, 1)

    draw_text(10, 8, "MAC: " + mac_str)
    draw_text(10, 22, "XRP: " + last_price)
    draw_text(10, 36, "VAL: " + last_value)
    draw_text(10, 50, "TIME: " + last_time + " CT")
    draw_xrp_logo(140, 40, 10)

    time.sleep(30)
