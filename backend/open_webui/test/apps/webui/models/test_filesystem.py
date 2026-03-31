import pytest

from open_webui.internal.db import engine
from open_webui.models.filesystem import (
    WatchedDirectory,
    WatchedDirectories,
    WatchedDirectoryForm,
    WatchedDirectoryModel,
)


@pytest.fixture(scope="module", autouse=True)
def create_table():
    WatchedDirectory.__table__.create(bind=engine, checkfirst=True)
    yield
    WatchedDirectory.__table__.drop(bind=engine, checkfirst=True)


class TestWatchedDirectories:
    """Unit tests for WatchedDirectoriesTable CRUD operations."""

    def test_insert_new_watched_directory(self):
        form = WatchedDirectoryForm(
            path="/tmp/test_watched",
            name="Test Dir",
            extensions=".md,.txt",
            exclude_patterns=".git,node_modules",
            enabled=True,
        )
        result = WatchedDirectories.insert("test-user-1", form)
        assert result is not None
        assert isinstance(result, WatchedDirectoryModel)
        assert result.path == "/tmp/test_watched"
        assert result.name == "Test Dir"
        assert result.user_id == "test-user-1"
        assert result.extensions == ".md,.txt"
        assert result.exclude_patterns == ".git,node_modules"
        assert result.enabled is True
        assert result.knowledge_id is None
        assert result.last_scan_at is None
        assert result.created_at > 0
        assert result.updated_at > 0

        # cleanup
        WatchedDirectories.delete_by_id(result.id)

    def test_get_all_watched_directories(self):
        form_a = WatchedDirectoryForm(path="/tmp/test_a", name="Dir A")
        form_b = WatchedDirectoryForm(path="/tmp/test_b", name="Dir B")
        a = WatchedDirectories.insert("test-user-1", form_a)
        b = WatchedDirectories.insert("test-user-1", form_b)

        try:
            all_dirs = WatchedDirectories.get_all()
            ids = [d.id for d in all_dirs]
            assert a.id in ids
            assert b.id in ids
        finally:
            WatchedDirectories.delete_by_id(a.id)
            WatchedDirectories.delete_by_id(b.id)

    def test_get_by_id(self):
        form = WatchedDirectoryForm(path="/tmp/test_get", name="Get Dir")
        created = WatchedDirectories.insert("test-user-1", form)

        try:
            fetched = WatchedDirectories.get_by_id(created.id)
            assert fetched is not None
            assert fetched.id == created.id
            assert fetched.path == "/tmp/test_get"

            # non-existent
            assert WatchedDirectories.get_by_id("nonexistent-id") is None
        finally:
            WatchedDirectories.delete_by_id(created.id)

    def test_update_watched_directory(self):
        form = WatchedDirectoryForm(path="/tmp/test_update", name="Original")
        created = WatchedDirectories.insert("test-user-1", form)

        try:
            update_form = WatchedDirectoryForm(
                path="/tmp/test_update_new",
                name="Updated",
                extensions=".pdf",
                exclude_patterns="__pycache__",
                enabled=False,
            )
            updated = WatchedDirectories.update_by_id(created.id, update_form)
            assert updated is not None
            assert updated.name == "Updated"
            assert updated.path == "/tmp/test_update_new"
            assert updated.extensions == ".pdf"
            assert updated.exclude_patterns == "__pycache__"
            assert updated.enabled is False
            assert updated.updated_at >= created.updated_at
        finally:
            WatchedDirectories.delete_by_id(created.id)

    def test_delete_watched_directory(self):
        form = WatchedDirectoryForm(path="/tmp/test_delete", name="Delete Me")
        created = WatchedDirectories.insert("test-user-1", form)

        assert WatchedDirectories.delete_by_id(created.id) is True
        assert WatchedDirectories.get_by_id(created.id) is None
        # deleting non-existent should return False
        assert WatchedDirectories.delete_by_id(created.id) is False

    def test_set_knowledge_id(self):
        form = WatchedDirectoryForm(path="/tmp/test_kb", name="KB Dir")
        created = WatchedDirectories.insert("test-user-1", form)

        try:
            WatchedDirectories.set_knowledge_id(created.id, "kb-123")
            fetched = WatchedDirectories.get_by_id(created.id)
            assert fetched.knowledge_id == "kb-123"
        finally:
            WatchedDirectories.delete_by_id(created.id)

    def test_set_last_scan(self):
        form = WatchedDirectoryForm(path="/tmp/test_scan", name="Scan Dir")
        created = WatchedDirectories.insert("test-user-1", form)
        assert created.last_scan_at is None

        try:
            WatchedDirectories.set_last_scan(created.id)
            fetched = WatchedDirectories.get_by_id(created.id)
            assert fetched.last_scan_at is not None
            assert fetched.last_scan_at > 0
        finally:
            WatchedDirectories.delete_by_id(created.id)
