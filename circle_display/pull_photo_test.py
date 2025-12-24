import requests

# Change this to your desktop's IP if different (e.g., what you see in ifconfig)
SERVER_IP = '192.168.1.198'  # From your earlier log
URL = f'http://{SERVER_IP}:9025/image.raw'

try:
    print("Fetching from:", URL)
    r = requests.get(URL, timeout=10)
    print("Status code:", r.status_code)
    print("Content length:", len(r.content), "bytes")
    
    if r.status_code == 200 and len(r.content) == 115200:
        print("SUCCESS: Valid RGB565 image data received!")
        print("First 20 bytes (hex):", r.content[:20].hex())  # Sample to confirm it's pixel data
    else:
        print("FAIL: Bad response or wrong size")
        if r.status_code != 200:
            print("HTTP error - server might not be reachable or returned error")
except Exception as e:
    print("Request failed:", e)
    print("Common causes: server not running, wrong IP/port, firewall blocking")
