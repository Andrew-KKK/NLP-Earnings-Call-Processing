"""Discover pre-computed cases (team outputs) and uploaded cases (cache dir)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from config import get_settings

ENHONG_DIR = "恩泓_ 逐字稿翻譯和 Q&A 擷取"
HAOCHENG_DIR = "浩誠_回答品質評分"
JINCING_DIR = "瑾慈：情緒分析&關鍵字擷取"
YINING_DIR = "奕寧_ 摘要&PII"


@dataclass(frozen=True)
class CaseInfo:
    slug: str
    display_name: str
    source: Literal["precomputed", "upload"]
    qna_json: Path
    full_json: Path
    scores_json: Path
    radar_png: Path
    sentiment_dir: Path
    keyphrase_dir: Path
    pii_summary_json: Path

    def all_files_exist(self) -> bool:
        return self.qna_json.exists() and self.full_json.exists()


def discover_cases() -> list[CaseInfo]:
    settings = get_settings()
    root = settings.precomputed_root_resolved()
    cache = settings.cache_dir_resolved()

    cases: list[CaseInfo] = []
    cases.extend(_discover_precomputed(root))
    cases.extend(_discover_uploaded(cache))
    # Stable order
    return sorted(cases, key=lambda c: (c.source != "precomputed", c.slug))


def _discover_precomputed(root: Path) -> list[CaseInfo]:
    enhong = root / ENHONG_DIR
    haocheng = root / HAOCHENG_DIR / "output" / "batch_from_json"
    jincing_sent = root / JINCING_DIR / "sentiment_output"
    jincing_kp = root / JINCING_DIR / "keyphrase_output"
    yining = root / YINING_DIR / "output"

    out: list[CaseInfo] = []
    if not enhong.exists():
        return out
    for qna_path in sorted(enhong.glob("*_extracted_qna_translation.json")):
        slug = qna_path.name.replace("_extracted_qna_translation.json", "")
        full_path = qna_path.with_name(f"{slug}_full_transcript_translation.json")
        out.append(
            CaseInfo(
                slug=slug,
                display_name=slug.upper(),
                source="precomputed",
                qna_json=qna_path,
                full_json=full_path,
                scores_json=haocheng / f"{slug}_scores.json",
                radar_png=haocheng / f"{slug}_transparency_radar.png",
                sentiment_dir=jincing_sent / slug,
                keyphrase_dir=jincing_kp / slug,
                pii_summary_json=yining / f"{slug}_extracted_qna_translation_pii_summary.json",
            )
        )
    return out


def _discover_uploaded(cache: Path) -> list[CaseInfo]:
    out: list[CaseInfo] = []
    if not cache.exists():
        return out
    for case_dir in sorted(p for p in cache.iterdir() if p.is_dir()):
        slug = case_dir.name
        out.append(
            CaseInfo(
                slug=slug,
                display_name=slug,
                source="upload",
                qna_json=case_dir / "extracted_qna_translation.json",
                full_json=case_dir / "full_transcript_translation.json",
                scores_json=case_dir / "scores.json",
                radar_png=case_dir / "transparency_radar.png",
                sentiment_dir=case_dir,
                keyphrase_dir=case_dir,
                pii_summary_json=case_dir / "pii_summary.json",
            )
        )
    return out


def find_case(slug: str) -> CaseInfo | None:
    for c in discover_cases():
        if c.slug == slug:
            return c
    return None
