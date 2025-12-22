# tracking_server.py - Rich ESP32-C2 tracker with RAM, coin, price
from flask import Flask, jsonify, request, render_template_string
from datetime import datetime
import threading
import time

app = Flask(__name__)

devices = {}
lock = threading.Lock()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ESP32-C2 Crypto Gifts - Live Tracker</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #1e1e1e; color: #eee; }
        h1 { color: #4CAF50; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
        th { background-color: #333; }
        tr:hover { background-color: #2a2a2a; }
        .timestamp { color: #aaa; font-size: 0.9em; }
        .ram-low { color: #ff6b6b; }
        .ram-ok { color: #51cf66; }
    </style>
</head>
<body>
    <h1>ESP32-C2 Crypto Gifts - Live Status</h1>
    <p>Last updated: <span class="timestamp">{{ now }}</span> (refresh 10s)</p>
    {% if devices %}
    <table>
        <tr>
            <th>MAC Address</th>
            <th>IP</th>
            <th>Uptime</th>
            <th>Coin</th>
            <th>Price</th>
            <th>Value</th>
            <th>Free RAM</th>
            <th>Total RAM</th>
            <th>Last Seen</th>
        </tr>
        {% for mac in devices|list|sort(reverse=True, attribute='last_seen') %}
        <tr>
            <td>{{ mac }}</td>
            <td>{{ devices[mac].ip }}</td>
            <td>{{ devices[mac].uptime }}s</td>
            <td>{{ devices[mac].coin }}</td>
            <td>{{ devices[mac].price }}</td>
            <td>{{ devices[mac].value }}</td>
            <td class="{{ 'ram-low' if devices[mac].free_ram < 30000 else 'ram-ok' }}">{{ devices[mac].free_ram }}</td>
            <td>{{ devices[mac].total_ram }}</td>
            <td class="timestamp">{{ devices[mac].last_seen_str }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No gifts online yet.</p>
    {% endif %}
</body>
</html>
'''

@app.route('/')
def index():
    with lock:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        display_devices = {}
        for mac, info in devices.items():
            i = info.copy()
            i['last_seen_str'] = datetime.fromtimestamp(i['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
            display_devices[mac] = i
        return render_template_string(HTML_TEMPLATE, devices=display_devices, now=now)

@app.route('/ping', methods=['POST'])
def ping():
    try:
        data = request.json
        mac = data['mac']
        with lock:
            devices[mac] = {
                'ip': data.get('ip', 'unknown'),
                'uptime': data.get('uptime', 0),
                'coin': data.get('coin', 'unknown'),
                'price': data.get('price', '---'),
                'value': data.get('value', '---'),
                'free_ram': data.get('free_ram', 0),
                'alloc_ram': data.get('alloc_ram', 0),
                'total_ram': data.get('total_ram', 0),
                'last_seen': time.time()
            }
        print(f"[{datetime.now()}] Rich ping from {mac}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("Bad ping:", e)
        return jsonify({'status': 'error'}), 400

if __name__ == '__main__':
    print("Rich tracking server starting on http://0.0.0.0:9020")
    app.run(host='0.0.0.0', port=9020, debug=False)
