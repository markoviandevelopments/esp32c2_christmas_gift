# photo_server.py - Fixed chunked pixel server (64x64 debug)
from flask import Flask, send_file, abort, Response, request
import os
import random
from PIL import Image
import threading
import time

app = Flask(__name__)

PHOTOS_DIR = '/home/preston/Desktop/x_mas_gift/circle_display/photos'
CACHE_DIR = '/home/preston/Desktop/x_mas_gift/circle_display/.cache_photos_64'
os.makedirs(CACHE_DIR, exist_ok=True)

SIZE = 64
PIXELS = SIZE * SIZE  # 4096
CHUNK_PIXELS = 16  # 16 pixels = 32 bytes

def convert_to_rgb565(image_path):
    cache_path = os.path.join(CACHE_DIR, os.path.basename(image_path) + '.raw')
    if os.path.exists(cache_path):
        return cache_path
    
    print(f"Converting {image_path} to {SIZE}x{SIZE} RGB565...")
    img = Image.open(image_path).convert('RGB')
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    
    pixels = img.load()
    raw_bytes = bytearray()
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b = pixels[x, y]
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            raw_bytes.append(rgb565 >> 8)
            raw_bytes.append(rgb565 & 0xFF)
    
    with open(cache_path, 'wb') as f:
        f.write(raw_bytes)
    print(f"Cached {cache_path} ({len(raw_bytes)} bytes)")
    return cache_path

def get_random_image_raw():
    images = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
    if not images:
        print("No photos found in directory!")
        abort(404, "No photos")
    chosen = random.choice(images)
    print(f"Selected photo: {chosen}")
    return convert_to_rgb565(os.path.join(PHOTOS_DIR, chosen))

current_raw_path = None

def load_random_image():
    global current_raw_path
    current_raw_path = get_random_image_raw()

load_random_image()  # Initial load

@app.route('/')
def index():
    return f"<h2>Pixel server ready (64x64)</h2><p>Chunks: 0 to {PIXELS//CHUNK_PIXELS - 1}</p><p>Current photo cached.</p>"

@app.route('/pixel')
def serve_pixel_chunk():
    global current_raw_path
    if current_raw_path is None:
        load_random_image()
    
    n_str = request.args.get('n')
    if n_str is None:
        print("ERROR: Missing 'n' parameter")
        abort(400, "Missing 'n' parameter")
    
    try:
        n = int(n_str)
    except ValueError:
        print(f"ERROR: Invalid 'n' value: {n_str}")
        abort(400, "Invalid 'n' - must be integer")
    
    max_chunk = PIXELS // CHUNK_PIXELS - 1
    if n < 0 or n > max_chunk:
        print(f"ERROR: n={n} out of range (0-{max_chunk})")
        abort(400, f"n out of range (0-{max_chunk})")
    
    start_byte = n * CHUNK_PIXELS * 2
    chunk_size = CHUNK_PIXELS * 2
    
    try:
        with open(current_raw_path, 'rb') as f:
            f.seek(start_byte)
            chunk = f.read(chunk_size)
    except Exception as e:
        print(f"ERROR reading cache: {e}")
        abort(500)
    
    if len(chunk) != chunk_size:
        print(f"ERROR: Short read - got {len(chunk)} bytes, expected {chunk_size}")
        abort(500)
    
    print(f"SUCCESS: Served chunk n={n} ({len(chunk)} bytes)")
    return Response(chunk, mimetype='application/octet-stream')

# Background watcher
def watcher():
    known = set()
    while True:
        current = set(os.path.join(PHOTOS_DIR, f) for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')))
        if current - known:
            print("New photo detected - reloading cache")
            load_random_image()
        known = current
        time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=watcher, daemon=True).start()
    print("FIXED pixel chunk server running — ready for /pixel?n=0")
    print("http://0.0.0.0:9025/pixel?n=0")
    app.run(host='0.0.0.0', port=9025)
