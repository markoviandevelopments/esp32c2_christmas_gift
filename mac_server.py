import socket

HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 9022       # Port to listen on

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server listening on port {PORT}...")
    
    while True:
        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            data = conn.recv(1024)  # Receive up to 1024 bytes (MAC is small)
            if data:
                mac_received = data.decode()
                print(f"Received MAC: {mac_received}")
            else:
                print("No data received")
