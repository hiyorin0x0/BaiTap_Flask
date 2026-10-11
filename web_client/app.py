"""Server-rendered demo client that calls the 3 service APIs over HTTP."""
import os
from urllib.parse import quote

import requests
from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SOA_SECRET_KEY', 'only-for-local-classroom-demo')
SERVICES = {
    'sinhvien': os.environ.get('SINHVIEN_URL', 'http://127.0.0.1:5001').rstrip('/'),
    'detai': os.environ.get('DETAI_URL', 'http://127.0.0.1:5002').rstrip('/'),
    'dangky': os.environ.get('DANGKY_URL', 'http://127.0.0.1:5003').rstrip('/'),
}


class APIError(Exception):
    pass


def api(service, method, path='', payload=None):
    url = f'{SERVICES[service]}/api/{service}{path}'
    try:
        response = requests.request(method, url, json=payload, timeout=4)
    except requests.RequestException:
        raise APIError(f'Khong ket noi duoc dich vu {service}. Kiem tra run_all.py.')
    try:
        value = response.json()
    except ValueError:
        raise APIError(f'Dich vu {service} tra ve du lieu khong hop le')
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


@app.get('/')
def index():
    status = {}
    for key, url in SERVICES.items():
        try:
            response = requests.get(url + '/api/health', timeout=1.5)
            status[key] = response.ok
        except requests.RequestException:
            status[key] = False
    return render_template('index.html', status=status, services=SERVICES)


@app.get('/sinhvien')
def sinhvien():
    rows = list_safe('sinhvien')
    selected = next((row for row in rows if row['ma_sv'] == request.args.get('edit')), None)
    return render_template('sinhvien.html', rows=rows, selected=selected)


@app.post('/sinhvien/save')
def save_student():
    data = {k: request.form.get(k, '').strip() for k in ('ma_sv', 'ho_ten', 'lop', 'email')}
    if request.form.get('mode') == 'edit':
        key = quote(data.pop('ma_sv'), safe='')
        return submit('sinhvien', 'PUT', '/' + key, data, 'Da cap nhat sinh vien')
    return submit('sinhvien', 'POST', '', data, 'Da them sinh vien')


@app.post('/sinhvien/delete')
def delete_student():
    return submit('sinhvien', 'DELETE', '/' + quote(request.form.get('ma_sv', ''), safe=''), None,
                  'Da xoa sinh vien')


@app.get('/detai')
def detai():
    rows = list_safe('detai')
    selected = next((row for row in rows if row['ma_dt'] == request.args.get('edit')), None)
    return render_template('detai.html', rows=rows, selected=selected)


@app.post('/detai/save')
def save_topic():
    data = {k: request.form.get(k, '').strip() for k in ('ma_dt', 'ten_dt', 'mo_ta', 'so_luong_toi_da')}
    if request.form.get('mode') == 'edit':
        key = quote(data.pop('ma_dt'), safe='')
        return submit('detai', 'PUT', '/' + key, data, 'Da cap nhat de tai')
    return submit('detai', 'POST', '', data, 'Da them de tai')


@app.post('/detai/delete')
def delete_topic():
    return submit('detai', 'DELETE', '/' + quote(request.form.get('ma_dt', ''), safe=''), None,
                  'Da xoa de tai')


@app.get('/dangky')
def dangky():
    rows = list_safe('dangky')
    students = list_safe('sinhvien')
    topics = list_safe('detai')
    selected = next((row for row in rows if str(row['ma_dk']) == request.args.get('edit')), None)
    return render_template('dangky.html', rows=rows, students=students, topics=topics,
                           student_names={x['ma_sv']: x['ho_ten'] for x in students},
                           topic_names={x['ma_dt']: x['ten_dt'] for x in topics}, selected=selected)


@app.post('/dangky/save')
def save_registration():
    data = {key: request.form.get(key, '').strip()
            for key in ('ma_sv', 'ma_dt', 'diem_huong_dan', 'diem_phan_bien')}
    if request.form.get('mode') == 'edit':
        key = request.form.get('ma_dk', '')
        if not key.isdigit():
            flash('Ma dang ky khong hop le', 'error')
            return redirect(url_for('dangky'))
        return submit('dangky', 'PUT', '/' + key, data, 'Da cap nhat dang ky')
    return submit('dangky', 'POST', '', data, 'Da dang ky de tai')


@app.post('/dangky/delete')
def delete_registration():
    key = request.form.get('ma_dk', '')
    if not key.isdigit():
        flash('Ma dang ky khong hop le', 'error')
        return redirect(url_for('dangky'))
    return submit('dangky', 'DELETE', '/' + key, None, 'Da xoa dang ky')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('WEB_PORT', '5000')), debug=False)
