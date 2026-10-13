#!/usr/bin/env bash
# Run on the bot server from its checkout. Requires an existing .env.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
if [[ ! -f .env ]]; then
  echo 'Missing .env: configure the bot environment before deployment.' >&2
  exit 1
fi
if [[ ! -x venv/bin/python ]]; then
  echo 'Missing venv: run python3 -m venv venv first.' >&2
  exit 1
fi
if ! command -v systemctl >/dev/null; then
  echo 'This deployment requires a Linux server with systemd.' >&2
  exit 1
fi
if [[ $EUID -ne 0 ]]; then
  echo 'Run with sudo to install/update the systemd service.' >&2
  exit 1
fi
git pull --ff-only
venv/bin/python -m pip install -r requirements.txt
# Validate code before stopping a previously running instance.
venv/bin/python -m compileall -q bot
SERVICE_FILE=/etc/systemd/system/humobot.service
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=HUMOBOT Telegram bot
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=$PROJECT_DIR/venv/bin/python -m bot.main
Restart=always
RestartSec=5
TimeoutStopSec=90

[Install]
WantedBy=multi-user.target
EOF
# Stop only this project's former screen session when it is confirmed to belong
# to this checkout; migration from any other supervisor must be done explicitly.
if command -v screen >/dev/null && screen -ls | grep -q '[.]taxibot'; then
  echo 'Existing taxibot screen detected. Stop the old bot explicitly before enabling this service.' >&2
  exit 1
fi
systemctl daemon-reload
systemctl enable humobot.service
systemctl restart humobot.service
systemctl is-active humobot.service
