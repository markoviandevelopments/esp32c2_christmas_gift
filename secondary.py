import machine
import time
import network
import urequests
import ujson
import ubinascii
from st7735 import TFT

# ======================
# 1. DISPLAY SETUP
# ======================
sck_pin = machine.Pin(8)   # SCL
mosi_pin = machine.Pin(20) # SDA (was TX — will be released later)
dc_pin = machine.Pin(9)    # DC
rst_pin = machine.Pin(19)  # RES (was RX — will be released later)

# Safe low baudrate to avoid fuzz
spi = machine.SPI(1, baudrate=4000000, polarity=0, phase=0, sck=sck_pin, mosi=mosi_pin)

tft = TFT(spi, dc_pin, rst_pin, None)
tft.init_7735(TFT.GREENTAB80x160)

# Your working orientation and mirror settings
tft.rotation(1)
mirror_text = False

# ======================
# 2. GET MAC ADDRESS EARLY
# ======================
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
mac_bytes = sta_if.config('mac')
mac = ubinascii.hexlify(mac_bytes, ':').decode().upper()

# ======================
# 3. DISPLAY MAC ADDRESS FIRST
# ======================
tft.fill(TFT.BLACK)  # White background
w, h = tft.size()
text_width = len(mac) * 6
x = (w - text_width) // 2
y = (h - 8) // 2
tft.draw_small_text((x, y), mac, TFT.WHITE, mirror=mirror_text)
time.sleep(8)  # Show MAC for 8 seconds

# ======================
# 4. RUN PEPE DISPLAY WITH CIRCLES (30 seconds total)
# ======================
seed = 12345
def rand():
    global seed
    seed = (1103515245 * seed + 12345) & 0x7fffffff
    return seed

def random_color():
    r = (rand() % 31) << 11
    g = (rand() % 63) << 5
    b = (rand() % 31)
    return r | g | b

def rand_range(min_val, max_val):
    return min_val + (rand() % (max_val - min_val + 1))

def gaussian_random():
    u1 = rand() / 0x7fffffff
    u2 = rand() / 0x7fffffff
    z = (-2.0 * u1 ** 0.5) * (u2 * 6.283185307179586)
    value = 2.0 + z * 0.1
    if value < 1.5: value = 1.5
    if value > 2.5: value = 2.5
    return value

start_time = time.time()
while time.time() - start_time < 30:  # Run display for 30 seconds
    tft.fill(TFT.BLACK)

    # Random background circles
    for _ in range(8):
        cx = rand_range(10, w - 10)
        cy = rand_range(10, h - 10)
        radius = rand_range(10, 25)
        color = random_color()
        tft.fillcircle((cx, cy), radius, color)

    # PEPE value on top
    dollar_amount = gaussian_random()
    text = "PEPE: ${:.2f}".format(dollar_amount)
    text_width = len(text) * 6
    x = (w - text_width) // 2
    y = (h - 8) // 2
    tft.draw_small_text((x, y), text, TFT.WHITE, mirror=mirror_text)

    time.sleep(5)

# ======================
# 5. CLEAN UP DISPLAY — RELEASE PINS
# ======================
# Deinitialize SPI and pins so GPIO19 (RX) and GPIO20 (TX) go back to UART0
spi.deinit()
dc_pin = None   # Release DC pin
rst_pin = None  # Release RST pin (important: was RX)
# mosi_pin and sck_pin are automatically released by spi.deinit()

# Small delay to let hardware settle
time.sleep(0.5)

# ======================
# 6. RESTORE UART0 (RX/TX) AND TRACKING PING CLIENT
# ======================
# Force UART0 back to default pins (this ensures REPL and prints work)
uart = machine.UART(0, baudrate=115200, tx=machine.Pin(20), rx=machine.Pin(19))

# Connect to WiFi
sta_if.active(True)
sta_if.connect("BrubakerWifi", "Pre$ton01")

print("\n=== Display phase complete. Pins released. Starting tracking client ===")
print("MAC: {}".format(mac))

# Wait for connection
while not sta_if.isconnected():
    print("Waiting for WiFi connection...")
    time.sleep(2)

local_ip = sta_if.ifconfig()[0]
print("Connected! IP: {}".format(local_ip))

PING_INTERVAL = 300  # 5 minutes

while True:
    if sta_if.isconnected():
        local_ip = sta_if.ifconfig()[0]
        uptime_sec = time.ticks_ms() // 1000
        data = {
            'mac': mac,
            'ip': local_ip,
            'uptime': uptime_sec
        }
        try:
            # Read server IP from file (create /server_ip.txt on the device with your desktop IP)
            server_ip = open('/server_ip.txt', 'r').read().strip()
            url = f"http://{server_ip}:9020/ping"
            response = urequests.post(
                url,
                data=ujson.dumps(data),
                headers={'Content-Type': 'application/json'}
            )
            print("[{}] Ping sent - IP: {}, Uptime: {}s (status: {})".format(
                uptime_sec, local_ip, uptime_sec, response.status_code))
            response.close()
        except Exception as e:
            print("[{}] Ping failed: {}".format(uptime_sec, e))
    else:
        print("WiFi disconnected - retrying...")
    
    time.sleep(PING_INTERVAL)
