import asyncio
import json
from pathlib import Path

import services.upload_processor as up
from services.job_store import JobStore, JobStatus


def test_process_calls_all_adapters_and_writes_status(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    import config; config._settings = None

    called: list[str] = []

    def fake_enhong(*, full_text, qna_text, out_dir, slug):
        called.append("enhong")
        out_dir.mkdir(parents=True, exist_ok=True)
        full = out_dir / "full_transcript_translation.json"
        qna = out_dir / "extracted_qna_translation.json"
        full.write_text(json.dumps({"metadata": {}, "content": []}), encoding="utf-8")
        qna.write_text(json.dumps({"metadata": {}, "qna_list": []}), encoding="utf-8")
        return full, qna

    def fake_haocheng(*, qna_json, full_json, out_dir):
        called.append("haocheng")
        (out_dir / "scores.json").write_text(json.dumps({"scores": {"綜合透明度": 80.0}}), encoding="utf-8")
        (out_dir / "transparency_radar.png").write_bytes(b"\x89PNG")
        return {"scores": {"綜合透明度": 80.0}}

    def fake_sentiment(*, qna_json, full_json, out_dir, slug):
        called.append("jincing_sentiment")
        (out_dir / "qna_sentiment_summary.json").write_text("{}", encoding="utf-8")
        (out_dir / "section_sentiment_summary.json").write_text("{}", encoding="utf-8")
        (out_dir / "company_tone_shift_summary.json").write_text("{}", encoding="utf-8")

    def fake_keyphrase(*, qna_json, full_json, out_dir, slug):
        called.append("jincing_keyphrase")
        (out_dir / "qna_keyphrase_summary.json").write_text("{}", encoding="utf-8")
        (out_dir / "topic_emphasis_summary.json").write_text("{}", encoding="utf-8")

    def fake_yining(*, qna_json, full_json, out_dir, slug):
        called.append("yining")
        (out_dir / "pii_summary.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(up.enhong_adapter, "run", fake_enhong)
    monkeypatch.setattr(up.haocheng_adapter, "run", fake_haocheng)
    monkeypatch.setattr(up.jincing_adapter, "run_sentiment", fake_sentiment)
    monkeypatch.setattr(up.jincing_adapter, "run_keyphrase", fake_keyphrase)
    monkeypatch.setattr(up.yining_adapter, "run", fake_yining)

    store = JobStore()
    job = store.create(slug="myco")
    asyncio.run(up.process_upload(
        job_id=job.id,
        store=store,
        full_text="some text",
        qna_text=None,
        slug="myco",
    ))
    assert store.get(job.id).status == JobStatus.DONE
    assert set(called) == {"enhong", "haocheng", "jincing_sentiment", "jincing_keyphrase", "yining"}
    cache = Path(config.get_settings().CACHE_DIR) / "myco"
    assert (cache / "scores.json").exists()
    assert (cache / "status.json").exists()
