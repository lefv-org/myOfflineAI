#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CORS_ALLOW_ORIGIN="http://localhost:5173;http://localhost:8081"
# Supports multiple backends separated by semicolons.
# MLX server (mcli run mlx_serve) runs on port 8082 by default.
export OLLAMA_BASE_URLS="${OLLAMA_BASE_URLS:-http://lysk-server:11434;http://127.0.0.1:8082}"
PORT="${PORT:-8081}"

# Activate venv if present
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" --reload
