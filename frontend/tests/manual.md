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
