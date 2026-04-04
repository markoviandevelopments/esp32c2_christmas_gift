import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = ''  # Listen on all interfaces
PORT = 9022

# Known MAC addresses and friendly names (exactly the same as before)
KNOWN_DEVICES = {
    '34:98:7A:07:13:B4': "Sydney's device",
    '34:98:7A:07:14:D0': "Alyssa's device",
    '34:98:7A:06:FC:A0': "Patrick's device",
    '34:98:7A:06:FB:D0': "Braden's device",
    '34:98:7A:07:11:24': "Pattie's device",
    '34:98:7A:07:12:B8': "Test's device",
    '34:98:7A:07:06:B4': "Chris's device",
    '34:98:7A:07:11:7C': "Second Circle Screen", 
    '34:98:7A:06:FD:74': "First Circle Screen", 
    '34:98:7A:07:13:40': "Third Circle Screen", 
    '34:98:7A:07:09:68': "Fourth Circle Screen", 
}

LOG_FILE = "mac_connection_logs.txt"

class MACHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/mac':
            content_length = int(self.headers.get('Content-Length', 0))
            mac = self.rfile.read(content_length).decode('utf-8').strip().upper()

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            friendly_name = KNOWN_DEVICES.get(mac, "Unknown device")
            client_ip = self.client_address[0]

            print(f"Received MAC: {mac} → {friendly_name} connected!")

            # Log line (exactly the same format as before)
            log_line = f"{timestamp} | {client_ip} | {mac} | {friendly_name}\n"
            with open(LOG_FILE, "a") as logf:
                logf.write(log_line)
                logf.flush()

            # Tell the ESP32 it was accepted
            self.send_response(200)
            self.end_headers()
            return

        # Any other path
        self.send_response(404)
        self.end_headers()

    # Silence the default logging spam
    def log_message(self, format, *args):
        return

print(f"HTTP MAC server listening on port {PORT}...")
httpd = HTTPServer((HOST, PORT), MACHandler)
httpd.serve_forever()
