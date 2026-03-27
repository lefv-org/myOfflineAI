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
