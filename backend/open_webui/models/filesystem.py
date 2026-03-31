import time
import uuid
from typing import Optional

from open_webui.internal.db import Base, get_db
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Text


####################
# WatchedDirectory DB Schema
####################


class WatchedDirectory(Base):
    __tablename__ = "watched_directory"

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text, nullable=False)
    path = Column(Text, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    knowledge_id = Column(Text, nullable=True)
    extensions = Column(Text, nullable=True)
    exclude_patterns = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
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


####################
# Forms
####################


class WatchedDirectoryForm(BaseModel):
    path: str
    name: str
    extensions: Optional[str] = None
    exclude_patterns: Optional[str] = None
    enabled: bool = True


####################
# CRUD
####################


class WatchedDirectoriesTable:
    def insert(
        self, user_id: str, form_data: WatchedDirectoryForm
    ) -> Optional[WatchedDirectoryModel]:
        with get_db() as db:
            model = WatchedDirectoryModel(
                **{
                    **form_data.model_dump(),
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "knowledge_id": None,
                    "last_scan_at": None,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )
            try:
                result = WatchedDirectory(**model.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return WatchedDirectoryModel.model_validate(result) if result else None
            except Exception:
                return None

    def get_all(self) -> list[WatchedDirectoryModel]:
        with get_db() as db:
            try:
                rows = db.query(WatchedDirectory).order_by(WatchedDirectory.updated_at.desc()).all()
                return [WatchedDirectoryModel.model_validate(r) for r in rows]
            except Exception:
                return []

    def get_by_id(self, id: str) -> Optional[WatchedDirectoryModel]:
        with get_db() as db:
            try:
                row = db.get(WatchedDirectory, id)
                return WatchedDirectoryModel.model_validate(row) if row else None
            except Exception:
                return None

    def update_by_id(
        self, id: str, form_data: WatchedDirectoryForm
    ) -> Optional[WatchedDirectoryModel]:
        with get_db() as db:
            try:
                db.query(WatchedDirectory).filter_by(id=id).update(
                    {
                        **form_data.model_dump(),
                        "updated_at": int(time.time()),
                    }
                )
                db.commit()
                return self.get_by_id(id)
            except Exception:
                return None

    def set_knowledge_id(self, id: str, knowledge_id: str) -> None:
        with get_db() as db:
            db.query(WatchedDirectory).filter_by(id=id).update(
                {"knowledge_id": knowledge_id, "updated_at": int(time.time())}
            )
            db.commit()

    def set_last_scan(self, id: str) -> None:
        with get_db() as db:
            db.query(WatchedDirectory).filter_by(id=id).update(
                {"last_scan_at": int(time.time()), "updated_at": int(time.time())}
            )
            db.commit()

    def delete_by_id(self, id: str) -> bool:
        with get_db() as db:
            try:
                count = db.query(WatchedDirectory).filter_by(id=id).delete()
                db.commit()
                return count > 0
            except Exception:
                return False


WatchedDirectories = WatchedDirectoriesTable()
