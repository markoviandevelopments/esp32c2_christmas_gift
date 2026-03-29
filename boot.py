# boot.py - FINAL working version (http only, no port, debug prints only where needed)
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
gc.collect()

connected = False
provisioned_ssid = None
provisioned_pass = None
provisioned_server_ip = 'ghostshrimp.immenseaccumulationonline.online'
provisioned_server_port = '9019'

ssid_handle = pass_handle = server_ip_handle = server_port_handle = None

def ble_irq(event, data):
    global connected, provisioned_ssid, provisioned_pass, provisioned_server_ip, provisioned_server_port
    if event == _IRQ_CENTRAL_CONNECT:
        connected = True
    elif event == _IRQ_CENTRAL_DISCONNECT:
        connected = False
    elif event == _IRQ_GATTS_WRITE:
        conn_handle, value_handle = data
        try:
            value = ble.gatts_read(value_handle)
            decoded = value.decode('utf-8').rstrip('\x00')
            if value_handle == ssid_handle:
                provisioned_ssid = decoded
                with open('/ssid.txt', 'w') as f: f.write(decoded)
            elif value_handle == pass_handle:
                provisioned_pass = decoded
                with open('/pass.txt', 'w') as f: f.write(decoded)
            elif value_handle == server_ip_handle:
                provisioned_server_ip = decoded
                with open('/server_ip.txt', 'w') as f: f.write(decoded)
            elif value_handle == server_port_handle:
                provisioned_server_port = decoded
                with open('/server_port.txt', 'w') as f: f.write(decoded)
        except:
            pass

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

register_services()
gc.collect()

async def connect_wifi(ssid, password):
    sta = network.WLAN(network.STA_IF)
    if sta.isconnected():
        return True
    sta.active(True)
    sta.connect(ssid, password)
    for _ in range(30):
        if sta.isconnected():
            return True
        await asyncio.sleep(1)
    return False

async def download_secondary():
    url = f'http://{provisioned_server_ip}/secondary.mpy'  # http only, no port
    print(f'Downloading from {url}')  # ← debug
    for attempt in range(8):  # more retries than before
        try:
            resp = urequests.get(url, timeout=20)  # longer timeout
            if resp.status_code == 200:
                with open('/secondary.mpy', 'wb') as f:
                    f.write(resp.content)
                print('Downloaded secondary.mpy successfully')
                return True
        except Exception as e:
            print(f'Download attempt {attempt+1} failed: {e}')
        await asyncio.sleep(5)
    print('Download failed after all retries')
    return False

async def run_secondary():
    if await download_secondary():
        gc.collect()
        try:
            import secondary
            print('secondary.mpy running')
        except Exception as e:
            import sys
            sys.print_exception(e)

async def advertise_and_provision():
    global connected
    name = b'XH-C2X'
    name_ad = bytes([len(name) + 1, 0x09]) + name
    adv_data = bytearray([0x02, 0x01, 0x06]) + name_ad + bytes([0x11, 0x07]) + bytes.fromhex('bc9a7856341234123412341278563412')
    resp_data = bytearray(name_ad)

    while True:
        ble.gap_advertise(100_000, adv_data=adv_data, resp_data=resp_data, connectable=True)
        while not connected:
            await asyncio.sleep_ms(100)

        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 30000:
            if provisioned_ssid and provisioned_pass:
                ble.gap_advertise(None)
                if await connect_wifi(provisioned_ssid, provisioned_pass):
                    await run_secondary()
                return
            await asyncio.sleep_ms(100)
        ble.gap_advertise(None)
        while connected:
            await asyncio.sleep_ms(100)

async def main():
    gc.collect()
    try:
        provisioned_ssid = open('/ssid.txt').read().strip()
    except OSError: pass
    try:
        provisioned_pass = open('/pass.txt').read().strip()
    except OSError: pass
    try:
        provisioned_server_ip = open('/server_ip.txt').read().strip() or 'ghostshrimp.immenseaccumulationonline.online'
    except OSError: pass

    if provisioned_ssid and provisioned_pass:
        if await connect_wifi(provisioned_ssid, provisioned_pass):
            await run_secondary()
            return
    await advertise_and_provision()

asyncio.run(main())
