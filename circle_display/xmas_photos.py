from flask import Flask, send_file, abort, Response, request
import os
import random
from PIL import Image
import threading
import time
import socket

app = Flask(__name__)

# ================= CONFIGURATION =================
BASE_DIR = '/home/preston/Desktop/x_mas_gift/circle_display'

PHOTO_DIRS = {
    'display_1': os.path.join(BASE_DIR, 'photos', 'circle_display_1'),  # Melanie
    'display_2': os.path.join(BASE_DIR, 'photos', 'circle_display_2'),  # Pattie
    'display_3': os.path.join(BASE_DIR, 'photos', 'circle_display_3'),  # Robbins
    'display_4': os.path.join(BASE_DIR, 'photos', 'circle_display_4'),  # Home/Default
}

CACHE_DIR = os.path.join(BASE_DIR, '.cache_photos')
os.makedirs(CACHE_DIR, exist_ok=True)

for d in PHOTO_DIRS.values():
    os.makedirs(d, exist_ok=True)

TARGET_SIZE = 240
RESAMPLE_FILTER = Image.LANCZOS
CHUNK_PIXELS = 256
BYTES_PER_PIXEL = 2
PIXELS_TOTAL = TARGET_SIZE * TARGET_SIZE
BYTES_TOTAL = PIXELS_TOTAL * BYTES_PER_PIXEL
CHUNKS_COUNT = PIXELS_TOTAL // CHUNK_PIXELS

# Global caches: list of ready .raw file paths for each display
cached_photos = {key: [] for key in PHOTO_DIRS}

# Current photo per client (ip → {'path': str, 'last_access': float})
client_current_photo = {}

# IP → target display key mapping (protected by lock)
mapping_lock = threading.Lock()
ip_to_display = {}  # ip → 'display_1' / 'display_2' / ...

MAC_TO_DISPLAY = {
    "34:98:7A:07:11:7C": "display_1",   # Melanie
    "34:98:7A:06:FD:74": "display_2",   # Pattie
    "34:98:7A:07:13:40": "display_3",   # Robbins
    # anything else → display_4 (Home/default)
}

# ================= HELPERS =================
def get_image_files(directory):
    supported = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.ico'}
    return [
        os.path.join(directory, f) for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and os.path.splitext(f.lower())[1] in supported
    ]


def convert_to_rgb565(image_path, display_key):
    base_name = os.path.basename(image_path)
    cache_name = f"{display_key}_{base_name}.{TARGET_SIZE}x{TARGET_SIZE}.raw"
    cache_path = os.path.join(CACHE_DIR, cache_name)

    if os.path.exists(cache_path) and os.path.getmtime(image_path) <= os.path.getmtime(cache_path):
        return cache_path

    print(f"Converting {display_key:10} : {base_name} → {TARGET_SIZE}x{TARGET_SIZE} RGB565...")

    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')

            img.thumbnail((TARGET_SIZE, TARGET_SIZE), RESAMPLE_FILTER)

            background = Image.new('RGB', (TARGET_SIZE, TARGET_SIZE), (0, 0, 0))
            offset = ((TARGET_SIZE - img.size[0]) // 2, (TARGET_SIZE - img.size[1]) // 2)
            background.paste(img, offset)

            pixels = background.load()
            raw_bytes = bytearray()

            for y in range(TARGET_SIZE):
                for x in range(TARGET_SIZE):
                    r, g, b = pixels[x, y]
                    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    raw_bytes.extend([rgb565 >> 8, rgb565 & 0xFF])

            with open(cache_path, 'wb') as f:
                f.write(raw_bytes)

            return cache_path

    except Exception as e:
        print(f"Failed to process {image_path}: {e}")
        return None


def preload_all():
    global cached_photos
    print("\n" + "="*70)
    print("STARTING PRELOAD - CURRENT WORKING DIR:", os.getcwd())
    print("BASE_DIR:", BASE_DIR)
    
    for key, directory in PHOTO_DIRS.items():
        print(f"\nProcessing display: {key}")
        print("  Expected folder:", directory)
        
        if not os.path.isdir(directory):
            print("  → FOLDER DOES NOT EXIST! Skipping.")
            continue
            
        files = get_image_files(directory)
        print(f"  Found {len(files)} image files")
        
        if not files:
            print("  → No supported images found!")
            continue
            
        print("  First few files:")
        for f in files[:3]:
            print("     ", os.path.basename(f))
            
        processed = []
        for p in files:
            result = convert_to_rgb565(p, key)
            if result:
                processed.append(result)
            else:
                print("     Failed →", os.path.basename(p))
                
        cached_photos[key] = processed
        print(f"  → Successfully cached: {len(processed)} / {len(files)}")
    
    print("\nFINAL CACHE STATUS:")
    for k, v in cached_photos.items():
        print(f"  {k:12} : {len(v)} photos")
    print("="*70 + "\n")
# ================= ROUTES =================
@app.route('/')
def index():
    counts = {k: len(v) for k, v in cached_photos.items()}
    return f"""
    <h2>GC9A01 Circle Display Photo Server</h2>
    <p>Serving {TARGET_SIZE}×{TARGET_SIZE} RGB565 images (chunks of {CHUNK_PIXELS} pixels)</p>
    <p>Photos per display:</p>
    <ul>
        <li>display_1 (Melanie) : {counts['display_1']} photos</li>
        <li>display_2 (Pattie)  : {counts['display_2']} photos</li>
        <li>display_3 (Robbins) : {counts['display_3']} photos</li>
        <li>display_4 (Home)    : {counts['display_4']} photos</li>
    </ul>
    <p>Use: <code>/pixel?n=0</code> … <code>/pixel?n={CHUNKS_COUNT-1}</code></p>
    """


@app.route('/pixel')
def serve_pixel_chunk():
    n_str = request.args.get('n')
    if n_str is None:
        abort(400, "Missing parameter 'n'")

    try:
        n = int(n_str)
    except ValueError:
        abort(400, "'n' must be integer")

    if not 0 <= n < CHUNKS_COUNT:
        abort(400, f"n must be between 0 and {CHUNKS_COUNT-1} inclusive")

    client_ip = request.remote_addr

    # Decide which photo set to use
    with mapping_lock:
        display_key = ip_to_display.get(client_ip, "display_4")  # default = home

    photos = cached_photos[display_key]

    if not photos:
        abort(503, f"No cached photos available for {display_key}")

    # Choose new random photo only on first chunk (n==0)
    if n == 0:
        chosen = random.choice(photos)
        client_current_photo[client_ip] = {
            'path': chosen,
            'last_access': time.time(),
            'display': display_key
        }
        print(f"New session {client_ip} → {display_key} : {os.path.basename(chosen)}")

    client_data = client_current_photo.get(client_ip)
    if not client_data:
        abort(400, "Must start with n=0")

    client_data['last_access'] = time.time()
    current_path = client_data['path']

    start = n * CHUNK_PIXELS * BYTES_PER_PIXEL
    size = CHUNK_PIXELS * BYTES_PER_PIXEL

    try:
        with open(current_path, 'rb') as f:
            f.seek(start)
            chunk = f.read(size)
    except Exception as e:
        print(f"Read error {client_ip} {os.path.basename(current_path)}: {e}")
        abort(500)

    if len(chunk) != size:
        abort(500, "Incomplete chunk read")

    return Response(chunk, mimetype='application/octet-stream')


# ================= MAC registration server =================
def mac_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 9022))
    sock.listen(5)
    print("MAC registration listener started on :9022")

    while True:
        try:
            client, addr = sock.accept()
            ip = addr[0]
            raw_data = client.recv(64)  # bigger buffer to catch extras
            data_str = raw_data.decode('ascii', errors='ignore').strip().upper()
            print(f"RAW from {ip}: bytes={raw_data!r} → string='{data_str}' (len={len(data_str)})")
            
            if len(data_str) < 17:
                print(f"  → Too short, ignoring")
                client.close()
                continue
                
            mac = data_str[:17]
            print(f"  Extracted MAC: '{mac}'")
            
            display = MAC_TO_DISPLAY.get(mac, "display_4")
            print(f"  Mapped to: {display}")
            
            with mapping_lock:
                ip_to_display[ip] = display
                print(f"  Stored mapping: {ip} → {display}")
                
            client.close()
        except Exception as e:
            print(f"MAC listener error: {e}")


# ================= Background maintenance =================
def maintenance_watcher():
    last_known = {k: set(get_image_files(d)) for k, d in PHOTO_DIRS.items()}

    while True:
        time.sleep(12)

        # Check for new/deleted photos
        changed = False
        for key, dir_path in PHOTO_DIRS.items():
            current = set(get_image_files(dir_path))
            if current != last_known[key]:
                changed = True
                last_known[key] = current

        if changed:
            print("Detected photo folder change → reloading cache")
            preload_all()

        # Cleanup old sessions
        now = time.time()
        to_remove = [
            ip for ip, data in list(client_current_photo.items())
            if now - data.get('last_access', 0) > 600  # 10 minutes
        ]
        for ip in to_remove:
            client_current_photo.pop(ip, None)
            with mapping_lock:
                ip_to_display.pop(ip, None)


# ================= STARTUP =================
if __name__ == '__main__':
    print("Starting GC9A01 circle display photo server...")

    preload_all()
    
    # ── TEMP DEBUG ───────────────────────────────────────────────
    print("\n=== CACHE STATUS DEBUG ===")
    for k, lst in cached_photos.items():
        print(f"{k:12} : {len(lst):3d} files")
        if lst:
            print("   First file:", os.path.basename(lst[0]))
        else:
            print("   → EMPTY ← this causes 503!")
    print("===========================\n")
    # ─────────────────────────────────────────────────────────────

    threading.Thread(target=mac_listener, daemon=True).start()
    threading.Thread(target=maintenance_watcher, daemon=True).start()

    print("Photo server ready on port 9025")
    app.run(host='0.0.0.0', port=9025, debug=False)
