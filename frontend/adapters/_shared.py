"""Shared helpers for adapters: sys.path injection + safe CWD swap."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import Iterator

from config import get_settings


def team_root(team_dir_name: str) -> Path:
    return get_settings().precomputed_root_resolved() / team_dir_name


@contextlib.contextmanager
def added_sys_path(path: Path) -> Iterator[None]:
    s = str(path)
    inserted = False
    if s not in sys.path:
        sys.path.insert(0, s)
        inserted = True
    try:
        yield
    finally:
        if inserted and sys.path and sys.path[0] == s:
            sys.path.pop(0)


@contextlib.contextmanager
def chdir(path: Path) -> Iterator[None]:
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)
