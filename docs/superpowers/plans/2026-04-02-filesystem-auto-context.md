# Filesystem Auto-Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all watched directory files automatically available as RAG context in every chat message.

**Architecture:** Inject watched directory knowledge base IDs into the chat middleware's file list, reusing the existing RAG pipeline. Add a `ENABLE_FILESYSTEM_AUTO_CONTEXT` config toggle exposed in both the retrieval API and the Filesystem admin UI.

**Tech Stack:** FastAPI (Python), SvelteKit (TypeScript), SQLAlchemy, existing RAG pipeline

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/open_webui/models/filesystem.py` | Modify | Add `get_all_enabled_knowledge_ids()` query method |
| `backend/open_webui/config.py` | Modify | Add `ENABLE_FILESYSTEM_AUTO_CONTEXT` PersistentConfig |
| `backend/open_webui/main.py` | Modify | Initialize config on `app.state.config` |
| `backend/open_webui/routers/retrieval.py` | Modify | Expose toggle in GET/POST config endpoints |
| `backend/open_webui/utils/middleware.py` | Modify | Inject filesystem knowledge into chat pipeline |
| `src/lib/components/admin/Settings/Filesystem.svelte` | Modify | Add auto-context toggle UI |

---

### Task 1: Add query method to WatchedDirectoriesTable

**Files:**
- Modify: `backend/open_webui/models/filesystem.py:65-146`

- [ ] **Step 1: Add `get_all_enabled_knowledge_ids` method**

Add this method to `WatchedDirectoriesTable` class, after the `get_all` method (line 96):

```python
def get_all_enabled_knowledge_ids(self) -> list[dict]:
    """Return knowledge_id and name for all enabled, indexed watched directories."""
    with get_db() as db:
        try:
            rows = (
                db.query(WatchedDirectory)
                .filter(
                    WatchedDirectory.enabled == True,
                    WatchedDirectory.knowledge_id.isnot(None),
                )
                .all()
            )
            return [
                {"knowledge_id": r.knowledge_id, "name": r.name}
                for r in rows
            ]
        except Exception:
            return []
```

- [ ] **Step 2: Verify the method works**

Run a quick Python check:

```bash
cd /Users/lefv/repos/myOfflineAI && python -c "
from backend.open_webui.models.filesystem import WatchedDirectories
result = WatchedDirectories.get_all_enabled_knowledge_ids()
print(f'Found {len(result)} enabled directories with knowledge IDs')
for r in result:
    print(f'  {r[\"name\"]}: {r[\"knowledge_id\"]}')
"
```

Expected: Prints list of enabled watched directories (may be empty if none configured).

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/models/filesystem.py
git commit -m "feat: add get_all_enabled_knowledge_ids query to WatchedDirectories"
```

---

### Task 2: Add ENABLE_FILESYSTEM_AUTO_CONTEXT config

**Files:**
- Modify: `backend/open_webui/config.py:2072-2081` (near ENABLE_RAG_HYBRID_SEARCH)
- Modify: `backend/open_webui/main.py` (app.state.config initialization)

- [ ] **Step 1: Add PersistentConfig to config.py**

Add after `ENABLE_RAG_HYBRID_SEARCH_ENRICHED_TEXTS` block (around line 2081):

```python
ENABLE_FILESYSTEM_AUTO_CONTEXT = PersistentConfig(
    'ENABLE_FILESYSTEM_AUTO_CONTEXT',
    'rag.filesystem_auto_context',
    os.environ.get('ENABLE_FILESYSTEM_AUTO_CONTEXT', 'true').lower() == 'true',
)
```

- [ ] **Step 2: Initialize on app.state.config in main.py**

Find the line `app.state.config.ENABLE_RAG_HYBRID_SEARCH = ENABLE_RAG_HYBRID_SEARCH` in main.py. Add directly after it:

```python
app.state.config.ENABLE_FILESYSTEM_AUTO_CONTEXT = ENABLE_FILESYSTEM_AUTO_CONTEXT
```

Also add the import at the top of main.py where other config values are imported:

```python
ENABLE_FILESYSTEM_AUTO_CONTEXT,
```

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/config.py backend/open_webui/main.py
git commit -m "feat: add ENABLE_FILESYSTEM_AUTO_CONTEXT config toggle"
```

---

### Task 3: Expose config in retrieval API

**Files:**
- Modify: `backend/open_webui/routers/retrieval.py:338-403` (GET /config)
- Modify: `backend/open_webui/routers/retrieval.py:406-477` (ConfigForm)
- Modify: `backend/open_webui/routers/retrieval.py:480-522` (POST /config/update)

- [ ] **Step 1: Add to GET /config response**

In the `get_rag_config` function (line 339), add after the `'ENABLE_RAG_HYBRID_SEARCH_ENRICHED_TEXTS'` entry (line 349):

```python
'ENABLE_FILESYSTEM_AUTO_CONTEXT': request.app.state.config.ENABLE_FILESYSTEM_AUTO_CONTEXT,
```

- [ ] **Step 2: Add to ConfigForm**

In the `ConfigForm` class, add after `ENABLE_RAG_HYBRID_SEARCH_ENRICHED_TEXTS` (line 415):

```python
ENABLE_FILESYSTEM_AUTO_CONTEXT: Optional[bool] = None
```

- [ ] **Step 3: Add to POST /config/update handler**

In `update_rag_config` function, add after the `ENABLE_RAG_HYBRID_SEARCH_ENRICHED_TEXTS` update block (line 507):

```python
request.app.state.config.ENABLE_FILESYSTEM_AUTO_CONTEXT = (
    form_data.ENABLE_FILESYSTEM_AUTO_CONTEXT
    if form_data.ENABLE_FILESYSTEM_AUTO_CONTEXT is not None
    else request.app.state.config.ENABLE_FILESYSTEM_AUTO_CONTEXT
)
```

- [ ] **Step 4: Verify endpoint works**

Start the backend and test:

```bash
curl -s http://localhost:8080/retrieval/config \
  -H "Authorization: Bearer <token>" | python -m json.tool | grep FILESYSTEM
```

Expected: `"ENABLE_FILESYSTEM_AUTO_CONTEXT": true`

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/retrieval.py
git commit -m "feat: expose ENABLE_FILESYSTEM_AUTO_CONTEXT in retrieval config API"
```

---

### Task 4: Inject filesystem knowledge in chat middleware

**Files:**
- Modify: `backend/open_webui/utils/middleware.py:1999-2039`

This is the core change. After the model knowledge injection block (line 2039), add filesystem knowledge injection.

- [ ] **Step 1: Add import at top of middleware.py**

Add with the other model imports (near the top of the file):

```python
from open_webui.models.filesystem import WatchedDirectories
```

- [ ] **Step 2: Add filesystem knowledge injection block**

Insert after line 2039 (`form_data['files'] = files`) and before line 2041 (`variables = form_data.pop('variables', None)`):

```python
    # Filesystem auto-context: inject all watched directory knowledge bases
    if request.app.state.config.ENABLE_FILESYSTEM_AUTO_CONTEXT:
        fs_knowledge = WatchedDirectories.get_all_enabled_knowledge_ids()
        if fs_knowledge:
            fs_files = [
                {
                    'name': item['name'],
                    'type': 'collection',
                    'collection_names': [item['knowledge_id']],
                    'legacy': True,
                }
                for item in fs_knowledge
            ]
            files = form_data.get('files', [])
            files.extend(fs_files)
            form_data['files'] = files
```

**Why `legacy: True`?** Looking at `get_sources_from_items` (retrieval/utils.py:917-918), when `type == 'collection'` and `legacy` is True, it uses `item.get('collection_names', [])` directly as the collection names for vector search. This matches how the filesystem watcher stores embeddings — using `knowledge_id` as the collection name.

- [ ] **Step 3: Verify the injection**

Start the backend (`cd backend && ./dev.sh`). Send a chat message via the UI. Check the backend logs for:

```
rag_contexts:sources: [...]
```

If watched directories with indexed files exist, you should see sources being retrieved.

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/utils/middleware.py
git commit -m "feat: auto-inject filesystem watcher knowledge into chat context"
```

---

### Task 5: Add auto-context toggle to Filesystem settings UI

**Files:**
- Modify: `src/lib/components/admin/Settings/Filesystem.svelte`

- [ ] **Step 1: Add imports and state**

At the top of the `<script>` block (after line 13), add:

```typescript
import Switch from '$lib/components/common/Switch.svelte';
import { getRAGConfig, updateRAGConfig } from '$lib/apis/retrieval';
```

After `let newExclude` (line 28), add:

```typescript
let autoContextEnabled = true;
let autoContextLoading = true;
```

- [ ] **Step 2: Load config on mount**

Replace the `onMount` block (line 135-137) with:

```typescript
onMount(async () => {
    await loadDirectories();
    try {
        const config = await getRAGConfig(localStorage.token);
        autoContextEnabled = config.ENABLE_FILESYSTEM_AUTO_CONTEXT ?? true;
    } catch (err) {
        console.error('Failed to load auto-context config:', err);
    }
    autoContextLoading = false;
});
```

- [ ] **Step 3: Add toggle handler**

After the `resyncDirectory` function (line 133), add:

```typescript
const toggleAutoContext = async () => {
    try {
        await updateRAGConfig(localStorage.token, {
            ENABLE_FILESYSTEM_AUTO_CONTEXT: autoContextEnabled
        });
        toast.success($i18n.t('Settings saved'));
    } catch (err) {
        toast.error(`${err}`);
        autoContextEnabled = !autoContextEnabled;
    }
};
```

- [ ] **Step 4: Add toggle UI**

In the template, after the "Watched Directories" subtitle `<div>` (line 147-150) and before the `<hr>` (line 152), add:

```svelte
<div class="flex w-full justify-between items-center mt-2 mb-1">
    <div>
        <div class="self-center text-xs font-medium">
            {$i18n.t('Auto-inject local files as context')}
        </div>
        <div class="text-xs text-gray-400 dark:text-gray-500">
            {$i18n.t('Automatically use watched files as context in all conversations')}
        </div>
    </div>
    <div class="flex items-center">
        {#if autoContextLoading}
            <Spinner className="size-4" />
        {:else}
            <Switch
                bind:state={autoContextEnabled}
                on:change={toggleAutoContext}
            />
        {/if}
    </div>
</div>
```

- [ ] **Step 5: Add ENABLE_FILESYSTEM_AUTO_CONTEXT to RAGConfigForm type**

In `src/lib/apis/retrieval/index.ts`, add to the `RAGConfigForm` type (line 53-62):

```typescript
ENABLE_FILESYSTEM_AUTO_CONTEXT?: boolean;
```

- [ ] **Step 6: Test the toggle**

1. Open the admin settings → Filesystem tab
2. Verify the toggle appears and shows the current state
3. Toggle it off → verify toast shows "Settings saved"
4. Refresh page → verify toggle state persisted
5. Send a chat message → verify no filesystem sources are injected
6. Toggle back on → send another message → verify sources appear

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/admin/Settings/Filesystem.svelte src/lib/apis/retrieval/index.ts
git commit -m "feat: add auto-context toggle to Filesystem admin settings"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Start the full stack**

```bash
make startAndBuild
```

Or for development:

```bash
# Terminal 1: backend
cd backend && ./dev.sh

# Terminal 2: frontend
npm run dev
```

- [ ] **Step 2: Configure a watched directory**

1. Go to Admin Settings → Filesystem
2. Add a directory with some test files (e.g., `/tmp/test-watched-dir/` with a few .md or .txt files)
3. Wait for the initial scan to complete (watch backend logs)

- [ ] **Step 3: Test automatic context injection**

1. Open a new chat
2. Ask a question related to the content of the watched files
3. Verify:
   - Status shows "Retrieved X sources" during streaming
   - Citation buttons appear below the AI response
   - Clicking a citation shows the file content snippet
   - The AI response references information from the watched files

- [ ] **Step 4: Test the toggle**

1. Go to Admin Settings → Filesystem
2. Turn off "Auto-inject local files as context"
3. Start a new chat and ask the same question
4. Verify: No sources retrieved, no citations, AI responds without file context

- [ ] **Step 5: Commit any fixes**

If any adjustments were needed during testing, commit them:

```bash
git add -u
git commit -m "fix: adjustments from end-to-end testing"
```
