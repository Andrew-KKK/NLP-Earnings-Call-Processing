"""Root conftest: makes the frontend package importable and isolates env per test."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

FRONTEND_ROOT = Path(__file__).resolve().parent
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))


@pytest.fixture(autouse=True)
def _clean_api_env(monkeypatch):
    """Each test starts with no real API keys set."""
    for key in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_TRANSLATOR_KEY",
        "AZURE_TRANSLATOR_REGION",
        "AZURE_LANGUAGE_KEY",
        "AZURE_LANGUAGE_ENDPOINT",
        "GEMINI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
