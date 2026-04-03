# x_mas_server.py - FULL MERGED SERVER (Git sync + auto-compile + ALL data endpoints)
from flask import Flask, send_file, abort, request
import threading
import time
import git
import os
import subprocess
import requests
from PIL import Image
import io
import struct
from zoneinfo import ZoneInfo
import datetime

app = Flask(__name__)

# === CONFIGURATION ===
REPO_DIR = '/home/preston/Desktop/x_mas_gift'
REPO_URL = 'https://github.com/markoviandevelopments/esp32c2_christmas_gift.git'
SYNC_INTERVAL = 300
MPY_CROSS_PATH = '/home/preston/micropython/mpy-cross/build/mpy-cross'

SECONDARY_PY = os.path.join(REPO_DIR, 'secondary.py')
SECONDARY_MPY = os.path.join(REPO_DIR, 'secondary.mpy')
BOOT_PY = os.path.join(REPO_DIR, 'boot.py')
BOOT_MPY = os.path.join(REPO_DIR, 'boot.mpy')
TERTIARY_PY = os.path.join(REPO_DIR, 'tertiary.py')
TERTIARY_MPY = os.path.join(REPO_DIR, 'tertiary.mpy')

LOGO_DIR = os.path.join(REPO_DIR, "logos")
os.makedirs(LOGO_DIR, exist_ok=True)

# === DATA CACHE ===
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
    local_path = os.path.join(LOGO_DIR, f"{coin}.png")
    if os.path.exists(local_path):
        img = Image.open(local_path).convert('RGB')
    else:
        r = requests.get(url, timeout=15)
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
    except:
        return None

def fetch_data():
    global cached_prices, cached_logos
    while True:
        # Prices from CoinGecko
        ids = "bitcoin,solana,dogecoin,pepe,ripple,litecoin,tesla-xstock"
        try:
            r = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd', timeout=10)
            data = r.json()
            cached_prices['btc'] = f"{data['bitcoin']['usd']:.8f}"
            cached_prices['sol'] = f"{data['solana']['usd']:.4f}"
            cached_prices['doge'] = f"{data['dogecoin']['usd']:.6f}"
            cached_prices['pepe'] = f"{data['pepe']['usd']:.10f}"
            cached_prices['xrp'] = f"{data['ripple']['usd']:.4f}"
            cached_prices['ltc'] = f"{data['litecoin']['usd']:.4f}"
            cached_prices['tsla'] = f"{data['tesla-xstock']['usd']:.2f}"
        except:
            pass

        # Logos
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
            if coin not in cached_logos:
                cached_logos[coin] = load_or_download_logo(coin, url)
            generate_big_logo(coin)

        time.sleep(180)  # refresh every 3 minutes

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

# === GIT SYNC + AUTO-COMPILE ===
def sync_github():
    while True:
        try:
            git_dir = os.path.join(REPO_DIR, '.git')
            if os.path.exists(git_dir):
                repo = git.Repo(REPO_DIR)
                origin = repo.remotes.origin
                origin.fetch()
                repo.git.reset('--hard', 'origin/main')
                repo.git.checkout('main')
                print(f'[{time.strftime("%H:%M:%S")}] GitHub sync successful')
            else:
                print(f'[{time.strftime("%H:%M:%S")}] Cloning repo...')
                git.Repo.clone_from(REPO_URL, REPO_DIR, branch='main')

            # Compile
            if os.path.isfile(SECONDARY_PY):
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', SECONDARY_PY, '-o', SECONDARY_MPY])
            if os.path.isfile(TERTIARY_PY):
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', TERTIARY_PY, '-o', TERTIARY_MPY])
            if os.path.isfile(BOOT_PY):
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', BOOT_PY, '-o', BOOT_MPY])
        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] Sync error: {e}')
        time.sleep(SYNC_INTERVAL)

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

@app.route('/tertiary.mpy')
def serve_tertiary_mpy():
    if not os.path.isfile(TERTIARY_MPY): abort(404)
    return send_file(TERTIARY_MPY, mimetype='application/octet-stream')

@app.route('/')
def index():
    return "✅ XH-C2X Full Server running - all endpoints active"

if __name__ == '__main__':
    threading.Thread(target=sync_github, daemon=True).start()
    threading.Thread(target=fetch_data, daemon=True).start()
    print("✅ Full merged XH-C2X server starting on port 9019...")
    app.run(host='0.0.0.0', port=9019, debug=False)# x_mas_server.py - FULL MERGED SERVER
# GitHub sync + auto-compile + ALL data endpoints for ESP32-C2
from flask import Flask, send_file, abort, request, send_from_directory
import threading
import time
import git
import os
import subprocess
import requests
from PIL import Image
import io
import struct
from zoneinfo import ZoneInfo
import datetime

app = Flask(__name__)

# === CONFIGURATION ===
REPO_DIR = '/home/preston/Desktop/x_mas_gift'
REPO_URL = 'https://github.com/markoviandevelopments/esp32c2_christmas_gift.git'
SYNC_INTERVAL = 300  # seconds (5 minutes)
MPY_CROSS_PATH = '/home/preston/micropython/mpy-cross/build/mpy-cross'

# File paths
SECONDARY_PY = os.path.join(REPO_DIR, 'secondary.py')
SECONDARY_MPY = os.path.join(REPO_DIR, 'secondary.mpy')
BOOT_PY = os.path.join(REPO_DIR, 'boot.py')
BOOT_MPY = os.path.join(REPO_DIR, 'boot.mpy')
TERTIARY_PY = os.path.join(REPO_DIR, 'tertiary.py')
TERTIARY_MPY = os.path.join(REPO_DIR, 'tertiary.mpy')

# Logo cache directory
LOGO_DIR = os.path.join(REPO_DIR, "logos")
os.makedirs(LOGO_DIR, exist_ok=True)

# === DATA PROXY CACHE ===
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
TEST_MAC = '34:98:7A:07:12:B8'

def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def load_or_download_logo(coin, url):
    local_path = os.path.join(LOGO_DIR, f"{coin}.png")
    if os.path.exists(local_path):
        img = Image.open(local_path).convert('RGB')
    else:
        r = requests.get(url, timeout=15)
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
    except:
        return None

def fetch_data():
    global cached_prices, cached_logos, cached_big_logos
    while True:
        # Prices
        ids = "bitcoin,solana,dogecoin,pepe,ripple,litecoin,tesla-xstock"
        try:
            r = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd', timeout=10)
            data = r.json()
            cached_prices['btc'] = f"{data['bitcoin']['usd']:.8f}"
            cached_prices['sol'] = f"{data['solana']['usd']:.4f}"
            cached_prices['doge'] = f"{data['dogecoin']['usd']:.6f}"
            cached_prices['pepe'] = f"{data['pepe']['usd']:.10f}"
            cached_prices['xrp'] = f"{data['ripple']['usd']:.4f}"
            cached_prices['ltc'] = f"{data['litecoin']['usd']:.4f}"
            cached_prices['tsla'] = f"{data['tesla-xstock']['usd']:.2f}"
        except:
            pass

        # Logos
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
            if coin not in cached_logos:
                cached_logos[coin] = load_or_download_logo(coin, url)
            generate_big_logo(coin)

        time.sleep(180)  # refresh every 3 minutes

# === DATA ENDPOINTS ===
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
    sorted_macs = sorted(values.keys(), key=lambda m: values[m], reverse=True)
    rank_dict = {}
    i = 0
    while i < len(sorted_macs):
        current = sorted_macs[i]
        current_val = values[current]
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

@app.route('/pixel')
def serve_pixel_chunk():
    n = request.args.get('n', type=int)
    mac = request.args.get('mac')
    if n is None or not (0 <= n < 225):
        abort(404)
    
    # TODO: Add your actual photo chunk logic here
    # For now, return a placeholder so it doesn't crash
    # Replace this with your real pixel data serving code
    return b'\x00' * 512   # 512-byte dummy chunk (adjust to your real image data)

# === GIT SYNC + AUTO-COMPILE ===
def sync_github():
    while True:
        try:
            git_dir = os.path.join(REPO_DIR, '.git')
            if os.path.exists(git_dir):
                repo = git.Repo(REPO_DIR)
                origin = repo.remotes.origin
                origin.fetch()
                repo.git.reset('--hard', 'origin/main')
                repo.git.checkout('main')
                print(f'[{time.strftime("%H:%M:%S")}] GitHub sync successful')
            else:
                print(f'[{time.strftime("%H:%M:%S")}] Cloning repo...')
                git.Repo.clone_from(REPO_URL, REPO_DIR, branch='main')

            # Compile files
            if os.path.isfile(SECONDARY_PY):
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', SECONDARY_PY, '-o', SECONDARY_MPY])
            if os.path.isfile(TERTIARY_PY):
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', TERTIARY_PY, '-o', TERTIARY_MPY])
            if os.path.isfile(BOOT_PY):
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', BOOT_PY, '-o', BOOT_MPY])

        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] Sync error: {e}')
        time.sleep(SYNC_INTERVAL)

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

@app.route('/tertiary.mpy')
def serve_tertiary_mpy():
    if not os.path.isfile(TERTIARY_MPY): abort(404)
    return send_file(TERTIARY_MPY, mimetype='application/octet-stream')

@app.route('/secondary.py')
def serve_secondary_py():
    if not os.path.isfile(SECONDARY_PY): abort(404)
    return send_file(SECONDARY_PY, mimetype='text/plain')

@app.route('/boot.py')
def serve_boot_py():
    if not os.path.isfile(BOOT_PY): abort(404)
    return send_file(BOOT_PY, mimetype='text/plain')

@app.route('/tertiary.py')
def serve_tertiary_py():
    if not os.path.isfile(TERTIARY_PY): abort(404)
    return send_file(TERTIARY_PY, mimetype='text/plain')

@app.route('/')
def index():
    return """
    <h1>XH-C2X Update Server</h1>
    <p>All endpoints active.</p>
    <a href="/secondary.mpy">/secondary.mpy</a><br>
    <a href="/boot.mpy">/boot.mpy</a><br>
    <a href="/time">/time</a><br>
    <a href="/rank">/rank</a>
    """

if __name__ == '__main__':
    threading.Thread(target=sync_github, daemon=True).start()
    threading.Thread(target=fetch_data, daemon=True).start()
    print("✅ Full merged XH-C2X server starting on port 9019...")
    app.run(host='0.0.0.0', port=9019, debug=False)
