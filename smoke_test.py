"""Integration tests against running local services (start run_all.py first)."""
import os
import sys
import uuid

import requests

SV = os.environ.get('SINHVIEN_URL', 'http://127.0.0.1:5001').rstrip('/') + '/api/sinhvien'
DT = os.environ.get('DETAI_URL', 'http://127.0.0.1:5002').rstrip('/') + '/api/detai'
DK = os.environ.get('DANGKY_URL', 'http://127.0.0.1:5003').rstrip('/') + '/api/dangky'


def check(method, url, status, **kwargs):
    response = requests.request(method, url, timeout=5, **kwargs)
    if response.status_code != status:
        raise AssertionError(f'{method} {url}: expected {status}, got {response.status_code}: {response.text}')
    print(f'  [OK] {method:<6} HTTP {status} {url}')
    return response.json()


def main():
    suffix = uuid.uuid4().hex[:8].upper()
    s1, s2, topic = f'TESTA{suffix}', f'TESTB{suffix}', f'TEST{suffix}'
    registration_id = None
    print('Starting SOA integration test (requires running services)...')
    try:
        for url in [SV, DT, DK]:
            check('GET', url, 200)
        check('POST', SV, 201, json={'ma_sv': s1, 'ho_ten': 'Demo A', 'lop': 'TEST01', 'email': f'{s1.lower()}@example.edu.vn'})
        check('POST', SV, 201, json={'ma_sv': s2, 'ho_ten': 'Demo B', 'lop': 'TEST02', 'email': f'{s2.lower()}@example.edu.vn'})
        check('GET', SV + '/' + s1, 200)
        check('PUT', SV + '/' + s1, 200, json={'ho_ten': 'Demo A New', 'lop': 'TEST01', 'email': f'{s1.lower()}@example.edu.vn'})
        check('POST', DT, 201, json={'ma_dt': topic, 'ten_dt': 'Test SOA integration', 'mo_ta': 'Auto test', 'so_luong_toi_da': 1})
        check('GET', DT + '/' + topic, 200)
        check('PUT', DT + '/' + topic, 200, json={'ten_dt': 'Test SOA REST', 'mo_ta': 'Updated', 'so_luong_toi_da': 1})
        check('POST', DK, 422, json={'ma_sv': 'KHONG_TON_TAI', 'ma_dt': topic})
        item = check('POST', DK, 201, json={'ma_sv': s1, 'ma_dt': topic})
        registration_id = item['ma_dk']
        check('GET', DK + '/' + str(registration_id), 200)
        check('POST', DK, 409, json={'ma_sv': s1, 'ma_dt': topic})
        check('POST', DK, 409, json={'ma_sv': s2, 'ma_dt': topic})
        edited = check('PUT', DK + '/' + str(registration_id), 200,
                       json={'ma_sv': s1, 'ma_dt': topic, 'diem_huong_dan': 8, 'diem_phan_bien': 9})
        assert edited['diem_trung_binh'] == 8.5, edited
        print('  [OK] Demo score 8 and 9 gives 8.5')
        print('\nSUCCESS: all CRUD, HTTP cross-service checks and sample scoring passed.')
        return 0
    except (AssertionError, requests.RequestException, KeyError) as exc:
        print(f'\nFAIL: {exc}', file=sys.stderr)
        return 1
    finally:
        # Cleanup test-only data; ignore any cleanup failure and leave real demo data untouched.
        for url in ([DK + '/' + str(registration_id)] if registration_id is not None else []) + [SV + '/' + s1, SV + '/' + s2, DT + '/' + topic]:
            try:
                requests.delete(url, timeout=3)
            except requests.RequestException:
                pass


if __name__ == '__main__':
    sys.exit(main())
