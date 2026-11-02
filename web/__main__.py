"""Enable ``python -m web`` from the project root."""

from __future__ import annotations

from .server import main

if __name__ == "__main__":
    raise SystemExit(main())
