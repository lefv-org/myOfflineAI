#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CORS_ALLOW_ORIGIN="http://localhost:5173;http://localhost:8081"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://lysk-server:11434}"
PORT="${PORT:-8081}"

# Activate venv if present
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" --reload
