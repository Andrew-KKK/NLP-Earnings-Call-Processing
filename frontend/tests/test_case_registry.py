from pathlib import Path

from services.case_registry import CaseInfo, discover_cases


def test_discover_includes_three_precomputed_companies():
    cases = discover_cases()
    slugs = {c.slug for c in cases}
    assert {"tsmc", "nvda", "foxconn"}.issubset(slugs)


def test_case_info_carries_expected_paths():
    cases = {c.slug: c for c in discover_cases()}
    tsmc = cases["tsmc"]
    assert tsmc.source == "precomputed"
    assert tsmc.qna_json.name == "tsmc_extracted_qna_translation.json"
    assert tsmc.full_json.name == "tsmc_full_transcript_translation.json"
    assert tsmc.scores_json.name == "tsmc_scores.json"
    assert tsmc.radar_png.name == "tsmc_transparency_radar.png"
    assert tsmc.sentiment_dir.name == "tsmc"
    assert tsmc.keyphrase_dir.name == "tsmc"


def test_upload_cases_listed_when_cache_present(tmp_path, monkeypatch):
    from config import get_settings, Settings
    # Override CACHE_DIR via env
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    # Clear cached settings
    import config
    config._settings = None
    # Pre-create an "uploaded" case
    case_dir = tmp_path / "myco"
    case_dir.mkdir()
    (case_dir / "extracted_qna_translation.json").write_text("{}", encoding="utf-8")
    cases = discover_cases()
    config._settings = None  # cleanup for other tests
    upload_slugs = {c.slug for c in cases if c.source == "upload"}
    assert "myco" in upload_slugs
