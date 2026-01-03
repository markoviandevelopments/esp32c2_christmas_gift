from flask import Flask, render_template_string
import threading
import time
import os
from datetime import datetime
import re

app = Flask(__name__)

# Hard-coded MAC to name/coin mapping (add/update as needed)
MAC_INFO = {
    '34:98:7A:07:13:B4': {"name": "Sydney's", "coin": "XRP"},
    '34:98:7A:07:14:D0': {"name": "Alyssa's", "coin": "SOL"},
    '34:98:7A:06:FC:A0': {"name": "Patrick's", "coin": "DOGE"},
    '34:98:7A:06:FB:D0': {"name": "Braden's", "coin": "PEPE"},
    '34:98:7A:07:11:24': {"name": "Pattie's", "coin": "LTC"},
    '34:98:7A:07:12:B8': {"name": "Test's", "coin": "DOGE (test)"},
    '34:98:7A:07:06:B4': {"name": "Chris's", "coin": "BTC"},
    # Add more if new devices appear
}

LOG_FILE = "/home/preston/.pm2/logs/mac-server-out.log"

# Global dict to hold last seen datetime for each MAC
last_seen = {mac: None for mac in MAC_INFO}

lock = threading.Lock()

def parse_log():
    global last_seen
    temp_seen = {mac: None for mac in MAC_INFO}
    
    if not os.path.exists(LOG_FILE):
        print(f"[{datetime.now()}] Log file not found: {LOG_FILE}")
        return
    
    try:
        with open(LOG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # PM2 log lines typically start with "YYYY-MM-DD HH:MM:SS: message"
                # Extract timestamp if present
                timestamp = None
                match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}):', line)
                if match:
                    ts_str = match.group(1)
                    try:
                        timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        timestamp = None
                    message = line[match.end():].strip()
                else:
                    message = line
                
                if "Received MAC:" in message:
                    parts = message.split("Received MAC:")
                    if len(parts) > 1:
                        mac = parts[1].strip().upper()
                        if mac in temp_seen:
                            # Use the latest (last in file) timestamp
                            if timestamp:
                                temp_seen[mac] = timestamp
                            else:
                                # Fallback to now if no timestamp
                                temp_seen[mac] = datetime.now()
        
        with lock:
            last_seen.update(temp_seen)
        print(f"[{datetime.now()}] Log parsed - updated last seen times")
    
    except Exception as e:
        print(f"[{datetime.now()}] Error parsing log: {e}")

def background_refresh():
    while True:
        parse_log()
        time.sleep(300)  # Every 5 minutes

# HTML template for the website
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Device Last Restart Times</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
        h1 { text-align: center; }
        table { width: 80%; margin: 0 auto; border-collapse: collapse; background: white; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #4CAF50; color: white; }
        tr:hover { background: #f5f5f5; }
        .never { color: red; }
        .recent { color: green; }
    </style>
</head>
<body>
    <h1>Device Last Restart Times</h1>
    <p style="text-align:center;">Data refreshed every 5 minutes from mac-server logs. Times in server local timezone.</p>
    <table>
        <tr>
            <th>Name</th>
            <th>Coin</th>
            <th>MAC Address</th>
            <th>Last Restart</th>
        </tr>
        {% for mac in macs %}
        <tr>
            <td>{{ info[mac]['name'] }}</td>
            <td>{{ info[mac]['coin'] }}</td>
            <td>{{ mac }}</td>
            <td>
                {% if last_seen[mac] %}
                    <span class="recent">{{ last_seen[mac].strftime("%Y-%m-%d %H:%M:%S") }}</span>
                    <br><small>({{ timesince(last_seen[mac]) }} ago)</small>
                {% else %}
                    <span class="never">Never seen</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
    <p style="text-align:center; margin-top:40px; color:#666;">
        Last log parse: {{ now.strftime("%Y-%m-%d %H:%M:%S") }}
    </p>
</body>
</html>
"""

def timesince(dt):
    if not dt:
        return "unknown"
    delta = datetime.now() - dt
    if delta.days > 0:
        return f"{delta.days} days"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours} hours"
    minutes = delta.seconds // 60
    if minutes > 0:
        return f"{minutes} minutes"
    return "just now"

@app.route('/')
def index():
    with lock:
        sorted_macs = sorted(MAC_INFO.keys())
        return render_template_string(
            TEMPLATE,
            macs=sorted_macs,
            info=MAC_INFO,
            last_seen=last_seen,
            timesince=timesince,
            now=datetime.now()
        )

if __name__ == '__main__':
    # Initial parse
    parse_log()
    
    # Start background refresh thread
    threading.Thread(target=background_refresh, daemon=True).start()
    
    print("Website starting on http://0.0.0.0:9024")
    print("Open in browser: http://your-server-ip:9024")
    app.run(host='0.0.0.0', port=9024)
