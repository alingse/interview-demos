"""Main entry point for python -m luma."""

import sys
import asyncio

from luma.cli import main


def cli_main() -> None:
    """Entry point for python -m luma."""
    sys.exit(main())


if __name__ == "__main__":
    cli_main()
