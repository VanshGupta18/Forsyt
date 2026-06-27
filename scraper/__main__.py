"""CLI entry point for the scraper package.

Usage:
  python -m scraper schedule            # 5-min continuous loop (default)
  python -m scraper schedule --interval 300
  python -m scraper once                # single cycle then exit
  python -m scraper api                 # start Flask API on :8080
  python -m scraper api --port 8080 --workers 2
"""

from __future__ import annotations

import argparse
import logging
import sys


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def cmd_schedule(args: argparse.Namespace) -> None:
    _setup_logging()
    from .scheduler import run_continuous  # noqa: PLC0415
    run_continuous(interval=args.interval)


def cmd_once(args: argparse.Namespace) -> None:
    _setup_logging()
    from .scheduler import run_once  # noqa: PLC0415
    run_once()


def cmd_api(args: argparse.Namespace) -> None:
    _setup_logging()
    import subprocess, sys  # noqa: E401, PLC0415
    # Use gunicorn when available for production; fall back to Flask dev server
    try:
        import gunicorn  # noqa: F401 PLC0415
        subprocess.run(
            [
                sys.executable, "-m", "gunicorn",
                "-w", str(args.workers),
                "-b", f"0.0.0.0:{args.port}",
                "scraper.api:app",
            ],
            check=True,
        )
    except (ImportError, subprocess.CalledProcessError):
        from .api import create_app  # noqa: PLC0415
        create_app().run(host="0.0.0.0", port=args.port, debug=False)


def main() -> None:
    p = argparse.ArgumentParser(
        prog="python -m scraper",
        description="Forsyt Indian news scraper",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s_sched = sub.add_parser("schedule", help="Continuous scrape loop")
    s_sched.add_argument("--interval", type=int, default=300, help="Seconds between cycles (default 300)")
    s_sched.set_defaults(func=cmd_schedule)

    s_once = sub.add_parser("once", help="Single cycle then exit")
    s_once.set_defaults(func=cmd_once)

    s_api = sub.add_parser("api", help="Start Flask read API")
    s_api.add_argument("--port",    type=int, default=8080)
    s_api.add_argument("--workers", type=int, default=2)
    s_api.set_defaults(func=cmd_api)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
