from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
from io import BytesIO, StringIO
import csv
import zipfile
import joblib
import os
import sqlite3
import numpy as np
import random
import re
import json
import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import google.generativeai as genai

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

from otp_delivery import (
    is_demo_otp_mode,
    sms_provider_configured,
    email_smtp_configured,
    send_sms_otp,
    send_email_otp,
)

app = Flask(__name__)
CORS(app)

# --- Configuration ---
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'court.db')
MODELS_PATH = os.path.join(os.path.dirname(__file__), 'models')
UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), 'uploads')
ADMIN_KEY = os.environ.get('NYAYAFLOW_ADMIN_KEY', 'hackfest-admin')
# Set to '0' to require manual admin approval before filing cases / posting decisions
AUTO_APPROVE = os.environ.get('NYAYAFLOW_AUTO_APPROVE', '1') not in ('0', 'false', 'False')

# --- Gemini Configuration ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Using 'gemini-flash-latest' which is verified to work with this API key
    gemini_model = genai.GenerativeModel('gemini-flash-latest')
else:
    gemini_model = None

def call_gemini(prompt):
    if not gemini_model:
        return None
    try:
        response = gemini_model.generate_content(prompt)
        if response and response.text:
            return response.text
        return None
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

# --- Load V3 AI Models ---
duration_model = priority_model = le_type = le_cat = le_priority = tfidf = None
try:
    duration_model = joblib.load(os.path.join(MODELS_PATH, 'duration_model_v3.joblib'))
    priority_model = joblib.load(os.path.join(MODELS_PATH, 'priority_model_v3.joblib'))
    le_type = joblib.load(os.path.join(MODELS_PATH, 'le_type_v3.joblib'))
    le_cat = joblib.load(os.path.join(MODELS_PATH, 'le_cat_v3.joblib'))
    le_priority = joblib.load(os.path.join(MODELS_PATH, 'le_priority_v3.joblib'))
    tfidf = joblib.load(os.path.join(MODELS_PATH, 'tfidf_v2.joblib'))
except Exception as e:
    print(f"Error loading models: {e}")

# --- OTP stores (demo; use Redis in production) ---
otp_store = {}
email_otp_store = {}


def _norm_code(s):
    if not s:
        return ''
    return re.sub(r'[^A-Za-z0-9]', '', str(s)).upper()[:12]


def normalize_contact(raw):
    """Single key for SMS OTP so +91 / spaces / 91-prefix all match."""
    if raw is None:
        return ''
    s = re.sub(r'[\s\-\(\)]', '', str(raw).strip())
    if s.startswith('+91'):
        s = s[3:]
    elif len(s) == 12 and s.startswith('91') and s[2:].isdigit():
        s = s[2:]
    return s


def migrate_db(conn):
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not c.fetchone():
        return
    c.execute('PRAGMA table_info(users)')
    existing = {row[1] for row in c.fetchall()}
    additions = [
        ("official_email", "TEXT DEFAULT ''"),
        ("gov_id_type", "TEXT DEFAULT ''"),
        ("gov_id_masked", "TEXT DEFAULT ''"),
        ("doc_gov_id_path", "TEXT DEFAULT ''"),
        ("doc_appointment_letter_path", "TEXT DEFAULT ''"),
        ("doc_court_id_card_path", "TEXT DEFAULT ''"),
        ("doc_bar_certificate_path", "TEXT DEFAULT ''"),
        ("doc_office_proof_path", "TEXT DEFAULT ''"),
        ("bar_code", "TEXT DEFAULT 'BCI'"),
        ("phone_verified", "INTEGER DEFAULT 0"),
        ("email_verified", "INTEGER DEFAULT 0"),
        ("face_verified", "INTEGER DEFAULT 0"),
        ("bar_api_verified", "INTEGER DEFAULT 0"),
        ("fraud_risk_score", "REAL DEFAULT 0"),
        ("admin_notes", "TEXT DEFAULT ''"),
    ]
    for col, decl in additions:
        if col not in existing:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
    try:
        # Earlier schema used 'Pending' without admin queue — treat as active
        c.execute("UPDATE users SET verification_status = 'Approved' WHERE verification_status = 'Pending'")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def init_db():
    data_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    if not os.path.exists(UPLOAD_ROOT):
        os.makedirs(UPLOAD_ROOT)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT UNIQUE,
                    case_type TEXT,
                    category TEXT,
                    description TEXT,
                    urgency INTEGER,
                    case_age_days INTEGER,
                    filing_date TEXT,
                    predicted_duration INTEGER,
                    priority TEXT,
                    status TEXT DEFAULT 'Pending',
                    decision TEXT DEFAULT '',
                    judge_id TEXT DEFAULT '',
                    lawyer_id TEXT DEFAULT ''
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nyaya_id TEXT UNIQUE,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT,
                    full_name TEXT,
                    dob TEXT,
                    contact TEXT,
                    email TEXT,
                    state_code TEXT,
                    court_level TEXT,
                    court_name TEXT,
                    designation TEXT,
                    employee_id TEXT,
                    appointment_date TEXT,
                    bar_reg_no TEXT,
                    bar_council_state TEXT,
                    experience INTEGER,
                    practice_area TEXT,
                    chamber_address TEXT,
                    verification_status TEXT DEFAULT 'Pending_Review',
                    credibility_score REAL DEFAULT 50.0,
                    digital_signature_path TEXT DEFAULT '',
                    official_email TEXT DEFAULT '',
                    gov_id_type TEXT DEFAULT '',
                    gov_id_masked TEXT DEFAULT '',
                    doc_gov_id_path TEXT DEFAULT '',
                    doc_appointment_letter_path TEXT DEFAULT '',
                    doc_court_id_card_path TEXT DEFAULT '',
                    doc_bar_certificate_path TEXT DEFAULT '',
                    doc_office_proof_path TEXT DEFAULT '',
                    bar_code TEXT DEFAULT 'BCI',
                    phone_verified INTEGER DEFAULT 0,
                    email_verified INTEGER DEFAULT 0,
                    face_verified INTEGER DEFAULT 0,
                    bar_api_verified INTEGER DEFAULT 0,
                    fraud_risk_score REAL DEFAULT 0,
                    admin_notes TEXT DEFAULT ''
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS case_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    actor_nyaya_id TEXT,
                    event_type TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )''')

    conn.commit()
    migrate_db(conn)
    
    # Create default admin user if not exists
    admin_exists = conn.execute("SELECT 1 FROM users WHERE username = 'admin'").fetchone()
    if not admin_exists:
        from werkzeug.security import generate_password_hash
        hashed_pw = generate_password_hash('admin123')
        conn.execute(
            '''INSERT INTO users (nyaya_id, username, password, role, full_name, verification_status, phone_verified, email_verified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            ('NYA-ADMIN-001', 'admin', hashed_pw, 'Judge', 'System Administrator', 'Approved', 1, 1)
        )
        conn.commit()
    
    conn.close()


init_db()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def user_public_dict(row):
    if row is None:
        return None
    u = dict(row)
    u.pop('password', None)
    return u


def next_id_suffix(conn, prefix):
    """Next 4-digit suffix for JDG-XX-YY- or LAW-XX-YY- style IDs (zero-padded)."""
    like_pat = prefix + '%'
    cur = conn.execute(
        "SELECT nyaya_id FROM users WHERE nyaya_id LIKE ? ORDER BY nyaya_id DESC LIMIT 50",
        (like_pat,),
    )
    mx = 0
    for r in cur.fetchall():
        parts = r[0].split('-')
        if len(parts) < 4:
            continue
        try:
            mx = max(mx, int(parts[-1]))
        except ValueError:
            continue
    n = mx + 1
    if n > 9999:
        n = random.randint(1, 9999)
    return f"{n:04d}"


def generate_unique_professional_id(conn, role, state_code, court_level=None, bar_code='BCI'):
    st = _norm_code(state_code) or 'IN'
    if role == 'Judge':
        cl = _norm_code(court_level) or 'HC'
        if cl not in ('SC', 'HC', 'DC'):
            cl = 'HC'
        prefix = f"JDG-{st}-{cl}-"
        suf = next_id_suffix(conn, prefix)
        return f"{prefix}{suf}"
    if role == 'Lawyer':
        bc = _norm_code(bar_code) or 'BCI'
        prefix = f"LAW-{bc}-{st}-"
        suf = next_id_suffix(conn, prefix)
        return f"{prefix}{suf}"
    return f"USR-{st}-{next_id_suffix(conn, f'USR-{st}-')}"


PAN_RE = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')
AADHAAR_RE = re.compile(r'^\d{12}$')


def mask_gov_id(gov_id_type, value):
    v = re.sub(r'\s', '', value or '')
    if gov_id_type == 'PAN' and len(v) >= 4:
        return 'XXXXXX' + v[-4:]
    if gov_id_type == 'Aadhaar' and len(v) >= 4:
        return 'XXXXXXXX' + v[-4:]
    return ''


def validate_registration(role, data, conn):
      errs = []
      if role not in ('Judge', 'Lawyer'):
          return ['Invalid role']
      if not data.get('full_name') or len(data['full_name'].strip()) < 3:
          errs.append('Full name is required (min 3 characters).')
      if not data.get('username') or len(data['username']) < 3:
          errs.append('Username is required.')
      if not data.get('password') or len(data['password']) < 6:
          errs.append('Password must be at least 6 characters.')
      contact = (data.get('contact') or '').strip()
      if not re.match(r'^\+?\d{10,15}$', re.sub(r'[\s-]', '', contact)):
          errs.append('Valid contact number is required.')
      email = (data.get('email') or '').strip()
      if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
          errs.append('Valid email is required.')

      if role == 'Judge':
          st = _norm_code(data.get('state_code'))
          if not st or len(st) < 2:
              errs.append('State code is required for judge ID (e.g. UP, DL).')
          cl = _norm_code(data.get('court_level'))
          if cl not in ('SC', 'HC', 'DC'):
              errs.append('Court level must be SC, HC, or DC.')
          if not (data.get('court_name') or '').strip():
              errs.append('Court name is required.')
          if not (data.get('designation') or '').strip():
              errs.append('Designation is required (Judge / Magistrate / etc.).')
          if not data.get('dob'):
              errs.append('Date of birth is required for judges.')
          if not data.get('appointment_date'):
              errs.append('Appointment date is required.')
          gid = (data.get('gov_id_type') or '').strip()
          if gid not in ('Aadhaar', 'PAN'):
              errs.append('Government ID type must be Aadhaar or PAN.')
          raw_id = re.sub(r'\s', '', data.get('gov_id_number') or '')
          if gid == 'PAN' and not PAN_RE.match(raw_id.upper()):
              errs.append('Invalid PAN format.')
          if gid == 'Aadhaar' and not AADHAAR_RE.match(raw_id):
              errs.append('Aadhaar must be 12 digits.')
      else:
          if not (data.get('bar_reg_no') or '').strip():
              errs.append('Bar Council registration number is required.')
          if not (data.get('bar_council_state') or '').strip():
              errs.append('State Bar Council is required.')
          try:
              exp = int(str(data.get('experience') or '').strip() or '-1')
          except ValueError:
              exp = -1
          if exp < 0:
              errs.append('Years of experience is required (0 or more).')
          if not (data.get('practice_area') or '').strip():
              errs.append('Practice area is required.')
          if not (data.get('chamber_address') or '').strip():
              errs.append('Chamber / office address is required.')
          gid = (data.get('gov_id_type') or '').strip()
          if gid not in ('Aadhaar', 'PAN'):
              errs.append('Government ID type must be Aadhaar or PAN.')
          raw_id = re.sub(r'\s', '', data.get('gov_id_number') or '')
          if gid == 'PAN' and not PAN_RE.match(raw_id.upper()):
              errs.append('Invalid PAN format.')
          if gid == 'Aadhaar' and not AADHAAR_RE.match(raw_id):
              errs.append('Aadhaar must be 12 digits.')

      dup = conn.execute(
          'SELECT 1 FROM users WHERE username = ? OR contact = ? OR email = ?',
          (data.get('username'), contact, email),
      ).fetchone()
      if dup:
          errs.append('Username, contact, or email already registered.')

      if role == 'Lawyer' and (data.get('bar_reg_no') or '').strip():
          br = conn.execute(
              'SELECT 1 FROM users WHERE bar_reg_no = ? AND role = ?',
              (data.get('bar_reg_no').strip(), 'Lawyer'),
          ).fetchone()
          if br:
              errs.append('This Bar registration number is already registered.')

      return errs


def compute_fraud_risk(role, data, conn):
    score = 0.0
    desc = (data.get('full_name') or '') + ' ' + (data.get('chamber_address') or '')
    if any(k in desc.lower() for k in ('test', 'fake', 'asdf', '12345')):
        score += 30
    if role == 'Judge':
        off = (data.get('official_email') or data.get('email') or '').strip().lower()
        if off and not any(x in off for x in ('.gov.in', 'nic.in', 'judiciary', 'court')):
            score += 15
    if role == 'Lawyer':
        row = conn.execute(
            'SELECT COUNT(*) c FROM users WHERE chamber_address = ? AND role = ?',
            ((data.get('chamber_address') or '').strip(), 'Lawyer'),
        ).fetchone()
        if row and row['c'] > 0:
            score += 25
    return min(100.0, score)


def mock_bar_council_lookup(bar_reg_no, state):
    """Simulated bar verification — replace with real API when available."""
    if not bar_reg_no or len(bar_reg_no) < 4:
        return False, 'Invalid registration number'
    last = sum(ord(c) for c in bar_reg_no[-4:]) % 10
    ok = last != 0
    return ok, 'BCI mock: verified' if ok else 'BCI mock: no match'


def save_upload(subfolder, file_storage):
    if not file_storage or not file_storage.filename:
        return ''
    fn = secure_filename(file_storage.filename) or 'upload'
    unique = f"{uuid.uuid4().hex[:10]}_{fn}"
    folder = os.path.join(UPLOAD_ROOT, subfolder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, unique)
    file_storage.save(path)
    return os.path.relpath(path, UPLOAD_ROOT).replace('\\', '/')


def log_case_event(conn, case_id, actor_id, event_type, details=None):
    conn.execute(
        '''INSERT INTO case_history (case_id, actor_nyaya_id, event_type, details, created_at)
           VALUES (?, ?, ?, ?, ?)''',
        (case_id, actor_id or '', event_type, json.dumps(details or {}), datetime.utcnow().isoformat()),
    )


def get_user_by_nyaya(conn, nyaya_id):
    if not nyaya_id:
        return None
    return conn.execute('SELECT * FROM users WHERE nyaya_id = ?', (nyaya_id,)).fetchone()


def require_approved_actor(conn, nyaya_id, allowed_roles):
    u = get_user_by_nyaya(conn, nyaya_id)
    if not u:
        return None, jsonify({'error': 'Unknown user'}), 403
    if u['role'] not in allowed_roles:
        return None, jsonify({'error': 'Action not allowed for this role'}), 403
    if u['verification_status'] != 'Approved':
        return None, jsonify({
            'error': 'Account pending verification. You cannot perform this action until approved by admin.',
            'verification_status': u['verification_status'],
        }), 403
    return u, None, None


@app.route('/api/otp-config', methods=['GET'])
def otp_config():
    demo = is_demo_otp_mode()
    return jsonify({
        "demo_mode": demo,
        "real_sms": sms_provider_configured(),
        "real_email": email_smtp_configured(),
        "hint": "Real OTP ke liye backend/.env mein Twilio ya Fast2SMS + SMTP set karein. Local test: NYAYAFLOW_OTP_MODE=demo",
    }), 200


@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.json or {}
    contact = data.get('contact')
    if not contact:
        return jsonify({"error": "Contact is required"}), 400

    key = normalize_contact(contact)
    if len(key) != 10 or not key.isdigit() or key[0] not in "6789":
        return jsonify({"error": "Valid 10-digit Indian mobile daalein (6–9 se start, bina +91)."}), 400

    otp = f"{random.randint(100000, 999999)}"
    otp_store[key] = {"otp": otp, "expiry": datetime.now() + timedelta(minutes=5)}

    if is_demo_otp_mode():
        print(f"DEMO OTP mobile {key}: {otp}")
        return jsonify({
            "message": "Demo mode: OTP screen par bhi dikhega.",
            "demo_mode": True,
            "debug_otp": otp,
            "normalized_contact": key,
        }), 200

    if not sms_provider_configured():
        otp_store.pop(key, None)
        return jsonify({
            "error": "SMS provider configure nahi hai. Twilio (TWILIO_*) ya Fast2SMS (FAST2SMS_API_KEY) .env mein set karein, ya test ke liye NYAYAFLOW_OTP_MODE=demo",
        }), 503

    ok, err = send_sms_otp(key, otp)
    if not ok:
        otp_store.pop(key, None)
        return jsonify({"error": f"SMS bhejne mein fail: {err}"}), 502

    return jsonify({
        "message": "OTP aapke mobile number par bhej diya gaya hai.",
        "demo_mode": False,
    }), 200


@app.route('/api/send-email-otp', methods=['POST'])
def send_email_otp_route():
    data = request.json or {}
    email = (data.get('email') or '').strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400
    email_key = email.lower()
    otp = f"{random.randint(100000, 999999)}"
    email_otp_store[email_key] = {"otp": otp, "expiry": datetime.now() + timedelta(minutes=5)}

    if is_demo_otp_mode():
        print(f"DEMO OTP email {email_key}: {otp}")
        return jsonify({
            "message": "Demo mode: OTP screen par bhi dikhega.",
            "demo_mode": True,
            "debug_email_otp": otp,
        }), 200

    if not email_smtp_configured():
        email_otp_store.pop(email_key, None)
        return jsonify({
            "error": "Email SMTP configure nahi hai. SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL .env mein set karein, ya NYAYAFLOW_OTP_MODE=demo",
        }), 503

    ok, err = send_email_otp(email, otp)
    if not ok:
        email_otp_store.pop(email_key, None)
        return jsonify({"error": f"Email bhejne mein fail: {err}"}), 502

    return jsonify({
        "message": "OTP aapke email par bhej diya gaya hai (inbox / spam check karein).",
        "demo_mode": False,
    }), 200


@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json or {}
    key = normalize_contact(data.get('contact'))
    otp = (data.get('otp') or '').strip()
    if key in otp_store:
        stored = otp_store[key]
        if datetime.now() < stored['expiry'] and str(stored['otp']) == otp:
            return jsonify({
                "message": "Mobile OTP sahi hai.",
                "thank_you": "Thank you! Mobile number verify ho gaya.",
            }), 200
    return jsonify({"error": "Galat ya purana mobile OTP. Dobara 'Send OTPs' try karein."}), 400


@app.route('/api/verify-email-otp', methods=['POST'])
def verify_email_otp():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    otp = (data.get('otp') or '').strip()
    if email in email_otp_store:
        stored = email_otp_store[email]
        if datetime.now() < stored['expiry'] and str(stored['otp']) == otp:
            return jsonify({
                "message": "Email OTP sahi hai.",
                "thank_you": "Thank you! Email verify ho gaya.",
            }), 200
    return jsonify({"error": "Galat ya purana email OTP. Dobara 'Resend OTPs' try karein."}), 400


@app.route('/api/verify-bar-mock', methods=['POST'])
def verify_bar_mock():
    data = request.json or {}
    ok, msg = mock_bar_council_lookup(data.get('bar_reg_no'), data.get('state'))
    return jsonify({'verified': ok, 'message': msg}), 200


@app.route('/api/register', methods=['POST'])
def register():
    if request.content_type and 'multipart/form-data' in request.content_type:
        return register_multipart()
    data = request.json or {}
    return _register_from_dict(data)


def register_multipart():
    role = request.form.get('role')
    data = {k: request.form.get(k) for k in request.form.keys()}
    data['role'] = role
    if data.get('experience') is not None and str(data.get('experience')).strip().isdigit():
        data['experience'] = int(data.get('experience'))
    files = {
        'gov_id_doc': request.files.get('gov_id_doc'),
        'appointment_letter': request.files.get('appointment_letter'),
        'court_id_card': request.files.get('court_id_card'),
        'bar_certificate': request.files.get('bar_certificate'),
        'office_proof': request.files.get('office_proof'),
    }
    paths = {}
    uid_folder = uuid.uuid4().hex[:12]
    if role == 'Judge':
        paths['doc_gov_id_path'] = save_upload(f'judge/{uid_folder}', files['gov_id_doc'])
        paths['doc_appointment_letter_path'] = save_upload(f'judge/{uid_folder}', files['appointment_letter'])
        paths['doc_court_id_card_path'] = save_upload(f'judge/{uid_folder}', files['court_id_card'])
    else:
        paths['doc_gov_id_path'] = save_upload(f'lawyer/{uid_folder}', files['gov_id_doc'])
        paths['doc_bar_certificate_path'] = save_upload(f'lawyer/{uid_folder}', files['bar_certificate'])
        paths['doc_office_proof_path'] = save_upload(f'lawyer/{uid_folder}', files['office_proof'])
    for k, v in list(paths.items()):
        if not v:
            paths.pop(k)
    if role == 'Judge':
        req = ('doc_gov_id_path', 'doc_appointment_letter_path', 'doc_court_id_card_path')
        if any(not paths.get(r) for r in req):
            return jsonify({'error': 'Judges must upload government ID, appointment letter, and court ID card.'}), 400
    elif role == 'Lawyer':
        req = ('doc_gov_id_path', 'doc_bar_certificate_path', 'doc_office_proof_path')
        if any(not paths.get(r) for r in req):
            return jsonify({'error': 'Lawyers must upload government ID, bar certificate, and office proof.'}), 400
    data.update(paths)
    return _register_from_dict(data)


def _register_from_dict(data):
    try:
        role = data.get('role')
        state_code = data.get('state_code', 'IN')
        court_level = data.get('court_level')
        bar_code = data.get('bar_code', 'BCI')

        conn = get_db_connection()
        errs = validate_registration(role, data, conn)
        if errs:
            conn.close()
            return jsonify({"error": "; ".join(errs)}), 400

        nyaya_id = generate_unique_professional_id(conn, role, state_code, court_level, bar_code)
        hashed_pw = generate_password_hash(data['password'])
        fraud = compute_fraud_risk(role, data, conn)

        bar_ok, _ = (False, '')
        if role == 'Lawyer':
            bar_ok, _ = mock_bar_council_lookup(data.get('bar_reg_no'), data.get('bar_council_state'))

        gov_type = (data.get('gov_id_type') or '').strip()
        gov_masked = mask_gov_id(gov_type, data.get('gov_id_number') or '')

        v_status = 'Approved' if AUTO_APPROVE else 'Pending_Review'
        if fraud >= 70:
            v_status = 'Pending_Review'

        conn.execute(
            '''INSERT INTO users
               (nyaya_id, username, password, role, full_name, dob, contact, email, official_email,
                state_code, court_level, court_name, designation, employee_id, appointment_date,
                bar_reg_no, bar_council_state, experience, practice_area, chamber_address,
                verification_status, credibility_score, bar_code, gov_id_type, gov_id_masked,
                doc_gov_id_path, doc_appointment_letter_path, doc_court_id_card_path,
                doc_bar_certificate_path, doc_office_proof_path,
                phone_verified, email_verified, bar_api_verified, fraud_risk_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                nyaya_id,
                data['username'],
                hashed_pw,
                role,
                data.get('full_name'),
                data.get('dob'),
                (data.get('contact') or '').strip(),
                (data.get('email') or '').strip(),
                (data.get('official_email') or data.get('email') or '').strip(),
                _norm_code(state_code),
                court_level,
                data.get('court_name'),
                data.get('designation'),
                data.get('employee_id'),
                data.get('appointment_date'),
                data.get('bar_reg_no'),
                data.get('bar_council_state'),
                int(data.get('experience') or 0),
                data.get('practice_area'),
                data.get('chamber_address'),
                v_status,
                50.0 if role == 'Lawyer' else 0.0,
                _norm_code(bar_code) or 'BCI',
                gov_type,
                gov_masked,
                data.get('doc_gov_id_path') or '',
                data.get('doc_appointment_letter_path') or '',
                data.get('doc_court_id_card_path') or '',
                data.get('doc_bar_certificate_path') or '',
                data.get('doc_office_proof_path') or '',
                1 if data.get('phone_verified') else 0,
                1 if data.get('email_verified') else 0,
                1 if bar_ok else 0,
                fraud,
            ),
        )
        conn.commit()
        conn.close()
        return jsonify({
            "message": "Registration successful",
            "thank_you": "Bahut dhanyawad! Aapka NyayaFlow account ban gaya. Neeche diye gaye ID se login karein.",
            "nyaya_id": nyaya_id,
            "username": data.get("username"),
            "verification_status": v_status,
            "fraud_risk_score": fraud,
            "bar_api_hint": "Simulated BCI check " + ("passed" if bar_ok else "flagged — admin may review"),
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (data.get('username'),)).fetchone()
    conn.close()
    if user and check_password_hash(user['password'], data.get('password', '')):
        return jsonify({"user": user_public_dict(user)}), 200
    return jsonify({"error": "Invalid username or password"}), 401


@app.route('/api/user/digital-signature', methods=['POST'])
def upload_signature():
    nyaya_id = request.form.get('nyaya_id')
    conn = get_db_connection()
    u, err, code = require_approved_actor(conn, nyaya_id, ('Judge', 'Lawyer'))
    if err:
        conn.close()
        return err, code
    rel = save_upload('signatures', request.files.get('signature'))
    if not rel:
        conn.close()
        return jsonify({'error': 'No file'}), 400
    conn.execute('UPDATE users SET digital_signature_path = ? WHERE nyaya_id = ?', (rel, nyaya_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Signature saved', 'path': rel}), 200


@app.route('/api/user/face-verify-demo', methods=['POST'])
def face_verify_demo():
    """Optional: accepts an image; mock pass/fail for hackathon demo."""
    nyaya_id = request.form.get('nyaya_id')
    conn = get_db_connection()
    u = get_user_by_nyaya(conn, nyaya_id)
    if not u:
        conn.close()
        return jsonify({'error': 'Unknown user'}), 404
    f = request.files.get('face_image')
    save_upload(f'faces/{nyaya_id}', f)
    ok = random.random() > 0.15
    conn.execute('UPDATE users SET face_verified = ? WHERE nyaya_id = ?', (1 if ok else 0, nyaya_id))
    conn.commit()
    conn.close()
    return jsonify({'face_verified': ok, 'message': 'Demo face check ' + ('passed' if ok else 'manual review suggested')}), 200


def get_case_age(filing_date_str):
    try:
        fd = datetime.strptime(filing_date_str, '%Y-%m-%d')
        return (datetime.now() - fd).days
    except Exception:
        return 0


# --- Case Endpoints ---
@app.route('/api/cases', methods=['POST'])
def add_case():
    data = request.json or {}
    lawyer_id = data.get('lawyer_id')
    conn = get_db_connection()
    u, err, code = require_approved_actor(conn, lawyer_id, ('Lawyer',))
    if err:
        conn.close()
        return err, code
    try:
        desc = data.get('description', '').lower()
        risk_keywords = ['fake', 'scam', 'bribe', 'money laundering']
        if any(k in desc for k in risk_keywords):
            conn.close()
            return jsonify({"error": "AI Security Alert: Potentially fraudulent filing — blocked for review."}), 403

        # Advanced Gemini Fraud Check
        if gemini_model:
            fraud_prompt = f"Analyze this legal case description for potential fraud, illegal activities, or non-legal content. Description: {desc}. Return only 'FRAUD' if suspicious, otherwise return 'OK'."
            fraud_result = call_gemini(fraud_prompt)
            if fraud_result and 'FRAUD' in fraud_result.upper():
                conn.close()
                return jsonify({"error": "Advanced AI Security Alert: This filing has been flagged as suspicious by our AI analysis system."}), 403

        age = get_case_age(data['filing_date'])
        if duration_model is not None and priority_model is not None:
            type_enc = le_type.transform([data['case_type']])[0]
            cat_enc = le_cat.transform([data['category']])[0]
            features = np.array([[type_enc, cat_enc, age, data['urgency']]])
            duration = int(duration_model.predict(features)[0])
            priority = le_priority.inverse_transform([priority_model.predict(features)[0]])[0]
        else:
            duration = 30 + (data['urgency'] or 3) * 5
            priority = 'High' if (data.get('urgency') or 0) >= 4 else 'Medium'

        conn.execute(
            '''INSERT INTO cases
               (case_id, case_type, category, description, urgency, case_age_days, filing_date, predicted_duration, priority, lawyer_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                data['case_id'],
                data['case_type'],
                data['category'],
                data.get('description', ''),
                data['urgency'],
                age,
                data['filing_date'],
                duration,
                priority,
                lawyer_id,
            ),
        )
        log_case_event(conn, data['case_id'], lawyer_id, 'FILING', {'priority': priority, 'predicted_duration': duration})
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "priority": priority, "predicted_duration": duration, "duration": duration}), 201
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@app.route('/api/cases', methods=['GET'])
def get_cases():
    conn = get_db_connection()
    cases = conn.execute('SELECT * FROM cases ORDER BY id DESC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in cases])


@app.route('/api/cases/<case_id>/history', methods=['GET'])
def case_history(case_id):
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT * FROM case_history WHERE case_id = ? ORDER BY id ASC',
        (case_id,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d['details'] = json.loads(d['details'] or '{}')
        except json.JSONDecodeError:
            d['details'] = {}
        out.append(d)
    return jsonify(out)


@app.route('/api/cases/decision', methods=['POST'])
def post_decision():
    data = request.json or {}
    judge_id = data.get('judge_id')
    conn = get_db_connection()
    u, err, code = require_approved_actor(conn, judge_id, ('Judge',))
    if err:
        conn.close()
        return err, code
    try:
        conn.execute(
            'UPDATE cases SET decision = ?, status = "Resolved", judge_id = ? WHERE case_id = ?',
            (data.get('decision'), judge_id, data.get('case_id')),
        )
        row = conn.execute(
            'SELECT lawyer_id FROM cases WHERE case_id = ?',
            (data.get('case_id'),),
        ).fetchone()
        if row and row['lawyer_id']:
            conn.execute(
                '''UPDATE users SET credibility_score =
                   CASE WHEN COALESCE(credibility_score, 0) + 2 > 100 THEN 100
                        ELSE COALESCE(credibility_score, 0) + 2 END
                   WHERE nyaya_id = ? AND role = ?''',
                (row['lawyer_id'], 'Lawyer'),
            )
        log_case_event(conn, data['case_id'], judge_id, 'DECISION', {'summary': (data.get('decision') or '')[:200]})
        conn.commit()
        conn.close()
        return jsonify({"message": "Decision uploaded successfully"}), 200
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@app.route('/api/lawyers/<nyaya_id>/credibility', methods=['GET'])
def lawyer_credibility(nyaya_id):
    conn = get_db_connection()
    u = get_user_by_nyaya(conn, nyaya_id)
    conn.close()
    if not u or u['role'] != 'Lawyer':
        return jsonify({'error': 'Not a lawyer'}), 404
    u = user_public_dict(u)
    return jsonify({
        'nyaya_id': u['nyaya_id'],
        'credibility_score': u['credibility_score'],
        'verification_status': u['verification_status'],
        'bar_api_verified': bool(u.get('bar_api_verified')),
    }), 200


# --- Admin ---
def _admin_ok():
    return request.headers.get('X-Admin-Key') == ADMIN_KEY


@app.route('/api/admin/pending-users', methods=['GET'])
def admin_pending():
    if not _admin_ok():
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM users WHERE verification_status = 'Pending_Review' ORDER BY id DESC",
    ).fetchall()
    conn.close()
    return jsonify([user_public_dict(r) for r in rows]), 200


@app.route('/api/admin/approve-user', methods=['POST'])
def admin_approve():
    if not _admin_ok():
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json or {}
    nyaya_id = data.get('nyaya_id')
    status = data.get('status', 'Approved')
    if status not in ('Approved', 'Rejected', 'Pending_Review'):
        return jsonify({'error': 'Invalid status'}), 400
    conn = get_db_connection()
    conn.execute(
        'UPDATE users SET verification_status = ?, admin_notes = ? WHERE nyaya_id = ?',
        (status, data.get('notes', ''), nyaya_id),
    )
    conn.commit()
    conn.close()
    return jsonify({'message': 'Updated', 'nyaya_id': nyaya_id, 'status': status}), 200


def _cases_as_dicts():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM cases ORDER BY id ASC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _history_as_dicts():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM case_history ORDER BY id ASC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _dicts_to_csv(rows, fieldnames):
    if not rows:
        return ''
    sio = StringIO()
    w = csv.DictWriter(sio, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    for row in rows:
        flat = {}
        for k, v in row.items():
            flat[k] = v if v is not None else ''
        w.writerow(flat)
    return sio.getvalue()


@app.route('/api/export/cases', methods=['GET'])
def export_cases():
    fmt = (request.args.get('format') or 'json').lower()
    rows = _cases_as_dicts()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    if fmt == 'csv':
        keys = ['id', 'case_id', 'case_type', 'category', 'description', 'urgency', 'case_age_days',
                'filing_date', 'predicted_duration', 'priority', 'status', 'decision', 'judge_id', 'lawyer_id']
        body = _dicts_to_csv(rows, keys)
        return Response(
            body,
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename=nyayaflow_cases_{ts}.csv'},
        )
    return Response(
        json.dumps(rows, indent=2, ensure_ascii=False),
        mimetype='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=nyayaflow_cases_{ts}.json'},
    )


@app.route('/api/export/case-history', methods=['GET'])
def export_case_history():
    fmt = (request.args.get('format') or 'json').lower()
    rows = _history_as_dicts()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    keys = ['id', 'case_id', 'actor_nyaya_id', 'event_type', 'details', 'created_at']
    if fmt == 'csv':
        body = _dicts_to_csv(rows, keys)
        return Response(
            body,
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename=nyayaflow_case_history_{ts}.csv'},
        )
    return Response(
        json.dumps(rows, indent=2, ensure_ascii=False),
        mimetype='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=nyayaflow_case_history_{ts}.json'},
    )


@app.route('/api/export/dashboard', methods=['GET'])
def export_dashboard():
    conn = get_db_connection()
    stats = conn.execute(
        '''SELECT COUNT(*) as total,
           SUM(CASE WHEN priority='High' THEN 1 ELSE 0 END) as high,
           SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) as pending,
           AVG(predicted_duration) as avg_dur FROM cases''',
    ).fetchone()
    case_rows = conn.execute('SELECT case_id, case_type, priority, status, filing_date, lawyer_id, judge_id FROM cases ORDER BY id DESC').fetchall()
    conn.close()
    payload = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'stats': {
            'total_cases': stats['total'] or 0,
            'high_priority': stats['high'] or 0,
            'pending_cases': stats['pending'] or 0,
            'avg_duration': int(stats['avg_dur'] or 0),
        },
        'cases_summary': [dict(r) for r in case_rows],
    }
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return Response(
        json.dumps(payload, indent=2, ensure_ascii=False),
        mimetype='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=nyayaflow_dashboard_{ts}.json'},
    )


@app.route('/api/export/users', methods=['GET'])
def export_users_safe():
    """Admin only — no passwords. Professional directory export."""
    if not _admin_ok():
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    rows = conn.execute(
        '''SELECT nyaya_id, role, full_name, email, contact, official_email, state_code, court_level,
           court_name, designation, bar_reg_no, bar_council_state, practice_area, verification_status,
           credibility_score, fraud_risk_score, appointment_date, experience
           FROM users ORDER BY id ASC''',
    ).fetchall()
    conn.close()
    users = [dict(r) for r in rows]
    fmt = (request.args.get('format') or 'json').lower()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    keys = list(users[0].keys()) if users else [
        'nyaya_id', 'role', 'full_name', 'email', 'contact', 'official_email', 'state_code',
        'court_level', 'court_name', 'designation', 'bar_reg_no', 'bar_council_state',
        'practice_area', 'verification_status', 'credibility_score', 'fraud_risk_score',
        'appointment_date', 'experience',
    ]
    if fmt == 'csv':
        body = _dicts_to_csv(users, keys)
        return Response(
            body,
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename=nyayaflow_users_{ts}.csv'},
        )
    return Response(
        json.dumps(users, indent=2, ensure_ascii=False),
        mimetype='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=nyayaflow_users_{ts}.json'},
    )


@app.route('/api/admin/download-backup', methods=['GET'])
def admin_download_backup():
    """ZIP: SQLite DB + JSON exports + uploaded verification files (admin key required)."""
    if not _admin_ok():
        return jsonify({'error': 'Unauthorized'}), 401
    buf = BytesIO()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.isfile(DB_PATH):
            zf.write(DB_PATH, arcname='data/court.db')
        cases = _cases_as_dicts()
        zf.writestr('export/cases.json', json.dumps(cases, indent=2, ensure_ascii=False))
        hist = _history_as_dicts()
        zf.writestr('export/case_history.json', json.dumps(hist, indent=2, ensure_ascii=False))
        conn = get_db_connection()
        urows = conn.execute(
            '''SELECT nyaya_id, role, full_name, email, contact, verification_status,
               credibility_score, fraud_risk_score, doc_gov_id_path, doc_appointment_letter_path,
               doc_court_id_card_path, doc_bar_certificate_path, doc_office_proof_path,
               digital_signature_path, bar_reg_no, state_code, court_level
               FROM users ORDER BY id ASC''',
        ).fetchall()
        conn.close()
        zf.writestr(
            'export/users_public.json',
            json.dumps([dict(r) for r in urows], indent=2, ensure_ascii=False),
        )
        if os.path.isdir(UPLOAD_ROOT):
            for root, _dirs, files in os.walk(UPLOAD_ROOT):
                for fn in files:
                    abs_path = os.path.join(root, fn)
                    rel = os.path.relpath(abs_path, UPLOAD_ROOT).replace('\\', '/')
                    zf.write(abs_path, arcname=f'uploads/{rel}')
    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'nyayaflow_full_backup_{ts}.zip',
    )


# --- Dashboard & Other Endpoints ---
@app.route('/api/dashboard-stats', methods=['GET'])
def get_stats():
    conn = get_db_connection()
    stats = conn.execute(
        '''SELECT COUNT(*) as total,
           SUM(CASE WHEN priority='High' THEN 1 ELSE 0 END) as high,
           SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) as pending,
           AVG(predicted_duration) as avg_dur FROM cases''',
    ).fetchone()
    conn.close()
    return jsonify({
        "total_cases": stats['total'] or 0,
        "high_priority": stats['high'] or 0,
        "pending_cases": stats['pending'] or 0,
        "avg_duration": int(stats['avg_dur'] or 0),
    })


@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    conn = get_db_connection()
    cases = conn.execute(
        '''SELECT * FROM cases WHERE status = 'Pending'
           ORDER BY
           CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
           case_age_days DESC''',
    ).fetchall()
    conn.close()

    today = datetime.now()
    schedule = []
    for i, c in enumerate(cases):
        date = today + timedelta(days=(i // 2) + 7)
        if date.weekday() >= 5:
            date += timedelta(days=2)
        schedule.append({
            "case_id": c['case_id'],
            "priority": c['priority'],
            "suggested_date": date.strftime('%Y-%m-%d'),
        })
    return jsonify(schedule)


@app.route('/api/summarize', methods=['POST'])
def summarize():
    text = request.json.get('text', '')
    summary = ". ".join(text.split('.')[:3]) + "."
    return jsonify({"summary": f"[NyayaFlow AI Summary]: {summary}"})


@app.route('/api/uploads/<path:filepath>')
def serve_upload(filepath):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_ROOT, filepath)


@app.route('/api/ai/analyze-case', methods=['POST'])
def ai_analyze_case():
    data = request.json or {}
    case_description = data.get('description')
    case_type = data.get('case_type')
    
    if not case_description:
        return jsonify({"error": "Description is required"}), 400
        
    prompt = f"""
    As a legal AI assistant for the Indian Judicial System (NyayaFlow), provide a detailed analysis of the following case:
    
    Case Type: {case_type}
    Description: {case_description}
    
    Please provide:
    1. A concise summary of the case.
    2. Potential legal sections (IPC/BNS) that might apply.
    3. Suggested next steps for the lawyer.
    4. Estimated complexity (Low/Medium/High).
    
    Format the response in clear Markdown.
    """
    
    analysis = call_gemini(prompt)
    if not analysis:
        return jsonify({"error": "AI analysis failed"}), 500
        
    return jsonify({"analysis": analysis})


@app.route('/api/ai/suggest-decision', methods=['POST'])
def ai_suggest_decision():
    data = request.json or {}
    case_id = data.get('case_id')
    
    if not case_id:
        return jsonify({"error": "Case ID is required"}), 400
        
    conn = get_db_connection()
    case = conn.execute('SELECT * FROM cases WHERE case_id = ?', (case_id,)).fetchone()
    conn.close()
    
    if not case:
        return jsonify({"error": "Case not found"}), 404
        
    case_dict = dict(case)
    
    prompt = f"""
    As a judicial AI assistant, suggest a draft decision or key points for consideration for the following case:
    
    Case ID: {case_dict['case_id']}
    Type: {case_dict['case_type']}
    Category: {case_dict['category']}
    Description: {case_dict['description']}
    
    Provide a balanced view considering legal principles and suggest a draft judgment structure.
    """
    
    suggestion = call_gemini(prompt)
    if not suggestion:
        return jsonify({"error": "AI suggestion failed"}), 500
        
    return jsonify({"suggestion": suggestion})


@app.route('/api/ai/summarize', methods=['POST'])
def ai_summarize():
    data = request.json or {}
    text = data.get('text')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
        
    prompt = f"""
    Summarize the following legal document or text provided below. 
    Focus on key facts, legal issues, and any potential conclusions. 
    Provide a professional, concise summary suitable for legal practitioners.
    
    Text:
    {text}
    """
    
    summary = call_gemini(prompt)
    if not summary:
        return jsonify({"error": "AI summarization failed"}), 500
        
    return jsonify({"summary": summary})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
