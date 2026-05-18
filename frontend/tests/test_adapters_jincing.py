from pathlib import Path

import pytest

import adapters.jincing_adapter as adapter


def _stub_sentiment_main(tmp_path: Path, monkeypatch):
    """Replace runpy.run_module with a no-op that writes sentiment outputs."""
    def fake_run_module(mod_name, run_name=None):
        sent_dir = tmp_path / "sent_out" / "tsmc"
        sent_dir.mkdir(parents=True, exist_ok=True)
        (sent_dir / "qna_sentiment_summary.json").write_text('{"qna_results": []}', encoding="utf-8")
        (sent_dir / "section_sentiment_summary.json").write_text('{"section_results": []}', encoding="utf-8")
        (sent_dir / "company_tone_shift_summary.json").write_text('{"tone_shift_results": []}', encoding="utf-8")

    monkeypatch.setattr(adapter, "_runpy_run_module", fake_run_module)


def test_sentiment_adapter_writes_three_jsons(tmp_path, monkeypatch):
    _stub_sentiment_main(tmp_path, monkeypatch)
    out_dir = tmp_path / "case-out"
    adapter.run_sentiment(
        qna_json=tmp_path / "fixture_qna.json",
        full_json=tmp_path / "fixture_full.json",
        out_dir=out_dir,
        slug="tsmc",
        sent_out=tmp_path / "sent_out",
    )
    assert (out_dir / "qna_sentiment_summary.json").exists()
    assert (out_dir / "section_sentiment_summary.json").exists()
    assert (out_dir / "company_tone_shift_summary.json").exists()


def test_keyphrase_adapter_writes_two_jsons(tmp_path, monkeypatch):
    def fake_run_module(mod_name, run_name=None):
        kp_dir = tmp_path / "kp_out" / "tsmc"
        kp_dir.mkdir(parents=True, exist_ok=True)
        (kp_dir / "qna_keyphrase_summary.json").write_text('{"qna_results": []}', encoding="utf-8")
        (kp_dir / "topic_emphasis_summary.json").write_text('{"topic_results": []}', encoding="utf-8")

    monkeypatch.setattr(adapter, "_runpy_run_module", fake_run_module)
    out_dir = tmp_path / "case-out-kp"
    adapter.run_keyphrase(
        qna_json=tmp_path / "fixture_qna.json",
        full_json=tmp_path / "fixture_full.json",
        out_dir=out_dir,
        slug="tsmc",
        kp_out=tmp_path / "kp_out",
    )
    assert (out_dir / "qna_keyphrase_summary.json").exists()
    assert (out_dir / "topic_emphasis_summary.json").exists()
