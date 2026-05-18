"""Thin wrapper around 浩誠/run_from_json.run_one — no upstream modifications.

Forces matplotlib's non-interactive ``agg`` backend before importing the
upstream radar_chart module. The team source defaults to the platform GUI
backend, which on macOS refuses to render off the main thread — uvicorn runs
this adapter on a worker thread via asyncio.to_thread, so we'd hit
``RuntimeError: Cannot create a GUI FigureManager outside the main thread``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("agg")

from adapters._shared import added_sys_path, chdir, team_root

HAOCHENG_ROOT = "浩誠_回答品質評分"


def run(*, qna_json: Path, full_json: Path, out_dir: Path) -> dict[str, Any]:
    """Compute the 5-dim + 綜合透明度 scores and write JSON + radar PNG to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    src = team_root(HAOCHENG_ROOT)

    with added_sys_path(src), chdir(src):
        from run_from_json import run_one  # type: ignore

        result = run_one(
            qna_json=Path(qna_json),
            full_json=Path(full_json),
            reference_text=None,
            out_dir=out_dir,
        )

    # Normalize filenames so loader/case_registry see consistent names.
    stem_png = Path(result["png"])
    stem_json = Path(result["json"])
    target_png = out_dir / "transparency_radar.png"
    target_json = out_dir / "scores.json"
    if stem_png != target_png:
        shutil.move(str(stem_png), target_png)
    if stem_json != target_json:
        shutil.move(str(stem_json), target_json)
    return {"scores": result["scores"], "json": str(target_json), "png": str(target_png)}
