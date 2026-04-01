#!/usr/bin/env python3
# @description: Start MLX model server for Open WebUI
# @version: 1.0.0
# @group: inference
# @requires: mlx-lm

"""
Start an MLX inference server that serves an OpenAI-compatible API.
Open WebUI connects to it as an OpenAI connection at http://localhost:{port}/v1.

Usage:
    mcli run mlx_serve                           # default model + port
    mcli run mlx_serve -- --model mlx-community/Meta-Llama-3.1-8B-Instruct-4bit
    mcli run mlx_serve -- --port 5050
    mcli run mlx_serve -- --list                 # show cached MLX models
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "mlx-community/DeepSeek-R1-Distill-Qwen-7B-4bit"
DEFAULT_PORT = 8082
DEFAULT_HOST = "127.0.0.1"


def get_cached_mlx_models() -> list[str]:
    """Find MLX models already downloaded in the HuggingFace cache."""
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    if not cache_dir.exists():
        return []
    models = []
    for d in sorted(cache_dir.iterdir()):
        if d.name.startswith("models--mlx-community--"):
            name = d.name.replace("models--", "").replace("--", "/")
            models.append(name)
    return models


def main():
    parser = argparse.ArgumentParser(description="Start MLX model server for Open WebUI")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"HF model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Bind address (default: {DEFAULT_HOST})")
    parser.add_argument("--list", "-l", action="store_true", help="List cached MLX models and exit")
    args = parser.parse_args()

    if args.list:
        models = get_cached_mlx_models()
        if models:
            print("Cached MLX models:")
            for m in models:
                marker = " <-- default" if m == DEFAULT_MODEL else ""
                print(f"  {m}{marker}")
        else:
            print("No cached MLX models found. Models will be downloaded on first use.")
        return

    print(f"Starting MLX server...")
    print(f"  Model: {args.model}")
    print(f"  Port:  {args.port}")
    print(f"  Host:  {args.host}")
    print()
    print(f"Connect Open WebUI -> Admin Settings -> Connections -> OpenAI API:")
    print(f"  URL: http://{args.host}:{args.port}/v1")
    print(f"  Key: mlx  (any non-empty string)")
    print()

    cmd = [
        sys.executable, "-m", "mlx_lm.server",
        "--model", args.model,
        "--port", str(args.port),
        "--host", args.host,
        "--log-level", "INFO",
    ]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nMLX server stopped.")


if __name__ == "__main__":
    main()
