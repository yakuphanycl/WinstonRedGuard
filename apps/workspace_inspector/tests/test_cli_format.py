import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workspace_inspector.cli import format_size_binary


def test_format_size_binary_bytes():
    assert format_size_binary(999) == "999.00 B"


def test_format_size_binary_kilobytes():
    assert format_size_binary(8912) == "8.70 KB"


def test_format_size_binary_megabytes():
    assert format_size_binary(5 * 1024 * 1024) == "5.00 MB"


def test_format_size_binary_gigabytes():
    assert format_size_binary(3 * 1024 * 1024 * 1024) == "3.00 GB"
