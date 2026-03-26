#!/usr/bin/env bash
# Pre-download models for airgapped deployment.
# Run this on a connected machine before transferring to airgapped environment.

set -euo pipefail

echo "=== Downloading embedding model for RAG ==="
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('Embedding model ready.')
"

echo ""
echo "=== Downloading Whisper model for STT ==="
python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('base', device='cpu', compute_type='int8')
print('Whisper model ready.')
"

echo ""
echo "=== Pre-pulling Ollama models ==="
echo "Pull the models you need. Examples:"
echo "  ollama pull llama3.2"
echo "  ollama pull mistral"
echo "  ollama pull codellama"
echo ""
echo "Done. Models are cached locally and will work offline."
