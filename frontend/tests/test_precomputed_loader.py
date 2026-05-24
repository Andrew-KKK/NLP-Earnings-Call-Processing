import pytest

from services.case_registry import find_case
from services.precomputed_loader import load_case_bundle, _clean_summary


def test_clean_summary_filters_placeholders_and_blanks():
    assert _clean_summary({"summary": ["S1"]}) == []          # bare placeholder id
    assert _clean_summary({"summary": ["  ", "S2", "真正的摘要句。"]}) == ["真正的摘要句。"]
    assert _clean_summary({"summary": []}) == []
    assert _clean_summary(None) == []
    assert _clean_summary({}) == []


def test_full_summary_loaded_and_clean_for_foxconn():
    bundle = load_case_bundle(find_case("foxconn"))
    assert isinstance(bundle.full_summary, list)
    assert len(bundle.full_summary) >= 1
    assert all(isinstance(s, str) and s.strip() for s in bundle.full_summary)


@pytest.mark.parametrize("slug", ["tsmc", "nvda", "foxconn"])
def test_loads_known_companies(slug):
    info = find_case(slug)
    assert info is not None
    bundle = load_case_bundle(info)
    assert bundle.slug == slug
    assert bundle.scores["綜合透明度"] is not None
    assert isinstance(bundle.qna_rows, list)
    assert len(bundle.qna_rows) > 0
    row = bundle.qna_rows[0]
    assert "question_translated" in row
    assert "answer_translated" in row
    assert "risk_label" in row
    assert "composite_score" in row
    assert "topic" in row


def test_tone_pill_present_for_tsmc():
    info = find_case("tsmc")
    bundle = load_case_bundle(info)
    assert bundle.tone_pill["variant"] in {"stable", "shifted"}
    assert bundle.tone_pill["text"]
