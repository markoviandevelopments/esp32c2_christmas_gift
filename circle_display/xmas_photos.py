# photo_server.py - Chunked pixel server for low-RAM devices (64x64 debug version)
from flask import Flask, send_file, abort, Response
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
CHUNK_PIXELS = 16  # 16 pixels per request = 32 bytes

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
    print(f"Cached {cache_path}")
    return cache_path

def get_random_image_raw():
    images = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
    if not images:
        abort(404, "No photos")
    chosen = random.choice(images)
    return convert_to_rgb565(os.path.join(PHOTOS_DIR, chosen))

# Cache the current image path
current_raw_path = None

def load_random_image():
    global current_raw_path
    current_raw_path = get_random_image_raw()

load_random_image()  # Initial load

@app.route('/')
def index():
    return f"<h2>Pixel server ready</h2><p>Serving 64x64 photo in chunks of {CHUNK_PIXELS} pixels</p><p>Use /pixel?n=0 to /pixel?n={PIXELS//CHUNK_PIXELS - 1}</p>"

@app.route('/pixel')
def serve_pixel_chunk():
    global current_raw_path
    if current_raw_path is None:
        load_random_image()
    
    try:
        n = int(request.args.get('n', '0'))
        if n < 0 or n >= (PIXELS // CHUNK_PIXELS):
            abort(404)
    except:
        abort(400)
    
    start_byte = n * CHUNK_PIXELS * 2
    end_byte = start_byte + CHUNK_PIXELS * 2
    
    with open(current_raw_path, 'rb') as f:
        f.seek(start_byte)
        chunk = f.read(CHUNK_PIXELS * 2)
    
    if len(chunk) != CHUNK_PIXELS * 2:
        abort(500)
    
    # Optional: refresh image every 60 seconds
    if time.time() % 60 < 1:
        load_random_image()
    
    return Response(chunk, mimetype='application/octet-stream')

# Background watcher for new photos
def watcher():
    known = set()
    while True:
        current = set(os.path.join(PHOTOS_DIR, f) for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')))
        if current - known:
            load_random_image()
        known = current
        time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=watcher, daemon=True).start()
    print("Pixel chunk server running — 16 pixels per request")
    print("Use http://<ip>:9025/pixel?n=0 ...")
    app.run(host='0.0.0.0', port=9025)
