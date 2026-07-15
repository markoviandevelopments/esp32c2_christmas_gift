import time
import urequests
import machine
import network
import gc
import os
import usocket

# ===================== FIXED MAC CAPTURE (javamoss:9022 raw TCP) =====================
# === Get MAC and WiFi interface ===
mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes]).upper()
print(f"Reporting MAC {mac_str} to javamoss.immenseaccumulationonline.online/mac ...")
try:
    r = urequests.post(
        'http://javamoss.immenseaccumulationonline.online/mac',
        data=mac_str,          # plain text MAC in body
        timeout=10
    )
    if r.status_code == 200 or r.status_code == 204:
        print("✅ MAC successfully sent to javamoss server")
    else:
        print(f"MAC sent but server returned {r.status_code}")
    r.close()
except Exception as e:
    print("MAC report failed (will retry next boot):", str(e))


machine.freq(120000000)

# === Pins & SPI ===
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

# === Reset & full GC9A01 init ===
rst.value(1)
time.sleep_ms(50)
rst.value(0)
time.sleep_ms(50)
rst.value(1)
time.sleep_ms(150)
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
send_command(0x36, b'\x48')

# === Window ===
def set_window(x0, y0, x1, y1):
    send_command(0x2A, bytes([0, x0, 0, x1]))
    send_command(0x2B, bytes([0, y0, 0, y1]))
    send_command(0x2C)

# ===================== ONE-TIME MIGRATION =====================
try:
    saved_ip = open('/server_ip.txt').read().strip()
except OSError:
    saved_ip = '108.254.1.184'

if saved_ip == '108.254.1.184':
    print("Old public IP detected - migrating to domain...")

    # Download special boot2.mpy from old server
    try:
        r = urequests.get("http://108.254.1.184:9019/boot2.mpy", timeout=20)
        if r.status_code == 200 and len(r.content) > 1000:
            with open('/boot2.mpy', 'wb') as f:
                f.write(r.content)
            print("Downloaded boot2.mpy using old IP")

            # Rename to boot.py so it becomes the active boot script
            os.rename('/boot2.mpy', '/boot.py')
            print("Renamed boot2.mpy → boot.py")
        r.close()
    except Exception as e:
        print("Boot download failed:", e)

    # Update config to new domain + port 80
    with open('/server_ip.txt', 'w') as f:
        f.write("ghostshrimp.immenseaccumulationonline.online")
    with open('/server_port.txt', 'w') as f:
        f.write("80")
    with open('/ip_updated.txt', 'w') as f:
        f.write("done")

    print("Migration complete - rebooting")
    time.sleep(3)
    machine.reset()
# ============================================================

# === MAC ===
mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes]).upper()

# === ONE-TIME MIGRATION: old public IP → DNS (port 80) ===
try:
    saved_ip = open('/server_ip.txt').read().strip()
except OSError:
    saved_ip = '108.254.1.184'

if saved_ip == '108.254.1.184':
    print("Old public IP detected - migrating to DNS (using old IP for download)...")
    # Download latest version of this script using old IP
    try:
        r = urequests.get("http://108.254.1.184:9019/pixel.mpy", timeout=20)  # or whatever your filename is
        if r.status_code == 200 and len(r.content) > 1000:
            with open('/pixel.mpy', 'wb') as f:   # adjust filename if needed
                f.write(r.content)
            print("Downloaded latest display code using old IP")
        r.close()
    except:
        pass

    # Update config to DNS + default port 80
    with open('/server_ip.txt', 'w') as f:
        f.write("ghostshrimp.immenseaccumulationonline.online")
    with open('/server_port.txt', 'w') as f:
        f.write("80")
    with open('/ip_updated.txt', 'w') as f:
        f.write("done")

    print("Migration complete - rebooting")
    time.sleep(3)
    machine.reset()

# === Photo server (chunked RGB565) ===
PHOTO_HOST = 'neontetra.immenseaccumulationonline.online'
PHOTO_PORT = 80

# === Hang prevention ===
# urequests timeouts are unreliable on ESP32 and often freeze mid-download.
# Use raw sockets + short settimeout, hardware WDT, and a 5-minute reboot.
BOOT_MS = time.ticks_ms()
REBOOT_MS = 5 * 60 * 1000          # forced reboot every 5 minutes
SOCK_TIMEOUT = 2.5                 # seconds per socket op
CHUNK_RETRIES = 2
MAX_FAIL_STREAK = 3
MIN_FREE_MEM = 8000
_wdt = None
_resolved = None                   # cached (ip, port) tuple

def start_wdt():
    """Start hardware watchdog ASAP; shorter = faster hang recovery."""
    global _wdt
    if _wdt is not None:
        return
    for ms in (3000, 5000, 8000):
        try:
            _wdt = machine.WDT(timeout=ms)
            print('WDT started, timeout_ms=', ms)
            return
        except Exception as e:
            print('WDT', ms, 'failed:', e)
    print('WARNING: no WDT available')

def feed_wdt():
    if _wdt:
        try:
            _wdt.feed()
        except Exception:
            pass

def hard_reset(reason=''):
    print('RESET:', reason)
    time.sleep_ms(100)
    machine.reset()

def maybe_periodic_reboot():
    if time.ticks_diff(time.ticks_ms(), BOOT_MS) >= REBOOT_MS:
        hard_reset('5-minute uptime')

def ensure_wifi():
    feed_wdt()
    sta = network.WLAN(network.STA_IF)
    if sta.isconnected():
        return True
    print('WiFi down - reconnecting')
    try:
        ssid = open('/ssid.txt').read().strip()
        pw = open('/pass.txt').read().strip()
    except OSError:
        hard_reset('no wifi creds')
    try:
        if not sta.active():
            sta.active(True)
        sta.disconnect()
    except Exception:
        pass
    try:
        sta.connect(ssid, pw)
    except Exception as e:
        print('wifi connect err', e)
        hard_reset('wifi connect err')
    for _ in range(20):
        feed_wdt()
        maybe_periodic_reboot()
        if sta.isconnected():
            print('WiFi ok', sta.ifconfig()[0])
            return True
        time.sleep_ms(300)
    hard_reset('wifi reconnect failed')

def resolve_host():
    """DNS resolve with WDT protection; cache result."""
    global _resolved
    feed_wdt()
    if _resolved is not None:
        return _resolved
    # getaddrinfo can hang; WDT is the backstop
    ai = usocket.getaddrinfo(PHOTO_HOST, PHOTO_PORT, 0, usocket.SOCK_STREAM)
    _resolved = ai[0][-1]
    feed_wdt()
    return _resolved

def invalidate_host():
    global _resolved
    _resolved = None

def http_get_chunk(n):
    """
    Fetch one 512-byte RGB565 chunk via raw socket (not urequests).
    Returns a bytes-like object of length 512, or None on failure.
    settimeout makes network stalls raise instead of freezing forever.
    """
    feed_wdt()
    s = None
    try:
        addr = resolve_host()
        s = usocket.socket()
        s.settimeout(SOCK_TIMEOUT)
        s.connect(addr)
        feed_wdt()
        path = '/pixel?n=%d&mac=%s' % (n, mac_str)
        # HTTP/1.0 + Connection: close → raw body, no chunked encoding
        req = b'GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n' % (
            path.encode(), PHOTO_HOST.encode())
        s.send(req)
        feed_wdt()

        # Read headers with a size cap (avoids unbounded += on C2 heap)
        buf = b''
        while b'\r\n\r\n' not in buf:
            feed_wdt()
            part = s.recv(128)
            if not part:
                return None
            buf += part
            if len(buf) > 1024:
                return None

        header, body = buf.split(b'\r\n\r\n', 1)
        # Status line must contain " 200"
        status_line = header.split(b'\r\n', 1)[0]
        if b' 200' not in status_line:
            return None

        # Assemble exactly 512 body bytes into one bytearray
        out = bytearray(512)
        got = len(body)
        if got > 512:
            got = 512
        if got:
            out[:got] = body[:got]
        while got < 512:
            feed_wdt()
            part = s.recv(512 - got)
            if not part:
                return None
            out[got:got + len(part)] = part
            got += len(part)

        return out
    except Exception as e:
        print('sock chunk', n, e)
        invalidate_host()
        return None
    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass
        feed_wdt()

def send_pixel_pair(high, low):
    """Write one RGB565 pixel (2 bytes) as data."""
    send_byte(high, 1)
    send_byte(low, 1)

# === Photo constants ===
SRC_SIZE = 240
CHUNKS = 225
TOTAL_PIXELS = SRC_SIZE * SRC_SIZE
CHUNK_BYTES = 512

def update_photo():
    feed_wdt()
    maybe_periodic_reboot()
    ensure_wifi()
    gc.collect()
    free = gc.mem_free()
    print('update_photo free=', free)
    if free < MIN_FREE_MEM:
        hard_reset('low memory')

    set_window(0, 0, 239, 239)
    pixel_index = 0

    for chunk_n in range(CHUNKS):
        feed_wdt()
        maybe_periodic_reboot()

        data = None
        for attempt in range(CHUNK_RETRIES):
            feed_wdt()
            data = http_get_chunk(chunk_n)
            if data is not None and len(data) == CHUNK_BYTES:
                break
            data = None
            # Brief backoff; re-check WiFi on last try
            time.sleep_ms(100 + attempt * 150)
            if attempt == CHUNK_RETRIES - 1:
                ensure_wifi()
            gc.collect()

        if data is None:
            print('chunk fail', chunk_n)
            return False

        # Stream pixels to panel immediately; feed WDT mid-chunk
        for i in range(0, CHUNK_BYTES, 2):
            if (i & 0x3F) == 0:
                feed_wdt()
            send_pixel_pair(data[i], data[i + 1])
            pixel_index += 1

        # Drop reference ASAP; reclaim every few chunks
        data = None
        if (chunk_n & 0x0F) == 0:
            gc.collect()
            feed_wdt()
            if chunk_n and (chunk_n % 50 == 0):
                print('chunk', chunk_n, 'free', gc.mem_free())

    print('All chunks ok, pixels=', pixel_index)
    return pixel_index == TOTAL_PIXELS

# === Font (unchanged) ===
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

def draw_text(x_start, y_start, text):
    # your existing draw_text function stays exactly the same
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

# === Main loop: WDT + 5-min reboot + never sit hung ===
start_wdt()
feed_wdt()
fail_streak = 0

while True:
    try:
        feed_wdt()
        maybe_periodic_reboot()
        gc.collect()
        set_window(0, 0, 239, 239)
        draw_text(90, 110, "LOADING...")
        print('=== photo update ===')
        if update_photo():
            fail_streak = 0
            print('Photo SUCCESS')
            # Keep success text minimal (saves time/heap)
            draw_text(80, 100, "ENJOY!!!")
        else:
            fail_streak += 1
            print('Photo FAIL streak', fail_streak)
            draw_text(40, 100, "NO PHOTO")
            draw_text(20, 130, "CHECK SERVER")
            if fail_streak >= MAX_FAIL_STREAK:
                hard_reset('fail streak')
            # Short pause then retry quickly instead of sitting on error
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < 1500:
                feed_wdt()
                maybe_periodic_reboot()
                time.sleep_ms(100)
            continue

        # Brief dwell between full frames (~3s); keep WDT alive
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 3000:
            feed_wdt()
            maybe_periodic_reboot()
            machine.idle()
            time.sleep_ms(100)
    except Exception as e:
        print('MAIN EXC:', e)
        try:
            import sys
            sys.print_exception(e)
        except Exception:
            pass
        time.sleep_ms(200)
        hard_reset('main exception')
