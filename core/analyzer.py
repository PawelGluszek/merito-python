"""Duplicate file analysis using multiprocessing for CPU-bound work."""

import hashlib
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from multiprocessing import cpu_count
from pathlib import Path

from utils.decorators import measure_time

logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """A group of files sharing the same content hash."""
    hash_digest: str
    size: int
    paths: list[Path] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        """Bytes that could be freed by removing all but one copy."""
        return self.size * (len(self.paths) - 1)

    def __len__(self) -> int:
        return len(self.paths)


def _hash_file_for_process(args: tuple[str, str]) -> tuple[str, str]:
    """Hash a single file — top-level function so it's picklable.

    Accepts a tuple (path_str, algorithm) and returns (path_str, hex_digest).
    """
    path_str, algorithm = args
    h = hashlib.new(algorithm)
    try:
        with open(path_str, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
    except OSError:
        return path_str, ""
    return path_str, h.hexdigest()


@measure_time
def hash_files_multiprocess(
    paths: list[Path],
    algorithm: str = "sha256",
    max_workers: int | None = None,
) -> dict[Path, str]:
    """Hash files in parallel using a process pool.

    Each worker runs in its own process with its own GIL, allowing
    true CPU parallelism for the hash computation.
    """
    workers = max_workers or min(cpu_count(), len(paths) or 1)
    args = [(str(p), algorithm) for p in paths]

    results: dict[Path, str] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for path_str, digest in pool.map(_hash_file_for_process, args):
            if digest:
                results[Path(path_str)] = digest
            else:
                logger.warning("Skipped (error): %s", path_str)

    return results


def find_duplicates(
    hash_map: dict[Path, str],
) -> list[DuplicateGroup]:
    """Group files by identical hash and return only groups with duplicates."""
    digest_to_paths: dict[str, list[Path]] = {}
    for path, digest in hash_map.items():
        digest_to_paths.setdefault(digest, []).append(path)

    groups = []
    for digest, paths in digest_to_paths.items():
        if len(paths) < 2:
            continue
        try:
            size = paths[0].stat().st_size
        except OSError:
            size = 0
        groups.append(DuplicateGroup(hash_digest=digest, size=size, paths=sorted(paths)))

    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return groups


def format_report(groups: list[DuplicateGroup]) -> str:
    """Format duplicate groups into a human-readable report."""
    if not groups:
        return "No duplicates found."

    lines = []
    total_wasted = 0
    total_groups = len(groups)
    total_files = sum(len(g) for g in groups)

    for i, group in enumerate(groups, 1):
        lines.append(f"--- Group {i} ({_human_size(group.size)} each, "
                      f"{len(group)} copies) ---")
        lines.append(f"    Hash: {group.hash_digest[:16]}...")
        for path in group.paths:
            lines.append(f"    {path}")
        total_wasted += group.wasted_bytes
        lines.append("")

    lines.append(f"Summary: {total_groups} duplicate groups, "
                 f"{total_files} files, "
                 f"{_human_size(total_wasted)} wasted space")
    return "\n".join(lines)


def _human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
