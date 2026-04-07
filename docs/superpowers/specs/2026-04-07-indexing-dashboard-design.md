# Indexing Dashboard — Filesystem Tab Enhancement

**Date:** 2026-04-07
**Status:** Approved
**Issue:** #6

## Goal

Add indexing visibility to the existing Filesystem admin settings tab — stats, per-directory health, file type breakdown, and per-directory index clearing.

## UX Summary

- **Stats grid** at the top of the Filesystem tab: Files Indexed (completed/total), Chunks, Disk Usage, Failed count
- **File type breakdown** below stats, collapsible, showing count per extension
- **Per-directory enrichment** on existing directory cards: file count + scan status dot (green/yellow/red)
- **Clear Index action** per directory: deletes vectors + file records without removing the directory config
- No new tabs, no new routes. Everything lives in the existing Filesystem settings page.

## Architecture

One new backend endpoint for aggregate stats. One new backend endpoint for per-directory index clearing. Frontend changes only in `Filesystem.svelte` and the filesystem API client.

```
Filesystem.svelte
  ↓ onMount
  ├─ getWatchedDirectories()       [existing]
  ├─ getFilesystemStats()          [NEW → GET /filesystem/stats]
  └─ getRAGConfig()                [existing, for auto-context toggle]
  
Stats grid renders from getFilesystemStats() response.
Directory cards enriched with per-directory data from same response.
Clear Index button calls DELETE /filesystem/{id}/index [NEW].
```

## Backend Changes

### 1. `GET /filesystem/stats` (admin-only)

Returns aggregate indexing stats computed server-side.

```python
{
    "total_files": 5814,
    "completed_files": 3677,
    "pending_files": 2137,
    "failed_files": 0,
    "total_chunks": 17614,
    "vector_db_size_bytes": 126000000,
    "file_types": {".perfs.txt": 3200, ".md": 59, ".js": 86},
    "directories": [
        {
            "id": "watched-dir-uuid",
            "file_count": 3677,
            "last_scan_age_seconds": 3600
        }
    ]
}
```

Data sources:
- `file` + `knowledge_file` tables joined for file counts and statuses
- File extension extracted from `filename` column
- ChromaDB collection `.count()` for total chunks
- `os.path.getsize()` walk on `DATA_DIR/vector_db/` for disk usage
- Per-directory: count files in `knowledge_file` grouped by `knowledge_id`, matched to watched directories

### 2. `DELETE /filesystem/{id}/index` (admin-only)

Clears all indexed data for a single watched directory without removing the directory config.

Steps:
1. Look up `WatchedDirectory.knowledge_id`
2. Delete the ChromaDB collection for that `knowledge_id`
3. Delete all `knowledge_file` records for that `knowledge_id`
4. Delete all `file` records where `meta.watched_directory_id == id`
5. Set `WatchedDirectory.last_scan_at = NULL` (triggers re-scan on next restart)

Returns `{"status": true}`.

## Frontend Changes

### 1. Stats grid (top of Filesystem tab)

Four cards in a responsive grid (`grid-cols-2 md:grid-cols-4`):

| Card | Label | Value |
|------|-------|-------|
| Files Indexed | `Files Indexed` | `{completed} / {total}` |
| Chunks | `Chunks` | `{total_chunks}` |
| Disk Usage | `Disk Usage` | `{size} MB` |
| Failed | `Failed` | `{failed_files}` (red if > 0) |

### 2. File types breakdown (collapsible)

Below the stats grid, a collapsible section showing `extension: count` pairs sorted by count descending. Collapsed by default.

### 3. Per-directory enrichment

Each existing directory card gains:
- **File count** text: "X files indexed"
- **Status dot**: green (< 24h since scan), yellow (1-7 days), red (never or > 7 days)

Data comes from `stats.directories[]` matched by directory ID.

### 4. Clear Index button

New button on each directory card (distinct from existing Remove button):
- Icon: eraser or trash-with-refresh
- Calls `DELETE /filesystem/{id}/index`
- Confirmation via `confirm()` dialog before executing
- After success: refresh stats and directory list

### 5. API client additions

In `src/lib/apis/filesystem/index.ts`, add:
- `getFilesystemStats(token)` → `GET /filesystem/stats`
- `clearDirectoryIndex(token, id)` → `DELETE /filesystem/{id}/index`

## Files Touched

| File | Change |
|------|--------|
| `backend/open_webui/routers/filesystem.py` | Add `GET /stats` and `DELETE /{id}/index` endpoints |
| `backend/open_webui/models/filesystem.py` | Add query methods for stats aggregation |
| `src/lib/components/admin/Settings/Filesystem.svelte` | Stats grid, directory enrichment, clear button |
| `src/lib/apis/filesystem/index.ts` | Add `getFilesystemStats()` and `clearDirectoryIndex()` |

## What Doesn't Change

- Watched directory CRUD (create, update, delete config)
- Filesystem watcher service behavior
- RAG pipeline
- Auto-context injection
- Existing resync button behavior
