"""Server-rendered demo client that calls the 3 service APIs over HTTP."""
import base64
from functools import wraps
import json
import os
from urllib.parse import quote

import requests
from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SOA_SECRET_KEY', 'only-for-local-classroom-demo')
SERVICES = {
    'sinhvien': os.environ.get('SINHVIEN_URL', 'http://127.0.0.1:5001').rstrip('/'),
    'detai': os.environ.get('DETAI_URL', 'http://127.0.0.1:5002').rstrip('/'),
    'dangky': os.environ.get('DANGKY_URL', 'http://127.0.0.1:5003').rstrip('/'),
}
AUTH_URL = os.environ.get('AUTH_URL', 'http://127.0.0.1:5004').rstrip('/')


class APIError(Exception):
    pass


class AuthExpired(Exception):
    """Service tra 401: token het han / khong hop le."""


@app.errorhandler(AuthExpired)
def on_auth_expired(_exc):
    session.clear()
    flash('Phien dang nhap het han, vui long dang nhap lai', 'error')
    return redirect(url_for('login'))


@app.before_request
def require_login():
    """Chua co JWT trong session thi chuyen sang trang dang nhap."""
    if request.endpoint in ('login', 'static') or 'token' in session:
        return None
    return redirect(url_for('login'))


@app.context_processor
def inject_user():
    return {
        'current_user': session.get('username'),
        'current_role': session.get('role'),
        'current_student_id': session.get('ma_sv'),
    }


def roles_required(*roles):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Tài khoản của bạn không có quyền thực hiện thao tác này.', 'error')
                return redirect(url_for('index'))
            return view(*args, **kwargs)
        return wrapped
    return decorate


def api(service, method, path='', payload=None):
    url = f'{SERVICES[service]}/api/{service}{path}'
    try:
        # Moi lan goi service deu dinh kem JWT trong header Authorization
        response = requests.request(method, url, json=payload, timeout=4,
                                    headers={'Authorization': 'Bearer ' + session.get('token', '')})
    except requests.RequestException:
        raise APIError(f'Khong ket noi duoc dich vu {service}. Kiem tra run_all.py.')
    try:
        value = response.json()
    except ValueError:
        raise APIError(f'Dich vu {service} tra ve du lieu khong hop le')
    if response.status_code == 401:
        raise AuthExpired()
    if not response.ok:
        raise APIError(value.get('error', f'HTTP {response.status_code}') if isinstance(value, dict) else f'HTTP {response.status_code}')
    return value


def list_safe(service):
    try:
        return api(service, 'GET')
    except APIError as exc:
        flash(str(exc), 'error')
        return []


def submit(service, method, path, payload, success_message):
    try:
        api(service, method, path, payload)
        flash(success_message, 'success')
    except APIError as exc:
        flash(str(exc), 'error')
    return redirect(url_for(service))


def b64_json(part):
    return json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            response = requests.post(AUTH_URL + '/api/auth/login', timeout=4, json={
                'username': request.form.get('username', ''), 'password': request.form.get('password', '')})
            value = response.json()
        except (requests.RequestException, ValueError):
            flash('Khong ket noi duoc Auth Service. Kiem tra run_all.py.', 'error')
            return render_template('login.html')
        if not response.ok:
            flash(value.get('error', 'Dang nhap that bai'), 'error')
            return render_template('login.html')
        session.clear()
        session['token'] = value['access_token']      # luu JWT
        session['username'] = value['username']
        session['role'] = value['role']
        session['ma_sv'] = value.get('ma_sv')
        return redirect(url_for('index'))
    return render_template('login.html')


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.get('/jwt')
@roles_required('admin')
def jwt_view():
    """Trang giai ma JWT de trinh bay: header, payload, signature."""
    token = session['token']
    head, payload, signature = token.split('.')
    return render_template('jwt.html', token=token, head=json.dumps(b64_json(head), indent=2),
                           payload=json.dumps(b64_json(payload), indent=2), signature=signature)


@app.get('/')
def index():
    status = {}
    for key, url in {**SERVICES, 'auth': AUTH_URL}.items():
        try:
            response = requests.get(url + '/api/health', timeout=1.5)
            status[key] = response.ok
        except requests.RequestException:
            status[key] = False
    return render_template('index.html', status=status, services={**SERVICES, 'auth': AUTH_URL})


@app.get('/sinhvien')
def sinhvien():
    rows = list_safe('sinhvien')
    selected = next((row for row in rows if row['ma_sv'] == request.args.get('edit')), None)
    profile_available = session.get('role') != 'sinhvien' or any(
        row['ma_sv'] == session.get('ma_sv') for row in rows)
    return render_template('sinhvien.html', rows=rows, selected=selected,
                           profile_available=profile_available)


@app.post('/sinhvien/save')
@roles_required('admin')
def save_student():
    data = {k: request.form.get(k, '').strip() for k in ('ma_sv', 'ho_ten', 'lop', 'email')}
    if request.form.get('mode') == 'edit':
        key = quote(data.pop('ma_sv'), safe='')
        return submit('sinhvien', 'PUT', '/' + key, data, 'Da cap nhat sinh vien')
    return submit('sinhvien', 'POST', '', data, 'Da them sinh vien')


@app.post('/sinhvien/delete')
@roles_required('admin')
def delete_student():
    return submit('sinhvien', 'DELETE', '/' + quote(request.form.get('ma_sv', ''), safe=''), None,
                  'Da xoa sinh vien')


@app.get('/detai')
def detai():
    rows = list_safe('detai')
    selected = next((row for row in rows if row['ma_dt'] == request.args.get('edit')), None)
    return render_template('detai.html', rows=rows, selected=selected)


@app.post('/detai/save')
@roles_required('admin')
def save_topic():
    data = {k: request.form.get(k, '').strip() for k in ('ma_dt', 'ten_dt', 'mo_ta', 'so_luong_toi_da')}
    if request.form.get('mode') == 'edit':
        key = quote(data.pop('ma_dt'), safe='')
        return submit('detai', 'PUT', '/' + key, data, 'Da cap nhat de tai')
    return submit('detai', 'POST', '', data, 'Da them de tai')


@app.post('/detai/delete')
@roles_required('admin')
def delete_topic():
    return submit('detai', 'DELETE', '/' + quote(request.form.get('ma_dt', ''), safe=''), None,
                  'Da xoa de tai')


@app.post('/detai/de-xuat')
@roles_required('sinhvien')
def propose_topic():
    data = {key: request.form.get(key, '').strip() for key in ('ten_dt', 'mo_ta')}
    return submit('detai', 'POST', '', data, 'Đã gửi đề xuất đề tài, chờ admin duyệt.')


@app.post('/detai/duyet')
@roles_required('admin')
def approve_topic():
    key = quote(request.form.get('ma_dt', ''), safe='')
    if not key:
        flash('Mã đề tài không hợp lệ.', 'error')
        return redirect(url_for('detai'))
    return submit('detai', 'PATCH', '/' + key + '/trang-thai',
                  {'trang_thai': 'da_duyet'}, 'Đã duyệt đề xuất đề tài.')


@app.post('/detai/tu-choi')
@roles_required('admin')
def reject_topic():
    key = quote(request.form.get('ma_dt', ''), safe='')
    if not key:
        flash('Mã đề tài không hợp lệ.', 'error')
        return redirect(url_for('detai'))
    return submit('detai', 'PATCH', '/' + key + '/trang-thai',
                  {'trang_thai': 'tu_choi'}, 'Đã từ chối đề xuất đề tài.')


@app.get('/dangky')
def dangky():
    rows = list_safe('dangky')
    students = list_safe('sinhvien')
    topics = [topic for topic in list_safe('detai')
              if topic.get('trang_thai', 'da_duyet') == 'da_duyet']
    selected = next((row for row in rows if str(row['ma_dk']) == request.args.get('edit')), None)
    role = session.get('role')
    student_can_register = role == 'sinhvien' and bool(students) and bool(topics) and not rows
    can_student_remove_registration = role == 'sinhvien' and any(
        row.get('trang_thai') in {'cho_duyet', 'tu_choi'} for row in rows)
    return render_template('dangky.html', rows=rows, students=students, topics=topics,
                           student_names={x['ma_sv']: x['ho_ten'] for x in students},
                           topic_names={x['ma_dt']: x['ten_dt'] for x in topics}, selected=selected,
                           can_register=(role == 'admin' or student_can_register),
                           student_profile_available=bool(students), topics_available=bool(topics),
                           show_registration_actions=(role == 'admin' or can_student_remove_registration))


@app.post('/dangky/save')
@roles_required('admin', 'sinhvien')
def save_registration():
    role = session.get('role')
    if role == 'sinhvien':
        if not session.get('ma_sv'):
            flash('Tài khoản sinh viên chưa được liên kết với mã sinh viên.', 'error')
            return redirect(url_for('dangky'))
        if request.form.get('mode') == 'edit':
            flash('Sinh viên không có quyền sửa đăng ký.', 'error')
            return redirect(url_for('dangky'))
        data = {
            'ma_sv': session.get('ma_sv', ''),
            'ma_dt': request.form.get('ma_dt', '').strip(),
        }
    else:
        data = {key: request.form.get(key, '').strip()
                for key in ('ma_sv', 'ma_dt', 'diem_huong_dan', 'diem_phan_bien')}
    if request.form.get('mode') == 'edit':
        key = request.form.get('ma_dk', '')
        if not key.isdigit():
            flash('Ma dang ky khong hop le', 'error')
            return redirect(url_for('dangky'))
        return submit('dangky', 'PUT', '/' + key, data, 'Da cap nhat dang ky')
    success_message = 'Đã gửi đăng ký, đang chờ duyệt.' if role == 'sinhvien' else 'Đã đăng ký đề tài.'
    return submit('dangky', 'POST', '', data, success_message)


@app.post('/dangky/duyet')
@roles_required('admin')
def approve_registration():
    key = request.form.get('ma_dk', '')
    if not key.isdigit():
        flash('Mã đăng ký không hợp lệ.', 'error')
        return redirect(url_for('dangky'))
    return submit('dangky', 'PATCH', '/' + key + '/trang-thai',
                  {'trang_thai': 'da_duyet'}, 'Đã duyệt đăng ký.')


@app.post('/dangky/tu-choi')
@roles_required('admin')
def reject_registration():
    key = request.form.get('ma_dk', '')
    if not key.isdigit():
        flash('Mã đăng ký không hợp lệ.', 'error')
        return redirect(url_for('dangky'))
    return submit('dangky', 'PATCH', '/' + key + '/trang-thai',
                  {'trang_thai': 'tu_choi'}, 'Đã từ chối đăng ký.')


@app.post('/dangky/delete')
@roles_required('admin', 'sinhvien')
def delete_registration():
    key = request.form.get('ma_dk', '')
    if not key.isdigit():
        flash('Ma dang ky khong hop le', 'error')
        return redirect(url_for('dangky'))
    success_message = ('Đã hủy/xóa đăng ký của bạn.' if session.get('role') == 'sinhvien'
                       else 'Đã xóa đăng ký.')
    return submit('dangky', 'DELETE', '/' + key, None, success_message)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('WEB_PORT', '5000')), debug=False)
