# Filesystem Vector Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Watch permitted filesystem directories and automatically sync their contents into the existing Chroma vector database so users can chat with local files in real time.

**Architecture:** A `watchdog`-based filesystem observer runs as a background `asyncio` task inside the FastAPI lifespan. A new `WatchedDirectory` SQLAlchemy model tracks which paths to watch. Changed files are processed through the existing `process_file()` RAG pipeline (chunking → sentence-transformers embedding → Chroma storage). Each watched directory maps 1:1 to a Knowledge Base, so files appear in the existing KB UI.

**Tech Stack:** Python `watchdog` for filesystem events, SQLAlchemy + Alembic for persistence, existing Chroma + sentence-transformers pipeline for embedding, SvelteKit admin panel for configuration.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/open_webui/models/filesystem.py` | `WatchedDirectory` ORM + Pydantic models, CRUD operations |
| `backend/open_webui/services/filesystem_watcher.py` | Watchdog observer, debounced event handler, background task |
| `backend/open_webui/routers/filesystem.py` | REST API: CRUD for watched directories, sync status, manual resync |
| `backend/open_webui/migrations/versions/xxx_add_watched_directory.py` | Alembic migration for new table |
| `backend/open_webui/test/apps/webui/models/test_filesystem.py` | Unit tests for model CRUD |
| `backend/open_webui/test/apps/webui/services/test_filesystem_watcher.py` | Unit tests for watcher logic |
| `src/lib/apis/filesystem/index.ts` | Frontend API client for filesystem endpoints |
| `src/lib/components/admin/Settings/Filesystem.svelte` | Admin UI panel for managing watched directories |

---

### Task 1: WatchedDirectory Model

**Files:**
- Create: `backend/open_webui/models/filesystem.py`
- Test: `backend/open_webui/test/apps/webui/models/test_filesystem.py`

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/apps/webui/models/test_filesystem.py`:

```python
import time
import pytest
from open_webui.models.filesystem import (
    WatchedDirectories,
    WatchedDirectoryForm,
    WatchedDirectoryModel,
)


def test_insert_new_watched_directory():
    form = WatchedDirectoryForm(
        path="/tmp/test-watch",
        name="Test Directory",
        extensions=".md,.txt,.pdf",
        exclude_patterns=".git,node_modules",
    )
    result = WatchedDirectories.insert(user_id="test-user-1", form_data=form)
    assert result is not None
    assert result.path == "/tmp/test-watch"
    assert result.name == "Test Directory"
    assert result.extensions == ".md,.txt,.pdf"
    assert result.exclude_patterns == ".git,node_modules"
    assert result.knowledge_id is None
    assert result.enabled is True
    # Cleanup
    WatchedDirectories.delete_by_id(result.id)


def test_get_all_watched_directories():
    form = WatchedDirectoryForm(path="/tmp/test-list", name="List Test")
    wd = WatchedDirectories.insert(user_id="test-user-1", form_data=form)
    results = WatchedDirectories.get_all()
    assert any(d.id == wd.id for d in results)
    WatchedDirectories.delete_by_id(wd.id)


def test_get_by_id():
    form = WatchedDirectoryForm(path="/tmp/test-get", name="Get Test")
    wd = WatchedDirectories.insert(user_id="test-user-1", form_data=form)
    fetched = WatchedDirectories.get_by_id(wd.id)
    assert fetched is not None
    assert fetched.path == "/tmp/test-get"
    WatchedDirectories.delete_by_id(wd.id)


def test_update_watched_directory():
    form = WatchedDirectoryForm(path="/tmp/test-update", name="Before")
    wd = WatchedDirectories.insert(user_id="test-user-1", form_data=form)
    updated = WatchedDirectories.update_by_id(
        wd.id,
        WatchedDirectoryForm(path="/tmp/test-update", name="After"),
    )
    assert updated is not None
    assert updated.name == "After"
    WatchedDirectories.delete_by_id(wd.id)


def test_delete_watched_directory():
    form = WatchedDirectoryForm(path="/tmp/test-delete", name="Delete Test")
    wd = WatchedDirectories.insert(user_id="test-user-1", form_data=form)
    assert WatchedDirectories.delete_by_id(wd.id) is True
    assert WatchedDirectories.get_by_id(wd.id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && python -m pytest open_webui/test/apps/webui/models/test_filesystem.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.models.filesystem'`

- [ ] **Step 3: Implement the model**

Create `backend/open_webui/models/filesystem.py`:

```python
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Text
from open_webui.internal.db import Base, get_db


class WatchedDirectory(Base):
    __tablename__ = "watched_directory"

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text, nullable=False)
    path = Column(Text, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    knowledge_id = Column(Text, nullable=True)

    extensions = Column(Text, nullable=True)  # comma-separated: ".md,.txt,.pdf"
    exclude_patterns = Column(Text, nullable=True)  # comma-separated: ".git,node_modules"

    enabled = Column(Boolean, default=True, nullable=False)
    last_scan_at = Column(BigInteger, nullable=True)

    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class WatchedDirectoryModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    path: str
    name: str
    knowledge_id: Optional[str] = None
    extensions: Optional[str] = None
    exclude_patterns: Optional[str] = None
    enabled: bool = True
    last_scan_at: Optional[int] = None
    created_at: int
    updated_at: int


class WatchedDirectoryForm(BaseModel):
    path: str
    name: str
    extensions: Optional[str] = None
    exclude_patterns: Optional[str] = None
    enabled: bool = True


class WatchedDirectoriesTable:
    def insert(
        self, user_id: str, form_data: WatchedDirectoryForm
    ) -> Optional[WatchedDirectoryModel]:
        with get_db() as db:
            now = int(time.time())
            wd = WatchedDirectory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                path=form_data.path,
                name=form_data.name,
                extensions=form_data.extensions,
                exclude_patterns=form_data.exclude_patterns,
                enabled=form_data.enabled,
                created_at=now,
                updated_at=now,
            )
            db.add(wd)
            db.commit()
            db.refresh(wd)
            return WatchedDirectoryModel.model_validate(wd)

    def get_all(self) -> list[WatchedDirectoryModel]:
        with get_db() as db:
            rows = db.query(WatchedDirectory).all()
            return [WatchedDirectoryModel.model_validate(r) for r in rows]

    def get_by_id(self, id: str) -> Optional[WatchedDirectoryModel]:
        with get_db() as db:
            row = db.query(WatchedDirectory).filter_by(id=id).first()
            return WatchedDirectoryModel.model_validate(row) if row else None

    def update_by_id(
        self, id: str, form_data: WatchedDirectoryForm
    ) -> Optional[WatchedDirectoryModel]:
        with get_db() as db:
            row = db.query(WatchedDirectory).filter_by(id=id).first()
            if not row:
                return None
            row.path = form_data.path
            row.name = form_data.name
            row.extensions = form_data.extensions
            row.exclude_patterns = form_data.exclude_patterns
            row.enabled = form_data.enabled
            row.updated_at = int(time.time())
            db.commit()
            db.refresh(row)
            return WatchedDirectoryModel.model_validate(row)

    def set_knowledge_id(self, id: str, knowledge_id: str) -> None:
        with get_db() as db:
            row = db.query(WatchedDirectory).filter_by(id=id).first()
            if row:
                row.knowledge_id = knowledge_id
                row.updated_at = int(time.time())
                db.commit()

    def set_last_scan(self, id: str) -> None:
        with get_db() as db:
            row = db.query(WatchedDirectory).filter_by(id=id).first()
            if row:
                row.last_scan_at = int(time.time())
                row.updated_at = int(time.time())
                db.commit()

    def delete_by_id(self, id: str) -> bool:
        with get_db() as db:
            row = db.query(WatchedDirectory).filter_by(id=id).first()
            if row:
                db.delete(row)
                db.commit()
                return True
            return False


WatchedDirectories = WatchedDirectoriesTable()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && python -m pytest open_webui/test/apps/webui/models/test_filesystem.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/filesystem.py backend/open_webui/test/apps/webui/models/test_filesystem.py
git commit -m "feat: add WatchedDirectory model with CRUD operations"
```

---

### Task 2: Alembic Migration

**Files:**
- Create: `backend/open_webui/migrations/versions/001_add_watched_directory.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend && source .venv/bin/activate
alembic revision --autogenerate -m "add watched_directory table"
```

- [ ] **Step 2: Verify the generated migration contains the table creation**

The generated file should contain:

```python
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from open_webui.migrations.util import get_existing_tables

revision: str = '<auto-generated>'
down_revision: Union[str, None] = '<previous>'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if "watched_directory" not in existing_tables:
        op.create_table(
            "watched_directory",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("knowledge_id", sa.Text(), nullable=True),
            sa.Column("extensions", sa.Text(), nullable=True),
            sa.Column("exclude_patterns", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_scan_at", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("path"),
        )


def downgrade() -> None:
    op.drop_table("watched_directory")
```

- [ ] **Step 3: Run migration**

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

Expected: `INFO [alembic.runtime.migration] Running upgrade ... -> ..., add watched_directory table`

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/migrations/versions/
git commit -m "feat: add watched_directory migration"
```

---

### Task 3: Filesystem Sync Engine

**Files:**
- Create: `backend/open_webui/services/filesystem_watcher.py`
- Test: `backend/open_webui/test/apps/webui/services/test_filesystem_watcher.py`

- [ ] **Step 1: Write the failing test for file discovery**

Create `backend/open_webui/test/apps/webui/services/test_filesystem_watcher.py`:

```python
import os
import tempfile
import pytest
from open_webui.services.filesystem_watcher import (
    discover_files,
    should_include_file,
    compute_file_hash,
)


def test_should_include_file_with_extensions():
    assert should_include_file("readme.md", extensions={".md", ".txt"}, exclude=set()) is True
    assert should_include_file("image.png", extensions={".md", ".txt"}, exclude=set()) is False


def test_should_include_file_no_extensions():
    assert should_include_file("anything.xyz", extensions=set(), exclude=set()) is True


def test_should_include_file_excludes():
    assert should_include_file(".git/config", extensions=set(), exclude={".git"}) is False
    assert should_include_file("node_modules/pkg/index.js", extensions=set(), exclude={"node_modules"}) is False
    assert should_include_file("src/main.py", extensions=set(), exclude={".git"}) is True


def test_discover_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        open(os.path.join(tmpdir, "readme.md"), "w").close()
        open(os.path.join(tmpdir, "notes.txt"), "w").close()
        open(os.path.join(tmpdir, "image.png"), "w").close()
        os.makedirs(os.path.join(tmpdir, ".git"))
        open(os.path.join(tmpdir, ".git", "config"), "w").close()

        files = discover_files(tmpdir, extensions={".md", ".txt"}, exclude={".git"})
        basenames = {os.path.basename(f) for f in files}
        assert basenames == {"readme.md", "notes.txt"}


def test_compute_file_hash():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello world")
        f.flush()
        h1 = compute_file_hash(f.name)
        assert isinstance(h1, str)
        assert len(h1) == 64  # SHA-256 hex digest

    os.unlink(f.name)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && python -m pytest open_webui/test/apps/webui/services/test_filesystem_watcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.services'`

- [ ] **Step 3: Implement the sync engine**

Create `backend/open_webui/services/__init__.py` (empty file).

Create `backend/open_webui/services/filesystem_watcher.py`:

```python
import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from open_webui.models.filesystem import WatchedDirectories, WatchedDirectoryModel

log = logging.getLogger(__name__)

# ── Pure helpers (no side effects, easy to test) ──────────────────────


def should_include_file(
    rel_path: str,
    extensions: set[str],
    exclude: set[str],
) -> bool:
    """Return True if the file passes extension and exclude filters."""
    parts = Path(rel_path).parts
    for part in parts:
        if part in exclude:
            return False

    if not extensions:
        return True

    return Path(rel_path).suffix.lower() in extensions


def discover_files(
    root: str,
    extensions: set[str],
    exclude: set[str],
) -> list[str]:
    """Walk a directory tree and return absolute paths of matching files."""
    results: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if d not in exclude]

        for fname in filenames:
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root)
            if should_include_file(rel_path, extensions, exclude):
                results.append(abs_path)
    return results


def compute_file_hash(path: str) -> str:
    """Return SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_csv_set(csv_str: Optional[str]) -> set[str]:
    """Parse a comma-separated string into a set, stripping whitespace."""
    if not csv_str:
        return set()
    return {s.strip() for s in csv_str.split(",") if s.strip()}


# ── Watchdog event handler ────────────────────────────────────────────


class DebouncedHandler(FileSystemEventHandler):
    """Collects filesystem events and flushes them after a quiet period."""

    def __init__(self, loop: asyncio.AbstractEventLoop, callback, debounce_sec: float = 2.0):
        super().__init__()
        self._loop = loop
        self._callback = callback
        self._debounce_sec = debounce_sec
        self._pending: dict[str, str] = {}  # path → event_type
        self._timer: Optional[asyncio.TimerHandle] = None

    def _schedule_flush(self):
        if self._timer:
            self._timer.cancel()
        self._timer = self._loop.call_later(self._debounce_sec, self._flush)

    def _flush(self):
        if not self._pending:
            return
        batch = dict(self._pending)
        self._pending.clear()
        asyncio.run_coroutine_threadsafe(self._callback(batch), self._loop)

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._pending[event.src_path] = "created"
            self._loop.call_soon_threadsafe(self._schedule_flush)

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._pending[event.src_path] = "modified"
            self._loop.call_soon_threadsafe(self._schedule_flush)

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._pending[event.src_path] = "deleted"
            self._loop.call_soon_threadsafe(self._schedule_flush)


# ── Background watcher lifecycle ──────────────────────────────────────


class FilesystemWatcherService:
    """Manages watchdog observers for all enabled WatchedDirectories."""

    def __init__(self, app):
        self._app = app
        self._observer: Optional[Observer] = None
        self._watches: dict[str, any] = {}  # wd_id → watch handle

    async def start(self):
        """Start watching all enabled directories. Call from lifespan startup."""
        self._observer = Observer()
        self._observer.daemon = True

        dirs = WatchedDirectories.get_all()
        loop = asyncio.get_running_loop()

        for wd in dirs:
            if not wd.enabled or not os.path.isdir(wd.path):
                if not os.path.isdir(wd.path):
                    log.warning(f"Watched path does not exist: {wd.path}")
                continue

            handler = DebouncedHandler(
                loop=loop,
                callback=lambda batch, _wd=wd: self._handle_batch(_wd, batch),
            )
            watch = self._observer.schedule(handler, wd.path, recursive=True)
            self._watches[wd.id] = watch
            log.info(f"Watching: {wd.path} (id={wd.id})")

        self._observer.start()
        log.info(f"Filesystem watcher started with {len(self._watches)} directories")

        # Run initial scan for all watched directories
        for wd in dirs:
            if wd.enabled and os.path.isdir(wd.path):
                await self._initial_scan(wd)

    async def stop(self):
        """Stop all watchers. Call from lifespan shutdown."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._watches.clear()
            log.info("Filesystem watcher stopped")

    async def _initial_scan(self, wd: WatchedDirectoryModel):
        """Scan a directory and sync any files not yet in the knowledge base."""
        extensions = parse_csv_set(wd.extensions)
        exclude = parse_csv_set(wd.exclude_patterns)
        files = discover_files(wd.path, extensions, exclude)
        log.info(f"Initial scan of {wd.path}: found {len(files)} files")

        for fpath in files:
            try:
                await self._sync_file(wd, fpath)
            except Exception as e:
                log.error(f"Error syncing {fpath}: {e}")

        WatchedDirectories.set_last_scan(wd.id)

    async def _handle_batch(self, wd: WatchedDirectoryModel, batch: dict[str, str]):
        """Handle a debounced batch of filesystem events."""
        extensions = parse_csv_set(wd.extensions)
        exclude = parse_csv_set(wd.exclude_patterns)

        for fpath, event_type in batch.items():
            rel = os.path.relpath(fpath, wd.path)
            if not should_include_file(rel, extensions, exclude):
                continue

            try:
                if event_type == "deleted":
                    await self._delete_file(wd, fpath)
                else:
                    await self._sync_file(wd, fpath)
            except Exception as e:
                log.error(f"Error handling {event_type} for {fpath}: {e}")

    async def _sync_file(self, wd: WatchedDirectoryModel, fpath: str):
        """Upload/update a single file into the knowledge base via the existing pipeline."""
        # This will be wired to the retrieval pipeline in Task 5
        log.info(f"Sync file: {fpath} → KB {wd.knowledge_id}")

    async def _delete_file(self, wd: WatchedDirectoryModel, fpath: str):
        """Remove a file's vectors from the knowledge base."""
        log.info(f"Delete file vectors: {fpath} from KB {wd.knowledge_id}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest open_webui/test/apps/webui/services/test_filesystem_watcher.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Install watchdog dependency**

```bash
cd backend && source .venv/bin/activate && uv pip install watchdog
echo "watchdog" >> requirements.txt
```

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/services/ backend/open_webui/test/apps/webui/services/ backend/requirements.txt
git commit -m "feat: add filesystem watcher service with debounced events"
```

---

### Task 4: REST API Router

**Files:**
- Create: `backend/open_webui/routers/filesystem.py`
- Modify: `backend/open_webui/main.py` (add router registration + lifespan hook)

- [ ] **Step 1: Create the router**

Create `backend/open_webui/routers/filesystem.py`:

```python
import os
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional

from open_webui.models.filesystem import (
    WatchedDirectories,
    WatchedDirectoryForm,
    WatchedDirectoryModel,
)
from open_webui.utils.auth import get_admin_user

log = logging.getLogger(__name__)

router = APIRouter()


class WatchedDirectoryResponse(BaseModel):
    id: str
    path: str
    name: str
    knowledge_id: Optional[str] = None
    extensions: Optional[str] = None
    exclude_patterns: Optional[str] = None
    enabled: bool
    last_scan_at: Optional[int] = None
    created_at: int
    updated_at: int


@router.get("/", response_model=list[WatchedDirectoryResponse])
async def list_watched_directories(user=Depends(get_admin_user)):
    return WatchedDirectories.get_all()


@router.get("/{id}", response_model=Optional[WatchedDirectoryResponse])
async def get_watched_directory(id: str, user=Depends(get_admin_user)):
    wd = WatchedDirectories.get_by_id(id)
    if not wd:
        raise HTTPException(status_code=404, detail="Watched directory not found")
    return wd


@router.post("/", response_model=WatchedDirectoryResponse)
async def create_watched_directory(
    request: Request,
    form_data: WatchedDirectoryForm,
    user=Depends(get_admin_user),
):
    # Validate path exists
    if not os.path.isdir(form_data.path):
        raise HTTPException(
            status_code=400,
            detail=f"Path does not exist or is not a directory: {form_data.path}",
        )

    wd = WatchedDirectories.insert(user_id=user.id, form_data=form_data)
    if not wd:
        raise HTTPException(status_code=400, detail="Failed to create watched directory")

    # Restart watcher to pick up new directory
    if hasattr(request.app.state, "filesystem_watcher"):
        await request.app.state.filesystem_watcher.stop()
        await request.app.state.filesystem_watcher.start()

    return wd


@router.put("/{id}", response_model=WatchedDirectoryResponse)
async def update_watched_directory(
    request: Request,
    id: str,
    form_data: WatchedDirectoryForm,
    user=Depends(get_admin_user),
):
    if not os.path.isdir(form_data.path):
        raise HTTPException(
            status_code=400,
            detail=f"Path does not exist or is not a directory: {form_data.path}",
        )

    wd = WatchedDirectories.update_by_id(id, form_data)
    if not wd:
        raise HTTPException(status_code=404, detail="Watched directory not found")

    if hasattr(request.app.state, "filesystem_watcher"):
        await request.app.state.filesystem_watcher.stop()
        await request.app.state.filesystem_watcher.start()

    return wd


@router.delete("/{id}")
async def delete_watched_directory(
    request: Request,
    id: str,
    user=Depends(get_admin_user),
):
    success = WatchedDirectories.delete_by_id(id)
    if not success:
        raise HTTPException(status_code=404, detail="Watched directory not found")

    if hasattr(request.app.state, "filesystem_watcher"):
        await request.app.state.filesystem_watcher.stop()
        await request.app.state.filesystem_watcher.start()

    return {"status": True}


@router.post("/{id}/resync")
async def resync_watched_directory(
    request: Request,
    id: str,
    user=Depends(get_admin_user),
):
    wd = WatchedDirectories.get_by_id(id)
    if not wd:
        raise HTTPException(status_code=404, detail="Watched directory not found")

    if hasattr(request.app.state, "filesystem_watcher"):
        await request.app.state.filesystem_watcher._initial_scan(wd)

    return {"status": True}
```

- [ ] **Step 2: Register router and add lifespan hook in main.py**

In `backend/open_webui/main.py`, add the import near the other router imports (around line 100):

```python
from open_webui.routers import filesystem
```

Add the router registration after the existing `app.include_router` calls (around line 1146):

```python
app.include_router(filesystem.router, prefix="/api/v1/filesystem", tags=["filesystem"])
```

In the `lifespan` function, add before the `yield` statement (around line 540):

```python
    # Start filesystem watcher
    from open_webui.services.filesystem_watcher import FilesystemWatcherService
    app.state.filesystem_watcher = FilesystemWatcherService(app)
    try:
        await app.state.filesystem_watcher.start()
    except Exception as e:
        log.warning(f"Failed to start filesystem watcher: {e}")
```

After the `yield` statement, add shutdown:

```python
    # Stop filesystem watcher
    if hasattr(app.state, "filesystem_watcher"):
        await app.state.filesystem_watcher.stop()
```

- [ ] **Step 3: Verify the server starts**

```bash
cd backend && source .venv/bin/activate && timeout 10 uvicorn open_webui.main:app --port 8081 --host 0.0.0.0 2>&1 | tail -5
```

Expected: Server starts without import errors, logs "Filesystem watcher started with 0 directories"

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/routers/filesystem.py backend/open_webui/main.py
git commit -m "feat: add filesystem REST API and wire watcher to lifespan"
```

---

### Task 5: Wire Sync Engine to Existing RAG Pipeline

**Files:**
- Modify: `backend/open_webui/services/filesystem_watcher.py` (implement `_sync_file` and `_delete_file`)

This is the critical integration task — connecting the watcher to the existing `process_file()` pipeline.

- [ ] **Step 1: Implement _sync_file and _delete_file**

Replace the stub methods in `backend/open_webui/services/filesystem_watcher.py`. Add these imports at the top:

```python
import mimetypes
import shutil
import uuid as uuid_mod

from open_webui.models.files import FileForm, Files
from open_webui.models.knowledge import KnowledgeForm, Knowledges, KnowledgeFile
from open_webui.internal.db import get_db
from open_webui.config import UPLOAD_DIR
```

Replace the `_sync_file` method:

```python
    async def _sync_file(self, wd: WatchedDirectoryModel, fpath: str):
        """Upload/update a single file into the knowledge base via the existing pipeline."""
        if not os.path.isfile(fpath):
            return

        # Ensure knowledge base exists for this watched directory
        if not wd.knowledge_id:
            kb = Knowledges.insert_new_knowledge(
                wd.user_id,
                KnowledgeForm(name=wd.name, description=f"Auto-synced from {wd.path}"),
            )
            if kb:
                WatchedDirectories.set_knowledge_id(wd.id, kb.id)
                wd = WatchedDirectories.get_by_id(wd.id)
                log.info(f"Created knowledge base '{wd.name}' (id={wd.knowledge_id})")

        file_hash = compute_file_hash(fpath)
        rel_path = os.path.relpath(fpath, wd.path)

        # Check if file already tracked with same hash (skip if unchanged)
        existing = self._find_existing_file(wd.knowledge_id, rel_path)
        if existing and existing.hash == file_hash:
            return

        # Copy file to upload dir so the pipeline can find it
        file_id = existing.id if existing else str(uuid_mod.uuid4())
        content_type = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
        dest_dir = os.path.join(UPLOAD_DIR, file_id)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, os.path.basename(fpath))
        shutil.copy2(fpath, dest_path)

        if existing:
            # Update existing file record
            Files.update_file_by_id(file_id, {"hash": file_hash})
        else:
            # Create new file record
            Files.insert_new_file(
                user_id=wd.user_id,
                form_data=FileForm(
                    id=file_id,
                    hash=file_hash,
                    filename=os.path.basename(fpath),
                    path=dest_path,
                    meta={
                        "name": os.path.basename(fpath),
                        "content_type": content_type,
                        "size": os.path.getsize(fpath),
                        "source_path": rel_path,
                        "watched_directory_id": wd.id,
                    },
                ),
            )

            # Link file to knowledge base
            self._link_file_to_kb(wd.knowledge_id, file_id, wd.user_id)

        # Trigger embedding via process_file (runs in thread pool)
        await self._embed_file(file_id, wd.knowledge_id)
        log.info(f"Synced: {rel_path} → KB {wd.knowledge_id}")

    def _find_existing_file(self, knowledge_id: str, rel_path: str):
        """Find an existing file in the KB by its source_path metadata."""
        with get_db() as db:
            from open_webui.models.files import File

            kb_file_ids = (
                db.query(KnowledgeFile.file_id)
                .filter_by(knowledge_id=knowledge_id)
                .all()
            )
            file_ids = [r[0] for r in kb_file_ids]
            if not file_ids:
                return None

            for fid in file_ids:
                f = db.query(File).filter_by(id=fid).first()
                if f and f.meta and f.meta.get("source_path") == rel_path:
                    from open_webui.models.files import FileModel
                    return FileModel.model_validate(f)
        return None

    def _link_file_to_kb(self, knowledge_id: str, file_id: str, user_id: str):
        """Add a file to a knowledge base's file list."""
        import time as _time

        with get_db() as db:
            existing = (
                db.query(KnowledgeFile)
                .filter_by(knowledge_id=knowledge_id, file_id=file_id)
                .first()
            )
            if not existing:
                kf = KnowledgeFile(
                    id=str(uuid_mod.uuid4()),
                    knowledge_id=knowledge_id,
                    file_id=file_id,
                    user_id=user_id,
                    created_at=int(_time.time()),
                    updated_at=int(_time.time()),
                )
                db.add(kf)
                db.commit()

    async def _embed_file(self, file_id: str, collection_name: str):
        """Run the existing embedding pipeline for a file."""
        from open_webui.routers.retrieval import process_file, ProcessFileForm

        try:
            # process_file is sync — run in thread pool
            loop = asyncio.get_running_loop()
            form = ProcessFileForm(
                file_id=file_id,
                collection_name=collection_name,
            )
            await loop.run_in_executor(
                None,
                lambda: process_file.__wrapped__(self._app, form),
            )
        except Exception as e:
            log.error(f"Embedding failed for file {file_id}: {e}")
```

Replace the `_delete_file` method:

```python
    async def _delete_file(self, wd: WatchedDirectoryModel, fpath: str):
        """Remove a file's vectors from the knowledge base."""
        if not wd.knowledge_id:
            return

        rel_path = os.path.relpath(fpath, wd.path)
        existing = self._find_existing_file(wd.knowledge_id, rel_path)
        if not existing:
            return

        # Delete from vector DB
        from open_webui.retrieval.vector.main import VECTOR_DB_CLIENT

        collection_name = f"file-{existing.id}"
        try:
            VECTOR_DB_CLIENT.delete_collection(collection_name=collection_name)
        except Exception as e:
            log.warning(f"Could not delete collection {collection_name}: {e}")

        # Remove KB link and file record
        with get_db() as db:
            db.query(KnowledgeFile).filter_by(
                knowledge_id=wd.knowledge_id, file_id=existing.id
            ).delete()
            db.commit()

        Files.delete_file_by_id(existing.id)
        log.info(f"Deleted: {rel_path} from KB {wd.knowledge_id}")
```

- [ ] **Step 2: Verify the server starts without errors**

```bash
cd backend && source .venv/bin/activate && timeout 10 uvicorn open_webui.main:app --port 8081 --host 0.0.0.0 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/services/filesystem_watcher.py
git commit -m "feat: wire filesystem sync to existing RAG pipeline"
```

---

### Task 6: Frontend API Client

**Files:**
- Create: `src/lib/apis/filesystem/index.ts`

- [ ] **Step 1: Create the API client**

Create `src/lib/apis/filesystem/index.ts`:

```typescript
import { WEBUI_API_BASE_URL } from '$lib/constants';

const FILESYSTEM_API_BASE_URL = `${WEBUI_API_BASE_URL}/filesystem`;

export const getWatchedDirectories = async (token: string) => {
	let error: any = null;

	const res = await fetch(`${FILESYSTEM_API_BASE_URL}/`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const createWatchedDirectory = async (
	token: string,
	payload: { path: string; name: string; extensions?: string; exclude_patterns?: string }
) => {
	let error: any = null;

	const res = await fetch(`${FILESYSTEM_API_BASE_URL}/`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(payload)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateWatchedDirectory = async (
	token: string,
	id: string,
	payload: { path: string; name: string; extensions?: string; exclude_patterns?: string }
) => {
	let error: any = null;

	const res = await fetch(`${FILESYSTEM_API_BASE_URL}/${id}`, {
		method: 'PUT',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(payload)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteWatchedDirectory = async (token: string, id: string) => {
	let error: any = null;

	const res = await fetch(`${FILESYSTEM_API_BASE_URL}/${id}`, {
		method: 'DELETE',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const resyncWatchedDirectory = async (token: string, id: string) => {
	let error: any = null;

	const res = await fetch(`${FILESYSTEM_API_BASE_URL}/${id}/resync`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
```

- [ ] **Step 2: Commit**

```bash
git add src/lib/apis/filesystem/
git commit -m "feat: add filesystem API client"
```

---

### Task 7: Admin Settings UI

**Files:**
- Create: `src/lib/components/admin/Settings/Filesystem.svelte`
- Modify: `src/lib/components/admin/Settings.svelte` (add tab)

- [ ] **Step 1: Create the Filesystem settings panel**

Create `src/lib/components/admin/Settings/Filesystem.svelte`:

```svelte
<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import { toast } from 'svelte-sonner';
	import { onMount } from 'svelte';

	import {
		getWatchedDirectories,
		createWatchedDirectory,
		deleteWatchedDirectory,
		resyncWatchedDirectory
	} from '$lib/apis/filesystem';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';

	const i18n = getI18nContext();

	export let saveHandler: Function;

	let directories: any[] | null = null;
	let newPath = '';
	let newName = '';
	let newExtensions = '.md,.txt,.pdf,.py,.ts,.js';
	let newExclude = '.git,node_modules,__pycache__,.venv';

	const loadDirectories = async () => {
		directories = await getWatchedDirectories(localStorage.token).catch((err) => {
			toast.error(`${err}`);
			return [];
		});
	};

	const addDirectory = async () => {
		if (!newPath || !newName) {
			toast.error($i18n.t('Path and name are required'));
			return;
		}

		const res = await createWatchedDirectory(localStorage.token, {
			path: newPath,
			name: newName,
			extensions: newExtensions || null,
			exclude_patterns: newExclude || null
		}).catch((err) => {
			toast.error(`${err}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Directory added'));
			newPath = '';
			newName = '';
			await loadDirectories();
		}
	};

	const removeDirectory = async (id: string) => {
		const res = await deleteWatchedDirectory(localStorage.token, id).catch((err) => {
			toast.error(`${err}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Directory removed'));
			await loadDirectories();
		}
	};

	const resyncDirectory = async (id: string) => {
		toast.info($i18n.t('Resync started...'));
		const res = await resyncWatchedDirectory(localStorage.token, id).catch((err) => {
			toast.error(`${err}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Resync complete'));
			await loadDirectories();
		}
	};

	onMount(async () => {
		await loadDirectories();
	});
</script>

<div class="flex flex-col h-full justify-between space-y-3 text-sm">
	{#if directories !== null}
		<div class="space-y-2.5 overflow-y-scroll scrollbar-hidden h-full pr-1.5">
			<div class="mb-3">
				<div class="mt-0.5 mb-2.5 text-base font-medium">
					{$i18n.t('Watched Directories')}
				</div>
				<div class="text-xs text-gray-500 dark:text-gray-400 mb-3">
					{$i18n.t('Directories are monitored for changes and automatically synced to a Knowledge Base.')}
				</div>
				<hr class="border-gray-100/30 dark:border-gray-850/30 my-2" />

				<!-- Existing directories -->
				{#if directories.length > 0}
					<div class="space-y-2 mb-4">
						{#each directories as dir}
							<div class="flex items-center justify-between gap-2 p-3 rounded-xl bg-gray-50 dark:bg-gray-850">
								<div class="flex-1 min-w-0">
									<div class="font-medium truncate">{dir.name}</div>
									<div class="text-xs text-gray-500 dark:text-gray-400 truncate">{dir.path}</div>
									{#if dir.extensions}
										<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
											{dir.extensions}
										</div>
									{/if}
									{#if dir.last_scan_at}
										<div class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
											{$i18n.t('Last scan')}: {new Date(dir.last_scan_at * 1000).toLocaleString()}
										</div>
									{/if}
								</div>
								<div class="flex items-center gap-1">
									<Tooltip content={$i18n.t('Resync')}>
										<button
											class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
											on:click={() => resyncDirectory(dir.id)}
										>
											<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
												<path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
											</svg>
										</button>
									</Tooltip>
									<Tooltip content={$i18n.t('Remove')}>
										<button
											class="p-1.5 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/20 text-red-500 transition"
											on:click={() => removeDirectory(dir.id)}
										>
											<GarbageBin className="size-4" />
										</button>
									</Tooltip>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="text-center text-gray-400 dark:text-gray-500 py-4 text-xs">
						{$i18n.t('No directories being watched.')}
					</div>
				{/if}

				<!-- Add new directory -->
				<hr class="border-gray-100/30 dark:border-gray-850/30 my-3" />
				<div class="mt-0.5 mb-2 text-sm font-medium">{$i18n.t('Add Directory')}</div>

				<div class="space-y-2">
					<div>
						<label class="text-xs font-medium mb-0.5 block" for="fs-path">{$i18n.t('Path')}</label>
						<input
							id="fs-path"
							class="w-full text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
							bind:value={newPath}
							placeholder="/home/user/documents"
						/>
					</div>
					<div>
						<label class="text-xs font-medium mb-0.5 block" for="fs-name">{$i18n.t('Name')}</label>
						<input
							id="fs-name"
							class="w-full text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
							bind:value={newName}
							placeholder="My Documents"
						/>
					</div>
					<div>
						<label class="text-xs font-medium mb-0.5 block" for="fs-ext">{$i18n.t('File Extensions (comma-separated)')}</label>
						<input
							id="fs-ext"
							class="w-full text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
							bind:value={newExtensions}
							placeholder=".md,.txt,.pdf"
						/>
					</div>
					<div>
						<label class="text-xs font-medium mb-0.5 block" for="fs-exclude">{$i18n.t('Exclude Patterns (comma-separated)')}</label>
						<input
							id="fs-exclude"
							class="w-full text-sm bg-transparent outline-hidden border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5"
							bind:value={newExclude}
							placeholder=".git,node_modules"
						/>
					</div>
					<button
						class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
						on:click={addDirectory}
					>
						<Plus className="size-3.5" />
						{$i18n.t('Add Directory')}
					</button>
				</div>
			</div>
		</div>
	{:else}
		<div class="flex justify-center py-8">
			<Spinner />
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Add the Filesystem tab to admin Settings.svelte**

In `src/lib/components/admin/Settings.svelte`, add the import:

```typescript
import Filesystem from './Settings/Filesystem.svelte';
```

Add the tab entry to the `allSettings` array (find it in the script block, add after the last entry):

```typescript
{
    id: 'filesystem',
    title: 'Filesystem',
    route: '/admin/settings/filesystem',
    keywords: 'filesystem watch directory sync vector'
}
```

Add the tab rendering in the template (find the `{#if selectedTab ===` chain, add before the last `{/if}`):

```svelte
{:else if selectedTab === 'filesystem'}
    <Filesystem
        saveHandler={() => {
            toast.success($i18n.t('Settings saved successfully!'));
        }}
    />
```

- [ ] **Step 3: Verify frontend compiles**

```bash
npm run check 2>&1 | grep -E "ERROR|COMPLETED"
```

Expected: 0 ERRORS

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/admin/Settings/Filesystem.svelte src/lib/components/admin/Settings.svelte
git commit -m "feat: add admin UI for filesystem watching"
```

---

## Self-Review Checklist

1. **Spec coverage:** Model CRUD ✓, migration ✓, watcher with debounce ✓, REST API ✓, RAG pipeline integration ✓, admin UI ✓, resync ✓, delete handling ✓
2. **Placeholder scan:** All code blocks contain complete implementations. No TBD/TODO.
3. **Type consistency:** `WatchedDirectoryForm`, `WatchedDirectoryModel`, `WatchedDirectoryResponse` used consistently across model → router → frontend. `process_file`/`ProcessFileForm` matches existing codebase signatures.
