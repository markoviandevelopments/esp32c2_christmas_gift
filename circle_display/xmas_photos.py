from flask import Flask, send_file, abort, Response, request
import os
import random
from PIL import Image
import threading
import time
import socket

app = Flask(__name__)

# === CONFIGURATION ===
BASE_DIR = '/home/preston/Desktop/x_mas_gift/circle_display'
PHOTOS_DIR_1 = os.path.join(BASE_DIR, 'photos', 'circle_display_1')
PHOTOS_DIR_2 = os.path.join(BASE_DIR, 'photos', 'circle_display_2')
CACHE_DIR = os.path.join(BASE_DIR, '.cache_photos')
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR_1, exist_ok=True)
os.makedirs(PHOTOS_DIR_2, exist_ok=True)

TARGET_SIZE = 240
RESAMPLE_FILTER = Image.LANCZOS

CHUNK_PIXELS = 256
PIXELS_TOTAL = TARGET_SIZE * TARGET_SIZE

# Global caches for each display
cached_paths_1 = []
cached_paths_2 = []

# Current photo per client (ip: {'path': str, 'last_access': time})
client_photos = {}

# MAC → directory mapping (thread-safe)
client_mac_map = threading.Lock()
client_mac_to_dir = {}  # mac_str → PHOTOS_DIR_X

def get_image_files(directory):
    supported = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.ico'}
    return [os.path.join(directory, f) for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f)) and os.path.splitext(f.lower())[1] in supported]

def convert_to_rgb565(image_path, directory_label):
    base_name = os.path.basename(image_path)
    cache_path = os.path.join(CACHE_DIR, f"{directory_label}_{base_name}.{TARGET_SIZE}x{TARGET_SIZE}.raw")
    
    if os.path.exists(cache_path):
        if os.path.getmtime(image_path) <= os.path.getmtime(cache_path):
            return cache_path
    
    print(f"Processing {base_name} ({directory_label}) → {TARGET_SIZE}x{TARGET_SIZE} RGB565...")
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((TARGET_SIZE, TARGET_SIZE), RESAMPLE_FILTER)
            background = Image.new('RGB', (TARGET_SIZE, TARGET_SIZE), (0, 0, 0))
            offset = ((TARGET_SIZE - img.size[0]) // 2, (TARGET_SIZE - img.size[1]) // 2)
            background.paste(img, offset)
            img = background
            
            pixels = img.load()
            raw_bytes = bytearray()
            for y in range(TARGET_SIZE):
                for x in range(TARGET_SIZE):
                    r, g, b = pixels[x, y]
                    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    raw_bytes += bytes([rgb565 >> 8, rgb565 & 0xFF])
            
            with open(cache_path, 'wb') as f:
                f.write(raw_bytes)
            return cache_path
    except Exception as e:
        print(f"Failed to process {image_path}: {e}")
        raise

def preload_all_images():
    global cached_paths_1, cached_paths_2
    images_1 = get_image_files(PHOTOS_DIR_1)
    images_2 = get_image_files(PHOTOS_DIR_2)
    
    cached_paths_1 = [convert_to_rgb565(p, "disp1") for p in images_1]
    cached_paths_2 = [convert_to_rgb565(p, "disp2") for p in images_2]
    
    print(f"Preloaded: {len(cached_paths_1)} from display_1, {len(cached_paths_2)} from display_2")

preload_all_images()

@app.route('/')
def index():
    return f"""
    <h2>GC9A01 Photo Server Ready</h2>
    <p>Serving {TARGET_SIZE}x{TARGET_SIZE} RGB565 images</p>
    <p>Display 1: {len(cached_paths_1)} photos | Display 2: {len(cached_paths_2)} photos</p>
    <p>Use: /pixel?n=0 to /pixel?n={PIXELS_TOTAL//CHUNK_PIXELS - 1}</p>
    """

@app.route('/pixel')
def serve_pixel_chunk():
    if not cached_paths_1 and not cached_paths_2:
        preload_all_images()
    
    n_str = request.args.get('n')
    if n_str is None:
        abort(400, "Missing 'n' parameter")
    try:
        n = int(n_str)
    except ValueError:
        abort(400, "Invalid 'n'")
    
    max_chunk = PIXELS_TOTAL // CHUNK_PIXELS - 1
    if n < 0 or n > max_chunk:
        abort(400, f"n out of range (0-{max_chunk})")
    
    client_ip = request.remote_addr
    
    # Determine which photo set this client should use
    with client_mac_map:
        photos_dir = client_mac_to_dir.get(client_ip)
    
    if photos_dir is None:
        # Default to display_2 if we never heard from this client
        cached_paths = cached_paths_2
    elif photos_dir == PHOTOS_DIR_1:
        cached_paths = cached_paths_1
    else:
        cached_paths = cached_paths_2
    
    if not cached_paths:
        abort(503, "No photos available for this client")
    
    if n == 0:
        chosen_path = random.choice(cached_paths)
        client_photos[client_ip] = {
            'path': chosen_path,
            'last_access': time.time()
        }
        print(f"New pull from {client_ip} - serving {'display_1' if photos_dir == PHOTOS_DIR_1 else 'display_2'} photo")
    
    client_data = client_photos.get(client_ip)
    if client_data is None:
        abort(500, "Start with n=0")
    
    client_data['last_access'] = time.time()
    current_raw_path = client_data['path']
    
    start_byte = n * CHUNK_PIXELS * 2
    chunk_size = CHUNK_PIXELS * 2
    
    try:
        with open(current_raw_path, 'rb') as f:
            f.seek(start_byte)
            chunk = f.read(chunk_size)
    except Exception as e:
        print(f"Read error: {e}")
        abort(500)
    
    if len(chunk) != chunk_size:
        abort(500)
    
    return Response(chunk, mimetype='application/octet-stream')

# === TCP listener for MAC registration ===
def mac_listener():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('0.0.0.0', 9022))
    server_sock.listen(5)
    print("MAC registration listener running on port 9022")
    
    while True:
        try:
            client_sock, addr = server_sock.accept()
            client_ip = addr[0]
            data = client_sock.recv(17)  # MAC is 17 chars like XX:XX:XX:XX:XX:XX
            if data:
                mac = data.decode('utf-8').strip().upper()
                print(f"Received MAC {mac} from {client_ip}")
                target_dir = PHOTOS_DIR_1 if mac == "34:98:7A:06:FD:74" else PHOTOS_DIR_2
                with client_mac_map:
                    client_mac_to_dir[client_ip] = target_dir
            client_sock.close()
        except Exception as e:
            print(f"MAC listener error: {e}")

# Background tasks
def watcher():
    known_1 = set(get_image_files(PHOTOS_DIR_1))
    known_2 = set(get_image_files(PHOTOS_DIR_2))
    while True:
        new_1 = set(get_image_files(PHOTOS_DIR_1))
        new_2 = set(get_image_files(PHOTOS_DIR_2))
        if new_1 != known_1 or new_2 != known_2:
            print("Photo folder(s) changed - reloading cache")
            preload_all_images()
            known_1, known_2 = new_1, new_2
        
        now = time.time()
        to_remove = [ip for ip, data in list(client_photos.items()) if now - data.get('last_access', 0) > 600]
        for ip in to_remove:
            del client_photos[ip]
            with client_mac_map:
                client_mac_to_dir.pop(ip, None)
        
        time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=mac_listener, daemon=True).start()
    threading.Thread(target=watcher, daemon=True).start()
    print(f"Photo server running — serving based on MAC address")
    app.run(host='0.0.0.0', port=9025, debug=False)
