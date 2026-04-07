import os
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import func, case

from open_webui.models.filesystem import (
    WatchedDirectories,
    WatchedDirectoryForm,
    WatchedDirectoryModel,
)
from open_webui.utils.auth import get_admin_user
from open_webui.internal.db import get_db
from open_webui.models.files import File
from open_webui.models.knowledge import KnowledgeFile
from open_webui.env import DATA_DIR

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


class BrowseResponse(BaseModel):
    path: str
    dirs: list[str]


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


@router.get("/browse")
async def browse_directories(
    path: str = os.path.expanduser("~"),
    user=Depends(get_admin_user),
) -> BrowseResponse:
    """List subdirectories at the given path for the folder picker."""
    resolved = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(resolved):
        raise HTTPException(status_code=400, detail=f"Not a directory: {resolved}")

    dirs = []
    try:
        for entry in sorted(os.scandir(resolved), key=lambda e: e.name.lower()):
            if entry.is_dir() and not entry.name.startswith("."):
                dirs.append(entry.name)
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {resolved}")

    return BrowseResponse(path=resolved, dirs=dirs)


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
    from open_webui.models.knowledge import KnowledgeFile as KFModel
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
