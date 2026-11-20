"""Tests for core/scanner.py."""

import pytest
from pathlib import Path

from core.scanner import ChunkReader, FileScanner, walk_files


@pytest.fixture
def sample_dir(tmp_path):
    """Create a sample directory structure for testing."""
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.dat").write_bytes(b"\x00" * 100)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("world")
    (sub / "d.log").write_text("log entry")
    return tmp_path


@pytest.fixture
def binary_file(tmp_path):
    """Create a binary file with known content."""
    path = tmp_path / "test.bin"
    path.write_bytes(b"A" * 100)
    return path


class TestChunkReader:
    def test_reads_all_content(self, binary_file):
        content = b"".join(ChunkReader(binary_file, chunk_size=30))
        assert content == b"A" * 100

    def test_chunk_sizes(self, binary_file):
        chunks = list(ChunkReader(binary_file, chunk_size=30))
        assert len(chunks) == 4
        assert len(chunks[0]) == 30
        assert len(chunks[-1]) == 10

    def test_empty_file(self, tmp_path):
        empty = tmp_path / "empty.bin"
        empty.write_bytes(b"")
        chunks = list(ChunkReader(empty))
        assert chunks == []

    def test_is_iterable(self, binary_file):
        reader = ChunkReader(binary_file)
        it = iter(reader)
        assert it is reader


class TestWalkFiles:
    def test_finds_all_files(self, sample_dir):
        files = list(walk_files(sample_dir))
        names = {f.name for f in files}
        assert names == {"a.txt", "b.dat", "c.txt", "d.log"}

    def test_yields_paths(self, sample_dir):
        for f in walk_files(sample_dir):
            assert isinstance(f, Path)
            assert f.is_file()

    def test_empty_directory(self, tmp_path):
        assert list(walk_files(tmp_path)) == []


class TestFileScanner:
    def test_scan_all_files(self, sample_dir):
        scanner = FileScanner(sample_dir)
        scanner.min_size = 0
        files = list(scanner.scan())
        assert len(files) == 4

    def test_min_size_filter(self, sample_dir):
        scanner = FileScanner(sample_dir)
        scanner.min_size = 50
        files = list(scanner.scan())
        names = {f.name for f in files}
        assert "b.dat" in names
        assert "a.txt" not in names

    def test_max_size_filter(self, sample_dir):
        scanner = FileScanner(sample_dir)
        scanner.min_size = 0
        scanner.max_size = 10
        files = list(scanner.scan())
        names = {f.name for f in files}
        assert "a.txt" in names
        assert "b.dat" not in names

    def test_min_size_validation(self):
        scanner = FileScanner(".")
        with pytest.raises(ValueError):
            scanner.min_size = -1

    def test_max_size_validation(self):
        scanner = FileScanner(".")
        with pytest.raises(ValueError):
            scanner.max_size = -1

    def test_with_size_range_classmethod(self, sample_dir):
        scanner = FileScanner.with_size_range(sample_dir, 0, 10)
        assert scanner.min_size == 0
        assert scanner.max_size == 10

    def test_human_readable_size(self):
        assert FileScanner.human_readable_size(500) == "500.0 B"
        assert FileScanner.human_readable_size(1024) == "1.0 KB"
        assert FileScanner.human_readable_size(1024 * 1024) == "1.0 MB"

    def test_requires_config_raises_on_missing_dir(self):
        scanner = FileScanner("/nonexistent/path/xyz")
        with pytest.raises(FileNotFoundError):
            list(scanner.scan())

    def test_exclude(self, sample_dir):
        scanner = FileScanner(sample_dir)
        scanner.min_size = 0
        scanner.exclude("a.txt")
        files = list(scanner.scan())
        names = {f.name for f in files}
        assert "a.txt" not in names

    def test_pattern_filter(self, sample_dir):
        from core.patterns import build_glob_filter
        scanner = FileScanner(sample_dir)
        scanner.min_size = 0
        txt_filter = build_glob_filter(["*.txt"])
        files = list(scanner.scan(txt_filter))
        assert all(f.suffix == ".txt" for f in files)
