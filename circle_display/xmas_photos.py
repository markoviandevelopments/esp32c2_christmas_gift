# photo_server.py - Serves random 240x240 RGB565 images from ./photos/
from flask import Flask, send_file, abort
import os
import random
from PIL import Image
import threading
import time

app = Flask(__name__)

PHOTOS_DIR = '/home/preston/Desktop/x_mas_gift/circle_display/photos'
CACHE_DIR = '/home/preston/Desktop/x_mas_gift/circle_display/.cache_photos'
os.makedirs(CACHE_DIR, exist_ok=True)

def convert_to_rgb565(image_path):
    cache_path = os.path.join(CACHE_DIR, os.path.basename(image_path) + '.raw')
    if os.path.exists(cache_path):
        return cache_path
    
    print(f"Converting {image_path}...")
    img = Image.open(image_path).convert('RGB')
    img = img.resize((240, 240), Image.LANCZOS)
    
    # Center crop if needed (in case aspect ratio is wrong)
    width, height = img.size
    left = (width - 240) // 2
    top = (height - 240) // 2
    img = img.crop((left, top, left+240, top+240))
    
    pixels = img.load()
    raw_bytes = bytearray()
    for y in range(240):
        for x in range(240):
            r, g, b = pixels[x, y]
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            raw_bytes.append(rgb565 >> 8)
            raw_bytes.append(rgb565 & 0xFF)
    
    with open(cache_path, 'wb') as f:
        f.write(raw_bytes)
    print(f"Cached {cache_path}")
    return cache_path

def get_available_images():
    images = []
    for file in os.listdir(PHOTOS_DIR):
        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            full_path = os.path.join(PHOTOS_DIR, file)
            images.append(full_path)
    return images

@app.route('/')
def index():
    images = get_available_images()
    if not images:
        return "No photos in folder yet."
    return "<br>".join([f"<li>{os.path.basename(p)}</li>" for p in images])

@app.route('/image.raw')
def serve_random_image():
    images = get_available_images()
    if not images:
        abort(404, "No photos found")
    
    chosen = random.choice(images)
    raw_path = convert_to_rgb565(chosen)
    return send_file(raw_path, mimetype='application/octet-stream')

# Optional: background watcher to pre-convert new photos
def watcher():
    known = set()
    while True:
        current = set(get_available_images())
        new = current - known
        for p in new:
            try:
                convert_to_rgb565(p)
            except Exception as e:
                print(f"Failed to convert {p}: {e}")
        known = current
        time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=watcher, daemon=True).start()
    print("Photo server running on http://0.0.0.0:9025/image.raw")
    print("Drop PNG/JPG files into /home/preston/Desktop/x_mas_gift/photos/")
    app.run(host='0.0.0.0', port=9025)
