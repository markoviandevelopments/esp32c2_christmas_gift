# mac_server.py - Logs MAC connections and identifies known devices
import socket
import datetime

HOST = ''  # Listen on all interfaces
PORT = 9022
LOG_FILE = "mac_connection_logs.txt"

# Known MAC addresses and friendly names (add/remove as needed)
KNOWN_DEVICES = {
    '34:98:7A:07:13:B4': "Sydney's device",
    '34:98:7A:07:14:D0': "Alyssa's device",
    '34:98:7A:06:FC:A0': "Patrick's device",
    '34:98:7A:06:FB:D0': "Braden's device",
    '34:98:7A:07:11:24': "Pattie's device",
    '34:98:7A:07:12:B8': "Test's device",
    '34:98:7A:07:06:B4': "Chris's device",
    '34:98:7A:07:11:7C': "Second Circle Screen", # Melanie's circle screen
    '34:98:7A:06:FD:74': "First Circle Screen", # Pattie's circle screen
    '34:98:7A:07:13:40': "Third Circle Screen", # Robbins' circle screen
    '34:98:7A:07:09:68': "Fourth Circle Screen", # Preston and Willoh's circle screen
}

print(f"Server listening on port {PORT}...")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()

    with open(LOG_FILE, "a") as logf:  # Append mode
        while True:
            conn, addr = s.accept()
            with conn:
                client_ip = addr[0]
                client_port = addr[1]
                print(f"Connected by {client_ip}:{client_port}")

                data = conn.recv(1024)
                if not data:
                    print("No data received - closing connection")
                    continue

                mac = data.decode('utf-8').strip().upper()
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Identify if known
                friendly_name = KNOWN_DEVICES.get(mac, "Unknown device")
                print(f"Received MAC: {mac} → {friendly_name} connected!")

                # Log line
                log_line = f"{timestamp} | {client_ip}:{client_port} | {mac} | {friendly_name}\n"
                logf.write(log_line)
                logf.flush()  # Ensure immediate write to disk
