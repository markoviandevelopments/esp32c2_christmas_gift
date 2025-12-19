# server.py - Reliable HTTP server for ESP32-C2 updates
# Automatically compiles secondary.py to secondary.mpy after Git sync
from flask import Flask, send_file, abort
import threading
import time
import git
import os
import subprocess

app = Flask(__name__)

# === CONFIGURATION ===
REPO_DIR = '/home/preston/Desktop/x_mas_gift'  # Folder for the cloned repo
REPO_URL = 'https://github.com/markoviandevelopments/esp32c2_christmas_gift.git'
SYNC_INTERVAL = 30  # Sync every 30 seconds

# Path to your mpy-cross compiler (update if different)
MPY_CROSS_PATH = '/home/preston/micropython/mpy-cross/build/mpy-cross'

SECONDARY_PY = os.path.join(REPO_DIR, 'secondary.py')
SECONDARY_MPY = os.path.join(REPO_DIR, 'secondary.mpy')

# Background Git sync + auto-compile to .mpy
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
                print(f'[{time.strftime("%H:%M:%S")}] GitHub sync successful (fetch + reset)')
            else:
                print(f'[{time.strftime("%H:%M:%S")}] No .git found. Cloning repo...')
                git.Repo.clone_from(REPO_URL, REPO_DIR, branch='main')
                print(f'[{time.strftime("%H:%M:%S")}] Initial clone complete')

            # Auto-compile secondary.py → secondary.mpy after sync
            if os.path.isfile(SECONDARY_PY):
                print(f'[{time.strftime("%H:%M:%S")}] Compiling secondary.py to secondary.mpy...')
                result = subprocess.run([
                    MPY_CROSS_PATH,
                    '-march=rv32imc',
                    SECONDARY_PY,
                    '-o', SECONDARY_MPY
                ], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f'[{time.strftime("%H:%M:%S")}] Compilation successful ({os.path.getsize(SECONDARY_MPY)} bytes)')
                else:
                    print(f'[{time.strftime("%H:%M:%S")}] Compilation failed: {result.stderr}')
            else:
                print(f'[{time.strftime("%H:%M:%S")}] secondary.py not found - skipping compile')

        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] Sync/compile error: {e}')

        time.sleep(SYNC_INTERVAL)

@app.route('/')
def index():
    return "XH-C2X Update Server – ready! Serving secondary.mpy (compiled)"

@app.route('/secondary.py')
def serve_secondary_py():
    if not os.path.isfile(SECONDARY_PY):
        print(f"ERROR: secondary.py not found at {SECONDARY_PY}")
        abort(404)
    print(f"Serving secondary.py ({os.path.getsize(SECONDARY_PY)} bytes)")
    return send_file(SECONDARY_PY, mimetype='text/plain')

@app.route('/secondary.mpy')
def serve_secondary_mpy():
    if not os.path.isfile(SECONDARY_MPY):
        print(f"ERROR: secondary.mpy not found at {SECONDARY_MPY} - trigger a sync or compile manually")
        abort(404)
    print(f"Serving secondary.mpy ({os.path.getsize(SECONDARY_MPY)} bytes)")
    return send_file(SECONDARY_MPY, mimetype='application/octet-stream')

if __name__ == '__main__':
    # Start sync + compile thread
    threading.Thread(target=sync_github, daemon=True).start()
    print("XH-C2X Update Server starting...")
    print(f" Serving from: {REPO_DIR}")
    print(" http://0.0.0.0:9019/secondary.mpy  (primary)")
    print(" http://0.0.0.0:9019/secondary.py   (fallback)")
    app.run(host='0.0.0.0', port=9019, debug=False)
