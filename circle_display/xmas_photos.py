from flask import Flask, abort, Response, request
import os
import random
from PIL import Image
import threading
import time

app = Flask(__name__)

# === CONFIGURATION ===
BASE_DIR = '/home/preston/Desktop/x_mas_gift/circle_display'
PHOTO_DIRS = {
    "screen1": os.path.join(BASE_DIR, 'photos', 'circle_display_1'),  # First Circle Screen - Pattie
    "screen2": os.path.join(BASE_DIR, 'photos', 'circle_display_2'),  # Second Circle Screen - Melanie
    "screen3": os.path.join(BASE_DIR, 'photos', 'circle_display_3'),  # Third Circle Screen - Robbins
    "screen4": os.path.join(BASE_DIR, 'photos', 'circle_display_4'),  # Fourth Circle Screen - Preston and Willoh
}
TARGET_SIZE = 240
RESAMPLE_FILTER = Image.LANCZOS
CHUNK_PIXELS = 256
PIXELS_TOTAL = TARGET_SIZE * TARGET_SIZE
BYTES_PER_PIXEL = 2
CHUNK_SIZE = CHUNK_PIXELS * BYTES_PER_PIXEL

# Thread-safe lock for per-device image sessions
client_lock = threading.Lock()

# Per-client sticky photo for the whole 0..N-1 transfer.
# mac → {
#   'raw_bytes': bytes, 'path': str, 'last_access': float,
#   'last_n': int, 'completed': bool, 'started': float
# }
client_current_photo = {}

# How long an incomplete transfer may sit idle before a new image is allowed.
# Long enough for slow ESP32-C2 chunked draws (225 × HTTP).
SESSION_STALE_SEC = 180

# MAC to directory key mapping
mac_to_key = {
    "34:98:7A:07:11:7C": "screen2",  # Second Circle Screen - Melanie's circle screen
    "34:98:7A:06:FD:74": "screen1",  # First Circle Screen - Pattie's circle screen
    "34:98:7A:07:13:40": "screen3",  # Third Circle Screen - Robbins' circle screen
    "34:98:7A:07:09:68": "screen4",  # Fourth Circle Screen - Preston and Willoh's circle
    "34:98:7A:07:12:B8": "screen1",  # Unknown MAC from logs - assuming screen1 (Pattie); change if needed
}

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
            <li>First Circle Screen (Pattie): {counts.get('screen1', 0)} photos</li>
            <li>Second Circle Screen (Melanie): {counts.get('screen2', 0)} photos</li>
            <li>Third Circle Screen (Robbins): {counts.get('screen3', 0)} photos</li>
            <li>Fourth Circle Screen (Preston and Willoh): {counts.get('screen4', 0)} photos</li>
        </ul>
        <p>Use: <code>/pixel?n=0&mac=XX:XX:XX:XX:XX:XX</code> ... <code>/pixel?n={PIXELS_TOTAL//CHUNK_PIXELS - 1}&mac=XX:XX:XX:XX:XX:XX</code></p>
    """

def _session_is_active(session, now):
    """True if this MAC still owns an in-progress image we must keep serving."""
    if not session or session.get('raw_bytes') is None:
        return False
    if session.get('completed'):
        return False
    if now - session.get('last_access', 0) > SESSION_STALE_SEC:
        return False
    return True

@app.route('/pixel')
def serve_pixel_chunk():
    n_str = request.args.get('n')
    mac = request.args.get('mac', '').upper()
    if n_str is None:
        abort(400, "Missing 'n' parameter")
    if not mac or len(mac) != 17:
        abort(400, "Missing or invalid 'mac' parameter (format: XX:XX:XX:XX:XX:XX)")
    try:
        n = int(n_str)
    except ValueError:
        abort(400, "Invalid n")
    max_chunk = (PIXELS_TOTAL // CHUNK_PIXELS) - 1
    if n < 0 or n > max_chunk:
        abort(400, f"n out of range (0-{max_chunk})")

    # Get dir_key from mac
    dir_key = mac_to_key.get(mac, "screen4")  # default to screen4 if unknown
    photo_dir = PHOTO_DIRS.get(dir_key)
    if not photo_dir:
        abort(500, "Invalid display configuration")
    image_files = get_image_files(photo_dir)
    if not image_files:
        abort(503, f"No photos found in {dir_key}")

    now = time.time()
    # Convert new images outside the lock (slow PIL work) after deciding we need one.
    pending_path = None
    pending_raw = None

    with client_lock:
        session = client_current_photo.get(mac)
        need_new = False

        if n == 0:
            # New image only when no active transfer for this MAC.
            # Re-requesting n=0 mid-draw (retry/reboot) keeps the SAME picture
            # so the screen never splices two photos together.
            if not _session_is_active(session, now):
                need_new = True
            else:
                session['last_access'] = now
                session['last_n'] = 0
                print(f"[{request.remote_addr}] MAC {mac} → reusing in-progress "
                      f"{os.path.basename(session.get('path', '?'))}")
        else:
            if not session or session.get('raw_bytes') is None:
                abort(500, "Start with n=0 or image conversion failed")
            if now - session.get('last_access', 0) > SESSION_STALE_SEC:
                # Stale mid-transfer — force client to restart at n=0
                client_current_photo.pop(mac, None)
                abort(409, "Session expired; restart from n=0")

        if need_new:
            pending_path = random.choice(image_files)

    if pending_path is not None:
        pending_raw = image_to_rgb565_bytes(pending_path)
        if pending_raw is None:
            abort(500, "Image conversion failed")

    with client_lock:
        if pending_path is not None:
            # Re-check: another request may have installed a session while we converted
            session = client_current_photo.get(mac)
            if n == 0 and _session_is_active(session, time.time()):
                # Prefer the session already serving this device
                pass
            else:
                client_current_photo[mac] = {
                    'raw_bytes': pending_raw,
                    'path': pending_path,
                    'last_access': time.time(),
                    'last_n': 0,
                    'completed': False,
                    'started': time.time(),
                }
                print(f"[{request.remote_addr}] MAC {mac} → {dir_key} : "
                      f"{os.path.basename(pending_path)} (new session)")

        client_data = client_current_photo.get(mac)
        if not client_data or client_data.get('raw_bytes') is None:
            abort(500, "Start with n=0 or image conversion failed")

        client_data['last_access'] = time.time()
        client_data['last_n'] = n
        if n >= max_chunk:
            client_data['completed'] = True

        raw_bytes = client_data['raw_bytes']
        start = n * CHUNK_SIZE
        chunk = raw_bytes[start : start + CHUNK_SIZE]
        if not chunk:
            abort(500, "Chunk read error")

    return Response(chunk, mimetype='application/octet-stream')

def cleanup_old_clients():
    while True:
        now = time.time()
        # Drop idle sessions (completed or abandoned). Active draws refresh last_access.
        to_remove = [
            mac for mac, data in list(client_current_photo.items())
            if now - data.get('last_access', 0) > max(600, SESSION_STALE_SEC * 2)
        ]
        with client_lock:
            for mac in to_remove:
                client_current_photo.pop(mac, None)
        time.sleep(30)

if __name__ == '__main__':
    threading.Thread(target=cleanup_old_clients, daemon=True).start()
    print("Starting GC9A01 photo server (no cache, on-the-fly RGB565 conversion)...")
    app.run(host='0.0.0.0', port=9025, debug=False)
