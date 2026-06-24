"""Command-line entry point: ``python -m metagaap2``.

Launches the MetaGaAP 2 local web app - the FastAPI backend defined in
:mod:`metagaap2.server` served by uvicorn - and, unless told otherwise, opens
the user's default web browser at the app URL once the server has had a moment
to start.

The app is intended to run locally, so it binds to the loopback interface
(``127.0.0.1``) by default. Use ``--host 0.0.0.0`` only if you deliberately want
to expose it on your network.
"""

from __future__ import annotations

import argparse
import threading
import time
import webbrowser

import uvicorn

from . import __version__

__all__ = ["main"]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the server launcher."""
    parser = argparse.ArgumentParser(
        prog="metagaap2",
        description=(
            "Launch the MetaGaAP 2 local web app (FastAPI backend + built UI)."
        ),
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Interface to bind to (default: 127.0.0.1, loopback only).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a web browser after starting the server.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"MetaGaAP 2 {__version__}",
    )
    return parser.parse_args(argv)


def _browser_url(host: str, port: int) -> str:
    """Return the URL a user should open for the given bind host/port.

    A wildcard bind address (``0.0.0.0`` / ``::``) is not a routable address, so
    the browser is pointed at the loopback interface instead.
    """
    display_host = host
    if host in ("0.0.0.0", "::", ""):
        display_host = "127.0.0.1"
    return f"http://{display_host}:{port}/"


def _open_browser_later(url: str, delay: float = 1.0) -> None:
    """Open ``url`` in a background thread after ``delay`` seconds.

    Running in a daemon thread keeps the (blocking) uvicorn server in control of
    the main thread while still giving it time to bind before the browser hits
    the page.
    """

    def _worker() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - a missing browser must not crash the app.
            pass

    thread = threading.Thread(target=_worker, name="metagaap2-open-browser", daemon=True)
    thread.start()


def main(argv: list[str] | None = None) -> None:
    """Parse arguments, optionally open a browser, and run the uvicorn server."""
    args = _parse_args(argv)

    if not args.no_browser:
        _open_browser_later(_browser_url(args.host, args.port))

    uvicorn.run(
        "metagaap2.server:app",
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
