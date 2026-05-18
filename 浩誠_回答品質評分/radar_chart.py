# -*- coding: utf-8 -*-
"""五維雷達圖（0–100）。"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "PingFang TC",
    "Noto Sans CJK TC",
    "SimHei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

RADAR_KEYS = ("直接性", "具體性", "迴避度", "語氣落差", "一致性")
RADAR_LABELS = (
    "直接性",
    "具體性",
    "迴避度\n(高=較迴避)",
    "語氣落差\n(最相反%;缺詞表=50)",
    "一致性",
)


def plot_transparency_radar(
    scores: Mapping[str, float],
    title: str = "法說會 Q&A 透明度雷達",
    save_path: str | Path | None = None,
) -> Path | None:
    values = [max(0.0, min(100.0, float(scores.get(k, 0.0)))) for k in RADAR_KEYS]
    angles = np.linspace(0, 2 * math.pi, len(RADAR_LABELS), endpoint=False).tolist()
    values = values + values[:1]
    angles = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    ax.plot(angles, values, "o-", linewidth=2, color="#2c7fb8")
    ax.fill(angles, values, alpha=0.25, color="#2c7fb8")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(RADAR_LABELS, fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="gray")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_title(title, y=1.08, fontsize=12)

    comp = scores.get("綜合透明度")
    if comp is not None:
        fig.text(0.5, 0.02, f"綜合透明度：{comp}", ha="center", fontsize=10, color="#333")

    fig.tight_layout()
    if save_path is not None:
        p = Path(save_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return p
    plt.show()
    return None
