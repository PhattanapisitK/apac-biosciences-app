from flask import Flask, request, redirect, url_for, send_file, flash, get_flashed_messages, render_template_string
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3
import os
import pandas as pd
import io
from openpyxl.utils import get_column_letter
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)
app.secret_key = 'your-super-secret-key-change-this-in-production'  # เปลี่ยนก่อน deploy

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'กรุณาเข้าสู่ระบบเพื่อใช้งาน!'

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    # Load user จาก DB (SQLite หรือ PostgreSQL)
    db = get_db()
    with db.cursor() if isinstance(db, sqlite3.Connection) else db.execute(text("SELECT id, username, password_hash FROM users WHERE id = :id")):
        if isinstance(db, sqlite3.Connection):
            row = cursor.fetchone()
        else:
            row = cursor.fetchone()
        if row:
            return User(row[0], row[1], row[2])
    return None

# Database Setup (SQLite local, PostgreSQL on cloud)
def get_db():
    if 'DATABASE_URL' in os.environ:
        # Cloud: PostgreSQL
        engine = create_engine(os.environ['DATABASE_URL'])
        Session = sessionmaker(bind=engine)
        return Session()
    else:
        # Local: SQLite
        conn = sqlite3.connect('database.db')
        return conn

def init_db():
    db = get_db()
    if 'DATABASE_URL' in os.environ:
        # --- PostgreSQL (Cloud) ---
        with db() as session:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    password_hash VARCHAR(120) NOT NULL
                );
            """))
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS entries (
                    code VARCHAR(50) PRIMARY KEY,
                    date VARCHAR(20),
                    weight_in NUMERIC,
                    weight_out NUMERIC,
                    quality NUMERIC
                );
            """))
            # ตรวจสอบว่ามี admin หรือยัง
            result = session.execute(text("SELECT 1 FROM users WHERE username = 'admin'"))
            if not result.fetchone():
                pw_hash = generate_password_hash('password123')
                session.execute(text("""
                    INSERT INTO users (username, password_hash) VALUES ('admin', :pw)
                """), {'pw': pw_hash})
            session.commit()
    else:
        # --- SQLite (Local) ---
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                code TEXT PRIMARY KEY,
                date TEXT,
                weight_in REAL,
                weight_out REAL,
                quality REAL
            )
        """)
        # ตรวจสอบว่ามี admin หรือยัง
        cursor.execute("SELECT 1 FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            pw_hash = generate_password_hash('password123')
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)
            """, ('admin', pw_hash))
        db.commit()
    if not 'DATABASE_URL' in os.environ:
        db.close()

init_db()

# สถานะ (เหมือนเดิม)
def get_status(quality):
    if quality is None:
        return '<span class="badge bg-secondary">ไม่ระบุ</span>'
    elif quality < 50:
        return '<span class="badge bg-danger">ส่งไปกลุ่ม < 50%</span>'
    elif 50 <= quality < 55:
        return '<span class="badge bg-warning">ส่งไปกลุ่ม 50 - 54.9%</span>'
    elif 55 <= quality < 60:
        return '<span class="badge bg-info">ส่งไปกลุ่ม 55 - 59.9%</span>'
    elif 60 <= quality < 65:
        return '<span class="badge bg-primary">ส่งไปกลุ่ม 60 - 64.9%</span>'
    elif 65 <= quality < 68:
        return '<span class="badge bg-success">ส่งไปกลุ่ม 65 - 67.9%</span>'
    elif 68 <= quality < 70:
        return '<span class="badge bg-dark">ส่งไปกลุ่ม 68 - 69.9%</span>'
    else:
        return '<span class="badge bg-success">ส่งไปกลุ่ม > 70%</span>'

# หน้า Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        if 'DATABASE_URL' in os.environ:
            with db() as session:
                result = session.execute(text("SELECT id, username, password_hash FROM users WHERE username = :username"), {'username': username})
                user_row = result.fetchone()
                session.close()
        else:
            cursor = db.cursor()
            cursor.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
            user_row = cursor.fetchone()
            db.close()
        if user_row and check_password_hash(user_row[2], password):
            user = User(user_row[0], user_row[1], user_row[2])
            login_user(user)
            return redirect(url_for('index'))
        flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง!', 'danger')
    # HTML Login Form
    login_html = """
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card p-4">
                    <h2 class="text-center mb-4">เข้าสู่ระบบ</h2>
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ 'danger' if category == 'danger' else 'success' }} alert-dismissible fade show">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    <form method="post">
                        <div class="mb-3">
                            <label class="form-label">ชื่อผู้ใช้</label>
                            <input type="text" name="username" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">รหัสผ่าน</label>
                            <input type="password" name="password" class="form-control" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">เข้าสู่ระบบ</button>
                    </form>
                    <div class="text-center mt-3">
                        <small>Default: admin / password123</small>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    return render_template_string(login_html, **locals())

# หน้า Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ออกจากระบบเรียบร้อย!', 'success')
    return redirect(url_for('login'))

# หน้าแรก (protected)
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    prefill = {'base_code': '', 'date': '', 'weight_in': '', 'weight_out': '', 'quality': ''}
    # ... (โค้ด index เดิมทั้งหมด – INSERT/UPDATE logic ใช้ get_db() แทน sqlite3.connect)
    # ตัวอย่าง: แทนที่ sqlite3.connect('database.db') ด้วย db = get_db()
    # สำหรับ INSERT/UPDATE: ใช้ cursor.execute เหมือนเดิม แต่ db.commit() และ db.close()
    # (ผมย่อเพื่อความสั้น – ใช้ logic เดิมจาก app.py ก่อนหน้า แต่ปรับ get_db())
    return render_form(prefill)  # ฟังก์ชันเดิม

# หน้ารายการ (protected)
@app.route('/list')
@login_required
def list_entries():
    # ... (logic เดิม แต่ใช้ get_db() สำหรับ query)
    return list_html  # ฟังก์ชันเดิม

# ลบ (protected)
@app.route('/delete', methods=['POST'])
@login_required
def delete_entry():
    # ... (logic เดิม)
    return redirect(url_for('list_entries'))

# Export (protected)
@app.route('/export')
@login_required
def export():
    # ... (logic เดิม แต่ใช้ get_db())
    return send_file(...)

if __name__ == '__main__':
    app.run(debug=True)
    