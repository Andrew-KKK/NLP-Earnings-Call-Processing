"""Adapter for 奕寧: PII redaction + extractive summary."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from adapters._shared import added_sys_path, chdir, team_root
from config import get_settings

YINING_ROOT = "奕寧_ 摘要&PII"


def _invoke_app(filename: str) -> None:
    """Import 奕寧/app.py and call run_pii_and_summary(filename) in its CWD."""
    # The module reads AZURE_LANGUAGE_* via dotenv at import time; ensure env is exported.
    import importlib
    if "app" in list(__import__("sys").modules):
        importlib.reload(__import__("sys").modules["app"])
    import app as yining_app  # type: ignore
    yining_app.run_pii_and_summary(filename)


def run(*, qna_json: Path, full_json: Path, out_dir: Path, slug: str) -> None:
    settings = get_settings()
    src = team_root(YINING_ROOT)
    data_dir = src / "data"
    output_dir = src / "output"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Stage inputs under the names 奕寧 expects.
    qna_name = f"{slug}_extracted_qna_translation.json"
    full_name = f"{slug}_full_transcript_translation.json"
    shutil.copy2(qna_json, data_dir / qna_name)
    shutil.copy2(full_json, data_dir / full_name)

    # Export env so app.py's module-level load_dotenv-respecting code sees them.
    os.environ["AZURE_LANGUAGE_KEY"] = settings.AZURE_LANGUAGE_KEY
    os.environ["AZURE_LANGUAGE_ENDPOINT"] = settings.AZURE_LANGUAGE_ENDPOINT

    out_dir.mkdir(parents=True, exist_ok=True)
    with added_sys_path(src), chdir(src):
        _invoke_app(qna_name)
        _invoke_app(full_name)

    # Copy outputs into our cache with the canonical name `pii_summary.json`
    qna_out = output_dir / qna_name.replace(".json", "_pii_summary.json")
    full_out = output_dir / full_name.replace(".json", "_pii_summary.json")
    if qna_out.exists():
        shutil.copy2(qna_out, out_dir / "pii_summary.json")
    if full_out.exists():
        shutil.copy2(full_out, out_dir / "pii_summary_full.json")
