"""Pytest configuration for stream processor tests."""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Pre-import modules that are patched in tests to make them available in src namespace
import src.processor  # noqa: F401, E402
