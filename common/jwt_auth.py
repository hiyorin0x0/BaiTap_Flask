"""JWT dung chung cho moi service: tao token va kiem tra token (HS256)."""
import os
from datetime import datetime, timedelta, timezone

import jwt
from flask import g, jsonify, request

# Khoa bi mat dung chung. Demo lop hoc: doi bang bien moi truong JWT_SECRET khi can.
JWT_SECRET = os.environ.get('JWT_SECRET', 'soa-demo-jwt-secret-key-only-for-classroom-2026')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '30'))

# Endpoint khong can token
PUBLIC_PATHS = {'/api/health', '/api/auth/login'}


def create_token(username, role, ma_sv=None):
    """Auth Service goi ham nay sau khi dang nhap dung."""
    now = datetime.now(timezone.utc)
    payload = {
        'sub': username,          # ai
        'role': role,             # quyen: admin / viewer / sinhvien
        'iat': now,               # thoi diem phat hanh
        'exp': now + timedelta(minutes=JWT_EXPIRE_MINUTES),  # het han
    }
    if role == 'sinhvien' and ma_sv:
        payload['ma_sv'] = ma_sv
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token):
    """Kiem tra chu ky + han su dung. Loi thi nem jwt.PyJWTError."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def _deny(message, code):
    return jsonify({'error': message}), code


def protect(app):
    """Gan bo loc cho moi request cua service:
    - Khong co/sai/het han token -> 401
    - admin: toan quyen
    - viewer: chi doc
    - sinhvien: doc du lieu duoc phan quyen, de xuat de tai, tao/huy dang ky cua minh
    """
    @app.before_request
    def check_jwt():
        if request.path in PUBLIC_PATHS or request.method == 'OPTIONS':
            return None
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return _deny('Thieu token. Gui header Authorization: Bearer <token>', 401)
        try:
            claims = decode_token(header[7:].strip())
        except jwt.ExpiredSignatureError:
            return _deny('Token da het han, vui long dang nhap lai', 401)
        except jwt.PyJWTError:
            return _deny('Token khong hop le', 401)
        g.user = claims
        role = claims.get('role')
        if role not in {'admin', 'viewer', 'sinhvien'}:
            return _deny('Role khong hop le', 403)
        if role == 'sinhvien' and (not isinstance(claims.get('ma_sv'), str) or not claims['ma_sv']):
            return _deny('Tai khoan sinh vien chua duoc gan ma sinh vien', 403)

        if request.method in {'GET', 'HEAD'}:
            if role == 'sinhvien' and request.path.startswith('/api/sinhvien/'):
                own_student_id = claims.get('ma_sv')
                requested_student_id = request.path.rsplit('/', 1)[-1]
                if not own_student_id or requested_student_id != own_student_id:
                    return _deny('Sinh vien chi duoc xem ho so cua minh', 403)
            return None

        if role == 'admin':
            return None

        if role == 'sinhvien' and request.method == 'POST' and request.path == '/api/dangky':
            data = request.get_json(silent=True)
            own_student_id = claims.get('ma_sv')
            if not own_student_id or not isinstance(data, dict) or data.get('ma_sv') != own_student_id:
                return _deny('Sinh vien chi duoc dang ky cho chinh minh', 403)
            if 'diem_huong_dan' in data or 'diem_phan_bien' in data:
                return _deny('Sinh vien khong duoc nhap diem', 403)
            return None

        if role == 'sinhvien' and request.method == 'POST' and request.path == '/api/detai':
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or not data.get('ten_dt'):
                return _deny('Can ten de tai de gui de xuat', 400)
            if {'ma_dt', 'so_luong_toi_da', 'trang_thai', 'nguoi_de_xuat_ma_sv'} & data.keys():
                return _deny('Sinh vien khong duoc tu dat ma, chi tieu hoac trang thai de tai', 403)
            return None

        if (role == 'sinhvien' and request.method == 'DELETE'
                and request.path.startswith('/api/dangky/')
                and request.path.rsplit('/', 1)[-1].isdigit()):
            # DangKy Service tu kiem tra quyen so huu va trang thai co the huy.
            return None

        return _deny('Khong du quyen thuc hien thao tac nay', 403)
