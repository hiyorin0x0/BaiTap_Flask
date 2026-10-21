"""SinhVien service: owns its own SQLite database and CRUD APIs."""
import os
import sys
import re
import sqlite3
from pathlib import Path
from flask import Flask, g, jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.jwt_auth import protect  # noqa: E402

app = Flask(__name__)
protect(app)  # moi request (tru /api/health) phai co JWT hop le
DATA_DIR = Path(os.environ.get('SOA_DATA_DIR', Path(__file__).resolve().parent.parent / 'data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DATA_DIR / 'sinhvien.sqlite3'


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA busy_timeout=3000')
    return g.db


@app.teardown_appcontext
def close_db(exc):
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS sinhvien (
            ma_sv TEXT PRIMARY KEY, ho_ten TEXT NOT NULL,
            lop TEXT NOT NULL, email TEXT NOT NULL UNIQUE
        )''')
        if conn.execute('SELECT COUNT(*) FROM sinhvien').fetchone()[0] == 0:
            conn.executemany('INSERT INTO sinhvien VALUES (?, ?, ?, ?)', [
                ('SV001', 'Nguyen Van An', 'CNTT01', 'an@example.edu.vn'),
                ('SV002', 'Tran Thi Binh', 'CNTT01', 'binh@example.edu.vn'),
                ('SV003', 'Le Minh Cuong', 'CNTT02', 'cuong@example.edu.vn'),
            ])
        conn.commit()


def error(message, code=400):
    return jsonify({'error': message}), code


def validate(data, is_create):
    if not isinstance(data, dict):
        return None, 'Du lieu phai la JSON object'
    required = ['ho_ten', 'lop', 'email'] + (['ma_sv'] if is_create else [])
    clean = {key: str(data.get(key, '')).strip() for key in required}
    if not all(clean.values()):
        return None, 'Vui long nhap day du: ' + ', '.join(required)
    if is_create and not re.fullmatch(r'[A-Za-z0-9_-]{2,20}', clean['ma_sv']):
        return None, 'ma_sv chi gom chu, so, _ hoac - (2-20 ky tu)'
    if len(clean['ho_ten']) > 100 or len(clean['lop']) > 40 or len(clean['email']) > 120:
        return None, 'Du lieu qua dai'
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', clean['email']):
        return None, 'Email khong hop le'
    return clean, None


@app.get('/api/health')
def health():
    return jsonify({'service': 'sinhvien', 'status': 'ok'})


@app.get('/api/sinhvien')
def list_students():
    if g.user.get('role') == 'sinhvien':
        ma_sv = g.user.get('ma_sv')
        if not ma_sv:
            return error('Tai khoan sinh vien chua duoc gan ma sinh vien', 403)
        rows = db().execute('SELECT * FROM sinhvien WHERE ma_sv=?', (ma_sv,)).fetchall()
    else:
        rows = db().execute('SELECT * FROM sinhvien ORDER BY ma_sv').fetchall()
    return jsonify([dict(row) for row in rows])


@app.get('/api/sinhvien/<string:ma_sv>')
def get_student(ma_sv):
    row = db().execute('SELECT * FROM sinhvien WHERE ma_sv=?', (ma_sv,)).fetchone()
    if row is None:
        return error('Khong tim thay sinh vien', 404)
    return jsonify(dict(row))


@app.post('/api/sinhvien')
def add_student():
    clean, err = validate(request.get_json(silent=True), True)
    if err:
        return error(err)
    try:
        db().execute('INSERT INTO sinhvien (ma_sv, ho_ten, lop, email) VALUES (?, ?, ?, ?)',
                     (clean['ma_sv'], clean['ho_ten'], clean['lop'], clean['email']))
        db().commit()
    except sqlite3.IntegrityError:
        return error('Ma sinh vien hoac email da ton tai', 409)
    return jsonify(clean), 201


@app.put('/api/sinhvien/<string:ma_sv>')
def update_student(ma_sv):
    clean, err = validate(request.get_json(silent=True), False)
    if err:
        return error(err)
    try:
        cursor = db().execute('UPDATE sinhvien SET ho_ten=?, lop=?, email=? WHERE ma_sv=?',
                              (clean['ho_ten'], clean['lop'], clean['email'], ma_sv))
        db().commit()
    except sqlite3.IntegrityError:
        return error('Email da duoc su dung', 409)
    if cursor.rowcount == 0:
        return error('Khong tim thay sinh vien', 404)
    return jsonify({'ma_sv': ma_sv, **clean})


@app.delete('/api/sinhvien/<string:ma_sv>')
def delete_student(ma_sv):
    cursor = db().execute('DELETE FROM sinhvien WHERE ma_sv=?', (ma_sv,))
    db().commit()
    if cursor.rowcount == 0:
        return error('Khong tim thay sinh vien', 404)
    return jsonify({'message': 'Da xoa sinh vien', 'ma_sv': ma_sv})


init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('SINHVIEN_PORT', '5001')), debug=False)
