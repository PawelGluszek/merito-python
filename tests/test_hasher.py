"""Tests for core/hasher.py."""

import hashlib
import pytest
from pathlib import Path

from core.hasher import (
    find_duplicate_candidates,
    group_by_size,
    hash_file,
    hash_files_sequential,
    hash_files_threaded,
)


@pytest.fixture
def duplicate_files(tmp_path):
    """Create files with known duplicate content."""
    content_a = b"content of file A" * 100
    content_b = b"content of file B" * 100

    (tmp_path / "a1.bin").write_bytes(content_a)
    (tmp_path / "a2.bin").write_bytes(content_a)
    (tmp_path / "b1.bin").write_bytes(content_b)
    (tmp_path / "unique.bin").write_bytes(b"unique content")
    return tmp_path


class TestHashFile:
    def test_produces_correct_hash(self, tmp_path):
        content = b"test content"
        path = tmp_path / "test.bin"
        path.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        assert hash_file(path) == expected

    def test_different_algorithms(self, tmp_path):
        path = tmp_path / "test.bin"
        path.write_bytes(b"data")

        sha256 = hash_file(path, "sha256")
        md5 = hash_file(path, "md5")
        assert sha256 != md5
        assert len(md5) == 32
        assert len(sha256) == 64


class TestHashFilesThreaded:
    def test_hashes_multiple_files(self, duplicate_files):
        paths = list(duplicate_files.glob("*.bin"))
        result = hash_files_threaded(paths)
        assert len(result) == 4

    def test_duplicates_have_same_hash(self, duplicate_files):
        paths = list(duplicate_files.glob("*.bin"))
        result = hash_files_threaded(paths)
        a1_hash = result[duplicate_files / "a1.bin"]
        a2_hash = result[duplicate_files / "a2.bin"]
        assert a1_hash == a2_hash


class TestHashFilesSequential:
    def test_matches_threaded_results(self, duplicate_files):
        paths = list(duplicate_files.glob("*.bin"))
        sequential = hash_files_sequential(paths)
        threaded = hash_files_threaded(paths)
        for path in paths:
            assert sequential[path] == threaded[path]


class TestGroupBySize:
    def test_groups_same_size_files(self, duplicate_files):
        paths = list(duplicate_files.glob("*.bin"))
        groups = group_by_size(paths)
        sizes_with_multiple = [s for s, files in groups.items() if len(files) >= 2]
        assert len(sizes_with_multiple) >= 1

    def test_excludes_singletons(self, duplicate_files):
        paths = list(duplicate_files.glob("*.bin"))
        groups = group_by_size(paths)
        for files in groups.values():
            assert len(files) >= 2


class TestFindDuplicateCandidates:
    def test_returns_groups(self, duplicate_files):
        paths = list(duplicate_files.glob("*.bin"))
        groups = find_duplicate_candidates(paths)
        assert isinstance(groups, list)
        assert all(isinstance(g, list) for g in groups)
