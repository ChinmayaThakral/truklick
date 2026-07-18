"""Frozen-binary entry point. No args -> control panel; otherwise normal CLI."""
import sys
from truklick.cli import main

if __name__ == "__main__":
    sys.exit(main())
