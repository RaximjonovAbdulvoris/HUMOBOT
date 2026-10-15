#!/usr/bin/env bash
# Installs a local vision model, then blocks Ollama's non-loopback network access.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
  echo 'Run this setup as root on the bot server.' >&2
  exit 1
fi
TASK_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$TASK_ROOT"
export OLLAMA_HOST=127.0.0.1:11434
export LOCAL_OCR_MODEL=qwen2.5vl:3b
python3 - <<'PY'
from pathlib import Path
import shutil
info = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
available = int(info['MemAvailable'].split()[0]) * 1024
if available < 6 * 1024**3:
    raise SystemExit('At least 6 GiB available RAM is required for this trial. Free RAM first; bot config unchanged.')
if shutil.disk_usage('/').free < 10 * 1024**3:
    raise SystemExit('At least 10 GiB free disk space is required. Bot config unchanged.')
print('RAM/disk preflight passed. Runtime speed and accuracy will be checked next.', flush=True)
PY
if ! command -v ollama >/dev/null 2>&1; then
  TASK_INSTALLER="$(mktemp)"
  trap 'rm -f "$TASK_INSTALLER"' EXIT
  curl --proto '=https' --tlsv1.2 -fSL https://ollama.com/install.sh -o "$TASK_INSTALLER"
  sh "$TASK_INSTALLER"
fi
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/20-humo-local.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_NO_CLOUD=1"
Environment="OLLAMA_DEBUG=false"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
LimitCORE=0
Nice=10
CPUQuota=300%
MemoryHigh=6G
MemoryMax=7G
EOF
systemctl daemon-reload
systemctl enable --now ollama
systemctl restart ollama
for attempt in $(seq 1 30); do
  if curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null; then break; fi
  sleep 1
done
if ! ollama show "$LOCAL_OCR_MODEL" >/dev/null 2>&1; then
  # Public model download only. No applicant document is involved.
  ollama pull "$LOCAL_OCR_MODEL"
fi
# Download is finished. Inference service may now communicate only over loopback.
cat > /etc/systemd/system/ollama.service.d/30-humo-network.conf <<'EOF'
[Service]
IPAddressDeny=any
IPAddressAllow=localhost
EOF
systemctl daemon-reload
systemctl restart ollama
for attempt in $(seq 1 30); do
  if curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null; then break; fi
  sleep 1
done
venv/bin/python scripts/check_local_ocr.py --smoke
# Switch the bot only after the local synthetic test succeeds. Never print secrets.
venv/bin/python - <<'PY'
from pathlib import Path
import os
import tempfile
path = Path('.env.test')
if not path.exists():
    raise SystemExit('.env.test missing; local engine installed, bot configuration unchanged.')
lines = [line for line in path.read_text().splitlines()
         if line.split('=', 1)[0].strip() not in
         {'CODECRAFT_API_KEY', 'CODECRAFT_VISION_MODEL', 'LOCAL_OCR_MODEL', 'DOCUMENT_AI_ENABLED'}]
lines += ['LOCAL_OCR_MODEL=qwen2.5vl:3b', 'DOCUMENT_AI_ENABLED=1']
fd, name = tempfile.mkstemp(prefix='.env-local-', dir='.')
try:
    with os.fdopen(fd, 'w') as stream:
        stream.write('\n'.join(lines) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(name, path)
finally:
    if os.path.exists(name):
        os.unlink(name)
print('Local OCR enabled in .env.test; obsolete CodeCraft settings removed.')
PY
venv/bin/python scripts/run_test_bot.py --check
systemctl restart humobot-test
systemctl status humobot-test --no-pager -l
