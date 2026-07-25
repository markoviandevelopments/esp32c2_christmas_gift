#!/usr/bin/env python3
"""
CircleScreen Web Uploader — port 9468 (PM2: circlescreen_web)

CRITICAL: gallery templates receive plain filename STRINGS only.
Never pass status dicts as `photos` — that breaks <img src>.
"""
from __future__ import annotations

import os
import secrets
import shutil
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

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

DISPLAY_SIZE = 240

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
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 14,
)

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

DEVICE_PHOTOS = "/home/preston/Desktop/x_mas_gift/circle_display/photos"
DEVICE_CROPPED = {
    "pattie": os.path.join(DEVICE_PHOTOS, "circle_display_1"),
    "melanie": os.path.join(DEVICE_PHOTOS, "circle_display_2"),
    "robbins": os.path.join(DEVICE_PHOTOS, "circle_display_3"),
    "home": os.path.join(DEVICE_PHOTOS, "circle_display_4"),
}

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def _user_folders(user: str) -> list[str]:
    folders = [FULL_FOLDERS[user], CROPPED_FOLDERS[user]]
    dev = DEVICE_CROPPED.get(user)
    if dev:
        folders.append(dev)
    return folders


def _display_folders(user: str) -> list[str]:
    folders = [CROPPED_FOLDERS[user]]
    dev = DEVICE_CROPPED.get(user)
    if dev:
        folders.append(dev)
    return folders


def _is_image(name: str) -> bool:
    return os.path.splitext(name.lower())[1] in ALLOWED_EXT


def _safe_name(filename: str) -> str | None:
    # Tolerate accidental dict-string leftovers from old bug
    s = str(filename)
    if s.startswith("{") and "filename" in s:
        # try extract 'filename': 'foo.jpg'
        import re
        m = re.search(r"['\"]filename['\"]\s*:\s*['\"]([^'\"]+)['\"]", s)
        if m:
            s = m.group(1)
    name = os.path.basename(s.replace("\\", "/"))
    if not name or name in (".", "..") or name.startswith(".") or ".." in name:
        return None
    if not _is_image(name):
        return None
    return name


for folder in list(FULL_FOLDERS.values()) + list(CROPPED_FOLDERS.values()):
    os.makedirs(folder, exist_ok=True)
for folder in DEVICE_CROPPED.values():
    os.makedirs(folder, exist_ok=True)


def create_circular_crop(input_stream, output_path: str) -> None:
    with Image.open(input_stream) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGBA")
        img = ImageOps.fit(img, (DISPLAY_SIZE, DISPLAY_SIZE), Image.LANCZOS)
        mask = Image.new("L", (DISPLAY_SIZE, DISPLAY_SIZE), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, DISPLAY_SIZE - 1, DISPLAY_SIZE - 1), fill=255)
        circular = Image.new("RGBA", (DISPLAY_SIZE, DISPLAY_SIZE), (0, 0, 0, 0))
        circular.paste(img, (0, 0), mask)
        background = Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), (0, 0, 0))
        background.paste(circular, mask=circular.split()[3])
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        background.save(output_path, "JPEG", quality=95, optimize=True)


def can_decode_image(source) -> tuple[bool, str]:
    try:
        with Image.open(source) as img:
            img.load()
            w, h = img.size
            if w < 1 or h < 1:
                return False, "Empty image"
            if w * h > 80_000_000:
                return False, f"Too large ({w}×{h})"
        return True, "ok"
    except Exception as e:
        return False, f"Cannot decode: {e}"


def is_display_ready(path: str) -> tuple[bool, str]:
    if not os.path.isfile(path):
        return False, "Missing"
    try:
        with Image.open(path) as img:
            img.load()
            if img.size != (DISPLAY_SIZE, DISPLAY_SIZE):
                return False, f"Size {img.size[0]}×{img.size[1]}"
            if img.mode not in ("RGB", "L"):
                return False, f"Mode {img.mode}"
        return True, "ok"
    except Exception as e:
        return False, str(e)


def write_display_crops(source, user: str, filename: str) -> None:
    create_circular_crop(source, os.path.join(CROPPED_FOLDERS[user], filename))
    dev = DEVICE_CROPPED.get(user)
    if dev:
        if hasattr(source, "seek"):
            source.seek(0)
        create_circular_crop(source, os.path.join(dev, filename))


def repair_display_photo(user: str, name: str) -> tuple[bool, str]:
    sources = []
    full = os.path.join(FULL_FOLDERS[user], name)
    if os.path.isfile(full):
        sources.append(full)
    for folder in _display_folders(user):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            sources.append(path)
    if not sources:
        return False, "No source"
    src = sources[0]
    try:
        out_name = name
        base, ext = os.path.splitext(name)
        if ext.lower() not in (".jpg", ".jpeg"):
            out_name = base + ".jpg"
        with open(src, "rb") as f:
            data = f.read()
        ok, reason = can_decode_image(BytesIO(data))
        if not ok:
            return False, reason
        write_display_crops(BytesIO(data), user, out_name)
        if out_name != name:
            for folder in _display_folders(user):
                old = os.path.join(folder, name)
                if os.path.isfile(old):
                    try:
                        os.remove(old)
                    except OSError:
                        pass
        ready, why = is_display_ready(os.path.join(CROPPED_FOLDERS[user], out_name))
        return (True, out_name if out_name != name else "repaired") if ready else (False, why)
    except Exception as e:
        return False, str(e)


def heal_user_library(user: str) -> dict[str, int]:
    stats = {"checked": 0, "repaired": 0, "failed": 0, "synced": 0}
    names: set[str] = set()
    for folder in _user_folders(user):
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if os.path.isfile(os.path.join(folder, f)) and _is_image(f):
                names.add(f)

    for name in sorted(names):
        stats["checked"] += 1
        crop = os.path.join(CROPPED_FOLDERS[user], name)
        dev_dir = DEVICE_CROPPED.get(user)
        dev = os.path.join(dev_dir, name) if dev_dir else None
        crop_ok = is_display_ready(crop)[0] if os.path.isfile(crop) else False
        dev_ok = is_display_ready(dev)[0] if dev and os.path.isfile(dev) else (dev is None)
        if crop_ok and dev_ok:
            continue
        ok, msg = repair_display_photo(user, name)
        if ok:
            stats["repaired"] += 1
            continue
        if crop_ok and dev and not os.path.isfile(dev):
            try:
                shutil.copy2(crop, dev)
                stats["synced"] += 1
                continue
            except OSError as e:
                msg = str(e)
        stats["failed"] += 1
        print(f"[heal] FAIL {user}/{name}: {msg}")

    if user in DEVICE_CROPPED:
        crop_dir, dev_dir = CROPPED_FOLDERS[user], DEVICE_CROPPED[user]
        try:
            crop_files = {
                f for f in os.listdir(crop_dir)
                if _is_image(f) and os.path.isfile(os.path.join(crop_dir, f))
            }
            dev_files = {
                f for f in os.listdir(dev_dir)
                if _is_image(f) and os.path.isfile(os.path.join(dev_dir, f))
            }
        except OSError:
            return stats
        for name in sorted(crop_files - dev_files):
            src = os.path.join(crop_dir, name)
            if is_display_ready(src)[0]:
                try:
                    shutil.copy2(src, os.path.join(dev_dir, name))
                    stats["synced"] += 1
                except OSError:
                    pass
        for name in sorted(dev_files - crop_files):
            src = os.path.join(dev_dir, name)
            if is_display_ready(src)[0]:
                try:
                    shutil.copy2(src, os.path.join(crop_dir, name))
                    stats["synced"] += 1
                except OSError:
                    pass
            else:
                ok, _ = repair_display_photo(user, name)
                stats["repaired" if ok else "failed"] += 1
    return stats


def list_photos(user: str) -> list[str]:
    """Return plain filename STRINGS only (for templates / <img src>)."""
    names: set[str] = set()
    for folder in _display_folders(user):
        if not os.path.isdir(folder):
            continue
        try:
            for f in os.listdir(folder):
                if os.path.isfile(os.path.join(folder, f)) and _is_image(f):
                    names.add(f)
        except OSError:
            continue

    def sort_key(name: str):
        for folder in _display_folders(user):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                try:
                    return (-os.path.getmtime(path), name)
                except OSError:
                    pass
        return (0, name)

    # Defensive: only strings
    return [str(n) for n in sorted(names, key=sort_key)]


def resolve_photo_path(user: str, filename: str) -> str | None:
    if user not in FULL_FOLDERS:
        return None
    name = _safe_name(filename)
    if not name:
        return None
    for folder in _user_folders(user):
        path = os.path.join(folder, name)
        try:
            if os.path.commonpath(
                [os.path.abspath(folder), os.path.abspath(path)]
            ) != os.path.abspath(folder):
                continue
        except ValueError:
            continue
        if os.path.isfile(path):
            return path
    return None


print("[startup] Healing display libraries…")
for _u in PINS:
    try:
        s = heal_user_library(_u)
        print(
            f"[startup] {_u}: checked={s['checked']} repaired={s['repaired']} "
            f"synced={s['synced']} failed={s['failed']}"
        )
    except Exception as e:
        print(f"[startup] heal error {_u}: {e}")


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


@app.route("/")
def index():
    return redirect(url_for("home" if current_user() else "login"))


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
            if not nxt.startswith("/") or nxt.startswith("//"):
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
    photos = list_photos(user)  # plain strings
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
    # PLAIN STRINGS ONLY — never pass dicts here
    photos = list_photos(user)
    assert all(isinstance(p, str) for p in photos), "photos must be filename strings"
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

    success = fail = 0
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
            ok, _ = can_decode_image(BytesIO(data))
            if not ok:
                fail += 1
                continue
            fn = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".jpg"
            with open(os.path.join(FULL_FOLDERS[user], fn), "wb") as out:
                out.write(data)
            write_display_crops(BytesIO(data), user, fn)
            ready, _ = is_display_ready(os.path.join(CROPPED_FOLDERS[user], fn))
            if not ready:
                for folder in _user_folders(user):
                    p = os.path.join(folder, fn)
                    if os.path.isfile(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
                fail += 1
                continue
            success += 1
            print(f"[upload] {user} → {fn}")
        except Exception as e:
            fail += 1
            print(f"[upload] error {user}: {e}")

    if fail == 0:
        flash(f"Uploaded {success} photo(s) 🎉", "ok")
    else:
        flash(f"Uploaded {success}, failed {fail}", "err")
    return redirect(url_for("gallery" if success else "home"))


@app.route("/delete/<path:filename>", methods=["POST"])
@login_required
def delete_photo(filename):
    user = current_user()
    name = _safe_name(filename)
    if not name:
        abort(400)
    deleted = False
    for folder in _user_folders(user):
        path = os.path.join(folder, name)
        try:
            if os.path.commonpath(
                [os.path.abspath(folder), os.path.abspath(path)]
            ) != os.path.abspath(folder):
                continue
        except ValueError:
            continue
        if os.path.isfile(path):
            try:
                os.remove(path)
                deleted = True
            except OSError as e:
                print(f"[delete] {path}: {e}")
    flash("Deleted" if deleted else "Not found", "ok" if deleted else "err")
    return redirect(url_for("gallery"))


@app.route("/img/<user>/<path:filename>")
@login_required
def serve_img(user, filename):
    me = current_user()
    if user != me:
        abort(403)
    path = resolve_photo_path(user, filename)
    if not path:
        abort(404)
    return send_from_directory(os.path.dirname(path), os.path.basename(path))


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
    print(f"  http://0.0.0.0:9468  (display {DISPLAY_SIZE}×{DISPLAY_SIZE})")
    for u in PINS:
        print(f"    {u}: {len(list_photos(u))} photos")
    app.run(host="0.0.0.0", port=9468, debug=False)
