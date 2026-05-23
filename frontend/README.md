# 法說會分析儀表板 — `earnings-call-dashboard`

A FastAPI dashboard that turns a 法說會逐字稿 (earnings-call transcript) into:

- **Q&A 摘要表** — every analyst question + management answer, with risk label and composite score
- **回答風險標籤** — 直接 / 模糊 / 迴避 / 語氣轉變
- **Q&A Transparency Score** — overall 0-100, plus 5-axis radar
- **投資洞察摘要** — LLM-written 2-3 sentence headline + auditable rule-based bullets
- **Gemini chat** — right-docked panel grounded in the full case

All UI text is Traditional Chinese; the package is designed to wrap the four read-only team modules in the parent project without modifying them.

---

## Quick start

```bash
# 1. Set up environment
cd frontend
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip

# 2. Install (either path works)
pip install -e .                # editable install with all runtime deps
# or:  pip install -r requirements.txt   # equivalent (delegates to -e .)
# add dev tools too:  pip install -e ".[dev]"

# 3. (Optional) Add your API keys
cp .env.example .env            # then edit .env — see "Configuration" below

# 4. Launch
earnings-call-dashboard         # installed console script
# or:  uvicorn app:app --port 8000 --reload
```

Open **http://127.0.0.1:8000** in your browser.

> **Demo mode (no keys required):** all four `.env` API keys can stay blank. The three pre-computed cases (TSMC / NVIDIA / Foxconn) still render fully from disk. The chat will reply with `(未啟用 LLM 對話)` and the LLM-written insights headline will be omitted; everything else works.

---

## What this package contains

| File / dir | Purpose |
|---|---|
| `app.py` | FastAPI entrypoint, mounts routers and `/static` |
| `config.py` | `Settings` from `.env` (Azure + Gemini keys, paths) |
| `cli.py` | console-script wrapper around `uvicorn` |
| `routes/` | `pages` (landing + dashboard), `upload`, `chat`, `partials` (HTMX), `preview` |
| `services/` | pre-computed loader, upload orchestrator, risk-label cascade, insights composer, chat context + streaming, slug, docx loader, job store |
| `adapters/` | thin wrappers around the four team modules — no upstream modifications |
| `templates/` | Jinja2 (`base.html`, `index.html`, `dashboard.html`, `partials/`) |
| `static/` | pre-built `tailwind.css`, vendored Chart.js / htmx / Alpine, chat `app.js` |
| `data/cache/` | per-upload output bundles (gitignored, created at runtime) |
| `tests/` | 66 pytest cases — `pytest -q` |
| `docs/superpowers/` | the design spec and implementation plan |

---

## Configuration

Edit `frontend/.env` (copy from `.env.example`). The keys fall into four buckets:

| Variable(s) | Required for | Notes |
|---|---|---|
| `AZURE_OPENAI_*` | Q&A extraction during upload | **Optional** — if blank, Gemini handles Q&A extraction (see spec §8.6) |
| `AZURE_TRANSLATOR_KEY`, `AZURE_TRANSLATOR_REGION` | Translation during upload | Required for upload |
| `AZURE_LANGUAGE_KEY`, `AZURE_LANGUAGE_ENDPOINT` | Sentiment + keyphrase + PII summary | Required for upload |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Preprocessing (raw ASR) + chat + LLM insights headline + Q&A fallback | Recommended; default model `gemini-2.5-flash` (free-tier eligible). Free tier is 20 req/day per key — see Troubleshooting if you hit a quota error. |

You can also override:

| Variable | Default | What it controls |
|---|---|---|
| `PRECOMPUTED_ROOT` | `..` | Where the four team output dirs live (relative to `frontend/`) |
| `CACHE_DIR` | `./data/cache` | Where upload outputs are written |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Daily use

### Browse a pre-computed case
1. Open `/`
2. Click `TSMC`, `NVIDIA`, or `FOXCONN`
3. Scroll, click anchor links in the insights panel, ask follow-up questions in the chat

### Upload a new transcript
1. From `/`, drag a `.docx` into the upload form (optional separate Q&A-only `.docx`)
2. Give it a case name (e.g. `nvda-2026q1`)
3. Wait ~90 seconds for the pipeline to finish. Stages are reported via SSE:
   `[preprocessing] → translating → scoring → sentiment → keyphrase → summary → done`
   `preprocessing` only fires when the input is raw ASR (no punctuation / no speaker turns); polished `.docx` skips straight to `translating`.
4. Browser lands on `/case/<slug>` with all five panels populated
5. Output bundle is saved at `frontend/data/cache/<slug>/`

### Chat with the case
1. On any dashboard, type into the chat panel on the right
2. Each turn streams via SSE from Gemini, with the full case as context
3. The model is prompted (in Traditional Chinese) to cite Q&A numbers and explain risk labels using underlying signals
4. Bot bubbles render a small subset of markdown — `**bold**`, `*italic*`, `` `code` ``, paragraphs, bullet/numbered lists

---

## Console script reference

After `pip install -e .`:

```bash
earnings-call-dashboard --help

# Common invocations
earnings-call-dashboard                                   # 127.0.0.1:8000
earnings-call-dashboard --host 0.0.0.0 --port 9000        # bind everywhere
earnings-call-dashboard --reload                          # dev mode
earnings-call-dashboard --log-level debug                 # noisy
```

Equivalent without the script: `uvicorn app:app --port 8000`.

---

## Tests

```bash
pip install -e ".[dev]"        # if not done already
pytest                          # 66 tests, ~15s
pytest -k risk_labels -v       # one module
pytest --collect-only           # list everything
```

External APIs are mocked everywhere in the suite — no Azure or Gemini quota is consumed. Manual smoke-test plan lives at `tests/manual.md`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot create a GUI FigureManager outside the main thread using the MacOS backend` | Already handled — `adapters/haocheng_adapter.py` forces `matplotlib.use("agg")` at import. Reinstall if you pulled. |
| Gemini 429 `limit: 0, model: gemini-2.0-flash` | The legacy `gemini-2.0-flash` model is no longer on the free tier. Default is now `gemini-2.5-flash`; if you customised `.env`, switch back, or enable billing on the Google Cloud project tied to the key. |
| `ModuleNotFoundError: google.genai` on first raw-ASR upload | The new Gemini SDK is bundled as a separate package (`google-genai`). Re-run `pip install -e .` from `frontend/` to pick it up after pulling. |
| Pipeline emits `SystemExit: 沒有讀到任何 Q&A` | The Q&A extractor returned zero pairs (rate-limit, wrong model, or 0-byte input). Check `data/cache/<slug>/status.json` for per-module errors. |
| Dashboard shows score `0/100` and empty radar | Pre-computed JSON files are missing for that case. Run the team pipeline or re-upload. |
| Chat shows `(未啟用 LLM 對話)` | `GEMINI_API_KEY` is blank in `.env`. |
| `ModuleNotFoundError: No module named 'app'` when running tests outside `frontend/` | Always run from `frontend/`. `pip install -e .` makes `app`, `config`, `cli`, `routes`, `services`, `adapters` importable anywhere — but the team source directories at `..` are still resolved relative to the install path, so the cwd needs to be `frontend/` for the adapters to find them. |

---

## Architecture & decisions

- Full design rationale: [`docs/superpowers/specs/2026-05-18-frontend-design.md`](docs/superpowers/specs/2026-05-18-frontend-design.md)
- Step-by-step implementation plan: [`docs/superpowers/plans/2026-05-18-frontend-implementation.md`](docs/superpowers/plans/2026-05-18-frontend-implementation.md)

Short version: server-rendered HTML via Jinja2 + a tiny `app.js` for SSE chat and markdown rendering; everything else is plain HTML/Tailwind. Adapters wrap upstream team modules via `sys.path` + `chdir` (serialized because `os.chdir` is process-global). Gemini supplies both the chat and the Q&A-extraction fallback when Azure OpenAI isn't configured.
