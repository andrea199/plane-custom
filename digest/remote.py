"""Transfer public source and run reviewed scripts on the authorized host."""
import io
import subprocess
import sys
import tarfile
from pathlib import Path

DEST = '/home/plane/oniro-digest'
SSH = ['tailscale', 'ssh', 'plane@plane-aziendaa']
mode = sys.argv[1]
if mode == 'inspect':
    source = Path(__file__).with_name('inspect_server.py').read_bytes()
    subprocess.run(SSH + ['docker exec -i plane-app-api-1 python manage.py shell'], input=source, check=True)
elif mode == 'script':
    source = Path(sys.argv[2]).read_text(encoding='utf-8').replace('\r\n', '\n')
    subprocess.run(SSH + ['bash -s'], input=source.encode(), check=True)
elif mode == 'upload':
    root = Path(__file__).resolve().parent
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for path in root.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.eml'):
                archive.add(path, arcname=str(path.relative_to(root)))
    subprocess.run(SSH + [f'umask 077; mkdir -p {DEST}/source; tar -xzf - -C {DEST}/source'], input=stream.getvalue(), check=True)
else:
    raise SystemExit('Use inspect, upload or script')
