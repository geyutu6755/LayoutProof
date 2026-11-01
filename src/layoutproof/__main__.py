"""Allow ``python -m layoutproof``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
