#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo 'Run as root on the bot server.' >&2; exit 1; fi
TASK_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$TASK_ROOT"
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus tesseract-ocr-uzb
apt-get install -y libgl1 libglib2.0-0 fonts-dejavu-core libseccomp2
venv/bin/python -m pip install -r requirements-ocr.txt
venv/bin/python scripts/check_neural_ocr.py
# This installation created Ollama for this test bot. Release old inference and RAM.
# Other Telegram services are not stopped.
if systemctl cat ollama >/dev/null 2>&1; then systemctl stop ollama; fi
venv/bin/python - <<'PY'
from pathlib import Path
import os
import tempfile
path = Path('.env.test')
if not path.is_file() or path.is_symlink():
    raise SystemExit('Existing regular .env.test required')
lines = [line for line in path.read_text().splitlines()
         if line.split('=', 1)[0].strip() not in {'DOCUMENT_OCR_BACKEND', 'DOCUMENT_AI_ENABLED'}]
lines += ['DOCUMENT_OCR_BACKEND=rapid', 'DOCUMENT_AI_ENABLED=1']
fd, name = tempfile.mkstemp(prefix='.env-fast-', dir='.')
try:
    with os.fdopen(fd, 'w') as stream:
        stream.write('\n'.join(lines) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(name, path)
finally:
    if os.path.exists(name): os.unlink(name)
print('Local neural OCR configured. Existing bot/Sheets credentials preserved.')
PY
venv/bin/python scripts/run_test_bot.py --check
systemctl restart humobot-test
systemctl status humobot-test --no-pager -l
