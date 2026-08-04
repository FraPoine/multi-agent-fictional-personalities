"""Start the local FastAPI web interface with Uvicorn."""

import argparse
from collections.abc import Sequence
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"
APPLICATION_IMPORT = "multi_agent_personalities.web.app:app"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _port(value: str) -> int:
    """Parse a valid TCP port for the startup command."""
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "port must be an integer between 1 and 65535"
        ) from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(
            "port must be an integer between 1 and 65535"
        )
    return port


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start the local fictional-personality web interface."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=_port, default=DEFAULT_PORT)
    parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse startup options and run the existing FastAPI application."""
    args = _parser().parse_args(argv)
    uvicorn.run(
        APPLICATION_IMPORT,
        app_dir=str(SOURCE_DIRECTORY),
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
