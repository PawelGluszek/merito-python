"""Tests for core/analyzer.py."""

import pytest
from pathlib import Path

from core.analyzer import DuplicateGroup, find_duplicates, format_report


@pytest.fixture
def sample_hash_map(tmp_path):
    """Create files and a hash map with known duplicates."""
    content_a = b"duplicate content A"
    content_b = b"duplicate content B"
    content_c = b"unique content C"

    paths = {
        "a1.bin": content_a,
        "a2.bin": content_a,
        "a3.bin": content_a,
        "b1.bin": content_b,
        "b2.bin": content_b,
        "c.bin": content_c,
    }
    hash_map = {}
    for name, content in paths.items():
        path = tmp_path / name
        path.write_bytes(content)
        import hashlib
        hash_map[path] = hashlib.sha256(content).hexdigest()

    return hash_map


class TestDuplicateGroup:
    def test_wasted_bytes(self):
        group = DuplicateGroup(
            hash_digest="abc123",
            size=1000,
            paths=[Path("a"), Path("b"), Path("c")],
        )
        assert group.wasted_bytes == 2000

    def test_len(self):
        group = DuplicateGroup(
            hash_digest="abc123",
            size=100,
            paths=[Path("x"), Path("y")],
        )
        assert len(group) == 2


class TestFindDuplicates:
    def test_finds_duplicate_groups(self, sample_hash_map):
        groups = find_duplicates(sample_hash_map)
        assert len(groups) == 2

    def test_excludes_unique_files(self, sample_hash_map):
        groups = find_duplicates(sample_hash_map)
        all_paths = [p for g in groups for p in g.paths]
        unique_names = {p.name for p in all_paths}
        assert "c.bin" not in unique_names

    def test_sorted_by_wasted_bytes_descending(self, sample_hash_map):
        groups = find_duplicates(sample_hash_map)
        wasted = [g.wasted_bytes for g in groups]
        assert wasted == sorted(wasted, reverse=True)

    def test_no_duplicates_returns_empty(self, tmp_path):
        (tmp_path / "a.bin").write_bytes(b"unique a")
        (tmp_path / "b.bin").write_bytes(b"unique b")
        import hashlib
        hash_map = {
            tmp_path / "a.bin": hashlib.sha256(b"unique a").hexdigest(),
            tmp_path / "b.bin": hashlib.sha256(b"unique b").hexdigest(),
        }
        groups = find_duplicates(hash_map)
        assert groups == []


class TestFormatReport:
    def test_no_duplicates_message(self):
        assert format_report([]) == "No duplicates found."

    def test_contains_summary(self, sample_hash_map):
        groups = find_duplicates(sample_hash_map)
        report = format_report(groups)
        assert "Summary:" in report
        assert "duplicate groups" in report
        assert "wasted space" in report

    def test_contains_group_info(self, sample_hash_map):
        groups = find_duplicates(sample_hash_map)
        report = format_report(groups)
        assert "Group 1" in report
        assert "Group 2" in report
