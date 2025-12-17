# secondary.py - Minimal tracking ping for ESP32-C2 (low RAM)
import network
import urequests
import time
import machine
import ubinascii

# Get STA interface
sta = network.WLAN(network.STA_IF)

# MAC as hex string
mac = ubinascii.hexlify(sta.config('mac'), ':').decode().upper()

# Read server from files (set by boot.py)
try:
    server_ip = open('/server_ip.txt').read().strip()
    server_port = open('/server_port.txt').read().strip()
except:
    server_ip = '108.254.1.184'  # Fallback
    server_port = '9019'

url = f'http://{server_ip}:{server_port}/ping'

while True:
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        uptime = time.ticks_ms() // 1000
        # Manual tiny JSON string (saves RAM vs ujson)
        payload = '{"mac":"' + mac + '","ip":"' + ip + '","uptime":' + str(uptime) + '}'
        try:
            urequests.post(url, data=payload, headers={'Content-Type': 'application/json'})
        except:
            pass  # Silent fail - keeps RAM low
    time.sleep(300)  # 5 minutes
