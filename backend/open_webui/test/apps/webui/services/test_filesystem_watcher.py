"""Tests for filesystem watcher pure helper functions."""

import hashlib
import os
import tempfile

import pytest

from open_webui.services.filesystem_watcher import (
    compute_file_hash,
    discover_files,
    parse_csv_set,
    should_include_file,
)


class TestShouldIncludeFile:
    def test_with_extensions_match(self):
        assert should_include_file("docs/readme.md", {".md", ".txt"}, set()) is True

    def test_with_extensions_no_match(self):
        assert should_include_file("docs/image.png", {".md", ".txt"}, set()) is False

    def test_with_extensions_case_insensitive(self):
        assert should_include_file("notes/FILE.MD", {".md"}, set()) is True

    def test_no_extensions_includes_all(self):
        assert should_include_file("anything/file.xyz", set(), set()) is True

    def test_excludes_directory(self):
        assert should_include_file(".git/config", set(), {".git"}) is False

    def test_excludes_nested_directory(self):
        assert (
            should_include_file("src/.git/objects/abc", {".txt"}, {".git"}) is False
        )

    def test_excludes_node_modules(self):
        assert (
            should_include_file(
                "project/node_modules/pkg/index.js", {".js"}, {"node_modules"}
            )
            is False
        )

    def test_not_excluded_when_no_match(self):
        assert should_include_file("src/main.py", {".py"}, {".git", "__pycache__"}) is True


class TestDiscoverFiles:
    def test_discovers_matching_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            open(os.path.join(tmpdir, "b.md"), "w").close()
            open(os.path.join(tmpdir, "c.py"), "w").close()

            result = discover_files(tmpdir, {".txt", ".md"}, set())
            basenames = sorted(os.path.basename(p) for p in result)
            assert basenames == ["a.txt", "b.md"]

    def test_discovers_all_when_no_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            open(os.path.join(tmpdir, "b.bin"), "w").close()

            result = discover_files(tmpdir, set(), set())
            assert len(result) == 2

    def test_excludes_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            excluded = os.path.join(tmpdir, ".git")
            os.makedirs(excluded)
            open(os.path.join(excluded, "config"), "w").close()
            open(os.path.join(tmpdir, "readme.md"), "w").close()

            result = discover_files(tmpdir, set(), {".git"})
            basenames = [os.path.basename(p) for p in result]
            assert "config" not in basenames
            assert "readme.md" in basenames

    def test_returns_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "f.txt"), "w").close()
            result = discover_files(tmpdir, set(), set())
            assert all(os.path.isabs(p) for p in result)

    def test_recursive_discovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = os.path.join(tmpdir, "sub")
            os.makedirs(sub)
            open(os.path.join(sub, "nested.txt"), "w").close()

            result = discover_files(tmpdir, {".txt"}, set())
            assert len(result) == 1
            assert result[0].endswith("nested.txt")


class TestComputeFileHash:
    def test_hash_known_content(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"hello world")
            f.flush()
            path = f.name

        try:
            expected = hashlib.sha256(b"hello world").hexdigest()
            assert compute_file_hash(path) == expected
        finally:
            os.unlink(path)

    def test_hash_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            path = f.name

        try:
            expected = hashlib.sha256(b"").hexdigest()
            assert compute_file_hash(path) == expected
        finally:
            os.unlink(path)


class TestParseCsvSet:
    def test_basic(self):
        assert parse_csv_set(".md,.txt,.py") == {".md", ".txt", ".py"}

    def test_with_whitespace(self):
        assert parse_csv_set(" .md , .txt , .py ") == {".md", ".txt", ".py"}

    def test_empty_string(self):
        assert parse_csv_set("") == set()

    def test_none(self):
        assert parse_csv_set(None) == set()

    def test_filters_empty_entries(self):
        assert parse_csv_set(".md,,,.txt,") == {".md", ".txt"}
