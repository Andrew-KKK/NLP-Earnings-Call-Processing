# 法說會分析儀表板 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI dashboard at `frontend/` that surfaces five NLP outputs (Q&A table, risk labels, transparency score, radar, investment insights) for earnings-call transcripts, with a Gemini-backed right-docked chat and an upload flow that runs the team pipeline live.

**Architecture:** Single-process FastAPI app with Jinja2-rendered server-side HTML. Three layers: `routes/` (HTTP), `services/` (orchestration + custom logic), `adapters/` (thin import-only wrappers around the four team modules at `../恩泓 source/`, `../浩誠`, `../瑾慈`, `../奕寧`). Pre-computed JSON is read directly from team output dirs; uploads write into `frontend/data/cache/{slug}/`. Chat and the insights headline use Gemini; Gemini also substitutes for Azure OpenAI in the Q&A extraction step when that key is absent.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, Pydantic v2 + pydantic-settings, python-docx, google-generativeai, requests (for Azure Translator REST calls used by 恩泓 source), azure-ai-textanalytics, openai (only loaded when Azure OpenAI is configured), pytest + pytest-asyncio + httpx + pytest-mock. Frontend assets: Tailwind via CDN, Chart.js + htmx + Alpine.js vendored locally.

---

## Spec reference

This plan implements `frontend/docs/superpowers/specs/2026-05-18-frontend-design.md`. All design decisions, custom-logic rules, error matrix, and visual palette are defined there. Cross-reference section numbers (§) below.

---

## File tree (what each task creates or modifies)

```
frontend/
├── .gitignore                          # Task 1
├── .env.example                        # Task 1
├── requirements.txt                    # Task 1
├── pyproject.toml                      # Task 1
├── README.md                           # Task 32
├── conftest.py                         # Task 1 (pytest sys.path + autouse env)
├── app.py                              # Task 2
├── config.py                           # Task 2
├── routes/
│   ├── __init__.py                     # Task 2
│   ├── pages.py                        # Tasks 23, 24
│   ├── upload.py                       # Task 25
│   ├── chat.py                         # Task 26
│   └── partials.py                     # Task 27
├── services/
│   ├── __init__.py                     # Task 2
│   ├── slug.py                         # Task 3
│   ├── risk_labels.py                  # Tasks 4, 5, 6, 7
│   ├── case_registry.py                # Task 8
│   ├── precomputed_loader.py           # Task 9
│   ├── gemini_qna_extractor.py         # Task 14
│   ├── docx_loader.py                  # Task 16
│   ├── job_store.py                    # Task 17
│   ├── upload_processor.py             # Task 18
│   ├── insights_composer.py            # Tasks 19, 20
│   └── chat_service.py                 # Tasks 21, 22
├── adapters/
│   ├── __init__.py                     # Task 10
│   ├── _shared.py                      # Task 10  (sys.path + chdir helpers)
│   ├── haocheng_adapter.py             # Task 10
│   ├── jincing_adapter.py              # Tasks 11, 12
│   ├── yining_adapter.py               # Task 13
│   └── enhong_adapter.py               # Task 15
├── templates/
│   ├── base.html                       # Task 23
│   ├── index.html                      # Task 23
│   ├── dashboard.html                  # Task 24
│   └── partials/
│       ├── qna_table.html              # Task 27
│       ├── insights.html               # Task 24
│       └── chat_message.html           # Task 26
├── static/
│   ├── app.js                          # Task 28
│   ├── chart.umd.js                    # Task 29 (vendored)
│   ├── htmx.min.js                     # Task 29 (vendored)
│   ├── htmx-sse.js                     # Task 29 (vendored)
│   └── alpine.min.js                   # Task 29 (vendored)
├── data/
│   └── cache/                          # created at runtime
├── tests/
│   ├── __init__.py                     # Task 1
│   ├── test_slug.py                    # Task 3
│   ├── test_risk_labels.py             # Tasks 4–7
│   ├── test_case_registry.py           # Task 8
│   ├── test_precomputed_loader.py      # Task 9
│   ├── test_adapters_haocheng.py       # Task 10
│   ├── test_adapters_jincing.py        # Tasks 11, 12
│   ├── test_adapters_yining.py         # Task 13
│   ├── test_gemini_qna_extractor.py    # Task 14
│   ├── test_adapters_enhong.py         # Task 15
│   ├── test_docx_loader.py             # Task 16
│   ├── test_job_store.py               # Task 17
│   ├── test_upload_processor.py        # Task 18
│   ├── test_insights_composer.py       # Tasks 19, 20
│   ├── test_chat_service.py            # Tasks 21, 22
│   ├── test_routes_pages.py            # Tasks 23, 24
│   ├── test_routes_upload.py           # Task 25
│   ├── test_routes_chat.py             # Task 26
│   ├── test_routes_partials.py         # Task 27
│   ├── test_integration.py             # Task 30
│   └── manual.md                       # Task 31
```

---

## Conventions used in this plan

- **All paths are absolute** under `frontend/` unless prefixed with `../`.
- **All tests use pytest** with collection from `frontend/` (run via `cd frontend && pytest`).
- **All commits are made from `frontend/`** (the repo we init in Task 1).
- **Real fixtures** for pre-computed loader and 浩誠 adapter come from the existing team output directories — no copies needed.
- **External API calls are always mocked in tests** (Gemini, Azure OpenAI, Azure Translator, Azure Language). Real-API verification lives in `tests/manual.md` (Task 31).
- **Conventional commits** for messages: `feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`.

---

# Phase 1 — Project setup

## Task 1: Initialize project skeleton & repo

**Files:**
- Create: `frontend/.gitignore`
- Create: `frontend/.env.example`
- Create: `frontend/requirements.txt`
- Create: `frontend/pyproject.toml`
- Create: `frontend/conftest.py`
- Create: `frontend/tests/__init__.py`

- [ ] **Step 1: Create the directory skeleton**

```bash
cd /Users/marktsai/Desktop/Projects/自然語言處理_期末專案/frontend
mkdir -p routes services adapters templates/partials static data/cache tests
touch routes/__init__.py services/__init__.py adapters/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# Virtualenv
.venv/
venv/
__pycache__/
*.pyc
*.pyo

# Env / secrets
.env

# Runtime cache
data/cache/

# Build / IDE
.pytest_cache/
.ruff_cache/
.mypy_cache/
.DS_Store
.idea/
.vscode/
```

- [ ] **Step 3: Write `.env.example`** (mirrors spec §13; keep keys blank)

```dotenv
# Azure OpenAI — OPTIONAL. If blank, Gemini handles Q&A extraction.
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT=

# Azure Translator — REQUIRED for upload.
AZURE_TRANSLATOR_KEY=
AZURE_TRANSLATOR_REGION=
AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com

# Azure Language — REQUIRED for upload.
AZURE_LANGUAGE_KEY=
AZURE_LANGUAGE_ENDPOINT=

# Gemini — REQUIRED for chat, insights headline, and Q&A fallback.
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

# Paths
PRECOMPUTED_ROOT=..
CACHE_DIR=./data/cache
LOG_LEVEL=INFO
```

- [ ] **Step 4: Write `requirements.txt`**

```
fastapi>=0.110,<1.0
uvicorn[standard]>=0.27
jinja2>=3.1
python-multipart>=0.0.9
python-docx>=1.1
pydantic>=2.6
pydantic-settings>=2.2
google-generativeai>=0.7
requests>=2.31
azure-ai-textanalytics>=5.3
azure-core>=1.30
openai>=1.30
python-dotenv>=1.0
pandas>=2.2

# tests
pytest>=8.0
pytest-asyncio>=0.23
pytest-mock>=3.12
httpx>=0.26
```

- [ ] **Step 5: Write `pyproject.toml`** (minimal — pytest config only)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra -q"
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

- [ ] **Step 6: Write `conftest.py`** (ensures `frontend/` is importable + sets test env)

```python
"""Root conftest: makes the frontend package importable and isolates env per test."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

FRONTEND_ROOT = Path(__file__).resolve().parent
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))


@pytest.fixture(autouse=True)
def _clean_api_env(monkeypatch):
    """Each test starts with no real API keys set."""
    for key in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_TRANSLATOR_KEY",
        "AZURE_TRANSLATOR_REGION",
        "AZURE_LANGUAGE_KEY",
        "AZURE_LANGUAGE_ENDPOINT",
        "GEMINI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
```

- [ ] **Step 7: Create the venv, install, init git**

```bash
cd /Users/marktsai/Desktop/Projects/自然語言處理_期末專案/frontend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
git init -b main
git add .gitignore .env.example requirements.txt pyproject.toml conftest.py routes/__init__.py services/__init__.py adapters/__init__.py tests/__init__.py
git commit -m "chore: initialize frontend project skeleton"
```

Expected: clean working tree, one commit on `main`.

---

## Task 2: FastAPI skeleton + Settings

**Files:**
- Create: `frontend/config.py`
- Create: `frontend/app.py`
- Create: `frontend/tests/test_health.py`

- [ ] **Step 1: Write the failing health-check test**

`frontend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app import app


def test_health_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run it — expect ModuleNotFoundError or AttributeError**

```bash
cd frontend && pytest tests/test_health.py -v
```

Expected: FAIL (`No module named 'app'`).

- [ ] **Step 3: Write `config.py`**

```python
"""Settings loaded from frontend/.env via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Azure OpenAI (optional)
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-08-01-preview"
    AZURE_OPENAI_DEPLOYMENT: str = ""

    # Azure Translator (required for upload)
    AZURE_TRANSLATOR_KEY: str = ""
    AZURE_TRANSLATOR_REGION: str = ""
    AZURE_TRANSLATOR_ENDPOINT: str = "https://api.cognitive.microsofttranslator.com"

    # Azure Language (required for upload)
    AZURE_LANGUAGE_KEY: str = ""
    AZURE_LANGUAGE_ENDPOINT: str = ""

    # Gemini (required for chat + insights + fallback)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Paths
    PRECOMPUTED_ROOT: Path = Path("..")
    CACHE_DIR: Path = Path("./data/cache")
    LOG_LEVEL: str = "INFO"

    def precomputed_root_resolved(self) -> Path:
        root = self.PRECOMPUTED_ROOT
        if not root.is_absolute():
            root = (Path(__file__).resolve().parent / root).resolve()
        return root

    def cache_dir_resolved(self) -> Path:
        cache = self.CACHE_DIR
        if not cache.is_absolute():
            cache = (Path(__file__).resolve().parent / cache).resolve()
        cache.mkdir(parents=True, exist_ok=True)
        return cache

    def has_azure_openai(self) -> bool:
        return bool(self.AZURE_OPENAI_API_KEY and self.AZURE_OPENAI_ENDPOINT and self.AZURE_OPENAI_DEPLOYMENT)

    def has_azure_translator(self) -> bool:
        return bool(self.AZURE_TRANSLATOR_KEY and self.AZURE_TRANSLATOR_REGION)

    def has_azure_language(self) -> bool:
        return bool(self.AZURE_LANGUAGE_KEY and self.AZURE_LANGUAGE_ENDPOINT)

    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

- [ ] **Step 4: Write `app.py`**

```python
"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.LOG_LEVEL)
log = logging.getLogger("frontend")

app = FastAPI(title="法說會分析儀表板")

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run the test, expect PASS**

```bash
cd frontend && pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && git add config.py app.py tests/test_health.py && git commit -m "feat(app): FastAPI skeleton with /health and Settings"
```

---

# Phase 2 — Pure-utility services (no I/O, TDD-friendly)

## Task 3: Slug generation

**Files:**
- Create: `frontend/services/slug.py`
- Create: `frontend/tests/test_slug.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_slug.py`:

```python
import time

import pytest

from services.slug import make_slug


def test_simple_ascii_lowercased():
    assert make_slug("TSMC Q1") == "tsmc-q1"


def test_chinese_stripped():
    # Chinese stripped → falls back to filename stem or timestamp
    assert make_slug("台積電 2026Q1") == "2026q1"


def test_punctuation_collapsed():
    assert make_slug("nvda__Q4!!") == "nvda-q4"


def test_collision_appends_suffix():
    taken = {"tsmc-q1"}
    assert make_slug("TSMC Q1", taken=taken) == "tsmc-q1-2"

    taken.add("tsmc-q1-2")
    assert make_slug("TSMC Q1", taken=taken) == "tsmc-q1-3"


def test_empty_falls_back_to_timestamp(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_700_000_000)
    assert make_slug("") == "case-1700000000"
    assert make_slug("    ") == "case-1700000000"
    assert make_slug("中文") == "case-1700000000"  # Chinese stripped to empty


def test_trims_leading_trailing_dashes():
    assert make_slug("-Foo-") == "foo"
```

- [ ] **Step 2: Run and verify failure**

```bash
cd frontend && pytest tests/test_slug.py -v
```

Expected: collection error (`No module named 'services.slug'`).

- [ ] **Step 3: Implement `services/slug.py`**

```python
"""Slug derivation for case names (URL/path-safe)."""

from __future__ import annotations

import re
import time
from typing import Iterable


def make_slug(name: str, *, taken: Iterable[str] | None = None) -> str:
    """Return a lower-case, ASCII-safe slug. Chinese characters are stripped.

    Falls back to ``case-{unix_timestamp}`` when the cleaned name is empty.
    If ``taken`` is provided and the slug collides, appends ``-2``, ``-3``, ...
    """
    raw = (name or "").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    if not cleaned:
        cleaned = f"case-{int(time.time())}"

    if not taken:
        return cleaned

    taken_set = set(taken)
    if cleaned not in taken_set:
        return cleaned

    n = 2
    while f"{cleaned}-{n}" in taken_set:
        n += 1
    return f"{cleaned}-{n}"
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
cd frontend && pytest tests/test_slug.py -v
```

- [ ] **Step 5: Commit**

```bash
cd frontend && git add services/slug.py tests/test_slug.py && git commit -m "feat(services): slug derivation with collision + timestamp fallback"
```

---

## Task 4: Risk-label cascade (§8.1)

**Files:**
- Create: `frontend/services/risk_labels.py`
- Create: `frontend/tests/test_risk_labels.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_risk_labels.py`:

```python
import pytest

from services.risk_labels import RiskLabel, derive_risk_label


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
```

- [ ] **Step 2: Run and verify failure**

```bash
cd frontend && pytest tests/test_risk_labels.py -v
```

- [ ] **Step 3: Implement `services/risk_labels.py`** (cascade only; other helpers follow in Tasks 5–7)

```python
"""Per-Q&A risk-label, composite score, topic and tone-pill derivation (spec §8)."""

from __future__ import annotations

from enum import Enum
from typing import Mapping


class RiskLabel(str, Enum):
    DIRECT = "direct"
    VAGUE = "vague"
    EVASIVE = "evasive"
    TONE_SHIFT = "tone_shift"

    @property
    def zh(self) -> str:
        return {
            "direct": "直接回答",
            "vague": "模糊回答",
            "evasive": "迴避回答",
            "tone_shift": "語氣轉變",
        }[self.value]

    @property
    def palette_class(self) -> str:
        # Matches Tailwind class names defined in templates/base.html
        return {
            "direct": "risk-direct",
            "vague": "risk-vague",
            "evasive": "risk-evasive",
            "tone_shift": "risk-tone",
        }[self.value]


def derive_risk_label(signals: Mapping[str, object]) -> RiskLabel:
    """Apply the cascade defined in spec §8.1. First match wins."""
    if signals.get("topic_mismatch_flag") or signals.get("risk_downplay_flag"):
        return RiskLabel.EVASIVE
    if signals.get("negative_question_soft_answer_flag") or signals.get("tone_gap_label", "aligned") != "aligned":
        return RiskLabel.TONE_SHIFT
    overlap = float(signals.get("overlap_ratio", 1.0) or 0.0)
    if overlap < 0.4:
        return RiskLabel.VAGUE
    return RiskLabel.DIRECT
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
cd frontend && pytest tests/test_risk_labels.py -v
```

- [ ] **Step 5: Commit**

```bash
cd frontend && git add services/risk_labels.py tests/test_risk_labels.py && git commit -m "feat(risk-labels): cascade derivation (direct/vague/evasive/tone-shift)"
```

---

## Task 5: Per-Q&A composite score (§8.2)

**Files:**
- Modify: `frontend/services/risk_labels.py`
- Modify: `frontend/tests/test_risk_labels.py`

- [ ] **Step 1: Add failing tests to `tests/test_risk_labels.py`**

Append:

```python
from services.risk_labels import composite_score


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
```

- [ ] **Step 2: Run tests — expect failure (composite_score undefined)**

```bash
cd frontend && pytest tests/test_risk_labels.py -v
```

- [ ] **Step 3: Append to `services/risk_labels.py`**

```python
def composite_score(
    *,
    overlap_ratio: float,
    topic_mismatch_flag: bool,
    risk_downplay_flag: bool,
    negative_question_soft_answer_flag: bool,
) -> int:
    """Per-Q&A composite score 0-100 (spec §8.2)."""
    addressed = float(overlap_ratio or 0.0) * 40
    transparency = 40 if not (topic_mismatch_flag or risk_downplay_flag) else 10
    tone = 20 if not negative_question_soft_answer_flag else 5
    return int(round(addressed + transparency + tone))
```

- [ ] **Step 4: Run tests, expect PASS.**
- [ ] **Step 5: Commit**

```bash
cd frontend && git add services/risk_labels.py tests/test_risk_labels.py && git commit -m "feat(risk-labels): per-Q&A composite score (§8.2)"
```

---

## Task 6: Topic derivation (§8.3)

**Files:**
- Modify: `frontend/services/risk_labels.py`
- Modify: `frontend/tests/test_risk_labels.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_risk_labels.py`:

```python
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
```

- [ ] **Step 2: Run and verify failure.**
- [ ] **Step 3: Append to `services/risk_labels.py`**

```python
def derive_topic(question_key_phrases: list[str], question_text: str) -> str:
    """Short 2-6 char topic tag (spec §8.3). Deterministic; no LLM call."""
    phrases = [p.strip() for p in (question_key_phrases or []) if p and p.strip()]
    if phrases:
        return "、".join(phrases[:2])
    text = (question_text or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return text + "…"
    return text[:8] + "…"
```

- [ ] **Step 4: Run tests, expect PASS.**
- [ ] **Step 5: Commit**

```bash
cd frontend && git add services/risk_labels.py tests/test_risk_labels.py && git commit -m "feat(risk-labels): topic derivation from keyphrases (§8.3)"
```

---

## Task 7: Tone-stability pill (§8.5)

**Files:**
- Modify: `frontend/services/risk_labels.py`
- Modify: `frontend/tests/test_risk_labels.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
from services.risk_labels import tone_pill


def test_tone_pill_stable():
    pill = tone_pill(False)
    assert pill["text"] == "● 語氣平穩"
    assert pill["variant"] == "stable"


def test_tone_pill_shifted():
    pill = tone_pill(True)
    assert pill["text"] == "⚠ 語氣轉趨保守"
    assert pill["variant"] == "shifted"
```

- [ ] **Step 2: Run, expect failure.**
- [ ] **Step 3: Append to `services/risk_labels.py`**

```python
def tone_pill(tone_shift_flag: bool) -> dict[str, str]:
    """Hero pill text + CSS variant key (spec §8.5)."""
    if tone_shift_flag:
        return {"text": "⚠ 語氣轉趨保守", "variant": "shifted"}
    return {"text": "● 語氣平穩", "variant": "stable"}
```

- [ ] **Step 4: Run tests, PASS. Commit.**

```bash
cd frontend && git add services/risk_labels.py tests/test_risk_labels.py && git commit -m "feat(risk-labels): tone-stability pill helper (§8.5)"
```

---

# Phase 3 — Data layer

## Task 8: Case registry

Discovers pre-computed cases by looking for `_extracted_qna_translation.json` files in the 恩泓 team output dir and matching files in the other team output dirs. Also enumerates uploaded cases from `data/cache/`.

**Files:**
- Create: `frontend/services/case_registry.py`
- Create: `frontend/tests/test_case_registry.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from services.case_registry import CaseInfo, discover_cases


def test_discover_includes_three_precomputed_companies():
    cases = discover_cases()
    slugs = {c.slug for c in cases}
    assert {"tsmc", "nvda", "foxconn"}.issubset(slugs)


def test_case_info_carries_expected_paths():
    cases = {c.slug: c for c in discover_cases()}
    tsmc = cases["tsmc"]
    assert tsmc.source == "precomputed"
    assert tsmc.qna_json.name == "tsmc_extracted_qna_translation.json"
    assert tsmc.full_json.name == "tsmc_full_transcript_translation.json"
    assert tsmc.scores_json.name == "tsmc_scores.json"
    assert tsmc.radar_png.name == "tsmc_transparency_radar.png"
    assert tsmc.sentiment_dir.name == "tsmc"
    assert tsmc.keyphrase_dir.name == "tsmc"


def test_upload_cases_listed_when_cache_present(tmp_path, monkeypatch):
    from config import get_settings, Settings
    # Override CACHE_DIR via env
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    # Clear cached settings
    import config
    config._settings = None
    # Pre-create an "uploaded" case
    case_dir = tmp_path / "myco"
    case_dir.mkdir()
    (case_dir / "extracted_qna_translation.json").write_text("{}", encoding="utf-8")
    cases = discover_cases()
    config._settings = None  # cleanup for other tests
    upload_slugs = {c.slug for c in cases if c.source == "upload"}
    assert "myco" in upload_slugs
```

- [ ] **Step 2: Run, expect failure.**
- [ ] **Step 3: Implement `services/case_registry.py`**

```python
"""Discover pre-computed cases (team outputs) and uploaded cases (cache dir)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from config import get_settings

ENHONG_DIR = "恩泓_ 逐字稿翻譯和 Q&A 擷取"
HAOCHENG_DIR = "浩誠_回答品質評分"
JINCING_DIR = "瑾慈：情緒分析&關鍵字擷取"
YINING_DIR = "奕寧_ 摘要&PII"


@dataclass(frozen=True)
class CaseInfo:
    slug: str
    display_name: str
    source: Literal["precomputed", "upload"]
    qna_json: Path
    full_json: Path
    scores_json: Path
    radar_png: Path
    sentiment_dir: Path
    keyphrase_dir: Path
    pii_summary_json: Path

    def all_files_exist(self) -> bool:
        return self.qna_json.exists() and self.full_json.exists()


def discover_cases() -> list[CaseInfo]:
    settings = get_settings()
    root = settings.precomputed_root_resolved()
    cache = settings.cache_dir_resolved()

    cases: list[CaseInfo] = []
    cases.extend(_discover_precomputed(root))
    cases.extend(_discover_uploaded(cache))
    # Stable order
    return sorted(cases, key=lambda c: (c.source != "precomputed", c.slug))


def _discover_precomputed(root: Path) -> list[CaseInfo]:
    enhong = root / ENHONG_DIR
    haocheng = root / HAOCHENG_DIR / "output" / "batch_from_json"
    jincing_sent = root / JINCING_DIR / "sentiment_output"
    jincing_kp = root / JINCING_DIR / "keyphrase_output"
    yining = root / YINING_DIR / "output"

    out: list[CaseInfo] = []
    if not enhong.exists():
        return out
    for qna_path in sorted(enhong.glob("*_extracted_qna_translation.json")):
        slug = qna_path.name.replace("_extracted_qna_translation.json", "")
        full_path = qna_path.with_name(f"{slug}_full_transcript_translation.json")
        out.append(
            CaseInfo(
                slug=slug,
                display_name=slug.upper(),
                source="precomputed",
                qna_json=qna_path,
                full_json=full_path,
                scores_json=haocheng / f"{slug}_scores.json",
                radar_png=haocheng / f"{slug}_transparency_radar.png",
                sentiment_dir=jincing_sent / slug,
                keyphrase_dir=jincing_kp / slug,
                pii_summary_json=yining / f"{slug}_extracted_qna_translation_pii_summary.json",
            )
        )
    return out


def _discover_uploaded(cache: Path) -> list[CaseInfo]:
    out: list[CaseInfo] = []
    if not cache.exists():
        return out
    for case_dir in sorted(p for p in cache.iterdir() if p.is_dir()):
        slug = case_dir.name
        out.append(
            CaseInfo(
                slug=slug,
                display_name=slug,
                source="upload",
                qna_json=case_dir / "extracted_qna_translation.json",
                full_json=case_dir / "full_transcript_translation.json",
                scores_json=case_dir / "scores.json",
                radar_png=case_dir / "transparency_radar.png",
                sentiment_dir=case_dir,
                keyphrase_dir=case_dir,
                pii_summary_json=case_dir / "pii_summary.json",
            )
        )
    return out


def find_case(slug: str) -> CaseInfo | None:
    for c in discover_cases():
        if c.slug == slug:
            return c
    return None
```

- [ ] **Step 4: Run tests, expect PASS.**
- [ ] **Step 5: Commit**

```bash
cd frontend && git add services/case_registry.py tests/test_case_registry.py && git commit -m "feat(case-registry): discover pre-computed + uploaded cases"
```

---

## Task 9: Pre-computed loader

Reads all JSON outputs for a case and returns a `CaseBundle` ready for the dashboard template.

**Files:**
- Create: `frontend/services/precomputed_loader.py`
- Create: `frontend/tests/test_precomputed_loader.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run, expect failure.**
- [ ] **Step 3: Implement `services/precomputed_loader.py`**

```python
"""Load a CaseInfo's JSON outputs and assemble the dashboard view-model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from services.case_registry import CaseInfo
from services.risk_labels import composite_score, derive_risk_label, derive_topic, tone_pill


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class CaseBundle:
    slug: str
    display_name: str
    source: str
    scores: dict[str, float]
    tone_pill: dict[str, str]
    qna_rows: list[dict[str, Any]]
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def transparency(self) -> float:
        return float(self.scores.get("綜合透明度", 0.0))


def load_case_bundle(info: CaseInfo) -> CaseBundle:
    qna_payload = _read_json(info.qna_json) or {"qna_list": []}
    scores_payload = _read_json(info.scores_json) or {"scores": {}}
    sent_payload = _read_json(info.sentiment_dir / "qna_sentiment_summary.json") or {"qna_results": []}
    kp_payload = _read_json(info.keyphrase_dir / "qna_keyphrase_summary.json") or {"qna_results": []}
    tone_shift = _read_json(info.sentiment_dir / "company_tone_shift_summary.json") or {"tone_shift_results": [{}]}
    pii_payload = _read_json(info.pii_summary_json) or {"summary": []}

    sent_by_pair = {int(float(r["pair_id"])): r for r in sent_payload.get("qna_results", []) if r.get("pair_id") is not None}
    kp_by_pair = {int(float(r["pair_id"])): r for r in kp_payload.get("qna_results", []) if r.get("pair_id") is not None}

    qna_rows: list[dict[str, Any]] = []
    for idx, pair in enumerate(qna_payload.get("qna_list", []), start=1):
        sent = sent_by_pair.get(idx, {})
        kp = kp_by_pair.get(idx, {})
        signals = {
            "topic_mismatch_flag": bool(kp.get("topic_mismatch_flag")),
            "risk_downplay_flag": bool(sent.get("risk_downplay_flag")),
            "negative_question_soft_answer_flag": bool(sent.get("negative_question_soft_answer_flag")),
            "tone_gap_label": sent.get("tone_gap_label", "aligned"),
            "overlap_ratio": float(kp.get("overlap_ratio") or 0.0),
        }
        label = derive_risk_label(signals)
        qna_rows.append(
            {
                "index": idx,
                "question": pair.get("question", ""),
                "answer": pair.get("answer", ""),
                "question_translated": pair.get("question_translated", ""),
                "answer_translated": pair.get("answer_translated", ""),
                "topic": derive_topic(kp.get("question_key_phrases") or [], pair.get("question_translated", "")),
                "risk_label": label.value,
                "risk_label_zh": label.zh,
                "risk_label_class": label.palette_class,
                "composite_score": composite_score(
                    overlap_ratio=signals["overlap_ratio"],
                    topic_mismatch_flag=signals["topic_mismatch_flag"],
                    risk_downplay_flag=signals["risk_downplay_flag"],
                    negative_question_soft_answer_flag=signals["negative_question_soft_answer_flag"],
                ),
                "_signals": signals,
            }
        )

    scores = dict(scores_payload.get("scores", {}))
    tone_shift_row = (tone_shift.get("tone_shift_results") or [{}])[0]
    pill = tone_pill(bool(tone_shift_row.get("tone_shift_flag")))

    return CaseBundle(
        slug=info.slug,
        display_name=info.display_name,
        source=info.source,
        scores=scores,
        tone_pill=pill,
        qna_rows=qna_rows,
        raw={
            "qna": qna_payload,
            "sentiment": sent_payload,
            "keyphrase": kp_payload,
            "tone_shift": tone_shift,
            "pii": pii_payload,
        },
    )
```

- [ ] **Step 4: Run tests, expect PASS.**
- [ ] **Step 5: Commit**

```bash
cd frontend && git add services/precomputed_loader.py tests/test_precomputed_loader.py && git commit -m "feat(loader): pre-computed bundle assembler with derived per-Q&A fields"
```

---

# Phase 4 — Adapters

All adapters live under `frontend/adapters/` and never modify upstream code. Common helpers live in `_shared.py`.

## Task 10: Adapter shared helpers + 浩誠 adapter

**Files:**
- Create: `frontend/adapters/__init__.py` (empty)
- Create: `frontend/adapters/_shared.py`
- Create: `frontend/adapters/haocheng_adapter.py`
- Create: `frontend/tests/test_adapters_haocheng.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from adapters.haocheng_adapter import run as run_haocheng
from services.case_registry import find_case


def test_haocheng_runs_on_tsmc(tmp_path):
    info = find_case("tsmc")
    out_dir = tmp_path / "tsmc"
    result = run_haocheng(qna_json=info.qna_json, full_json=info.full_json, out_dir=out_dir)
    assert (out_dir / "scores.json").exists()
    assert (out_dir / "transparency_radar.png").exists()
    assert result["scores"]["綜合透明度"] >= 0
    assert "直接性" in result["scores"]
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `adapters/_shared.py`**

```python
"""Shared helpers for adapters: sys.path injection + safe CWD swap."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import Iterator

from config import get_settings


def team_root(team_dir_name: str) -> Path:
    return get_settings().precomputed_root_resolved() / team_dir_name


@contextlib.contextmanager
def added_sys_path(path: Path) -> Iterator[None]:
    s = str(path)
    inserted = False
    if s not in sys.path:
        sys.path.insert(0, s)
        inserted = True
    try:
        yield
    finally:
        if inserted and sys.path and sys.path[0] == s:
            sys.path.pop(0)


@contextlib.contextmanager
def chdir(path: Path) -> Iterator[None]:
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)
```

- [ ] **Step 4: Implement `adapters/haocheng_adapter.py`**

```python
"""Thin wrapper around 浩誠/run_from_json.run_one — no upstream modifications."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from adapters._shared import added_sys_path, chdir, team_root

HAOCHENG_ROOT = "浩誠_回答品質評分"


def run(*, qna_json: Path, full_json: Path, out_dir: Path) -> dict[str, Any]:
    """Compute the 5-dim + 綜合透明度 scores and write JSON + radar PNG to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    src = team_root(HAOCHENG_ROOT)

    with added_sys_path(src), chdir(src):
        from run_from_json import run_one  # type: ignore

        result = run_one(
            qna_json=Path(qna_json),
            full_json=Path(full_json),
            reference_text=None,
            out_dir=out_dir,
        )

    # Normalize filenames so loader/case_registry see consistent names.
    stem_png = Path(result["png"])
    stem_json = Path(result["json"])
    target_png = out_dir / "transparency_radar.png"
    target_json = out_dir / "scores.json"
    if stem_png != target_png:
        shutil.move(str(stem_png), target_png)
    if stem_json != target_json:
        shutil.move(str(stem_json), target_json)
    return {"scores": result["scores"], "json": str(target_json), "png": str(target_png)}
```

- [ ] **Step 5: Run tests, expect PASS.**

```bash
cd frontend && pytest tests/test_adapters_haocheng.py -v
```

- [ ] **Step 6: Commit**

```bash
cd frontend && git add adapters/__init__.py adapters/_shared.py adapters/haocheng_adapter.py tests/test_adapters_haocheng.py && git commit -m "feat(adapter): 浩誠 wrapper with normalized output filenames"
```

---

## Task 11: 瑾慈 sentiment adapter

`瑾慈` ships two CLI scripts that each read `config.ini` and process a `company_prefix`. The adapter writes a per-run `config.ini` pointing at our paths, then calls each script's `main()` via `runpy`.

**Files:**
- Create: `frontend/adapters/jincing_adapter.py` (with `run_sentiment`)
- Create: `frontend/tests/test_adapters_jincing.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `adapters/jincing_adapter.py`** (sentiment part; keyphrase added in Task 12)

```python
"""Adapter for 瑾慈: sentiment + keyphrase analysis.

Strategy: each upstream script reads config.ini from CWD. The adapter writes a
fresh config.ini that points the input dir at a temp directory containing the
case JSONs and the output dir at our cache, then calls the script's main().
"""

from __future__ import annotations

import configparser
import json
import runpy
import shutil
from pathlib import Path
from typing import Iterable

from adapters._shared import added_sys_path, chdir, team_root
from config import get_settings

JINCING_ROOT = "瑾慈：情緒分析&關鍵字擷取"

# Indirection so tests can patch this.
def _runpy_run_module(mod_name: str, run_name: str | None = None) -> None:
    runpy.run_module(mod_name, run_name=run_name)


def _stage_inputs(qna_json: Path, full_json: Path, staging: Path, slug: str) -> Path:
    """Copy the two JSON files into `staging` with the names the scripts expect."""
    staging.mkdir(parents=True, exist_ok=True)
    target_qna = staging / f"{slug}_extracted_qna_translation.json"
    target_full = staging / f"{slug}_full_transcript_translation.json"
    shutil.copy2(qna_json, target_qna)
    shutil.copy2(full_json, target_full)
    return staging


def _write_sentiment_config(
    config_path: Path,
    *,
    azure_key: str,
    azure_endpoint: str,
    input_dir: Path,
    output_dir: Path,
    company_prefix: str,
) -> None:
    cfg = configparser.ConfigParser()
    cfg["azure"] = {"language_key": azure_key, "language_endpoint": azure_endpoint}
    cfg["path"] = {"input_dir": str(input_dir), "output_dir": str(output_dir)}
    cfg["input"] = {"company_prefix": company_prefix}
    cfg["setting"] = {"use_translated": "false", "batch_size": "10", "max_chars": "4500"}
    with config_path.open("w", encoding="utf-8") as f:
        cfg.write(f)


def _copy_outputs(src_company_dir: Path, out_dir: Path, files: Iterable[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in files:
        src = src_company_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)


def run_sentiment(
    *,
    qna_json: Path,
    full_json: Path,
    out_dir: Path,
    slug: str,
    sent_out: Path | None = None,
) -> None:
    settings = get_settings()
    src = team_root(JINCING_ROOT)

    staging = (sent_out or (out_dir / "_stage_sent")).parent / "_jincing_stage_sent"
    input_dir = _stage_inputs(qna_json, full_json, staging / "input", slug)
    raw_out = (sent_out or (out_dir / "_sent_raw"))
    raw_out.mkdir(parents=True, exist_ok=True)

    _write_sentiment_config(
        src / "config.ini",
        azure_key=settings.AZURE_LANGUAGE_KEY,
        azure_endpoint=settings.AZURE_LANGUAGE_ENDPOINT,
        input_dir=input_dir,
        output_dir=raw_out,
        company_prefix=slug,
    )

    with added_sys_path(src), chdir(src):
        _runpy_run_module("sentiment_analysis", run_name="__main__")

    _copy_outputs(
        raw_out / slug,
        out_dir,
        ["qna_sentiment_summary.json", "section_sentiment_summary.json", "company_tone_shift_summary.json"],
    )
```

- [ ] **Step 4: Run tests, expect PASS.**
- [ ] **Step 5: Commit**

```bash
cd frontend && git add adapters/jincing_adapter.py tests/test_adapters_jincing.py && git commit -m "feat(adapter): 瑾慈 sentiment runner via config injection"
```

---

## Task 12: 瑾慈 keyphrase adapter (extend Task 11)

**Files:**
- Modify: `frontend/adapters/jincing_adapter.py`
- Modify: `frontend/tests/test_adapters_jincing.py`

- [ ] **Step 1: Append failing test**

```python
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
```

- [ ] **Step 2: Run, expect failure.**
- [ ] **Step 3: Append to `adapters/jincing_adapter.py`**

```python
def _write_keyphrase_config(
    config_path: Path,
    *,
    azure_key: str,
    azure_endpoint: str,
    input_dir: Path,
    output_dir: Path,
    company_prefix: str,
) -> None:
    cfg = configparser.ConfigParser()
    cfg["azure"] = {"language_key": azure_key, "language_endpoint": azure_endpoint}
    cfg["path"] = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "keyphrase_output_dir": str(output_dir),
    }
    cfg["input"] = {"company_prefix": company_prefix}
    cfg["setting"] = {"keyphrase_use_translated": "auto", "batch_size": "10", "max_chars": "4500"}
    with config_path.open("w", encoding="utf-8") as f:
        cfg.write(f)


def run_keyphrase(
    *,
    qna_json: Path,
    full_json: Path,
    out_dir: Path,
    slug: str,
    kp_out: Path | None = None,
) -> None:
    settings = get_settings()
    src = team_root(JINCING_ROOT)

    staging = (kp_out or (out_dir / "_stage_kp")).parent / "_jincing_stage_kp"
    input_dir = _stage_inputs(qna_json, full_json, staging / "input", slug)
    raw_out = (kp_out or (out_dir / "_kp_raw"))
    raw_out.mkdir(parents=True, exist_ok=True)

    _write_keyphrase_config(
        src / "config.ini",
        azure_key=settings.AZURE_LANGUAGE_KEY,
        azure_endpoint=settings.AZURE_LANGUAGE_ENDPOINT,
        input_dir=input_dir,
        output_dir=raw_out,
        company_prefix=slug,
    )

    with added_sys_path(src), chdir(src):
        _runpy_run_module("key_phrase_extraction", run_name="__main__")

    _copy_outputs(
        raw_out / slug,
        out_dir,
        ["qna_keyphrase_summary.json", "topic_emphasis_summary.json"],
    )
```

- [ ] **Step 4: Run, expect PASS. Commit.**

```bash
cd frontend && git add adapters/jincing_adapter.py tests/test_adapters_jincing.py && git commit -m "feat(adapter): 瑾慈 keyphrase runner via config injection"
```

---

## Task 13: 奕寧 PII + summary adapter

`奕寧/app.py` reads env vars at import time and hardcodes `data/` and `output/` relative to CWD. The adapter loads the module after exporting env vars and chdir-ing into 奕寧's directory with our JSON staged in `data/`.

**Files:**
- Create: `frontend/adapters/yining_adapter.py`
- Create: `frontend/tests/test_adapters_yining.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `adapters/yining_adapter.py`**

```python
"""Adapter for 奕寧: PII redaction + extractive summary."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from adapters._shared import added_sys_path, chdir, team_root
from config import get_settings

YINING_ROOT = "奕寧_ 摘要&PII"


def _invoke_app(filename: str) -> None:
    """Import 奕寧/app.py and call run_pii_and_summary(filename) in its CWD."""
    # The module reads AZURE_LANGUAGE_* via dotenv at import time; ensure env is exported.
    import importlib
    if "app" in list(__import__("sys").modules):
        importlib.reload(__import__("sys").modules["app"])
    import app as yining_app  # type: ignore
    yining_app.run_pii_and_summary(filename)


def run(*, qna_json: Path, full_json: Path, out_dir: Path, slug: str) -> None:
    settings = get_settings()
    src = team_root(YINING_ROOT)
    data_dir = src / "data"
    output_dir = src / "output"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Stage inputs under the names 奕寧 expects.
    qna_name = f"{slug}_extracted_qna_translation.json"
    full_name = f"{slug}_full_transcript_translation.json"
    shutil.copy2(qna_json, data_dir / qna_name)
    shutil.copy2(full_json, data_dir / full_name)

    # Export env so app.py's module-level load_dotenv-respecting code sees them.
    os.environ["AZURE_LANGUAGE_KEY"] = settings.AZURE_LANGUAGE_KEY
    os.environ["AZURE_LANGUAGE_ENDPOINT"] = settings.AZURE_LANGUAGE_ENDPOINT

    out_dir.mkdir(parents=True, exist_ok=True)
    with added_sys_path(src), chdir(src):
        _invoke_app(qna_name)
        _invoke_app(full_name)

    # Copy outputs into our cache with the canonical name `pii_summary.json`
    qna_out = output_dir / qna_name.replace(".json", "_pii_summary.json")
    full_out = output_dir / full_name.replace(".json", "_pii_summary.json")
    if qna_out.exists():
        shutil.copy2(qna_out, out_dir / "pii_summary.json")
    if full_out.exists():
        shutil.copy2(full_out, out_dir / "pii_summary_full.json")
```

- [ ] **Step 4: Run, expect PASS. Commit.**

```bash
cd frontend && git add adapters/yining_adapter.py tests/test_adapters_yining.py && git commit -m "feat(adapter): 奕寧 PII+summary runner with input staging"
```

---

# Phase 5 — Gemini Q&A extractor + 恩泓 adapter

## Task 14: Gemini Q&A extractor (spec §8.6)

**Files:**
- Create: `frontend/services/gemini_qna_extractor.py`
- Create: `frontend/tests/test_gemini_qna_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
import json

import services.gemini_qna_extractor as extractor


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModel:
    def __init__(self, *_, **__):
        self.calls: list[str] = []

    def generate_content(self, prompt, generation_config=None):
        self.calls.append(prompt)
        return _FakeResponse(json.dumps({
            "qna_list": [
                {"question": "What about AI demand?", "answer": "It's very strong."},
                {"question": "", "answer": "too short"},  # filtered downstream
            ]
        }))


def test_extract_returns_validated_pairs(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(extractor, "_GenerativeModel", lambda *_a, **_k: fake)
    pairs = extractor.extract_qna_from_chunk("chunk text", api_key="k", model="gemini-2.0-flash")
    assert pairs == [
        {"question": "What about AI demand?", "answer": "It's very strong."},
    ]
    assert "chunk text" in fake.calls[0]


def test_extract_retries_on_failure(monkeypatch):
    calls = {"n": 0}

    class _FailingModel:
        def generate_content(self, prompt, generation_config=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("transient")
            return _FakeResponse(json.dumps({"qna_list": [{"question": "Q?", "answer": "A!"}]}))

    monkeypatch.setattr(extractor, "_GenerativeModel", lambda *_a, **_k: _FailingModel())
    monkeypatch.setattr(extractor.time, "sleep", lambda _s: None)
    pairs = extractor.extract_qna_from_chunk("c", api_key="k", model="x")
    assert pairs == [{"question": "Q?", "answer": "A!"}]
    assert calls["n"] == 3
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `services/gemini_qna_extractor.py`**

```python
"""Gemini-based fallback for 恩泓's Azure-OpenAI Q&A extraction (spec §8.6)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位專業的金融數據萃取專家。
請從法說會逐字稿中，精準找出「提問 (Question)」與「回答 (Answer)」配對。

【嚴格規則】：
1. 100% 複製原文，不可摘要。
2. Question 絕不可包含回答；Answer 絕不可為空。
3. 過濾 Operator/串場句（如 "The first question is..."）。
4. 當語氣轉為「給予解答的陳述句」（如 "We expect...", "Let me answer...", "我們預期..."），
   即為回答的起點，必須在此切斷。

僅以下列 JSON 格式回應，不附加其他文字：
{"qna_list": [{"question": "...", "answer": "..."}, ...]}"""


def _GenerativeModel(model: str, api_key: str):
    """Indirection so tests can monkey-patch without importing google.generativeai."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model, system_instruction=SYSTEM_PROMPT)


def extract_qna_from_chunk(
    chunk_text: str,
    *,
    api_key: str,
    model: str,
    max_retries: int = 3,
) -> list[dict[str, str]]:
    """Return a list of {question, answer} dicts with the same shape 恩泓 produces."""
    client = _GenerativeModel(model, api_key)
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.generate_content(
                chunk_text,
                generation_config={"response_mime_type": "application/json"},
            )
            data = json.loads(resp.text)
            pairs = data.get("qna_list", []) or []
            return [p for p in pairs if _is_valid_pair(p)]
        except Exception as exc:  # noqa: BLE001 — broad on purpose, retried
            last_err = exc
            log.warning("Gemini extraction attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2**attempt)
    if last_err:
        log.error("Gemini extraction failed after %d retries: %s", max_retries, last_err)
    return []


def _is_valid_pair(pair: Any) -> bool:
    if not isinstance(pair, dict):
        return False
    q = (pair.get("question") or "").strip()
    a = (pair.get("answer") or "").strip()
    return len(q) > 5 and len(a) > 5
```

- [ ] **Step 4: Run tests, expect PASS.**
- [ ] **Step 5: Commit**

```bash
cd frontend && git add services/gemini_qna_extractor.py tests/test_gemini_qna_extractor.py && git commit -m "feat(gemini): Q&A extractor fallback with JSON-mode + retries (§8.6)"
```

---

## Task 15: 恩泓 adapter (with extractor selection)

The 恩泓 module's `qa_pipeline.py` reads `config.ini` at import time and uses both an Azure OpenAI client and an Azure Translator REST client. The adapter writes a config.ini with the right Translator values, then either uses the upstream Azure OpenAI path (if configured) or monkey-patches `extract_qna_from_chunk` to call our Gemini extractor before invoking the upstream module functions.

**Files:**
- Create: `frontend/adapters/enhong_adapter.py`
- Create: `frontend/tests/test_adapters_enhong.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `adapters/enhong_adapter.py`**

```python
"""Adapter for 恩泓: translation + Q&A extraction.

Uses Azure OpenAI when AZURE_OPENAI_API_KEY is set; otherwise routes Q&A
extraction through services.gemini_qna_extractor (spec §8.6).

Translation always uses Azure Translator via the upstream module's REST call.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from adapters._shared import added_sys_path, chdir, team_root
from config import get_settings
from services import gemini_qna_extractor

ENHONG_ROOT = "恩泓_ 逐字稿翻譯和 Q&A 擷取/source"

log = logging.getLogger(__name__)


def _detect_language(text: str) -> tuple[str, str]:
    sample = text[:500]
    chinese_chars = re.findall(r"[一-鿿]", sample)
    if len(chinese_chars) > 10:
        return "zh-Hant", "en"
    return "en", "zh-Hant"


def _ensure_config_ini(src: Path, settings) -> None:
    """Write a minimal config.ini that satisfies qa_pipeline.py's read at import."""
    cfg_path = src / "config.ini"
    content = (
        "[AzureOpenAI]\n"
        f"API_KEY = {settings.AZURE_OPENAI_API_KEY or 'unused'}\n"
        f"API_ENDPOINT = {settings.AZURE_OPENAI_ENDPOINT or 'https://example.invalid'}\n"
        f"API_VERSION = {settings.AZURE_OPENAI_API_VERSION}\n"
        f"DEPLOYMENT_NAME = {settings.AZURE_OPENAI_DEPLOYMENT or 'unused'}\n"
        "\n[AzureTranslator]\n"
        f"TRANSLATOR_KEY = {settings.AZURE_TRANSLATOR_KEY}\n"
        f"TRANSLATOR_REGION = {settings.AZURE_TRANSLATOR_REGION}\n"
        f"TRANSLATOR_ENDPOINT = {settings.AZURE_TRANSLATOR_ENDPOINT}\n"
    )
    cfg_path.write_text(content, encoding="utf-8")


# Indirections so tests can patch.
def _translate_text(text: str, target_lang: str) -> str:
    import sys
    qa_pipeline = sys.modules["qa_pipeline"]
    return qa_pipeline.translate_text(text, target_lang)


def _extract_qna_for_chunk(chunk: str) -> list[dict[str, str]]:
    settings = get_settings()
    if settings.has_azure_openai():
        import sys
        qa_pipeline = sys.modules["qa_pipeline"]
        return qa_pipeline.extract_qna_from_chunk(chunk)
    return gemini_qna_extractor.extract_qna_from_chunk(
        chunk,
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
    )


def _import_qa_pipeline():
    settings = get_settings()
    src = team_root(ENHONG_ROOT)
    _ensure_config_ini(src, settings)
    with added_sys_path(src), chdir(src):
        import importlib
        import sys
        if "qa_pipeline" in sys.modules:
            importlib.reload(sys.modules["qa_pipeline"])
        else:
            import qa_pipeline  # noqa: F401
    return src


def run(
    *,
    full_text: str,
    qna_text: str | None,
    out_dir: Path,
    slug: str,
) -> tuple[Path, Path]:
    """Produce the two 恩泓-shaped JSON files in out_dir.

    Returns: (full_transcript_path, extracted_qna_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    _import_qa_pipeline()

    import sys
    qa_pipeline = sys.modules["qa_pipeline"]

    source_lang, target_lang = _detect_language(full_text)

    # --- Track 1: full transcript translation ---
    paragraphs = [p.strip() for p in full_text.split("\n") if p.strip()]
    content_list = []
    for idx, para in enumerate(paragraphs, start=1):
        translated = _translate_text(para, target_lang)
        content_list.append({"paragraph_index": idx, "original_text": para, "translated_text": translated})
        time.sleep(0.05)

    full_doc = {
        "metadata": {
            "source_language": source_lang,
            "target_language": target_lang,
            "total_paragraphs": len(paragraphs),
        },
        "content": content_list,
    }

    # --- Track 2: Q&A extraction + translation ---
    text_for_qna = qna_text or full_text
    chunks = qa_pipeline.chunk_text(text_for_qna, chunk_size=8000, overlap=1500)
    all_pairs: list[dict[str, str]] = []
    for chunk in chunks:
        all_pairs.extend(_extract_qna_for_chunk(chunk))

    # Dedup same as upstream
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in all_pairs:
        key = item.get("question", "")[:50].strip().lower()
        if key and key not in seen and len(key) > 10:
            seen.add(key)
            unique.append(item)

    for item in unique:
        item["question_translated"] = _translate_text(item["question"], target_lang)
        item["answer_translated"] = _translate_text(item["answer"], target_lang)

    qna_doc = {
        "metadata": {
            "source_language": source_lang,
            "target_language": target_lang,
            "total_qna_pairs": len(unique),
        },
        "qna_list": unique,
    }

    full_path = out_dir / "full_transcript_translation.json"
    qna_path = out_dir / "extracted_qna_translation.json"
    full_path.write_text(json.dumps(full_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    qna_path.write_text(json.dumps(qna_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return full_path, qna_path
```

- [ ] **Step 4: Run tests, expect PASS.**
- [ ] **Step 5: Commit**

```bash
cd frontend && git add adapters/enhong_adapter.py tests/test_adapters_enhong.py && git commit -m "feat(adapter): 恩泓 wrapper with Azure-OpenAI/Gemini extractor selection"
```

---

# Phase 6 — Upload flow

## Task 16: docx loader

**Files:**
- Create: `frontend/services/docx_loader.py`
- Create: `frontend/tests/test_docx_loader.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from docx import Document

from services.docx_loader import docx_to_text


def test_docx_to_text_extracts_paragraphs(tmp_path: Path):
    doc = Document()
    doc.add_paragraph("Welcome to the call.")
    doc.add_paragraph("Q: What about demand?")
    doc.add_paragraph("A: Strong.")
    target = tmp_path / "fixture.docx"
    doc.save(target)

    text = docx_to_text(target)
    assert "Welcome to the call." in text
    assert "Q: What about demand?" in text
    assert "A: Strong." in text
    assert text.count("\n") >= 2


def test_docx_to_text_rejects_non_docx(tmp_path: Path):
    target = tmp_path / "bad.txt"
    target.write_text("not docx", encoding="utf-8")
    try:
        docx_to_text(target)
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-docx")
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `services/docx_loader.py`**

```python
"""Convert a .docx upload into newline-separated plain text."""

from __future__ import annotations

from pathlib import Path

from docx import Document


def docx_to_text(path: Path) -> str:
    if path.suffix.lower() != ".docx":
        raise ValueError(f"Expected .docx, got {path.suffix}")
    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(paragraphs)
```

- [ ] **Step 4: Run, PASS. Commit.**

```bash
cd frontend && git add services/docx_loader.py tests/test_docx_loader.py && git commit -m "feat(docx): minimal .docx -> plain text loader"
```

---

## Task 17: Job store (in-memory SSE state)

**Files:**
- Create: `frontend/services/job_store.py`
- Create: `frontend/tests/test_job_store.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio

import pytest

from services.job_store import JobStore, JobStatus


def test_create_and_get():
    store = JobStore()
    job = store.create(slug="tsmc")
    assert job.slug == "tsmc"
    assert job.status == JobStatus.PENDING
    fetched = store.get(job.id)
    assert fetched is job


def test_update_status_and_emit():
    store = JobStore()
    job = store.create(slug="x")
    events: list[dict] = []

    async def consume():
        async for evt in store.events(job.id):
            events.append(evt)
            if evt["status"] == JobStatus.DONE.value:
                break

    async def driver():
        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0)
        store.update(job.id, status=JobStatus.RUNNING, step="translating")
        store.update(job.id, status=JobStatus.RUNNING, step="extracting_qna")
        store.update(job.id, status=JobStatus.DONE, step="done")
        await consumer

    asyncio.run(driver())
    assert [e["step"] for e in events] == ["translating", "extracting_qna", "done"]
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `services/job_store.py`**

```python
"""In-memory job store used by the upload flow + SSE progress route."""

from __future__ import annotations

import asyncio
import enum
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    slug: str
    status: JobStatus = JobStatus.PENDING
    step: str = "queued"
    error: str | None = None
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue, repr=False)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, *, slug: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, slug=slug)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update(self, job_id: str, *, status: JobStatus, step: str, error: str | None = None) -> None:
        job = self._jobs[job_id]
        job.status = status
        job.step = step
        job.error = error
        job._queue.put_nowait({"status": status.value, "step": step, "error": error})

    async def events(self, job_id: str) -> AsyncIterator[dict]:
        job = self._jobs[job_id]
        while True:
            evt = await job._queue.get()
            yield evt
            if evt["status"] in {JobStatus.DONE.value, JobStatus.FAILED.value}:
                return


_store: JobStore | None = None


def get_job_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
```

- [ ] **Step 4: Run, PASS. Commit.**

```bash
cd frontend && git add services/job_store.py tests/test_job_store.py && git commit -m "feat(job-store): in-memory job + SSE event queue"
```

---

## Task 18: Upload processor

**Files:**
- Create: `frontend/services/upload_processor.py`
- Create: `frontend/tests/test_upload_processor.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `services/upload_processor.py`**

```python
"""Orchestrates the upload pipeline: docx → 恩泓 → (haocheng | jincing | yining)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from adapters import enhong_adapter, haocheng_adapter, jincing_adapter, yining_adapter
from config import get_settings
from services.job_store import JobStatus, JobStore

log = logging.getLogger(__name__)


async def process_upload(
    *,
    job_id: str,
    store: JobStore,
    full_text: str,
    qna_text: str | None,
    slug: str,
) -> None:
    settings = get_settings()
    case_dir = settings.cache_dir_resolved() / slug
    case_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, dict] = {}

    def _set(step: str) -> None:
        store.update(job_id, status=JobStatus.RUNNING, step=step)

    try:
        _set("translating")
        full_json, qna_json = await asyncio.to_thread(
            enhong_adapter.run,
            full_text=full_text, qna_text=qna_text, out_dir=case_dir, slug=slug,
        )
        status["enhong"] = {"ok": True}

        async def _haocheng():
            try:
                _set("scoring")
                await asyncio.to_thread(
                    haocheng_adapter.run,
                    qna_json=qna_json, full_json=full_json, out_dir=case_dir,
                )
                status["haocheng"] = {"ok": True}
            except Exception as exc:  # noqa: BLE001
                status["haocheng"] = {"ok": False, "error": str(exc)}

        async def _sentiment():
            try:
                _set("sentiment")
                await asyncio.to_thread(
                    jincing_adapter.run_sentiment,
                    qna_json=qna_json, full_json=full_json, out_dir=case_dir, slug=slug,
                )
                status["jincing_sentiment"] = {"ok": True}
            except Exception as exc:  # noqa: BLE001
                status["jincing_sentiment"] = {"ok": False, "error": str(exc)}

        async def _keyphrase():
            try:
                _set("keyphrase")
                await asyncio.to_thread(
                    jincing_adapter.run_keyphrase,
                    qna_json=qna_json, full_json=full_json, out_dir=case_dir, slug=slug,
                )
                status["jincing_keyphrase"] = {"ok": True}
            except Exception as exc:  # noqa: BLE001
                status["jincing_keyphrase"] = {"ok": False, "error": str(exc)}

        async def _yining():
            try:
                _set("summary")
                await asyncio.to_thread(
                    yining_adapter.run,
                    qna_json=qna_json, full_json=full_json, out_dir=case_dir, slug=slug,
                )
                status["yining"] = {"ok": True}
            except Exception as exc:  # noqa: BLE001
                status["yining"] = {"ok": False, "error": str(exc)}

        await asyncio.gather(_haocheng(), _sentiment(), _keyphrase(), _yining())

        (case_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        store.update(job_id, status=JobStatus.DONE, step="done")

    except Exception as exc:  # noqa: BLE001
        log.exception("Upload pipeline failed for slug=%s", slug)
        store.update(job_id, status=JobStatus.FAILED, step="failed", error=str(exc))
        (case_dir / "status.json").write_text(json.dumps({**status, "_fatal": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests, PASS. Commit.**

```bash
cd frontend && git add services/upload_processor.py tests/test_upload_processor.py && git commit -m "feat(upload): pipeline orchestration with per-module status capture"
```

---

# Phase 7 — Insights & chat

## Task 19: Insights composer (rule-based list, §8.4(b))

**Files:**
- Create: `frontend/services/insights_composer.py`
- Create: `frontend/tests/test_insights_composer.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `services/insights_composer.py`**

```python
"""Investment-insights panel composition (spec §8.4)."""

from __future__ import annotations

from typing import Any


def compose_rule_list(
    *,
    scores: dict[str, float],
    qna_rows: list[dict[str, Any]],
    tone_shift_flag: bool,
    negative_score_shift: float,
) -> dict[str, list]:
    """Return the deterministic part of the insights panel."""
    worth_tracking: list[dict[str, str]] = []
    for row in qna_rows:
        if row["risk_label"] in {"evasive", "tone_shift"}:
            worth_tracking.append(
                {
                    "index": row["index"],
                    "bullet": f"第 {row['index']} 題 · {row.get('topic', '')} · {row['risk_label_zh']}",
                }
            )

    disclosure: list[str] = []
    transparency = float(scores.get("綜合透明度", 0.0))
    if transparency < 50:
        disclosure.append(f"整體透明度偏低 ({transparency:.0f}/100)")
    if tone_shift_flag:
        disclosure.append(f"Q&A 階段語氣較簡報轉趨保守 (Δ {negative_score_shift:+.2f})")
    n_downplay = sum(1 for row in qna_rows if row.get("_signals", {}).get("risk_downplay_flag"))
    if n_downplay > 0:
        disclosure.append(f"{n_downplay} 題出現負面議題弱化訊號")

    return {"worth_tracking": worth_tracking, "disclosure_risks": disclosure}
```

- [ ] **Step 4: Run, PASS. Commit.**

```bash
cd frontend && git add services/insights_composer.py tests/test_insights_composer.py && git commit -m "feat(insights): rule-based worth-tracking + disclosure-risk list (§8.4b)"
```

---

## Task 20: Insights composer — LLM headline (§8.4(a))

**Files:**
- Modify: `frontend/services/insights_composer.py`
- Modify: `frontend/tests/test_insights_composer.py`

- [ ] **Step 1: Append failing test**

```python
import services.insights_composer as composer


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
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Append to `services/insights_composer.py`**

```python
import json
import logging

log = logging.getLogger(__name__)

HEADLINE_SYSTEM_PROMPT = """你是金融分析師。給定法說會 Q&A 的分析結果（透明度分數、風險旗標、情緒落差），
請以繁體中文寫 2-3 句重點摘要：
  1. 整體透明度評價（高 / 中 / 低 + 一句佐證）
  2. 最需追蹤的一題（題號 + 一句原因）
  3. 是否有語氣轉變或揭露風險（若無則略過）
不得編造資料中未出現的細節。"""


def _HeadlineModel(model: str, api_key: str):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model, system_instruction=HEADLINE_SYSTEM_PROMPT)


def compose_headline(payload: dict, *, api_key: str, model: str) -> str:
    """LLM-written 2-3 sentence summary in Traditional Chinese. Empty if no key."""
    if not api_key:
        return ""
    try:
        client = _HeadlineModel(model, api_key)
        resp = client.generate_content(json.dumps(payload, ensure_ascii=False))
        return (resp.text or "").strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("Insights headline failed: %s", exc)
        return ""


def build_headline_payload(*, slug: str, scores: dict, tone_shift_flag: bool, qna_rows: list) -> dict:
    """Build the compact JSON payload the LLM receives."""
    worst = None
    for row in sorted(qna_rows, key=lambda r: r.get("composite_score", 100)):
        if row["risk_label"] in {"evasive", "tone_shift", "vague"}:
            worst = {
                "index": row["index"],
                "topic": row.get("topic", ""),
                "label": row["risk_label_zh"],
                "score": row["composite_score"],
            }
            break
    flagged = sum(1 for r in qna_rows if r["risk_label"] in {"evasive", "tone_shift"})
    return {
        "company": slug,
        "transparency": int(round(float(scores.get("綜合透明度", 0.0)))),
        "tone_shift_flag": bool(tone_shift_flag),
        "worst_qna": worst,
        "flagged_count": flagged,
    }
```

- [ ] **Step 4: Run, PASS. Commit.**

```bash
cd frontend && git add services/insights_composer.py tests/test_insights_composer.py && git commit -m "feat(insights): LLM headline composer + payload builder (§8.4a)"
```

---

## Task 21: Chat service — context builder

**Files:**
- Create: `frontend/services/chat_service.py`
- Create: `frontend/tests/test_chat_service.py`

- [ ] **Step 1: Failing test**

```python
from services.case_registry import find_case
from services.precomputed_loader import load_case_bundle
from services.chat_service import build_context, SYSTEM_PROMPT


def test_build_context_includes_qna_and_scores():
    bundle = load_case_bundle(find_case("tsmc"))
    ctx = build_context(bundle)
    assert "Q&A" in ctx or "問題" in ctx
    assert "綜合透明度" in ctx
    assert SYSTEM_PROMPT[:8] in ctx or "你是" in ctx
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `services/chat_service.py`** (context builder + prompt only)

```python
"""Gemini chat service: per-case context builder + streaming proxy."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from services.precomputed_loader import CaseBundle

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位專業的金融分析助手，正在協助使用者解讀一場法說會的 Q&A 與分析結果。
規則：
1. 回答必須以繁體中文。
2. 引用 Q&A 時要附上題號（例：「第 2 題」）。
3. 解釋風險標籤時，引用底層訊號（如 overlap_ratio、tone_gap_label）。
4. 如使用者提出與本案件無關的問題，禮貌拒答並請對方換題。
5. 不得編造資料中未出現的細節。"""


def build_context(bundle: CaseBundle) -> str:
    """Compose the per-case context bundle for Gemini."""
    payload = {
        "company": bundle.slug,
        "transparency_scores": bundle.scores,
        "tone_pill": bundle.tone_pill,
        "qna": [
            {
                "index": row["index"],
                "question": row["question_translated"] or row["question"],
                "answer": row["answer_translated"] or row["answer"],
                "topic": row["topic"],
                "risk_label": row["risk_label_zh"],
                "composite_score": row["composite_score"],
                "signals": row["_signals"],
            }
            for row in bundle.qna_rows
        ],
        "summary_bullets": (bundle.raw.get("pii") or {}).get("summary", []),
    }
    return SYSTEM_PROMPT + "\n\n<case_data>\n" + json.dumps(payload, ensure_ascii=False) + "\n</case_data>"
```

- [ ] **Step 4: Run, PASS. Commit.**

```bash
cd frontend && git add services/chat_service.py tests/test_chat_service.py && git commit -m "feat(chat): context builder with TC system prompt"
```

---

## Task 22: Chat service — streaming

**Files:**
- Modify: `frontend/services/chat_service.py`
- Modify: `frontend/tests/test_chat_service.py`

- [ ] **Step 1: Append failing test**

```python
import asyncio

import services.chat_service as chat


def test_stream_chat_yields_chunks(monkeypatch):
    class _Chunk:
        def __init__(self, text):
            self.text = text

    class _FakeModel:
        def generate_content(self, contents, stream=False, generation_config=None):
            assert stream is True
            return iter([_Chunk("第 2 題（"), _Chunk("資本支出）為 41 分。")])

    monkeypatch.setattr(chat, "_ChatModel", lambda *_a, **_k: _FakeModel())

    async def collect():
        out = []
        async for piece in chat.stream_chat(
            context="ctx", history=[], user_msg="哪一題分數最低？",
            api_key="k", model="x",
        ):
            out.append(piece)
        return out

    assert asyncio.run(collect()) == ["第 2 題（", "資本支出）為 41 分。"]
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Append to `services/chat_service.py`**

```python
def _ChatModel(model: str, api_key: str, *, system_instruction: str | None = None):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model, system_instruction=system_instruction)


async def stream_chat(
    *,
    context: str,
    history: list[dict],
    user_msg: str,
    api_key: str,
    model: str,
) -> AsyncIterator[str]:
    """Yield text chunks from Gemini. Each chunk is forwarded to the SSE response."""
    if not api_key:
        yield "(未啟用 LLM 對話)"
        return

    client = _ChatModel(model, api_key, system_instruction=context)
    contents = list(history) + [{"role": "user", "parts": [user_msg]}]

    try:
        resp = client.generate_content(contents, stream=True)
        for chunk in resp:
            text = getattr(chunk, "text", "") or ""
            if text:
                yield text
    except Exception as exc:  # noqa: BLE001
        log.warning("Chat streaming failed: %s", exc)
        yield f"(對話發生錯誤：{exc})"
```

- [ ] **Step 4: Run, PASS. Commit.**

```bash
cd frontend && git add services/chat_service.py tests/test_chat_service.py && git commit -m "feat(chat): Gemini streaming wrapper"
```

---

# Phase 8 — Routes & templates

## Task 23: Landing route + base template + index template

**Files:**
- Create: `frontend/templates/base.html`
- Create: `frontend/templates/index.html`
- Create: `frontend/routes/pages.py`
- Modify: `frontend/app.py`
- Create: `frontend/tests/test_routes_pages.py`

- [ ] **Step 1: Failing test**

```python
from fastapi.testclient import TestClient

from app import app


def test_landing_lists_three_precomputed_companies():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    body = response.text
    assert "法說會分析" in body
    assert "TSMC" in body and "NVDA" in body and "FOXCONN" in body
    assert "上傳逐字稿" in body
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Create `templates/base.html`**

```html
<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}法說會分析{% endblock %}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;600;700&family=Noto+Serif+TC:wght@500;700&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    theme: {
      extend: {
        colors: {
          bg: '#f4f6fa', surface: '#ffffff',
          ink: '#14213d', muted: '#6b7693',
          line: '#e2e8f2', accent: '#1d4ed8', 'accent-soft': '#e0eaff',
          'risk-direct-bg': '#dceee2', 'risk-direct-ink': '#1a5e3c',
          'risk-vague-bg':  '#e0e7ff', 'risk-vague-ink':  '#2547a8',
          'risk-evasive-bg':'#fbe1e3', 'risk-evasive-ink':'#9a1f30',
          'risk-tone-bg':   '#e9e3f8', 'risk-tone-ink':   '#4e3a96',
        },
        fontFamily: {
          sans: ['Noto Sans TC', 'system-ui', 'sans-serif'],
          serif: ['Noto Serif TC', 'Georgia', 'serif'],
        },
      },
    },
  };
</script>
<style>
  .risk-direct  { background:#dceee2; color:#1a5e3c; }
  .risk-vague   { background:#e0e7ff; color:#2547a8; }
  .risk-evasive { background:#fbe1e3; color:#9a1f30; }
  .risk-tone    { background:#e9e3f8; color:#4e3a96; }
</style>
</head>
<body class="bg-bg text-ink font-sans antialiased">
  <header class="border-b border-line bg-surface">
    <div class="max-w-7xl mx-auto px-6 h-10 flex items-center gap-3">
      <a href="/" class="font-serif font-bold tracking-wide text-ink">法說會分析</a>
      <span class="text-muted">·</span>
      <span class="text-sm text-muted">{% block subtitle %}{% endblock %}</span>
    </div>
  </header>
  <main class="max-w-7xl mx-auto px-6 py-10">
    {% block content %}{% endblock %}
  </main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Create `templates/index.html`**

```html
{% extends "base.html" %}
{% block content %}
<section class="space-y-4">
  <h1 class="font-serif text-3xl text-ink">選擇案件</h1>
  <p class="text-muted">已預先分析的法說會案例，點擊即可進入儀表板。</p>

  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    {% for case in precomputed_cases %}
    <a href="/case/{{ case.slug }}" class="block bg-surface border border-line rounded-lg p-5 hover:border-accent transition">
      <div class="text-xs uppercase tracking-widest text-muted">{{ case.source }}</div>
      <div class="font-serif text-2xl mt-1 text-ink">{{ case.display_name }}</div>
      <div class="mt-3 text-xs uppercase tracking-widest text-muted">Q&A 透明度評分</div>
      <div class="font-serif text-4xl text-ink mt-1">{{ case.transparency|round|int }}<span class="text-sm text-muted"> / 100</span></div>
      <div class="mt-3 text-xs inline-block px-2.5 py-1 rounded-full {% if case.tone_pill.variant == 'stable' %}bg-accent-soft text-accent{% else %}bg-risk-evasive-bg text-risk-evasive-ink{% endif %}">
        {{ case.tone_pill.text }}
      </div>
    </a>
    {% endfor %}
  </div>
</section>

{% if uploaded_cases %}
<section class="space-y-3 mt-10">
  <h2 class="font-serif text-2xl text-ink">已上傳案件</h2>
  <ul class="space-y-2 text-sm">
    {% for case in uploaded_cases %}
    <li class="bg-surface border border-line rounded px-4 py-2 flex items-center gap-3">
      <a class="text-accent hover:underline" href="/case/{{ case.slug }}">{{ case.display_name }}</a>
      <span class="text-muted">透明度 {{ case.transparency|round|int }}</span>
    </li>
    {% endfor %}
  </ul>
</section>
{% endif %}

<section class="space-y-3 mt-10">
  <h2 class="font-serif text-2xl text-ink">上傳新案件</h2>
  <form action="/upload" method="post" enctype="multipart/form-data"
        class="bg-surface border border-line rounded-lg p-6 space-y-3">
    <label class="block text-sm text-ink">完整逐字稿 (.docx)
      <input type="file" name="full_docx" accept=".docx" required
             class="block mt-1 text-sm text-muted file:mr-3 file:px-3 file:py-1.5 file:rounded file:border-0 file:bg-accent file:text-white">
    </label>
    <label class="block text-sm text-ink">純 Q&amp;A 段 (.docx，可選)
      <input type="file" name="qna_docx" accept=".docx"
             class="block mt-1 text-sm text-muted file:mr-3 file:px-3 file:py-1.5 file:rounded file:border-0 file:bg-accent file:text-white">
    </label>
    <label class="block text-sm text-ink">案件名稱（可選）
      <input type="text" name="case_name" placeholder="e.g. tsmc-2026q2"
             class="block mt-1 w-full px-3 py-2 border border-line rounded text-sm">
    </label>
    <button class="bg-ink text-white px-4 py-2 rounded text-sm font-medium">上傳並開始分析</button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 5: Implement `routes/pages.py`**

```python
"""Page routes for landing and dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from services.case_registry import discover_cases
from services.precomputed_loader import load_case_bundle

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/")
def landing(request: Request):
    cases = discover_cases()
    bundles = []
    for c in cases:
        if c.all_files_exist():
            try:
                bundle = load_case_bundle(c)
                bundles.append(_card(bundle, c.source))
            except Exception:
                continue
    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "precomputed_cases": [b for b in bundles if b["source"] == "precomputed"],
            "uploaded_cases": [b for b in bundles if b["source"] == "upload"],
        },
    )


def _card(bundle, source: str) -> dict:
    return {
        "slug": bundle.slug,
        "display_name": bundle.display_name,
        "source": source,
        "transparency": bundle.transparency,
        "tone_pill": bundle.tone_pill,
    }
```

- [ ] **Step 6: Wire router in `app.py`**

Modify `frontend/app.py` — add after the `app = FastAPI(...)` line:

```python
from routes.pages import router as pages_router

app.include_router(pages_router)
```

- [ ] **Step 7: Run tests, PASS. Commit.**

```bash
cd frontend && git add templates/base.html templates/index.html routes/pages.py app.py tests/test_routes_pages.py && git commit -m "feat(pages): landing route with case cards + upload form"
```

---

## Task 24: Dashboard route + template + insights partial

**Files:**
- Create: `frontend/templates/dashboard.html`
- Create: `frontend/templates/partials/insights.html`
- Modify: `frontend/routes/pages.py`
- Modify: `frontend/tests/test_routes_pages.py`

- [ ] **Step 1: Append failing test**

```python
def test_dashboard_renders_all_five_panels():
    response = TestClient(app).get("/case/tsmc")
    assert response.status_code == 200
    body = response.text
    # Hero
    assert "Q&A 透明度評分" in body
    # Radar
    assert "雷達圖" in body
    assert "radar-canvas" in body
    # Insights
    assert "投資洞察" in body
    # Q&A table
    assert "Q&A 摘要表" in body
    assert "分析師問題" in body
    # Risk-label classes present
    assert "risk-direct" in body or "risk-vague" in body or "risk-evasive" in body or "risk-tone" in body
    # Chat panel
    assert "GEMINI 智能問答" in body
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Create `templates/partials/insights.html`**

```html
<div class="space-y-4">
  {% if headline %}
  <p class="font-serif text-base text-ink leading-relaxed border-l-2 border-accent pl-4">
    {{ headline }}
  </p>
  {% endif %}

  <div class="text-xs uppercase tracking-widest text-muted">需要追蹤的回答</div>
  {% if worth_tracking %}
  <ul class="text-sm text-ink space-y-1">
    {% for item in worth_tracking %}
    <li>· <a href="#qna-{{ item.index }}" class="hover:text-accent">{{ item.bullet }}</a></li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="text-sm text-muted">本場法說會無迴避或語氣轉變訊號。</p>
  {% endif %}

  <div class="text-xs uppercase tracking-widest text-muted pt-2">公司資訊揭露風險</div>
  {% if disclosure_risks %}
  <ul class="text-sm text-ink space-y-1">
    {% for bullet in disclosure_risks %}
    <li>· {{ bullet }}</li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="text-sm text-muted">未偵測到揭露風險訊號。</p>
  {% endif %}
</div>
```

- [ ] **Step 4: Create `templates/dashboard.html`**

```html
{% extends "base.html" %}
{% block subtitle %}{{ bundle.display_name }}{% endblock %}
{% block content %}
<div class="grid grid-cols-12 gap-6">
  <!-- Main column -->
  <div class="col-span-12 lg:col-span-9 space-y-6">

    <!-- Hero -->
    <section id="hero" class="bg-surface border border-line rounded-lg p-8 text-center">
      <div class="text-xs uppercase tracking-widest text-muted">Q&A 透明度評分</div>
      <div class="font-serif text-6xl text-ink mt-2">{{ bundle.transparency|round|int }}<span class="text-2xl text-muted"> / 100</span></div>
      <div class="mt-4 inline-block text-xs px-3 py-1 rounded-full {% if bundle.tone_pill.variant == 'stable' %}bg-accent-soft text-accent{% else %}bg-risk-evasive-bg text-risk-evasive-ink{% endif %}">
        {{ bundle.tone_pill.text }}
      </div>
    </section>

    <!-- Radar + Insights -->
    <section class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div id="radar" class="bg-surface border border-line rounded-lg p-5">
        <div class="text-xs uppercase tracking-widest text-muted">雷達圖</div>
        <canvas id="radar-canvas" class="mt-3" height="240"></canvas>
      </div>
      <div id="insights" class="bg-surface border border-line rounded-lg p-5">
        <div class="text-xs uppercase tracking-widest text-muted mb-3">投資洞察</div>
        {% include "partials/insights.html" %}
      </div>
    </section>

    <!-- Q&A table -->
    <section id="qna" class="bg-surface border border-line rounded-lg overflow-hidden">
      <div class="text-xs uppercase tracking-widest text-muted px-5 pt-4">Q&A 摘要表</div>
      <table class="w-full text-sm mt-2">
        <thead class="text-muted text-xs uppercase tracking-widest">
          <tr class="border-b border-line">
            <th class="text-left px-5 py-2 w-10">#</th>
            <th class="text-left px-5 py-2">分析師問題</th>
            <th class="text-left px-5 py-2">管理層回答</th>
            <th class="text-left px-5 py-2 w-28">風險標籤</th>
            <th class="text-left px-5 py-2 w-16">分數</th>
          </tr>
        </thead>
        <tbody>
          {% for row in bundle.qna_rows %}
          <tr id="qna-{{ row.index }}" class="border-b border-line align-top">
            <td class="px-5 py-3 text-muted">{{ row.index }}</td>
            <td class="px-5 py-3 max-w-md">{{ row.question_translated or row.question }}</td>
            <td class="px-5 py-3 max-w-md">{{ row.answer_translated or row.answer }}</td>
            <td class="px-5 py-3"><span class="text-xs px-2 py-0.5 rounded-full {{ row.risk_label_class }}">{{ row.risk_label_zh }}</span></td>
            <td class="px-5 py-3 font-serif text-ink">{{ row.composite_score }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>
  </div>

  <!-- Chat sidebar -->
  <aside class="col-span-12 lg:col-span-3 sticky top-4 self-start">
    <div class="bg-surface border border-line rounded-lg p-4 flex flex-col h-[calc(100vh-6rem)]">
      <div class="text-xs uppercase tracking-widest text-muted">GEMINI 智能問答</div>
      <div id="chat-log" class="flex-1 mt-3 space-y-2 overflow-y-auto text-sm"></div>
      <form id="chat-form" data-case="{{ bundle.slug }}" class="mt-3 flex gap-2">
        <input type="text" id="chat-input" placeholder="輸入後續問題…" class="flex-1 px-3 py-2 border border-line rounded text-sm">
        <button class="bg-ink text-white px-3 py-2 rounded text-sm">送出</button>
      </form>
    </div>
  </aside>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/chart.umd.js"></script>
<script>
const radarData = {{ radar_json|safe }};
const ctx = document.getElementById('radar-canvas').getContext('2d');
new Chart(ctx, {
  type: 'radar',
  data: {
    labels: Object.keys(radarData),
    datasets: [{
      data: Object.values(radarData),
      borderColor: '#1d4ed8', backgroundColor: 'rgba(29,78,216,0.15)',
      pointBackgroundColor: '#1d4ed8',
    }],
  },
  options: {
    scales: { r: { min: 0, max: 100, ticks: { stepSize: 25, color: '#6b7693' }, grid: { color: '#e2e8f2' }, angleLines: { color: '#e2e8f2' } } },
    plugins: { legend: { display: false } },
  },
});
</script>
<script src="/static/app.js"></script>
{% endblock %}
```

- [ ] **Step 5: Append to `routes/pages.py`**

```python
import json

from fastapi import HTTPException

from services.case_registry import find_case
from services.insights_composer import build_headline_payload, compose_headline, compose_rule_list
from config import get_settings


@router.get("/case/{slug}")
def dashboard(request: Request, slug: str):
    info = find_case(slug)
    if info is None:
        raise HTTPException(status_code=404, detail="case not found")
    bundle = load_case_bundle(info)
    tone_shift_row = (bundle.raw.get("tone_shift", {}).get("tone_shift_results") or [{}])[0]
    rule_list = compose_rule_list(
        scores=bundle.scores,
        qna_rows=bundle.qna_rows,
        tone_shift_flag=bool(tone_shift_row.get("tone_shift_flag")),
        negative_score_shift=float(tone_shift_row.get("negative_score_shift") or 0.0),
    )
    settings = get_settings()
    headline = compose_headline(
        build_headline_payload(
            slug=bundle.slug,
            scores=bundle.scores,
            tone_shift_flag=bool(tone_shift_row.get("tone_shift_flag")),
            qna_rows=bundle.qna_rows,
        ),
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
    )

    radar = {k: bundle.scores.get(k, 0) for k in ("直接性", "具體性", "迴避度", "語氣落差", "一致性")}
    return TEMPLATES.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "bundle": bundle,
            "radar_json": json.dumps(radar, ensure_ascii=False),
            "headline": headline,
            "worth_tracking": rule_list["worth_tracking"],
            "disclosure_risks": rule_list["disclosure_risks"],
        },
    )
```

- [ ] **Step 6: Run tests, PASS. Commit.**

```bash
cd frontend && git add templates/dashboard.html templates/partials/insights.html routes/pages.py tests/test_routes_pages.py && git commit -m "feat(pages): dashboard with hero + radar + insights + Q&A table + chat shell"
```

---

## Task 25: Upload route + SSE progress

**Files:**
- Create: `frontend/routes/upload.py`
- Modify: `frontend/app.py`
- Create: `frontend/tests/test_routes_upload.py`

- [ ] **Step 1: Failing test**

```python
import io

from docx import Document
from fastapi.testclient import TestClient

from app import app


def _make_docx_bytes() -> bytes:
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Welcome.")
    doc.add_paragraph("Q: demand?")
    doc.add_paragraph("A: strong.")
    doc.save(buf)
    return buf.getvalue()


def test_upload_starts_job(monkeypatch):
    async def fake_process(**kwargs):
        kwargs["store"].update(kwargs["job_id"],
                               status=__import__("services.job_store", fromlist=["JobStatus"]).JobStatus.DONE,
                               step="done")

    monkeypatch.setattr("routes.upload._process_upload", fake_process)
    client = TestClient(app)
    response = client.post(
        "/upload",
        files={"full_docx": ("a.docx", _make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"case_name": "myco"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "myco"
    assert payload["job_id"]
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `routes/upload.py`**

```python
"""Upload endpoint + SSE progress channel."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import StreamingResponse

router = APIRouter()

from services.case_registry import discover_cases
from services.docx_loader import docx_to_text
from services.job_store import JobStatus, get_job_store
from services.slug import make_slug
from services.upload_processor import process_upload as _process_upload


@router.post("/upload")
async def upload(
    background: BackgroundTasks,
    full_docx: UploadFile = File(...),
    qna_docx: UploadFile | None = File(None),
    case_name: str = Form(""),
) -> dict[str, str]:
    tmpdir = Path(tempfile.mkdtemp(prefix="upload_"))
    full_path = tmpdir / (full_docx.filename or "full.docx")
    full_path.write_bytes(await full_docx.read())
    full_text = docx_to_text(full_path)
    qna_text: str | None = None
    if qna_docx is not None and qna_docx.filename:
        qna_path = tmpdir / qna_docx.filename
        qna_path.write_bytes(await qna_docx.read())
        qna_text = docx_to_text(qna_path)

    raw_name = case_name or (full_docx.filename or "")
    taken = {c.slug for c in discover_cases()}
    slug = make_slug(raw_name, taken=taken)

    store = get_job_store()
    job = store.create(slug=slug)
    background.add_task(
        _run_pipeline_async,
        job_id=job.id,
        full_text=full_text,
        qna_text=qna_text,
        slug=slug,
    )
    return {"job_id": job.id, "slug": slug}


async def _run_pipeline_async(*, job_id: str, full_text: str, qna_text: str | None, slug: str) -> None:
    await _process_upload(
        job_id=job_id,
        store=get_job_store(),
        full_text=full_text,
        qna_text=qna_text,
        slug=slug,
    )


@router.get("/sse/job/{job_id}")
async def sse_job(job_id: str) -> StreamingResponse:
    store = get_job_store()
    job = store.get(job_id)
    if job is None:
        return StreamingResponse(iter([f"event: error\ndata: not_found\n\n"]), media_type="text/event-stream")

    async def emit():
        # Replay current status first
        yield f"data: {json.dumps({'status': job.status.value, 'step': job.step})}\n\n"
        async for evt in store.events(job_id):
            yield f"data: {json.dumps(evt)}\n\n"

    return StreamingResponse(emit(), media_type="text/event-stream")
```

- [ ] **Step 4: Wire router in `app.py`**

Add to `app.py`:

```python
from routes.upload import router as upload_router

app.include_router(upload_router)
```

- [ ] **Step 5: Run tests, PASS. Commit.**

```bash
cd frontend && git add routes/upload.py app.py tests/test_routes_upload.py && git commit -m "feat(upload): POST /upload + SSE progress channel"
```

---

## Task 26: Chat SSE route

**Files:**
- Create: `frontend/routes/chat.py`
- Modify: `frontend/app.py`
- Create: `frontend/tests/test_routes_chat.py`

- [ ] **Step 1: Failing test**

```python
from fastapi.testclient import TestClient

from app import app


def test_chat_returns_sse(monkeypatch):
    async def fake_stream(**_kwargs):
        yield "你好"
        yield "，"
        yield "這裡是回覆。"

    monkeypatch.setattr("routes.chat._stream_chat", fake_stream)

    client = TestClient(app)
    with client.stream("GET", "/chat/stream", params={"case": "tsmc", "msg": "hi"}) as response:
        assert response.status_code == 200
        body = "".join(chunk for chunk in response.iter_text())
    assert "你好" in body and "回覆" in body
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Implement `routes/chat.py`**

```python
"""Gemini chat SSE proxy."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from config import get_settings
from services.case_registry import find_case
from services.chat_service import build_context, stream_chat as _stream_chat
from services.precomputed_loader import load_case_bundle

router = APIRouter()


@router.get("/chat/stream")
async def chat_stream(
    case: str = Query(...),
    msg: str = Query(...),
    history: str = Query("[]"),
):
    info = find_case(case)
    if info is None:
        raise HTTPException(status_code=404, detail="case not found")
    bundle = load_case_bundle(info)
    ctx = build_context(bundle)

    try:
        parsed_history = json.loads(history) or []
    except json.JSONDecodeError:
        parsed_history = []

    settings = get_settings()

    async def emit():
        async for piece in _stream_chat(
            context=ctx,
            history=parsed_history,
            user_msg=msg,
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        ):
            yield f"data: {piece}\n\n"
        yield "event: done\ndata: 1\n\n"

    return StreamingResponse(emit(), media_type="text/event-stream")
```

- [ ] **Step 4: Wire router**

`app.py`:

```python
from routes.chat import router as chat_router

app.include_router(chat_router)
```

- [ ] **Step 5: Run tests, PASS. Commit.**

```bash
cd frontend && git add routes/chat.py app.py tests/test_routes_chat.py && git commit -m "feat(chat): GET /chat/stream SSE proxy to Gemini"
```

---

## Task 27: HTMX Q&A partial route

**Files:**
- Create: `frontend/templates/partials/qna_table.html`
- Create: `frontend/routes/partials.py`
- Modify: `frontend/app.py`
- Create: `frontend/tests/test_routes_partials.py`

- [ ] **Step 1: Failing test**

```python
from fastapi.testclient import TestClient

from app import app


def test_partial_returns_table_rows_only():
    response = TestClient(app).get("/api/case/tsmc/qna")
    assert response.status_code == 200
    body = response.text
    assert "<table" in body
    assert "分析師問題" in body
    assert "<html" not in body and "<body" not in body
```

- [ ] **Step 2: Run, expect failure.**

- [ ] **Step 3: Create `templates/partials/qna_table.html`**

```html
<table class="w-full text-sm">
  <thead class="text-muted text-xs uppercase tracking-widest">
    <tr class="border-b border-line">
      <th class="text-left px-5 py-2 w-10">#</th>
      <th class="text-left px-5 py-2">分析師問題</th>
      <th class="text-left px-5 py-2">管理層回答</th>
      <th class="text-left px-5 py-2 w-28">風險標籤</th>
      <th class="text-left px-5 py-2 w-16">分數</th>
    </tr>
  </thead>
  <tbody>
    {% for row in qna_rows %}
    <tr id="qna-{{ row.index }}" class="border-b border-line align-top">
      <td class="px-5 py-3 text-muted">{{ row.index }}</td>
      <td class="px-5 py-3 max-w-md">{{ row.question_translated or row.question }}</td>
      <td class="px-5 py-3 max-w-md">{{ row.answer_translated or row.answer }}</td>
      <td class="px-5 py-3"><span class="text-xs px-2 py-0.5 rounded-full {{ row.risk_label_class }}">{{ row.risk_label_zh }}</span></td>
      <td class="px-5 py-3 font-serif text-ink">{{ row.composite_score }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

- [ ] **Step 4: Implement `routes/partials.py`**

```python
"""HTMX swap targets."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from services.case_registry import find_case
from services.precomputed_loader import load_case_bundle

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/api/case/{slug}/qna")
def qna_partial(request: Request, slug: str):
    info = find_case(slug)
    if info is None:
        raise HTTPException(status_code=404)
    bundle = load_case_bundle(info)
    return TEMPLATES.TemplateResponse("partials/qna_table.html", {"request": request, "qna_rows": bundle.qna_rows})
```

- [ ] **Step 5: Wire router in `app.py`**

```python
from routes.partials import router as partials_router

app.include_router(partials_router)
```

- [ ] **Step 6: Run tests, PASS. Commit.**

```bash
cd frontend && git add templates/partials/qna_table.html routes/partials.py app.py tests/test_routes_partials.py && git commit -m "feat(partials): HTMX Q&A table swap target"
```

---

# Phase 9 — Frontend assets

## Task 28: Client JS — chat + upload modal

**Files:**
- Create: `frontend/static/app.js`

- [ ] **Step 1: Create `static/app.js`**

```javascript
// Chat panel: posts to /chat/stream via EventSource and appends chunks to #chat-log.
(function () {
  const form = document.getElementById('chat-form');
  if (!form) return;
  const log = document.getElementById('chat-log');
  const input = document.getElementById('chat-input');
  const slug = form.dataset.case;
  const history = [];

  function bubble(role, text) {
    const div = document.createElement('div');
    div.className = role === 'me'
      ? 'self-end inline-block px-3 py-2 rounded-xl bg-ink text-white max-w-[85%]'
      : 'self-start inline-block px-3 py-2 rounded-xl bg-accent-soft text-ink max-w-[92%]';
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const msg = (input.value || '').trim();
    if (!msg) return;
    bubble('me', msg);
    history.push({ role: 'user', parts: [msg] });
    input.value = '';

    const bot = bubble('bot', '');
    const url = `/chat/stream?case=${encodeURIComponent(slug)}&msg=${encodeURIComponent(msg)}&history=${encodeURIComponent(JSON.stringify(history))}`;
    const es = new EventSource(url);
    let acc = '';
    es.onmessage = (e) => { acc += e.data; bot.textContent = acc; log.scrollTop = log.scrollHeight; };
    es.addEventListener('done', () => { es.close(); history.push({ role: 'model', parts: [acc] }); });
    es.onerror = () => { es.close(); };
  });
})();
```

- [ ] **Step 2: Commit (no test — this is a static asset; covered indirectly by template tests).**

```bash
cd frontend && git add static/app.js && git commit -m "feat(static): chat panel client wiring via EventSource"
```

---

## Task 29: Vendor Chart.js + htmx + Alpine

**Files:**
- Add: `frontend/static/chart.umd.js`
- Add: `frontend/static/htmx.min.js`
- Add: `frontend/static/alpine.min.js`

- [ ] **Step 1: Download vendored assets**

```bash
cd frontend/static
curl -L -o chart.umd.js https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js
curl -L -o htmx.min.js  https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js
curl -L -o alpine.min.js https://unpkg.com/alpinejs@3.13.5/dist/cdn.min.js
```

- [ ] **Step 2: Verify files**

```bash
ls -la frontend/static/{chart.umd.js,htmx.min.js,alpine.min.js}
# Expected: three files, each > 30KB.
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add static/chart.umd.js static/htmx.min.js static/alpine.min.js && git commit -m "chore(static): vendor Chart.js, htmx, Alpine.js"
```

---

# Phase 10 — Integration & docs

## Task 30: End-to-end integration test on TSMC

**Files:**
- Create: `frontend/tests/test_integration.py`

- [ ] **Step 1: Failing test**

```python
from fastapi.testclient import TestClient

from app import app


def test_landing_then_dashboard_then_partial_for_tsmc():
    client = TestClient(app)

    landing = client.get("/")
    assert landing.status_code == 200
    assert "TSMC" in landing.text

    dash = client.get("/case/tsmc")
    assert dash.status_code == 200
    assert "雷達圖" in dash.text
    assert "Q&A 摘要表" in dash.text
    assert "GEMINI" in dash.text

    partial = client.get("/api/case/tsmc/qna")
    assert partial.status_code == 200
    assert "<table" in partial.text


def test_unknown_case_returns_404():
    response = TestClient(app).get("/case/does-not-exist")
    assert response.status_code == 404
```

- [ ] **Step 2: Run — should PASS already with all prior tasks completed.**

```bash
cd frontend && pytest tests/test_integration.py -v
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add tests/test_integration.py && git commit -m "test(integration): landing + dashboard + partial round-trip on TSMC"
```

---

## Task 31: Manual test plan

**Files:**
- Create: `frontend/tests/manual.md`

- [ ] **Step 1: Write `tests/manual.md`**

```markdown
# Manual test plan

Run these checks after every release of substance. Assumes Azure Translator,
Azure Language, and Gemini keys are filled in `frontend/.env`. Azure OpenAI may
be blank — the upload path falls back to Gemini.

## 1. Boot

- `cd frontend && source .venv/bin/activate && uvicorn app:app --reload --port 8000`
- Open <http://localhost:8000>
- Verify three case cards render: TSMC, NVIDIA, FOXCONN
- Verify each card shows a transparency score and a tone pill
- Verify the upload form is visible at the bottom

## 2. Pre-computed dashboard

For each of `tsmc`, `nvda`, `foxconn`:

- Click the card
- Verify the URL is `/case/<slug>`
- Verify the hero shows the 綜合透明度 number and tone pill
- Verify the radar chart renders 5 axes with sensible values
- Verify the investment-insights panel:
  - LLM headline appears (2-3 TC sentences) if `GEMINI_API_KEY` is set
  - Rule list shows "需要追蹤的回答" with bullets that anchor to Q&A rows
  - Rule list shows "公司資訊揭露風險" entries when applicable
- Verify the Q&A table renders all rows with:
  - Index, translated question, translated answer
  - Risk label chip in the correct color
  - Composite score 0–100

## 3. Gemini chat

On `/case/tsmc`:

- Type "哪一題的透明度最低？" → submit
- Verify a user bubble appears immediately
- Verify a bot bubble starts streaming text within ~2s
- Verify the answer cites a Q&A number
- Submit a follow-up question that depends on history
- Verify the model uses the prior conversation

## 4. Upload flow (Gemini fallback)

- From the landing page, upload an English `.docx` earnings-call transcript
- Watch the modal show stages: translating → extracting_qna → scoring → sentiment → keyphrase → summary → done
- On done, verify redirect to `/case/<your-slug>`
- Verify all five panels render with values reflecting your upload

## 5. Missing-key degradation

- Blank `GEMINI_API_KEY` in `.env` and restart
- Verify dashboards still render; chat panel shows "(未啟用 LLM 對話)"
- Verify insights show only the rule list (no LLM headline)
- Restore key
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add tests/manual.md && git commit -m "docs(tests): manual smoke-test plan"
```

---

## Task 32: README + run instructions

**Files:**
- Create: `frontend/README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# 法說會分析儀表板 — Frontend

A FastAPI dashboard surfacing the project's NLP earnings-call analysis with a
right-docked Gemini chat. Designed to live alongside the four team modules at
the project root and import them without modification.

## Quick start

```bash
cd frontend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in keys (see below); optional for demo mode
uvicorn app:app --reload --port 8000
# open http://localhost:8000
```

## Configuration

See `.env.example`. The four key buckets:

| Key | Required for | Notes |
|---|---|---|
| `AZURE_OPENAI_*` | Upload Q&A extraction (preferred path) | **Optional** — falls back to Gemini |
| `AZURE_TRANSLATOR_*` | Upload translation | Required for upload |
| `AZURE_LANGUAGE_*` | Upload sentiment / keyphrase / PII | Required for upload |
| `GEMINI_*` | Chat + insights headline + Q&A extraction fallback | Recommended |

If all keys are blank, the app still serves the three pre-computed cases
(NVIDIA / TSMC / Foxconn) read directly from the team output directories.

## Tests

```bash
cd frontend && pytest
```

External APIs (Gemini, Azure) are mocked in tests. Real-API verification lives
in `tests/manual.md`.

## Design & implementation docs

- Spec: `docs/superpowers/specs/2026-05-18-frontend-design.md`
- Plan: `docs/superpowers/plans/2026-05-18-frontend-implementation.md`
````

- [ ] **Step 2: Commit**

```bash
cd frontend && git add README.md && git commit -m "docs: README with quick-start, configuration, and links to spec/plan"
```

---

# Self-review checklist (run after writing the plan, before handoff)

- [x] **Spec coverage:** Every section in the spec maps to one or more tasks:
  - §1–3 (goal, constraints, decisions) → README + spec links (Tasks 1, 32)
  - §4 (upstream inventory) → Tasks 10–15 (adapters)
  - §5 (architecture) + §6 (module map) → Tasks 1, 2, and every task that creates a file
  - §6.1 (adapter notes) → Tasks 10–15
  - §7.1 (pre-computed flow) → Tasks 8, 9, 23, 24
  - §7.2 (upload flow) → Tasks 16, 17, 18, 25
  - §7.3 (chat flow) → Tasks 21, 22, 26
  - §8.1–8.5 (custom logic) → Tasks 4, 5, 6, 7, and 9 (per-Q&A signal application)
  - §8.6 (Gemini fallback) → Tasks 14, 15
  - §9 (pages) → Tasks 23, 24
  - §10 (visual design) → Task 23 (base.html palette, fonts)
  - §11 (error matrix) → covered partially in Tasks 24, 22, 18, 25 (graceful degradation paths); fully exercised by `tests/manual.md` in Task 31
  - §12 (testing) → Tasks 3–22, 30, 31
  - §13 (configuration) → Tasks 1, 2, 32
  - §14 (out of scope) → not implemented (intentional)
  - §15 (compliance) → enforced structurally by Tasks 10–15

- [x] **Placeholder scan:** No TBDs, no "implement later", no "similar to Task N". Every code block is complete and self-contained.
- [x] **Type consistency:** `RiskLabel`, `CaseInfo`, `CaseBundle`, `Job`, `JobStatus`, `JobStore`, adapter `run`/`run_sentiment`/`run_keyphrase` signatures are consistent across tasks.
- [x] **Cross-references match:** All `import` statements reference modules created in earlier tasks. All file paths in tests match the implementation paths.

---

## Execution handoff

Plan complete and saved to `frontend/docs/superpowers/plans/2026-05-18-frontend-implementation.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints

Which approach?
