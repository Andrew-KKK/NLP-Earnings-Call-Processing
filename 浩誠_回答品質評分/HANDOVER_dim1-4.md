# Handover — 浩誠 scoring revision, dimensions 1–4

You are implementing **4 of 5** dimensions of the revised 法說會 Q&A scoring system.
Owner is doing dim 5 (`前瞻可行性`, LLM-based) and assembling the composite.

**Ground rules**
- All scores are 0–100, **higher = better** (no inversions).
- Each dimension = mean of its named sub-signals.
- **Fail loudly** if any required upstream file is missing, empty, or a stub. The error message must name the offending file and dimension.
- Touch only files inside `浩誠_回答品質評分/`. Do not modify `frontend/` or any teammate's module.

---

## 1. Project layout

Project root: `/Users/marktsai/Desktop/Projects/自然語言處理_期末專案`

Companies: `tsmc`, `nvda`, `foxconn` (substitute as `{co}` below).

### Upstream files to read

| Used by | Path (relative to project root) |
|---|---|
| dims 1, 3, 4 | `瑾慈：情緒分析&關鍵字擷取/keyphrase_output/{co}/qna_keyphrase_summary.json` |
| dims 1, 4 | `瑾慈：情緒分析&關鍵字擷取/keyphrase_output/{co}/topic_emphasis_summary.json` |
| dim 3 | `瑾慈：情緒分析&關鍵字擷取/sentiment_output/{co}/qna_sentiment_summary.json` |
| dims 3, 4 | `瑾慈：情緒分析&關鍵字擷取/sentiment_output/{co}/section_sentiment_summary.json` |
| dim 3 | `瑾慈：情緒分析&關鍵字擷取/sentiment_output/{co}/company_tone_shift_summary.json` |
| dims 2, 4 | `奕寧_ 摘要&PII/output/{co}_full_transcript_translation_pii_summary.json` |

> ⚠️ **TSMC stub**: 奕寧's TSMC file is currently `{"summary":["S1"],"pii_redacted_full":["X"]}`. Treat any `summary == ["S1"]` (or empty) as missing and fail loudly. 奕寧 must re-run before TSMC can be scored.

---

## 2. Sub-signal formulas

### Dimension 1 — `直接性` (answer addresses the question)

| Sub-signal | Formula |
|---|---|
| `mean_overlap_ratio` | `mean(qna_keyphrase_summary.qna_results[*].overlap_ratio) × 100` |
| `topic_match_rate` | `(1 − mean(qna_keyphrase_summary.qna_results[*].topic_mismatch_flag)) × 100` |
| `cross_section_topic_overlap` | Let `Q` = top-N topics by frequency in `topic_emphasis_summary` where `section_type == "question"` (N = min(10, available)); `A` = same for `"answer"`. Score = `|Q ∩ A| / N × 100` |

`直接性 = mean(3 sub-signals)`

### Dimension 2 — `具體性` (answer carries concrete information)

| Sub-signal | Formula |
|---|---|
| `prep_anchor_coverage` | Let `S` = lowercased concatenation of 奕寧 `summary` sentences. For each Q&A pair, hit if any of its `answer_key_phrases` (lowercased) appears as a substring of `S`. Score = `(hits / total_pairs) × 100` |
| `answer_keyphrase_density` | `min(mean(qna_keyphrase_summary.qna_results[*].answer_key_phrase_count), 8) × 12.5` |
| `answer_topic_richness` | `min(count of topic_emphasis_summary rows where section_type == "answer" AND frequency ≥ 2, 8) × 12.5` |

`具體性 = mean(3 sub-signals)`

### Dimension 3 — `坦誠度` (management answers without dodging or shifting tone)

Compute **`主題坦誠`** and **`語氣坦誠`** separately, then `坦誠度 = mean(主題坦誠, 語氣坦誠)`.

**`主題坦誠` = mean of:**

| Sub-signal | Formula |
|---|---|
| `non_risk_downplay_rate` | `(1 − mean(qna_sentiment_summary.qna_results[*].risk_downplay_flag)) × 100` |
| `non_soft_answer_rate` | `(1 − mean(qna_sentiment_summary.qna_results[*].negative_question_soft_answer_flag)) × 100` |
| `on_topic_rate` | `(1 − mean(qna_keyphrase_summary.qna_results[*].topic_mismatch_flag)) × 100` |

**`語氣坦誠` = mean of:**

| Sub-signal | Formula |
|---|---|
| `pos_shift_stability` | `max(0, 100 − abs(company_tone_shift_summary.tone_shift_results[0].positive_score_shift) × 200)` |
| `neg_shift_stability` | `max(0, 100 − abs(negative_score_shift) × 200)` |
| `section_sentiment_alignment` | Let `Δpos = abs(prep.positive_score − answer.positive_score)`, `Δneg = abs(prep.negative_score − answer.negative_score)` (from `section_sentiment_summary.section_results`). Score = `max(0, 100 − (Δpos + Δneg) × 100)` |

**Hard floor**: if `company_tone_shift_summary.tone_shift_results[0].tone_shift_flag == true`, after computing `語氣坦誠`, cap it at 40.

### Dimension 4 — `一致性` (Q&A narrative aligns with prepared remarks)

| Sub-signal | Formula |
|---|---|
| `summary_keyphrase_overlap` | For each pair, compute fraction of `answer_key_phrases` (lowercased) that appear as substring in lowercased-joined 奕寧 `summary`. Average across pairs × 100 |
| `topic_set_overlap` | Let `P` = top-N topics for `section_type == "prepared"` (N = min(10, available)); `A` = same for `"answer"`. Score = `|P ∩ A| / N × 100` |
| `section_sentiment_direction_match` | Dominant sentiment of prep vs answer = `argmax(positive_score, neutral_score, negative_score)` from `section_sentiment_summary`. Score = 100 if same; 50 if drift one step (positive↔neutral or neutral↔negative); 0 if opposite (positive↔negative) |

`一致性 = mean(3 sub-signals)`

---

## 3. Required output

Write to `浩誠_回答品質評分/output/batch_from_json/{co}_scores.json`. All numeric values **rounded to 1 decimal**. Owner will fold in `前瞻可行性` and `綜合透明度` later.

```json
{
  "source_qna": "...",
  "source_full_transcript": "...",
  "qna_pairs": 25,
  "scores": {
    "直接性": 46.2,
    "具體性": 38.1,
    "坦誠度": 51.0,
    "一致性": 44.7
  },
  "sub_signals": {
    "直接性": {
      "mean_overlap_ratio": 23.0,
      "topic_match_rate": 60.0,
      "cross_section_topic_overlap": 55.6
    },
    "具體性": {
      "prep_anchor_coverage": 30.0,
      "answer_keyphrase_density": 42.5,
      "answer_topic_richness": 41.7
    },
    "坦誠度": {
      "主題坦誠": {
        "non_risk_downplay_rate": 84.0,
        "non_soft_answer_rate": 96.0,
        "on_topic_rate": 40.0
      },
      "語氣坦誠": {
        "pos_shift_stability": 95.9,
        "neg_shift_stability": 93.0,
        "section_sentiment_alignment": 90.5
      }
    },
    "一致性": {
      "summary_keyphrase_overlap": 35.0,
      "topic_set_overlap": 50.0,
      "section_sentiment_direction_match": 100.0
    }
  }
}
```

---

## 4. Required API

Add to `metrics.py`:

```python
from pathlib import Path

def compute_dimensions_1_to_4(
    company_slug: str,
    *,
    project_root: Path,
) -> dict:
    """
    Returns:
      {
        "scores": {"直接性": float, "具體性": float, "坦誠度": float, "一致性": float},
        "sub_signals": {...}  # exact shape per Section 3
      }
    Raises:
      FileNotFoundError if any required upstream file is missing.
      ValueError       if a required file is empty/stub (e.g., 奕寧 summary == ["S1"]).
    """
```

---

## 5. Code-change scope

Modify **only** these files inside `浩誠_回答品質評分/`:

- `metrics.py` — replace the 5 legacy dimension functions with the new logic; delete `tone_shift_score`, `_POS_WORDS`, `_NEG_WORDS`, and the buggy unreachable code in the old `tone_shift_score`.
- `radar_chart.py` — set `RADAR_KEYS = ("直接性", "具體性", "坦誠度", "一致性")` and update `RADAR_LABELS` to match. Owner will extend to 5 later.
- `run_from_json.py` — call `compute_dimensions_1_to_4()` and write the new JSON shape from Section 3.
- `requirements.txt` — no new dependencies are needed for dims 1–4.

Do **not** touch:
- `frontend/`
- The composite `綜合透明度` (owner will add after dim 5).
- Anyone else's modules.

---

## 6. Acceptance criteria

1. `python run_from_json.py` produces a complete `{co}_scores.json` (per Section 3) for `nvda` and `foxconn`.
2. For `tsmc`, the run fails loudly with a clear error naming 奕寧's stub summary file.
3. `output/batch_from_json/{co}_transparency_radar.png` shows a clean 4-spoke radar for `nvda` and `foxconn`.
4. One unit test with a synthetic upstream fixture verifying each sub-signal formula on a hand-computable example.

---

## 7. Notes / pitfalls

- Substring matching for `prep_anchor_coverage` and `summary_keyphrase_overlap` should be **case-insensitive** and treat both sides as the same script (don't romanize CJK). A simple `phrase.lower() in summary_joined.lower()` is sufficient.
- For `cross_section_topic_overlap` / `topic_set_overlap`, when fewer than 10 topics of a given `section_type` exist, set `N = available` and proceed (don't pad).
- For the `tone_shift_flag` floor, apply it **after** averaging the three `語氣坦誠` sub-signals, not to individual sub-signals.
- The 奕寧 file's `summary` field is only populated for the **full transcript** PII-summary file, not the Q&A PII-summary file. Use the full-transcript one for both dims 2 and 4.
- Round at the **leaf** (1 decimal) only when serializing; do the arithmetic with full precision internally.
