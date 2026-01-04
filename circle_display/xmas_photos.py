# photo_server.py - Versatile photo server with smart scaling & cropping
from flask import Flask, send_file, abort, Response, request
import os
import random
from PIL import Image
import threading
import time

app = Flask(__name__)

# === CONFIGURATION ===
PHOTOS_DIR = '/home/preston/Desktop/x_mas_gift/circle_display/photos'
CACHE_DIR = '/home/preston/Desktop/x_mas_gift/circle_display/.cache_photos'
os.makedirs(CACHE_DIR, exist_ok=True)

# Target size for display (240 for full resolution)
TARGET_SIZE = 240

# Choose resampling filter:
# - Image.LANCZOS: smooth, high quality (good for photos)
# - Image.NEAREST: sharp pixels (good for pixel art, memes, text)
RESAMPLE_FILTER = Image.LANCZOS

CHUNK_PIXELS = 256
PIXELS_TOTAL = TARGET_SIZE * TARGET_SIZE

def get_image_files():
    """Return list of supported image files in PHOTOS_DIR"""
    supported = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.ico'}
    return [os.path.join(PHOTOS_DIR, f) for f in os.listdir(PHOTOS_DIR)
            if os.path.splitext(f.lower())[1] in supported]

def convert_to_rgb565(image_path):
    """Convert any image to TARGET_SIZE x TARGET_SIZE RGB565 raw bytes with center crop"""
    base_name = os.path.basename(image_path)
    cache_path = os.path.join(CACHE_DIR, base_name + f'.{TARGET_SIZE}x{TARGET_SIZE}.raw')
    
    # Skip conversion if cache exists and original is not newer
    if os.path.exists(cache_path):
        if os.path.getmtime(image_path) <= os.path.getmtime(cache_path):
            return cache_path
    
    print(f"Processing {base_name} → {TARGET_SIZE}x{TARGET_SIZE} RGB565...")
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if needed (handles PNG alpha, GIF, etc.)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize while maintaining aspect ratio (letterbox style)
            img.thumbnail((TARGET_SIZE, TARGET_SIZE), RESAMPLE_FILTER)
            
            # Create new square image with black background
            background = Image.new('RGB', (TARGET_SIZE, TARGET_SIZE), (0, 0, 0))
            # Paste resized image centered
            offset = ((TARGET_SIZE - img.size[0]) // 2, (TARGET_SIZE - img.size[1]) // 2)
            background.paste(img, offset)
            img = background
            
            # Convert to RGB565 raw bytes
            pixels = img.load()
            raw_bytes = bytearray()
            for y in range(TARGET_SIZE):
                for x in range(TARGET_SIZE):
                    r, g, b = pixels[x, y]
                    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    raw_bytes += bytes([rgb565 >> 8, rgb565 & 0xFF])
            
            # Save cache
            with open(cache_path, 'wb') as f:
                f.write(raw_bytes)
            
            print(f"Cached {cache_path} ({len(raw_bytes)} bytes)")
            return cache_path
            
    except Exception as e:
        print(f"Failed to process {image_path}: {e}")
        raise

# Global list of all pre-cached image paths
cached_paths = []

# Per-client current photo (ip: {'path': str, 'last_access': time})
client_photos = {}

def preload_all_images():
    """Pre-process and cache ALL photos in the folder"""
    global cached_paths
    images = get_image_files()
    if not images:
        print("No images found in photos directory!")
        cached_paths = []
        return
    
    cached_paths = []
    for img_path in images:
        cached_path = convert_to_rgb565(img_path)
        cached_paths.append(cached_path)
    
    print(f"Preloaded {len(cached_paths)} images.")

# Initial preload
preload_all_images()

@app.route('/')
def index():
    images = get_image_files()
    count = len(images)
    return f"""
    <h2>GC9A01 Photo Server Ready</h2>
    <p>Serving {TARGET_SIZE}x{TARGET_SIZE} RGB565 images</p>
    <p>Found {count} photo(s) in folder, {len(cached_paths)} cached</p>
    <p>Use: /pixel?n=0 to /pixel?n={PIXELS_TOTAL//CHUNK_PIXELS - 1}</p>
    """

@app.route('/pixel')
def serve_pixel_chunk():
    if not cached_paths:
        preload_all_images()  # In case watcher hasn't caught up
        if not cached_paths:
            abort(503, "No photos available")
    
    n_str = request.args.get('n')
    if n_str is None:
        abort(400, "Missing 'n' parameter")
    
    try:
        n = int(n_str)
    except ValueError:
        abort(400, "Invalid 'n' - must be integer")
    
    max_chunk = PIXELS_TOTAL // CHUNK_PIXELS - 1
    if n < 0 or n > max_chunk:
        abort(400, f"n out of range (0-{max_chunk})")
    
    # Get client IP
    client_ip = request.remote_addr
    
    # If this is the start of a new photo pull (n=0), pick a new random photo for this client
    if n == 0:
        client_photos[client_ip] = {
            'path': random.choice(cached_paths),
            'last_access': time.time()
        }
        print(f"New pull started from {client_ip} - serving random photo: {os.path.basename(client_photos[client_ip]['path'])}")
    
    # Get the current path for this client
    client_data = client_photos.get(client_ip)
    if client_data is None or 'path' not in client_data or not os.path.exists(client_data['path']):
        abort(500, "No current photo selected for this client - start with n=0")
    
    # Update last access time
    client_data['last_access'] = time.time()
    
    current_raw_path = client_data['path']
    
    start_byte = n * CHUNK_PIXELS * 2
    chunk_size = CHUNK_PIXELS * 2
    
    try:
        with open(current_raw_path, 'rb') as f:
            f.seek(start_byte)
            chunk = f.read(chunk_size)
    except Exception as e:
        print(f"Read error for {client_ip}: {e}")
        abort(500)
    
    if len(chunk) != chunk_size:
        print(f"Short read for {client_ip}: got {len(chunk)}, expected {chunk_size}")
        abort(500)
    
    return Response(chunk, mimetype='application/octet-stream')

# Background watcher - reloads cache when photos change
def watcher():
    known_files = set(get_image_files())
    while True:
        new_files = set(get_image_files())
        if new_files != known_files:
            print("Photo folder changed - preloading all images")
            preload_all_images()
            known_files = new_files
        
        # Optional: Clean up stale client entries (older than 10 min)
        now = time.time()
        to_remove = [ip for ip, data in list(client_photos.items()) if now - data.get('last_access', 0) > 600]
        for ip in to_remove:
            del client_photos[ip]
        
        time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=watcher, daemon=True).start()
    print(f"Versatile photo server running — {TARGET_SIZE}x{TARGET_SIZE} with smart scaling/cropping")
    print("Drop any JPG, PNG, GIF, WebP, etc. into the photos folder")
    app.run(host='0.0.0.0', port=9025, debug=False)
