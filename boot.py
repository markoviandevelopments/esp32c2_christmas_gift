# boot.py — Rectangular crypto screens (ST7735) on ESP32-C2
#
# Flow: BLE provision → fully stop BLE → WiFi → download secondary.mpy → import
#
# Cloudflare hostnames (e.g. update.immenseaccumulationonline.online) map to
# desktop ports on the tunnel side (update → :9019). Devices always use
# http://hostname with NO :8080 / :9019 in the URL.
#
# IMPORTANT: Flash this file as SOURCE /boot.py (not .mpy). MicroPython runs boot.py.
import asyncio
import bluetooth
import gc
import machine
import network
import os
import time
import urequests
import binascii

gc.collect()

mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes])
print('=== XH-C2X RECT boot ===')
print(mac_str)

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
print('BLE activated, free=', gc.mem_free())
gc.collect()

connected = False
provisioned_ssid = None
provisioned_pass = None
provisioned_server_ip = 'update.immenseaccumulationonline.online'
provisioned_server_port = ''

ssid_handle = pass_handle = server_ip_handle = server_port_handle = None
MIN_SECONDARY_BYTES = 2000


def ble_irq(event, data):
    global connected, provisioned_ssid, provisioned_pass, provisioned_server_ip, provisioned_server_port
    if event == _IRQ_CENTRAL_CONNECT:
        print('BLE central connected')
        connected = True
    elif event == _IRQ_CENTRAL_DISCONNECT:
        print('BLE central disconnected')
        connected = False
    elif event == _IRQ_GATTS_WRITE:
        conn_handle, value_handle = data
        try:
            value = ble.gatts_read(value_handle)
            decoded = value.decode('utf-8').rstrip('\x00')
            if value_handle == ssid_handle:
                provisioned_ssid = decoded
                with open('/ssid.txt', 'w') as f:
                    f.write(decoded)
                print('SSID saved')
            elif value_handle == pass_handle:
                provisioned_pass = decoded
                with open('/pass.txt', 'w') as f:
                    f.write(decoded)
                print('Password saved')
            elif value_handle == server_ip_handle:
                provisioned_server_ip = decoded
                with open('/server_ip.txt', 'w') as f:
                    f.write(decoded)
                print('Server host saved:', decoded)
            elif value_handle == server_port_handle:
                provisioned_server_port = decoded
                with open('/server_port.txt', 'w') as f:
                    f.write(decoded)
                print('Server port field saved:', decoded)
        except Exception as e:
            print('IRQ error:', e)


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
    print('BLE services registered')


register_services()
gc.collect()


def stop_ble():
    """Turn BLE fully off. On C2, WiFi+BLE concurrent often breaks HTTP."""
    global ble
    try:
        ble.gap_advertise(None)
    except Exception:
        pass
    try:
        ble.active(False)
    except Exception:
        pass
    gc.collect()
    print('BLE off, free=', gc.mem_free())


async def connect_wifi(ssid, password, tries=40):
    print('WiFi connect free=', gc.mem_free())
    sta = network.WLAN(network.STA_IF)
    if not sta.active():
        sta.active(True)
        await asyncio.sleep_ms(300)
    if sta.isconnected():
        print('Already on WiFi', sta.ifconfig()[0])
        return True
    try:
        try:
            sta.disconnect()
        except Exception:
            pass
        await asyncio.sleep_ms(200)
        sta.connect(ssid, password)
    except Exception as e:
        print('WiFi connect err', e)
        return False
    print('Connecting WiFi...')
    for i in range(tries):
        if sta.isconnected():
            print('WiFi OK', sta.ifconfig())
            return True
        await asyncio.sleep(1)
        if i % 5 == 4:
            print('  still waiting WiFi...', i + 1)
    print('WiFi failed')
    return False


def server_base_url(host=None, port=None):
    if host is None:
        host = provisioned_server_ip
    if port is None:
        port = provisioned_server_port
    host = (host or 'update.immenseaccumulationonline.online').strip()
    port = (port or '').strip()
    # Cloudflare tunnel public names → always port 80 (no suffix)
    if host.endswith('immenseaccumulationonline.online'):
        return 'http://' + host
    if port in ('', '80', '443', '8080'):
        return 'http://' + host
    return 'http://%s:%s' % (host, port)


def has_local_secondary():
    try:
        return os.stat('/secondary.mpy')[6] >= MIN_SECONDARY_BYTES
    except OSError:
        return False


async def download_secondary():
    """Fetch secondary.mpy. Prefer update host (desktop :9019 via CF)."""
    hosts = []
    for h in (
        (provisioned_server_ip or '').strip(),
        'update.immenseaccumulationonline.online',
        'ghostshrimp.immenseaccumulationonline.online',
    ):
        if h and h not in hosts:
            hosts.append(h)

    print('download free=', gc.mem_free())
    for host in hosts:
        url = server_base_url(host, provisioned_server_port) + '/secondary.mpy'
        print('GET', url)
        for attempt in range(4):
            try:
                # Confirm WiFi still up
                sta = network.WLAN(network.STA_IF)
                if not sta.isconnected():
                    print('WiFi dropped before download')
                    return False
                resp = urequests.get(url, timeout=20)
                code = resp.status_code
                data = resp.content
                try:
                    resp.close()
                except Exception:
                    pass
                if code == 200 and data and len(data) >= MIN_SECONDARY_BYTES and data[0:1] == b'M':
                    with open('/secondary.mpy.tmp', 'wb') as f:
                        f.write(data)
                    try:
                        os.remove('/secondary.mpy')
                    except OSError:
                        pass
                    os.rename('/secondary.mpy.tmp', '/secondary.mpy')
                    print('OK secondary.mpy', len(data), 'from', host)
                    return True
                print('bad response', code, len(data) if data else 0)
            except Exception as e:
                print('download err', attempt, e)
            gc.collect()
            await asyncio.sleep(2)
    return False


async def reboot_soon(reason, seconds=15):
    print(reason, '- reset in', seconds, 's')
    await asyncio.sleep(seconds)
    machine.reset()


async def run_secondary():
    # BLE must already be off before this (WiFi exclusive on C2).
    had = has_local_secondary()
    ok = await download_secondary()
    if not ok:
        if had or has_local_secondary():
            print('Using cached secondary.mpy')
        else:
            await reboot_soon('no secondary.mpy')
            return

    gc.collect()
    print('import free=', gc.mem_free())
    try:
        import secondary
        print('secondary running')
        await reboot_soon('secondary returned', 10)
    except Exception as e:
        print('import failed', e)
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
        await reboot_soon('import failed')


async def go_online_and_run():
    """Shared path: kill BLE, join WiFi, pull secondary."""
    stop_ble()
    # Let radio fully release BLE before STA
    await asyncio.sleep_ms(800)
    ssid = provisioned_ssid
    pw = provisioned_pass
    if not ssid or not pw:
        await reboot_soon('missing wifi creds')
        return
    for attempt in range(3):
        if await connect_wifi(ssid, pw, tries=40):
            # DNS / DHCP settle — without this, first HTTP often fails on C2
            await asyncio.sleep(2)
            await run_secondary()
            return
        print('WiFi attempt', attempt + 1, 'failed')
        await asyncio.sleep(2)
    await reboot_soon('wifi failed')


async def advertise_and_provision():
    global connected
    name = b'XH-C2X'
    name_ad = bytes([len(name) + 1, 0x09]) + name
    adv_data = bytearray([0x02, 0x01, 0x06]) + name_ad + bytes([0x11, 0x07]) + bytes.fromhex(
        'bc9a7856341234123412341278563412'
    )
    resp_data = bytearray(name_ad)

    while True:
        ble.gap_advertise(100_000, adv_data=adv_data, resp_data=resp_data, connectable=True)
        print('Advertising XH-C2X — provision with BLE app')
        while not connected:
            await asyncio.sleep_ms(100)
        print('Phone connected — waiting for SSID/password/host...')
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 45000:
            if provisioned_ssid and provisioned_pass:
                # Allow time for host/port writes after ssid/pass (WRITE_NO_RESPONSE races)
                await asyncio.sleep_ms(2000)
                print('Creds ready host=', provisioned_server_ip, 'port_field=', provisioned_server_port or '(none)')
                print('OTA base=', server_base_url())
                await go_online_and_run()
                return
            await asyncio.sleep_ms(100)
        print('Provision timeout — disconnect and re-advertise')
        try:
            ble.gap_advertise(None)
        except Exception:
            pass
        while connected:
            await asyncio.sleep_ms(100)


async def main():
    global provisioned_ssid, provisioned_pass, provisioned_server_ip, provisioned_server_port
    gc.collect()
    print('boot free=', gc.mem_free())
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
        print('Saved WiFi found — going online')
        print('host=', provisioned_server_ip, 'OTA=', server_base_url())
        await go_online_and_run()
        return

    await advertise_and_provision()
    await reboot_soon('boot ended', 30)


asyncio.run(main())
