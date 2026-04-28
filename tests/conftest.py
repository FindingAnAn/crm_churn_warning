"""Pytest configuration — ensure src/ is on the Python path.

This conftest.py adds src/ to sys.path so that tests can import
modules using the same package paths as production code.
"""

import sys
from pathlib import Path

# Add src/ to Python path for test imports
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
