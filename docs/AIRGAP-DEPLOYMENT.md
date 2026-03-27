# Airgap Deployment Guide

This guide explains how to build, export, transfer, and run myOfflineAI on a machine with no internet access.

---

## Overview

myOfflineAI is designed to run entirely offline. All AI models (Ollama LLMs, embedding models, Whisper) are bundled into Docker images or pulled into persistent Docker volumes before transfer. Once deployed on the airgapped machine, no outbound network calls are made.

---

## Step 1: Build on a Connected Machine

On a machine with internet access:

```bash
# Clone the repository
git clone https://github.com/your-org/myOfflineAI.git
cd myOfflineAI

# Build the Docker images (embedding + Whisper models are pre-downloaded during build)
make startAndBuild

# Wait for services to be healthy, then pull Ollama LLM models into the volume
make pull-models

# To pull additional models beyond the default:
docker exec ollama ollama pull mistral
docker exec ollama ollama pull codellama
```

The `make startAndBuild` step bakes the sentence-transformers embedding model (`all-MiniLM-L6-v2`) and the Whisper `base` model directly into the `open-webui` image layer. No internet access is required for these models at runtime.

---

## Step 2: Export Images and Volumes

### Export Docker images

```bash
make export-images
# Produces: myofflineai-images.tar
```

This saves both `ollama/ollama` and `ghcr.io/open-webui/open-webui` into a single tar archive.

### Export the Ollama model volume

```bash
# Stop services to ensure a clean snapshot
docker compose stop

# Export the ollama volume (contains downloaded LLM weights)
docker run --rm \
  -v myofflineai_ollama:/data \
  -v "$(pwd)":/backup \
  alpine tar czf /backup/ollama-volume.tar.gz -C /data .

# Restart if needed
docker compose start
```

This produces `ollama-volume.tar.gz` containing all pulled Ollama model weights.

---

## Step 3: Transfer to the Airgapped Machine

Use a USB drive, secure file transfer, or any approved offline transfer method to copy the following files to the airgapped machine:

```
myofflineai-images.tar       # Docker images (open-webui + ollama)
ollama-volume.tar.gz         # Ollama LLM model weights
docker-compose.yaml          # Compose configuration
Makefile                     # Convenience targets
.env (optional)              # Any environment overrides
```

---

## Step 4: Load Images and Start

On the airgapped machine (Docker must already be installed):

```bash
# Load images from the archive
make load-images
# Or: docker load -i myofflineai-images.tar

# Restore the Ollama model volume
docker volume create myofflineai_ollama
docker run --rm \
  -v myofflineai_ollama:/data \
  -v "$(pwd)":/backup \
  alpine sh -c "tar xzf /backup/ollama-volume.tar.gz -C /data"

# Start the stack
make install
```

Open a browser and navigate to `http://localhost:3000`.

---

## Step 5: Optional — Strict Network Isolation

To prevent any accidental outbound traffic, configure Docker to use an internal-only network:

```yaml
# In docker-compose.yaml, add a network block:
networks:
  airgap-net:
    internal: true

# Attach services to it:
services:
  ollama:
    networks:
      - airgap-net

  open-webui:
    networks:
      - airgap-net
    # Keep ports mapping for host browser access
    ports:
      - "3000:8080"
```

With `internal: true`, Docker will not create a default route for that network, blocking all outbound internet traffic from the containers. The host can still reach port 3000.

---

## Verifying Offline Operation

After starting on the airgapped machine, confirm no external calls are attempted:

```bash
# Check that open-webui is healthy
curl -sf http://localhost:3000/health | python3 -m json.tool

# Confirm Ollama responds locally
curl http://localhost:11434/api/tags

# Optional: monitor network traffic to confirm no external connections
docker stats
```

---

## Updating Models on an Airgapped Machine

To add a new Ollama model after initial deployment:

1. Pull the model on a connected machine:
   ```bash
   docker exec ollama ollama pull <new-model>
   ```
2. Re-export the volume (`ollama-volume.tar.gz`) using the Step 2 command above.
3. Transfer the updated archive to the airgapped machine.
4. Restore the volume using the Step 4 restore command.

---

## Troubleshooting

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `open-webui` fails to start | Missing model files | Confirm models were baked into image during `make startAndBuild` |
| Ollama returns empty model list | Volume not restored | Re-run the volume restore command in Step 4 |
| Browser shows connection refused | Services not running | Run `make install` or `docker compose ps` to check status |
| RAG embeddings fail | Wrong embedding cache path | Confirm `SENTENCE_TRANSFORMERS_HOME` env var is set in compose |
