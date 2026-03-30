"""Entry point for Rook Agent."""
import asyncio
import sys

from rook.cli.app import RookApp
from rook.utils.exceptions import RookError


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    app = RookApp()

    try:
        await app.run()
        return 0

    except KeyboardInterrupt:
        # User pressed Ctrl+C
        return 0

    except RookError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
