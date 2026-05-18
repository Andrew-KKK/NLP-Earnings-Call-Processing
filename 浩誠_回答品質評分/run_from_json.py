# -*- coding: utf-8 -*-
"""
從整份法說會 JSON（Q&A 擷取檔 + 同名的 full 逐字稿）計算五維與雷達圖。

專案裡與你們管線對齊的「三份」Q&A 文字檔（JSON）通常為：
  1. 瑾慈：情緒分析&關鍵字擷取\\input\\tsmc_extracted_qna_translation.json
  2. 瑾慈：情緒分析&關鍵字擷取\\input\\nvda_extracted_qna_translation.json
  3. 瑾慈：情緒分析&關鍵字擷取\\input\\foxconn_extracted_qna_translation.json

同資料夾內還需有對應的 full 逐字稿（檔名把 extracted_qna 換成 full_transcript）：
  tsmc_full_transcript_translation.json、nvda_full_transcript_translation.json、
  foxconn_full_transcript_translation.json

用法（在「浩誠_回答品質評分」目錄下）：
  python run_from_json.py
  python run_from_json.py --input-dir "..\\瑾慈：情緒分析&關鍵字擷取\\input"
  python run_from_json.py --qna-json "..\\瑾慈：情緒分析&關鍵字擷取\\input\\tsmc_extracted_qna_translation.json"
  python run_from_json.py --reference "..\\某前次摘要.txt"   # 可選，強化「一致性」
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from json_transcript import (
    full_transcript_path_for_qna,
    load_qna_pairs,
    presentation_text_from_full_transcript,
    stem_from_qna_filename,
)
from metrics import session_scores
from radar_chart import plot_transparency_radar


def _default_input_dir() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / "瑾慈：情緒分析&關鍵字擷取" / "input"


def _iter_qna_json_files(input_dir: Path) -> list[Path]:
    if not input_dir.is_dir():
        return []
    return sorted(input_dir.glob("*_extracted_qna_translation.json"))


def _radar_dict(scores: dict) -> dict:
    out = {k: scores[k] for k in ("直接性", "具體性", "迴避度", "語氣落差", "一致性") if k in scores}
    if "綜合透明度" in scores:
        out["綜合透明度"] = scores["綜合透明度"]
    return out


def run_one(
    qna_json: Path,
    *,
    full_json: Path | None,
    reference_text: str | None,
    out_dir: Path,
) -> dict:
    pairs = load_qna_pairs(qna_json)
    if not pairs:
        raise SystemExit(f"沒有讀到任何 Q&A：{qna_json}")

    full_path = full_json if full_json is not None else full_transcript_path_for_qna(qna_json)
    if not full_path.is_file():
        raise SystemExit(f"找不到逐字稿 JSON（簡報段語氣用）：{full_path}")

    first_q = pairs[0].question
    presentation = presentation_text_from_full_transcript(full_path, first_q)

    scores = session_scores(pairs, presentation, reference_text)
    stem = stem_from_qna_filename(qna_json)

    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{stem}_transparency_radar.png"
    plot_transparency_radar(
        _radar_dict(scores),
        title=f"{stem} 法說會 Q&A 透明度雷達",
        save_path=png,
    )
    js = out_dir / f"{stem}_scores.json"
    with js.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source_qna": str(qna_json),
                "source_full_transcript": str(full_path),
                "qna_pairs": len(pairs),
                "scores": scores,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return {"stem": stem, "png": str(png), "json": str(js), "scores": scores}


def main() -> None:
    ap = argparse.ArgumentParser(description="從 JSON 整檔計算法說會 Q&A 透明度雷達")
    ap.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="含 *_extracted_qna_translation.json 的資料夾（預設：專案內瑾慈/input）",
    )
    ap.add_argument(
        "--qna-json",
        type=Path,
        default=None,
        help="只處理單一 Q&A JSON（若指定則忽略 --input-dir 批次）",
    )
    ap.add_argument(
        "--full-json",
        type=Path,
        default=None,
        help="逐字稿 JSON 路徑（預設依檔名自動對應 full_transcript）",
    )
    ap.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="可選：前次法說或參考敘述的 .txt（UTF-8），供一致性維度使用",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="輸出目錄（預設：本模組下的 output/batch_from_json）",
    )
    args = ap.parse_args()

    ref_text: str | None = None
    if args.reference is not None:
        ref_text = args.reference.read_text(encoding="utf-8").strip() or None

    out_dir = args.out_dir or (Path(__file__).resolve().parent / "output" / "batch_from_json")

    if args.qna_json is not None:
        paths = [args.qna_json.resolve()]
    else:
        input_dir = (args.input_dir or _default_input_dir()).resolve()
        paths = _iter_qna_json_files(input_dir)
        if not paths:
            raise SystemExit(f"在資料夾找不到 *_extracted_qna_translation.json：{input_dir}")

    print("將處理以下 Q&A 檔：")
    for p in paths:
        print(f"  - {p}")
    print()

    full_override = args.full_json if len(paths) == 1 else None
    if args.full_json is not None and len(paths) > 1:
        print("注意：批次模式會依各檔自動配對 full_transcript，已忽略 --full-json。\n")

    for p in paths:
        info = run_one(p, full_json=full_override, reference_text=ref_text, out_dir=out_dir)
        s = info["scores"]
        print(f"[{info['stem']}] 五維與綜合：")
        for k in ("直接性", "具體性", "迴避度", "語氣落差", "一致性", "綜合透明度"):
            if k in s:
                print(f"  {k}: {s[k]}")
        print(f"  雷達圖：{info['png']}")
        print(f"  分數 JSON：{info['json']}")
        print()


if __name__ == "__main__":
    main()
