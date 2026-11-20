"""File hashing with threaded I/O using ThreadPoolExecutor."""

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from threading import Lock

from core.scanner import ChunkReader
from utils.decorators import measure_time

logger = logging.getLogger(__name__)


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    """Compute the hash digest of a file using the ChunkReader iterator.

    Reading happens in chunks to avoid loading the entire file into memory.
    """
    h = hashlib.new(algorithm)
    for chunk in ChunkReader(path):
        h.update(chunk)
    return h.hexdigest()


@measure_time
def hash_files_threaded(
    paths: list[Path],
    algorithm: str = "sha256",
    max_workers: int | None = None,
) -> dict[Path, str]:
    """Hash multiple files concurrently using a thread pool.

    Threads are well-suited here because file reading is I/O-bound,
    and hashlib releases the GIL for large data blocks.

    Returns a mapping from file path to its hex digest.
    """
    results: dict[Path, str] = {}
    errors: list[tuple[Path, Exception]] = []
    lock = Lock()

    def _hash_one(path: Path) -> tuple[Path, str | None]:
        try:
            digest = hash_file(path, algorithm)
            return path, digest
        except OSError as exc:
            logger.warning("Cannot hash %s: %s", path, exc)
            return path, None

    workers = max_workers or min(16, len(paths) or 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for path, digest in pool.map(lambda p: _hash_one(p), paths):
            if digest is not None:
                with lock:
                    results[path] = digest
            else:
                errors.append((path, OSError("hash failed")))

    if errors:
        logger.info("Skipped %d files due to errors", len(errors))

    return results


@measure_time
def hash_files_sequential(
    paths: list[Path],
    algorithm: str = "sha256",
) -> dict[Path, str]:
    """Hash files one by one (baseline for benchmarking)."""
    results: dict[Path, str] = {}
    for path in paths:
        try:
            results[path] = hash_file(path, algorithm)
        except OSError as exc:
            logger.warning("Cannot hash %s: %s", path, exc)
    return results


def group_by_size(paths: list[Path]) -> dict[int, list[Path]]:
    """Group files by their size in bytes.

    Only groups with 2+ files are potential duplicates worth hashing.
    """
    size_map: dict[int, list[Path]] = {}
    for path in paths:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        size_map.setdefault(size, []).append(path)
    return {size: files for size, files in size_map.items() if len(files) >= 2}


def find_duplicate_candidates(paths: list[Path]) -> list[list[Path]]:
    """Return groups of files that share the same size.

    This is the first pass — a cheap pre-filter before expensive hashing.
    """
    size_groups = group_by_size(paths)
    return list(size_groups.values())
