from flask import Flask, request, redirect, url_for, send_file, flash, get_flashed_messages, render_template_string
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import pandas as pd
import io
from openpyxl.utils import get_column_letter
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sqlite3

app = Flask(__name__)
app.secret_key = 'your-super-secret-key-change-this-in-production'

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
    db = get_db()
    try:
        if 'DATABASE_URL' in os.environ:
            # PostgreSQL
            with db() as session:
                result = session.execute(text("SELECT id, username, password_hash FROM users WHERE id = :id"), {'id': user_id})
                row = result.fetchone()
                return User(row[0], row[1], row[2]) if row else None
        else:
            # SQLite
            cursor = db.cursor()
            cursor.execute("SELECT id, username, password_hash FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            db.close()
            return User(row[0], row[1], row[2]) if row else None
    except:
        return None

# Database Setup
def get_db():
    if 'DATABASE_URL' in os.environ:
        # Cloud: PostgreSQL
        engine = create_engine(os.environ['DATABASE_URL'])
        Session = sessionmaker(bind=engine)
        return Session
    else:
        # Local: SQLite
        return sqlite3.connect('database.db')

def init_db():
    db = get_db()
    try:
        if 'DATABASE_URL' in os.environ:
            # PostgreSQL
            with db() as session:
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(80) UNIQUE NOT NULL,
                        password_hash VARCHAR(120) NOT NULL
                    )
                """))
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS entries (
                        code VARCHAR(50) PRIMARY KEY,
                        date VARCHAR(20),
                        weight_in NUMERIC,
                        weight_out NUMERIC,
                        quality NUMERIC
                    )
                """))
                # Check admin
                result = session.execute(text("SELECT 1 FROM users WHERE username = 'admin'"))
                if not result.fetchone():
                    pw_hash = generate_password_hash('password123')
                    session.execute(text("INSERT INTO users (username, password_hash) VALUES ('admin', :pw)"), {'pw': pw_hash})
                session.commit()
        else:
            # SQLite
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
            # Check admin
            cursor.execute("SELECT 1 FROM users WHERE username = 'admin'")
            if not cursor.fetchone():
                pw_hash = generate_password_hash('password123')
                cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('admin', pw_hash))
            db.commit()
            db.close()
        print("DB initialized successfully!")  # For logs
    except Exception as e:
        print(f"DB init error: {e}")

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
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        try:
            if 'DATABASE_URL' in os.environ:
                with db() as session:
                    result = session.execute(text("SELECT id, username, password_hash FROM users WHERE username = :username"), {'username': username})
                    user_row = result.fetchone()
                    if user_row and check_password_hash(user_row[2], password):
                        user = User(user_row[0], user_row[1], user_row[2])
                        login_user(user)
                        return redirect(url_for('index'))
                    flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง!', 'danger')
            else:
                cursor = db.cursor()
                cursor.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
                user_row = cursor.fetchone()
                if user_row and check_password_hash(user_row[2], password):
                    user = User(user_row[0], user_row[1], user_row[2])
                    login_user(user)
                    db.close()
                    return redirect(url_for('index'))
                flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง!', 'danger')
                db.close()
        except Exception as e:
            flash(f'เกิดข้อผิดพลาด: {e}', 'danger')
    # HTML Login Form
    login_html = """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>เข้าสู่ระบบ</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
        <style>body { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); min-height: 100vh; }</style>
    </head>
    <body>
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card p-4">
                    <h2 class="text-center mb-4"><i class="bi bi-shield-lock"></i> เข้าสู่ระบบ</h2>
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
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return render_template_string(login_html)

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

    if request.method == 'POST':
        base_code = request.form.get('base_code')
        if not base_code:
            flash("กรุณาระบุรหัสหลัก!", "danger")
        else:
            date = request.form.get('date') or None
            weight_in = float(request.form['weight_in']) if request.form.get('weight_in') else None
            weight_out = float(request.form['weight_out']) if request.form.get('weight_out') else None
            quality = float(request.form['quality']) if request.form.get('quality') else None

            db = get_db()
            try:
                cursor = db.cursor() if not 'DATABASE_URL' in os.environ else db()
                if 'DATABASE_URL' in os.environ:
                    cursor.execute(text("SELECT code FROM entries WHERE code LIKE :pattern ORDER BY code"), {'pattern': f"{base_code}-%"})
                    existing_codes = [row[0] for row in cursor.fetchall()]
                else:
                    cursor.execute("SELECT code FROM entries WHERE code LIKE ? ORDER BY code", (f"{base_code}-%",))
                    existing_codes = [row[0] for row in cursor.fetchall()]

                next_num = 1
                while f"{base_code}-{next_num}" in existing_codes:
                    next_num += 1
                full_code = f"{base_code}-{next_num}"

                if 'DATABASE_URL' in os.environ:
                    cursor.execute(text("INSERT INTO entries (code, date, weight_in, weight_out, quality) VALUES (:code, :date, :wi, :wo, :q)"), {
                        'code': full_code, 'date': date, 'wi': weight_in, 'wo': weight_out, 'q': quality
                    })
                    cursor.commit()
                else:
                    cursor.execute("INSERT INTO entries VALUES (?, ?, ?, ?, ?)", (full_code, date, weight_in, weight_out, quality))
                    db.commit()

                flash(f"บันทึกข้อมูลรหัส <strong>{full_code}</strong> เรียบร้อยแล้ว! <a href='/list' class='alert-link'>ไปหน้ารายการ</a>", "success")
            except Exception as e:
                flash(f'เกิดข้อผิดพลาดในการบันทึก: {e}', 'danger')
            finally:
                if not 'DATABASE_URL' in os.environ:
                    db.close()

    # Prefill for edit
    if 'code' in request.args:
        code = request.args['code']
        db = get_db()
        try:
            if 'DATABASE_URL' in os.environ:
                with db() as session:
                    result = session.execute(text("SELECT * FROM entries WHERE code = :code"), {'code': code})
                    row = result.fetchone()
            else:
                cursor = db.cursor()
                cursor.execute("SELECT * FROM entries WHERE code=?", (code,))
                row = cursor.fetchone()
                db.close()
            if row:
                base = code.rsplit('-', 1)[0]
                prefill = {
                    'base_code': base,
                    'date': row[1] or '',
                    'weight_in': row[2] if row[2] is not None else '',
                    'weight_out': row[3] if row[3] is not None else '',
                    'quality': row[4] if row[4] is not None else ''
                }
        except Exception as e:
            flash(f'เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}', 'danger')

    return render_form(prefill)

# ฟอร์ม (เหมือนเดิม)
def render_form(prefill):
    flash_html = ""
    for message, category in get_flashed_messages(with_categories=True):
        alert_class = "alert-success" if category == "success" else "alert-danger"
        flash_html += f'<div class="alert {alert_class} alert-dismissible fade show mt-3"><button type="button" class="btn-close" data-bs-dismiss="alert"></button>{message}</div>'

    form_content = f"""
    <div class="card p-4">
        <h2 class="text-primary mb-4"><i class="bi bi-journal-plus"></i> เพิ่ม/แก้ไขข้อมูล</h2>
        {flash_html}
        <form method="post">
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label"><strong>รหัสหลัก *</strong></label>
                    <div class="input-group">
                        <input name="base_code" class="form-control" value="{prefill['base_code']}" required placeholder="เช่น L9R3-0711">
                        <span class="input-group-text">-1, -2, ...</span>
                    </div>
                    <small class="text-muted">ระบบจะเพิ่มเลขลำดับให้อัตโนมัติ</small>
                </div>
                <div class="col-md-6">
                    <label class="form-label">วันที่</label>
                    <input name="date" class="form-control" value="{prefill['date']}" placeholder="เช่น 07/11/2568">
                </div>
                <div class="col-md-6">
                    <label class="form-label">น้ำหนักขาเข้า</label>
                    <input type="number" step="0.01" name="weight_in" class="form-control" value="{prefill['weight_in']}">
                </div>
                <div class="col-md-6">
                    <label class="form-label">น้ำหนักขาออก</label>
                    <input type="number" step="0.01" name="weight_out" class="form-control" value="{prefill['weight_out']}">
                </div>
                <div class="col-12">
                    <label class="form-label">คุณภาพ</label>
                    <input type="number" step="0.01" name="quality" class="form-control" value="{prefill['quality']}">
                </div>
                <div class="col-12">
                    <button type="submit" class="btn btn-primary btn-lg px-4">
                        <i class="bi bi-save"></i> บันทึกข้อมูล
                    </button>
                    <a href="/list" class="btn btn-outline-secondary btn-lg px-4">
                        <i class="bi bi-table"></i> ไปหน้ารายการ
                    </a>
                </div>
            </div>
        </form>
    </div>
    """

    return f"""
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>ระบบจัดการตัวอย่าง</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            body {{ background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); min-height: 100vh; }}
            .container {{ max-width: 1000px; }}
            .card {{ box-shadow: 0 4px 12px rgba(0,0,0,0.1); border: none; }}
        </style>
    </head>
    <body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-flask"></i> APAC Biosciences</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/list">รายการ</a>
                <a class="nav-link" href="/logout">ออกจากระบบ</a>
            </div>
        </div>
    </nav>
    <div class="container py-5">
        {form_content}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

# หน้ารายการ (protected)
@app.route('/list')
@login_required
def list_entries():
    db = get_db()
    try:
        if 'DATABASE_URL' in os.environ:
            with db() as session:
                result = session.execute(text("SELECT * FROM entries"))
                df = pd.DataFrame(result.fetchall(), columns=['code', 'date', 'weight_in', 'weight_out', 'quality'])
        else:
            df = pd.read_sql_query("SELECT * FROM entries", db)
            db.close()

        if not df.empty:
            df['สถานะ'] = df['quality'].apply(get_status)
            df['แก้ไข'] = df['code'].apply(lambda x: f'<a href="/?code={x}" class="btn btn-sm btn-warning"><i class="bi bi-pencil"></i></a>')
            df['ลบ'] = df['code'].apply(lambda x: f'<button onclick="confirmDelete(\'{x}\')" class="btn btn-sm btn-danger"><i class="bi bi-trash"></i></button>')
            df = df.rename(columns={
                'date': 'วันที่',
                'code': 'รหัสตัวอย่าง',
                'weight_in': 'น้ำหนักขาเข้า',
                'weight_out': 'น้ำหนักขาออก',
                'quality': 'คุณภาพ'
            })
            df = df[['วันที่', 'รหัสตัวอย่าง', 'น้ำหนักขาเข้า', 'น้ำหนักขาออก', 'คุณภาพ', 'สถานะ', 'แก้ไข', 'ลบ']]
        else:
            df = pd.DataFrame(columns=['วันที่', 'รหัสตัวอย่าง', 'น้ำหนักขาเข้า', 'น้ำหนักขาออก', 'คุณภาพ', 'สถานะ', 'แก้ไข', 'ลบ'])

        def center(val):
            return f'<div class="text-center">{val}</div>'
        formatters = {col: center for col in df.columns}

        table_html = df.to_html(escape=False, index=False, classes="table table-striped table-hover", formatters=formatters, border=0)

        list_content = f"""
        <div class="card p-4">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h2 class="text-success"><i class="bi bi-list-ul"></i> รายการทั้งหมด ({len(df)} รายการ)</h2>
                <div>
                    <a href="/export" class="btn btn-success">
                        <i class="bi bi-file-excel"></i> Export Excel
                    </a>
                    <a href="/" class="btn btn-outline-primary">
                        <i class="bi bi-plus-circle"></i> เพิ่มข้อมูล
                    </a>
                </div>
            </div>
            {table_html if not df.empty else '<div class="alert alert-info">ยังไม่มีข้อมูล</div>'}
        </div>
        """

        # Modal ลบ
        modal = """
        <div class="modal fade" id="deleteModal" tabindex="-1">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header bg-danger text-white">
                <h5 class="modal-title"><i class="bi bi-exclamation-triangle"></i> ยืนยันการลบ</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                <p>คุณแน่ใจหรือไม่ว่าต้องการลบข้อมูลรหัส <strong id="deleteCode"></strong>?</p>
                <p class="text-danger"><small>การกระทำนี้ไม่สามารถกู้คืนได้</small></p>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">ยกเลิก</button>
                <form method="post" action="/delete" style="display:inline;">
                  <input type="hidden" name="code" id="deleteCodeInput">
                  <button type="submit" class="btn btn-danger">ลบข้อมูล</button>
                </form>
              </div>
            </div>
          </div>
        </div>
        <script>
            function confirmDelete(code) {
                document.getElementById('deleteCode').textContent = code;
                document.getElementById('deleteCodeInput').value = code;
                new bootstrap.Modal(document.getElementById('deleteModal')).show();
            }
        </script>
        """

        return f"""
        <!DOCTYPE html>
        <html lang="th">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>รายการข้อมูล</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
            <style>
                body {{ background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); min-height: 100vh; }}
                .container {{ max-width: 1100px; }}
                .card {{ box-shadow: 0 4px 12px rgba(0,0,0,0.1); border: none; }}
                .table th {{ background-color: #0d6efd; color: white; text-align: center; }}
                .table td {{ vertical-align: middle; text-align: center; }}
                .btn-sm {{ font-size: 0.8rem; }}
            </style>
        </head>
        <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container">
                <a class="navbar-brand" href="/"><i class="bi bi-flask"></i> APAC Biosciences</a>
                <div class="navbar-nav ms-auto">
                    <a class="nav-link" href="/">เพิ่มข้อมูล</a>
                    <a class="nav-link" href="/logout">ออกจากระบบ</a>
                </div>
            </div>
        </nav>
        <div class="container py-5">
            {list_content}
            {modal}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
        """
    except Exception as e:
        flash(f'เกิดข้อผิดพลาดในการโหลดรายการ: {e}', 'danger')
        return redirect(url_for('index'))

# ลบ (protected)
@app.route('/delete', methods=['POST'])
@login_required
def delete_entry():
    code = request.form.get('code')
    if code:
        db = get_db()
        try:
            if 'DATABASE_URL' in os.environ:
                with db() as session:
                    session.execute(text("DELETE FROM entries WHERE code = :code"), {'code': code})
                    session.commit()
                flash(f"ลบข้อมูลรหัส {code} เรียบร้อยแล้ว!", "success")
            else:
                cursor = db.cursor()
                cursor.execute("DELETE FROM entries WHERE code=?", (code,))
                db.commit()
                db.close()
                flash(f"ลบข้อมูลรหัส {code} เรียบร้อยแล้ว!", "success")
        except Exception as e:
            flash(f'เกิดข้อผิดพลาดในการลบ: {e}', 'danger')
    return redirect(url_for('list_entries'))

# Export Excel (protected)
@app.route('/export')
@login_required
def export():
    db = get_db()
    try:
        if 'DATABASE_URL' in os.environ:
            with db() as session:
                result = session.execute(text("SELECT * FROM entries"))
                df = pd.DataFrame(result.fetchall(), columns=['code', 'date', 'weight_in', 'weight_out', 'quality'])
        else:
            df = pd.read_sql_query("SELECT * FROM entries", db)
            db.close()

        def clean_status(q):
            if q is None: return 'ไม่ระบุ'
            elif q < 50: return 'ส่งไปกลุ่ม < 50%'
            elif q < 55: return 'ส่งไปกลุ่ม 50 - 54.9%'
            elif q < 60: return 'ส่งไปกลุ่ม 55 - 59.9%'
            elif q < 65: return 'ส่งไปกลุ่ม 60 - 64.9%'
            elif q < 68: return 'ส่งไปกลุ่ม 65 - 67.9%'
            elif q < 70: return 'ส่งไปกลุ่ม 68 - 69.9%'
            else: return 'ส่งไปกลุ่ม > 70%'

        if not df.empty:
            df['สถานะ'] = df['quality'].apply(clean_status)
            df = df.rename(columns={
                'date': 'วันที่', 'code': 'รหัสตัวอย่าง',
                'weight_in': 'น้ำหนักขาเข้า', 'weight_out': 'น้ำหนักขาออก',
                'quality': 'คุณภาพ'
            })
            df = df[['วันที่', 'รหัสตัวอย่าง', 'น้ำหนักขาเข้า', 'น้ำหนักขาออก', 'คุณภาพ', 'สถานะ']]
        else:
            df = pd.DataFrame(columns=['วันที่', 'รหัสตัวอย่าง', 'น้ำหนักขาเข้า', 'น้ำหนักขาออก', 'คุณภาพ', 'สถานะ'])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ข้อมูลตัวอย่าง')
            worksheet = writer.sheets['ข้อมูลตัวอย่าง']
            for idx, col in enumerate(df.columns, 1):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[get_column_letter(idx)].width = min(max_len, 50)

        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name='ข้อมูลตัวอย่าง.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f'เกิดข้อผิดพลาดในการ export: {e}', 'danger')
        return redirect(url_for('list_entries'))

if __name__ == '__main__':
    app.run(debug=True)