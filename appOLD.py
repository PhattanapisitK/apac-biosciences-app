from flask import Flask, request, render_template_string, redirect, url_for, send_file, flash
import sqlite3
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # สำหรับ flash message

# --- ฟังก์ชัน DB และสถานะ ---
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS entries
                 (code TEXT PRIMARY KEY, date TEXT, weight_in REAL, weight_out REAL, quality REAL)''')
    conn.commit()
    conn.close()

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

init_db()

# --- HTML Template ---
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ระบบจัดการตัวอย่าง</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); min-height: 100vh; }
        .container { max-width: 1100px; }
        .card { box-shadow: 0 4px 12px rgba(0,0,0,0.1); border: none; }
        .table th { background-color: #0d6efd; color: white; text-align: center; }
        .table td { vertical-align: middle; } /* ทำให้แนวตั้งกึ่งกลาง */
        .btn-sm { font-size: 0.8rem; }
    </style>
</head>
<body>
<div class="container py-5">
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="alert alert-success alert-dismissible fade show">
          {{ messages[0] }}
          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
      {% endif %}
    {% endwith %}
    {{ content|safe }}
</div>

<!-- Modal ลบ -->
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

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
    function confirmDelete(code) {
        document.getElementById('deleteCode').textContent = code;
        document.getElementById('deleteCodeInput').value = code;
        new bootstrap.Modal(document.getElementById('deleteModal')).show();
    }
</script>
</body>
</html>
"""

# --- หน้าแรก: ฟอร์ม ---
@app.route('/', methods=['GET', 'POST'])
def index():
    prefill = {'date': '', 'code': '', 'weight_in': '', 'weight_out': '', 'quality': ''}

    if request.method == 'POST':
        code = request.form.get('code')
        if not code:
            return render_template_string(BASE_TEMPLATE, content="<div class='alert alert-danger'>กรุณาระบุรหัสตัวอย่าง!</div>")

        date = request.form.get('date') or None
        weight_in = float(request.form['weight_in']) if request.form.get('weight_in') else None
        weight_out = float(request.form['weight_out']) if request.form.get('weight_out') else None
        quality = float(request.form['quality']) if request.form.get('quality') else None

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM entries WHERE code=?", (code,))
        existing = c.fetchone()

        if existing:
            updates = []
            params = []
            if date is not None: updates.append("date=?"); params.append(date)
            if weight_in is not None: updates.append("weight_in=?"); params.append(weight_in)
            if weight_out is not None: updates.append("weight_out=?"); params.append(weight_out)
            if quality is not None: updates.append("quality=?"); params.append(quality)
            if updates:
                query = f"UPDATE entries SET {', '.join(updates)} WHERE code=?"
                c.execute(query, params + [code])
        else:
            c.execute("INSERT INTO entries VALUES (?, ?, ?, ?, ?)", (code, date, weight_in, weight_out, quality))

        conn.commit()
        conn.close()
        flash("บันทึกข้อมูลเรียบร้อย!")
        return redirect(url_for('list_entries'))

    # Prefill สำหรับแก้ไข
    if 'code' in request.args:
        code = request.args['code']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM entries WHERE code=?", (code,))
        row = c.fetchone()
        conn.close()
        if row:
            prefill = {
                'code': row[0],
                'date': row[1] or '',
                'weight_in': row[2] if row[2] is not None else '',
                'weight_out': row[3] if row[3] is not None else '',
                'quality': row[4] if row[4] is not None else ''
            }

    form_html = f"""
    <div class="card p-4">
        <h2 class="text-primary mb-4">เพิ่ม/แก้ไขข้อมูล</h2>
        <form method="post">
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label"><strong>รหัสตัวอย่าง</strong></label>
                    <input name="code" class="form-control" value="{prefill['code']}" required>
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
                        บันทึกข้อมูล
                    </button>
                    <a href="/list" class="btn btn-outline-secondary btn-lg px-4">
                        ไปหน้ารายการ
                    </a>
                </div>
            </div>
        </form>
    </div>
    """
    return render_template_string(BASE_TEMPLATE, content=form_html)

# --- หน้ารายการ ---
@app.route('/list')
def list_entries():
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query("SELECT * FROM entries", conn)
    conn.close()

    if not df.empty:
        df['สถานะ'] = df['quality'].apply(get_status)
        df['แก้ไข'] = df['code'].apply(lambda x: f'<a href="/?code={x}" class="btn btn-sm btn-warning"><i class="bi bi-pencil"></i></a>')
        df['ลบ'] = df['code'].apply(lambda x: f'<button onclick="confirmDelete(\'{x}\')" class="btn btn-sm btn-danger"><i class="bi bi-trash"></i></button>')

        # --- เปลี่ยนชื่อคอลัมน์เป็นภาษาไทย ---
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

    # --- ทำให้ทุกเซลล์กึ่งกลาง ---
    def center_cell(val):
        return f'<div class="text-center align-middle">{val}</div>'

    # ใช้ formatters กับทุกคอลัมน์
    formatters = {col: center_cell for col in df.columns}

    table_html = df.to_html(
        escape=False,
        index=False,
        classes="table table-striped table-hover",
        table_id="dataTable",
        formatters=formatters,
        border=0
    )

    list_html = f"""
    <div class="card p-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2 class="text-success">รายการทั้งหมด ({len(df)} รายการ)</h2>
            <div>
                <a href="/export" class="btn btn-success">
                    Export Excel
                </a>
                <a href="/" class="btn btn-outline-primary">
                    เพิ่มข้อมูล
                </a>
            </div>
        </div>
        {table_html if not df.empty else '<div class="alert alert-info">ยังไม่มีข้อมูล</div>'}
    </div>
    """
    return render_template_string(BASE_TEMPLATE, content=list_html)

# --- ลบข้อมูล ---
@app.route('/delete', methods=['POST'])
def delete_entry():
    code = request.form.get('code')
    if not code:
        flash("ไม่พบรหัสตัวอย่าง!", "danger")
        return redirect(url_for('list_entries'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM entries WHERE code=?", (code,))
    conn.commit()
    conn.close()

    flash(f"ลบข้อมูลรหัส {code} เรียบร้อยแล้ว!", "success")
    return redirect(url_for('list_entries'))

# --- Export Excel (ภาษาไทย) ---
@app.route('/export')
def export():
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query("SELECT * FROM entries", conn)
    conn.close()

    # --- แปลงสถานะเป็นข้อความธรรมดา ---
    def clean_status(quality):
        if quality is None:
            return 'ไม่ระบุ'
        elif quality < 50:
            return 'ส่งไปกลุ่ม < 50%'
        elif 50 <= quality < 55:
            return 'ส่งไปกลุ่ม 50 - 54.9%'
        elif 55 <= quality < 60:
            return 'ส่งไปกลุ่ม 55 - 59.9%'
        elif 60 <= quality < 65:
            return 'ส่งไปกลุ่ม 60 - 64.9%'
        elif 65 <= quality < 68:
            return 'ส่งไปกลุ่ม 65 - 67.9%'
        elif 68 <= quality < 70:
            return 'ส่งไปกลุ่ม 68 - 69.9%'
        else:
            return 'ส่งไปกลุ่ม > 70%'

    if not df.empty:
        df['สถานะ'] = df['quality'].apply(clean_status)

        # --- เปลี่ยนชื่อคอลัมน์เป็นภาษาไทย ---
        df = df.rename(columns={
            'date': 'วันที่',
            'code': 'รหัสตัวอย่าง',
            'weight_in': 'น้ำหนักขาเข้า',
            'weight_out': 'น้ำหนักขาออก',
            'quality': 'คุณภาพ'
        })

        df = df[['วันที่', 'รหัสตัวอย่าง', 'น้ำหนักขาเข้า', 'น้ำหนักขาออก', 'คุณภาพ', 'สถานะ']]
    else:
        df = pd.DataFrame(columns=['วันที่', 'รหัสตัวอย่าง', 'น้ำหนักขาเข้า', 'น้ำหนักขาออก', 'คุณภาพ', 'สถานะ'])

    # --- เขียนลง Excel และปรับความกว้างคอลัมน์ ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='ข้อมูลตัวอย่าง')
        
        # ดึง worksheet เพื่อปรับความกว้าง
        worksheet = writer.sheets['ข้อมูลตัวอย่าง']
        
        # ปรับความกว้างแต่ละคอลัมน์
        for idx, column in enumerate(df.columns, 1):  # เริ่มจากคอลัมน์ 1
            # หาความยาวสูงสุดของข้อความในคอลัมน์ (รวม header)
            max_length = max(
                df[column].astype(str).map(len).max(),  # ข้อมูล
                len(str(column))  # ชื่อคอลัมน์
            )
            # ตั้งค่าความกว้าง (1 หน่วย ≈ 1 ตัวอักษร, เพิ่ม padding)
            adjusted_width = min(max_length + 2, 50)  # จำกัดสูงสุด 50
            worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = adjusted_width

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name='ข้อมูลตัวอย่าง.xlsx',
        mimetype='application/vnd.openpyxlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    app.run(debug=True)