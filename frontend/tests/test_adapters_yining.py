from pathlib import Path

import adapters.yining_adapter as adapter


def test_yining_runs_with_mocked_app(tmp_path, monkeypatch):
    def fake_load_and_run(filename):
        # The fake writes an output file at the location 奕寧/app.py would.
        from adapters._shared import team_root
        out = team_root(adapter.YINING_ROOT) / "output" / filename.replace(".json", "_pii_summary.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('{"summary": ["S1"], "pii_redacted_full": ["X"]}', encoding="utf-8")

    monkeypatch.setattr(adapter, "_invoke_app", fake_load_and_run)
    out_dir = tmp_path / "case-out"
    qna = tmp_path / "tsmc_extracted_qna_translation.json"
    qna.write_text('{"qna_list": []}', encoding="utf-8")
    full = tmp_path / "tsmc_full_transcript_translation.json"
    full.write_text('{"content": []}', encoding="utf-8")

    adapter.run(qna_json=qna, full_json=full, out_dir=out_dir, slug="tsmc")
    assert (out_dir / "pii_summary.json").exists()
