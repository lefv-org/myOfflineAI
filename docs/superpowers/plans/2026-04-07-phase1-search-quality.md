# Phase 1: Make Search Actually Good — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four biggest search quality issues so RAG actually returns relevant results for user queries.

**Architecture:** Four targeted changes to existing config defaults and one middleware tweak. No new files, no new endpoints, no schema changes.

**Tech Stack:** FastAPI (Python), existing RAG pipeline

**Issues:** #2, #3, #4, #5

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/open_webui/utils/middleware.py` | Modify | Always include raw user message in queries |
| `backend/open_webui/config.py` | Modify | Change defaults for threshold, hybrid search, embedding model/engine |

---

### Task 1: Always include raw user message in retrieval queries (Issue #2)

**Files:**
- Modify: `backend/open_webui/utils/middleware.py:1623-1666`

- [ ] **Step 1: Modify query construction to always include raw user message**

In `chat_completion_files_handler`, after the LLM query generation block (line 1650) and before the empty-check fallback (line 1665), ensure the raw user message is always prepended to the queries list.

Change lines 1665-1666 from:

```python
        if len(queries) == 0:
            queries = [get_last_user_message(body['messages'])]
```

To:

```python
        # Always include the raw user message for direct semantic matching,
        # supplemented by any LLM-generated query variants.
        raw_query = get_last_user_message(body['messages'])
        if raw_query and raw_query not in queries:
            queries.insert(0, raw_query)
```

This ensures the original user intent is always searched, with LLM-generated variants as supplements.

- [ ] **Step 2: Commit**

```bash
git add backend/open_webui/utils/middleware.py
git commit -m "fix(rag): always include raw user message in retrieval queries (fixes #2)"
```

---

### Task 2: Set meaningful relevance threshold (Issue #3)

**Files:**
- Modify: `backend/open_webui/config.py:2061-2065`

- [ ] **Step 1: Change default RELEVANCE_THRESHOLD from 0.0 to 0.3**

Change line 2064 from:

```python
    float(os.environ.get('RAG_RELEVANCE_THRESHOLD', '0.0')),
```

To:

```python
    float(os.environ.get('RAG_RELEVANCE_THRESHOLD', '0.3')),
```

- [ ] **Step 2: Commit**

```bash
git add backend/open_webui/config.py
git commit -m "feat(rag): set default relevance threshold to 0.3 (fixes #3)"
```

---

### Task 3: Enable hybrid search by default (Issue #5)

**Files:**
- Modify: `backend/open_webui/config.py:2072-2076`

- [ ] **Step 1: Change default ENABLE_RAG_HYBRID_SEARCH from False to True**

Change line 2075 from:

```python
    os.environ.get('ENABLE_RAG_HYBRID_SEARCH', '').lower() == 'true',
```

To:

```python
    os.environ.get('ENABLE_RAG_HYBRID_SEARCH', 'true').lower() == 'true',
```

- [ ] **Step 2: Commit**

```bash
git add backend/open_webui/config.py
git commit -m "feat(rag): enable hybrid search (BM25 + vector) by default (fixes #5)"
```

---

### Task 4: Switch embedding model to nomic-embed-text via Ollama (Issue #4)

**Files:**
- Modify: `backend/open_webui/config.py:2127-2131` and `2145-2149`

- [ ] **Step 1: Change default RAG_EMBEDDING_ENGINE to 'ollama'**

Change line 2130 from:

```python
    os.environ.get('RAG_EMBEDDING_ENGINE', ''),
```

To:

```python
    os.environ.get('RAG_EMBEDDING_ENGINE', 'ollama'),
```

- [ ] **Step 2: Change default RAG_EMBEDDING_MODEL to 'nomic-embed-text'**

Change line 2148 from:

```python
    os.environ.get('RAG_EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'),
```

To:

```python
    os.environ.get('RAG_EMBEDDING_MODEL', 'nomic-embed-text'),
```

- [ ] **Step 3: Pull the nomic-embed-text model via Ollama**

```bash
ollama pull nomic-embed-text
```

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/config.py
git commit -m "feat(rag): switch to nomic-embed-text via Ollama for better embeddings (fixes #4)"
```

---

### Task 5: Re-index existing files with new embedding model

After changing the embedding model, existing embeddings (generated with all-MiniLM-L6-v2 at 384 dimensions) are incompatible with nomic-embed-text (768 dimensions). The vector DB must be cleared and files re-indexed.

- [ ] **Step 1: Clear the vector DB via the admin API or directly**

Use the existing admin endpoint:
```bash
curl -X POST http://localhost:8081/retrieval/reset/db \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json"
```

Or directly:
```bash
rm -rf backend/data/vector_db/*
```

- [ ] **Step 2: Reset file statuses to trigger re-indexing**

```bash
sqlite3 backend/data/webui.db "UPDATE file SET data = json_set(data, '$.status', NULL) WHERE json_extract(data, '$.status') = 'completed';"
sqlite3 backend/data/webui.db "UPDATE watched_directory SET last_scan_at = NULL;"
```

- [ ] **Step 3: Restart backend to trigger a full re-scan with new embeddings**

```bash
make dev
```

- [ ] **Step 4: Verify new embeddings are being created**

Check logs for embedding model being used:
```
Embedding model set: nomic-embed-text
```

Check vector DB for new dimension:
```bash
sqlite3 backend/data/vector_db/chroma.sqlite3 "SELECT dimension FROM collections;"
```

Expected: `768` (nomic-embed-text dimension)

- [ ] **Step 5: Commit any cleanup**

```bash
git add -u
git commit -m "chore: re-index with nomic-embed-text embeddings"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Wait for initial scan to complete**

Watch logs for "Scan complete for 'repos'" message.

- [ ] **Step 2: Test queries that previously failed**

Send these messages in the chat:
1. "tell me about my test results" — should now return performance benchmark sources
2. "what GPU was used?" — should match .perfs.txt content
3. "what changed in version 1.2.1?" — should match release notes

- [ ] **Step 3: Verify "Retrieved X sources" appears**

Each query should show a non-zero source count and citation buttons.

- [ ] **Step 4: Verify irrelevant queries return no sources**

"what's the weather today?" should return 0 sources (relevance threshold filters them).
