# boot.py — Rectangular crypto screens (ESP32-C2 + ST7735)
#
# CRITICAL: Do NOT enable BLE until needed. ble.active(True) brownouts these
# boards (display + radio current spike) and was causing infinite reboot:
#   === XH-C2X RECT boot ===
#   free ...
#   E BOD: Brownout detector was triggered
#
# Flash as SOURCE:  mpremote connect /dev/ttyUSB0 fs cp boot.py :boot.py
#
# Cloudflare: update.immenseaccumulationonline.online → desktop :9019
# Prefer LAN http://192.168.1.219:9019 for OTA when on same WiFi.
import gc
import machine
import network
import os
import time
import binascii

gc.collect()

mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes])
print('=== XH-C2X RECT boot ===')
print(mac_str)
print('free', gc.mem_free())

# Lower CPU a bit before radio/display work (helps weak USB supplies)
try:
    machine.freq(120000000)
except Exception:
    pass

MIN_MPY = 2000
LAN_OTA = 'http://192.168.1.219:9019'
DEFAULT_HOST = 'update.immenseaccumulationonline.online'

# Load saved provisioning FIRST — before any BLE
ssid = ''
password = ''
server_host = DEFAULT_HOST
server_port = ''
try:
    ssid = open('/ssid.txt').read().strip()
except OSError:
    pass
try:
    password = open('/pass.txt').read().strip()
except OSError:
    pass
try:
    server_host = open('/server_ip.txt').read().strip() or DEFAULT_HOST
except OSError:
    pass
try:
    server_port = open('/server_port.txt').read().strip()
except OSError:
    pass


def http_get_bytes(url, timeout_s=25):
    try:
        import usocket as socket
    except ImportError:
        import socket
    if not url.startswith('http://'):
        raise ValueError('http only')
    rest = url[7:]
    hostpath = rest.split('/', 1)
    hostport = hostpath[0]
    path = '/' + hostpath[1] if len(hostpath) > 1 else '/'
    if ':' in hostport:
        host, ps = hostport.split(':', 1)
        port = int(ps)
    else:
        host, port = hostport, 80
    print('GET', host, port, path)
    ai = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    addr = ai[0][-1]
    s = socket.socket()
    s.settimeout(timeout_s)
    try:
        s.connect(addr)
        req = b'GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n' % (
            path.encode(), host.encode())
        s.send(req)
        buf = b''
        while True:
            try:
                chunk = s.recv(1024)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            if len(buf) > 40000:
                break
    finally:
        try:
            s.close()
        except Exception:
            pass
    if b'\r\n\r\n' not in buf:
        raise OSError('no http headers')
    header, body = buf.split(b'\r\n\r\n', 1)
    if b' 200' not in header.split(b'\r\n', 1)[0]:
        raise OSError(header.split(b'\r\n', 1)[0].decode('utf-8', 'ignore'))
    return body


def ota_urls():
    urls = [LAN_OTA + '/secondary.mpy']
    hosts = []
    for h in (server_host, DEFAULT_HOST, 'ghostshrimp.immenseaccumulationonline.online'):
        h = (h or '').strip()
        if h and h not in hosts:
            hosts.append(h)
    for h in hosts:
        # IP with real non-CF port
        parts = h.split('.')
        is_ip = len(parts) == 4 and all(p.isdigit() for p in parts)
        if is_ip:
            p = (server_port or '').strip()
            if p and p not in ('80', '443', '8080'):
                urls.append('http://%s:%s/secondary.mpy' % (h, p))
            else:
                urls.append('http://%s/secondary.mpy' % h)
        else:
            # Cloudflare tunnel hostname — no port suffix
            urls.append('http://%s/secondary.mpy' % h)
    out = []
    for u in urls:
        if u not in out:
            out.append(u)
    return out


def connect_wifi(ssid, password, tries=50):
    sta = network.WLAN(network.STA_IF)
    if not sta.active():
        sta.active(True)
        time.sleep_ms(400)
    if sta.isconnected():
        print('wifi already', sta.ifconfig())
        return True
    try:
        try:
            sta.disconnect()
        except Exception:
            pass
        time.sleep_ms(200)
        print('wifi connect', ssid)
        sta.connect(ssid, password)
    except Exception as e:
        print('wifi err', e)
        return False
    for i in range(tries):
        if sta.isconnected():
            print('wifi OK', sta.ifconfig())
            return True
        time.sleep(1)
        if (i + 1) % 10 == 0:
            print('wifi wait', i + 1)
    print('wifi FAIL')
    return False


def has_secondary():
    try:
        return os.stat('/secondary.mpy')[6] >= MIN_MPY
    except OSError:
        return False


def download_secondary():
    print('OTA free', gc.mem_free())
    for url in ota_urls():
        for attempt in range(3):
            try:
                sta = network.WLAN(network.STA_IF)
                if not sta.isconnected():
                    print('wifi down')
                    return False
                print('try', url, attempt)
                body = http_get_bytes(url, 25)
                if body and len(body) >= MIN_MPY and body[0:1] == b'M':
                    with open('/secondary.mpy.tmp', 'wb') as f:
                        f.write(body)
                    try:
                        os.remove('/secondary.mpy')
                    except OSError:
                        pass
                    os.rename('/secondary.mpy.tmp', '/secondary.mpy')
                    print('saved secondary.mpy', len(body))
                    return True
                print('bad body', len(body) if body else 0)
            except Exception as e:
                print('ota err', e)
            gc.collect()
            time.sleep(1)
    return False


def run_secondary():
    had = has_secondary()
    ok = download_secondary()
    if not ok:
        if had:
            print('using cached secondary.mpy')
        else:
            print('no secondary.mpy — reset in 12s')
            time.sleep(12)
            machine.reset()
            return
    gc.collect()
    print('import free', gc.mem_free())
    try:
        import secondary
        print('secondary running')
    except Exception as e:
        print('import fail', e)
        try:
            import sys
            sys.print_exception(e)
        except Exception:
            pass
        if ok:
            try:
                os.remove('/secondary.mpy')
            except OSError:
                pass
        time.sleep(12)
        machine.reset()


def go_online():
    if not ssid or not password:
        print('missing wifi creds')
        time.sleep(8)
        machine.reset()
        return
    for n in range(4):
        if connect_wifi(ssid, password):
            time.sleep(2)
            run_secondary()
            return
        print('wifi retry', n + 1)
        time.sleep(2)
    print('wifi failed — reset')
    time.sleep(12)
    machine.reset()


def provision_via_ble():
    """Only path that turns BLE on — after a short settle delay."""
    import bluetooth
    import asyncio

    global ssid, password, server_host, server_port

    print('BLE provision mode (settle power first)...')
    time.sleep_ms(1500)
    gc.collect()
    print('free before BLE', gc.mem_free())

    _SERVICE = bluetooth.UUID('12345678-1234-1234-1234-123456789abc')
    _SSID = bluetooth.UUID('87654321-4321-4321-4321-cba987654321')
    _PASS = bluetooth.UUID('cba98765-4321-4321-4321-123456789abc')
    _HOST = bluetooth.UUID('11111111-2222-3333-4444-555555555555')
    _PORT = bluetooth.UUID('99999999-8888-7777-6666-555555555555')
    IRQ_CONNECT = 1
    IRQ_DISCONNECT = 2
    IRQ_WRITE = 3

    ble = bluetooth.BLE()
    # Single active(True) — if BOD still fires, power supply is insufficient
    ble.active(True)
    print('BLE active free', gc.mem_free())
    gc.collect()

    state = {
        'connected': False,
        'ssid': None,
        'pass': None,
        'host': server_host,
        'port': server_port,
        'sh': None,
        'ph': None,
        'hh': None,
        'oh': None,
    }

    def irq(event, data):
        if event == IRQ_CONNECT:
            state['connected'] = True
            print('phone connected')
        elif event == IRQ_DISCONNECT:
            state['connected'] = False
            print('phone disconnected')
        elif event == IRQ_WRITE:
            try:
                raw = ble.gatts_read(data[1])
                text = raw.decode('utf-8').rstrip('\x00')
                h = data[1]
                if h == state['sh']:
                    state['ssid'] = text
                    open('/ssid.txt', 'w').write(text)
                    print('SSID ok')
                elif h == state['ph']:
                    state['pass'] = text
                    open('/pass.txt', 'w').write(text)
                    print('PASS ok')
                elif h == state['hh']:
                    state['host'] = text
                    open('/server_ip.txt', 'w').write(text)
                    print('HOST ok', text)
                elif h == state['oh']:
                    state['port'] = text
                    open('/server_port.txt', 'w').write(text)
                    print('PORT ok', text)
            except Exception as e:
                print('IRQ', e)

    ble.irq(irq)
    chars = (
        (_SSID, bluetooth.FLAG_WRITE_NO_RESPONSE),
        (_PASS, bluetooth.FLAG_WRITE_NO_RESPONSE),
        (_HOST, bluetooth.FLAG_WRITE_NO_RESPONSE),
        (_PORT, bluetooth.FLAG_WRITE_NO_RESPONSE),
    )
    handles = ble.gatts_register_services([(_SERVICE, chars)])[0]
    state['sh'], state['ph'], state['hh'], state['oh'] = handles
    ble.gatts_set_buffer(state['hh'], 80)
    print('BLE services ok')

    name = b'XH-C2X'
    name_ad = bytes([len(name) + 1, 0x09]) + name
    adv = bytearray([0x02, 0x01, 0x06]) + name_ad
    adv += bytes([0x11, 0x07]) + bytes.fromhex('bc9a7856341234123412341278563412')
    resp = bytearray(name_ad)

    async def loop():
        while True:
            ble.gap_advertise(100_000, adv_data=adv, resp_data=resp, connectable=True)
            print('Advertising XH-C2X')
            while not state['connected']:
                await asyncio.sleep_ms(100)
            print('waiting SSID+PASS...')
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < 60000:
                if state['ssid'] and state['pass']:
                    await asyncio.sleep_ms(2500)
                    # Update globals for OTA host selection
                    global ssid, password, server_host, server_port
                    ssid = state['ssid']
                    password = state['pass']
                    server_host = state['host'] or DEFAULT_HOST
                    server_port = state['port'] or ''
                    print('creds ready — stop adv, then WiFi (BLE stays on, no active(False))')
                    try:
                        ble.gap_advertise(None)
                    except Exception:
                        pass
                    gc.collect()
                    await asyncio.sleep_ms(500)
                    # leave asyncio; go_online is sync
                    return
                await asyncio.sleep_ms(100)
            print('provision timeout')
            try:
                ble.gap_advertise(None)
            except Exception:
                pass
            while state['connected']:
                await asyncio.sleep_ms(100)

    asyncio.run(loop())
    # After BLE provision returns: connect WiFi + secondary
    go_online()


# === Entry ===
if ssid and password:
    print('saved WiFi — skip BLE (avoids brownout)')
    go_online()
else:
    print('no saved WiFi — BLE provision')
    try:
        provision_via_ble()
    except Exception as e:
        print('BLE provision crash', e)
        try:
            import sys
            sys.print_exception(e)
        except Exception:
            pass
        time.sleep(8)
        machine.reset()
