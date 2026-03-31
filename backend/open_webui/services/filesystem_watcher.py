"""Filesystem watcher service with debounced event handling.

Watches directories registered in WatchedDirectory and syncs file changes
to the RAG pipeline. Part A contains pure helpers; Part B contains the
watchdog-based service classes.
"""

import asyncio
import hashlib
import logging
import mimetypes
import os
import shutil
import time
import uuid as uuid_mod
from pathlib import Path
from typing import Optional

from starlette.datastructures import Headers
from starlette.requests import Request
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from open_webui.config import UPLOAD_DIR
from open_webui.internal.db import get_db
from open_webui.models.files import FileForm, FileModel, Files
from open_webui.models.filesystem import WatchedDirectories, WatchedDirectoryModel
from open_webui.models.knowledge import KnowledgeForm, Knowledges

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Part A: Pure helper functions
# ---------------------------------------------------------------------------


def parse_csv_set(csv_str: Optional[str]) -> set[str]:
    """Split a comma-separated string into a set, stripping whitespace."""
    if not csv_str:
        return set()
    return {s.strip() for s in csv_str.split(",") if s.strip()}


def should_include_file(
    rel_path: str, extensions: set[str], exclude: set[str]
) -> bool:
    """Decide whether a file should be included based on extension and exclusion rules."""
    parts = Path(rel_path).parts
    if any(part in exclude for part in parts):
        return False
    if not extensions:
        return True
    return Path(rel_path).suffix.lower() in extensions


def discover_files(
    root: str, extensions: set[str], exclude: set[str]
) -> list[str]:
    """Walk *root* and return absolute paths of files matching the filter rules."""
    result: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place so os.walk skips them.
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for fname in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fname), root)
            if should_include_file(rel, extensions, exclude):
                result.append(os.path.join(dirpath, fname))
    return result


def compute_file_hash(path: str) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Part B: Watchdog classes
# ---------------------------------------------------------------------------


class DebouncedHandler(FileSystemEventHandler):
    """Accumulates filesystem events and flushes them as a batch after a quiet period."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        callback,  # async callable(dict[str, str])
        debounce_sec: float = 2.0,
    ):
        super().__init__()
        self._loop = loop
        self._callback = callback
        self._debounce_sec = debounce_sec
        self._pending: dict[str, str] = {}  # path -> event_type
        self._timer = None

    # -- watchdog hooks (called from observer thread) --

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._record(event.src_path, "created")

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._record(event.src_path, "modified")

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._record(event.src_path, "deleted")

    # -- internal --

    def _record(self, path: str, event_type: str):
        self._pending[path] = event_type
        if self._timer is not None:
            self._timer.cancel()
        self._timer = self._loop.call_later(self._debounce_sec, self._flush)

    def _flush(self):
        batch = dict(self._pending)
        self._pending.clear()
        self._timer = None
        if batch:
            asyncio.run_coroutine_threadsafe(self._callback(batch), self._loop)


class FilesystemWatcherService:
    """Manages watchdog observers for all enabled WatchedDirectory entries."""

    def __init__(self, app=None):
        self._app = app
        self._observer: Optional[Observer] = None
        self._watches: list = []

    async def start(self):
        """Start watching all enabled directories."""
        directories = WatchedDirectories.get_all()
        enabled = [wd for wd in directories if wd.enabled]

        if not enabled:
            log.info("No enabled watched directories, skipping observer start.")
            return

        loop = asyncio.get_running_loop()
        self._observer = Observer()

        for wd in enabled:
            if not os.path.isdir(wd.path):
                log.warning("Watched directory does not exist: %s", wd.path)
                continue

            async def make_callback(watched_dir):
                async def cb(batch):
                    await self._handle_batch(watched_dir, batch)
                return cb

            callback = await make_callback(wd)
            handler = DebouncedHandler(loop, callback)
            watch = self._observer.schedule(handler, wd.path, recursive=True)
            self._watches.append(watch)
            log.info("Watching directory: %s", wd.path)

        self._observer.start()
        log.info("Filesystem observer started with %d directories.", len(self._watches))

        # Run initial scan for each directory.
        for wd in enabled:
            if os.path.isdir(wd.path):
                await self._initial_scan(wd)

    async def stop(self):
        """Stop the observer and clean up."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._watches.clear()
            self._observer = None
            log.info("Filesystem observer stopped.")

    async def _initial_scan(self, wd: WatchedDirectoryModel):
        """Discover existing files and sync them."""
        extensions = parse_csv_set(wd.extensions)
        exclude = parse_csv_set(wd.exclude_patterns)
        files = discover_files(wd.path, extensions, exclude)
        log.info("Initial scan of '%s': found %d files.", wd.path, len(files))
        for fpath in files:
            await self._sync_file(wd, fpath)
        WatchedDirectories.set_last_scan(wd.id)

    async def _handle_batch(
        self, wd: WatchedDirectoryModel, batch: dict[str, str]
    ):
        """Process a batch of debounced events."""
        extensions = parse_csv_set(wd.extensions)
        exclude = parse_csv_set(wd.exclude_patterns)

        for fpath, event_type in batch.items():
            rel = os.path.relpath(fpath, wd.path)
            if not should_include_file(rel, extensions, exclude):
                continue
            if event_type == "deleted":
                await self._delete_file(wd, fpath)
            else:
                await self._sync_file(wd, fpath)

    def _mock_request(self) -> Request:
        """Build a mock Starlette Request backed by the real FastAPI app state."""
        return Request(
            {
                "type": "http",
                "asgi.version": "3.0",
                "asgi.spec_version": "2.0",
                "method": "GET",
                "path": "/internal",
                "query_string": b"",
                "headers": Headers({}).raw,
                "client": ("127.0.0.1", 12345),
                "server": ("127.0.0.1", 80),
                "scheme": "http",
                "app": self._app,
            }
        )

    async def _sync_file(self, wd: WatchedDirectoryModel, fpath: str):
        """Sync a single file into the knowledge base via the RAG pipeline."""
        if not os.path.isfile(fpath):
            return

        # Ensure a knowledge base exists for this watched directory.
        if not wd.knowledge_id:
            kb = Knowledges.insert_new_knowledge(
                wd.user_id,
                KnowledgeForm(
                    name=wd.name,
                    description=f"Auto-synced from {wd.path}",
                ),
            )
            if kb:
                WatchedDirectories.set_knowledge_id(wd.id, kb.id)
                wd = WatchedDirectories.get_by_id(wd.id)
                log.info("Created knowledge base '%s' (id=%s)", wd.name, wd.knowledge_id)

        rel_path = os.path.relpath(fpath, wd.path)
        file_hash = compute_file_hash(fpath)

        # Skip unchanged files.
        existing = self._find_existing_file(wd.knowledge_id, rel_path)
        if existing and existing.hash == file_hash:
            return

        # Copy into upload dir so the loader can access it.
        file_id = existing.id if existing else str(uuid_mod.uuid4())
        content_type = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
        dest_dir = Path(UPLOAD_DIR) / file_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = str(dest_dir / os.path.basename(fpath))
        shutil.copy2(fpath, dest_path)

        if not existing:
            Files.insert_new_file(
                user_id=wd.user_id,
                form_data=FileForm(
                    id=file_id,
                    hash=file_hash,
                    filename=os.path.basename(fpath),
                    path=dest_path,
                    data={},
                    meta={
                        "name": os.path.basename(fpath),
                        "content_type": content_type,
                        "size": os.path.getsize(fpath),
                        "source_path": rel_path,
                        "watched_directory_id": wd.id,
                    },
                ),
            )
            Knowledges.add_file_to_knowledge_by_id(wd.knowledge_id, file_id, wd.user_id)

        # Process and embed the file via the existing pipeline.
        try:
            await self._process_and_embed(file_id, wd)
            log.info("Synced: %s -> KB %s", rel_path, wd.knowledge_id)
        except Exception as e:
            log.error("Embedding failed for %s: %s", rel_path, e)

    async def _delete_file(self, wd: WatchedDirectoryModel, fpath: str):
        """Remove a file's vectors and records from the knowledge base."""
        if not wd.knowledge_id:
            return

        rel_path = os.path.relpath(fpath, wd.path)
        existing = self._find_existing_file(wd.knowledge_id, rel_path)
        if not existing:
            return

        from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT

        try:
            VECTOR_DB_CLIENT.delete_collection(collection_name=f"file-{existing.id}")
        except Exception as e:
            log.warning("Could not delete vector collection for %s: %s", existing.id, e)

        Knowledges.remove_file_from_knowledge_by_id(wd.knowledge_id, existing.id)
        Files.delete_file_by_id(existing.id)
        log.info("Deleted: %s from KB %s", rel_path, wd.knowledge_id)

    def _find_existing_file(self, knowledge_id: str, rel_path: str) -> Optional[FileModel]:
        """Find a file already linked to the KB by its source_path metadata."""
        if not knowledge_id:
            return None

        with get_db() as db:
            from open_webui.models.knowledge import KnowledgeFile
            from open_webui.models.files import File

            rows = (
                db.query(KnowledgeFile.file_id)
                .filter_by(knowledge_id=knowledge_id)
                .all()
            )
            for (fid,) in rows:
                f = db.query(File).filter_by(id=fid).first()
                if f and f.meta and f.meta.get("source_path") == rel_path:
                    return FileModel.model_validate(f)
        return None

    async def _process_and_embed(self, file_id: str, wd: WatchedDirectoryModel):
        """Load, chunk, embed, and store a file using the existing RAG pipeline."""
        from open_webui.retrieval.loaders.main import Loader
        from open_webui.retrieval.vector.utils import filter_metadata
        from open_webui.routers.retrieval import save_docs_to_vector_db
        from open_webui.utils.misc import calculate_sha256_string
        from langchain_core.documents import Document

        file = Files.get_file_by_id(file_id)
        if not file or not file.path:
            return

        request = self._mock_request()
        config = request.app.state.config

        # Load document content
        loader = Loader(
            engine=config.CONTENT_EXTRACTION_ENGINE,
            TIKA_SERVER_URL=config.TIKA_SERVER_URL,
            PDF_EXTRACT_IMAGES=config.PDF_EXTRACT_IMAGES,
            PDF_LOADER_MODE=config.PDF_LOADER_MODE,
        )
        docs = loader.load(file.filename, file.meta.get("content_type", ""), file.path)
        docs = [
            Document(
                page_content=doc.page_content,
                metadata={
                    **filter_metadata(doc.metadata),
                    "name": file.filename,
                    "created_by": file.user_id,
                    "file_id": file.id,
                    "source": file.filename,
                },
            )
            for doc in docs
        ]

        text_content = " ".join(doc.page_content for doc in docs)
        Files.update_file_data_by_id(file.id, {"content": text_content})
        content_hash = calculate_sha256_string(text_content)

        collection_name = wd.knowledge_id

        # Run embedding in thread pool (save_docs_to_vector_db is sync + CPU-bound)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: save_docs_to_vector_db(
                request,
                docs=docs,
                collection_name=collection_name,
                metadata={
                    "file_id": file.id,
                    "name": file.filename,
                    "hash": content_hash,
                },
                add=True,
            ),
        )

        # Update file status
        Files.update_file_metadata_by_id(file.id, {"collection_name": collection_name})
        Files.update_file_data_by_id(file.id, {"status": "completed"})
        Files.update_file_hash_by_id(file.id, content_hash)
