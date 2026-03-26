# myOfflineAI Airgap Simplification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip Open WebUI down to an airgappable local LLM interface with zero outbound network calls at runtime.

**Architecture:** Surgical code removal — delete cloud-specific providers, routers, components, and UI paths. Keep local-only features (Ollama, Faster Whisper, Chroma, Automatic1111/ComfyUI). Replace external asset references with local alternatives.

**Tech Stack:** FastAPI (Python), SvelteKit (TypeScript), SQLAlchemy/Alembic, Docker Compose, Ollama

**Design Spec:** `docs/superpowers/specs/2026-03-26-airgap-simplification-design.md`

---

## Phase 1: Baseline & Safety Net

### Task 1: Tag pre-simplification baseline

**Files:**
- None (git operations only)

- [ ] **Step 1: Create git tag**

```bash
git tag -a pre-simplification -m "Baseline before airgap simplification (Open WebUI v0.8.11)"
```

- [ ] **Step 2: Verify tag**

```bash
git tag -l "pre-simplification"
```

Expected: `pre-simplification`

- [ ] **Step 3: Push tag to remote**

```bash
git push origin pre-simplification
```

---

### Task 2: Create backend smoke test

**Files:**
- Create: `test/test_smoke.py`

This test verifies core chat infrastructure is intact after each phase of changes. It does NOT require a running Ollama instance — it tests that the FastAPI app starts and core endpoints respond.

- [ ] **Step 1: Write smoke test**

```python
"""
Smoke tests for myOfflineAI.
Verifies core endpoints respond after simplification changes.
Does not require a running Ollama instance.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app."""
    from open_webui.main import app
    with TestClient(app) as c:
        yield c


class TestAppStarts:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_app_config_endpoint(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "name" in data

    def test_auth_signin_rejects_empty(self, client):
        response = client.post("/api/v1/auths/signin", json={})
        assert response.status_code in (400, 401, 422)


class TestOllamaRouterRegistered:
    def test_ollama_endpoint_exists(self, client):
        """Ollama router should be registered (will 401 without auth, but not 404)."""
        response = client.get("/ollama/api/tags")
        assert response.status_code != 404


class TestRemovedRoutersGone:
    """After Phase 2, these endpoints should return 404."""

    @pytest.mark.parametrize("path", [
        "/api/v1/channels",
        "/api/v1/notes",
        "/api/v1/scim/v2/Users",
        "/api/v1/pipelines",
        "/api/v1/terminals",
        "/openai/api/chat/completions",
    ])
    def test_removed_endpoint_is_404(self, client, path):
        response = client.get(path)
        assert response.status_code == 404, f"{path} should be removed but returned {response.status_code}"
```

- [ ] **Step 2: Verify test file structure**

```bash
cd /Users/lefv/myOfflineAI && ls test/test_smoke.py
```

- [ ] **Step 3: Run the smoke test (expect partial failures — removed-router tests will fail until Phase 2)**

```bash
cd /Users/lefv/myOfflineAI/backend && python -m pytest ../test/test_smoke.py -v -k "TestAppStarts or TestOllamaRouterRegistered" 2>&1 | head -40
```

Expected: `TestAppStarts` and `TestOllamaRouterRegistered` tests PASS. `TestRemovedRoutersGone` tests will fail (routers still present) — this is correct.

- [ ] **Step 4: Commit**

```bash
git add test/test_smoke.py
git commit -m "test: add smoke tests for airgap simplification"
```

---

### Task 3: Document current working build steps

**Files:**
- Create: `docs/BUILD.md`

- [ ] **Step 1: Write build documentation**

```markdown
# Build & Run Instructions

## Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.11+ with UV
- Ollama (for local inference)

## Docker (Production)
```bash
make install          # docker compose up -d
make startAndBuild    # rebuild and start
make stop             # stop containers
```

## Local Development

### Frontend
```bash
npm install
npm run dev           # SvelteKit dev server on localhost:5173
```

### Backend
```bash
cd backend
pip install -r requirements.txt   # or: uv sync
./dev.sh              # uvicorn on localhost:8080 with hot reload
```

### Tests
```bash
# Frontend
npm run test:frontend

# Backend
cd backend && python -m pytest ../test/ -v

# Lint
npm run lint
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/BUILD.md
git commit -m "docs: add build and run instructions"
```

---

## Phase 2: Backend Removal

### Task 4: Delete dead routers — channels, notes, SCIM, pipelines, terminals

**Files:**
- Delete: `backend/open_webui/routers/channels.py`
- Delete: `backend/open_webui/routers/notes.py`
- Delete: `backend/open_webui/routers/scim.py`
- Delete: `backend/open_webui/routers/pipelines.py`
- Delete: `backend/open_webui/routers/terminals.py`
- Modify: `backend/open_webui/main.py:1487-1528` (router registrations)

- [ ] **Step 1: Delete the router files**

```bash
cd /Users/lefv/myOfflineAI
rm backend/open_webui/routers/channels.py
rm backend/open_webui/routers/notes.py
rm backend/open_webui/routers/scim.py
rm backend/open_webui/routers/pipelines.py
rm backend/open_webui/routers/terminals.py
```

- [ ] **Step 2: Remove router registrations from main.py**

In `backend/open_webui/main.py`, remove these lines from the router registration block (around lines 1487-1528):

- Remove the import statements for: `channels`, `notes`, `scim`, `pipelines`, `terminals`
- Remove `app.include_router(channels.router, ...)` (line ~1504)
- Remove `app.include_router(notes.router, ...)` (line ~1506)
- Remove `app.include_router(pipelines.router, ...)` (line ~1491)
- Remove `app.include_router(terminals.router, ...)` (line ~1524)
- Remove the conditional `app.include_router(scim.router, ...)` block (line ~1528)

Search the entire `main.py` file for any other references to these routers (imports at the top of the file, middleware, lifespan hooks, etc.) and remove those too.

- [ ] **Step 3: Remove channel/note references from main.py lifespan and socket handlers**

Search `main.py` for `channel` and `note` references outside the router block. These may include:
- Socket.IO event handlers for real-time channel messaging
- Any startup initialization for these features

Remove all such references.

- [ ] **Step 4: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

Expected: `OK` (no import errors)

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor: remove channels, notes, SCIM, pipelines, terminals routers"
```

---

### Task 5: Delete the OpenAI router

**Files:**
- Delete: `backend/open_webui/routers/openai.py`
- Modify: `backend/open_webui/main.py` (remove openai router registration and imports)

The OpenAI router is the proxy to cloud LLM APIs. With Ollama as the only backend, this is not needed. However, this is a high-impact change — other parts of the codebase may reference OpenAI-style endpoints or the router's helper functions.

- [ ] **Step 1: Find all imports of the openai router**

```bash
cd /Users/lefv/myOfflineAI
grep -rn "from.*routers.*openai\|from.*routers import.*openai\|routers.openai" backend/ --include="*.py"
```

Document every file that imports from the openai router.

- [ ] **Step 2: Find references to OpenAI-style completion endpoints in backend code**

```bash
grep -rn "openai.*completions\|/openai/\|OPENAI_API_BASE\|ENABLE_OPENAI_API" backend/ --include="*.py" | grep -v "config.py\|env.py\|routers/openai.py"
```

These references need to be removed or guarded. Common patterns:
- Chat completion code that tries OpenAI before Ollama
- Model listing that merges OpenAI + Ollama models
- Direct connections that use OpenAI-compatible API format

- [ ] **Step 3: Delete the router file**

```bash
rm backend/open_webui/routers/openai.py
```

- [ ] **Step 4: Remove registration from main.py**

Remove the `openai.router` include (line ~1488) and its import from `main.py`.

- [ ] **Step 5: Fix all broken imports found in Step 1-2**

For each file that imported from the openai router:
- If the import was for a utility function used elsewhere, move that function to a shared utils module or inline it
- If the import was for routing/proxying, remove it entirely
- If model listing code merges OpenAI + Ollama models, simplify to Ollama-only

- [ ] **Step 6: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: remove OpenAI router and cloud LLM proxy"
```

---

### Task 6: Delete web search modules

**Files:**
- Delete: `backend/open_webui/retrieval/web/` (entire directory)
- Modify: `backend/open_webui/routers/retrieval.py` (remove web search references)
- Modify: `backend/open_webui/config.py` (remove web search config, lines ~2482+)

- [ ] **Step 1: Find all imports from retrieval.web**

```bash
grep -rn "from.*retrieval.web\|retrieval\.web\|web_search\|WEB_SEARCH\|ENABLE_RAG_WEB_SEARCH" backend/ --include="*.py" | grep -v "retrieval/web/"
```

- [ ] **Step 2: Delete the web search directory**

```bash
rm -rf backend/open_webui/retrieval/web/
```

- [ ] **Step 3: Remove web search references from retrieval.py**

In `backend/open_webui/routers/retrieval.py`:
- Remove all imports from `retrieval.web.*`
- Remove web search endpoint handlers
- Remove web search configuration endpoints
- Keep document upload, chunking, embedding, and vector search functionality

- [ ] **Step 4: Remove web search config from config.py**

In `backend/open_webui/config.py`, remove the entire web search configuration section (starts around line 2482). This includes:
- All `*_SEARCH_*` env vars (Brave, Tavily, Serper, SerpAPI, SearchAPI, Kagi, Mojeek, Bing, Yandex, etc.)
- `ENABLE_RAG_WEB_SEARCH` flag
- `RAG_WEB_SEARCH_ENGINE` setting
- FireCrawl configuration
- Perplexity search configuration

- [ ] **Step 5: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "refactor: remove all web search integrations"
```

---

### Task 7: Simplify auths.py — remove OAuth

**Files:**
- Modify: `backend/open_webui/routers/auths.py:1205-1295` (remove token_exchange)
- Modify: `backend/open_webui/main.py` (remove OAuth callback routes)
- Modify: `backend/open_webui/config.py:313-828` (remove OAuth config section)

- [ ] **Step 1: Find all OAuth routes in main.py**

```bash
grep -n "oauth\|OAuth\|OIDC\|saml\|SAML\|feishu\|SSO" backend/open_webui/main.py
```

These are typically callback endpoints registered directly on the app (not via routers).

- [ ] **Step 2: Remove OAuth callback routes from main.py**

Remove all OAuth/OIDC/SAML callback route handlers from `main.py`. These are the `/oauth/*/callback` endpoints.

- [ ] **Step 3: Remove token_exchange from auths.py**

In `backend/open_webui/routers/auths.py`, remove the `token_exchange()` function (lines ~1205-1295) and its route decorator.

- [ ] **Step 4: Remove OAuth config from config.py**

In `backend/open_webui/config.py`, remove the OAuth configuration section (lines ~313-828). This includes:
- Google OAuth config (client_id, client_secret, redirect_uri)
- Microsoft OAuth config
- GitHub OAuth config
- Feishu OAuth config
- Generic OIDC config
- SAML config
- `ENABLE_OAUTH_*` flags
- OAuth scope, claim mappings, role mappings

- [ ] **Step 5: Remove OAuth env vars from env.py**

Search `backend/open_webui/env.py` for OAuth-related variables and remove them:

```bash
grep -n "OAUTH\|oauth\|OIDC\|SAML\|MICROSOFT_CLIENT\|GOOGLE_CLIENT\|GITHUB_CLIENT\|FEISHU" backend/open_webui/env.py
```

- [ ] **Step 6: Remove LDAP config**

In `backend/open_webui/config.py`, remove the LDAP configuration section (around line 3937+).

- [ ] **Step 7: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 8: Commit**

```bash
git add -u
git commit -m "refactor: remove OAuth, OIDC, SAML, LDAP authentication"
```

---

### Task 8: Simplify audio.py — keep only local Whisper

**Files:**
- Modify: `backend/open_webui/routers/audio.py`
- Modify: `backend/open_webui/config.py` (audio config sections around lines 3424-3900)

- [ ] **Step 1: Identify cloud audio code paths**

```bash
grep -n "azure\|Azure\|deepgram\|Deepgram\|elevenlabs\|ElevenLabs\|ELEVENLABS\|mistral\|Mistral\|openai\|OpenAI" backend/open_webui/routers/audio.py | head -40
```

- [ ] **Step 2: Simplify audio.py STT endpoints**

In `backend/open_webui/routers/audio.py`:
- Remove Azure Speech STT code paths (around line 769)
- Remove Deepgram STT code path (around line 669)
- Remove OpenAI Whisper API STT code path (cloud API call)
- Remove Mistral STT code path
- Keep the local Faster Whisper (on-device) STT code path
- Simplify the STT engine selection to only support `""` (local whisper) or `"web"` (browser-native)

- [ ] **Step 3: Simplify audio.py TTS endpoints**

In `backend/open_webui/routers/audio.py`:
- Remove Azure TTS code path (around line 483)
- Remove ElevenLabs TTS code path
- Remove OpenAI TTS code path (cloud API call)
- Keep Web Speech API passthrough (browser-native)
- If there's a local TTS option (e.g., Piper, Transformers), keep it

- [ ] **Step 4: Remove voice listing endpoints for cloud providers**

Remove endpoints that list voices from Azure (line ~1293), ElevenLabs (line ~1314), etc.

- [ ] **Step 5: Remove cloud audio config from config.py**

In `backend/open_webui/config.py`, remove:
- `AUDIO_STT_OPENAI_API_*` variables
- `AUDIO_STT_AZURE_*` variables
- `AUDIO_STT_DEEPGRAM_*` variables
- `AUDIO_STT_MISTRAL_*` variables
- `AUDIO_TTS_OPENAI_API_*` variables
- `ELEVENLABS_*` variables
- `AUDIO_TTS_AZURE_*` variables
- Keep `WHISPER_MODEL`, `WHISPER_COMPUTE_TYPE`, and other local whisper config

- [ ] **Step 6: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: remove cloud audio providers, keep local Whisper only"
```

---

### Task 9: Simplify images.py — keep only local generators

**Files:**
- Modify: `backend/open_webui/routers/images.py`
- Modify: `backend/open_webui/config.py` (image config)

- [ ] **Step 1: Identify cloud image gen code paths**

```bash
grep -n "dall.e\|DALL_E\|dalle\|gemini\|Gemini\|GEMINI\|openai\|OpenAI" backend/open_webui/routers/images.py | head -20
```

- [ ] **Step 2: Remove cloud image generation from images.py**

- Remove DALL-E (OpenAI) image generation code path
- Remove Gemini image generation code path
- Keep Automatic1111 code path
- Keep ComfyUI code path
- Simplify the engine selection to only support `automatic1111` and `comfyui`

- [ ] **Step 3: Remove cloud image gen config from config.py**

Remove:
- `IMAGES_OPENAI_API_KEY`, `IMAGES_OPENAI_API_BASE_URL`
- `IMAGES_GEMINI_API_KEY`, `IMAGES_GEMINI_API_BASE_URL`
- Keep `AUTOMATIC1111_BASE_URL`, `AUTOMATIC1111_API_AUTH`
- Keep `COMFYUI_BASE_URL`, `COMFYUI_WORKFLOW`, `COMFYUI_WORKFLOW_NODES`

- [ ] **Step 4: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor: remove cloud image generation, keep Automatic1111 and ComfyUI"
```

---

### Task 10: Simplify retrieval.py — local embeddings only

**Files:**
- Modify: `backend/open_webui/routers/retrieval.py`
- Modify: `backend/open_webui/config.py` (RAG config around lines 1687-2003)

- [ ] **Step 1: Identify cloud embedding code paths**

```bash
grep -n "openai\|OpenAI\|azure\|Azure\|RAG_OPENAI\|RAG_AZURE" backend/open_webui/routers/retrieval.py | head -20
```

- [ ] **Step 2: Remove cloud embedding providers from retrieval.py**

- Remove OpenAI embedding API code path
- Remove Azure OpenAI embedding code path
- Keep local sentence-transformers embedding engine
- Keep Ollama embedding engine (local)
- Simplify `RAG_EMBEDDING_ENGINE` to only support `""` (sentence-transformers) or `"ollama"`

- [ ] **Step 3: Remove cloud vector DB options**

Check which vector DB integrations are present. Keep Chroma (default). If removing others would break imports, leave them as optional but remove their config defaults:

```bash
grep -n "milvus\|qdrant\|pgvector\|mariadb\|opensearch\|elasticsearch" backend/open_webui/config.py | head -20
```

Keep Chroma as the default and only documented option. Other local-capable vector DBs (pgvector, Milvus) can remain in code as they don't require internet, but remove cloud-only options.

- [ ] **Step 4: Remove cloud RAG config from config.py**

Remove:
- `RAG_OPENAI_API_KEY`, `RAG_OPENAI_API_BASE_URL`
- `RAG_AZURE_OPENAI_API_KEY`, `RAG_AZURE_OPENAI_*`
- `RAG_EMBEDDING_MODEL_AUTO_UPDATE` (set to False and remove the toggle)
- Keep `RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_ENGINE`, `RAG_CHUNK_SIZE`, etc.

- [ ] **Step 5: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "refactor: remove cloud embedding providers, keep local sentence-transformers and Ollama"
```

---

### Task 11: Remove URL-based loading from functions.py and tools.py

**Files:**
- Modify: `backend/open_webui/routers/functions.py`
- Modify: `backend/open_webui/routers/tools.py`

- [ ] **Step 1: Find URL loading code in functions.py**

```bash
grep -n "raw.githubusercontent\|url\|URL\|import_from\|from_url" backend/open_webui/routers/functions.py | head -20
```

- [ ] **Step 2: Remove URL-based function loading from functions.py**

Remove endpoints or code paths that:
- Fetch function code from GitHub raw URLs
- Import functions from external URLs
- Reference the OpenWebUI community marketplace

Keep:
- Manual function CRUD (create, read, update, delete)
- Function execution
- The built-in code editor workflow

- [ ] **Step 3: Remove URL-based tool loading from tools.py**

Same approach — remove URL/remote loading, keep manual CRUD:

```bash
grep -n "raw.githubusercontent\|url\|URL\|import_from\|from_url\|openapi\|OpenAPI" backend/open_webui/routers/tools.py | head -20
```

Remove endpoints that fetch tool definitions from remote URLs or OpenAPI specs from external services.

- [ ] **Step 4: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor: remove URL-based function and tool loading"
```

---

### Task 12: Remove telemetry (OTEL)

**Files:**
- Delete: `backend/open_webui/utils/telemetry/` (entire directory)
- Modify: `backend/open_webui/main.py:750-752` (remove telemetry setup call)
- Modify: `backend/open_webui/env.py` (remove OTEL env vars)

- [ ] **Step 1: Find all telemetry references**

```bash
grep -rn "telemetry\|OTEL\|otel\|opentelemetry\|setup_opentelemetry\|Instrumentor" backend/ --include="*.py" | grep -v "utils/telemetry/"
```

- [ ] **Step 2: Remove telemetry setup call from main.py**

In `backend/open_webui/main.py`, remove:
- The import of telemetry setup functions
- The `setup_opentelemetry(app=app, db_engine=engine)` call (line ~750-752)

- [ ] **Step 3: Delete the telemetry directory**

```bash
rm -rf backend/open_webui/utils/telemetry/
```

- [ ] **Step 4: Remove OTEL env vars from env.py**

Remove all `ENABLE_OTEL*`, `OTEL_EXPORTER_*`, `OTEL_METRICS_*`, `OTEL_LOGS_*` variables from `backend/open_webui/env.py`.

- [ ] **Step 5: Remove any remaining telemetry imports**

Fix any files found in Step 1 that import from the now-deleted telemetry module.

- [ ] **Step 6: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: remove OpenTelemetry instrumentation"
```

---

### Task 13: Remove version check, branding fetch, and Gravatar

**Files:**
- Modify: `backend/open_webui/main.py:2200-2219` (version check endpoint)
- Modify: `backend/open_webui/config.py:880-914` (branding fetch)
- Modify: `backend/open_webui/routers/utils.py` (Gravatar)
- Modify: `backend/open_webui/env.py` (ENABLE_VERSION_UPDATE_CHECK, WEBUI_FAVICON_URL)

- [ ] **Step 1: Remove version check endpoint from main.py**

In `backend/open_webui/main.py`:
- Remove `get_app_latest_release_version()` endpoint (lines ~2200-2219)
- Remove or stub the version check config that gets sent to frontend (line ~2056)

- [ ] **Step 2: Remove branding fetch from config.py**

In `backend/open_webui/config.py`, remove lines ~880-914:
- The `CUSTOM_NAME` fetch block that calls `https://api.openwebui.com`
- The logo and splash image download/caching logic

Replace with a simple static assignment:

```python
CUSTOM_NAME = os.environ.get("CUSTOM_NAME", "")
```

- [ ] **Step 3: Fix WEBUI_FAVICON_URL default**

In `backend/open_webui/env.py`, change the default for `WEBUI_FAVICON_URL` from `https://openwebui.com/favicon.png` to `/static/favicon.png` (or whatever the local favicon path is).

- [ ] **Step 4: Remove ENABLE_VERSION_UPDATE_CHECK from env.py**

Remove the env var and set it permanently to `False` (or delete the references entirely).

- [ ] **Step 5: Remove Gravatar from utils.py**

```bash
grep -n "gravatar\|Gravatar\|GRAVATAR" backend/open_webui/routers/utils.py
```

Remove Gravatar URL generation. Replace with a local default avatar URL or empty string.

- [ ] **Step 6: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: remove version check, branding fetch, and Gravatar"
```

---

### Task 14: Clean config.py — remove remaining cloud provider config

**Files:**
- Modify: `backend/open_webui/config.py`

This is a sweep of `config.py` (4030 lines) to remove all config sections for deleted features that weren't already cleaned in previous tasks.

- [ ] **Step 1: Remove OpenAI API config**

Remove the OpenAI API section (around lines 1045-1098):
- `ENABLE_OPENAI_API`
- `OPENAI_API_BASE_URLS`
- `OPENAI_API_KEYS`
- `OPENAI_API_CONFIGS`
- All related helper functions

- [ ] **Step 2: Remove tool server and terminal server config**

Remove:
- `TOOL_SERVERS` config (around line 1110)
- `TERMINAL_SERVER` config (around line 1127)

- [ ] **Step 3: Remove direct connections config (if cloud-dependent)**

Check if `ENABLE_DIRECT_CONNECTIONS` is used only for cloud API endpoints. If so, remove it. If it's used for local API endpoints too, keep it.

```bash
grep -n "DIRECT_CONNECTIONS\|direct_connections" backend/open_webui/config.py
```

- [ ] **Step 4: Remove Google Drive and OneDrive config**

```bash
grep -n "GOOGLE_DRIVE\|google_drive\|ONEDRIVE\|onedrive\|ONE_DRIVE" backend/open_webui/config.py
```

Remove all Google Drive and OneDrive integration config.

- [ ] **Step 5: Remove channel and note config references**

```bash
grep -n "channel\|CHANNEL\|note\|NOTE" backend/open_webui/config.py | grep -vi "# note\|changelog"
```

Remove any config flags for channels and notes features.

- [ ] **Step 6: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 7: Run smoke tests**

```bash
cd /Users/lefv/myOfflineAI/backend && python -m pytest ../test/test_smoke.py -v 2>&1 | head -40
```

Expected: All `TestAppStarts`, `TestOllamaRouterRegistered`, and `TestRemovedRoutersGone` tests PASS.

- [ ] **Step 8: Commit**

```bash
git add -u
git commit -m "refactor: clean config.py of all cloud provider configuration"
```

---

### Task 15: Delete backend model files for removed features

**Files:**
- Delete: `backend/open_webui/models/channels.py`
- Delete: `backend/open_webui/models/notes.py`
- Modify: any files that import from these models

Note: We do NOT create a migration to drop the database tables. Existing databases will have orphan tables that are harmless. New databases simply won't use them. This avoids migration complexity and preserves data for users who might want to re-enable features later.

- [ ] **Step 1: Find all imports of channel and note models**

```bash
grep -rn "from.*models.channels\|from.*models.notes\|models\.channels\|models\.notes" backend/ --include="*.py"
```

- [ ] **Step 2: Remove the model files**

```bash
rm backend/open_webui/models/channels.py
rm backend/open_webui/models/notes.py
```

- [ ] **Step 3: Fix broken imports**

For every file found in Step 1 that imported channel or note models, remove the import and any code that used those models. At this point, the routers are already deleted, so the remaining references should be in:
- Model `__init__.py` or index files
- Main.py table creation
- Any utility functions

- [ ] **Step 4: Verify backend starts**

```bash
cd /Users/lefv/myOfflineAI/backend && python -c "from open_webui.main import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor: remove channel and note database models"
```

---

## Phase 3: Frontend Removal

### Task 16: Delete frontend route pages — channels, notes, watch

**Files:**
- Delete: `src/routes/(app)/channels/` (entire directory)
- Delete: `src/routes/(app)/notes/` (entire directory)
- Delete: `src/routes/watch/` (entire directory)

- [ ] **Step 1: Delete the route directories**

```bash
cd /Users/lefv/myOfflineAI
rm -rf src/routes/\(app\)/channels/
rm -rf src/routes/\(app\)/notes/
rm -rf src/routes/watch/
```

- [ ] **Step 2: Check for references to these routes**

```bash
grep -rn "'/channels\|'/notes\|'/watch\|\"channels\|\"notes\|\"watch" src/ --include="*.svelte" --include="*.ts" --include="*.js" | head -30
```

Fix any remaining navigation links, redirects, or imports that reference these routes.

- [ ] **Step 3: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

Fix any TypeScript/Svelte errors.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor: remove channels, notes, and watch frontend routes"
```

---

### Task 17: Delete frontend API clients and utilities for removed features

**Files:**
- Delete: `src/lib/apis/channels/index.ts` (and parent directory if empty)
- Delete: `src/lib/apis/notes/index.ts` (and parent directory if empty)
- Delete: `src/lib/apis/terminal/index.ts` (and parent directory if empty)
- Delete: `src/lib/utils/google-drive-picker.ts`
- Delete: `src/lib/utils/onedrive-file-picker.ts`

- [ ] **Step 1: Delete the files**

```bash
cd /Users/lefv/myOfflineAI
rm -rf src/lib/apis/channels/
rm -rf src/lib/apis/notes/
rm -rf src/lib/apis/terminal/
rm src/lib/utils/google-drive-picker.ts
rm src/lib/utils/onedrive-file-picker.ts
```

- [ ] **Step 2: Find broken imports**

```bash
grep -rn "apis/channels\|apis/notes\|apis/terminal\|google-drive-picker\|onedrive-file-picker" src/ --include="*.svelte" --include="*.ts" --include="*.js" | head -30
```

- [ ] **Step 3: Fix broken imports**

For each file with a broken import:
- If the import is for a component that's already been deleted, remove the import
- If the import is in a component that's kept (e.g., MessageInput.svelte importing Google Drive picker), remove the import and the conditional UI that used it

Key files to check:
- `src/lib/components/chat/MessageInput/InputMenu.svelte` — remove Google Drive picker import and menu item
- `src/lib/components/chat/MessageInput.svelte` — remove Google Drive and OneDrive imports and handlers

- [ ] **Step 4: Clean stores/index.ts**

In `src/lib/stores/index.ts`:
- Remove `channels` writable (line ~57)
- Remove `channelId` writable (line ~58)
- Remove `terminalServers` writable (line ~75)
- Remove `selectedTerminalId` writable (line ~106)
- Remove `enable_google_drive_integration` from config (line ~278)
- Remove `enable_onedrive_integration` from config (line ~279)

- [ ] **Step 5: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "refactor: remove frontend API clients and utilities for deleted features"
```

---

### Task 18: Clean the sidebar — remove channels and notes navigation

**Files:**
- Modify: `src/lib/components/layout/Sidebar/Sidebar.svelte`

- [ ] **Step 1: Remove channel navigation from sidebar**

In `src/lib/components/layout/Sidebar/Sidebar.svelte`:
- Remove channel imports (line ~22: `channels` store, line ~57,202: `getChannels`, `createNewChannel`)
- Remove the channels section rendering (lines ~1073-1092)
- Remove the channel feature flag check (lines ~469-472)

- [ ] **Step 2: Remove notes navigation from sidebar**

- Remove the notes navigation item (lines ~770-780, `href="/notes"`)
- Remove the notes sidebar button (lines ~1004-1009)

- [ ] **Step 3: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor: remove channels and notes from sidebar navigation"
```

---

### Task 19: Clean auth page — remove OAuth buttons

**Files:**
- Modify: `src/routes/auth/+page.svelte`

- [ ] **Step 1: Remove OAuth buttons**

In `src/routes/auth/+page.svelte`:
- Remove the OAuth provider button section (lines ~419-551):
  - Google OAuth button (lines ~432-459)
  - Microsoft OAuth button (lines ~462-489)
  - GitHub OAuth button (lines ~493-511)
  - OIDC/SSO button (lines ~514-543)
  - Feishu OAuth button (lines ~544-551)
- Remove `oauthCallbackHandler()` function and related OAuth handling code (lines ~116, ~183)
- Remove OAuth-related imports and store references
- Keep the email/password signin/signup form

- [ ] **Step 2: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "refactor: remove OAuth buttons from auth page"
```

---

### Task 20: Clean About page — remove external links and badges

**Files:**
- Modify: `src/lib/components/chat/Settings/About.svelte`

- [ ] **Step 1: Remove version update check**

In `About.svelte`:
- Remove the version check handler (lines ~21-42) that calls the backend version endpoint
- Replace with static version display

- [ ] **Step 2: Remove Shields.io badges**

Remove the badge images (lines ~129-143):
- Discord badge
- Twitter follow badge
- GitHub stars badge

- [ ] **Step 3: Remove external links**

Remove links to:
- `discord.gg` community
- `twitter.com/OpenWebUI`
- `github.com/open-webui/open-webui`
- `openwebui.com`

Replace with a simple local project description:

```svelte
<div class="text-sm text-gray-500">
    <p>myOfflineAI — Airgapped local LLM interface</p>
    <p>Based on Open WebUI</p>
</div>
```

- [ ] **Step 4: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor: replace external links and badges with local project info"
```

---

### Task 21: Delete component directories for removed features

**Files:**
- Delete: `src/lib/components/channel/` (entire directory)
- Delete: `src/lib/components/notes/` (entire directory)
- Delete: `src/lib/components/chat/Messages/ResponseMessage/WebSearchResults.svelte`

- [ ] **Step 1: Delete the directories and files**

```bash
cd /Users/lefv/myOfflineAI
rm -rf src/lib/components/channel/
rm -rf src/lib/components/notes/
rm -f src/lib/components/chat/Messages/ResponseMessage/WebSearchResults.svelte
```

- [ ] **Step 2: Find and fix broken imports**

```bash
grep -rn "components/channel\|components/notes\|WebSearchResults" src/ --include="*.svelte" --include="*.ts" | head -20
```

Remove all imports and usages of these deleted components. For WebSearchResults, find the parent component that renders it and remove the conditional block.

- [ ] **Step 3: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor: delete channel, notes, and web search result components"
```

---

### Task 22: Simplify settings panels — remove cloud provider config UI

**Files:**
- Modify: Components under `src/lib/components/chat/Settings/`
- Modify: Components under `src/lib/components/admin/Settings/`

- [ ] **Step 1: Identify cloud provider settings components**

```bash
find src/lib/components -path "*/Settings/*" -name "*.svelte" | sort
```

```bash
grep -rln "openai\|OpenAI\|OPENAI\|azure\|Azure\|elevenlabs\|ElevenLabs\|deepgram\|Deepgram\|gemini\|Gemini" src/lib/components/*/Settings/ src/lib/components/admin/Settings/ 2>/dev/null
```

- [ ] **Step 2: Remove OpenAI connection settings**

In admin settings components:
- Remove the OpenAI API connections tab/panel
- Remove OpenAI API key input fields
- Remove OpenAI base URL configuration
- Keep Ollama connection settings

- [ ] **Step 3: Remove cloud audio settings**

In audio/speech settings:
- Remove Azure, ElevenLabs, Deepgram, OpenAI cloud STT/TTS configuration
- Keep local Whisper model selection
- Keep Web Speech API settings

- [ ] **Step 4: Remove cloud image gen settings**

In image settings:
- Remove DALL-E configuration
- Remove Gemini image generation configuration
- Keep Automatic1111 and ComfyUI settings

- [ ] **Step 5: Remove web search settings**

Remove any UI for configuring web search engines and API keys.

- [ ] **Step 6: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: remove cloud provider configuration from settings UI"
```

---

### Task 23: Clean Citations component — remove Google favicon fetch

**Files:**
- Modify: `src/lib/components/chat/Messages/Citations.svelte:178-183`

- [ ] **Step 1: Replace external favicon fetch**

In `Citations.svelte`, replace the Google favicon URL (line ~178):

```svelte
<!-- BEFORE -->
<img src="https://www.google.com/s2/favicons?sz=32&domain={citation.source.name}" ... />

<!-- AFTER -->
<img src="/static/favicon.png" ... />
```

Or replace with a generic document icon / first-letter avatar.

- [ ] **Step 2: Check CitationsModal.svelte for similar references**

```bash
grep -n "google.com/s2/favicons\|favicon" src/lib/components/chat/Messages/Citations/CitationsModal.svelte
```

Fix any similar external favicon references.

- [ ] **Step 3: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor: replace external favicon fetch with local fallback"
```

---

### Task 24: Remove Gravatar from frontend

**Files:**
- Modify: `src/lib/apis/utils/index.ts:3` (remove getGravatarUrl)
- Modify: `src/lib/components/chat/Settings/Account.svelte:10`
- Modify: `src/lib/components/chat/Settings/Account/UserProfileImage.svelte:7,145`
- Modify: `src/lib/components/chat/Messages/ProfileImage.svelte:13`

- [ ] **Step 1: Remove getGravatarUrl function**

In `src/lib/apis/utils/index.ts`, delete the `getGravatarUrl()` function definition.

- [ ] **Step 2: Remove Gravatar usage from Account settings**

In `Account.svelte` and `UserProfileImage.svelte`:
- Remove import of `getGravatarUrl`
- Remove the Gravatar URL option from profile image selection
- Keep local upload and default avatar options

- [ ] **Step 3: Remove Gravatar check from ProfileImage**

In `ProfileImage.svelte`:
- Remove the Gravatar URL check (line ~13)
- Use local default avatar for all users without a custom image

- [ ] **Step 4: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor: remove Gravatar integration, use local avatars"
```

---

### Task 25: Remove OpenAI references from frontend API clients and stores

**Files:**
- Modify: `src/lib/apis/` (OpenAI API client modules)
- Modify: `src/lib/stores/index.ts` (OpenAI-related stores)
- Modify: `src/lib/constants.ts` (cloud provider constants)

- [ ] **Step 1: Find OpenAI frontend API module**

```bash
ls src/lib/apis/openai/ 2>/dev/null
grep -rn "apis/openai" src/ --include="*.svelte" --include="*.ts" | head -20
```

- [ ] **Step 2: Delete or simplify OpenAI API client**

If there's a dedicated `src/lib/apis/openai/` directory, delete it. Fix all imports.

- [ ] **Step 3: Clean stores**

In `src/lib/stores/index.ts`, remove any OpenAI-specific state:

```bash
grep -n "openai\|OPENAI\|OpenAI" src/lib/stores/index.ts
```

- [ ] **Step 4: Clean constants**

In `src/lib/constants.ts`, remove cloud provider constants:

```bash
grep -n "OPENAI\|AZURE\|openai\|azure" src/lib/constants.ts
```

- [ ] **Step 5: Verify frontend builds**

```bash
cd /Users/lefv/myOfflineAI && npm run check 2>&1 | tail -20
```

- [ ] **Step 6: Run frontend tests**

```bash
cd /Users/lefv/myOfflineAI && npm run test:frontend 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "refactor: remove OpenAI frontend API client and store references"
```

---

## Phase 4: Network Hardening

### Task 26: Disable model auto-download defaults

**Files:**
- Modify: `backend/open_webui/config.py`
- Modify: `backend/open_webui/env.py`

- [ ] **Step 1: Set RAG_EMBEDDING_MODEL_AUTO_UPDATE to False**

Find and change the default:

```bash
grep -n "RAG_EMBEDDING_MODEL_AUTO_UPDATE\|EMBEDDING_MODEL_AUTO_UPDATE" backend/open_webui/config.py backend/open_webui/env.py
```

Set the default to `False`. Users who build on a connected machine can set it to `True` in their `.env`.

- [ ] **Step 2: Set WHISPER_MODEL_AUTO_UPDATE to False**

```bash
grep -n "WHISPER_MODEL_AUTO_UPDATE" backend/open_webui/config.py backend/open_webui/env.py
```

Set the default to `False`.

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "refactor: disable model auto-download by default for airgap safety"
```

---

### Task 27: Full external URL audit

**Files:**
- None (audit only, fixes in subsequent steps)

- [ ] **Step 1: Audit backend for external HTTPS URLs**

```bash
grep -rn "https://" backend/ --include="*.py" | grep -v "__pycache__\|\.pyc\|#.*https://\|migrations/" | grep -v "localhost\|127.0.0.1\|0.0.0.0" | head -60
```

Every remaining `https://` reference should be one of:
- A configurable URL that defaults to a local address
- A comment or docstring
- A license reference
- A URL in a constant that is never called at runtime without explicit user configuration

Flag any that are hardcoded runtime fetches.

- [ ] **Step 2: Audit frontend for external HTTPS URLs**

```bash
grep -rn "https://" src/ --include="*.svelte" --include="*.ts" --include="*.js" --include="*.html" | grep -v "node_modules\|//.*https://" | head -60
```

Same criteria as backend.

- [ ] **Step 3: Audit for fetch/request calls to external hosts**

```bash
grep -rn "fetch(\|requests\.\(get\|post\|put\)\|httpx\.\(get\|post\|put\)\|aiohttp" backend/ --include="*.py" | grep -v "__pycache__\|test\|migrations/" | head -40
```

```bash
grep -rn "fetch(" src/ --include="*.svelte" --include="*.ts" | grep -v "node_modules" | head -40
```

Verify every fetch/request call targets a relative URL or a user-configured base URL (Ollama, Automatic1111, ComfyUI).

- [ ] **Step 4: Document audit results**

Create a brief audit log noting:
- Number of remaining external URLs
- Which ones are acceptable (comments, user-configured, etc.)
- Any that need additional cleanup

- [ ] **Step 5: Fix any remaining issues found in audit**

Apply targeted fixes for any hardcoded external URLs discovered.

- [ ] **Step 6: Commit fixes**

```bash
git add -u
git commit -m "refactor: fix remaining external URL references from audit"
```

---

### Task 28: Create model pre-download scripts

**Files:**
- Create: `scripts/download-models.sh`

- [ ] **Step 1: Create the pre-download script**

```bash
#!/usr/bin/env bash
# Pre-download models for airgapped deployment.
# Run this on a connected machine before transferring to airgapped environment.

set -euo pipefail

echo "=== Downloading embedding model for RAG ==="
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print(f'Model downloaded to: {model._model_card_vars.get(\"model_name\", \"cache\")}')
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/download-models.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/download-models.sh
git commit -m "feat: add model pre-download script for airgapped deployment"
```

---

## Phase 5: Docker & Deployment

### Task 29: Update Dockerfile for bundled models

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Read current Dockerfile**

```bash
cat Dockerfile
```

Understand the current build stages and where Python packages are installed.

- [ ] **Step 2: Add model pre-download to Docker build**

Add a build stage (or append to existing pip install stage) that pre-downloads the embedding and Whisper models into the image:

```dockerfile
# Pre-download models for offline use
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
```

Place these after the Python dependency installation step.

- [ ] **Step 3: Verify Docker build**

```bash
docker build -t myofflineai:test . 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: pre-download embedding and Whisper models in Docker image"
```

---

### Task 30: Update docker-compose.yaml and Makefile

**Files:**
- Modify: `docker-compose.yaml`
- Modify: `Makefile`

- [ ] **Step 1: Simplify docker-compose.yaml**

Review and update `docker-compose.yaml`:
- Remove `WEBUI_SECRET_KEY=` empty env var (generate one or use a default)
- Remove any cloud-specific environment variables
- Add comment documenting airgap deployment

```yaml
services:
  ollama:
    volumes:
      - ollama:/root/.ollama
    container_name: ollama
    pull_policy: always
    tty: true
    restart: unless-stopped
    image: ollama/ollama:${OLLAMA_DOCKER_TAG-latest}

  open-webui:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/open-webui/open-webui:${WEBUI_DOCKER_TAG-main}
    container_name: open-webui
    volumes:
      - open-webui:/app/backend/data
    depends_on:
      - ollama
    ports:
      - ${OPEN_WEBUI_PORT-3000}:8080
    environment:
      - 'OLLAMA_BASE_URL=http://ollama:11434'
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped

volumes:
  ollama: {}
  open-webui: {}
```

- [ ] **Step 2: Add pull-models target to Makefile**

Add to `Makefile`:

```makefile
pull-models:
	@echo "Pulling Ollama models into Docker volume..."
	docker exec ollama ollama pull llama3.2
	@echo "Models pulled. Add more with: docker exec ollama ollama pull <model>"

export-images:
	@echo "Exporting Docker images for airgap transfer..."
	docker save -o myofflineai-images.tar ollama/ollama ghcr.io/open-webui/open-webui
	@echo "Saved to myofflineai-images.tar"

load-images:
	@echo "Loading Docker images from archive..."
	docker load -i myofflineai-images.tar
	@echo "Images loaded. Run 'make install' to start."
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yaml Makefile
git commit -m "feat: update Docker config and add airgap deployment targets"
```

---

### Task 31: Write airgap deployment guide

**Files:**
- Create: `docs/AIRGAP-DEPLOYMENT.md`

- [ ] **Step 1: Write the deployment guide**

```markdown
# Airgap Deployment Guide

myOfflineAI is designed for fully offline, airgapped environments. Follow this
guide to build on a connected machine and deploy to a disconnected one.

## Step 1: Build on Connected Machine

```bash
# Clone and build
git clone https://github.com/lefv-org/myOfflineAI.git
cd myOfflineAI
docker compose build

# Start services temporarily to pull models
docker compose up -d
docker exec ollama ollama pull llama3.2     # or your preferred model
docker exec ollama ollama pull nomic-embed-text  # optional: for RAG
docker compose down
```

## Step 2: Export Images and Volumes

```bash
# Export Docker images
make export-images
# Creates: myofflineai-images.tar

# Export Ollama model volume
docker run --rm -v myofflineai_ollama:/data -v $(pwd):/backup \
    alpine tar czf /backup/ollama-models.tar.gz -C /data .
```

## Step 3: Transfer to Airgapped Machine

Transfer these files to the target machine:
- `myofflineai-images.tar` (Docker images)
- `ollama-models.tar.gz` (Ollama models)
- `docker-compose.yaml` (compose config)

## Step 4: Load on Airgapped Machine

```bash
# Load Docker images
make load-images
# Or: docker load -i myofflineai-images.tar

# Create and populate Ollama volume
docker volume create myofflineai_ollama
docker run --rm -v myofflineai_ollama:/data -v $(pwd):/backup \
    alpine tar xzf /backup/ollama-models.tar.gz -C /data

# Start
docker compose up -d
```

## Step 5: Access

Open `http://localhost:3000` in a browser. Create an admin account on first visit.

## Optional: Strict Network Isolation

To enforce zero network access at the Docker level:

```yaml
# Add to docker-compose.yaml
networks:
  internal:
    internal: true

services:
  ollama:
    networks: [internal]
  open-webui:
    networks: [internal]
    ports:
      - "3000:8080"
```

## Updating Models

To add new models to an airgapped deployment, repeat the export/transfer/load
cycle for the Ollama volume on a connected machine.
```

- [ ] **Step 2: Commit**

```bash
git add docs/AIRGAP-DEPLOYMENT.md
git commit -m "docs: add airgap deployment guide"
```

---

### Task 32: Final end-to-end verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full backend smoke test**

```bash
cd /Users/lefv/myOfflineAI/backend && python -m pytest ../test/test_smoke.py -v
```

Expected: All tests PASS.

- [ ] **Step 2: Run frontend build**

```bash
cd /Users/lefv/myOfflineAI && npm run build 2>&1 | tail -10
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Run frontend type check**

```bash
npm run check 2>&1 | tail -20
```

Expected: No type errors.

- [ ] **Step 4: Run frontend lint**

```bash
npm run lint:frontend 2>&1 | tail -20
```

Expected: No errors (warnings acceptable).

- [ ] **Step 5: Run frontend tests**

```bash
npm run test:frontend 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 6: Final external URL audit**

```bash
echo "=== Backend external URLs ==="
grep -rn "https://" backend/ --include="*.py" | grep -v "__pycache__\|migrations/\|#" | grep -v "localhost\|127.0.0.1" | wc -l

echo "=== Frontend external URLs ==="
grep -rn "https://" src/ --include="*.svelte" --include="*.ts" --include="*.js" --include="*.html" | grep -v "node_modules\|//.*https://" | wc -l
```

Review remaining URLs. All should be either:
- In comments/docstrings
- User-configurable (Ollama, Automatic1111, ComfyUI base URLs)
- License attributions

- [ ] **Step 7: Docker build verification**

```bash
docker compose build 2>&1 | tail -10
```

Expected: Build succeeds.

- [ ] **Step 8: Commit any final fixes and tag the release**

```bash
git tag -a v0.1.0-airgap -m "First airgapped release of myOfflineAI"
git push origin v0.1.0-airgap
```

---

## Task Dependency Map

```
Phase 1: [Task 1] → [Task 2] → [Task 3]
                                    ↓
Phase 2: [Task 4] → [Task 5] → [Task 6] → [Task 7] → [Task 8]
              → [Task 9] → [Task 10] → [Task 11] → [Task 12]
              → [Task 13] → [Task 14] → [Task 15]
                                              ↓
Phase 3: [Task 16] → [Task 17] → [Task 18] → [Task 19] → [Task 20]
              → [Task 21] → [Task 22] → [Task 23] → [Task 24] → [Task 25]
                                                                       ↓
Phase 4: [Task 26] → [Task 27] → [Task 28]
                                       ↓
Phase 5: [Task 29] → [Task 30] → [Task 31] → [Task 32]
```

Within each phase, tasks are largely sequential (later tasks depend on earlier removals to avoid merge conflicts). Between phases, each phase depends on the previous completing.
