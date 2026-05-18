# -*- coding: utf-8 -*-
"""
法說會 Q&A 五維指標（0–100）。

直接性、具體性、一致性：數值越高通常對投資人越有利。
迴避度、語氣落差：數值越高代表越迴避／簡報與 Q&A 在詞表語氣軸上差異越大（語氣落差為相對「最相反語氣」的百分比，見 tone_shift_score）。

「訊號不足」的中性分統一為 NEUTRAL_SCORE（50），與各維度實際量到的 0 或低分區隔較清楚。

綜合透明度：將迴避度、語氣落差以「100 − 該分」納入後再做平均，故仍為越高越透明。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

try:
    import jieba.analyse as _jieba_analyse

    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False

_HEDGE_PHRASES = (
    "不便評論",
    "不便透露",
    "無法評論",
    "無法預測",
    "視情況而定",
    "持續觀察",
    "密切關注",
    "有信心",
    "穩健成長",
    "審慎樂觀",
    "不予置評",
    "以公告為準",
    "請參考簡報",
    "之後再說明",
    "尚待評估",
    "無法提供",
    "不方便說明",
)

_POS_WORDS = (
    "強勁",
    "樂觀",
    "成長",
    "突破",
    "新高",
    "大幅",
    "顯著",
    "亮眼",
    "優於預期",
    "充滿信心",
)
_NEG_WORDS = (
    "下滑",
    "衰退",
    "保守",
    "趨緩",
    "壓力",
    "挑戰",
    "不明",
    "風險",
    "下修",
    "不如預期",
)

# 無法可靠量測時的中性分（與「量到很低／零」區隔）
NEUTRAL_SCORE = 50.0


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _normalize_tokens(text: str) -> list[str]:
    t = re.sub(r"\s+", " ", text.strip())
    if not t:
        return []
    if _HAS_JIEBA:
        return _jieba_analyse.extract_tags(t, topK=12, withWeight=False)
    chars = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", t)
    ngrams: list[str] = []
    for n in (4, 3, 2):
        if len(chars) < n:
            continue
        for i in range(0, len(chars) - n + 1, max(1, n // 2)):
            ngrams.append(chars[i : i + n])
    return list(dict.fromkeys(ngrams))[:20]


def _count_hits(haystack: str, needles: Iterable[str]) -> int:
    return sum(1 for w in needles if w and w in haystack)


def _pos_neg_lexicon_counts(text: str) -> tuple[int, int]:
    if not text.strip():
        return 0, 0
    return _count_hits(text, _POS_WORDS), _count_hits(text, _NEG_WORDS)


def _laplace_tone_axis(p: int, n: int, *, smooth: float = 1.0) -> float:
    """正／負向詞命中數經拉普拉斯平滑後的語氣軸，約在 (-1, 1)，可比較兩段文本。"""
    ps = float(p + smooth)
    ns = float(n + smooth)
    return (ps - ns) / (ps + ns)


def _specificity_signals(answer: str) -> float:
    if not answer.strip():
        return 0.0
    score = 0.0
    score += min(40, len(re.findall(r"\d+(?:\.\d+)?%?", answer)) * 8)
    score += min(20, len(re.findall(r"\d+\s*[-~～至到]\s*\d+", answer)) * 10)
    time_hits = _count_hits(
        answer,
        ("Q1", "Q2", "Q3", "Q4", "FY", "明年", "下季", "本季", "年底", "上半年", "下半年"),
    )
    score += min(20, time_hits * 4)
    year_tags = len(re.findall(r"(?:19|20)\d{2}", answer))
    score += min(16, year_tags * 4)
    if re.search(r"因為|由於|主要來自|原因在於", answer):
        score += 10
    if re.search(r"預估|預期|目標|指引|區間", answer):
        score += 10
    score -= min(30, _count_hits(answer, _HEDGE_PHRASES) * 6)
    return score


def _evasion_index(question: str, answer: str) -> float:
    if not answer.strip():
        return 100.0
    q_tokens = set(_normalize_tokens(question))
    a_lower = answer
    overlap = sum(1 for t in q_tokens if len(t) >= 2 and t in a_lower)
    overlap_score = 100.0 * (1.0 - min(1.0, overlap / max(3, len(q_tokens) or 1)))
    hedge = min(50.0, _count_hits(answer, _HEDGE_PHRASES) * 10)
    short_penalty = 25.0 if len(answer) < 25 and "?" not in question and "？" not in question else 0.0
    if len(answer) < 15:
        short_penalty = max(short_penalty, 15.0)
    return _clip(0.55 * overlap_score + 0.35 * hedge + 0.10 * short_penalty)


def directness_score(question: str, answer: str) -> float:
    """直接性：回答是否覆蓋問題中的關鍵主題（關鍵詞重疊）。"""
    q_tokens = [t for t in _normalize_tokens(question) if len(t) >= 2]
    if not q_tokens:
        return NEUTRAL_SCORE
    hits = sum(1 for t in q_tokens if t in answer)
    base = 100.0 * hits / len(q_tokens)
    return _clip(base)


def specificity_score(answer: str) -> float:
    """具體性：數字、時間、因果、指引等可驗證訊號。"""
    raw = _specificity_signals(answer)
    return _clip(12.0 * math.sqrt(max(0.0, raw + 5.0)))


def evasion_score(question: str, answer: str) -> float:
    """迴避度 0–100：越高代表越迴避／偏題／官腔代理訊號越強（不從 100 反扣）。"""
    return _clip(_evasion_index(question, answer))


def tone_shift_score(presentation_text: str, qa_block_text: str) -> float:
    """
    語氣落差評分：
    1. 計算簡報與 Q&A 的原始情緒得分差。
    2. 印出原始差值供使用者參考評分標準。
    3. 回傳 0, 20, 40, 60, 80, 100 六個等級之一。
    """
    
    # --- 步驟 1: 定義情緒計算邏輯 ---
    # 如果你有現成的模型（如瑾慈做的），請把這裡換成呼叫模型的代碼
    def get_positivity_score(text):
        if not text: return 0.0
        # 這裡僅為示意：實際應串接你們的情緒分析模組
        # 假設正向詞越多分數越高 (0~1)
        pos_words = ['strong', 'growth', 'confident', 'positive', 'excellent', '成長', '信心']
        words = text.lower()
        score = sum(1 for w in pos_words if w in words) / (len(words.split()) + 1)
        return min(1.0, score * 10) # 放大分數便於觀察

    # --- 步驟 2: 計算原始數值 ---
    r_prep = get_positivity_score(presentation_text) # 簡報正向度
    r_qa = get_positivity_score(qa_block_text)       # Q&A 正向度
    
    # 原始差值 (Raw Shift)
    raw_shift = r_prep - r_qa
    

    # --- 步驟 3: 根據原始差值進行六級分評分 ---
    # 你可以根據上面印出的 raw_shift 來微調下方的 0.05, 0.10 等門檻
    if raw_shift <= 0:
        final_score = 100.0  # Q&A 比簡報更樂觀或一致
    elif raw_shift <= 0.05:
        final_score = 80.0   # 穩定
    elif raw_shift <= 0.10:
        final_score = 60.0   # 輕微轉向
    elif raw_shift <= 0.20:
        final_score = 40.0   # 明顯保守
    elif raw_shift <= 0.30:
        final_score = 20.0   # 高度警示
    else:
        final_score = 0.0    # 極端落差 (變臉)# 計算絕對值差，因為「過正」或「過負」都代表語氣不一致
    abs_shift = abs(raw_shift) 

    if abs_shift <= 0.03:
        return 100.0  # 極度穩定（如：鴻海）
    elif abs_shift <= 0.07:
        return 80.0   # 輕微落差
    elif abs_shift <= 0.12:
        return 60.0   # 明顯波動（如：台積電、輝達會落在這）
    elif abs_shift <= 0.20:
        return 40.0   # 語氣大變
    else:
        return 20.0   # 極端不一致
        
    return final_score

def consistency_score(answer: str, reference_text: str | None = None) -> float:
    """
    一致性：回答用語／敘事與「參考文本」關鍵詞是否對齊，並對明顯負向轉折詞組扣分。

    注意：若呼叫端未提供參考文本，本函式回傳 NEUTRAL_SCORE。
    整場層級的「無外部稿」一致性請見 `session_internal_consistency_average`，
    由 `session_scores` 在沒有 reference_text 時自動改算。
    """
    if not reference_text or not reference_text.strip():
        return NEUTRAL_SCORE
    ref_keywords = [t for t in _normalize_tokens(reference_text) if len(t) >= 2]
    if not ref_keywords:
        return NEUTRAL_SCORE
    hits = sum(1 for t in ref_keywords if t in answer)
    base = 100.0 * hits / len(ref_keywords)
    contra_hits = _count_hits(
        answer + reference_text,
        ("下修", "不如預期", "衰退", "不如先前"),
    )
    base -= min(40.0, contra_hits * 12.0)
    return _clip(base)


def session_internal_consistency_average(
    pairs: Sequence[QAPair],
    presentation_text: str,
) -> float:
    """
    無「前次法說／外部參考稿」時的場內一致性（會有區間、公司之間可區分）：

    - 多組 Q&A：每一題以「同場其他所有回答」當參考（leave-one-out），
      看本題回答是否仍落在整場管理層敘事主軸（關鍵詞重疊）上。
    - 僅一組 Q&A：改以「簡報段」當參考，看單一回答是否銜接官方說法。
    - 僅一組且簡報為空：維持中性 NEUTRAL_SCORE。
    """
    if not pairs:
        return NEUTRAL_SCORE
    pres = (presentation_text or "").strip()

    if len(pairs) == 1:
        if not pres:
            return NEUTRAL_SCORE
        return float(consistency_score(pairs[0].answer, pres))

    vals: list[float] = []
    for i, p in enumerate(pairs):
        others = "\n".join(
            pr.answer for j, pr in enumerate(pairs) if j != i and pr.answer.strip()
        )
        ref = (others.strip() or pres or "").strip() or None
        vals.append(consistency_score(p.answer, ref))
    return float(sum(vals) / len(vals))


@dataclass
class QAPair:
    question: str
    answer: str


def aggregate_scores(pairs: Sequence[QAPair]) -> dict[str, float]:
    """多組 Q&A 平均：直接性、具體性、迴避度（語氣落差與一致性於 session_scores 補上）。"""
    if not pairs:
        return {
            "直接性": 0.0,
            "具體性": 0.0,
            "迴避度": 0.0,
            "語氣落差": 0.0,
            "一致性": 0.0,
        }
    d = sum(directness_score(p.question, p.answer) for p in pairs) / len(pairs)
    s = sum(specificity_score(p.answer) for p in pairs) / len(pairs)
    e = sum(evasion_score(p.question, p.answer) for p in pairs) / len(pairs)
    return {
        "直接性": round(d, 1),
        "具體性": round(s, 1),
        "迴避度": round(e, 1),
        "語氣落差": 0.0,
        "一致性": 0.0,
    }


def session_scores(
    pairs: Sequence[QAPair],
    presentation_text: str,
    reference_text: str | None = None,
) -> dict[str, float]:
    base = aggregate_scores(pairs)
    qa_blob = "\n".join(p.answer for p in pairs)
    base["語氣落差"] = round(tone_shift_score(presentation_text, qa_blob), 1)
    if reference_text and reference_text.strip():
        c = sum(consistency_score(p.answer, reference_text) for p in pairs) / len(pairs)
        base["一致性"] = round(c, 1)
    else:
        base["一致性"] = round(session_internal_consistency_average(pairs, presentation_text), 1)
    base["綜合透明度"] = composite_transparency_score(base)
    return base


def composite_transparency_score(
    session: Mapping[str, float],
) -> float:
    """
    綜合透明度（0–100）：越高代表整體越透明、越有利解讀。

    直接性、具體性、一致性為「越高越好」；迴避度、語氣落差為「越高越不利」，
    故綜合分使用 (100 − 迴避度)、(100 − 語氣落差) 與前三項平均。
    """
    d = float(session.get("直接性", 0.0))
    s = float(session.get("具體性", 0.0))
    c = float(session.get("一致性", NEUTRAL_SCORE))
    ev = float(session.get("迴避度", 0.0))
    gap = float(session.get("語氣落差", 0.0))
    raw = (d + s + c + (100.0 - ev) + (100.0 - gap)) / 5.0
    return round(_clip(raw), 1)


def session_scores_with_composite(
    pairs: Sequence[QAPair],
    presentation_text: str,
    reference_text: str | None = None,
) -> dict[str, float]:
    """與 session_scores 相同（已內含綜合透明度）；保留函式名供舊程式相容。"""
    return session_scores(pairs, presentation_text, reference_text)


# 舊名稱相容
session_scores_with_risk = session_scores_with_composite
