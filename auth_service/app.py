"""Auth service: kiem tra tai khoan va phat hanh JWT cho cac service khac."""
import os
import sys
from pathlib import Path

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.jwt_auth import JWT_EXPIRE_MINUTES, create_token, protect  # noqa: E402

app = Flask(__name__)

# Tai khoan demo (mat khau luu dang bam, khong luu van ban thuong)
USERS = {
    'admin': {'password_hash': generate_password_hash('admin123'), 'role': 'admin'},
    'viewer': {'password_hash': generate_password_hash('viewer123'), 'role': 'viewer'},
    'sv001': {'password_hash': generate_password_hash('sv001123'), 'role': 'sinhvien', 'ma_sv': 'SV001'},
}


def error(message, code=400):
    return jsonify({'error': message}), code


@app.get('/api/health')
def health():
    return jsonify({'service': 'auth', 'status': 'ok'})


@app.post('/api/auth/login')
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error('Du lieu phai la JSON object')
    username = str(data.get('username', '')).strip().lower()
    password = str(data.get('password', ''))
    user = USERS.get(username)
    if user is None or not check_password_hash(user['password_hash'], password):
        return error('Sai ten dang nhap hoac mat khau', 401)
    if user['role'] == 'sinhvien' and not user.get('ma_sv'):
        return error('Tai khoan sinh vien chua duoc gan ma sinh vien', 403)
    response = {
        'access_token': create_token(username, user['role'], user.get('ma_sv')),
        'token_type': 'Bearer',
        'expires_in': JWT_EXPIRE_MINUTES * 60,
        'username': username,
        'role': user['role'],
    }
    if user.get('ma_sv'):
        response['ma_sv'] = user['ma_sv']
    return jsonify(response)


@app.get('/api/auth/me')
def me():
    """Can token hop le: tra ve thong tin lay tu payload."""
    result = {'username': g.user['sub'], 'role': g.user['role']}
    if g.user.get('role') == 'sinhvien':
        result['ma_sv'] = g.user['ma_sv']
    return jsonify(result)


protect(app)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('AUTH_PORT', '5004')), debug=False)
