#!/usr/bin/env python3
"""
Root launcher for JARVIS AI OS v2.0.

Usage:
    python run.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from jarvis.main import main

if __name__ == "__main__":
    raise SystemExit(main())
