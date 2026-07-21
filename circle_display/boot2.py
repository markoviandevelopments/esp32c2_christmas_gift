# boot2.py - Circle-screen boot (DNS + long URLs + BLE buffer fix)
# Flow: BLE provision if needed → WiFi → download tertiary.mpy (or use cache) → import
# Must NEVER exit idle: any failure path soft-reboots so the chip recovers alone.
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

# Print MAC early
mac_bytes = machine.unique_id()
mac_str = ':'.join(['{:02X}'.format(b) for b in mac_bytes])
print("=== XH-C2X MAC ===")
print(mac_str)
print("=================================")

# BLE UUIDs
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
print('BLE activated')
gc.collect()

connected = False
provisioned_ssid = None
provisioned_pass = None
provisioned_server_ip = 'ghostshrimp.immenseaccumulationonline.online'
provisioned_server_port = ''   # empty = no port in URL

ssid_handle = pass_handle = server_ip_handle = server_port_handle = None

# Minimum valid tertiary.mpy size — refuse to overwrite cache with HTML/error bodies
MIN_TERTIARY_BYTES = 2000


def ble_irq(event, data):
    global connected, provisioned_ssid, provisioned_pass, provisioned_server_ip, provisioned_server_port
    if event == _IRQ_CENTRAL_CONNECT:
        conn_handle, _, addr = data
        print('Connected:', binascii.hexlify(addr).decode())
        connected = True
    elif event == _IRQ_CENTRAL_DISCONNECT:
        print('Disconnected')
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
                print('SSID saved:', decoded)
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
                print('Server port saved:', decoded)
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
    # CRITICAL FIX FOR LONG DNS NAMES
    ble.gatts_set_buffer(server_ip_handle, 80)
    print('Services registered')


register_services()
print('Ready - starting advertising')
gc.collect()


def stop_ble():
    """Free RAM before WiFi + large mpy import (C2 is tight)."""
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


async def reboot_soon(reason, seconds=20):
    """Never leave the chip idle forever."""
    print(reason, '- reboot in', seconds, 's')
    await asyncio.sleep(seconds)
    machine.reset()


async def connect_wifi(ssid, password, tries=30):
    print('Free memory before WiFi:', gc.mem_free())
    sta = network.WLAN(network.STA_IF)
    if sta.isconnected():
        print('Already connected:', sta.ifconfig()[0])
        return True
    try:
        if not sta.active():
            sta.active(True)
        try:
            sta.disconnect()
        except Exception:
            pass
        sta.connect(ssid, password)
    except Exception as e:
        print('WiFi connect err:', e)
        return False
    print('Connecting to WiFi "%s"...' % ssid)
    for _ in range(tries):
        if sta.isconnected():
            ip = sta.ifconfig()[0]
            print('WiFi connected:', ip)
            return True
        await asyncio.sleep(1)
    print('WiFi failed')
    return False


def has_local_tertiary():
    try:
        st = os.stat('/tertiary.mpy')
        return st[6] >= MIN_TERTIARY_BYTES
    except OSError:
        return False


async def download_tertiary():
    """
    Try a short OTA of tertiary.mpy. On any failure keep the existing cache.
    Never write a tiny/error body over a good local file.
    """
    url = 'http://%s/tertiary.mpy' % provisioned_server_ip
    print('Downloading from', url)
    print('Free memory before download:', gc.mem_free())
    # Few attempts, short timeout — soft-reset recovers better than sitting here 2 minutes
    for attempt in range(3):
        try:
            resp = urequests.get(url, timeout=10)
            code = resp.status_code
            data = resp.content
            try:
                resp.close()
            except Exception:
                pass
            if code == 200 and data and len(data) >= MIN_TERTIARY_BYTES:
                # Atomic-ish replace so a reset mid-write is less likely to brick cache
                with open('/tertiary.mpy.tmp', 'wb') as f:
                    f.write(data)
                try:
                    os.remove('/tertiary.mpy')
                except OSError:
                    pass
                os.rename('/tertiary.mpy.tmp', '/tertiary.mpy')
                print('Downloaded tertiary.mpy (%d bytes)' % len(data))
                return True
            print('Bad tertiary response:', code, len(data) if data else 0)
        except Exception as e:
            print('Download error:', e)
        gc.collect()
        await asyncio.sleep(2)
    print('Download failed (will try cache if present)')
    return False


async def run_tertiary():
    # Boot is flashed once; only tertiary.mpy is OTA'd.
    # Prefer a quick OTA, but if it fails use last good cache so reboot #2+ still works.
    stop_ble()
    had_cache = has_local_tertiary()
    downloaded = await download_tertiary()
    if not downloaded:
        if had_cache or has_local_tertiary():
            print('Using cached /tertiary.mpy')
        else:
            await reboot_soon('No tertiary.mpy available', 15)
            return

    gc.collect()
    print('Free memory before import:', gc.mem_free())
    try:
        import tertiary
        print('tertiary.mpy running')
        # tertiary owns the main loop; if it ever returns, reboot
        await reboot_soon('tertiary returned', 10)
    except Exception as e:
        print('Import failed:', e)
        try:
            import sys
            sys.print_exception(e)
        except Exception:
            pass
        print('Free memory after failed import:', gc.mem_free())
        # Bad OTA can leave a broken tertiary.mpy — remove it so next boot re-downloads
        if downloaded:
            try:
                os.remove('/tertiary.mpy')
                print('Removed bad tertiary.mpy after import fail')
            except OSError:
                pass
        await reboot_soon('tertiary import failed', 15)


async def advertise_and_provision():
    global connected
    name = b'XH-C2X'
    name_ad = bytes([len(name) + 1, 0x09]) + name
    adv_data = bytearray()
    adv_data += bytes([0x02, 0x01, 0x06])
    adv_data += name_ad
    adv_data += bytes([0x11, 0x07]) + bytes.fromhex('bc9a7856341234123412341278563412')
    resp_data = bytearray()
    resp_data += name_ad

    while True:
        ble.gap_advertise(100_000, adv_data=adv_data, resp_data=resp_data, connectable=True)
        print('Advertising - scan for XH-C2X')
        while not connected:
            await asyncio.sleep_ms(100)
        print('Connected - waiting for credentials...')
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 30000:
            if provisioned_ssid and provisioned_pass:
                print('Full credentials received! Proceeding to WiFi...')
                ble.gap_advertise(None)
                if await connect_wifi(provisioned_ssid, provisioned_pass):
                    await run_tertiary()
                else:
                    await reboot_soon('WiFi failed after provision', 15)
                return
            await asyncio.sleep_ms(100)
        print('Timeout - no full credentials')
        ble.gap_advertise(None)
        while connected:
            await asyncio.sleep_ms(100)


async def main():
    global provisioned_ssid, provisioned_pass, provisioned_server_ip, provisioned_server_port
    gc.collect()
    print('Free memory at start:', gc.mem_free())
    try:
        provisioned_ssid = open('/ssid.txt').read().strip()
    except OSError:
        pass
    try:
        provisioned_pass = open('/pass.txt').read().strip()
    except OSError:
        pass
    try:
        provisioned_server_ip = open('/server_ip.txt').read().strip() or 'ghostshrimp.immenseaccumulationonline.online'
    except OSError:
        pass
    try:
        provisioned_server_port = open('/server_port.txt').read().strip() or ''
    except OSError:
        pass

    if provisioned_ssid and provisioned_pass:
        print('Saved credentials found - connecting directly')
        # A few WiFi attempts before rebooting (soft-reset can leave radio flaky)
        for attempt in range(3):
            if await connect_wifi(provisioned_ssid, provisioned_pass, tries=20):
                await run_tertiary()
                return
            print('WiFi attempt', attempt + 1, 'failed')
            await asyncio.sleep(2)
        # Do not fall into forever-BLE when we already have creds — reboot and retry
        await reboot_soon('WiFi failed with saved credentials', 15)
        return

    await advertise_and_provision()
    await reboot_soon('boot ended without tertiary', 30)


asyncio.run(main())
