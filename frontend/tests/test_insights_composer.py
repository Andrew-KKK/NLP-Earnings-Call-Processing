import services.insights_composer as composer
from services.insights_composer import compose_rule_list


def _row(idx, label, topic, downplay=False):
    return {
        "index": idx,
        "risk_label": label,
        "risk_label_zh": {"direct": "直接回答", "vague": "模糊回答",
                          "evasive": "迴避回答", "tone_shift": "語氣轉變"}[label],
        "topic": topic,
        "_signals": {"risk_downplay_flag": downplay},
    }


def test_rule_list_flags_evasive_and_tone_shift_rows():
    rows = [
        _row(1, "direct", "AI 需求"),
        _row(2, "evasive", "資本支出"),
        _row(3, "tone_shift", "地緣風險"),
        _row(4, "vague", "毛利率"),
    ]
    out = compose_rule_list(
        scores={"綜合透明度": 80.0},
        qna_rows=rows,
        tone_shift_flag=False,
        negative_score_shift=0.0,
    )
    track = out["worth_tracking"]
    assert [item["index"] for item in track] == [2, 3]
    assert all("第" in item["bullet"] for item in track)


def test_disclosure_risks_low_transparency_and_tone_shift_and_downplay():
    rows = [_row(1, "evasive", "x", downplay=True)]
    out = compose_rule_list(
        scores={"綜合透明度": 42.0},
        qna_rows=rows,
        tone_shift_flag=True,
        negative_score_shift=0.18,
    )
    bullets = out["disclosure_risks"]
    joined = " | ".join(b for b in bullets)
    assert "整體透明度偏低" in joined
    assert "語氣較簡報" in joined
    assert "弱化訊號" in joined


def test_empty_when_no_signals():
    rows = [_row(1, "direct", "x")]
    out = compose_rule_list(
        scores={"綜合透明度": 90.0},
        qna_rows=rows,
        tone_shift_flag=False,
        negative_score_shift=0.0,
    )
    assert out["worth_tracking"] == []
    assert out["disclosure_risks"] == []


def test_compose_headline_uses_gemini(monkeypatch):
    class _FakeResponse:
        text = "整體透明度尚佳，但資本支出題明顯迴避。"

    class _FakeModel:
        last_payload = None
        def generate_content(self, prompt, generation_config=None):
            _FakeModel.last_payload = prompt
            return _FakeResponse()

    monkeypatch.setattr(composer, "_HeadlineModel", lambda *_a, **_k: _FakeModel())
    payload = {
        "company": "tsmc",
        "transparency": 78,
        "tone_shift_flag": False,
        "worst_qna": {"index": 2, "topic": "資本支出", "label": "迴避", "score": 41},
        "flagged_count": 1,
    }
    headline = composer.compose_headline(payload, api_key="g", model="gemini-2.0-flash")
    assert "資本支出" in headline
    assert "tsmc" in _FakeModel.last_payload or "78" in _FakeModel.last_payload


def test_compose_headline_returns_empty_without_api_key():
    payload = {"company": "x", "transparency": 0, "tone_shift_flag": False,
               "worst_qna": None, "flagged_count": 0}
    assert composer.compose_headline(payload, api_key="", model="x") == ""
