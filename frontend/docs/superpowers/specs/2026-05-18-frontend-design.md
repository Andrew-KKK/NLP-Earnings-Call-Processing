# 法說會分析儀表板 — Frontend Design

**Date:** 2026-05-18
**Status:** Approved, ready for implementation planning
**Scope:** A modern-minimalist FastAPI web UI that surfaces the project's NLP earnings-call analysis outputs and offers a Gemini-backed follow-up chat.

---

## 1. Goal & context

The project at `/Users/marktsai/Desktop/Projects/自然語言處理_期末專案` contains a four-team NLP pipeline that analyzes 法說會逐字稿 (earnings-call transcripts) and produces translation, Q&A extraction, sentiment, keyphrase, transparency scoring, and PII-redacted summary outputs. The frontend ties these together into a single dashboard view per case and lets users ask follow-up questions about a case via Gemini.

The product must:

- Render exactly the five outputs the user specified (and no extras):
  1. **Q&A 摘要表** — analyst question + management answer per pair
  2. **回答風險標籤** — Direct / Vague / Evasive / Tone-Shift label per pair
  3. **Q&A Transparency Score** — composite quality score
  4. **雷達圖** — 5-dimension management answer quality
  5. **投資洞察摘要** — what to track + disclosure-risk signals
- Display all UI text in **Traditional Chinese**.
- Support **two ingest paths**: pre-computed (read existing team outputs) and live upload (process a new `.docx`).
- Offer a **right-docked Gemini chat** with full case context for follow-up Q&A.

---

## 2. Hard constraints

1. **No upstream modifications.** Team source code under `奕寧_ 摘要&PII/`, `恩泓_ 逐字稿翻譯和 Q&A 擷取/`, `浩誠_回答品質評分/`, and `瑾慈：情緒分析&關鍵字擷取/` must not be edited. The frontend imports their functions through thin adapters.
2. **All new code lives under `frontend/`.**
3. **Output transformations happen in `frontend/services/`.** Any change to how team outputs are presented (e.g., deriving risk labels) is done in the frontend layer, not in the upstream module.
4. **UI text is Traditional Chinese.** Internal logs, code comments, identifiers stay in English.

---

## 3. Decisions locked during brainstorming

| Question | Decision |
|---|---|
| Data source | **Hybrid** — pre-computed for 3 sample companies + upload-driven live pipeline |
| Gemini chat context | **Full case context** (transcript + Q&A + analysis) |
| Outputs surfaced | The user's **5 required outputs only**; other framework outputs available to chat but not displayed |
| Cases shown at once | **One case at a time**; case selector at top |
| Investment-insights composition | **Hybrid** — short LLM-written headline + rule-based bullet list |
| Layout | **Top bar + single scrollable main + persistent right-docked chat** |
| Visual style | **Cool editorial blue** + serif headings (Noto Serif TC) + sans body (Noto Sans TC) |
| Stack | **Jinja2 + HTMX + Alpine.js + Tailwind + Chart.js**, with SSE for chat and upload progress |
| Communication language | English between Claude and the user; Traditional Chinese throughout the product |

---

## 4. Upstream module inventory

| Module | Inputs | Outputs the frontend consumes | API needs |
|---|---|---|---|
| **恩泓** (`恩泓_ 逐字稿翻譯和 Q&A 擷取/source/qa_pipeline.py`) | `.txt` full transcript + `.txt` Q&A-only | `{slug}_full_transcript_translation.json` (paragraph list); `{slug}_extracted_qna_translation.json` (qna_list) | Azure OpenAI (Q&A extraction) **OR Gemini (fallback when Azure OpenAI is not configured — see §8.6)**; Azure Translator (translation) |
| **浩誠** (`浩誠_回答品質評分/run_from_json.py`) | the two 恩泓 JSON files | `{slug}_scores.json` (5-dim + 綜合透明度); `{slug}_transparency_radar.png` | none (lexicon-based) |
| **瑾慈 — sentiment** (`瑾慈：情緒分析&關鍵字擷取/sentiment_analysis.py`) | the two 恩泓 JSON files | `qna_sentiment_summary.json`; `section_sentiment_summary.json`; `company_tone_shift_summary.json` | Azure Language Service |
| **瑾慈 — keyphrase** (`瑾慈：情緒分析&關鍵字擷取/key_phrase_extraction.py`) | same | `qna_keyphrase_summary.json`; `topic_emphasis_summary.json` | Azure Language Service |
| **奕寧** (`奕寧_ 摘要&PII/app.py`) | the two 恩泓 JSON files | `{slug}_*_pii_summary.json` (summary array + pii_redacted_full array) | Azure Language Service |

Pre-computed outputs already exist for `tsmc`, `nvda`, `foxconn` in their respective team output directories.

---

## 5. Architecture

```
┌────────────────────────────────┐
│ Browser  (Traditional Chinese) │
└──────────────┬─────────────────┘
               │ HTTP · HTMX · SSE
               ▼
┌──────────────────────────────────────────────────────────┐
│ FastAPI  (frontend/)                                     │
│                                                          │
│  routes/                                                 │
│    GET  /              → 案件列表 + 上傳                 │
│    GET  /case/{slug}   → 儀表板 (5 panels)               │
│    POST /upload        → 觸發完整 pipeline               │
│    GET  /sse/job/{id}  → 上傳進度 SSE                    │
│    GET  /chat/stream   → Gemini SSE                      │
│                                                          │
│  services/                                               │
│    precomputed_loader  讀取 4 個 team 目錄的 JSON        │
│    upload_processor    docx→txt→pipeline 編排            │
│    risk_labels         flags → 4 類風險標籤              │
│    insights_composer   LLM headline + 規則列表           │
│    chat_service        Gemini 串流 + context builder     │
│    gemini_qna_extractor  Azure OpenAI 不可用時的 fallback│
│                                                          │
│  adapters/    (不修改 upstream 源碼)                     │
│    enhong_adapter      → wraps qa_pipeline.py functions  │
│    haocheng_adapter    → wraps run_from_json.run_one()   │
│    jincing_adapter     → wraps 瑾慈 sentiment + keyphrase│
│    yining_adapter      → wraps 奕寧/app.py functions     │
│                                                          │
│  templates/   Jinja2 + Tailwind classes                  │
│  static/      Chart.js · Alpine · htmx · htmx-sse        │
└──────┬──────────────────────┬──────────────────┬─────────┘
       │                      │                  │
       ▼                      ▼                  ▼
 Team modules         Pre-computed JSON     Gemini API
 (read-only)          frontend/data/cache/  (chat + headline)
       │                      ▲
       ▼                      │
  Azure: OpenAI · Translator · Language
```

---

## 6. Backend module map

```
frontend/
├── app.py                          # FastAPI app + lifespan
├── config.py                       # pydantic-settings; reads .env
├── routes/
│   ├── pages.py                    # GET /, /case/{slug}
│   ├── upload.py                   # POST /upload, GET /sse/job/{id}
│   ├── chat.py                     # GET /chat/stream
│   └── partials.py                 # HTMX swap targets
├── services/
│   ├── precomputed_loader.py       # discover & load team outputs
│   ├── upload_processor.py         # docx→txt→pipeline orchestration
│   ├── risk_labels.py              # derive 直接/模糊/迴避/語氣轉變
│   ├── insights_composer.py        # LLM headline + rule list
│   ├── chat_service.py             # Gemini SSE proxy
│   ├── gemini_qna_extractor.py     # Gemini-based fallback for 恩泓 Q&A extraction
│   ├── case_registry.py            # slug ↔ data-path mapping
│   ├── docx_loader.py              # python-docx → plain text
│   └── job_store.py                # in-memory job state for SSE progress
├── adapters/                       # thin wrappers; no upstream modifications
│   ├── enhong_adapter.py
│   ├── haocheng_adapter.py
│   ├── jincing_adapter.py
│   └── yining_adapter.py
├── templates/
│   ├── base.html                   # layout shell + nav + chat
│   ├── index.html                  # landing + case picker + upload
│   ├── dashboard.html              # the 5-panel page
│   └── partials/                   # HTMX swap targets
│       ├── qna_table.html
│       ├── insights.html
│       └── chat_message.html
├── static/
│   ├── tailwind.css                # pre-built
│   ├── app.js                      # Alpine components
│   ├── chart.umd.js                # vendored Chart.js
│   ├── htmx.min.js                 # vendored
│   └── htmx-sse.js                 # vendored
├── data/
│   └── cache/{slug}/               # outputs for user uploads
├── tests/
│   ├── test_risk_labels.py
│   ├── test_composite_score.py
│   ├── test_insights_rules.py
│   ├── test_slug.py
│   ├── test_adapters.py
│   ├── test_precomputed_loader.py
│   ├── test_routes.py
│   └── manual.md
├── .env.example
├── requirements.txt
└── pyproject.toml
```

---

### 6.1 Adapter implementation notes

Each adapter is a thin wrapper that:

1. **Injects the team module's directory into `sys.path`** at import time so its sibling imports resolve (e.g., `浩誠/run_from_json.py` imports from `json_transcript`, `metrics`, `radar_chart` in the same directory).
2. **Handles module-level config dependencies.** `恩泓/source/qa_pipeline.py` and the two 瑾慈 scripts read a `config.ini` / `.env` at import time. The adapter writes a temporary config file populated from the frontend's `.env` into the module's CWD before import, or uses `unittest.mock.patch` to inject values — whichever is less invasive.
3. **Exposes a single function** with a stable signature (e.g., `enhong_adapter.run(full_text: str, qna_text: str | None) -> tuple[dict, dict]`). The signature is the integration contract; internals can change without affecting the rest of the frontend.
4. **Never writes outside `frontend/data/cache/{slug}/`** (the upstream modules may default to writing into their own `output/` — adapters redirect via function arguments or by changing CWD).
5. **`enhong_adapter` selects between two Q&A extractors at runtime.** If `AZURE_OPENAI_API_KEY` is set, it uses 恩泓's original `extract_qna_from_chunk()`. Otherwise it calls `services.gemini_qna_extractor.extract_qna_from_chunk()`, which emits the same `QnAExtraction` Pydantic shape so downstream code is identical. The rest of `qa_pipeline.py` (chunking, dedup, translation via Azure Translator, JSON envelope) is reused unchanged.

## 7. Data flows

### 7.1 Pre-computed case load (no API cost)

```
Browser → GET /case/tsmc → FastAPI
                              │
                              ▼
                  precomputed_loader.load(slug)
                  ├─ 恩泓 JSON (qna + full transcript)
                  ├─ 浩誠 scores.json + radar.png
                  ├─ 瑾慈 qna_sentiment + qna_keyphrase + section_sentiment + tone_shift + topic_emphasis
                  └─ 奕寧 pii_summary.json (summary + pii_redacted_full)
                              │
                              ▼
                  risk_labels.derive_per_qna(...)
                  insights_composer.compose(...)
                              │
                              ▼
                  Jinja2 renders dashboard.html
```

Latency target: <100 ms. Cached in memory keyed by `(slug, max-mtime over the files)`.

### 7.2 Upload & process

```
POST /upload (multipart: full.docx + optional qna.docx + case_name)
    → upload_processor.start(...)
        background task:
          1. docx_loader.to_text(full.docx)    → full_text
          2. docx_loader.to_text(qna.docx) if absent fall back to full_text
          3. enhong_adapter.run(full_text, qna_text) → 2 JSON files
                 [Q&A extraction: Azure OpenAI if AZURE_OPENAI_API_KEY set, else Gemini fallback]
                 [Translation: Azure Translator]
          4. parallel:
              - haocheng_adapter.run(qna_json, full_json)
              - jincing_adapter.run_sentiment(qna_json, full_json)
              - jincing_adapter.run_keyphrase(qna_json, full_json)
              - yining_adapter.run(qna_json, full_json)
          5. write all outputs into frontend/data/cache/{slug}/
          6. write status.json (per-module success/failure)
          7. emit "done" SSE event
    → returns {job_id, slug}

GET /sse/job/{job_id}      ← browser modal subscribes
    streams: translating → extracting_qna → scoring → sentiment → keyphrase → summary → done
    on done: browser redirects to /case/{slug}
```

**Slug derivation:** lower-case `case_name` if provided, else the uploaded filename stem, else `case-{timestamp}`. Non-alphanumeric characters become `-`. Chinese characters are stripped (the slug is purely for URL/path safety; the display name preserves the original). Collisions get a numeric suffix (`-2`, `-3`, …).

### 7.3 Chat stream

```
Browser opens EventSource("/chat/stream?case=tsmc&msg=…&history_id=…")
    chat_service.build_context(case)
        - Caches a Gemini context bundle per case (full transcript + qna + scores + risk flags + summary bullets)
        - Refreshes when underlying files change
    chat_service.system_prompt (TC)
        - Cite Q numbers when referencing
        - Explain risk labels using underlying flags
        - Politely refuse off-case questions
    gemini.generate_content(stream=True)
        - SSE text chunks back to browser
```

Conversation history is held in the browser's `sessionStorage`. The server is stateless across chat requests aside from the per-case context cache.

---

## 8. Custom logic (the only new logic the frontend introduces)

### 8.1 Per-Q&A risk label (priority cascade)

Each pair gets exactly one label, evaluated in order — first match wins:

| Label | Condition | Sources |
|---|---|---|
| **迴避回答** | `topic_mismatch_flag` OR `risk_downplay_flag` | 瑾慈 keyphrase + sentiment |
| **語氣轉變** | `negative_question_soft_answer_flag` OR `tone_gap_label != "aligned"` | 瑾慈 sentiment |
| **模糊回答** | `overlap_ratio < 0.4` (and neither of the above) | 瑾慈 keyphrase |
| **直接回答** | default | — |

**Rationale:** evasion (skipping the topic / hiding bad news) is more severe than tone shift, which is more notable than vagueness. The cascade keeps labels exclusive so the table reads cleanly.

### 8.2 Per-Q&A composite score (the table's "分數" column)

```
composite = round(
    overlap_ratio * 40
  + (40 if not (topic_mismatch_flag or risk_downplay_flag) else 10)
  + (20 if not negative_question_soft_answer_flag else 5)
)
```

Range 0–100. Uses only signals 瑾慈 already provides. The session-level radar still uses 浩誠's official numbers; this is purely a per-row view.

### 8.3 Per-Q&A topic (short tag)

```
topic = question_key_phrases[:2] joined with "、"
        or question_translated[:8] + "…" if no key phrases
```

Deterministic; no LLM call.

### 8.4 Investment-insights panel

**(a) LLM headline (2-3 TC sentences)** — Gemini call. System prompt (in TC):

```
你是金融分析師。給定法說會 Q&A 的分析結果（透明度分數、風險旗標、情緒落差），
請以繁體中文寫 2-3 句重點摘要：
  1. 整體透明度評價（高 / 中 / 低 + 一句佐證）
  2. 最需追蹤的一題（題號 + 一句原因）
  3. 是否有語氣轉變或揭露風險（若無則略過）
不得編造資料中未出現的細節。
```

Input payload to the model is a compact JSON with `company`, `transparency`, `tone_shift_flag`, `worst_qna`, `flagged_count`.

**(b) Rule-based bullet list** — deterministic and audit-able:

```
需要追蹤的回答:
  · 第 N 題 · {topic} · {risk_label_zh}    ← Q&A with 迴避 or 語氣轉變

公司資訊揭露風險:
  · 整體透明度偏低 ({score}/100)            ← if 綜合透明度 < 50
  · Q&A 階段語氣較簡報轉趨保守 (Δ {x})       ← if tone_shift_flag
  · {n} 題出現負面議題弱化訊號               ← if any per-Q&A risk_downplay_flag
```

Each bullet anchors to its originating Q&A row via `<a href="#qna-{n}">`.

### 8.5 Tone-stability hero pill

```
if company_tone_shift_summary.tone_shift_flag:
    pill = "⚠ 語氣轉趨保守"   (burgundy)
else:
    pill = "● 語氣平穩"        (blue)
```

### 8.6 Gemini Q&A extractor (fallback for Azure OpenAI)

When `AZURE_OPENAI_API_KEY` is unset, the adapter routes per-chunk Q&A extraction through Gemini instead of 恩泓's Azure OpenAI call. Chunking (8000 chars / 1500 overlap), dedup, and translation in `qa_pipeline.py` are reused unchanged — only the per-chunk extraction call swaps out.

**Prompt (system, Traditional Chinese):**

```
你是一位專業的金融數據萃取專家。
請從法說會逐字稿中，精準找出「提問 (Question)」與「回答 (Answer)」配對。

【嚴格規則】：
1. 100% 複製原文，不可摘要。
2. Question 絕不可包含回答；Answer 絕不可為空。
3. 過濾 Operator/串場句（如 "The first question is..."）。
4. 當語氣轉為「給予解答的陳述句」（如 "We expect...", "Let me answer...", "我們預期..."），
   即為回答的起點，必須在此切斷。

僅以下列 JSON 格式回應，不附加其他文字：
{"qna_list": [{"question": "...", "answer": "..."}, ...]}
```

**Implementation:** `gemini.GenerativeModel(model).generate_content(chunk_text, generation_config={"response_mime_type": "application/json", "response_schema": QnAExtraction_schema})`. The returned JSON is parsed back into the same `QnAExtraction` Pydantic model 恩泓 defines, so downstream filtering and packaging is identical. Same 3-retry policy with exponential backoff.

**Model choice:** `GEMINI_MODEL` env var (default `gemini-2.0-flash`); switch to `gemini-2.5-pro` if extraction accuracy proves shaky on long calls.

---

## 9. Pages

### 9.1 `GET /` — Landing

- Brand header `法說會分析`
- Pre-computed case cards (TSMC / NVIDIA / Foxconn) with score preview and tone pill
- Uploaded case list (if any)
- Upload card (drag-drop `.docx`, case-name field, submit)

### 9.2 `GET /case/{slug}` — Dashboard

Anchors (vertical scroll order):

| Anchor | Renders | Source |
|---|---|---|
| `#hero` | 綜合透明度 + 語氣 pill | `scores.json` + `company_tone_shift_summary.json` |
| `#radar` | Chart.js radar (5-dim) | `scores.json` |
| `#insights` | LLM headline + rule list | composed |
| `#qna` | Q&A table (topic, risk label, composite score) | `extracted_qna_translation.json` + 瑾慈 outputs + `risk_labels.derive_per_qna` |
| `chat-panel` | Right-docked Gemini chat (collapsible on narrow viewports) | Gemini SSE |

---

## 10. Visual design

- **Background:** `#f4f6fa` (cool blue-grey), cards `#ffffff`
- **Text:** `#14213d` (deep navy)
- **Borders:** `#e2e8f2`
- **Accent:** `#1d4ed8` (clean blue), light variant `#e0eaff`
- **Risk-label palette:**
  - 直接回答 → `bg #dceee2 / text #1a5e3c`
  - 模糊回答 → `bg #e0e7ff / text #2547a8`
  - 迴避回答 → `bg #fbe1e3 / text #9a1f30`
  - 語氣轉變 → `bg #e9e3f8 / text #4e3a96`
- **Typography:** Noto Serif TC (headings + numerals), Noto Sans TC (body / UI)
- **Layout:** top bar (40 px) + main scroll + right-docked chat panel (~280 px)

---

## 11. Error handling matrix

| Scenario | User-facing behavior (TC) | Behind the scenes |
|---|---|---|
| Pre-computed file missing | 「此案件尚未完整處理：缺少 {file}」 | Other panels still render; missing panel shows placeholder |
| Upload: docx parse fails | 「無法解析此檔案，請確認為 .docx 格式」 | Job marked failed before pipeline starts |
| Upload: a downstream module errors | 「{module} 處理失敗：{reason}。其他面板已可瀏覽。」 | Other modules continue; `status.json` records per-module result |
| Missing Azure OpenAI (Gemini available) | Silent fallback to Gemini Q&A extractor; no UI change | Logged at INFO; uploads succeed normally |
| Missing Azure Translator | Upload card replaced with 「需設定 Azure Translator 金鑰才能上傳新案件」 | Pre-computed cases still work |
| Missing Azure Language | Upload runs but sentiment / keyphrase / PII fail per-module via `status.json` | Whatever succeeded renders; failed panels show placeholder |
| Missing BOTH Azure OpenAI AND Gemini | Upload disabled with 「需設定 Gemini 或 Azure OpenAI 金鑰才能擷取 Q&A」 | Pre-computed cases still work |
| Missing Gemini key (Azure OpenAI available) | Chat hidden; insights show rule list only with 「（未啟用 LLM 摘要）」 | Uploads still work via Azure OpenAI |
| Chat: Gemini rate-limit / network error | Error bubble in chat with retry | SSE closes with `error` event |
| Slug collision on upload | Server appends `-2`, `-3`, … silently | Final slug returned in job response |

---

## 12. Testing strategy

| Layer | What we test | How |
|---|---|---|
| Unit · risk labels | 4-way cascade, edge cases | pytest table-driven, ~15 cases |
| Unit · composite score | Boundary values (overlap 0 / 0.4 / 1.0; flag combinations) | pytest parametrize |
| Unit · insights rule list | Bullets fire only when conditions hold | pytest with synthetic JSON fixtures |
| Unit · slug | Collisions, Chinese-filename sanitization | pytest |
| Integration · adapters | Each adapter loads a sample team JSON and returns the expected shape | pytest using real TSMC/NVDA/Foxconn outputs |
| Integration · pre-computed loader | Builds full case dict from real team directories | pytest against real data |
| Integration · routes | `/` and `/case/{slug}` render; HTML contains expected anchors and label tags | FastAPI `TestClient` |
| Manual | Upload flow with one real .docx; chat with full context; missing-key degradation | `frontend/tests/manual.md` |

**Out of scope:** mocking Azure APIs end-to-end; browser E2E (Playwright).

---

## 13. Configuration

Single `.env` at `frontend/.env`:

```
# Azure OpenAI — OPTIONAL. If blank, Gemini handles Q&A extraction (see §8.6).
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT=

# Azure Translator — REQUIRED for upload flow (translation step).
AZURE_TRANSLATOR_KEY=                          # fill in locally; see frontend/.env.example
AZURE_TRANSLATOR_REGION=
AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com

# Azure Language Service — REQUIRED for upload flow (sentiment + keyphrase + PII + summary).
AZURE_LANGUAGE_KEY=                            # fill in locally
AZURE_LANGUAGE_ENDPOINT=                       # fill in locally

# Gemini — REQUIRED for chat, insights headline, and Q&A extractor fallback.
GEMINI_API_KEY=                                # fill in locally
GEMINI_MODEL=gemini-2.0-flash

PRECOMPUTED_ROOT=..
CACHE_DIR=./data/cache
LOG_LEVEL=INFO
```

Run:

```
cd frontend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # optional for demo
uvicorn app:app --reload --port 8000
```

**Demo mode:** all keys blank → pre-computed cases only, no chat, no LLM headline (rule list still shown).

---

## 14. Out of scope (for this iteration)

- Browser E2E tests
- Authentication / multi-user
- Persistent chat history on the server
- Cross-company comparison view
- Surfacing the extra outputs the framework also produces (section sentiment, topic emphasis, etc.) — they remain available to the chat as context only
- Mobile-first layout (desktop-first; chat collapses on narrow viewports)
- Real-time pipeline cancellation (the upload job runs to completion or fails)

---

## 15. Constraint compliance summary

- ✅ Upstream code never modified — adapters import only.
- ✅ All new code under `frontend/` (this spec lives at `frontend/docs/superpowers/specs/`).
- ✅ Output transformations live in `frontend/services/`.
- ✅ UI text in Traditional Chinese.
- ✅ Code comments / identifiers / logs in English.
