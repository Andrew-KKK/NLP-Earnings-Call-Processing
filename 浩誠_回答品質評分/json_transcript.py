# -*- coding: utf-8 -*-
"""從專案標準 JSON（逐字稿 + Q&A 擷取）載入全文與 Q&A 配對。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from metrics import QAPair


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_qna_pairs(qna_json_path: Path) -> list[QAPair]:
    data = _read_json(qna_json_path)
    items = data.get("qna_list") or []
    pairs: list[QAPair] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        q = (row.get("question_translated") or row.get("question") or "").strip()
        a = (row.get("answer_translated") or row.get("answer") or "").strip()
        if q or a:
            pairs.append(QAPair(question=q, answer=a))
    return pairs


def full_transcript_path_for_qna(qna_json_path: Path) -> Path:
    name = qna_json_path.name
    if "extracted_qna" not in name:
        return qna_json_path.with_name(name.replace("qna", "full_transcript_translation"))
    return qna_json_path.with_name(name.replace("extracted_qna_translation", "full_transcript_translation"))


def presentation_text_from_full_transcript(
    full_json_path: Path,
    first_question_hint: str,
    *,
    fallback_head_ratio: float = 0.42,
) -> str:
    """
    以「第一題問題文字」在逐字稿段落中首次出現處切開：之前視為簡報／說明段，
    之後視為 Q&A（避免把分析師問句算進簡報語氣）。
    找不到則取前 fallback_head_ratio 的段落字數拼接。
    """
    data = _read_json(full_json_path)
    blocks = data.get("content") or []
    paras: list[str] = []
    for b in blocks:
        if isinstance(b, dict):
            t = (b.get("translated_text") or b.get("original_text") or "").strip()
            if t:
                paras.append(t)
    if not paras:
        return ""

    hint = re.sub(r"\s+", "", (first_question_hint or "")[:80])
    split_at = len(paras)
    if len(hint) >= 12:
        for i, p in enumerate(paras):
            if hint and re.sub(r"\s+", "", p).find(hint[:40]) >= 0:
                split_at = i
                break

    if split_at >= len(paras):
        # 字數比例切頭部當「簡報段」代理
        total = sum(len(p) for p in paras) + 1
        acc = 0
        split_at = 0
        cap = int(total * max(0.15, min(0.85, fallback_head_ratio)))
        for i, p in enumerate(paras):
            acc += len(p)
            split_at = i + 1
            if acc >= cap:
                break

    return "\n".join(paras[:split_at])


def stem_from_qna_filename(path: Path) -> str:
    name = path.name
    for suffix in ("_extracted_qna_translation.json", "_extracted_qna.json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem
