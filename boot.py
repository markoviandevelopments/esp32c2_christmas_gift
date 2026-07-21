# boot.py — Rectangular crypto screens (ESP32-C2 + ST7735)
#
# Flash as SOURCE text:  ampy put boot.py /boot.py
# MicroPython only auto-runs /boot.py (not boot.mpy).
#
# After BLE wifi creds:
#   1) stop advertising (do NOT ble.active(False) — hangs on many C2 builds)
#   2) connect WiFi
#   3) download secondary.mpy (LAN first, then Cloudflare hostnames)
#   4) import secondary
#
# Cloudflare: update.immenseaccumulationonline.online → desktop :9019
# Devices use http://hostname with no port. Port field "8080" is ignored for CF hosts.
import asyncio
import bluetooth
import gc
import machine
import network
import os
import time
import binascii

try:
    import usocket as socket
except ImportError:
    import socket

gc.collect()

mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes])
print('=== XH-C2X RECT boot ===')
print(mac_str)
print('free', gc.mem_free())

# BLE UUIDs (must match ble_provisioner)
_SERVICE_UUID = bluetooth.UUID('12345678-1234-1234-1234-123456789abc')
_SSID_UUID = bluetooth.UUID('87654321-4321-4321-4321-cba987654321')
_PASS_UUID = bluetooth.UUID('cba98765-4321-4321-4321-123456789abc')
_SERVER_IP_UUID = bluetooth.UUID('11111111-2222-3333-4444-555555555555')
_SERVER_PORT_UUID = bluetooth.UUID('99999999-8888-7777-6666-555555555555')

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2
_IRQ_GATTS_WRITE = 3

ble = bluetooth.BLE()
ble.active(True)
print('BLE on free', gc.mem_free())
gc.collect()

connected = False
provisioned_ssid = None
provisioned_pass = None
provisioned_server_ip = 'update.immenseaccumulationonline.online'
provisioned_server_port = ''

ssid_handle = pass_handle = server_ip_handle = server_port_handle = None
MIN_MPY = 2000

# Desktop on the same LAN as BrubakerWifi2 (x_mas_server :9019)
LAN_OTA_BASES = (
    'http://192.168.1.219:9019',
)


def ble_irq(event, data):
    global connected, provisioned_ssid, provisioned_pass
    global provisioned_server_ip, provisioned_server_port
    if event == _IRQ_CENTRAL_CONNECT:
        connected = True
        print('BLE phone connected')
    elif event == _IRQ_CENTRAL_DISCONNECT:
        connected = False
        print('BLE phone disconnected')
    elif event == _IRQ_GATTS_WRITE:
        try:
            value = ble.gatts_read(data[1])
            decoded = value.decode('utf-8').rstrip('\x00')
            h = data[1]
            if h == ssid_handle:
                provisioned_ssid = decoded
                open('/ssid.txt', 'w').write(decoded)
                print('SSID ok')
            elif h == pass_handle:
                provisioned_pass = decoded
                open('/pass.txt', 'w').write(decoded)
                print('PASS ok')
            elif h == server_ip_handle:
                provisioned_server_ip = decoded
                open('/server_ip.txt', 'w').write(decoded)
                print('HOST ok', decoded)
            elif h == server_port_handle:
                provisioned_server_port = decoded
                open('/server_port.txt', 'w').write(decoded)
                print('PORT field ok', decoded)
        except Exception as e:
            print('IRQ', e)


ble.irq(ble_irq)


def register_services():
    global ssid_handle, pass_handle, server_ip_handle, server_port_handle
    chars = (
        (_SSID_UUID, bluetooth.FLAG_WRITE_NO_RESPONSE),
        (_PASS_UUID, bluetooth.FLAG_WRITE_NO_RESPONSE),
        (_SERVER_IP_UUID, bluetooth.FLAG_WRITE_NO_RESPONSE),
        (_SERVER_PORT_UUID, bluetooth.FLAG_WRITE_NO_RESPONSE),
    )
    handles = ble.gatts_register_services([(_SERVICE_UUID, chars)])[0]
    ssid_handle, pass_handle, server_ip_handle, server_port_handle = handles
    ble.gatts_set_buffer(server_ip_handle, 80)
    print('services ok')


register_services()
gc.collect()


def stop_adv():
    """Stop advertising only. Never ble.active(False) — freezes many C2 builds."""
    try:
        ble.gap_advertise(None)
    except Exception:
        pass
    gc.collect()
    print('adv off free', gc.mem_free())


def http_get_bytes(url, timeout_s=20):
    """Minimal HTTP/1.0 GET via usocket (more reliable than urequests on C2)."""
    # url: http://host[:port]/path
    if not url.startswith('http://'):
        raise ValueError('only http')
    rest = url[7:]
    hostpath = rest.split('/', 1)
    hostport = hostpath[0]
    path = '/' + hostpath[1] if len(hostpath) > 1 else '/'
    if ':' in hostport:
        host, ports = hostport.split(':', 1)
        port = int(ports)
    else:
        host = hostport
        port = 80
    print('socket GET', host, port, path)
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
            # cap (secondary.mpy ~10KB; allow headroom)
            if len(buf) > 40000:
                break
    finally:
        try:
            s.close()
        except Exception:
            pass
    if b'\r\n\r\n' not in buf:
        raise OSError('no headers')
    header, body = buf.split(b'\r\n\r\n', 1)
    status = header.split(b'\r\n', 1)[0]
    if b' 200' not in status:
        raise OSError('http ' + status.decode('utf-8', 'ignore'))
    return body


def ota_url_list():
    """Order matters: LAN desktop first (works offline of Cloudflare), then CF hosts."""
    urls = []
    for base in LAN_OTA_BASES:
        urls.append(base + '/secondary.mpy')
    hosts = []
    h0 = (provisioned_server_ip or '').strip()
    if h0:
        hosts.append(h0)
    for h in (
        'update.immenseaccumulationonline.online',
        'ghostshrimp.immenseaccumulationonline.online',
    ):
        if h not in hosts:
            hosts.append(h)
    for h in hosts:
        # CF / domain: never append :8080
        if h.endswith('immenseaccumulationonline.online') or not h[0].isdigit():
            # if it looks like an IP, allow real port
            if h.replace('.', '').isdigit():
                port = (provisioned_server_port or '').strip()
                if port and port not in ('80', '443', '8080'):
                    urls.append('http://%s:%s/secondary.mpy' % (h, port))
                else:
                    urls.append('http://%s/secondary.mpy' % h)
            else:
                urls.append('http://%s/secondary.mpy' % h)
        else:
            urls.append('http://%s/secondary.mpy' % h)
    # de-dupe preserve order
    out = []
    for u in urls:
        if u not in out:
            out.append(u)
    return out


async def connect_wifi(ssid, password, tries=45):
    sta = network.WLAN(network.STA_IF)
    if not sta.active():
        sta.active(True)
        await asyncio.sleep_ms(400)
    if sta.isconnected():
        print('wifi already', sta.ifconfig())
        return True
    try:
        try:
            sta.disconnect()
        except Exception:
            pass
        await asyncio.sleep_ms(200)
        print('wifi connect', ssid)
        sta.connect(ssid, password)
    except Exception as e:
        print('wifi err', e)
        return False
    for i in range(tries):
        if sta.isconnected():
            print('wifi OK', sta.ifconfig())
            return True
        await asyncio.sleep(1)
        if (i + 1) % 10 == 0:
            print('wifi wait', i + 1)
    print('wifi FAIL')
    return False


def has_secondary():
    try:
        return os.stat('/secondary.mpy')[6] >= MIN_MPY
    except OSError:
        return False


async def download_secondary():
    urls = ota_url_list()
    print('OTA candidates', len(urls), 'free', gc.mem_free())
    for url in urls:
        for attempt in range(3):
            try:
                sta = network.WLAN(network.STA_IF)
                if not sta.isconnected():
                    print('wifi down')
                    return False
                print('try', url, 'n', attempt)
                body = http_get_bytes(url, timeout_s=25)
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
            await asyncio.sleep(1)
    return False


async def reboot_soon(msg, sec=12):
    print(msg, 'reset', sec)
    await asyncio.sleep(sec)
    machine.reset()


async def run_secondary():
    had = has_secondary()
    ok = await download_secondary()
    if not ok:
        if had:
            print('using cache secondary.mpy')
        else:
            await reboot_soon('no secondary.mpy')
            return
    gc.collect()
    print('import free', gc.mem_free())
    try:
        import secondary
        print('secondary running')
        # secondary owns forever; if it returns:
        await reboot_soon('secondary returned', 8)
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
        await reboot_soon('import fail')


async def go_online():
    stop_adv()
    await asyncio.sleep_ms(500)
    if not provisioned_ssid or not provisioned_pass:
        await reboot_soon('no wifi creds')
        return
    for n in range(4):
        if await connect_wifi(provisioned_ssid, provisioned_pass):
            await asyncio.sleep(2)  # DHCP/DNS settle
            await run_secondary()
            return
        print('wifi retry', n + 1)
        await asyncio.sleep(2)
    await reboot_soon('wifi failed')


async def advertise_and_provision():
    global connected
    name = b'XH-C2X'
    name_ad = bytes([len(name) + 1, 0x09]) + name
    adv = bytearray([0x02, 0x01, 0x06]) + name_ad
    adv += bytes([0x11, 0x07]) + bytes.fromhex('bc9a7856341234123412341278563412')
    resp = bytearray(name_ad)

    while True:
        ble.gap_advertise(100_000, adv_data=adv, resp_data=resp, connectable=True)
        print('Advertising XH-C2X')
        while not connected:
            await asyncio.sleep_ms(100)
        print('waiting SSID+PASS...')
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 60000:
            if provisioned_ssid and provisioned_pass:
                # wait for optional host/port writes (app sends after pass)
                await asyncio.sleep_ms(2500)
                print('creds ready host=', provisioned_server_ip)
                await go_online()
                return
            await asyncio.sleep_ms(100)
        print('provision timeout')
        stop_adv()
        while connected:
            await asyncio.sleep_ms(100)


async def main():
    global provisioned_ssid, provisioned_pass, provisioned_server_ip, provisioned_server_port
    gc.collect()
    try:
        provisioned_ssid = open('/ssid.txt').read().strip()
    except OSError:
        pass
    try:
        provisioned_pass = open('/pass.txt').read().strip()
    except OSError:
        pass
    try:
        provisioned_server_ip = open('/server_ip.txt').read().strip() or 'update.immenseaccumulationonline.online'
    except OSError:
        pass
    try:
        provisioned_server_port = open('/server_port.txt').read().strip() or ''
    except OSError:
        pass

    if provisioned_ssid and provisioned_pass:
        print('saved wifi, going online')
        await go_online()
        return
    await advertise_and_provision()
    await reboot_soon('boot end', 20)


asyncio.run(main())
