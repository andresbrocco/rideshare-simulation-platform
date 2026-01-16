#!/usr/bin/env python3
"""
CLI wrapper for building Great Expectations data docs.
GE 1.x removed the CLI, so this script provides a command-line interface.
"""

import sys
import great_expectations as gx


def build_data_docs() -> int:
    """
    Build Great Expectations data documentation.

    Returns:
        0 if successful, 1 if failed
    """
    try:
        # Initialize context from gx directory
        context = gx.get_context(project_root_dir="gx")

        # Build data docs
        context.build_data_docs()

        print("✓ Data docs built successfully")
        return 0

    except Exception as e:
        print(f"✗ Error building data docs: {e}")
        return 1


if __name__ == "__main__":
    exit_code = build_data_docs()
    sys.exit(exit_code)
