"""
Test that all DBT models have complete documentation.
"""

import json
from pathlib import Path


def test_all_models_have_descriptions():
    """Verify all models have descriptions in schema.yml files."""
    manifest_path = Path(
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt/target/manifest.json"
    )

    assert manifest_path.exists(), "Run 'dbt compile' first to generate manifest.json"

    with open(manifest_path) as f:
        manifest = json.load(f)

    models_without_descriptions = []
    test_models_to_skip = ["bronze_gps_pings", "bronze_driver_status"]

    for node_id, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") == "model":
            model_name = node.get("name")

            if model_name in test_models_to_skip:
                continue

            description = node.get("description", "").strip()

            if not description:
                models_without_descriptions.append(model_name)

    assert (
        len(models_without_descriptions) == 0
    ), f"Models missing descriptions: {', '.join(models_without_descriptions)}"


def test_documentation_files_exist():
    """Verify all required documentation files exist."""
    base_path = Path(
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt"
    )

    required_files = [
        "models/overview.md",
        "models/staging/staging_overview.md",
        "models/marts/marts_overview.md",
        "models/staging/doc_blocks.md",
        "README.md",
    ]

    missing_files = []
    for file_path in required_files:
        full_path = base_path / file_path
        if not full_path.exists():
            missing_files.append(file_path)

    assert (
        len(missing_files) == 0
    ), f"Missing documentation files: {', '.join(missing_files)}"


def test_doc_blocks_referenced_in_schema():
    """Verify doc blocks are referenced in schema.yml files."""
    base_path = Path(
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt"
    )

    schema_files = [
        base_path / "models/staging/schema.yml",
        base_path / "models/marts/dimensions/schema.yml",
    ]

    doc_block_found = False
    for schema_file in schema_files:
        if schema_file.exists():
            content = schema_file.read_text()
            if "{{ doc(" in content:
                doc_block_found = True
                break

    assert doc_block_found, (
        "No doc block references found in schema.yml files. "
        "Expected to find {{ doc('block_name') }} syntax."
    )


def test_catalog_json_exists():
    """Verify dbt docs generate creates catalog.json."""
    catalog_path = Path(
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt/target/catalog.json"
    )

    assert (
        catalog_path.exists()
    ), "catalog.json not found. Run 'dbt docs generate' to create it."


def test_manifest_json_exists():
    """Verify dbt docs generate creates manifest.json."""
    manifest_path = Path(
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt/target/manifest.json"
    )

    assert (
        manifest_path.exists()
    ), "manifest.json not found. Run 'dbt compile' or 'dbt docs generate' to create it."


def test_lineage_shows_bronze_to_silver():
    """Verify lineage graph shows Bronze → Silver dependencies."""
    manifest_path = Path(
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt/target/manifest.json"
    )

    assert manifest_path.exists(), "Run 'dbt compile' first to generate manifest.json"

    with open(manifest_path) as f:
        manifest = json.load(f)

    stg_trips_found = False
    bronze_reference_found = False

    for node_id, node in manifest.get("nodes", {}).items():
        if node.get("name") == "stg_trips":
            stg_trips_found = True
            raw_code = node.get("raw_code", "").lower()

            if "bronze_trips" in raw_code:
                bronze_reference_found = True
            break

    assert stg_trips_found, "stg_trips model not found in manifest"
    assert (
        bronze_reference_found
    ), "stg_trips model does not reference bronze_trips table in compiled SQL"


def test_lineage_shows_silver_to_gold():
    """Verify lineage graph shows Silver → Gold dependencies."""
    manifest_path = Path(
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt/target/manifest.json"
    )

    assert manifest_path.exists(), "Run 'dbt compile' first to generate manifest.json"

    with open(manifest_path) as f:
        manifest = json.load(f)

    fact_trips_found = False
    required_dependencies = ["stg_trips", "dim_riders", "dim_drivers", "dim_zones"]
    found_dependencies = []

    for node_id, node in manifest.get("nodes", {}).items():
        if node.get("name") == "fact_trips":
            fact_trips_found = True
            depends_on = node.get("depends_on", {}).get("nodes", [])

            for dep in depends_on:
                for required_dep in required_dependencies:
                    if required_dep in dep:
                        found_dependencies.append(required_dep)
            break

    assert fact_trips_found, "fact_trips model not found in manifest"

    missing_deps = set(required_dependencies) - set(found_dependencies)
    assert (
        len(missing_deps) == 0
    ), f"fact_trips missing expected dependencies: {', '.join(missing_deps)}"


def test_key_columns_have_descriptions():
    """Verify key columns have descriptions in schema.yml files."""
    manifest_path = Path(
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt/target/manifest.json"
    )

    assert manifest_path.exists(), "Run 'dbt compile' first to generate manifest.json"

    with open(manifest_path) as f:
        manifest = json.load(f)

    key_columns_without_descriptions = []

    for node_id, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") == "model":
            model_name = node.get("name")
            columns = node.get("columns", {})

            for col_name, col_info in columns.items():
                if (
                    "_key" in col_name
                    or "_id" in col_name
                    or col_name in ["timestamp", "fare", "rating"]
                ):
                    description = col_info.get("description", "").strip()
                    if not description:
                        key_columns_without_descriptions.append(
                            f"{model_name}.{col_name}"
                        )

    assert (
        len(key_columns_without_descriptions) == 0
    ), f"Key columns missing descriptions: {', '.join(key_columns_without_descriptions[:10])}"
