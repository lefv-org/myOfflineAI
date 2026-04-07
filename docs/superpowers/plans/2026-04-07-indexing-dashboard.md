# Indexing Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add indexing stats, per-directory health indicators, and index clearing to the existing Filesystem admin settings tab.

**Architecture:** One new stats endpoint, one new clear-index endpoint, frontend enhancements to the existing Filesystem.svelte component and filesystem API client.

**Tech Stack:** FastAPI (Python), SvelteKit (TypeScript), SQLAlchemy, ChromaDB

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/open_webui/routers/filesystem.py` | Modify | Add `GET /stats` and `DELETE /{id}/index` endpoints |
| `backend/open_webui/models/filesystem.py` | Modify | Add `clear_last_scan` method |
| `src/lib/apis/filesystem/index.ts` | Modify | Add `getFilesystemStats()` and `clearDirectoryIndex()` API functions |
| `src/lib/components/admin/Settings/Filesystem.svelte` | Modify | Add stats grid, per-directory enrichment, clear button |

---

### Task 1: Add stats endpoint to filesystem router

**Files:**
- Modify: `backend/open_webui/routers/filesystem.py:1-151`

- [ ] **Step 1: Add imports for stats computation**

At the top of `backend/open_webui/routers/filesystem.py`, add these imports after the existing ones (after line 13):

```python
import time
from open_webui.internal.db import get_db
from open_webui.models.files import File
from open_webui.models.knowledge import KnowledgeFile
from open_webui.env import DATA_DIR
from sqlalchemy import func, case
```

- [ ] **Step 2: Add the stats response model**

After the `BrowseResponse` class (after line 35), add:

```python
class DirectoryStats(BaseModel):
    id: str
    file_count: int
    last_scan_age_seconds: Optional[int] = None


class FilesystemStatsResponse(BaseModel):
    total_files: int
    completed_files: int
    pending_files: int
    failed_files: int
    total_chunks: int
    vector_db_size_bytes: int
    file_types: dict[str, int]
    directories: list[DirectoryStats]
```

- [ ] **Step 3: Add the stats endpoint**

After the `browse_directories` endpoint (after line 56), add:

```python
@router.get("/stats")
async def get_filesystem_stats(user=Depends(get_admin_user)) -> FilesystemStatsResponse:
    """Return aggregate indexing stats for all watched directories."""
    watched = WatchedDirectories.get_all()
    knowledge_ids = [wd.knowledge_id for wd in watched if wd.knowledge_id]

    total_files = 0
    completed_files = 0
    pending_files = 0
    failed_files = 0
    file_types: dict[str, int] = {}

    if knowledge_ids:
        with get_db() as db:
            rows = (
                db.query(
                    func.count(File.id),
                    func.sum(case((File.data['status'].as_string() == 'completed', 1), else_=0)),
                    func.sum(case((File.data['status'].as_string() == 'failed', 1), else_=0)),
                )
                .join(KnowledgeFile, File.id == KnowledgeFile.file_id)
                .filter(KnowledgeFile.knowledge_id.in_(knowledge_ids))
                .first()
            )
            if rows:
                total_files = rows[0] or 0
                completed_files = int(rows[1] or 0)
                failed_files = int(rows[2] or 0)
                pending_files = total_files - completed_files - failed_files

            # File type breakdown
            type_rows = (
                db.query(File.filename)
                .join(KnowledgeFile, File.id == KnowledgeFile.file_id)
                .filter(KnowledgeFile.knowledge_id.in_(knowledge_ids))
                .all()
            )
            for (filename,) in type_rows:
                ext = os.path.splitext(filename)[1].lower() if filename else ''
                if ext:
                    file_types[ext] = file_types.get(ext, 0) + 1

    # Vector DB chunk count
    total_chunks = 0
    try:
        from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
        for kid in knowledge_ids:
            if VECTOR_DB_CLIENT.has_collection(kid):
                result = VECTOR_DB_CLIENT.get(kid)
                if result and result.get('ids'):
                    total_chunks += len(result['ids'][0]) if isinstance(result['ids'][0], list) else len(result['ids'])
    except Exception as e:
        log.warning("Could not count vector chunks: %s", e)

    # Vector DB disk usage
    vector_db_size = 0
    vector_db_path = DATA_DIR / 'vector_db'
    if vector_db_path.exists():
        for dirpath, dirnames, filenames in os.walk(vector_db_path):
            for f in filenames:
                vector_db_size += os.path.getsize(os.path.join(dirpath, f))

    # Per-directory stats
    now = int(time.time())
    dir_stats = []
    for wd in watched:
        file_count = 0
        if wd.knowledge_id:
            with get_db() as db:
                file_count = (
                    db.query(func.count(KnowledgeFile.id))
                    .filter(KnowledgeFile.knowledge_id == wd.knowledge_id)
                    .scalar() or 0
                )
        dir_stats.append(DirectoryStats(
            id=wd.id,
            file_count=file_count,
            last_scan_age_seconds=(now - wd.last_scan_at) if wd.last_scan_at else None,
        ))

    return FilesystemStatsResponse(
        total_files=total_files,
        completed_files=completed_files,
        pending_files=pending_files,
        failed_files=failed_files,
        total_chunks=total_chunks,
        vector_db_size_bytes=vector_db_size,
        file_types=dict(sorted(file_types.items(), key=lambda x: -x[1])),
        directories=dir_stats,
    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/routers/filesystem.py
git commit -m "feat: add GET /filesystem/stats endpoint for indexing dashboard (issue #6)"
```

---

### Task 2: Add clear-index endpoint

**Files:**
- Modify: `backend/open_webui/routers/filesystem.py`
- Modify: `backend/open_webui/models/filesystem.py`

- [ ] **Step 1: Add `clear_last_scan` method to WatchedDirectoriesTable**

In `backend/open_webui/models/filesystem.py`, after the `set_last_scan` method (after line 153), add:

```python
    def clear_last_scan(self, id: str) -> None:
        with get_db() as db:
            db.query(WatchedDirectory).filter_by(id=id).update(
                {"last_scan_at": None, "updated_at": int(time.time())}
            )
            db.commit()
```

- [ ] **Step 2: Add the clear-index endpoint to filesystem router**

In `backend/open_webui/routers/filesystem.py`, after the `resync_watched_directory` endpoint (after line 150), add:

```python
@router.delete("/{id}/index")
async def clear_directory_index(
    id: str,
    user=Depends(get_admin_user),
):
    """Clear all indexed data for a watched directory without removing the directory config."""
    wd = WatchedDirectories.get_by_id(id)
    if not wd:
        raise HTTPException(status_code=404, detail="Watched directory not found")

    if not wd.knowledge_id:
        return {"status": True, "message": "No index to clear"}

    # Delete vector collection
    try:
        from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
        if VECTOR_DB_CLIENT.has_collection(wd.knowledge_id):
            VECTOR_DB_CLIENT.delete_collection(wd.knowledge_id)
            log.info("Deleted vector collection %s", wd.knowledge_id)
    except Exception as e:
        log.warning("Could not delete vector collection: %s", e)

    # Delete knowledge_file links and file records
    from open_webui.models.knowledge import Knowledges, KnowledgeFile as KFModel
    from open_webui.models.files import Files

    with get_db() as db:
        file_ids = [
            row[0] for row in
            db.query(KFModel.file_id).filter_by(knowledge_id=wd.knowledge_id).all()
        ]
        db.query(KFModel).filter_by(knowledge_id=wd.knowledge_id).delete()
        db.commit()

    for fid in file_ids:
        Files.delete_file_by_id(fid)

    # Reset scan timestamp to trigger re-scan on next restart
    WatchedDirectories.clear_last_scan(id)

    log.info("Cleared index for directory '%s' (%d files removed)", wd.name, len(file_ids))
    return {"status": True, "files_removed": len(file_ids)}
```

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/routers/filesystem.py backend/open_webui/models/filesystem.py
git commit -m "feat: add DELETE /filesystem/{id}/index endpoint to clear directory index (issue #6)"
```

---

### Task 3: Add API client functions

**Files:**
- Modify: `src/lib/apis/filesystem/index.ts`

- [ ] **Step 1: Add TypeScript types for stats response**

At the end of the types section (after the `WatchedDirectoryForm` type, line 57), add:

```typescript
export type DirectoryStats = {
	id: string;
	file_count: number;
	last_scan_age_seconds: number | null;
};

export type FilesystemStats = {
	total_files: number;
	completed_files: number;
	pending_files: number;
	failed_files: number;
	total_chunks: number;
	vector_db_size_bytes: number;
	file_types: Record<string, number>;
	directories: DirectoryStats[];
};
```

- [ ] **Step 2: Add `getFilesystemStats` function**

After the `resyncWatchedDirectory` function (after line 201), add:

```typescript
export const getFilesystemStats = async (token: string): Promise<FilesystemStats> => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/stats`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
```

- [ ] **Step 3: Add `clearDirectoryIndex` function**

After the `getFilesystemStats` function, add:

```typescript
export const clearDirectoryIndex = async (token: string, id: string) => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/${id}/index`, {
		method: 'DELETE',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
```

- [ ] **Step 4: Commit**

```bash
git add src/lib/apis/filesystem/index.ts
git commit -m "feat: add getFilesystemStats and clearDirectoryIndex API functions (issue #6)"
```

---

### Task 4: Add stats grid to Filesystem.svelte

**Files:**
- Modify: `src/lib/components/admin/Settings/Filesystem.svelte`

- [ ] **Step 1: Add imports and state for stats**

In the `<script>` block, add to the imports (after the existing filesystem imports on line 13):

```typescript
import {
	getWatchedDirectories,
	createWatchedDirectory,
	deleteWatchedDirectory,
	resyncWatchedDirectory,
	browseDirectories,
	getFilesystemStats,
	clearDirectoryIndex,
	type WatchedDirectory,
	type FilesystemStats
} from '$lib/apis/filesystem';
```

Replace the existing individual imports with this combined import.

After the `autoContextLoading` variable (around line 32), add:

```typescript
let stats: FilesystemStats | null = null;
let showFileTypes = false;
```

- [ ] **Step 2: Update onMount to load stats**

In the `onMount` block, after `await loadDirectories();`, add:

```typescript
    try {
        stats = await getFilesystemStats(localStorage.token);
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
```

- [ ] **Step 3: Add refreshStats helper and clearIndex handler**

After the `toggleAutoContext` function, add:

```typescript
const refreshStats = async () => {
    try {
        stats = await getFilesystemStats(localStorage.token);
    } catch (err) {
        console.error('Failed to refresh stats:', err);
    }
};

const clearIndex = async (id: string, name: string) => {
    if (!confirm($i18n.t('Clear all indexed data for "{{name}}"? This will require a re-scan.', { name }))) {
        return;
    }
    try {
        await clearDirectoryIndex(localStorage.token, id);
        toast.success($i18n.t('Index cleared'));
        await loadDirectories();
        await refreshStats();
    } catch (err) {
        toast.error(`${err}`);
    }
};
```

- [ ] **Step 4: Add stats grid UI**

In the template, after the auto-context toggle `</div>` and before the `<hr>` (around line 195 in the current file), add:

```svelte
				{#if stats}
					<div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850">
							<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Files Indexed')}</div>
							<div class="text-lg font-bold mt-0.5">
								{stats.completed_files.toLocaleString()}
								<span class="text-xs font-normal text-gray-400">/ {stats.total_files.toLocaleString()}</span>
							</div>
						</div>
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850">
							<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Chunks')}</div>
							<div class="text-lg font-bold mt-0.5">{stats.total_chunks.toLocaleString()}</div>
						</div>
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-850">
							<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Disk Usage')}</div>
							<div class="text-lg font-bold mt-0.5">{(stats.vector_db_size_bytes / 1024 / 1024).toFixed(1)} MB</div>
						</div>
						<div class="p-3 rounded-lg {stats.failed_files > 0 ? 'bg-red-50 dark:bg-red-900/20' : 'bg-gray-50 dark:bg-gray-850'}">
							<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Failed')}</div>
							<div class="text-lg font-bold mt-0.5 {stats.failed_files > 0 ? 'text-red-600 dark:text-red-400' : ''}">{stats.failed_files}</div>
						</div>
					</div>

					{#if Object.keys(stats.file_types).length > 0}
						<button
							class="text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 mt-2 transition"
							on:click={() => (showFileTypes = !showFileTypes)}
						>
							{showFileTypes ? $i18n.t('Hide file types') : $i18n.t('Show file types')}
						</button>
						{#if showFileTypes}
							<div class="flex flex-wrap gap-2 mt-1">
								{#each Object.entries(stats.file_types) as [ext, count]}
									<span class="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
										{ext}: {count.toLocaleString()}
									</span>
								{/each}
							</div>
						{/if}
					{/if}
				{/if}
```

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/admin/Settings/Filesystem.svelte
git commit -m "feat: add stats grid and file type breakdown to Filesystem settings (issue #6)"
```

---

### Task 5: Add per-directory enrichment and clear button

**Files:**
- Modify: `src/lib/components/admin/Settings/Filesystem.svelte`

- [ ] **Step 1: Add helper function for scan status color**

In the `<script>` block, after the `clearIndex` function, add:

```typescript
const getScanStatusColor = (ageSeconds: number | null): string => {
    if (ageSeconds === null) return 'bg-red-500';
    if (ageSeconds < 86400) return 'bg-green-500';
    if (ageSeconds < 604800) return 'bg-yellow-500';
    return 'bg-red-500';
};

const getDirStats = (dirId: string) => {
    return stats?.directories?.find((d) => d.id === dirId) || null;
};
```

- [ ] **Step 2: Enrich directory cards**

In the template, find the directory card content (around line 160-177 in the current file). The section that shows `{dir.name}`, `{dir.path}`, extensions, and last scan time.

Replace the `<div class="flex-1 min-w-0">` block inside each directory card with:

```svelte
								<div class="flex-1 min-w-0">
									<div class="flex items-center gap-2">
										{#if getDirStats(dir.id)}
											<span class="w-2 h-2 rounded-full {getScanStatusColor(getDirStats(dir.id)?.last_scan_age_seconds ?? null)}" title="{getDirStats(dir.id)?.last_scan_age_seconds !== null ? Math.floor((getDirStats(dir.id)?.last_scan_age_seconds ?? 0) / 3600) + 'h ago' : 'Never scanned'}"></span>
										{/if}
										<span class="font-medium truncate">{dir.name}</span>
									</div>
									<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
										{dir.path}
									</div>
									{#if getDirStats(dir.id)?.file_count}
										<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
											{getDirStats(dir.id)?.file_count.toLocaleString()} {$i18n.t('files indexed')}
										</div>
									{/if}
									{#if dir.extensions}
										<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
											{dir.extensions}
										</div>
									{/if}
									{#if dir.last_scan_at}
										<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
											{$i18n.t('Last scan')}: {new Date(
												dir.last_scan_at * 1000
											).toLocaleString()}
										</div>
									{/if}
								</div>
```

- [ ] **Step 3: Add clear index button to directory action buttons**

Find the button group with Resync and Remove buttons (around line 178-207). Between the Resync button's `</Tooltip>` and the Remove button's `<Tooltip>`, add:

```svelte
									<Tooltip content={$i18n.t('Clear Index')}>
										<button
											class="p-1.5 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/20 text-amber-600 transition"
											on:click={() => clearIndex(dir.id, dir.name)}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="size-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
												/>
											</svg>
										</button>
									</Tooltip>
```

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/admin/Settings/Filesystem.svelte
git commit -m "feat: add per-directory stats, scan status dots, and clear index button (issue #6)"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Start the dev server**

```bash
make dev
```

- [ ] **Step 2: Verify stats endpoint**

```bash
curl -s http://localhost:8081/api/v1/filesystem/stats \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

Expected: JSON with total_files, completed_files, total_chunks, vector_db_size_bytes, file_types, directories.

- [ ] **Step 3: Verify the UI**

1. Open Admin Settings → Filesystem
2. Verify: stats grid shows at the top (Files Indexed, Chunks, Disk Usage, Failed)
3. Verify: "Show file types" link expands to show extension breakdown
4. Verify: each directory card has a colored status dot and file count
5. Verify: "Clear Index" button appears on each directory card

- [ ] **Step 4: Test clear index**

1. Click "Clear Index" on a directory
2. Verify: confirmation dialog appears
3. Confirm → verify: toast "Index cleared"
4. Verify: stats refresh and show 0 files for that directory
5. Verify: vector DB collection is deleted

- [ ] **Step 5: Commit any fixes**

```bash
git add -u
git commit -m "fix: adjustments from end-to-end testing"
```
