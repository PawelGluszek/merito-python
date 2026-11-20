"""File system scanner with iterators and generators."""

import functools
import logging
import os
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Method decorator that accesses instance state
# ---------------------------------------------------------------------------

def requires_config(method):
    """Ensure the scanner is configured before the method runs."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.root_directory:
            raise RuntimeError(
                f"{method.__name__}: scanner has no root directory configured"
            )
        if not self.root_directory.is_dir():
            raise FileNotFoundError(
                f"{method.__name__}: {self.root_directory} is not a directory"
            )
        return method(self, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Iterator: reads a file in fixed-size chunks
# ---------------------------------------------------------------------------

class ChunkReader:
    """Read a file in fixed-size binary chunks.

    Implements the iterator protocol (__iter__ + __next__).
    Useful for hashing large files without loading them entirely into memory.
    """

    def __init__(self, path: Path, chunk_size: int = 8192):
        self._path = path
        self._chunk_size = chunk_size
        self._file = None

    def __iter__(self) -> "ChunkReader":
        self._file = open(self._path, "rb")
        return self

    def __next__(self) -> bytes:
        if self._file is None:
            raise StopIteration
        chunk = self._file.read(self._chunk_size)
        if not chunk:
            self._file.close()
            self._file = None
            raise StopIteration
        return chunk

    def __del__(self):
        if self._file is not None:
            self._file.close()


# ---------------------------------------------------------------------------
# Generator: recursive directory walk
# ---------------------------------------------------------------------------

def walk_files(directory: Path) -> Iterator[Path]:
    """Yield all file paths under *directory* recursively.

    Uses ``yield from`` for recursive delegation and ``os.scandir``
    for efficient directory traversal.
    """
    try:
        entries = os.scandir(directory)
    except PermissionError:
        logger.warning("Permission denied: %s", directory)
        return

    with entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                yield from walk_files(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                yield Path(entry.path)


# ---------------------------------------------------------------------------
# Scanner class (uses property, classmethod, staticmethod)
# ---------------------------------------------------------------------------

class FileScanner:
    """Scan a directory tree and yield files matching configured filters."""

    DEFAULT_MIN_SIZE: int = 1

    def __init__(self, root: str | Path):
        self.root_directory = Path(root)
        self._min_size = self.DEFAULT_MIN_SIZE
        self._max_size: int | None = None
        self._exclude_names: set[str] = set()

    # --- property with setter (validation) ---

    @property
    def min_size(self) -> int:
        return self._min_size

    @min_size.setter
    def min_size(self, value: int) -> None:
        if value < 0:
            raise ValueError("min_size must be non-negative")
        self._min_size = value

    @property
    def max_size(self) -> int | None:
        return self._max_size

    @max_size.setter
    def max_size(self, value: int | None) -> None:
        if value is not None and value < 0:
            raise ValueError("max_size must be non-negative")
        self._max_size = value

    # --- classmethod: alternative constructor ---

    @classmethod
    def with_size_range(cls, root: str | Path, min_size: int, max_size: int) -> "FileScanner":
        """Create a scanner pre-configured with a size filter range."""
        scanner = cls(root)
        scanner.min_size = min_size
        scanner.max_size = max_size
        return scanner

    # --- staticmethod ---

    @staticmethod
    def human_readable_size(size_bytes: int) -> str:
        """Convert byte count to a human-readable string."""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size_bytes) < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    # --- decorated method using self ---

    @requires_config
    def scan(self, pattern_filter=None) -> Iterator[Path]:
        """Yield files matching size and optional pattern filters.

        Uses a generator expression for lazy filtering.
        """
        all_files = walk_files(self.root_directory)

        sized = (
            f for f in all_files
            if self._passes_size_filter(f) and f.name not in self._exclude_names
        )

        if pattern_filter is not None:
            yield from (f for f in sized if pattern_filter(f.name))
        else:
            yield from sized

    def _passes_size_filter(self, path: Path) -> bool:
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size < self._min_size:
            return False
        if self._max_size is not None and size > self._max_size:
            return False
        return True

    def exclude(self, *names: str) -> "FileScanner":
        """Add filenames to the exclusion set. Returns self for chaining."""
        self._exclude_names.update(names)
        return self
