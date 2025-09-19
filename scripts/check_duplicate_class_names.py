#!/usr/bin/env python3
"""Pre-commit hook to detect duplicate class names across the codebase."""
import ast
import sys
from collections import defaultdict
from pathlib import Path


def find_class_definitions(file_path: Path) -> list[str]:
    """Extract class names from a Python file."""
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())
        return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    except Exception:
        return []


def main():
    paths = [Path("simulation/src"), Path("stream-processor/src")]
    class_locations: dict[str, list[str]] = defaultdict(list)

    for base_path in paths:
        if not base_path.exists():
            continue
        for py_file in base_path.rglob("*.py"):
            if "test" in str(py_file):
                continue
            for class_name in find_class_definitions(py_file):
                class_locations[class_name].append(str(py_file))

    duplicates = {name: locs for name, locs in class_locations.items() if len(locs) > 1}

    # Allow documented duplicates and cross-service duplicates
    # Classes are allowed to have the same name when:
    # 1. Documented in NAMING_CONVENTIONS.md (StateSnapshotManager)
    # 2. They exist in separate services (simulation vs stream-processor)
    # 3. They represent different concepts (Trip domain vs Trip ORM)
    ALLOWED_DUPLICATES = {
        "StateSnapshotManager",  # Documented: api/snapshots.py vs redis_client/snapshots.py
        "Trip",  # Domain model in trip.py vs SQLAlchemy model in db/schema.py
        "ErrorStats",  # Internal metrics vs API response model
    }

    # Filter out cross-service duplicates (same name in different services is OK)
    def is_cross_service_only(locations: list[str]) -> bool:
        sim_count = sum(1 for loc in locations if loc.startswith("simulation/"))
        stream_count = sum(
            1 for loc in locations if loc.startswith("stream-processor/")
        )
        return sim_count <= 1 and stream_count <= 1

    unexpected = {
        name: locs
        for name, locs in duplicates.items()
        if name not in ALLOWED_DUPLICATES and not is_cross_service_only(locs)
    }

    if unexpected:
        print("ERROR: Duplicate class names detected:")
        for name, locations in unexpected.items():
            print(f"\n{name}:")
            for loc in locations:
                print(f"  - {loc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
