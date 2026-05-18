import json
from pathlib import Path

import adapters.enhong_adapter as adapter


def test_enhong_uses_gemini_when_no_azure_openai(tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "k")
    monkeypatch.setenv("AZURE_TRANSLATOR_REGION", "centralus")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    import config; config._settings = None

    monkeypatch.setattr(
        adapter, "_translate_text", lambda text, target_lang: text + "[translated]"
    )
    monkeypatch.setattr(
        adapter, "_extract_qna_for_chunk",
        lambda chunk: [{"question": "Q? long enough", "answer": "A! long enough"}],
    )

    out_dir = tmp_path / "case-out"
    full_path, qna_path = adapter.run(
        full_text="Operator: Welcome.\nQ? long enough\nA! long enough",
        qna_text="Q? long enough\nA! long enough",
        out_dir=out_dir,
        slug="myco",
    )
    assert full_path.exists() and qna_path.exists()
    full_doc = json.loads(full_path.read_text(encoding="utf-8"))
    qna_doc = json.loads(qna_path.read_text(encoding="utf-8"))
    assert full_doc["metadata"]["total_paragraphs"] >= 1
    assert qna_doc["metadata"]["total_qna_pairs"] == 1
    assert qna_doc["qna_list"][0]["question_translated"].endswith("[translated]")
