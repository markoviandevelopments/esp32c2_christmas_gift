import socket
import datetime

HOST = ''  # Listen on all interfaces
PORT = 9022
LOG_FILE = "mac_connection_logs.txt"

print(f"Server listening on port {PORT}...")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()

    with open(LOG_FILE, "a") as logf:  # Append mode
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                data = conn.recv(1024)
                if not data:
                    continue
                mac = data.decode('utf-8').strip().upper()
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_line = f"{timestamp} | {addr[0]}:{addr[1]} | {mac}\n"
                print(f"Received MAC: {mac}")
                logf.write(log_line)
                logf.flush()  # Ensure immediate write to disk
