from pathlib import Path

import pytest

from adapters.haocheng_adapter import run as run_haocheng
from services.case_registry import find_case


def test_haocheng_runs_on_tsmc(tmp_path):
    info = find_case("tsmc")
    out_dir = tmp_path / "tsmc"
    result = run_haocheng(qna_json=info.qna_json, full_json=info.full_json, out_dir=out_dir)
    assert (out_dir / "scores.json").exists()
    assert (out_dir / "transparency_radar.png").exists()
    assert result["scores"]["綜合透明度"] >= 0
    assert "直接性" in result["scores"]
