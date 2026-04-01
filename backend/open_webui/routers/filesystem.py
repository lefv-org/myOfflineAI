import os
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
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


class BrowseResponse(BaseModel):
    path: str
    dirs: list[str]


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
