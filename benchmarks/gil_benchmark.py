"""GIL benchmark: sequential vs threads vs processes for file hashing.

Demonstrates the practical impact of the Global Interpreter Lock on
CPU-bound and I/O-bound workloads.

Run directly:
    python -m benchmarks.gil_benchmark [test_data_directory]
"""

import hashlib
import os
import sys
import sysconfig
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import cpu_count
from pathlib import Path


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------

def _hash_file(path_str: str) -> str:
    """Hash a single file (top-level for pickling in process pool)."""
    h = hashlib.sha256()
    with open(path_str, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def benchmark_sequential(files: list[str]) -> tuple[float, int]:
    """Hash all files sequentially. Returns (elapsed_seconds, file_count)."""
    start = time.perf_counter()
    for f in files:
        _hash_file(f)
    elapsed = time.perf_counter() - start
    return elapsed, len(files)


def benchmark_threads(files: list[str], workers: int) -> tuple[float, int]:
    """Hash all files with a thread pool."""
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_hash_file, files))
    elapsed = time.perf_counter() - start
    return elapsed, len(files)


def benchmark_processes(files: list[str], workers: int) -> tuple[float, int]:
    """Hash all files with a process pool."""
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_hash_file, files))
    elapsed = time.perf_counter() - start
    return elapsed, len(files)


# ---------------------------------------------------------------------------
# Pure CPU benchmark (no I/O, shows GIL most clearly)
# ---------------------------------------------------------------------------

def _cpu_work(n: int) -> int:
    """Burn CPU cycles: sum of squares up to n."""
    total = 0
    for i in range(n):
        total += i * i
    return total


def _cpu_work_for_process(n: int) -> int:
    """Same as _cpu_work, top-level for pickling."""
    return _cpu_work(n)


def benchmark_cpu_sequential(tasks: list[int]) -> float:
    start = time.perf_counter()
    for n in tasks:
        _cpu_work(n)
    return time.perf_counter() - start


def benchmark_cpu_threads(tasks: list[int], workers: int) -> float:
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_cpu_work, tasks))
    return time.perf_counter() - start


def benchmark_cpu_processes(tasks: list[int], workers: int) -> float:
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_cpu_work_for_process, tasks))
    return time.perf_counter() - start


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_environment_info():
    """Print Python and GIL configuration details."""
    print("=" * 60)
    print("ENVIRONMENT")
    print("=" * 60)
    print(f"Python version:      {sys.version}")
    print(f"CPU cores:           {cpu_count()}")
    print(f"Switch interval:     {sys.getswitchinterval()} s")
    free_threading = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    print(f"Free-threading build: {free_threading}")
    if hasattr(sys, "_is_gil_enabled"):
        print(f"GIL enabled:         {sys._is_gil_enabled()}")
    print()


def run_benchmark(test_dir: str | None = None):
    """Run the full GIL benchmark suite and print results."""
    workers = cpu_count()

    print_environment_info()

    # --- CPU-bound benchmark ---
    print("=" * 60)
    print("BENCHMARK 1: Pure CPU (sum of squares)")
    print("=" * 60)
    tasks = [2_000_000] * workers
    print(f"Tasks: {len(tasks)} x sum_of_squares(2_000_000)\n")

    t_seq = benchmark_cpu_sequential(tasks)
    t_thr = benchmark_cpu_threads(tasks, workers)
    t_proc = benchmark_cpu_processes(tasks, workers)

    _print_results("Sequential", t_seq, "Threads", t_thr, "Processes", t_proc)

    # --- File hashing benchmark (I/O + CPU) ---
    if test_dir:
        files = _collect_files(test_dir)
        if not files:
            print(f"\nNo files found in {test_dir}")
            return

        total_size = sum(os.path.getsize(f) for f in files)
        print()
        print("=" * 60)
        print("BENCHMARK 2: File hashing (SHA-256)")
        print("=" * 60)
        print(f"Files: {len(files)}, Total size: {total_size / 1024 / 1024:.1f} MB\n")

        t_seq, _ = benchmark_sequential(files)
        t_thr, _ = benchmark_threads(files, workers)
        t_proc, _ = benchmark_processes(files, workers)

        _print_results("Sequential", t_seq, "Threads", t_thr, "Processes", t_proc)

    _print_conclusions()


def _collect_files(directory: str, min_size: int = 1024) -> list[str]:
    """Collect files from directory suitable for benchmarking."""
    files = []
    for root, _, names in os.walk(directory):
        for name in names:
            path = os.path.join(root, name)
            try:
                if os.path.getsize(path) >= min_size:
                    files.append(path)
            except OSError:
                continue
    return files


def _print_results(
    name1: str, t1: float,
    name2: str, t2: float,
    name3: str, t3: float,
):
    """Print a formatted comparison table."""
    print(f"  {'Method':<15} {'Time (s)':>10} {'Speedup':>10}")
    print(f"  {'-' * 15} {'-' * 10} {'-' * 10}")
    for name, t in [(name1, t1), (name2, t2), (name3, t3)]:
        speedup = t1 / t if t > 0 else float("inf")
        print(f"  {name:<15} {t:>10.3f} {speedup:>9.2f}x")
    print()


def _print_conclusions():
    """Print general conclusions about GIL impact."""
    print("=" * 60)
    print("CONCLUSIONS")
    print("=" * 60)
    print("""
For PURE CPU tasks (Benchmark 1):
  - Threads offer NO speedup due to GIL — only one thread
    executes Python bytecode at a time.
  - Processes achieve near-linear speedup because each has
    its own interpreter and GIL.

For FILE HASHING (Benchmark 2, when available):
  - Threads CAN help because:
    (a) file I/O releases the GIL while waiting for the OS,
    (b) hashlib releases the GIL during hash computation on
        large data blocks (implemented in C).
  - Processes also help but have higher startup cost and
    require data serialization (pickle).

Rule of thumb:
  - I/O-bound → threads or asyncio
  - CPU-bound in pure Python → processes
  - CPU-bound in C extensions that release GIL → threads may suffice
""")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else None
    run_benchmark(directory)
