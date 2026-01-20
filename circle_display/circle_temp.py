from flask import Flask, abort, Response, request
import os
import random
from PIL import Image
import threading
import time
import socket

app = Flask(__name__)

# === CONFIGURATION ===
BASE_DIR = '/home/preston/Desktop/circle_displays'

PHOTO_DIRS = {
    "disp1": os.path.join(BASE_DIR, 'photos', 'circle_display_1'),  # Melanie
    "disp2": os.path.join(BASE_DIR, 'photos', 'circle_display_2'),  # Pattie
    "disp3": os.path.join(BASE_DIR, 'photos', 'circle_display_3'),  # Robbins
    "disp4": os.path.join(BASE_DIR, 'photos', 'circle_display_4'),  # Home/Default
}

TARGET_SIZE = 240
RESAMPLE_FILTER = Image.LANCZOS
CHUNK_PIXELS = 256
PIXELS_TOTAL = TARGET_SIZE * TARGET_SIZE
BYTES_PER_PIXEL = 2
CHUNK_SIZE = CHUNK_PIXELS * BYTES_PER_PIXEL

# Thread-safe mapping: client IP → which photo directory to use
client_mac_lock = threading.Lock()
client_ip_to_dirkey = {}  # ip → "disp1" / "disp2" / "disp3" / "disp4"

# Per-client current photo (ip → {'path': str, 'last_access': float})
client_current_photo = {}


def get_image_files(directory):
    supported = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
    try:
        return [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
            and os.path.splitext(f.lower())[1] in supported
        ]
    except Exception:
        return []


def image_to_rgb565_bytes(image_path):
    """Convert image → 240×240 centered RGB565 raw bytes (on the fly)"""
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')

            img.thumbnail((TARGET_SIZE, TARGET_SIZE), RESAMPLE_FILTER)

            background = Image.new('RGB', (TARGET_SIZE, TARGET_SIZE), (0, 0, 0))
            offset = ((TARGET_SIZE - img.size[0]) // 2, (TARGET_SIZE - img.size[1]) // 2)
            background.paste(img, offset)

            pixels = background.load()
            raw = bytearray()

            for y in range(TARGET_SIZE):
                for x in range(TARGET_SIZE):
                    r, g, b = pixels[x, y]
                    # RGB565: 5 red, 6 green, 5 blue
                    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    raw.extend([rgb565 >> 8, rgb565 & 0xFF])

            return bytes(raw)
    except Exception as e:
        print(f"Failed to process {image_path}: {e}")
        return None


@app.route('/')
def index():
    counts = {}
    for key, path in PHOTO_DIRS.items():
        files = get_image_files(path)
        counts[key] = len(files)

    return f"""
    <h2>GC9A01 RGB565 Photo Server (No Cache)</h2>
    <p>Serving 240×240 images, RGB565, converted on-the-fly</p>
    <ul>
        <li>Display 1 (Melanie): {counts.get('disp1', 0)} photos</li>
        <li>Display 2 (Pattie):  {counts.get('disp2', 0)} photos</li>
        <li>Display 3 (Robbins): {counts.get('disp3', 0)} photos</li>
        <li>Display 4 (Home):    {counts.get('disp4', 0)} photos</li>
    </ul>
    <p>Use: <code>/pixel?n=0</code> ... <code>/pixel?n={PIXELS_TOTAL//CHUNK_PIXELS - 1}</code></p>
    """


@app.route('/pixel')
def serve_pixel_chunk():
    n_str = request.args.get('n')
    if n_str is None:
        abort(400, "Missing 'n' parameter")

    try:
        n = int(n_str)
    except ValueError:
        abort(400, "Invalid n")

    max_chunk = (PIXELS_TOTAL // CHUNK_PIXELS) - 1
    if n < 0 or n > max_chunk:
        abort(400, f"n out of range (0-{max_chunk})")

    client_ip = request.remote_addr

    # Decide which photo folder this client should use
    with client_mac_lock:
        dir_key = client_ip_to_dirkey.get(client_ip, "disp4")  # default = home

    photo_dir = PHOTO_DIRS.get(dir_key)
    if not photo_dir:
        abort(500, "Invalid display configuration")

    image_files = get_image_files(photo_dir)
    if not image_files:
        abort(503, f"No photos found in {dir_key}")

    # Choose new photo only on first chunk (n==0)
    if n == 0:
        chosen_path = random.choice(image_files)
        client_current_photo[client_ip] = {
            'raw_bytes': image_to_rgb565_bytes(chosen_path),
            'last_access': time.time(),
            'path': chosen_path  # just for logging
        }

        short_name = os.path.basename(chosen_path)
        print(f"[{client_ip}] → {dir_key} : {short_name}")

    client_data = client_current_photo.get(client_ip)
    if not client_data or client_data.get('raw_bytes') is None:
        abort(500, "Start with n=0 or image conversion failed")

    client_data['last_access'] = time.time()
    raw_bytes = client_data['raw_bytes']

    start = n * CHUNK_SIZE
    chunk = raw_bytes[start : start + CHUNK_SIZE]

    if not chunk:
        abort(500, "Chunk read error")

    return Response(chunk, mimetype='application/octet-stream')


def mac_listener():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 9022))
    server.listen(5)
    print("MAC registration listener started on port 9022")

    mac_to_key = {
        "34:98:7A:07:11:7C": "disp1",   # Melanie
        "34:98:7A:06:FD:74": "disp2",   # Pattie
        "34:98:7A:07:13:40": "disp3",   # Robbins
        "34:98:7A:07:09:68": "disp4",   # Home
    }

    while True:
        try:
            conn, addr = server.accept()
            client_ip = addr[0]
            data = conn.recv(32).decode('utf-8', errors='ignore').strip().upper()
            if data and len(data) >= 17:
                mac = data[:17]  # take first 17 chars (XX:XX:XX:XX:XX:XX)
                dir_key = mac_to_key.get(mac)
                if dir_key:
                    with client_mac_lock:
                        client_ip_to_dirkey[client_ip] = dir_key
                    print(f"Registered {client_ip} → {dir_key} (MAC: {mac})")
                else:
                    print(f"Unknown MAC from {client_ip}: {mac}")
            conn.close()
        except Exception as e:
            print(f"MAC listener error: {e}")


def cleanup_old_clients():
    while True:
        now = time.time()
        to_remove = [
            ip for ip, data in list(client_current_photo.items())
            if now - data.get('last_access', 0) > 600  # 10 minutes
        ]
        for ip in to_remove:
            client_current_photo.pop(ip, None)
            with client_mac_lock:
                client_ip_to_dirkey.pop(ip, None)
        time.sleep(30)


if __name__ == '__main__':
    threading.Thread(target=mac_listener, daemon=True).start()
    threading.Thread(target=cleanup_old_clients, daemon=True).start()

    print("Starting GC9A01 photo server (no cache, on-the-fly RGB565 conversion)...")
    app.run(host='0.0.0.0', port=9025, debug=False)