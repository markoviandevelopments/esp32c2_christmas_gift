# boot.py - Pure BLE provisioning + immediate WiFi connect after provisioning (no restart needed)
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
provisioned_server_ip = '108.254.1.184'
provisioned_server_port = '9019'

ssid_handle = pass_handle = server_ip_handle = server_port_handle = None

def ble_irq(event, data):
    global connected, provisioned_ssid, provisioned_pass
    global provisioned_server_ip, provisioned_server_port
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
                with open('/ssid.txt', 'w') as f: f.write(decoded)
                print('SSID saved:', decoded)
            elif value_handle == pass_handle:
                provisioned_pass = decoded
                with open('/pass.txt', 'w') as f: f.write(decoded)
                print('Password saved')
            elif value_handle == server_ip_handle:
                provisioned_server_ip = decoded
                with open('/server_ip.txt', 'w') as f: f.write(decoded)
                print('Server IP saved:', decoded)
            elif value_handle == server_port_handle:
                provisioned_server_port = decoded
                with open('/server_port.txt', 'w') as f: f.write(decoded)
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
    print('Services registered')

register_services()
print('Ready - starting advertising')
gc.collect()

async def connect_wifi(ssid, password):
    print('Free memory before WiFi:', gc.mem_free())
    sta = network.WLAN(network.STA_IF)
    if sta.isconnected():
        print('Already connected:', sta.ifconfig()[0])
        return True
    sta.active(True)
    sta.connect(ssid, password)
    print(f'Connecting to WiFi "{ssid}"...')
    for _ in range(30):
        if sta.isconnected():
            ip = sta.ifconfig()[0]
            print('WiFi connected:', ip)
            return True
        await asyncio.sleep(1)
    print('WiFi failed')
    return False

async def download_secondary():
    url = f'http://{provisioned_server_ip}:{provisioned_server_port}/tertiary.mpy'
    print(f'Downloading from {url}')
    print('Free memory before download:', gc.mem_free())
    for attempt in range(5):
        try:
            resp = urequests.get(url, timeout=10)
            if resp.status_code == 200:
                with open('/tertiary.mpy', 'wb') as f:
                    f.write(resp.content)
                print('Downloaded tertiary.mpy (' + str(len(resp.content)) + ' bytes)')
                return True
        except Exception as e:
            print('Download error:', e)
        await asyncio.sleep(5)
    print('Download failed')
    return False

async def run_secondary():
    if await download_secondary():
        gc.collect()
        print('Free memory before import:', gc.mem_free())
        try:
            import secondary
            print('tertiary.mpy running')
        except Exception as e:
            print('Import failed:', e)
            import sys
            sys.print_exception(e)
            print('Free memory after failed import:', gc.mem_free())

async def advertise_and_provision():
    global connected
    # Name in both adv and scan response
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
                ble.gap_advertise(None)  # Stop advertising immediately
                if await connect_wifi(provisioned_ssid, provisioned_pass):
                    await run_secondary()
                return  # Exit loop - secondary takes over forever
            await asyncio.sleep_ms(100)

        print('Timeout - no full credentials')
        ble.gap_advertise(None)

        # Optional: wait for disconnect before re-advertising
        while connected:
            await asyncio.sleep_ms(100)

async def main():
    global provisioned_ssid, provisioned_pass, provisioned_server_ip, provisioned_server_port
    gc.collect()
    print('Free memory at start:', gc.mem_free())
    try:
        provisioned_ssid = open('/ssid.txt').read().strip()
    except OSError: pass
    try:
        provisioned_pass = open('/pass.txt').read().strip()
    except OSError: pass
    try:
        provisioned_server_ip = open('/server_ip.txt').read().strip() or '108.254.1.184'
    except OSError: pass
    try:
        provisioned_server_port = open('/server_port.txt').read().strip() or '9019'
    except OSError: pass

    if provisioned_ssid and provisioned_pass:
        print('Saved credentials found - connecting directly')
        if await connect_wifi(provisioned_ssid, provisioned_pass):
            await run_secondary()
            return

    await advertise_and_provision()

asyncio.run(main())
