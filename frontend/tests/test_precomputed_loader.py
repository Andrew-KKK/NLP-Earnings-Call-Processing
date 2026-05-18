import pytest

from services.case_registry import find_case
from services.precomputed_loader import load_case_bundle


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
