# -*- coding: utf-8 -*-
"""
示範：計算五維分數（0–100）、綜合透明度，並輸出雷達圖至 output/。
執行：在專案根目錄或本資料夾下
  python run_demo.py
"""

from __future__ import annotations

from pathlib import Path

from metrics import QAPair, session_scores
from radar_chart import plot_transparency_radar


def main() -> None:
    presentation = (
        "本季營收創新高，各產品線動能強勁，我們對下半年展望審慎樂觀，"
        "將持續擴大市占並追求顯著成長。"
    )
    reference_prior = (
        "上季法說曾說明客戶需求穩健，預期毛利率維持在 42% 至 45% 區間。"
    )
    pairs = [
        QAPair(
            question="請問本季毛利率變化與原因？未來兩季的指引為何？",
            answer=(
                "毛利率方面，本季約 43.2%，較上季略降 0.8 個百分點，"
                "主要來自產品組合與運費上升。展望下季，我們預估介於 41% 至 44% 區間，"
                "並將透過成本控管與定價策略改善。若匯率波動加大，可能影響實際落點。"
            ),
        ),
        QAPair(
            question="短期終端需求是否出現疲軟？",
            answer=(
                "長期來看產業趨勢仍然正向，我們會持續觀察市場並保持審慎樂觀。"
            ),
        ),
    ]

    scores = session_scores(pairs, presentation, reference_prior)
    print("— 五維分數（0–100）—")
    for k in ("直接性", "具體性", "迴避度", "語氣落差", "一致性", "綜合透明度"):
        if k in scores:
            print(f"  {k}: {scores[k]}")

    out_dir = Path(__file__).resolve().parent / "output"
    out_path = out_dir / "qa_transparency_radar.png"
    radar_scores = {k: scores[k] for k in ("直接性", "具體性", "迴避度", "語氣落差", "一致性")}
    radar_scores["綜合透明度"] = scores.get("綜合透明度")
    plot_transparency_radar(
        radar_scores,
        title="示範：法說會 Q&A 透明度雷達",
        save_path=out_path,
    )
    print(f"\n已輸出雷達圖：{out_path}")


if __name__ == "__main__":
    main()
