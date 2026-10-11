"""DangKy service: coordinates with SinhVien and DeTai through HTTP/REST."""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
from flask import Flask, g, jsonify, request

app = Flask(__name__)
DATA_DIR = Path(os.environ.get('SOA_DATA_DIR', Path(__file__).resolve().parent.parent / 'data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DATA_DIR / 'dangky.sqlite3'
STUDENT_URL = os.environ.get('SINHVIEN_URL', 'http://127.0.0.1:5001').rstrip('/')
TOPIC_URL = os.environ.get('DETAI_URL', 'http://127.0.0.1:5002').rstrip('/')


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
        conn.execute('''CREATE TABLE IF NOT EXISTS dangky (
            ma_dk INTEGER PRIMARY KEY AUTOINCREMENT,
            ma_sv TEXT NOT NULL UNIQUE,
            ma_dt TEXT NOT NULL,
            ngay_dang_ky TEXT NOT NULL,
            diem_huong_dan REAL,
            diem_phan_bien REAL
        )''')
        conn.commit()


def error(message, code=400):
    return jsonify({'error': message}), code


def row_out(row):
    data = dict(row)
    a, b = data['diem_huong_dan'], data['diem_phan_bien']
    # Quy tac DEMO: trung binh cong, KHONG phai cong thuc do giang vien cung cap.
    data['diem_trung_binh'] = round((a + b) / 2, 2) if a is not None and b is not None else None
    return data


def validate(data):
    if not isinstance(data, dict):
        return None, 'Du lieu phai la JSON object'
    ma_sv = str(data.get('ma_sv', '')).strip()
    ma_dt = str(data.get('ma_dt', '')).strip()
    if not ma_sv or not ma_dt or len(ma_sv) > 20 or len(ma_dt) > 20:
        return None, 'Can ma_sv va ma_dt hop le'
    a = data.get('diem_huong_dan')
    b = data.get('diem_phan_bien')
    a = None if a in (None, '') else a
    b = None if b in (None, '') else b
    if (a is None) != (b is None):
        return None, 'Nhap ca hai diem hoac de trong ca hai'
    if a is not None:
        try:
            if isinstance(a, bool) or isinstance(b, bool):
                raise ValueError
            a, b = float(a), float(b)
            if not (0 <= a <= 10 and 0 <= b <= 10):
                raise ValueError
        except (ValueError, TypeError):
            return None, 'Diem phai tu 0 den 10'
    return {'ma_sv': ma_sv, 'ma_dt': ma_dt, 'diem_huong_dan': a, 'diem_phan_bien': b}, None


def get_remote(base, resource, code):
    """Return (JSON object, None) or (None, response error tuple)."""
    try:
        response = requests.get(f'{base}/api/{resource}/{quote(code, safe="")}', timeout=3)
    except requests.RequestException:
        return None, error(f'Dich vu {resource} khong phan hoi', 503)
    if response.status_code == 404:
        return None, error(f'{resource} khong ton tai: {code}', 422)
    if not response.ok:
        return None, error(f'Khong the xac minh {resource} (HTTP {response.status_code})', 502)
    try:
        return response.json(), None
    except ValueError:
        return None, error(f'Dich vu {resource} tra ve JSON khong hop le', 502)


def validate_refs_and_capacity(clean, exclude=None):
    _, err = get_remote(STUDENT_URL, 'sinhvien', clean['ma_sv'])
    if err:
        return err
    topic, err = get_remote(TOPIC_URL, 'detai', clean['ma_dt'])
    if err:
        return err
    query = 'SELECT COUNT(*) FROM dangky WHERE ma_dt=?'
    args = [clean['ma_dt']]
    if exclude is not None:
        query += ' AND ma_dk<>?'
        args.append(exclude)
    count = db().execute(query, args).fetchone()[0]
    if count >= topic['so_luong_toi_da']:
        return error('De tai da du so luong dang ky', 409)
    return None


@app.get('/api/health')
def health():
    return jsonify({'service': 'dangky', 'status': 'ok', 'depends_on': ['sinhvien', 'detai']})


@app.get('/api/dangky')
def list_registrations():
    rows = db().execute('SELECT * FROM dangky ORDER BY ma_dk DESC').fetchall()
    return jsonify([row_out(row) for row in rows])


@app.get('/api/dangky/<int:ma_dk>')
def get_registration(ma_dk):
    row = db().execute('SELECT * FROM dangky WHERE ma_dk=?', (ma_dk,)).fetchone()
    if row is None:
        return error('Khong tim thay dang ky', 404)
    return jsonify(row_out(row))


@app.post('/api/dangky')
def add_registration():
    clean, err = validate(request.get_json(silent=True))
    if err:
        return error(err)
    remote_err = validate_refs_and_capacity(clean)
    if remote_err:
        return remote_err
    try:
        cursor = db().execute('''INSERT INTO dangky
            (ma_sv, ma_dt, ngay_dang_ky, diem_huong_dan, diem_phan_bien)
            VALUES (?, ?, ?, ?, ?)''',
            (clean['ma_sv'], clean['ma_dt'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             clean['diem_huong_dan'], clean['diem_phan_bien']))
        db().commit()
    except sqlite3.IntegrityError:
        return error('Sinh vien da dang ky de tai', 409)
    row = db().execute('SELECT * FROM dangky WHERE ma_dk=?', (cursor.lastrowid,)).fetchone()
    return jsonify(row_out(row)), 201


@app.put('/api/dangky/<int:ma_dk>')
def update_registration(ma_dk):
    previous = db().execute('SELECT * FROM dangky WHERE ma_dk=?', (ma_dk,)).fetchone()
    if previous is None:
        return error('Khong tim thay dang ky', 404)
    clean, err = validate(request.get_json(silent=True))
    if err:
        return error(err)
    remote_err = validate_refs_and_capacity(clean, exclude=ma_dk)
    if remote_err:
        return remote_err
    try:
        db().execute('''UPDATE dangky SET ma_sv=?, ma_dt=?,
            diem_huong_dan=?, diem_phan_bien=? WHERE ma_dk=?''',
            (clean['ma_sv'], clean['ma_dt'], clean['diem_huong_dan'], clean['diem_phan_bien'], ma_dk))
        db().commit()
    except sqlite3.IntegrityError:
        return error('Sinh vien da dang ky de tai khac', 409)
    row = db().execute('SELECT * FROM dangky WHERE ma_dk=?', (ma_dk,)).fetchone()
    return jsonify(row_out(row))


@app.delete('/api/dangky/<int:ma_dk>')
def delete_registration(ma_dk):
    cursor = db().execute('DELETE FROM dangky WHERE ma_dk=?', (ma_dk,))
    db().commit()
    if cursor.rowcount == 0:
        return error('Khong tim thay dang ky', 404)
    return jsonify({'message': 'Da xoa dang ky', 'ma_dk': ma_dk})


init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('DANGKY_PORT', '5003')), debug=False)
