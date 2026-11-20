"""Duplicate File Finder — CLI entry point.

Usage:
    python main.py <directory> [options]
    python main.py --benchmark [directory]

Examples:
    python main.py ~/Documents --pattern "*.jpg" "*.png"
    python main.py . --min-size 1KB --max-size 100MB
    python main.py --benchmark test_data
"""

import argparse
import logging
import sys
from pathlib import Path

from core.analyzer import find_duplicates, format_report, hash_files_multiprocess
from core.hasher import find_duplicate_candidates, hash_files_threaded
from core.patterns import build_glob_filter, parse_size
from core.scanner import FileScanner
from utils.decorators import measure_time


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dupfinder",
        description="Find duplicate files in a directory tree.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--pattern", "-p",
        nargs="+",
        metavar="GLOB",
        help="Include only files matching these glob patterns (e.g. '*.jpg' '*.png')",
    )
    parser.add_argument(
        "--min-size",
        default="1B",
        help="Minimum file size (e.g. 1KB, 10MB). Default: 1B",
    )
    parser.add_argument(
        "--max-size",
        default=None,
        help="Maximum file size (e.g. 500MB, 1GB)",
    )
    parser.add_argument(
        "--algorithm", "-a",
        default="sha256",
        choices=["md5", "sha1", "sha256", "sha512"],
        help="Hash algorithm (default: sha256)",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        help="Number of worker threads/processes",
    )
    parser.add_argument(
        "--use-processes",
        action="store_true",
        help="Use processes instead of threads for hashing",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run GIL benchmark on the specified directory",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="Increase logging verbosity (-v for INFO, -vv for DEBUG)",
    )
    return parser.parse_args(argv)


def configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@measure_time
def run_scan(args: argparse.Namespace) -> list[Path]:
    """Scan the directory and return matching file paths."""
    scanner = FileScanner(args.directory)
    scanner.min_size = parse_size(args.min_size)
    if args.max_size:
        scanner.max_size = parse_size(args.max_size)

    pattern_filter = build_glob_filter(args.pattern) if args.pattern else None
    return list(scanner.scan(pattern_filter))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    if args.benchmark:
        from benchmarks.gil_benchmark import run_benchmark
        run_benchmark(args.directory)
        return 0

    root = Path(args.directory)
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        return 1

    print(f"Scanning {root.resolve()}...")
    files = run_scan(args)
    print(f"Found {len(files)} files")

    if not files:
        print("No files to analyze.")
        return 0

    candidate_groups = find_duplicate_candidates(files)
    candidates = [f for group in candidate_groups for f in group]
    print(f"Size-based pre-filter: {len(candidates)} files in "
          f"{len(candidate_groups)} groups to hash")

    if not candidates:
        print("No potential duplicates (all files have unique sizes).")
        return 0

    print(f"\nHashing with {args.algorithm}...")
    if args.use_processes:
        hash_map = hash_files_multiprocess(candidates, args.algorithm, args.workers)
    else:
        hash_map = hash_files_threaded(candidates, args.algorithm, args.workers)

    duplicates = find_duplicates(hash_map)
    print()
    print(format_report(duplicates))
    return 0


if __name__ == "__main__":
    sys.exit(main())
