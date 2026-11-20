"""Tests for core/patterns.py."""

import pytest

from core.patterns import (
    build_glob_filter,
    extract_extensions,
    parse_filename,
    parse_size,
)


class TestParseSize:
    def test_bytes(self):
        assert parse_size("100B") == 100

    def test_kilobytes(self):
        assert parse_size("10KB") == 10 * 1024

    def test_megabytes(self):
        assert parse_size("5 MB") == 5 * 1024 * 1024

    def test_gigabytes(self):
        assert parse_size("1GB") == 1024 ** 3

    def test_case_insensitive(self):
        assert parse_size("10kb") == parse_size("10KB")

    def test_decimal(self):
        assert parse_size("1.5MB") == int(1.5 * 1024 * 1024)

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_size("not a size")


class TestParseFilename:
    def test_simple_name(self):
        result = parse_filename("report.pdf")
        assert result["basename"] == "report"
        assert result["ext"] == ".pdf"
        assert result["copy"] is None

    def test_name_with_copy_number(self):
        result = parse_filename("report (2).pdf")
        assert result["basename"] == "report"
        assert result["copy"] == "2"
        assert result["ext"] == ".pdf"

    def test_no_extension(self):
        result = parse_filename("Makefile")
        assert result["basename"] == "Makefile"
        assert result["ext"] is None

    def test_dotfile(self):
        result = parse_filename(".gitignore")
        assert result["basename"] == ".gitignore"
        assert result["ext"] is None


class TestBuildGlobFilter:
    def test_star_pattern(self):
        f = build_glob_filter(["*.txt"])
        assert f("readme.txt") is True
        assert f("readme.pdf") is False

    def test_question_mark(self):
        f = build_glob_filter(["file?.dat"])
        assert f("file1.dat") is True
        assert f("file12.dat") is False

    def test_multiple_patterns(self):
        f = build_glob_filter(["*.jpg", "*.png"])
        assert f("photo.jpg") is True
        assert f("image.png") is True
        assert f("doc.pdf") is False

    def test_none_for_empty_list(self):
        assert build_glob_filter([]) is None

    def test_character_class(self):
        f = build_glob_filter(["file[123].txt"])
        assert f("file1.txt") is True
        assert f("file4.txt") is False


class TestExtractExtensions:
    def test_extracts_unique(self):
        result = extract_extensions(["a.py", "b.txt", "c.py", "readme"])
        assert result == [".py", ".txt"]

    def test_no_extensions(self):
        assert extract_extensions(["Makefile", "LICENSE"]) == []

    def test_case_normalization(self):
        result = extract_extensions(["photo.JPG", "image.jpg"])
        assert result == [".jpg"]
