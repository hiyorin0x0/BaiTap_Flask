"""DeTai service: independently serves topic information over HTTP/JSON."""
import os
import re
import sqlite3
from pathlib import Path
from flask import Flask, g, jsonify, request

app = Flask(__name__)
DATA_DIR = Path(os.environ.get('SOA_DATA_DIR', Path(__file__).resolve().parent.parent / 'data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DATA_DIR / 'detai.sqlite3'


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
        conn.execute('''CREATE TABLE IF NOT EXISTS detai (
            ma_dt TEXT PRIMARY KEY,
            ten_dt TEXT NOT NULL,
            mo_ta TEXT NOT NULL DEFAULT '',
            so_luong_toi_da INTEGER NOT NULL DEFAULT 1
        )''')
        if conn.execute('SELECT COUNT(*) FROM detai').fetchone()[0] == 0:
            conn.executemany('INSERT INTO detai VALUES (?, ?, ?, ?)', [
                ('DT001', 'Xay dung website quan ly thu vien', 'Demo REST API', 2),
                ('DT002', 'Phat trien ung dung truyen file Wi-Fi', 'Ung dung mang may tinh', 2),
                ('DT003', 'He thong nhan dien hinh anh', 'Mo hinh AI co ban', 1),
            ])
        conn.commit()


def error(message, code=400):
    return jsonify({'error': message}), code


def validate(data, is_create):
    if not isinstance(data, dict):
        return None, 'Du lieu phai la JSON object'
    clean = {key: str(data.get(key, '')).strip() for key in (['ma_dt'] if is_create else []) + ['ten_dt', 'mo_ta']}
    if not clean['ten_dt'] or (is_create and not clean['ma_dt']):
        return None, 'Ma de tai va ten de tai la bat buoc'
    if is_create and not re.fullmatch(r'[A-Za-z0-9_-]{2,20}', clean['ma_dt']):
        return None, 'ma_dt chi gom chu, so, _ hoac - (2-20 ky tu)'
    if len(clean['ten_dt']) > 200 or len(clean['mo_ta']) > 1000:
        return None, 'Du lieu qua dai'
    try:
        capacity_raw = data.get('so_luong_toi_da', 1)
        if isinstance(capacity_raw, bool):
            raise ValueError
        capacity = int(capacity_raw)
        if str(capacity) != str(capacity_raw).strip() or not 1 <= capacity <= 100:
            raise ValueError
    except (ValueError, TypeError):
        return None, 'so_luong_toi_da phai la so nguyen tu 1 den 100'
    clean['so_luong_toi_da'] = capacity
    return clean, None


@app.get('/api/health')
def health():
    return jsonify({'service': 'detai', 'status': 'ok'})


@app.get('/api/detai')
def list_topics():
    return jsonify([dict(row) for row in db().execute('SELECT * FROM detai ORDER BY ma_dt').fetchall()])


@app.get('/api/detai/<string:ma_dt>')
def get_topic(ma_dt):
    row = db().execute('SELECT * FROM detai WHERE ma_dt=?', (ma_dt,)).fetchone()
    if row is None:
        return error('Khong tim thay de tai', 404)
    return jsonify(dict(row))


@app.post('/api/detai')
def add_topic():
    clean, err = validate(request.get_json(silent=True), True)
    if err:
        return error(err)
    try:
        db().execute('INSERT INTO detai (ma_dt, ten_dt, mo_ta, so_luong_toi_da) VALUES (?, ?, ?, ?)',
                     (clean['ma_dt'], clean['ten_dt'], clean['mo_ta'], clean['so_luong_toi_da']))
        db().commit()
    except sqlite3.IntegrityError:
        return error('Ma de tai da ton tai', 409)
    return jsonify(clean), 201


@app.put('/api/detai/<string:ma_dt>')
def update_topic(ma_dt):
    clean, err = validate(request.get_json(silent=True), False)
    if err:
        return error(err)
    cursor = db().execute('UPDATE detai SET ten_dt=?, mo_ta=?, so_luong_toi_da=? WHERE ma_dt=?',
                          (clean['ten_dt'], clean['mo_ta'], clean['so_luong_toi_da'], ma_dt))
    db().commit()
    if cursor.rowcount == 0:
        return error('Khong tim thay de tai', 404)
    return jsonify({'ma_dt': ma_dt, **clean})


@app.delete('/api/detai/<string:ma_dt>')
def delete_topic(ma_dt):
    cursor = db().execute('DELETE FROM detai WHERE ma_dt=?', (ma_dt,))
    db().commit()
    if cursor.rowcount == 0:
        return error('Khong tim thay de tai', 404)
    return jsonify({'message': 'Da xoa de tai', 'ma_dt': ma_dt})


init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('DETAI_PORT', '5002')), debug=False)
