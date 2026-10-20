#!/usr/bin/env python3
"""Run the data pipeline from a checkout without an editable install."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eigenpolitics.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
