# secondary.py - ESP32-C2 Chip Tracking Ping Client
# Periodically reports MAC, IP, and uptime to your desktop server.
# Prints status to console on successful ping.

import network
import urequests
import ujson
import ubinascii
import time
import machine

# Get WiFi interface
sta_if = network.WLAN(network.STA_IF)

# Get MAC address (as colon-separated hex string, uppercase)
mac_bytes = sta_if.config('mac')
mac = ubinascii.hexlify(mac_bytes, ':').decode().upper()

print("secondary.py loaded. MAC: {}".format(mac))
print("Starting tracking ping loop (every 5 minutes)...")

PING_INTERVAL = 300  # 5 minutes in seconds

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
            server_ip = open('/server_ip.txt', 'r').read().strip()
            server_port = '9020'  # Force tracking port
            url = f"http://{server_ip}:{server_port}/ping"

            response = urequests.post(
                url,
                data=ujson.dumps(data),
                headers={'Content-Type': 'application/json'}
            )
            # Optional: check response.status_code == 200 for stricter success
            print("[{}] Ping successful - reported IP: {}, Uptime: {}s (status: {})".format(
                time.ticks_ms() // 1000, local_ip, uptime_sec, response.status_code))
            response.close()
        except Exception as e:
            print("[{}] Ping failed: {}".format(time.ticks_ms() // 1000, e))
    else:
        print("Not connected to WiFi - skipping ping")

    time.sleep(PING_INTERVAL)
