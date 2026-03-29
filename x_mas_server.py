# server.py - Reliable HTTP server for ESP32-C2 updates
# Automatically compiles secondary.py AND tertiary.py to .mpy after Git sync
from flask import Flask, send_file, abort, request
import threading
import time
import git
import os
import subprocess

app = Flask(__name__)

# === CONFIGURATION ===
REPO_DIR = '/home/preston/Desktop/x_mas_gift' # Folder for the cloned repo
REPO_URL = 'https://github.com/markoviandevelopments/esp32c2_christmas_gift.git'
SYNC_INTERVAL = 300000 # Sync every 30 seconds
MPY_CROSS_PATH = '/home/preston/micropython/mpy-cross/build/mpy-cross'

# Files to handle
SECONDARY_PY = os.path.join(REPO_DIR, 'secondary.py')
SECONDARY_MPY = os.path.join(REPO_DIR, 'secondary.mpy')
BOOT_PY = os.path.join(REPO_DIR, 'boot.py')
BOOT_MPY = os.path.join(REPO_DIR, 'boot.mpy')
TERTIARY_PY = os.path.join(REPO_DIR, 'tertiary.py')
TERTIARY_MPY = os.path.join(REPO_DIR, 'tertiary.mpy')

# Background Git sync + auto-compile
def sync_github():
    while True:
        try:
            git_dir = os.path.join(REPO_DIR, '.git')
            if os.path.exists(git_dir):
                repo = git.Repo(REPO_DIR)
                if 'origin' not in repo.remotes:
                    repo.create_remote('origin', REPO_URL)
                origin = repo.remotes.origin
                origin.fetch()
                repo.git.reset('--hard', 'origin/main')
                repo.git.checkout('main')
                print(f'[{time.strftime("%H:%M:%S")}] GitHub sync successful')
            else:
                print(f'[{time.strftime("%H:%M:%S")}] No .git found. Cloning repo...')
                git.Repo.clone_from(REPO_URL, REPO_DIR, branch='main')
            # Compile secondary
            if os.path.isfile(SECONDARY_PY):
                print(f'[{time.strftime("%H:%M:%S")}] Compiling secondary.py...')
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', SECONDARY_PY, '-o', SECONDARY_MPY])
            # Compile tertiary
            if os.path.isfile(TERTIARY_PY):
                print(f'[{time.strftime("%H:%M:%S")}] Compiling tertiary.py...')
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', TERTIARY_PY, '-o', TERTIARY_MPY])
            # Compile boot
            if os.path.isfile(BOOT_PY):
                print(f'[{time.strftime("%H:%M:%S")}] Compiling boot.py...')
                subprocess.run([MPY_CROSS_PATH, '-march=rv32imc', BOOT_PY, '-o', BOOT_MPY])
        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] Sync error: {e}')
        time.sleep(SYNC_INTERVAL)

# === NEW /update ENDPOINT FOR REMOTE ESP32 UPDATES ===
@app.route('/update')
def serve_update():
    mac = request.args.get('mac')
    file_type = request.args.get('file')
    if mac == '34:98:7A:07:12:B8':
        try:
            if file_type == 'secondary':
                print(f"✅ Serving NEW secondary.py to target MAC {mac}")
                return send_file(SECONDARY_PY, mimetype='text/plain')
            elif file_type == 'tertiary':
                print(f"✅ Serving NEW tertiary.py to target MAC {mac}")
                return send_file(TERTIARY_PY, mimetype='text/plain')
            elif file_type == 'boot':
                print(f"✅ Serving NEW boot.py to target MAC {mac}")
                return send_file(BOOT_PY, mimetype='text/plain')
        except Exception as e:
            print("Update file error:", e)
            abort(404)
    return "wrong mac or no file"

# === Existing routes (unchanged) ===
@app.route('/')
def index():
    return """
    XH-C2X Update Server – ready!<br><br>
    <b>Available files:</b><br>
    • <a href="/secondary.mpy">/secondary.mpy</a><br>
    • <a href="/secondary.py">/secondary.py</a><br>
    • <a href="/tertiary.mpy">/tertiary.mpy</a><br>
    • <a href="/tertiary.py">/tertiary.py</a><br>
    • <a href="/boot.mpy">/boot.mpy</a><br>
    • <a href="/boot.py">/boot.py</a>
    """

@app.route('/secondary.py')
def serve_secondary_py():
    if not os.path.isfile(SECONDARY_PY):
        abort(404)
    return send_file(SECONDARY_PY, mimetype='text/plain')

@app.route('/secondary.mpy')
def serve_secondary_mpy():
    if not os.path.isfile(SECONDARY_MPY):
        abort(404)
    return send_file(SECONDARY_MPY, mimetype='application/octet-stream')

@app.route('/tertiary.py')
def serve_tertiary_py():
    if not os.path.isfile(TERTIARY_PY):
        abort(404)
    return send_file(TERTIARY_PY, mimetype='text/plain')

@app.route('/tertiary.mpy')
def serve_tertiary_mpy():
    if not os.path.isfile(TERTIARY_MPY):
        abort(404)
    return send_file(TERTIARY_MPY, mimetype='application/octet-stream')

@app.route('/boot.py')
def serve_boot_py():
    if not os.path.isfile(BOOT_PY):
        abort(404)
    return send_file(BOOT_PY, mimetype='text/plain')

@app.route('/boot.mpy')
def serve_boot_mpy():
    if not os.path.isfile(BOOT_MPY):
        abort(404)
    return send_file(BOOT_MPY, mimetype='application/octet-stream')

@app.route('/new_boot.py')
def serve_new_boot():
    path = os.path.join(REPO_DIR, 'new_boot.py')
    if not os.path.isfile(path):
        abort(404)
    print(f"Serving new_boot.py")
    return send_file(path, mimetype='text/plain')

@app.route('/new_secondary.mpy')
def serve_new_secondary_mpy():
    path = os.path.join(REPO_DIR, 'new_secondary.mpy')
    if not os.path.isfile(path):
        abort(404)
    print(f"Serving new_secondary.mpy")
    return send_file(path, mimetype='application/octet-stream')

if __name__ == '__main__':
    threading.Thread(target=sync_github, daemon=True).start()
    print("XH-C2X Update Server starting on port 9019...")
    app.run(host='0.0.0.0', port=9019, debug=False)
