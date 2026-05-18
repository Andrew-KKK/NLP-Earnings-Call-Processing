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


from routes.pages import router as pages_router  # noqa: E402

app.include_router(pages_router)

from routes.upload import router as upload_router  # noqa: E402

app.include_router(upload_router)

from routes.chat import router as chat_router  # noqa: E402

app.include_router(chat_router)

from routes.partials import router as partials_router  # noqa: E402

app.include_router(partials_router)


# Temporary preview route — replaced by /case/{slug} once Tasks 23-24 land.
from routes.preview import router as preview_router  # noqa: E402

app.include_router(preview_router)
