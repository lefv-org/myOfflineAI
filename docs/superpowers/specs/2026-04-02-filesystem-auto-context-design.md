# Filesystem Auto-Context: Search-is-Chat

**Date:** 2026-04-02
**Status:** Approved
**Approach:** Filesystem Knowledge as Global Context (Approach 1)

## Goal

Transform the filesystem watcher from a passive indexer into the backbone of a local document search engine. Every chat message automatically queries all watched file embeddings, shows source indicators, and injects relevant context — no manual knowledge base attachment required.

## UX Summary

- **Search-is-chat:** The chat input is the search. Every message first retrieves matching document sources, then the AI responds with those sources as context.
- **Minimal source display:** Filenames and relevance indicator (e.g., "Retrieved 3 sources"), expandable on click to see snippets. Uses the existing `Citations.svelte` component — no new UI for source display.
- **All-or-nothing corpus:** All enabled watched directories form one unified search corpus. No per-directory filtering.
- **Toggleable:** Admin UI toggle in Filesystem settings to enable/disable auto-injection.

## Architecture

No new services, endpoints, or components. The change rides the existing RAG pipeline.

```
User message
  ↓
middleware.py:process_chat_payload()
  ↓
[Existing] Model knowledge injection (lines 1999-2039)
  ↓
[NEW] Filesystem knowledge injection
  - WatchedDirectories.get_all_enabled_knowledge_ids()
  - Build knowledge file entries (same format as model knowledge)
  - Append to form_data['files']
  ↓
[Existing] chat_completion_files_handler()
  - generate_queries() → vector search → get_sources_from_items()
  ↓
[Existing] apply_source_context_to_messages()
  - RAG template injection into prompt
  ↓
[Existing] Citations.svelte
  - Renders source indicators, expandable to snippets
  ↓
LLM response with local file context
```

## Changes Required

### 1. Backend — Auto-inject filesystem knowledge

**File:** `backend/open_webui/utils/middleware.py`
**Location:** After model knowledge block (~line 2039), before filter functions.

Logic:
1. Check `request.app.state.config.ENABLE_FILESYSTEM_AUTO_CONTEXT`
2. Call `WatchedDirectories.get_all_enabled_knowledge_ids()`
3. For each `knowledge_id`, build a knowledge file entry:
   ```python
   {
       'name': '<watched directory name>',
       'type': 'collection',
       'collection_names': [knowledge_id],
   }
   ```
4. Append to `form_data['files']`

~15 lines of code mirroring the model knowledge pattern.

### 2. Model query method

**File:** `backend/open_webui/models/filesystem.py`

New class method on `WatchedDirectories`:
```python
@classmethod
def get_all_enabled_knowledge_ids(cls) -> list[str]:
    """Return knowledge_ids for all enabled watched directories that have been indexed."""
    # SELECT knowledge_id FROM watched_directory WHERE enabled = true AND knowledge_id IS NOT NULL
```

No schema changes. No migrations.

### 3. Config

**File:** `backend/open_webui/config.py`

New config variable:
- `ENABLE_FILESYSTEM_AUTO_CONTEXT` — `bool`, default `True`
- Stored in `app.state.config` (same pattern as `ENABLE_RAG_HYBRID_SEARCH`)
- Settable via `POST /retrieval/config/update`

### 4. Admin UI toggle

**File:** `src/lib/components/admin/Settings/Filesystem.svelte`

Add toggle: "Auto-inject local files as context" with subtitle "Automatically use watched files as context in all conversations."

Calls existing retrieval config update endpoint. No new API endpoint needed.

### 5. Frontend source display

**No changes.** The existing pipeline handles everything:
- `StatusItem.svelte` shows "Retrieved X sources" during streaming
- `Citations.svelte` renders expandable source buttons with modals
- Filesystem watcher sources flow through unchanged once injected into `form_data['files']`

## Edge Cases

- **Empty state:** No watched directories or none indexed → empty files list → RAG skipped. Handled gracefully.
- **Large corpus:** Vector search returns `TOP_K` chunks regardless of collection size. Local ChromaDB handles this fine.
- **Duplicate context:** Overlapping manual + auto knowledge bases → reranker handles dedup. Harmless worst case.
- **Pending indexing:** Directories without `knowledge_id` yet are filtered out by `IS NOT NULL`.
- **Latency:** ~50-200ms for local vector search. Acceptable for single-user offline tool.

## What Doesn't Change

- Filesystem watcher service — scan, embed, store behavior unchanged
- RAG pipeline — query generation, vector search, reranking, template injection all unchanged
- Knowledge base model — no schema changes
- Chat routing — Ollama/OpenAI-compatible routing unchanged

## Files Touched

| File | Change |
|------|--------|
| `backend/open_webui/utils/middleware.py` | Add filesystem knowledge injection block |
| `backend/open_webui/models/filesystem.py` | Add `get_all_enabled_knowledge_ids()` method |
| `backend/open_webui/config.py` | Add `ENABLE_FILESYSTEM_AUTO_CONTEXT` config |
| `src/lib/components/admin/Settings/Filesystem.svelte` | Add auto-context toggle |
