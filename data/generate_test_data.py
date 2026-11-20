"""Generate test data for the duplicate file finder.

Creates a directory tree with known duplicates for testing
and benchmarking purposes.

Usage:
    python -m data.generate_test_data [--output test_data] [--count 50]
"""

import argparse
import os
import random
import sys
from pathlib import Path


def generate_test_data(output_dir: Path, file_count: int = 50, seed: int = 42) -> None:
    """Generate a directory tree with files, some of which are duplicates."""
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    subdirs = [
        output_dir / "documents",
        output_dir / "images",
        output_dir / "logs",
        output_dir / "backup" / "old",
        output_dir / "backup" / "recent",
    ]
    for d in subdirs:
        d.mkdir(parents=True, exist_ok=True)

    extensions = [".txt", ".log", ".dat", ".csv", ".json", ".xml", ".bin"]
    unique_contents: list[bytes] = []

    unique_count = int(file_count * 0.6)
    for i in range(unique_count):
        size = rng.randint(1024, 512 * 1024)
        content = rng.randbytes(size)
        unique_contents.append(content)

        ext = rng.choice(extensions)
        directory = rng.choice(subdirs)
        path = directory / f"file_{i:04d}{ext}"
        path.write_bytes(content)

    duplicate_count = file_count - unique_count
    for i in range(duplicate_count):
        original = rng.choice(unique_contents)
        ext = rng.choice(extensions)
        directory = rng.choice(subdirs)
        path = directory / f"copy_{i:04d}{ext}"
        path.write_bytes(original)

    total_size = sum(
        f.stat().st_size
        for f in output_dir.rglob("*")
        if f.is_file()
    )
    print(f"Generated {file_count} files ({unique_count} unique, "
          f"{duplicate_count} duplicates)")
    print(f"Total size: {total_size / 1024 / 1024:.1f} MB")
    print(f"Output: {output_dir.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate test data")
    parser.add_argument("--output", "-o", default="test_data",
                        help="Output directory (default: test_data)")
    parser.add_argument("--count", "-c", type=int, default=50,
                        help="Number of files to generate (default: 50)")
    parser.add_argument("--seed", "-s", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    generate_test_data(Path(args.output), args.count, args.seed)
