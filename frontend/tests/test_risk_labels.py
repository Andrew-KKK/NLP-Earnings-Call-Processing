import pytest

from services.risk_labels import RiskLabel, derive_risk_label
from services.risk_labels import composite_score


def _sig(**overrides):
    base = {
        "topic_mismatch_flag": False,
        "risk_downplay_flag": False,
        "negative_question_soft_answer_flag": False,
        "tone_gap_label": "aligned",
        "overlap_ratio": 0.6,
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "signals, expected",
    [
        (_sig(topic_mismatch_flag=True), RiskLabel.EVASIVE),
        (_sig(risk_downplay_flag=True), RiskLabel.EVASIVE),
        (_sig(topic_mismatch_flag=True, tone_gap_label="negative_question_positive_answer"), RiskLabel.EVASIVE),
        (_sig(negative_question_soft_answer_flag=True), RiskLabel.TONE_SHIFT),
        (_sig(tone_gap_label="negative_question_positive_answer"), RiskLabel.TONE_SHIFT),
        (_sig(tone_gap_label="positive_question_less_positive_answer"), RiskLabel.TONE_SHIFT),
        (_sig(overlap_ratio=0.39), RiskLabel.VAGUE),
        (_sig(overlap_ratio=0.0), RiskLabel.VAGUE),
        (_sig(overlap_ratio=0.4), RiskLabel.DIRECT),
        (_sig(overlap_ratio=0.95), RiskLabel.DIRECT),
        (_sig(), RiskLabel.DIRECT),
    ],
)
def test_cascade(signals, expected):
    assert derive_risk_label(signals) is expected


def test_label_zh_strings():
    assert RiskLabel.DIRECT.zh == "直接回答"
    assert RiskLabel.VAGUE.zh == "模糊回答"
    assert RiskLabel.EVASIVE.zh == "迴避回答"
    assert RiskLabel.TONE_SHIFT.zh == "語氣轉變"


@pytest.mark.parametrize(
    "overlap, topic_mm, risk_dp, neg_soft, expected",
    [
        (1.0, False, False, False, 100),          # 40 + 40 + 20
        (0.0, False, False, False, 60),           # 0 + 40 + 20
        (0.5, True,  False, False, 50),           # 20 + 10 + 20
        (0.5, False, True,  False, 50),           # 20 + 10 + 20
        (0.5, False, False, True,  35),           # 20 + 40 - wait: 20 + 40 + 5 = 65? recompute
    ],
)
def test_composite_boundary(overlap, topic_mm, risk_dp, neg_soft, expected):
    # Last row sanity: 0.5*40=20; not (mm or dp) → +40; neg_soft True → +5; total 65
    if (overlap, topic_mm, risk_dp, neg_soft) == (0.5, False, False, True):
        expected = 65
    score = composite_score(
        overlap_ratio=overlap,
        topic_mismatch_flag=topic_mm,
        risk_downplay_flag=risk_dp,
        negative_question_soft_answer_flag=neg_soft,
    )
    assert score == expected


def test_composite_rounds_and_clips():
    # Random fractional inputs round correctly
    assert composite_score(overlap_ratio=0.333, topic_mismatch_flag=False,
                           risk_downplay_flag=False,
                           negative_question_soft_answer_flag=False) == round(0.333 * 40 + 40 + 20)


from services.risk_labels import derive_topic


def test_topic_from_keyphrases():
    assert derive_topic(["AI 需求", "毛利率"], "ignored question text") == "AI 需求、毛利率"


def test_topic_single_keyphrase():
    assert derive_topic(["capex"], "Q") == "capex"


def test_topic_more_than_two_keyphrases_only_takes_first_two():
    assert derive_topic(["a", "b", "c", "d"], "Q") == "a、b"


def test_topic_falls_back_to_question_prefix():
    assert derive_topic([], "What is the outlook for capex over the next two years?") == "What is …"


def test_topic_falls_back_handles_short_question():
    assert derive_topic([], "Hi") == "Hi…"


def test_topic_empty_when_both_empty():
    assert derive_topic([], "") == ""


from services.risk_labels import tone_pill


def test_tone_pill_stable():
    pill = tone_pill(False)
    assert pill["text"] == "● 語氣平穩"
    assert pill["variant"] == "stable"


def test_tone_pill_shifted():
    pill = tone_pill(True)
    assert pill["text"] == "⚠ 語氣轉趨保守"
    assert pill["variant"] == "shifted"
