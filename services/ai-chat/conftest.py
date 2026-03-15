"""Pytest configuration for ai-chat Lambda tests.

Adds the lambda package root to sys.path so handler.py is importable
from the tests/ subdirectory without manipulating sys.path in each test file.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
