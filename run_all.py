"""Start every service and the browser client using one command."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APPS = [
    'sinhvien_service/app.py',
    'detai_service/app.py',
    'dangky_service/app.py',
    'web_client/app.py',
]


def main():
    env = os.environ.copy()
    env.setdefault('PYTHONUNBUFFERED', '1')
    workers = []
    try:
        for script in APPS:
            proc = subprocess.Popen([sys.executable, str(ROOT / script)], cwd=ROOT, env=env)
            workers.append(proc)
            print(f'[{script}] PID={proc.pid}', flush=True)
            time.sleep(0.4)
            if proc.poll() is not None:
                raise RuntimeError(f'{script} khong khoi dong (ma thoat {proc.returncode})')
        print('\nTruy cap: http://127.0.0.1:' + env.get('WEB_PORT', '5000'))
        print('Nhan Ctrl+C de tat ca 4 ung dung.\n', flush=True)
        while True:
            for proc in workers:
                if proc.poll() is not None:
                    raise RuntimeError(f'Dich vu PID={proc.pid} da dung bat ngo')
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nDang tat cac dich vu...')
    except Exception as exc:
        print(f'LOI: {exc}', file=sys.stderr)
        sys.exit_code = 1
    finally:
        for proc in workers:
            if proc.poll() is None:
                proc.terminate()
        for proc in workers:
            if proc.poll() is None:
                try:
                    proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.kill()
    return getattr(sys, 'exit_code', 0)


if __name__ == '__main__':
    sys.exit(main())
