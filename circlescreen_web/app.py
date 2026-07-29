#!/usr/bin/env python3
"""
CircleScreen Web Uploader — port 9468 (PM2: circlescreen_web)

CRITICAL: gallery templates receive plain filename STRINGS only.
Never pass status dicts as `photos` — that breaks <img src>.

Display folders (app crops + ESP device feeds) may ONLY contain
240×240 RGB JPEG files. Enforcement runs:
  - on every upload
  - at process startup
  - on a background timer (COMB_INTERVAL_SEC)
"""
from __future__ import annotations

import os
import secrets
import shutil
import functools
import threading
import time
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
COMB_INTERVAL_SEC = 10 * 60  # re-scan display folders every 10 minutes
JPEG_QUALITY = 95

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
# Crop folders named to match app display names
CROPPED_FOLDERS = {
    "pattie": os.path.join(APP_PHOTOS, "Pattie"),
    "melanie": os.path.join(APP_PHOTOS, "Rob & Melanie"),
    "robbins": os.path.join(APP_PHOTOS, "Arwyn & Bella"),
    "home": os.path.join(APP_PHOTOS, "Preston & Willoh"),
    "brufam": os.path.join(APP_PHOTOS, "Douglas & Shari"),
}

DEVICE_PHOTOS = "/home/preston/Desktop/x_mas_gift/circle_display/photos"
# ESP32 device feed — same display names as the web app
DEVICE_CROPPED = {
    "pattie": os.path.join(DEVICE_PHOTOS, "Pattie"),
    "melanie": os.path.join(DEVICE_PHOTOS, "Rob & Melanie"),
    "robbins": os.path.join(DEVICE_PHOTOS, "Arwyn & Bella"),
    "home": os.path.join(DEVICE_PHOTOS, "Preston & Willoh"),
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
    """Write a 240×240 RGB JPEG (circular cover-crop on black). Always .jpg content."""
    # Normalize extension to .jpg
    base, ext = os.path.splitext(output_path)
    if ext.lower() not in (".jpg", ".jpeg"):
        output_path = base + ".jpg"
    elif ext.lower() == ".jpeg":
        output_path = base + ".jpg"

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
        # Atomic-ish write: temp then replace
        tmp = output_path + ".tmp"
        background.save(tmp, "JPEG", quality=JPEG_QUALITY, optimize=True)
        os.replace(tmp, output_path)


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
    """
    Strict check for files allowed in display folders:
    - .jpg / .jpeg extension
    - 240×240 pixels
    - RGB mode
    - JPEG format on disk
    """
    if not os.path.isfile(path):
        return False, "Missing"
    ext = os.path.splitext(path.lower())[1]
    if ext not in (".jpg", ".jpeg"):
        return False, f"Not .jpg ({ext or 'no ext'})"
    try:
        with Image.open(path) as img:
            img.load()
            if img.format not in (None, "JPEG"):
                return False, f"Format {img.format} (need JPEG)"
            if img.size != (DISPLAY_SIZE, DISPLAY_SIZE):
                return False, f"Size {img.size[0]}×{img.size[1]} (need {DISPLAY_SIZE}×{DISPLAY_SIZE})"
            if img.mode != "RGB":
                return False, f"Mode {img.mode} (need RGB)"
        return True, "ok"
    except Exception as e:
        return False, str(e)


def enforce_display_file(path: str) -> tuple[str, str]:
    """
    Make one file in a display folder valid, or remove it.

    Returns (action, detail) where action is:
      ok | fixed | renamed | removed | failed
    """
    if not os.path.isfile(path):
        return "failed", "not a file"

    ready, why = is_display_ready(path)
    if ready:
        # Normalize .jpeg → .jpg
        base, ext = os.path.splitext(path)
        if ext.lower() == ".jpeg":
            new_path = base + ".jpg"
            if not os.path.exists(new_path):
                try:
                    os.rename(path, new_path)
                    return "renamed", os.path.basename(new_path)
                except OSError as e:
                    return "failed", str(e)
        return "ok", why

    # Try to re-encode from this file (or remove if not an image)
    try:
        with open(path, "rb") as f:
            data = f.read()
        ok, reason = can_decode_image(BytesIO(data))
        if not ok:
            os.remove(path)
            return "removed", f"unreadable: {reason}"

        base = os.path.splitext(os.path.basename(path))[0]
        # Avoid double-fix when rewriting
        out_name = base + ".jpg"
        out_path = os.path.join(os.path.dirname(path), out_name)
        create_circular_crop(BytesIO(data), out_path)

        # Remove original if it was a different path/name
        if os.path.abspath(path) != os.path.abspath(out_path) and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass

        ready2, why2 = is_display_ready(out_path)
        if ready2:
            return "fixed", out_name
        # Last resort: delete bad output
        if os.path.isfile(out_path):
            os.remove(out_path)
        return "removed", f"still invalid after fix: {why2}"
    except Exception as e:
        try:
            if os.path.isfile(path):
                os.remove(path)
                return "removed", f"error: {e}"
        except OSError:
            pass
        return "failed", str(e)


def comb_display_folder(folder: str) -> dict[str, int]:
    """
    Scan a display folder: every file must be 240×240 RGB JPEG.
    Non-images and unfixable files are removed.
    """
    stats = {"checked": 0, "ok": 0, "fixed": 0, "renamed": 0, "removed": 0, "failed": 0}
    if not os.path.isdir(folder):
        return stats
    try:
        names = list(os.listdir(folder))
    except OSError as e:
        print(f"[comb] cannot list {folder}: {e}")
        return stats

    for name in names:
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        # Skip temp files from atomic writes
        if name.endswith(".tmp"):
            try:
                os.remove(path)
                stats["removed"] += 1
            except OSError:
                pass
            continue

        stats["checked"] += 1
        action, detail = enforce_display_file(path)
        if action == "ok":
            stats["ok"] += 1
        elif action == "fixed":
            stats["fixed"] += 1
            print(f"[comb] fixed {folder}/{name} → {detail}")
        elif action == "renamed":
            stats["renamed"] += 1
            print(f"[comb] renamed {folder}/{name} → {detail}")
        elif action == "removed":
            stats["removed"] += 1
            print(f"[comb] removed {folder}/{name}: {detail}")
        else:
            stats["failed"] += 1
            print(f"[comb] FAIL {folder}/{name}: {detail}")
    return stats


def all_display_folders() -> list[str]:
    """Every folder that must only contain display-ready JPEGs."""
    folders = list(CROPPED_FOLDERS.values()) + list(DEVICE_CROPPED.values())
    # Unique preserve order
    seen = set()
    out = []
    for f in folders:
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def comb_all_display_folders() -> dict[str, int]:
    totals = {"checked": 0, "ok": 0, "fixed": 0, "renamed": 0, "removed": 0, "failed": 0}
    for folder in all_display_folders():
        s = comb_display_folder(folder)
        for k in totals:
            totals[k] += s.get(k, 0)
    return totals


def write_display_crops(source, user: str, filename: str) -> None:
    """Write enforced 240×240 JPEG crops to app + device display folders."""
    # Always store as .jpg
    base, _ext = os.path.splitext(filename)
    filename = base + ".jpg"
    create_circular_crop(source, os.path.join(CROPPED_FOLDERS[user], filename))
    dev = DEVICE_CROPPED.get(user)
    if dev:
        if hasattr(source, "seek"):
            source.seek(0)
        create_circular_crop(source, os.path.join(dev, filename))
    # Immediate verify + repair if something went wrong
    for folder in _display_folders(user):
        path = os.path.join(folder, filename)
        if not is_display_ready(path)[0]:
            action, detail = enforce_display_file(path)
            print(f"[upload-enforce] {path}: {action} {detail}")


def repair_display_photo(user: str, name: str) -> tuple[bool, str]:
    sources = []
    full = os.path.join(FULL_FOLDERS[user], name)
    if os.path.isfile(full):
        sources.append(full)
    for folder in _display_folders(user):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            sources.append(path)
    # Also try stem.jpg / stem with other ext
    base, _ = os.path.splitext(name)
    for folder in _display_folders(user):
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
            path = os.path.join(folder, base + ext)
            if os.path.isfile(path) and path not in sources:
                sources.append(path)

    if not sources:
        return False, "No source"
    src = sources[0]
    try:
        out_name = base + ".jpg"
        with open(src, "rb") as f:
            data = f.read()
        ok, reason = can_decode_image(BytesIO(data))
        if not ok:
            return False, reason
        write_display_crops(BytesIO(data), user, out_name)
        # Remove non-jpg variants of same stem in display folders
        for folder in _display_folders(user):
            for ext in ALLOWED_EXT:
                old = os.path.join(folder, base + ext)
                if ext in (".jpg", ".jpeg"):
                    # keep only the canonical .jpg
                    if ext == ".jpeg" and os.path.isfile(old):
                        try:
                            os.remove(old)
                        except OSError:
                            pass
                    continue
                if os.path.isfile(old):
                    try:
                        os.remove(old)
                    except OSError:
                        pass
        ready, why = is_display_ready(os.path.join(CROPPED_FOLDERS[user], out_name))
        return (True, out_name) if ready else (False, why)
    except Exception as e:
        return False, str(e)


def heal_user_library(user: str) -> dict[str, int]:
    """Comb display folders for user, then mirror missing crops between app/device."""
    stats = {"checked": 0, "repaired": 0, "failed": 0, "synced": 0, "removed": 0}

    # 1) Enforce every file already in display folders
    for folder in _display_folders(user):
        s = comb_display_folder(folder)
        stats["checked"] += s["checked"]
        stats["repaired"] += s["fixed"] + s["renamed"]
        stats["removed"] += s["removed"]
        stats["failed"] += s["failed"]

    # 2) Rebuild crops from full-res originals that have no valid display crop
    crop_dir = CROPPED_FOLDERS[user]
    full_dir = FULL_FOLDERS[user]
    if os.path.isdir(full_dir):
        try:
            full_names = [
                f for f in os.listdir(full_dir)
                if os.path.isfile(os.path.join(full_dir, f)) and _is_image(f)
            ]
        except OSError:
            full_names = []
        for name in full_names:
            base = os.path.splitext(name)[0]
            crop_jpg = os.path.join(crop_dir, base + ".jpg")
            if is_display_ready(crop_jpg)[0]:
                continue
            ok, msg = repair_display_photo(user, name)
            stats["checked"] += 1
            if ok:
                stats["repaired"] += 1
            else:
                stats["failed"] += 1
                print(f"[heal] FAIL {user}/{name}: {msg}")

    # 3) Sync valid crops app ↔ device
    if user in DEVICE_CROPPED:
        crop_dir, dev_dir = CROPPED_FOLDERS[user], DEVICE_CROPPED[user]
        try:
            crop_files = {
                f for f in os.listdir(crop_dir)
                if os.path.isfile(os.path.join(crop_dir, f)) and is_display_ready(os.path.join(crop_dir, f))[0]
            }
            dev_files = {
                f for f in os.listdir(dev_dir)
                if os.path.isfile(os.path.join(dev_dir, f)) and is_display_ready(os.path.join(dev_dir, f))[0]
            }
        except OSError:
            return stats
        for name in sorted(crop_files - dev_files):
            try:
                shutil.copy2(os.path.join(crop_dir, name), os.path.join(dev_dir, name))
                # re-enforce after copy (copy should already be valid)
                enforce_display_file(os.path.join(dev_dir, name))
                stats["synced"] += 1
            except OSError:
                pass
        for name in sorted(dev_files - crop_files):
            try:
                shutil.copy2(os.path.join(dev_dir, name), os.path.join(crop_dir, name))
                enforce_display_file(os.path.join(crop_dir, name))
                stats["synced"] += 1
            except OSError:
                pass
    return stats


def comb_loop():
    """Background: periodically enforce display-folder invariants."""
    while True:
        time.sleep(COMB_INTERVAL_SEC)
        try:
            totals = comb_all_display_folders()
            # Also heal each user (sync + full-res rebuilds)
            for u in PINS:
                heal_user_library(u)
            print(
                f"[comb] periodic: checked={totals['checked']} ok={totals['ok']} "
                f"fixed={totals['fixed']} renamed={totals['renamed']} "
                f"removed={totals['removed']} failed={totals['failed']}"
            )
        except Exception as e:
            print(f"[comb] loop error: {e}")


def list_photos(user: str) -> list[str]:
    """Return plain filename STRINGS of display-ready photos only."""
    names: set[str] = set()
    for folder in _display_folders(user):
        if not os.path.isdir(folder):
            continue
        try:
            for f in os.listdir(folder):
                path = os.path.join(folder, f)
                if os.path.isfile(path) and is_display_ready(path)[0]:
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

    return [str(n) for n in sorted(names, key=sort_key)]


def resolve_photo_path(user: str, filename: str) -> str | None:
    """
    Resolve a photo for the web UI.

    Prefer display-ready 240×240 crops (what the circle screens show), not the
    full-resolution originals kept under *_full_photos.
    Order: app crop → device crop → full-res fallback.
    """
    if user not in FULL_FOLDERS:
        return None
    name = _safe_name(filename)
    if not name:
        return None

    folders = list(_display_folders(user))
    # Full-res only as last resort (should rarely be needed for gallery)
    folders.append(FULL_FOLDERS[user])

    for folder in folders:
        if not folder:
            continue
        path = os.path.join(folder, name)
        try:
            if os.path.commonpath(
                [os.path.abspath(folder), os.path.abspath(path)]
            ) != os.path.abspath(folder):
                continue
        except ValueError:
            continue
        if os.path.isfile(path):
            # Prefer a path that is actually display-ready when available
            if folder == FULL_FOLDERS[user] or is_display_ready(path)[0]:
                return path
            # non-ready crop: keep looking for a ready one, else use this later
    # Second pass: any existing file in display folders (even if not ready)
    for folder in _display_folders(user):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    full = os.path.join(FULL_FOLDERS[user], name)
    if os.path.isfile(full):
        return full
    return None


print("[startup] Enforcing 240×240 RGB JPEG in all display folders…")
try:
    totals = comb_all_display_folders()
    print(
        f"[startup] comb: checked={totals['checked']} ok={totals['ok']} "
        f"fixed={totals['fixed']} renamed={totals['renamed']} "
        f"removed={totals['removed']} failed={totals['failed']}"
    )
except Exception as e:
    print(f"[startup] comb error: {e}")

for _u in PINS:
    try:
        s = heal_user_library(_u)
        print(
            f"[startup] {_u}: checked={s['checked']} repaired={s['repaired']} "
            f"synced={s['synced']} removed={s.get('removed', 0)} failed={s['failed']}"
        )
    except Exception as e:
        print(f"[startup] heal error {_u}: {e}")

# Background periodic comb (also started when run under PM2 via import)
_comb_thread_started = False


def _ensure_comb_thread():
    global _comb_thread_started
    if _comb_thread_started:
        return
    _comb_thread_started = True
    t = threading.Thread(target=comb_loop, name="display-folder-comb", daemon=True)
    t.start()
    print(f"[startup] comb thread every {COMB_INTERVAL_SEC}s")


_ensure_comb_thread()


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
            # Always produce enforced 240×240 RGB JPEG in display folders
            write_display_crops(BytesIO(data), user, fn)

            crop_path = os.path.join(CROPPED_FOLDERS[user], fn)
            dev_path = None
            if user in DEVICE_CROPPED:
                dev_path = os.path.join(DEVICE_CROPPED[user], fn)

            crop_ok = is_display_ready(crop_path)[0]
            dev_ok = is_display_ready(dev_path)[0] if dev_path else True
            if not crop_ok or not dev_ok:
                # Final force-enforce pass
                if os.path.isfile(crop_path):
                    enforce_display_file(crop_path)
                if dev_path and os.path.isfile(dev_path):
                    enforce_display_file(dev_path)
                crop_ok = is_display_ready(crop_path)[0]
                dev_ok = is_display_ready(dev_path)[0] if dev_path else True

            if not crop_ok or not dev_ok:
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
            print(f"[upload] {user} → {fn} (240×240 JPEG ✓)")
        except Exception as e:
            fail += 1
            print(f"[upload] error {user}: {e}")

    # Comb this user's display folders after upload so nothing bad remains
    try:
        for folder in _display_folders(user):
            comb_display_folder(folder)
    except Exception as e:
        print(f"[upload] post-comb error: {e}")

    if fail == 0:
        flash(f"Uploaded {success} photo(s) as 240×240 JPEG 🎉", "ok")
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


@app.route("/api/comb", methods=["POST"])
@login_required
def api_comb():
    """Force an immediate comb of all display folders."""
    totals = comb_all_display_folders()
    for u in PINS:
        heal_user_library(u)
    return jsonify({"ok": True, "stats": totals})


if __name__ == "__main__":
    print("CircleScreen Web Uploader")
    print(f"  http://0.0.0.0:9468  (display {DISPLAY_SIZE}×{DISPLAY_SIZE} JPEG only)")
    for u in PINS:
        print(f"    {u}: {len(list_photos(u))} photos")
    app.run(host="0.0.0.0", port=9468, debug=False)
