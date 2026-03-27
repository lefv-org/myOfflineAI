# myOfflineAI: Airgap Simplification Design

**Date:** 2026-03-26
**Status:** Approved
**Baseline:** Open WebUI v0.8.11 (commit `4d058a125`)

---

## Goal

Transform the Open WebUI fork into a simplified, airgappable local LLM interface. The result is a self-contained application that makes zero outbound network calls at runtime, suitable for secure, disconnected, or privacy-sensitive environments.

## Approach

**Surgical code removal (Approach B):** Delete cloud-specific provider code, routers, components, and UI paths. Keep the architecture intact. Replace external asset references with local alternatives. Tag a pre-simplification baseline for upstream diff comparison.

---

## Scope Decisions

| Feature | Decision | Rationale |
|---------|----------|-----------|
| Cloud LLM providers (OpenAI, Azure, Gemini) | **Remove** | Internet-dependent |
| OAuth/OIDC/SAML/SCIM/LDAP | **Remove** | Internet-dependent; local accounts sufficient |
| RAG / Knowledge base | **Keep** | Works offline with local embeddings + Chroma |
| Cloud embedding providers (OpenAI, Azure) | **Remove** | Use local sentence-transformers only |
| Web search (15+ providers) | **Remove** | All internet-dependent |
| Audio — cloud (OpenAI Whisper API, Azure, Deepgram, ElevenLabs, Mistral) | **Remove** | Internet-dependent |
| Audio — local (Faster Whisper STT, Web Speech TTS) | **Keep** | Runs on device |
| Image gen — cloud (DALL-E, Gemini) | **Remove** | Internet-dependent |
| Image gen — local (Automatic1111, ComfyUI) | **Keep** | Runs locally |
| Channels (team messaging) | **Remove** | Out of scope for simplified interface |
| Notes | **Remove** | Out of scope for simplified interface |
| Analytics | **Keep** | Useful for multi-user deployments |
| Plugins (functions/tools/skills) | **Keep** | Remove URL loading, keep manual create/edit |
| Google Drive / OneDrive | **Remove** | Cloud storage |
| Telemetry (OTEL) | **Remove** | External collector dependency |
| Gravatar | **Remove** | External fetch |
| GitHub version checks | **Remove** | Internet-dependent |
| Pipelines | **Remove** | External loading mechanism |
| Terminals | **Remove** | Remote proxy feature |

---

## Preserved Feature Set

### Core chat
- Chat with Ollama models (create, continue, branch, regenerate, edit)
- Model selector (Ollama models only)
- Chat history, folders, search, export/import
- Full Markdown + LaTeX rendering
- Code syntax highlighting
- Streaming responses
- System prompts and parameters (temperature, top_p, etc.)

### RAG (local only)
- Document upload (PDF, Markdown, text, etc.)
- Knowledge base management
- Local embeddings via sentence-transformers
- Chroma vector database
- `#` command to reference documents in chat

### Audio (local only)
- Speech-to-text via Faster Whisper
- Text-to-speech via Web Speech API (browser-native)

### Image generation (local only)
- Automatic1111 (Stable Diffusion WebUI)
- ComfyUI

### Plugins (local only)
- Custom functions, tools, skills (manual create/edit, no URL import)
- Built-in Python code editor

### Admin and user management
- Local account signup/signin
- Role-based access (user, admin)
- User groups and permissions
- Usage analytics

### Infrastructure
- SQLite (default) or PostgreSQL
- Docker Compose (Ollama + WebUI)
- PWA mobile support
- Responsive design
- i18n

---

## Backend Changes

### Routers to delete entirely

| Router | Reason |
|--------|--------|
| `channels.py` | Channels feature removed |
| `notes.py` | Notes feature removed |
| `scim.py` | SCIM provisioning removed |
| `pipelines.py` | External pipeline loading removed |
| `terminals.py` | Remote terminal proxy removed |
| `openai.py` | Cloud LLM proxy removed; Ollama is the only backend |

### Routers to simplify

| Router | Changes |
|--------|---------|
| `auths.py` | Remove all OAuth/OIDC/SAML flows. Keep local signup/signin/API key management only |
| `audio.py` | Remove OpenAI Whisper API, Azure Speech, Deepgram, ElevenLabs, Mistral STT. Keep Faster Whisper (local) + Web Speech API passthrough |
| `images.py` | Remove DALL-E and Gemini generators. Keep Automatic1111 + ComfyUI |
| `retrieval.py` | Remove all web search integrations. Remove cloud embedding providers (OpenAI, Azure). Keep local sentence-transformers + Chroma |
| `functions.py` | Remove URL-based function loading from GitHub. Keep manual create/edit/delete |
| `tools.py` | Remove URL-based tool loading. Keep manual tool management |
| `utils.py` | Remove Gravatar fetching |
| `configs.py` | Remove OpenAI connection management. Keep Ollama connection config |

### Directories to delete

- `backend/open_webui/retrieval/web/` — all 15+ search provider modules

### Config and env cleanup

- Remove all OAuth env vars (Google, GitHub, Microsoft, Feishu OIDC)
- Remove all cloud API key configs (OpenAI, Azure, ElevenLabs, Deepgram, Mistral, Perplexity)
- Remove `ENABLE_VERSION_UPDATE_CHECK` and the GitHub release check logic
- Remove all OTEL/telemetry env vars and setup code
- Remove all web search engine config vars
- Remove `ENABLE_OPENAI_API` (no longer applicable)
- Remove `ENABLE_SCIM`
- Remove custom branding fetch from `api.openwebui.com`
- Remove `WEBUI_FAVICON_URL` external default (use local path)
- Set `RAG_EMBEDDING_MODEL_AUTO_UPDATE=False` default
- Set `WHISPER_MODEL_AUTO_UPDATE=False` default

---

## Frontend Changes

### Route pages to delete

| Route | Reason |
|-------|--------|
| `/channels/[id]` | Channels removed |
| `/notes/`, `/notes/new`, `/notes/[id]` | Notes removed |
| `/watch` | Live sharing removed |

### Route pages to simplify

| Route | Changes |
|-------|---------|
| `/auth` | Remove OAuth buttons (Google, GitHub, Microsoft, Feishu). Email/password form only |
| `/admin/settings/[tab]` | Remove OpenAI connections tab, web search config, cloud audio/image provider settings. Simplify to Ollama + local services |
| `/playground` | Keep if functional with Ollama, otherwise remove |

### Component groups to delete

| Component | Reason |
|-----------|--------|
| `channel/` directory | Channels removed |
| `notes/` directory | Notes removed |
| `chat/Messages/ResponseMessage/WebSearchResults.svelte` | Web search removed |

### Component groups to simplify

| Component | Changes |
|-----------|---------|
| `chat/Settings/` | Remove cloud provider config tabs (OpenAI, cloud TTS/STT, cloud image gen). Keep Ollama, local Whisper, Automatic1111/ComfyUI |
| `chat/Messages/Citations.svelte` | Remove Google favicon fetching. Use local placeholder |
| `chat/Settings/About.svelte` | Remove Shields.io badges and external links. Replace with local project info |
| `ModelSelector` | Remove OpenAI model listing. Ollama models only |
| `layout/Sidebar` | Remove channel and notes navigation entries |

### Frontend files to delete

| File | Reason |
|------|--------|
| `src/lib/utils/google-drive-picker.ts` | Cloud storage removed |
| `src/lib/utils/onedrive-file-picker.ts` | Cloud storage removed |

### Frontend files to clean

| File | Changes |
|------|---------|
| `src/lib/utils/index.ts` | Remove Gravatar hash generation |
| `src/app.html` | Verify no external URL references remain |
| `src/lib/constants.ts` | Remove cloud provider constants |

---

## Network Hardening

### Runtime calls to eliminate

| Call | Location | Fix |
|------|----------|-----|
| GitHub release version check | Backend startup | Delete check |
| Gravatar avatar fetch | `utils.py` + frontend | Use local default avatar |
| Google favicon fetch | `Citations.svelte` | Local placeholder |
| Custom branding fetch (`api.openwebui.com`) | `config.py` | Delete fetch block |
| Shields.io badge images | `About.svelte` | Replace with static text |
| HuggingFace model auto-download | RAG init | Pre-download at build time |
| Whisper model auto-download | Audio STT init | Pre-download at build time |

### Build-time asset pinning

- `npm ci` with lockfile (already in place)
- `uv sync` with lockfile (`uv.lock` already in place)
- Pre-download sentence-transformer model into Docker image
- Pre-download Whisper model into Docker image
- Pyodide packages already fetched at build time via `scripts/prepare-pyodide.js`

### Verification

After all changes, run a full grep audit for:
- `https://` references (should only be in comments, licenses, or docs)
- `fetch(` calls to non-relative URLs
- `requests.get/post`, `httpx`, `aiohttp` calls to external hosts
- Any remaining cloud provider API key references

---

## Docker and Deployment

### Image changes

- Bundle pre-downloaded sentence-transformer embedding model
- Bundle pre-downloaded Whisper STT model
- Remove unused Python dependencies for cloud providers where possible

### Docker Compose changes

- Update `docker-compose.yaml` to reflect simplified service set
- Add make target: `make pull-models` to pre-pull Ollama models into Docker volume
- Document `network_mode: internal` for strict airgap enforcement

### Deployment workflow

**"Online build, offline run":**
1. On a connected machine: `docker compose build`, `make pull-models`
2. Export images: `docker save -o myofflineai.tar open-webui ollama`
3. Transfer to airgapped machine
4. Load images: `docker load -i myofflineai.tar`
5. Start: `docker compose up -d`

---

## Phased Execution

### Phase 1: Baseline and Safety Net
- Git tag `pre-simplification` on current commit
- Establish smoke test (chat round-trip with Ollama)
- Document current working build/run steps

### Phase 2: Backend Removal
- Delete dead routers (channels, notes, SCIM, pipelines, terminals, openai)
- Simplify remaining routers (auths, audio, images, retrieval, functions, tools, utils, configs)
- Delete `retrieval/web/` directory
- Clean config.py and env.py
- Remove OAuth, cloud API, telemetry, and version check code
- Run backend tests after each major deletion

### Phase 3: Frontend Removal
- Delete route pages (channels, notes, watch)
- Delete cloud integration components (Google Drive, OneDrive, OAuth buttons, cloud provider settings)
- Simplify settings panels, model selector, about page
- Remove external URL references from templates and components
- Delete frontend utility files for removed features

### Phase 4: Network Hardening
- Remove Gravatar, favicon fetches, badges, branding fetch
- Disable model auto-download defaults
- Add build-time model pre-download scripts
- Run full grep audit for external URLs
- Verify zero outbound calls

### Phase 5: Docker and Deployment
- Update Docker image with bundled models
- Add make target for Ollama model pre-pull
- Update docker-compose.yaml
- Document airgapped deployment workflow
- End-to-end test in network-isolated environment

---

## Upstream Sync Strategy

After simplification, syncing with upstream Open WebUI releases requires:

1. Compare upstream release diff against the removed feature list
2. Cherry-pick bug fixes and improvements to preserved features (chat, RAG, Ollama, local audio, local image gen)
3. Reject changes to removed features (cloud providers, OAuth, channels, notes, web search, telemetry)
4. Review any new features for airgap compliance before merging

Tag each upstream sync point for traceability.
