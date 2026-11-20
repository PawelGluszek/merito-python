"""Regex patterns for file filtering and metadata extraction."""

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Compiled patterns with named groups
# ---------------------------------------------------------------------------

FILE_PATTERN = re.compile(
    r"""
    ^
    (?P<basename>.+?)           # file name without extension
    (?:\s*\((?P<copy>\d+)\))?   # optional copy number e.g. "(2)"
    (?P<ext>\.[a-zA-Z0-9]+)?    # optional extension
    $
    """,
    re.VERBOSE,
)

SIZE_PATTERN = re.compile(
    r"""
    ^
    (?P<value>\d+(?:\.\d+)?)    # numeric value
    \s*
    (?P<unit>[KMGTP]?B)         # unit: B, KB, MB, GB, TB, PB
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)

GITIGNORE_PATTERN = re.compile(
    r"""
    ^\s*                         # leading whitespace
    (?P<negation>!)?             # optional negation
    (?P<pattern>[^\s\#]+)        # the glob pattern
    \s*                          # trailing whitespace
    (?:\#.*)?                    # optional inline comment
    $
    """,
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Functions using the patterns
# ---------------------------------------------------------------------------

_SIZE_MULTIPLIERS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024 ** 2,
    "GB": 1024 ** 3,
    "TB": 1024 ** 4,
    "PB": 1024 ** 5,
}


def parse_size(text: str) -> int:
    """Parse a human-readable size string into bytes.

    >>> parse_size("10 MB")
    10485760
    >>> parse_size("512KB")
    524288
    """
    match = SIZE_PATTERN.fullmatch(text.strip())
    if not match:
        raise ValueError(f"Invalid size format: {text!r}")
    value = float(match.group("value"))
    unit = match.group("unit").upper()
    return int(value * _SIZE_MULTIPLIERS[unit])


def parse_filename(name: str) -> dict[str, str | None]:
    """Extract structured parts from a filename.

    >>> parse_filename("report (2).pdf")
    {'basename': 'report', 'copy': '2', 'ext': '.pdf'}
    """
    match = FILE_PATTERN.fullmatch(name)
    if not match:
        return {"basename": name, "copy": None, "ext": None}
    return match.groupdict()


def build_glob_filter(patterns: list[str]):
    """Build a filename filter from glob-like patterns.

    Supported: ``*`` matches anything, ``?`` matches one char,
    ``[abc]`` matches one of the listed chars.

    Returns a callable ``(filename: str) -> bool``.
    """
    if not patterns:
        return None

    regexes = []
    for pat in patterns:
        regex = _glob_to_regex(pat)
        regexes.append(regex)

    combined = re.compile("|".join(f"(?:{r})" for r in regexes))

    def _filter(filename: str) -> bool:
        return combined.fullmatch(filename) is not None

    return _filter


def _glob_to_regex(pattern: str) -> str:
    """Convert a simple glob pattern to a regex string."""
    result = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            result.append(".*")
        elif ch == "?":
            result.append(".")
        elif ch == "[":
            end = pattern.find("]", i)
            if end == -1:
                result.append(re.escape(ch))
            else:
                result.append(pattern[i:end + 1])
                i = end
        else:
            result.append(re.escape(ch))
        i += 1
    return "".join(result)


def extract_extensions(filenames: list[str]) -> list[str]:
    """Extract unique file extensions using regex.

    >>> sorted(extract_extensions(["a.py", "b.txt", "c.py", "readme"]))
    ['.py', '.txt']
    """
    ext_re = re.compile(r"(?P<ext>\.[a-zA-Z0-9]+)$")
    extensions = set()
    for name in filenames:
        match = ext_re.search(name)
        if match:
            extensions.add(match.group("ext").lower())
    return sorted(extensions)
