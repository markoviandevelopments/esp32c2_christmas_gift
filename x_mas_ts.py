# simple_tracking_server.py - Minimal live tracker (static HTML)
from flask import Flask, request
from datetime import datetime
import time

app = Flask(__name__)

devices = {}  # Same in-memory storage: mac -> dict of info

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Crypto Gifts Live Tracker</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: sans-serif; background: #111; color: #eee; margin: 20px; }
        h1 { color: #0f0; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; border: 1px solid #444; text-align: left; }
        th { background: #222; }
    </style>
</head>
<body>
    <h1>Crypto Gifts - Live Status</h1>
    <p>Last refresh: <span id="time"></span></p>
    <script>document.getElementById('time').innerText = new Date().toLocaleString();</script>
    {%DEVICES%}
    {% if not devices %}
    <p>No devices online yet.</p>
    {% endif %}
</body>
</html>
"""

def generate_table():
    if not devices:
        return ""
    sorted_devices = sorted(devices.items(), key=lambda x: x[1]['last_seen'], reverse=True)
    rows = ""
    for mac, info in sorted_devices:
        rows += f"<tr><td>{mac}</td><td>{info.get('ip', 'unknown')}</td><td>{info.get('uptime', 0)}s</td>"
        rows += f"<td>{info.get('coin', 'unknown')}</td><td>{info.get('price', '---')}</td><td>{info.get('value', '---')}</td>"
        rows += f"<td style='color: {'red' if info.get('free_ram', 0) < 30000 else 'lime'}'>{info.get('free_ram', 0)}</td>"
        rows += f"<td>{info.get('total_ram', 0)}</td>"
        rows += f"<td>{datetime.fromtimestamp(info['last_seen']).strftime('%H:%M:%S')}</td></tr>"
    return "<table><tr><th>MAC</th><th>IP</th><th>Uptime</th><th>Coin</th><th>Price</th><th>Value</th><th>Free RAM</th><th>Total RAM</th><th>Last Seen</th></tr>" + rows + "</table>"

@app.route('/')
def index():
    table = generate_table()
    page = HTML_PAGE.replace("{%DEVICES%}", table)
    if "{% if not devices %}" in page and not devices:
        page = page.replace("{% if not devices %}", "<p>No devices online yet.</p>").replace("{% endif %}", "")
    return page

@app.route('/ping', methods=['POST'])
def ping():
    try:
        data = request.get_json(force=True)  # Force JSON parse even if header missing
        if not data or 'mac' not in data:
            raise ValueError("No mac in payload")
        mac = data['mac']
        devices[mac] = {
            'ip': data.get('ip', 'unknown'),
            'uptime': data.get('uptime', 0),
            'coin': data.get('coin', 'unknown'),
            'price': data.get('price', '---'),
            'value': data.get('value', '---'),
            'free_ram': data.get('free_ram', 0),
            'total_ram': data.get('total_ram', 0),
            'last_seen': time.time()
        }
        print(f"[{datetime.now()}] Ping OK from {mac}")
        return "OK", 200
    except Exception as e:
        print(f"Bad ping: {e} | Data: {request.data}")
        return "ERROR", 400

if __name__ == '__main__':
    print("Simple tracking server starting on http://0.0.0.0:9020")
    app.run(host='0.0.0.0', port=9020)
