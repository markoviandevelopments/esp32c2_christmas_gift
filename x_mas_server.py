# x_mas_server.py - FULL MERGED SERVER
# Crypto data + local auto-compile + FULL round-screen photo server
# (Git sync removed — hard reset was wiping local edits)
from flask import Flask, send_file, abort, request, Response
import threading
import time
import os
import shutil
import hashlib
import subprocess
import requests
from PIL import Image
import numpy as np
import io
import struct
from zoneinfo import ZoneInfo
import datetime
import random

app = Flask(__name__)

# === CONFIGURATION ===
REPO_DIR = '/home/preston/Desktop/x_mas_gift'
# How often to *check* whether a source changed. The check is a stat() per file
# (a few microseconds); mpy-cross only actually runs when the content changed,
# so this can be short without costing anything.
COMPILE_CHECK_INTERVAL = 30
MPY_CROSS_PATH = '/home/preston/micropython/mpy-cross/build/mpy-cross'

# File paths for crypto screens
SECONDARY_PY = os.path.join(REPO_DIR, 'secondary.py')
SECONDARY_MPY = os.path.join(REPO_DIR, 'secondary.mpy')
BOOT_PY = os.path.join(REPO_DIR, 'boot.py')
BOOT_MPY = os.path.join(REPO_DIR, 'boot.mpy')
TERTIARY_PY = os.path.join(REPO_DIR, 'tertiary.py')
TERTIARY_MPY = os.path.join(REPO_DIR, 'tertiary.mpy')

# Logo cache for crypto screens
LOGO_DIR = os.path.join(REPO_DIR, "logos")
os.makedirs(LOGO_DIR, exist_ok=True)

# === PHOTO SERVER CONFIG (round screens) ===
BASE_DIR = '/home/preston/Desktop/x_mas_gift/circle_display'
PHOTO_DIRS = {
    "screen1": os.path.join(BASE_DIR, 'photos', 'Pattie'),
    "screen2": os.path.join(BASE_DIR, 'photos', 'Rob & Melanie'),
    "screen3": os.path.join(BASE_DIR, 'photos', 'Arwyn & Bella'),
    "screen4": os.path.join(BASE_DIR, 'photos', 'Preston & Willoh')
}
TARGET_SIZE = 240
RESAMPLE_FILTER = Image.LANCZOS
CHUNK_PIXELS = 256
PIXELS_TOTAL = TARGET_SIZE * TARGET_SIZE
BYTES_PER_PIXEL = 2
CHUNK_SIZE = CHUNK_PIXELS * BYTES_PER_PIXEL

client_lock = threading.Lock()
client_current_photo = {}  # mac → {'raw_bytes': bytes, 'last_access': float, 'path': str}

mac_to_key = {
    "34:98:7A:07:11:7C": "screen2",
    "34:98:7A:06:FD:74": "screen1",
    "34:98:7A:07:13:40": "screen3",
    "34:98:7A:07:09:68": "screen4",
    "34:98:7A:07:12:B8": "screen1",   # test device
}

SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
_listing_cache = {}   # directory → (dir_mtime_ns, [paths])

def get_image_files(directory):
    """Listing keyed on the directory's own mtime: one stat() on the hot path,
    and still instantly correct when a photo is uploaded or removed."""
    try:
        mtime = os.stat(directory).st_mtime_ns
    except OSError:
        return []
    cached = _listing_cache.get(directory)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    try:
        with os.scandir(directory) as it:
            files = [e.path for e in it
                     if e.is_file() and os.path.splitext(e.name.lower())[1] in SUPPORTED_EXT]
    except OSError:
        return []
    _listing_cache[directory] = (mtime, files)
    return files

def image_to_rgb565_bytes(image_path):
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((TARGET_SIZE, TARGET_SIZE), RESAMPLE_FILTER)
            background = Image.new('RGB', (TARGET_SIZE, TARGET_SIZE), (0, 0, 0))
            offset = ((TARGET_SIZE - img.size[0]) // 2, (TARGET_SIZE - img.size[1]) // 2)
            background.paste(img, offset)
            # Vectorized RGB565 — byte-identical to the old per-pixel loop, ~22x cheaper
            a = np.asarray(background, dtype=np.uint16)
            packed = ((a[:, :, 0] & 0xF8) << 8) | ((a[:, :, 1] & 0xFC) << 3) | (a[:, :, 2] >> 3)
            return packed.astype('>u2').tobytes()
    except Exception as e:
        print(f"Failed to process {image_path}: {e}")
        return None

# === DATA PROXY CACHE (crypto screens) ===
cached_prices = {'btc': "error", 'sol': "error", 'doge': "error", 'pepe': "error",
                 'xrp': "error", 'ltc': "error", 'tsla': "error"}
cached_logos = {}
cached_big_logos = {}

HOLDINGS = {
    '34:98:7A:07:13:B4': {'coin': 'xrp', 'amount': 2.76412},
    '34:98:7A:07:14:D0': {'coin': 'sol', 'amount': 0.062432083},
    '34:98:7A:06:FC:A0': {'coin': 'doge', 'amount': 40.7874},
    '34:98:7A:06:FB:D0': {'coin': 'pepe', 'amount': 1291895},
    '34:98:7A:07:11:24': {'coin': 'ltc', 'amount': 0.067632},
    '34:98:7A:07:12:B8': {'coin': 'tsla', 'amount': 0.012164027},
    '34:98:7A:07:06:B4': {'coin': 'btc', 'amount': 0.0000566},
}

def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def load_or_download_logo(coin, url):
    """Prefer on-disk PNG under logos/; only hit network if missing."""
    local_path = os.path.join(LOGO_DIR, f"{coin}.png")
    try:
        if os.path.exists(local_path):
            img = Image.open(local_path).convert('RGB')
        else:
            r = requests.get(url, timeout=15, headers={'User-Agent': 'x-mas-gift/1.0'})
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert('RGB')
            img.save(local_path)
        img = img.resize((20, 20), Image.LANCZOS)
        pixels = []
        for y in range(20):
            for x in range(20):
                r, g, b = img.getpixel((x, y))
                pixels.append(f"0x{rgb565(r,g,b):04X}")
        return ','.join(pixels)
    except Exception as e:
        print(f'logo load failed for {coin}: {e}')
        return "error"

def generate_big_logo(coin):
    if coin in cached_big_logos:
        return cached_big_logos[coin]
    local_path = os.path.join(LOGO_DIR, f"{coin}.png")
    if not os.path.exists(local_path):
        return None
    try:
        img = Image.open(local_path).convert('RGB')
        orig_w, orig_h = img.size
        ratio = min(160 / orig_w, 80 / orig_h)
        new_w = max(1, int(orig_w * ratio))
        new_h = max(1, int(orig_h * ratio))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        offset_x = (160 - new_w) // 2
        offset_y = (80 - new_h) // 2
        pixels = []
        for y in range(80):
            for x in range(160):
                if x < offset_x or x >= offset_x + new_w or y < offset_y or y >= offset_y + new_h:
                    pixels.append(0)
                else:
                    px_x = x - offset_x
                    px_y = y - offset_y
                    r, g, b = img.getpixel((px_x, px_y))
                    pixels.append(rgb565(r, g, b))
        cached_big_logos[coin] = pixels
        return pixels
    except Exception as e:
        print(f'biglogo failed for {coin}: {e}')
        return None

def _yahoo_tsla_price():
    """Fallback when CoinGecko tesla-xstock is missing/rate-limited."""
    try:
        r = requests.get(
            'https://query1.finance.yahoo.com/v8/finance/chart/TSLA?interval=1d&range=1d',
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        r.raise_for_status()
        meta = r.json()['chart']['result'][0]['meta']
        price = meta.get('regularMarketPrice') or meta.get('previousClose')
        if price is not None:
            return float(price)
    except Exception as e:
        print(f'yahoo TSLA fallback failed: {e}')
    return None

def fetch_data():
    global cached_prices, cached_logos, cached_big_logos
    while True:
        ids = "bitcoin,solana,dogecoin,pepe,ripple,litecoin,tesla-xstock"
        try:
            r = requests.get(
                f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd',
                timeout=10,
            )
            data = r.json()
            if 'bitcoin' in data:
                cached_prices['btc'] = f"{data['bitcoin']['usd']:.8f}"
            if 'solana' in data:
                cached_prices['sol'] = f"{data['solana']['usd']:.4f}"
            if 'dogecoin' in data:
                cached_prices['doge'] = f"{data['dogecoin']['usd']:.6f}"
            if 'pepe' in data:
                cached_prices['pepe'] = f"{data['pepe']['usd']:.10f}"
            if 'ripple' in data:
                cached_prices['xrp'] = f"{data['ripple']['usd']:.4f}"
            if 'litecoin' in data:
                cached_prices['ltc'] = f"{data['litecoin']['usd']:.4f}"
            if 'tesla-xstock' in data:
                cached_prices['tsla'] = f"{data['tesla-xstock']['usd']:.2f}"
            else:
                yp = _yahoo_tsla_price()
                if yp is not None:
                    cached_prices['tsla'] = f"{yp:.2f}"
        except Exception as e:
            print(f'coingecko fetch failed: {e}')
            # Keep last good crypto prices; still try Yahoo for TSLA
            if cached_prices.get('tsla') in (None, 'error'):
                yp = _yahoo_tsla_price()
                if yp is not None:
                    cached_prices['tsla'] = f"{yp:.2f}"

        # Local logos preferred; remote URLs only for first-time seed if file missing
        logo_urls = {
            'btc': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
            'sol': 'https://cryptologos.cc/logos/solana-sol-logo.png',
            'doge': 'https://cryptologos.cc/logos/dogecoin-doge-logo.png',
            'pepe': 'https://cryptologos.cc/logos/pepe-pepe-logo.png',
            'xrp': 'https://cryptologos.cc/logos/xrp-xrp-logo.png',
            'ltc': 'https://cryptologos.cc/logos/litecoin-ltc-logo.png',
            'tsla': 'https://upload.wikimedia.org/wikipedia/commons/e/e8/Tesla_logo.png',
        }
        for coin, url in logo_urls.items():
            if coin not in cached_logos or cached_logos.get(coin) == "error":
                try:
                    cached_logos[coin] = load_or_download_logo(coin, url)
                except Exception as e:
                    print(f'logo cache {coin}: {e}')
            generate_big_logo(coin)
        time.sleep(180)


# === ROUTES ===
@app.route('/<coin>')
def get_price(coin):
    coin = coin.lower()
    return cached_prices.get(coin, "error")

@app.route('/time')
def get_time():
    try:
        now = datetime.datetime.now(ZoneInfo("America/Chicago"))
        return now.strftime('%H:%M:%S')
    except:
        return "error"

@app.route('/rank')
def get_rank():
    values = {}
    for mac, info in HOLDINGS.items():
        coin_key = info['coin']
        try:
            price = float(cached_prices.get(coin_key, "0"))
            usd = price * info['amount']
            values[mac] = usd
        except:
            values[mac] = 0.0
    sorted_macs = sorted(values, key=lambda m: values[m], reverse=True)
    rank_dict = {}
    i = 0
    while i < len(sorted_macs):
        current_val = values[sorted_macs[i]]
        j = i
        while j < len(sorted_macs) and values[sorted_macs[j]] == current_val:
            rank_dict[sorted_macs[j]] = i + 1
            j += 1
        i = j
    return rank_dict

@app.route('/logo/<coin>')
def get_logo(coin):
    coin = coin.lower()
    return cached_logos.get(coin, "error")

@app.route('/biglogo_chunks/<coin>')
def biglogo_chunks(coin):
    pixels = generate_big_logo(coin.lower())
    if pixels is None:
        return "0"
    return str((len(pixels) + 255) // 256)

@app.route('/biglogo/<coin>/<int:chunk>')
def biglogo_chunk(coin, chunk):
    pixels = generate_big_logo(coin.lower())
    if pixels is None:
        return b''
    start = chunk * 256
    if start >= len(pixels):
        return b''
    end = min(start + 256, len(pixels))
    chunk_pixels = pixels[start:end]
    return struct.pack(">{}H".format(len(chunk_pixels)), *chunk_pixels)

# === ROUND SCREEN PHOTO ENDPOINT (exactly as your standalone server) ===
@app.route('/pixel')
def serve_pixel_chunk():
    n_str = request.args.get('n')
    mac = request.args.get('mac', '').upper()
    if n_str is None:
        abort(400, "Missing 'n' parameter")
    if not mac or len(mac) != 17:
        abort(400, "Missing or invalid 'mac' parameter")
    try:
        n = int(n_str)
    except ValueError:
        abort(400, "Invalid n")
    max_chunk = (PIXELS_TOTAL // CHUNK_PIXELS) - 1
    if n < 0 or n > max_chunk:
        abort(400, f"n out of range (0-{max_chunk})")

    dir_key = mac_to_key.get(mac, "screen4")
    photo_dir = PHOTO_DIRS.get(dir_key)
    if not photo_dir:
        abort(500, "Invalid display configuration")

    # Only chunk 0 picks a new picture, so only chunk 0 needs the listing.
    if n == 0:
        image_files = get_image_files(photo_dir)
        if not image_files:
            abort(503, f"No photos found in {dir_key}")

    with client_lock:
        if n == 0:
            chosen_path = random.choice(image_files)
            client_current_photo[mac] = {
                'raw_bytes': image_to_rgb565_bytes(chosen_path),
                'last_access': time.time(),
                'path': chosen_path
            }
            short_name = os.path.basename(chosen_path)
            print(f"[{request.remote_addr}] MAC {mac} → {dir_key} : {short_name}")

        client_data = client_current_photo.get(mac)
        if not client_data or client_data.get('raw_bytes') is None:
            abort(500, "Start with n=0 or image conversion failed")

        client_data['last_access'] = time.time()
        raw_bytes = client_data['raw_bytes']
        start = n * CHUNK_SIZE
        chunk = raw_bytes[start : start + CHUNK_SIZE]
        if not chunk:
            abort(500, "Chunk read error")

    return Response(chunk, mimetype='application/octet-stream')

def cleanup_old_clients():
    while True:
        now = time.time()
        to_remove = [mac for mac, data in list(client_current_photo.items())
                     if now - data.get('last_access', 0) > 600]
        with client_lock:
            for mac in to_remove:
                client_current_photo.pop(mac, None)
        # Entries expire at 600s; sweeping every 30s just woke the CPU 20x more
        # often than needed to free a few hundred KB.
        time.sleep(300)

# === LOCAL AUTO-COMPILE (no git) ===
# Recompiling every source on a timer burned mpy-cross ~1150x/day to produce
# byte-identical output. Instead: stat() the sources cheaply, and only shell out
# to mpy-cross when the content actually changed (any edit — a VERSION bump, a
# one-character fix — so the .mpy is never behind the source).
_compile_state = {}   # src path → {'fp': (mtime_ns, size), 'sha': hexdigest}

def _file_sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest()

def _needs_compile(src, dst):
    """(should_compile, stamp). Stamp is recorded only after a successful compile
    so a failed build retries on the next tick instead of being marked done."""
    try:
        st = os.stat(src)
    except OSError:
        return False, None                      # source absent — nothing to do, quietly
    fp = (st.st_mtime_ns, st.st_size)
    prev = _compile_state.get(src)
    dst_exists = os.path.isfile(dst)

    # Fast path: nothing touched the file since the last look. One stat, no read.
    if prev is not None and prev['fp'] == fp and dst_exists:
        return False, None

    digest = _file_sha1(src)
    stamp = {'fp': fp, 'sha': digest}

    if not dst_exists:
        return True, stamp
    # Touched but identical (git checkout, editor rewrite) — don't rebuild.
    if prev is not None and prev['sha'] == digest:
        _compile_state[src] = stamp
        return False, None
    # First look after a restart: trust an existing .mpy that is newer than its source.
    if prev is None and os.stat(dst).st_mtime_ns >= st.st_mtime_ns:
        _compile_state[src] = stamp
        return False, None
    return True, stamp

def _compile_mpy(src, dst, label):
    if not os.path.isfile(MPY_CROSS_PATH):
        print(f'[{time.strftime("%H:%M:%S")}] ❌ mpy-cross not found: {MPY_CROSS_PATH}')
        return False
    result = subprocess.run(
        [MPY_CROSS_PATH, '-march=rv32imc', src, '-o', dst],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and os.path.isfile(dst):
        print(f'[{time.strftime("%H:%M:%S")}] ✅ Compiled {label} → {os.path.basename(dst)} ({os.path.getsize(dst)} bytes)')
        return True
    err = (result.stderr or '')[-200:]
    print(f'[{time.strftime("%H:%M:%S")}] ❌ Failed {label}: rc={result.returncode} {err}')
    return False

CIRCLE_BOOT_PY = os.path.join(REPO_DIR, 'circle_display', 'boot2.py')
BOOT2_MPY = os.path.join(REPO_DIR, 'boot2.mpy')
BOOT2_PY = os.path.join(REPO_DIR, 'boot2.py')

COMPILE_TARGETS = [
    (BOOT_PY, BOOT_MPY, 'boot.py (rect screens)'),
    (SECONDARY_PY, SECONDARY_MPY, 'secondary.py (rect app)'),
    (TERTIARY_PY, TERTIARY_MPY, 'tertiary.py (circle app)'),
    (CIRCLE_BOOT_PY, BOOT2_MPY, 'circle_display/boot2.py (circle boot)'),
]

def compile_firmware_loop():
    """Watch local sources; compile only what changed. Does not touch git."""
    while True:
        try:
            for src, dst, label in COMPILE_TARGETS:
                should, stamp = _needs_compile(src, dst)
                if not should:
                    continue
                if not _compile_mpy(src, dst, label):
                    continue
                _compile_state[src] = stamp
                if src == CIRCLE_BOOT_PY:
                    try:
                        shutil.copy2(CIRCLE_BOOT_PY, BOOT2_PY)
                        print(f'[{time.strftime("%H:%M:%S")}] ✅ Copied circle boot2.py source → boot2.py')
                    except Exception as e:
                        print(f'[{time.strftime("%H:%M:%S")}] Warning copying boot2.py: {e}')
        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] Compile loop error: {e}')

        time.sleep(COMPILE_CHECK_INTERVAL)


# === UPDATE ENDPOINT ===
@app.route('/update')
def serve_update():
    mac = request.args.get('mac')
    file_type = request.args.get('file')
    if mac == '34:98:7A:07:12:B8':
        try:
            if file_type == 'secondary':
                return send_file(SECONDARY_PY, mimetype='text/plain')
            elif file_type == 'tertiary':
                return send_file(TERTIARY_PY, mimetype='text/plain')
            elif file_type == 'boot':
                return send_file(BOOT_PY, mimetype='text/plain')
        except:
            abort(404)
    return "error"

# === STATIC FILE ROUTES ===
@app.route('/secondary.mpy')
def serve_secondary_mpy():
    if not os.path.isfile(SECONDARY_MPY): abort(404)
    return send_file(SECONDARY_MPY, mimetype='application/octet-stream')

@app.route('/boot.mpy')
def serve_boot_mpy():
    if not os.path.isfile(BOOT_MPY): abort(404)
    return send_file(BOOT_MPY, mimetype='application/octet-stream')

@app.route('/boot.py')
def serve_boot_py_source():
    """Rect screens need SOURCE boot.py flashed to the device."""
    if not os.path.isfile(BOOT_PY): abort(404)
    return send_file(BOOT_PY, mimetype='text/plain')

@app.route('/tertiary.mpy')
def serve_tertiary_mpy():
    if not os.path.isfile(TERTIARY_MPY): abort(404)
    return send_file(TERTIARY_MPY, mimetype='application/octet-stream')

@app.route('/boot2.mpy')
def serve_boot2_mpy():
    boot2_mpy = os.path.join(REPO_DIR, 'boot2.mpy')
    if not os.path.isfile(boot2_mpy):
        abort(404)
    return send_file(boot2_mpy, mimetype='application/octet-stream')

@app.route('/boot2.py')
def serve_boot2_py():
    boot2_py = os.path.join(REPO_DIR, 'boot2.py')
    if not os.path.isfile(boot2_py):
        abort(404)
    return send_file(boot2_py, mimetype='text/plain')

@app.route('/')
def index():
    return "✅ XH-C2X Full Server running - crypto + round photo endpoints active"

if __name__ == '__main__':
    threading.Thread(target=compile_firmware_loop, daemon=True).start()
    threading.Thread(target=fetch_data, daemon=True).start()
    threading.Thread(target=cleanup_old_clients, daemon=True).start()
    print("✅ Full merged XH-C2X server starting on port 9019...")
    print("   (git sync disabled — local tree will not be reset)")
    app.run(host='0.0.0.0', port=9019, debug=False)