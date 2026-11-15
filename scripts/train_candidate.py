#!/usr/bin/env python
"""Crea la candidata v2 (S3-S4) cambiando solo C rispetto alla v1."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from train_baseline import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["--version", "v2", "--C", "0.5", *sys.argv[1:]]))
