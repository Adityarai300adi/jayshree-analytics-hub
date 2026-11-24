"""
Jayshree Polymers India Pvt. Ltd. - Analytics Hub
Flask + SQLite backend: authentication, user management, an activity log and
password-protected workbook unlocking.

Workbooks are NEVER stored. The browser reads the Excel file you pick and builds the
dashboard from it (static/index.html); the server only keeps who analyzed which file name.
"""
import base64
import configparser
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, Response, g, jsonify, redirect, request, send_file,
                   send_from_directory, session)
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import msoffcrypto
except ImportError:  # decryption endpoint reports a clear message
    msoffcrypto = None

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("JP_DATA_DIR", os.path.join(BASE, "data"))
OLD_UPLOADS = os.path.join(DATA, "uploads")  # created by older versions; removed on start
DB_PATH = os.path.join(DATA, "hub.db")
MAX_MB = int(os.environ.get("JP_MAX_MB", "200"))
ADMIN_PASSWORD_ENV = os.environ.get("JP_ADMIN_PASSWORD", "")  # optional: create the first admin from this instead of the setup page

os.makedirs(DATA, exist_ok=True)


def _secret_key():
    path = os.path.join(DATA, "secret.key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


RECOVERY_FILE = os.path.join(DATA, "recovery_key.txt")


def _make_recovery_key():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(chars) for _ in range(16))
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def recovery_key():
    """Master recovery key, stored in data/recovery_key.txt (created on first run)."""
    if not os.path.exists(RECOVERY_FILE):
        with open(RECOVERY_FILE, "w") as f:
            f.write(_make_recovery_key() + "\n")
        print(f"Recovery key created: {RECOVERY_FILE}")
    with open(RECOVERY_FILE) as f:
        return f.read().strip()


def _norm_key(k):
    return re.sub(r"[^A-Z0-9]", "", str(k).upper())


app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="/static")
app.config.update(
    SECRET_KEY=_secret_key(),
    MAX_CONTENT_LENGTH=MAX_MB * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get("JP_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes", "on"),
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

# ---------------------------------------------------------------- database
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user','admin')),
            must_change INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            filename TEXT NOT NULL,
            sheets INTEGER,
            master TEXT,
            at TEXT NOT NULL
        );
        DROP TABLE IF EXISTS uploads;
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    for name, ddl in (("email", "TEXT"), ("phone", "TEXT"), ("email_verified", "INTEGER NOT NULL DEFAULT 0"),
                      ("phone_verified", "INTEGER NOT NULL DEFAULT 0"), ("pwd_version", "INTEGER NOT NULL DEFAULT 0")):
        if name not in cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
    conn.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone) WHERE phone IS NOT NULL;
        CREATE TABLE IF NOT EXISTS pending (token TEXT PRIMARY KEY, payload TEXT NOT NULL, expires_at REAL NOT NULL);
        """
    )
    if ADMIN_PASSWORD_ENV and conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                     ("admin", generate_password_hash(ADMIN_PASSWORD_ENV), "admin", now()))
        print("First run: created user 'admin' from JP_ADMIN_PASSWORD.")
    conn.commit()
    conn.close()
    if os.path.isdir(OLD_UPLOADS):  # earlier versions kept copies of uploaded workbooks
        count = sum(len(files) for _, _, files in os.walk(OLD_UPLOADS))
        shutil.rmtree(OLD_UPLOADS, ignore_errors=True)
        print(f"Removed {count} stored workbook(s) left by an older version. Files are no longer kept.")


init_db()
recovery_key()


# ---------------------------------------------------------------- helpers
def err(message, status=400):
    return jsonify(error=message), status


def current_user():
    uid = session.get("uid")
    if uid is None:
        return None
    user = db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if user is None or session.get("pv", 0) != user["pwd_version"]:  # password changed elsewhere -> log out
        return None
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if user is None:
            return err("Please log in.", 401)
        g.user = user
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if g.user["role"] != "admin":
            return err("Administrator access required.", 403)
        return fn(*a, **kw)
    return wrapper


_failures = {}  # ip -> (count, first_failure_time)


def _blocked(ip):
    count, first = _failures.get(ip, (0, 0))
    if count >= 5 and time.time() - first < 300:
        return True
    if time.time() - first >= 300:
        _failures.pop(ip, None)
    return False


def _fail(ip):
    count, first = _failures.get(ip, (0, time.time()))
    _failures[ip] = (count + 1, first)


def user_json(u):
    return {"id": u["id"], "username": u["username"], "role": u["role"], "must_change": bool(u["must_change"]),
            "email": u["email"], "phone": u["phone"]}


# ---------------------------------------------------------------- pages
VENDOR_CDN = {
    "xlsx.full.min.js": "https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js",
    "chart.umd.js": "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js",
    "firebase-app-compat.js": "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js",
    "firebase-auth-compat.js": "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth-compat.js",
}
INDEX_CANDIDATES = [os.path.join(BASE, "static", "index.html"), os.path.join(BASE, "index.html")]

MISSING_PAGE = """<!doctype html><meta charset="utf-8"><title>Setup problem</title>
<body style="font:16px/1.6 Segoe UI,Arial;max-width:680px;margin:60px auto;padding:0 20px">
<h2>The server is running, but the dashboard page (index.html) was not found</h2>
<p>Put <b>index.html</b> inside the <b>static</b> folder, next to <b>app.py</b>:</p>
<pre style="background:#f2f2f2;padding:14px;border-radius:8px">jayshree-hub/
  app.py
  static/
    index.html
    vendor/   (xlsx.full.min.js, chart.umd.js)</pre>
<p>The server looked here:<br><code>%s</code></p>
<p>Then reload this page (Ctrl+F5). You do not need to restart the server.</p></body>"""


def _index_path():
    for path in INDEX_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


@app.get("/")
@app.get("/index.html")
def index():
    path = _index_path()
    if path is None:
        return Response(MISSING_PAGE % INDEX_CANDIDATES[0], status=404, mimetype="text/html")
    return send_file(path, mimetype="text/html")


@app.get("/static/vendor/<name>")
def vendor(name):
    """Serve the bundled libraries; if the vendor folder is missing, fall back to a CDN."""
    folder = os.path.join(BASE, "static", "vendor")
    if os.path.isfile(os.path.join(folder, name)):
        return send_from_directory(folder, name)
    if name in VENDOR_CDN:
        return redirect(VENDOR_CDN[name])
    return Response("Not found", status=404)


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return err("Not found.", 404)
    if request.path.startswith("/static/"):
        return Response("Not found", status=404)
    return redirect("/")  # any mistyped address (e.g. /login, /dashboard) opens the app


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"  # Google/Firebase API keys may be restricted by referrer
    if request.path.startswith("/api/") or request.path in ("/", "/index.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.errorhandler(413)
def too_large(_e):
    return err(f"File too large (limit {MAX_MB} MB).", 413)


# ---------------------------------------------------------------- auth
@app.post("/api/login")
def login():
    ip = request.remote_addr or "?"
    if _blocked(ip):
        return err("Too many failed attempts. Try again in a few minutes.", 429)
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    role = body.get("role")
    user = find_user(username)
    if not user or not check_password_hash(user["password_hash"], password):
        _fail(ip)
        return err("Wrong username or password.", 401)
    if role in ("user", "admin") and user["role"] != role:
        return err(f"This account is not a{'n' if role == 'admin' else ''} {role} account. Switch the login tab.", 403)
    _failures.pop(ip, None)
    _login_session(user)
    return jsonify(user_json(user))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@login_required
def me():
    return jsonify(user_json(g.user))


@app.post("/api/password")
@login_required
def change_password():
    body = request.get_json(silent=True) or {}
    if not check_password_hash(g.user["password_hash"], str(body.get("old", ""))):
        return err("Current password is wrong.", 403)
    new = str(body.get("new", ""))
    problem = check_password(new, g.user["username"])
    if problem:
        return err(problem)
    db().execute("UPDATE users SET password_hash = ?, must_change = 0, pwd_version = pwd_version + 1 WHERE id = ?",
                 (generate_password_hash(new), g.user["id"]))
    db().commit()
    session["pv"] = g.user["pwd_version"] + 1  # keep this browser logged in; other sessions end
    return jsonify(ok=True)


@app.post("/api/forgot")
def forgot_password():
    """Reset a password using the recovery key stored in data/recovery_key.txt."""
    ip = request.remote_addr or "?"
    if _blocked(ip):
        return err("Too many failed attempts. Try again in a few minutes.", 429)
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    new = str(body.get("new", ""))
    problem = check_password(new, username)
    if problem:
        return err(problem)
    user = db().execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    key_ok = hmac.compare_digest(_norm_key(body.get("key", "")), _norm_key(recovery_key()))
    if user is None or not key_ok:
        _fail(ip)
        return err("Username or recovery key is wrong.", 403)
    db().execute("UPDATE users SET password_hash = ?, must_change = 0, pwd_version = pwd_version + 1 WHERE id = ?",
                 (generate_password_hash(new), user["id"]))
    db().commit()
    _failures.pop(ip, None)
    return jsonify(ok=True)


@app.post("/api/decrypt")
@login_required
def decrypt_workbook():
    """Open a password-protected workbook. Nothing is stored; the decrypted bytes are returned."""
    if msoffcrypto is None:
        return err("The server is missing msoffcrypto-tool. Run: pip install msoffcrypto-tool", 501)
    f = request.files.get("file")
    if f is None:
        return err("No file received.")
    try:
        office = msoffcrypto.OfficeFile(io.BytesIO(f.read()))
        if not office.is_encrypted():
            return err("This file is not password-protected.")
        office.load_key(password=request.form.get("password", ""))
        out = io.BytesIO()
        office.decrypt(out)
    except msoffcrypto.exceptions.InvalidKeyError:
        return err("WRONG_PW", 403)
    except Exception as exc:  # unsupported or damaged file
        return err(f"Could not decrypt this file: {exc}")
    out.seek(0)
    return send_file(out, mimetype="application/octet-stream")


# ---------------------------------------------------------------- users (admin)
@app.get("/api/users")
@admin_required
def list_users():
    rows = db().execute("SELECT id, username, role, email, phone, email_verified, phone_verified, created_at FROM users ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/users")
@admin_required
def create_user():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    role = body.get("role", "user")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        return err("Username: 3-32 letters, digits, dot, dash or underscore.")
    problem = check_password(password, username)
    if problem:
        return err(problem)
    if role not in ("user", "admin"):
        return err("Role must be user or admin.")
    email, phone = norm_email(body.get("email")), norm_phone(body.get("phone"))
    if email is None or phone is None:
        return err("Check the email address and phone number.")
    try:
        db().execute(
            "INSERT INTO users (username, password_hash, role, email, phone, created_at) VALUES (?,?,?,?,?,?)",
            (username, generate_password_hash(password), role, email or None, phone or None, now()))
        db().commit()
    except sqlite3.IntegrityError:
        return err("That username already exists.", 409)
    return jsonify(ok=True), 201


@app.delete("/api/users/<int:uid>")
@admin_required
def delete_user(uid):
    if uid == g.user["id"]:
        return err("You cannot remove your own account.")
    db().execute("DELETE FROM users WHERE id = ?", (uid,))
    db().commit()
    return jsonify(ok=True)


@app.post("/api/users/<int:uid>/password")
@admin_required
def reset_password(uid):
    new = str((request.get_json(silent=True) or {}).get("new", ""))
    problem = check_password(new)
    if problem:
        return err(problem)
    cur = db().execute("UPDATE users SET password_hash = ?, must_change = 0, pwd_version = pwd_version + 1 WHERE id = ?",
                       (generate_password_hash(new), uid))
    if cur.rowcount == 0:
        return err("User not found.", 404)
    db().commit()
    return jsonify(ok=True)


# ---------------------------------------------------------------- accounts: Google + mobile OTP (Firebase)
# The browser signs the person in with Google (proves an email address) or with an SMS code that Google/Firebase
# sends (proves a mobile number). Firebase returns a signed "ID token"; this server checks its signature with
# Google's public keys and only then trusts the email / mobile number inside it.
USERNAME_RE = re.compile(r"[A-Za-z0-9_.-]{3,32}")
EMAIL_RE = re.compile(r"[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}")
FIREBASE_CERTS_URL = os.environ.get(
    "JP_FIREBASE_CERTS_URL", "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com")
CONFIG_PATH = os.environ.get("JP_CONFIG", os.path.join(BASE, "config.ini"))
CONFIG_TEMPLATE = """# Jayshree Analytics Hub - settings
#
# Fill in the details below ONCE, save this file, then refresh the website.
# You do not need to restart the server. Do not put quotes around values.
#
# Google sign-in and mobile OTP are provided by Firebase (a free Google service).
# Steps: 1) open https://console.firebase.google.com and create a project
#        2) Build -> Authentication -> Get started -> Sign-in method:
#           turn ON "Google" and turn ON "Phone"
#        3) Project settings (gear icon) -> General -> "Your apps" -> add a Web app (</>)
#        4) copy the four values it shows into the lines below

[firebase]
api_key =
auth_domain =
project_id =
app_id =

[general]
# on = new users can register themselves, off = registration is closed
registration = on
# Added to mobile numbers typed without a country code
country_code = +91
# Only the owner can create the FIRST account (the administrator).
# Write the owner's Google email and/or mobile number (with country code, e.g. +919876543210).
admin_email =
admin_phone =
"""
CONFIG_MAP = {
    "fb_api_key": ("firebase", "api_key"), "fb_auth_domain": ("firebase", "auth_domain"),
    "fb_project_id": ("firebase", "project_id"), "fb_app_id": ("firebase", "app_id"),
    "allow_signup": ("general", "registration"), "default_cc": ("general", "country_code"),
    "admin_email": ("general", "admin_email"), "admin_phone": ("general", "admin_phone"),
}
CONFIG_ENV_MAP = {
    "fb_api_key": "JP_FIREBASE_API_KEY", "fb_auth_domain": "JP_FIREBASE_AUTH_DOMAIN",
    "fb_project_id": "JP_FIREBASE_PROJECT_ID", "fb_app_id": "JP_FIREBASE_APP_ID",
    "allow_signup": "JP_REGISTRATION", "default_cc": "JP_COUNTRY_CODE",
    "admin_email": "JP_ADMIN_EMAIL", "admin_phone": "JP_ADMIN_PHONE",
}
CONFIG_DEFAULTS = {"default_cc": "+91"}
_cfg = {"stamp": None, "parser": None}
_rates = {}       # key -> list of timestamps
_certs = {"keys": {}, "until": 0}
_signer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="jp-reset")


def ensure_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE)
        print(f"Created the settings file: {CONFIG_PATH}")


def _config():
    """config.ini is re-read whenever it is saved, so no restart is needed."""
    try:
        st = os.stat(CONFIG_PATH)
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = None
    if _cfg["parser"] is None or _cfg["stamp"] != stamp:
        parser = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=None)
        if stamp:
            try:
                parser.read(CONFIG_PATH, encoding="utf-8")
            except configparser.Error as exc:
                app.logger.warning("config.ini could not be read: %s", exc)
        _cfg["parser"], _cfg["stamp"] = parser, stamp
    return _cfg["parser"]


def get_setting(key):
    env_key = CONFIG_ENV_MAP.get(key)
    if env_key and env_key in os.environ:
        value = os.environ[env_key].strip()
    else:
        section, option = CONFIG_MAP[key]
        value = _config().get(section, option, fallback="").strip()
    if key == "allow_signup":
        return "0" if value.lower() in ("off", "no", "0", "false") else "1"
    return value or CONFIG_DEFAULTS.get(key, "")


def firebase_config():
    cfg = {"apiKey": get_setting("fb_api_key"), "authDomain": get_setting("fb_auth_domain"),
           "projectId": get_setting("fb_project_id"), "appId": get_setting("fb_app_id")}
    return cfg if cfg["apiKey"] and cfg["authDomain"] and cfg["projectId"] else None


def _rate_ok(key, limit, window):
    t = time.time()
    hits = [x for x in _rates.get(key, []) if t - x < window]
    if len(hits) >= limit:
        _rates[key] = hits
        return False
    hits.append(t)
    _rates[key] = hits
    return True


# ---- checking Firebase ID tokens (RS256 JWT signed by Google)
class TokenError(Exception):
    pass


def _b64u(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _firebase_keys(force=False):
    if force or not _certs["keys"] or time.time() > _certs["until"]:
        try:
            with urllib.request.urlopen(FIREBASE_CERTS_URL, timeout=10) as resp:
                data = json.loads(resp.read())
                age = re.search(r"max-age=(\d+)", resp.headers.get("Cache-Control", ""))
            _certs["keys"] = {kid: x509.load_pem_x509_certificate(pem.encode()).public_key() for kid, pem in data.items()}
            _certs["until"] = time.time() + (int(age.group(1)) if age else 3600)
        except (OSError, ValueError) as exc:
            raise TokenError("Could not reach Google to check the sign-in. Check the internet connection.") from exc
    return _certs["keys"]


def verify_firebase_token(token, max_age=600):
    cfg = firebase_config()
    if cfg is None:
        raise TokenError("Google / mobile verification is not set up yet. The owner must fill in config.ini.")
    try:
        head_b64, body_b64, sig_b64 = token.split(".")
        header, claims, signature = json.loads(_b64u(head_b64)), json.loads(_b64u(body_b64)), _b64u(sig_b64)
    except (ValueError, TypeError) as exc:
        raise TokenError("The sign-in could not be read. Please try again.") from exc
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise TokenError("The sign-in is not valid.")
    key = _firebase_keys().get(header["kid"]) or _firebase_keys(force=True).get(header["kid"])
    if key is None:
        raise TokenError("The sign-in is not valid.")
    try:
        key.verify(signature, f"{head_b64}.{body_b64}".encode(), padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise TokenError("The sign-in is not valid.") from exc
    now_s = time.time()
    try:
        ok = (claims["aud"] == cfg["projectId"] and claims["iss"] == f"https://securetoken.google.com/{cfg['projectId']}"
              and claims["exp"] > now_s and claims["iat"] <= now_s + 60 and claims["auth_time"] <= now_s + 60
              and isinstance(claims["sub"], str) and 0 < len(claims["sub"]) <= 128)
    except (KeyError, TypeError):
        ok = False
    if not ok:
        raise TokenError("The sign-in is not valid or has expired. Please try again.")
    if now_s - claims["auth_time"] > max_age:
        raise TokenError("The sign-in is too old. Please verify again.")
    return claims


def norm_email(value):
    v = str(value or "").strip().lower()
    if not v:
        return ""
    return v if len(v) <= 254 and EMAIL_RE.fullmatch(v) else None


def norm_phone(value):
    s = str(value or "").strip()
    if not s:
        return ""
    digits = re.sub(r"\D", "", s)
    cc = get_setting("default_cc") or "+91"
    if s.startswith("+"):
        num = "+" + digits
    elif s.startswith("00"):
        num = "+" + digits[2:]
    elif len(digits) == 10:
        num = cc + digits
    elif len(digits) == 11 and digits.startswith("0"):
        num = cc + digits[1:]
    else:
        num = "+" + digits
    return num if re.fullmatch(r"\+\d{8,15}", num) else None


def contact_from_claims(claims):
    """("email", address) when Google proved an email, ("sms", +number) when an SMS code proved a mobile number."""
    provider = (claims.get("firebase") or {}).get("sign_in_provider")
    if provider == "google.com" and claims.get("email_verified") is True:
        email = norm_email(claims.get("email"))
        if email:
            return "email", email
    if provider == "phone":
        phone = norm_phone(claims.get("phone_number"))
        if phone:
            return "sms", phone
    raise TokenError("This sign-in does not prove an email address or a mobile number.")


def _verified_contact(body):
    try:
        return contact_from_claims(verify_firebase_token(str(body.get("id_token", "")))), None
    except TokenError as exc:
        return None, err(str(exc), 503 if "not set up" in str(exc) else 400)


def check_password(pw, username=""):
    if len(pw) < 8 or len(pw) > 128:
        return "Password must have 8 to 128 characters."
    if not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        return "Password must contain at least one letter and one number."
    if username and pw.lower() == username.lower():
        return "Password must not be the same as the username."
    return None


def find_user(identifier):
    """Sign-in by username, or by an email address / mobile number that was verified."""
    ident = str(identifier or "").strip()
    if not ident:
        return None
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (ident,)).fetchone()
    if user:
        return user
    email = norm_email(ident) if "@" in ident else None
    if email:
        return conn.execute("SELECT * FROM users WHERE email = ? AND email_verified = 1", (email,)).fetchone()
    if re.fullmatch(r"\+?[\d\s\-]{8,18}", ident):
        phone = norm_phone(ident)
        if phone:
            return conn.execute("SELECT * FROM users WHERE phone = ? AND phone_verified = 1", (phone,)).fetchone()
    return None


def _user_by_contact(channel, value, verified_only=True):
    col = "email" if channel == "email" else "phone"
    sql = f"SELECT * FROM users WHERE {col} = ?" + (f" AND {col}_verified = 1" if verified_only else "")
    return db().execute(sql, (value,)).fetchone()


def _login_session(user):
    session.clear()
    session["uid"] = user["id"]
    session["pv"] = user["pwd_version"]
    session.permanent = True


def mask_email(e):
    name, dom = e.split("@", 1)
    return name[:2] + "***@" + dom if len(name) > 2 else name[:1] + "***@" + dom


def mask_phone(p):
    return p[:3] + "*" * max(len(p) - 6, 0) + p[-3:]


def _users_exist():
    return db().execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


def _owner_ok(channel, value):
    """Before the first account exists only the owner (named in config.ini) may create it."""
    owner_email, owner_phone = get_setting("admin_email").lower(), norm_phone(get_setting("admin_phone")) or ""
    if not (owner_email or owner_phone):
        return True
    return (channel == "email" and value == owner_email) or (channel == "sms" and value == owner_phone)


def _pending_get(token):
    row = db().execute("SELECT * FROM pending WHERE token = ?", (str(token or ""),)).fetchone()
    if row is None or row["expires_at"] < time.time():
        return None
    return json.loads(row["payload"])


def _pending_put(token, data):
    db().execute("INSERT INTO pending (token, payload, expires_at) VALUES (?,?,?) "
                 "ON CONFLICT(token) DO UPDATE SET payload = excluded.payload, expires_at = excluded.expires_at",
                 (token, json.dumps(data), time.time() + 1800))
    db().commit()


def _start_or_extend_pending(token, channel, value):
    """Remember a freshly verified email / mobile number until the person has chosen a username and password."""
    data = _pending_get(token) if token else None
    if data is None:
        token, data = secrets.token_urlsafe(24), {"kind": "register" if _users_exist() else "setup", "email": None, "phone": None}
        db().execute("DELETE FROM pending WHERE expires_at < ?", (time.time(),))
    data["email" if channel == "email" else "phone"] = value
    _pending_put(token, data)
    return token, data


def _pending_reply(token, data):
    return {"ptoken": token, "kind": data["kind"],
            "email": mask_email(data["email"]) if data["email"] else None,
            "phone": mask_phone(data["phone"]) if data["phone"] else None}


@app.get("/api/public-config")
def public_config():
    return jsonify(setup_needed=not _users_exist(), allow_signup=get_setting("allow_signup") == "1",
                   firebase=firebase_config(), default_cc=get_setting("default_cc"))


# ---- Continue with Google / mobile OTP on the sign-in page: signs in a known person, or starts registration
@app.post("/api/firebase/login")
def firebase_login():
    if not _rate_ok("fbl:" + (request.remote_addr or "?"), 40, 3600):
        return err("Too many attempts. Try again later.", 429)
    b = request.get_json(silent=True) or {}
    contact, bad = _verified_contact(b)
    if bad:
        return bad
    channel, value = contact
    user = _user_by_contact(channel, value)
    if user:
        _login_session(user)
        return jsonify(user_json(user))
    label = "Google account" if channel == "email" else "mobile number"
    if _user_by_contact(channel, value, verified_only=False):
        return err(f"This {label} is on an account that is not verified yet. Sign in with your username and password, "
                   "then verify it in My profile.", 409)
    setup = not _users_exist()
    if not setup and get_setting("allow_signup") != "1":
        return err(f"No account uses this {label}, and registration is closed.", 403)
    if setup and not _owner_ok(channel, value):
        return err("Only the owner's email address or mobile number can create the first account.", 403)
    token, data = _start_or_extend_pending(None, channel, value)
    return jsonify(new=True, **_pending_reply(token, data))


# ---- registration: 1) verify email (Google) and/or mobile (SMS code)  2) choose username + password  3) sign in
@app.post("/api/signup/verify")
def signup_verify():
    if not _rate_ok("reg:" + (request.remote_addr or "?"), 40, 3600):
        return err("Too many attempts. Try again later.", 429)
    b = request.get_json(silent=True) or {}
    contact, bad = _verified_contact(b)
    if bad:
        return bad
    channel, value = contact
    setup = not _users_exist()
    if not setup and get_setting("allow_signup") != "1":
        return err("Registration is closed. Please contact the administrator.", 403)
    label = "Google account" if channel == "email" else "mobile number"
    if _user_by_contact(channel, value, verified_only=False):
        return err(f"This {label} is already registered. Please sign in.", 409)
    token = str(b.get("ptoken", ""))
    if setup and _pending_get(token) is None and not _owner_ok(channel, value):
        return err("Only the owner's email address or mobile number can create the first account.", 403)
    token, data = _start_or_extend_pending(token, channel, value)
    return jsonify(ok=True, **_pending_reply(token, data))


@app.post("/api/signup/create")
def signup_create():
    b = request.get_json(silent=True) or {}
    token = str(b.get("ptoken", ""))
    data = _pending_get(token)
    if data is None or not (data["email"] or data["phone"]):
        return err("Please verify your Google account or mobile number first.", 400)
    username, password = str(b.get("username", "")).strip(), str(b.get("password", ""))
    if password != str(b.get("confirm_password", "")):
        return err("The two passwords do not match.")
    problem = (None if USERNAME_RE.fullmatch(username) else "Username: 3-32 letters, digits, dot, dash or underscore.") \
        or check_password(password, username)
    if problem:
        return err(problem)
    conn = db()
    conn.execute("BEGIN IMMEDIATE")
    if data["kind"] == "setup" and conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        conn.rollback()
        return err("Setup is already done. Please sign in.", 409)
    if data["kind"] == "register" and get_setting("allow_signup") != "1":
        conn.rollback()
        return err("Registration is closed. Please contact the administrator.", 403)
    try:
        conn.execute("INSERT INTO users (username, password_hash, role, email, phone, email_verified, phone_verified, created_at) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (username, generate_password_hash(password), "admin" if data["kind"] == "setup" else "user",
                      data["email"], data["phone"], 1 if data["email"] else 0, 1 if data["phone"] else 0, now()))
        conn.execute("DELETE FROM pending WHERE token = ?", (token,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return err("That username is taken. Choose another one.", 409)
    return jsonify(ok=True, username=username), 201  # the person now signs in with the new username and password


# ---- forgot password: prove the email (Google) or mobile (SMS code), then choose a new username/password
@app.post("/api/forgot/verify")
def forgot_verify():
    if not _rate_ok("fp:" + (request.remote_addr or "?"), 30, 3600):
        return err("Too many attempts. Try again later.", 429)
    b = request.get_json(silent=True) or {}
    contact, bad = _verified_contact(b)
    if bad:
        return bad
    channel, value = contact
    user = _user_by_contact(channel, value)
    if user is None:
        return err("No account uses this " + ("Google account." if channel == "email" else "mobile number."), 404)
    return jsonify(ok=True, token=_signer.dumps({"uid": user["id"], "pv": user["pwd_version"]}), username=user["username"])


@app.post("/api/forgot/reset")
def forgot_reset():
    b = request.get_json(silent=True) or {}
    try:
        data = _signer.loads(str(b.get("token", "")), max_age=900)
    except (BadSignature, SignatureExpired):
        return err("This reset session has expired. Start again.", 403)
    user = db().execute("SELECT * FROM users WHERE id = ?", (data["uid"],)).fetchone()
    if user is None or user["pwd_version"] != data["pv"]:
        return err("This reset session has already been used. Start again.", 403)
    new_name = str(b.get("new_username", "")).strip() or user["username"]
    password = str(b.get("new_password", ""))
    if password != str(b.get("confirm_password", "")):
        return err("The two passwords do not match.")
    problem = check_password(password, new_name) or (None if USERNAME_RE.fullmatch(new_name)
                                                    else "Username: 3-32 letters, digits, dot, dash or underscore.")
    if problem:
        return err(problem)
    try:
        db().execute("UPDATE users SET username = ?, password_hash = ?, must_change = 0, pwd_version = pwd_version + 1 WHERE id = ?",
                     (new_name, generate_password_hash(password), user["id"]))
        db().commit()
    except sqlite3.IntegrityError:
        return err("That username is already taken.", 409)
    return jsonify(ok=True, username=new_name)


# ---- my profile
@app.get("/api/profile")
@login_required
def profile():
    u = g.user
    return jsonify(username=u["username"], role=u["role"], email=u["email"], phone=u["phone"],
                   email_verified=bool(u["email_verified"]), phone_verified=bool(u["phone_verified"]))


@app.post("/api/profile/contact")
@login_required
def profile_contact():
    """Add or confirm an email (Google) or mobile number (SMS code) for the signed-in person."""
    b = request.get_json(silent=True) or {}
    contact, bad = _verified_contact(b)
    if bad:
        return bad
    channel, value = contact
    col = "email" if channel == "email" else "phone"
    other = db().execute(f"SELECT id FROM users WHERE {col} = ? AND id != ?", (value, g.user["id"])).fetchone()
    if other:
        return err("This " + ("Google account" if channel == "email" else "mobile number") + " belongs to another account.", 409)
    db().execute(f"UPDATE users SET {col} = ?, {col}_verified = 1 WHERE id = ?", (value, g.user["id"]))
    db().commit()
    return jsonify(ok=True, channel=channel, value=value)


@app.post("/api/profile/contact/remove")
@login_required
def profile_contact_remove():
    channel = (request.get_json(silent=True) or {}).get("channel")
    if channel not in ("email", "sms"):
        return err("Choose email or mobile.")
    col = "email" if channel == "email" else "phone"
    db().execute(f"UPDATE users SET {col} = NULL, {col}_verified = 0 WHERE id = ?", (g.user["id"],))
    db().commit()
    return jsonify(ok=True)


@app.post("/api/profile/username")
@login_required
def profile_username():
    b = request.get_json(silent=True) or {}
    new = str(b.get("new", "")).strip()
    if not check_password_hash(g.user["password_hash"], str(b.get("password", ""))):
        return err("Your password is wrong.", 403)
    if not USERNAME_RE.fullmatch(new):
        return err("Username: 3-32 letters, digits, dot, dash or underscore.")
    try:
        db().execute("UPDATE users SET username = ? WHERE id = ?", (new, g.user["id"]))
        db().commit()
    except sqlite3.IntegrityError:
        return err("That username is taken.", 409)
    return jsonify(ok=True, username=new)


ensure_config()


@app.post("/api/activity")
@login_required
def log_activity():
    """Remember WHO analyzed WHICH file name (never the file itself)."""
    body = request.get_json(silent=True) or {}
    filename = os.path.basename(str(body.get("filename", "")).replace("\\", "/"))[:200] or "workbook"
    sheets = body.get("sheets") if isinstance(body.get("sheets"), int) else None
    master = str(body.get("master", ""))[:80]
    db().execute("INSERT INTO activity (user_id, filename, sheets, master, at) VALUES (?,?,?,?,?)",
                 (g.user["id"], filename, sheets, master, now()))
    db().commit()
    return jsonify(ok=True), 201


@app.get("/api/activity")
@admin_required
def list_activity():
    rows = db().execute(
        """SELECT a.id, a.filename, a.sheets, a.master, a.at, u.username
           FROM activity a LEFT JOIN users u ON u.id = a.user_id
           ORDER BY a.id DESC LIMIT 200""").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


# ---------------------------------------------------------------- run
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def free_port(host, start):
    """Return the first port >= start that nothing else is using."""
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if os.name != "nt":  # on Linux/macOS a port in TIME_WAIT after a restart is still free to use
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit("No free port found. Set JP_PORT to a free port number.")


def lan_ips():
    """Every non-loopback IPv4 address of this computer (WiFi, Ethernet, hotspot...)."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if not info[4][0].startswith("127."):
                ips.add(info[4][0])
    except OSError:
        pass
    main = lan_ip()
    if main != "127.0.0.1":
        ips.add(main)
    return sorted(ips)


if __name__ == "__main__":
    host = os.environ.get("JP_HOST", "0.0.0.0")
    wanted = int(os.environ.get("JP_PORT") or os.environ.get("PORT", "8085"))
    port = free_port(host, wanted)
    if port != wanted:
        print(f"\n  Port {wanted} is already used by another program (maybe your older project).")
        print(f"  Using port {port} instead.")
    if _index_path() is None:
        print(f"\n  WARNING: index.html not found. Put it here: {INDEX_CANDIDATES[0]}")
    for lib in VENDOR_CDN:
        if not os.path.isfile(os.path.join(BASE, "static", "vendor", lib)):
            print(f"  WARNING: static/vendor/{lib} is missing (the page will try to load it from the internet).")
    urls = [f"http://localhost:{port}"] + [f"http://{ip}:{port}" for ip in lan_ips()]
    print("\n  Jayshree Analytics Hub is running. Keep this window open.")
    print(f"  Recovery key file : {RECOVERY_FILE}")
    print(f"  Open on this computer : {urls[0]}")
    for u in urls[1:]:
        print(f"  Open from other devices (same WiFi): {u}")
    print("  (The address is also saved in data/server_address.txt)\n")
    print(f"  Settings file (Google / mobile verification): {CONFIG_PATH}")
    if firebase_config() is None:
        print("  Google / mobile verification is NOT set up yet: open config.ini, follow the steps at the top, save, refresh the website.")
    else:
        print("  Google sign-in and mobile OTP only work when you open the website as http://localhost:%d (or on your own https:// domain)." % port)
    _c = sqlite3.connect(DB_PATH)
    if _c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        print("  FIRST TIME: open the address above and create your administrator account on the website.")
    _c.close()
    print()
    try:
        with open(os.path.join(DATA, "server_address.txt"), "w") as f:
            f.write("\n".join(urls) + "\n")
    except OSError:
        pass

    # Automatically open the browser only when explicitly enabled.
    if os.environ.get("JP_OPEN_BROWSER", "0") == "1":
        import threading
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(urls[0])).start()

    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=8, max_request_body_size=MAX_MB * 1024 * 1024)
    except ImportError:
        app.run(host=host, port=port)
    except OSError as exc:
        print(f"\n  The server could not start: {exc}")
        print("  Close other programs using this port, or set a different one: set JP_PORT=9000")
        raise SystemExit(1)
