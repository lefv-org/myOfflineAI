"""Filesystem watcher service with debounced event handling.

Watches directories registered in WatchedDirectory and syncs file changes
to the RAG pipeline. Part A contains pure helpers; Part B contains the
watchdog-based service classes (wired in Task 5).
"""

import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from open_webui.models.filesystem import WatchedDirectories, WatchedDirectoryModel

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

    async def _sync_file(self, wd: WatchedDirectoryModel, fpath: str):
        """Stub: sync a file into the RAG pipeline. Implemented in Task 5."""
        log.info("Sync file: %s", fpath)

    async def _delete_file(self, wd: WatchedDirectoryModel, fpath: str):
        """Stub: remove a file from the RAG pipeline. Implemented in Task 5."""
        log.info("Delete file: %s", fpath)
