#!/usr/bin/env python3
"""
CircleScreen Web Uploader — port 9468
Mobile + desktop friendly UI that mirrors the Flutter circlescreen-app:
  - Screen selection + PIN login
  - Upload photos (circular 240×240 crop for displays)
  - Gallery list / preview / delete
  - Session-based auth (protects filesystem paths)

Writes full-resolution images under circle_displays/photos/*_full_photos
and circular crops under both circle_displays and x_mas_gift device folders
so ESP32 circle screens (xmas_photos.py) see new photos.
"""
from __future__ import annotations

import os
import secrets
import functools
from datetime import datetime
from io import BytesIO

from flask import (
    Flask,
    request,
    session,
    redirect,
    url_for,
    render_template,
    jsonify,
    send_from_directory,
    flash,
    abort,
)
from PIL import Image, ImageDraw, ImageOps
from werkzeug.utils import secure_filename
from werkzeug.security import safe_join

app = Flask(__name__)

# Persistent secret so sessions survive restarts (not hardcoded in repo)
_SECRET_PATH = os.path.join(os.path.dirname(__file__), ".session_secret")
if os.path.isfile(_SECRET_PATH):
    with open(_SECRET_PATH, "rb") as f:
        app.secret_key = f.read()
else:
    app.secret_key = secrets.token_bytes(32)
    with open(_SECRET_PATH, "wb") as f:
        f.write(app.secret_key)
    try:
        os.chmod(_SECRET_PATH, 0o600)
    except OSError:
        pass

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,  # 32 MB
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14,  # 14 days
)

# Same PINs as circlescreens_server / Flutter app
PINS = {
    "pattie": "1234",
    "melanie": "2026",
    "robbins": "6767",
    "home": "5324",
    "brufam": "5500",
}

DISPLAY_NAMES = {
    "home": "Preston & Willoh",
    "pattie": "Pattie",
    "melanie": "Rob & Melanie",
    "robbins": "Arwyn & Bella",
    "brufam": "Douglas & Shari",
}

# App storage (matches circlescreens_server.py on :9026)
APP_PHOTOS = "/home/preston/Desktop/circle_displays/photos"
FULL_FOLDERS = {
    "melanie": os.path.join(APP_PHOTOS, "melanie_full_photos"),
    "pattie": os.path.join(APP_PHOTOS, "pattie_full_photos"),
    "robbins": os.path.join(APP_PHOTOS, "robbins_full_photos"),
    "home": os.path.join(APP_PHOTOS, "home_full_photos"),
    "brufam": os.path.join(APP_PHOTOS, "brufam_full_photos"),
}
CROPPED_FOLDERS = {
    "melanie": os.path.join(APP_PHOTOS, "circle_display_2"),
    "pattie": os.path.join(APP_PHOTOS, "circle_display_1"),
    "robbins": os.path.join(APP_PHOTOS, "circle_display_3"),
    "home": os.path.join(APP_PHOTOS, "circle_display_4"),
    "brufam": os.path.join(APP_PHOTOS, "circle_display_5"),
}

# Device feed used by xmas_photos.py / neontetra (ESP32 circle screens)
DEVICE_PHOTOS = "/home/preston/Desktop/x_mas_gift/circle_display/photos"
DEVICE_CROPPED = {
    "pattie": os.path.join(DEVICE_PHOTOS, "circle_display_1"),
    "melanie": os.path.join(DEVICE_PHOTOS, "circle_display_2"),
    "robbins": os.path.join(DEVICE_PHOTOS, "circle_display_3"),
    "home": os.path.join(DEVICE_PHOTOS, "circle_display_4"),
    # brufam has no matching device dir in x_mas_gift yet
}

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

for folder in list(FULL_FOLDERS.values()) + list(CROPPED_FOLDERS.values()):
    os.makedirs(folder, exist_ok=True)
for folder in DEVICE_CROPPED.values():
    if folder:
        os.makedirs(folder, exist_ok=True)


def create_circular_crop(input_stream, output_path: str) -> None:
    with Image.open(input_stream) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGBA")
        img = ImageOps.fit(img, (240, 240), Image.LANCZOS)
        mask = Image.new("L", (240, 240), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 240, 240), fill=255)
        circular = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
        circular.paste(img, (0, 0), mask)
        background = Image.new("RGB", (240, 240), (0, 0, 0))
        background.paste(circular, mask=circular.split()[3])
        background.save(output_path, "JPEG", quality=95)


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        user = session.get("user")
        if not user or user not in PINS:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def current_user() -> str | None:
    u = session.get("user")
    return u if u in PINS else None


def list_photos(user: str) -> list[str]:
    folder = CROPPED_FOLDERS[user]
    if not os.path.isdir(folder):
        return []
    files = [
        f
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
        and os.path.splitext(f.lower())[1] in ALLOWED_EXT
    ]
    files.sort(reverse=True)
    return files


def safe_filename_in_user(user: str, filename: str) -> str | None:
    """Resolve a user photo path; reject path traversal."""
    if user not in FULL_FOLDERS:
        return None
    name = os.path.basename(filename)
    if name != filename or ".." in name or name.startswith("."):
        return None
    # Prefer full-res for serving to browsers
    full = os.path.join(FULL_FOLDERS[user], name)
    if os.path.isfile(full):
        return full
    cropped = os.path.join(CROPPED_FOLDERS[user], name)
    if os.path.isfile(cropped):
        return cropped
    return None


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("home"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user() and request.method == "GET":
        return redirect(url_for("home"))

    error = None
    selected = request.form.get("user") or request.args.get("user") or ""

    if request.method == "POST":
        user = (request.form.get("user") or "").strip().lower()
        pin = (request.form.get("pin") or "").strip()
        if user not in PINS:
            error = "Select a screen"
        elif pin != PINS[user]:
            error = "Wrong PIN — try again"
        else:
            session.clear()
            session.permanent = True
            session["user"] = user
            session["display_name"] = DISPLAY_NAMES.get(user, user)
            flash(f"Connected as {session['display_name']}", "ok")
            nxt = request.args.get("next") or url_for("home")
            if not nxt.startswith("/"):
                nxt = url_for("home")
            return redirect(nxt)
        selected = user

    return render_template(
        "login.html",
        users=[(u, DISPLAY_NAMES.get(u, u)) for u in PINS],
        selected=selected,
        error=error,
    )


@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    flash("Signed out", "ok")
    return redirect(url_for("login"))


@app.route("/home")
@login_required
def home():
    user = current_user()
    photos = list_photos(user)
    return render_template(
        "home.html",
        user=user,
        display_name=session.get("display_name", user),
        photo_count=len(photos),
        preview=photos[0] if photos else None,
    )


@app.route("/gallery")
@login_required
def gallery():
    user = current_user()
    photos = list_photos(user)
    return render_template(
        "gallery.html",
        user=user,
        display_name=session.get("display_name", user),
        photos=photos,
    )


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    user = current_user()
    files = request.files.getlist("images")
    if not files or all(not f.filename for f in files):
        flash("No images selected", "err")
        return redirect(url_for("home"))

    success = 0
    fail = 0
    for file in files:
        if not file or not file.filename:
            continue
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in ALLOWED_EXT:
            fail += 1
            continue
        try:
            data = file.read()
            if not data:
                fail += 1
                continue
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            fn = f"{ts}.jpg"
            full_path = os.path.join(FULL_FOLDERS[user], fn)
            crop_path = os.path.join(CROPPED_FOLDERS[user], fn)
            with open(full_path, "wb") as out:
                out.write(data)
            create_circular_crop(BytesIO(data), crop_path)
            # Mirror crop to ESP device folder used by xmas_photos.py
            dev = DEVICE_CROPPED.get(user)
            if dev:
                os.makedirs(dev, exist_ok=True)
                create_circular_crop(BytesIO(data), os.path.join(dev, fn))
            success += 1
            print(f"[upload] {user} → {fn}")
        except Exception as e:
            print(f"[upload] error {user}: {e}")
            fail += 1

    if fail == 0:
        flash(f"Uploaded {success} photo(s) 🎉", "ok")
    else:
        flash(f"Uploaded {success}, failed {fail}", "err")
    return redirect(url_for("gallery" if success else "home"))


@app.route("/delete/<path:filename>", methods=["POST"])
@login_required
def delete_photo(filename):
    user = current_user()
    name = os.path.basename(filename)
    if name != filename:
        abort(400)
    deleted = False
    for folder in (
        FULL_FOLDERS[user],
        CROPPED_FOLDERS[user],
        DEVICE_CROPPED.get(user),
    ):
        if not folder:
            continue
        path = os.path.join(folder, name)
        # Ensure path stays inside folder
        if os.path.commonpath([os.path.abspath(folder), os.path.abspath(path)]) != os.path.abspath(
            folder
        ):
            continue
        if os.path.isfile(path):
            os.remove(path)
            deleted = True
    if deleted:
        flash("Deleted", "ok")
    else:
        flash("Not found", "err")
    return redirect(url_for("gallery"))


@app.route("/img/<user>/<path:filename>")
@login_required
def serve_img(user, filename):
    """Serve images only for the logged-in user (or reject)."""
    me = current_user()
    if user != me:
        abort(403)
    path = safe_filename_in_user(user, filename)
    if not path:
        abort(404)
    directory, name = os.path.dirname(path), os.path.basename(path)
    return send_from_directory(directory, name)


# Optional JSON API compatible with mobile app (session cookie OR can add JWT later)
@app.route("/api/list")
@login_required
def api_list():
    return jsonify(list_photos(current_user()))


@app.route("/api/me")
@login_required
def api_me():
    u = current_user()
    return jsonify({"user": u, "display_name": DISPLAY_NAMES.get(u, u)})


if __name__ == "__main__":
    print("CircleScreen Web Uploader")
    print("  http://0.0.0.0:9468")
    print("  Users:", ", ".join(f"{u}" for u in PINS))
    app.run(host="0.0.0.0", port=9468, debug=False)
