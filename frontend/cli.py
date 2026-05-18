"""Console entrypoint installed by `pip install -e .` as `earnings-call-dashboard`.

Wraps ``uvicorn app:app`` with a small argparse shell so users can change the
host, port, log level, or enable --reload from the command line without
remembering uvicorn's argument format.
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="earnings-call-dashboard",
        description="Launch the 法說會分析儀表板 FastAPI app.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="bind port (default: 8000)")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="enable auto-reload on file changes (development only)",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="uvicorn log level (default: info)",
    )
    args = parser.parse_args()

    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
