# tracking_server.py - Flask server to track ESP32-C2 chips
# Run with: python3 tracking_server.py
# Access at http://<your-public-ip>:9020/ (port forward 9020 if needed)

from flask import Flask, jsonify, request, render_template_string
from datetime import datetime
import threading
import time

app = Flask(__name__)

# In-memory storage: mac -> dict with ip, uptime, last_seen (timestamp)
devices = {}
lock = threading.Lock()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ESP32-C2 Chip Tracker</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
        h1 { color: #333; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #4CAF50; color: white; }
        tr:hover { background-color: #f5f5f5; }
        .timestamp { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>ESP32-C2 Chips - Live Status</h1>
    <p>Last updated: <span class="timestamp">{{ now }}</span> (auto-refreshes every 10s)</p>
    {% if devices %}
    <table>
        <tr>
            <th>MAC Address</th>
            <th>IP Address</th>
            <th>Uptime (seconds)</th>
            <th>Last Seen</th>
        </tr>
        {% for mac in devices|list|sort(reverse=True, attribute='last_seen') %}
        <tr>
            <td>{{ mac }}</td>
            <td>{{ devices[mac].ip }}</td>
            <td>{{ devices[mac].uptime }}</td>
            <td class="timestamp">{{ devices[mac].last_seen_str }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No chips have checked in yet.</p>
    {% endif %}
</body>
</html>
'''

@app.route('/')
def index():
    with lock:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Prepare copy with string timestamps for template
        display_devices = {}
        for mac, info in devices.items():
            info_copy = info.copy()
            info_copy['last_seen_str'] = datetime.fromtimestamp(info['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
            display_devices[mac] = info_copy
        return render_template_string(HTML_TEMPLATE, devices=display_devices, now=now)

@app.route('/ping', methods=['POST'])
def ping():
    try:
        data = request.json
        mac = data['mac']
        ip = data['ip']
        uptime = data['uptime']

        with lock:
            devices[mac] = {
                'ip': ip,
                'uptime': uptime,
                'last_seen': time.time()
            }
        print(f"[{datetime.now()}] Ping from {mac} - IP: {ip}, Uptime: {uptime}s")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("Bad ping:", e)
        return jsonify({'status': 'error'}), 400

if __name__ == '__main__':
    print("ESP32-C2 Tracking Server starting on http://0.0.0.0:9020")
    print("Open in browser (forward port 9020 if accessing publicly)")
    app.run(host='0.0.0.0', port=9020, debug=False)
