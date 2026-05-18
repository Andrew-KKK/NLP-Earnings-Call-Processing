"""Adapter for 恩泓: translation + Q&A extraction.

Uses Azure OpenAI when AZURE_OPENAI_API_KEY is set; otherwise routes Q&A
extraction through services.gemini_qna_extractor (spec §8.6).

Translation always uses Azure Translator via the upstream module's REST call.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from adapters._shared import added_sys_path, chdir, team_root
from config import get_settings
from services import gemini_qna_extractor

ENHONG_ROOT = "恩泓_ 逐字稿翻譯和 Q&A 擷取/source"

log = logging.getLogger(__name__)


def _detect_language(text: str) -> tuple[str, str]:
    sample = text[:500]
    chinese_chars = re.findall(r"[一-鿿]", sample)
    if len(chinese_chars) > 10:
        return "zh-Hant", "en"
    return "en", "zh-Hant"


def _ensure_config_ini(src: Path, settings) -> None:
    """Write a minimal config.ini that satisfies qa_pipeline.py's read at import."""
    cfg_path = src / "config.ini"
    content = (
        "[AzureOpenAI]\n"
        f"API_KEY = {settings.AZURE_OPENAI_API_KEY or 'unused'}\n"
        f"API_ENDPOINT = {settings.AZURE_OPENAI_ENDPOINT or 'https://example.invalid'}\n"
        f"API_VERSION = {settings.AZURE_OPENAI_API_VERSION}\n"
        f"DEPLOYMENT_NAME = {settings.AZURE_OPENAI_DEPLOYMENT or 'unused'}\n"
        "\n[AzureTranslator]\n"
        f"TRANSLATOR_KEY = {settings.AZURE_TRANSLATOR_KEY}\n"
        f"TRANSLATOR_REGION = {settings.AZURE_TRANSLATOR_REGION}\n"
        f"TRANSLATOR_ENDPOINT = {settings.AZURE_TRANSLATOR_ENDPOINT}\n"
    )
    cfg_path.write_text(content, encoding="utf-8")


# Indirections so tests can patch.
def _translate_text(text: str, target_lang: str) -> str:
    import sys
    qa_pipeline = sys.modules["qa_pipeline"]
    return qa_pipeline.translate_text(text, target_lang)


def _extract_qna_for_chunk(chunk: str) -> list[dict[str, str]]:
    settings = get_settings()
    if settings.has_azure_openai():
        import sys
        qa_pipeline = sys.modules["qa_pipeline"]
        return qa_pipeline.extract_qna_from_chunk(chunk)
    return gemini_qna_extractor.extract_qna_from_chunk(
        chunk,
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
    )


def _import_qa_pipeline():
    settings = get_settings()
    src = team_root(ENHONG_ROOT)
    _ensure_config_ini(src, settings)
    with added_sys_path(src), chdir(src):
        import importlib
        import sys
        if "qa_pipeline" in sys.modules:
            importlib.reload(sys.modules["qa_pipeline"])
        else:
            import qa_pipeline  # noqa: F401
    return src


def run(
    *,
    full_text: str,
    qna_text: str | None,
    out_dir: Path,
    slug: str,
) -> tuple[Path, Path]:
    """Produce the two 恩泓-shaped JSON files in out_dir.

    Returns: (full_transcript_path, extracted_qna_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    _import_qa_pipeline()

    import sys
    qa_pipeline = sys.modules["qa_pipeline"]

    source_lang, target_lang = _detect_language(full_text)

    # --- Track 1: full transcript translation ---
    paragraphs = [p.strip() for p in full_text.split("\n") if p.strip()]
    content_list = []
    for idx, para in enumerate(paragraphs, start=1):
        translated = _translate_text(para, target_lang)
        content_list.append({"paragraph_index": idx, "original_text": para, "translated_text": translated})
        time.sleep(0.05)

    full_doc = {
        "metadata": {
            "source_language": source_lang,
            "target_language": target_lang,
            "total_paragraphs": len(paragraphs),
        },
        "content": content_list,
    }

    # --- Track 2: Q&A extraction + translation ---
    text_for_qna = qna_text or full_text
    chunks = qa_pipeline.chunk_text(text_for_qna, chunk_size=8000, overlap=1500)
    all_pairs: list[dict[str, str]] = []
    for chunk in chunks:
        all_pairs.extend(_extract_qna_for_chunk(chunk))

    # Dedup same as upstream
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in all_pairs:
        key = item.get("question", "")[:50].strip().lower()
        if key and key not in seen and len(key) > 10:
            seen.add(key)
            unique.append(item)

    for item in unique:
        item["question_translated"] = _translate_text(item["question"], target_lang)
        item["answer_translated"] = _translate_text(item["answer"], target_lang)

    qna_doc = {
        "metadata": {
            "source_language": source_lang,
            "target_language": target_lang,
            "total_qna_pairs": len(unique),
        },
        "qna_list": unique,
    }

    full_path = out_dir / "full_transcript_translation.json"
    qna_path = out_dir / "extracted_qna_translation.json"
    full_path.write_text(json.dumps(full_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    qna_path.write_text(json.dumps(qna_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return full_path, qna_path
