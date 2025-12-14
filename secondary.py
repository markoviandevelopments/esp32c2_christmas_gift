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
            # Server URL from provisioned files (same as download URL but different endpoint)
            # Assumes you provisioned the same IP but port 9020 for tracking
            url = "http://{}:{}/ping".format(
                open('/server_ip.txt', 'r').read().strip(),
                open('/server_port.txt', 'r').read().strip() or '9020'  # fallback if not provisioned
            )

            response = urequests.post(
                url,
                data=ujson.dumps(data),
                headers={'Content-Type': 'application/json'}
            )
            response.close()
            print("[{}] Ping successful - reported IP: {}, Uptime: {}s".format(
                time.ticks_ms() // 1000, local_ip, uptime_sec))
        except Exception as e:
            print("[{}] Ping failed: {}".format(time.ticks_ms() // 1000, e))
    else:
        print("Not connected to WiFi - skipping ping")

    time.sleep(PING_INTERVAL)
