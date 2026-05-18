"""Adapter for 瑾慈: sentiment + keyphrase analysis.

Strategy: each upstream script reads config.ini from CWD. The adapter writes a
fresh config.ini that points the input dir at a temp directory containing the
case JSONs and the output dir at our cache, then calls the script's main().
"""

from __future__ import annotations

import configparser
import json
import runpy
import shutil
from pathlib import Path
from typing import Iterable

from adapters._shared import added_sys_path, chdir, team_root
from config import get_settings

JINCING_ROOT = "瑾慈：情緒分析&關鍵字擷取"

# Indirection so tests can patch this.
def _runpy_run_module(mod_name: str, run_name: str | None = None) -> None:
    runpy.run_module(mod_name, run_name=run_name)


def _stage_inputs(qna_json: Path, full_json: Path, staging: Path, slug: str) -> Path:
    """Copy the two JSON files into `staging` with the names the scripts expect.

    If a source path doesn't exist (test fixtures often skip the file), a
    placeholder is created instead so the upstream script's filename check
    (when invoked for real) passes. Tests typically stub the runpy call so
    the placeholder is never actually read.
    """
    staging.mkdir(parents=True, exist_ok=True)
    target_qna = staging / f"{slug}_extracted_qna_translation.json"
    target_full = staging / f"{slug}_full_transcript_translation.json"
    if Path(qna_json).exists():
        shutil.copy2(qna_json, target_qna)
    else:
        target_qna.write_text("{}", encoding="utf-8")
    if Path(full_json).exists():
        shutil.copy2(full_json, target_full)
    else:
        target_full.write_text("{}", encoding="utf-8")
    return staging


def _write_sentiment_config(
    config_path: Path,
    *,
    azure_key: str,
    azure_endpoint: str,
    input_dir: Path,
    output_dir: Path,
    company_prefix: str,
) -> None:
    cfg = configparser.ConfigParser()
    cfg["azure"] = {"language_key": azure_key, "language_endpoint": azure_endpoint}
    cfg["path"] = {"input_dir": str(input_dir), "output_dir": str(output_dir)}
    cfg["input"] = {"company_prefix": company_prefix}
    cfg["setting"] = {"use_translated": "false", "batch_size": "10", "max_chars": "4500"}
    with config_path.open("w", encoding="utf-8") as f:
        cfg.write(f)


def _copy_outputs(src_company_dir: Path, out_dir: Path, files: Iterable[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in files:
        src = src_company_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)


def run_sentiment(
    *,
    qna_json: Path,
    full_json: Path,
    out_dir: Path,
    slug: str,
    sent_out: Path | None = None,
) -> None:
    settings = get_settings()
    src = team_root(JINCING_ROOT)

    staging = (sent_out or (out_dir / "_stage_sent")).parent / "_jincing_stage_sent"
    input_dir = _stage_inputs(qna_json, full_json, staging / "input", slug)
    raw_out = (sent_out or (out_dir / "_sent_raw"))
    raw_out.mkdir(parents=True, exist_ok=True)

    _write_sentiment_config(
        src / "config.ini",
        azure_key=settings.AZURE_LANGUAGE_KEY,
        azure_endpoint=settings.AZURE_LANGUAGE_ENDPOINT,
        input_dir=input_dir,
        output_dir=raw_out,
        company_prefix=slug,
    )

    with added_sys_path(src), chdir(src):
        _runpy_run_module("sentiment_analysis", run_name="__main__")

    _copy_outputs(
        raw_out / slug,
        out_dir,
        ["qna_sentiment_summary.json", "section_sentiment_summary.json", "company_tone_shift_summary.json"],
    )


def _write_keyphrase_config(
    config_path: Path,
    *,
    azure_key: str,
    azure_endpoint: str,
    input_dir: Path,
    output_dir: Path,
    company_prefix: str,
) -> None:
    cfg = configparser.ConfigParser()
    cfg["azure"] = {"language_key": azure_key, "language_endpoint": azure_endpoint}
    cfg["path"] = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "keyphrase_output_dir": str(output_dir),
    }
    cfg["input"] = {"company_prefix": company_prefix}
    cfg["setting"] = {"keyphrase_use_translated": "auto", "batch_size": "10", "max_chars": "4500"}
    with config_path.open("w", encoding="utf-8") as f:
        cfg.write(f)


def run_keyphrase(
    *,
    qna_json: Path,
    full_json: Path,
    out_dir: Path,
    slug: str,
    kp_out: Path | None = None,
) -> None:
    settings = get_settings()
    src = team_root(JINCING_ROOT)

    staging = (kp_out or (out_dir / "_stage_kp")).parent / "_jincing_stage_kp"
    input_dir = _stage_inputs(qna_json, full_json, staging / "input", slug)
    raw_out = (kp_out or (out_dir / "_kp_raw"))
    raw_out.mkdir(parents=True, exist_ok=True)

    _write_keyphrase_config(
        src / "config.ini",
        azure_key=settings.AZURE_LANGUAGE_KEY,
        azure_endpoint=settings.AZURE_LANGUAGE_ENDPOINT,
        input_dir=input_dir,
        output_dir=raw_out,
        company_prefix=slug,
    )

    with added_sys_path(src), chdir(src):
        _runpy_run_module("key_phrase_extraction", run_name="__main__")

    _copy_outputs(
        raw_out / slug,
        out_dir,
        ["qna_keyphrase_summary.json", "topic_emphasis_summary.json"],
    )
