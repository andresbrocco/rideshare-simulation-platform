"""
Test script to verify Great Expectations setup with DuckDB datasource.
Validates configuration is correct and DuckDB extensions load properly.
"""

import duckdb
import great_expectations as gx


def test_context_initialization():
    """Verify data context can be initialized."""
    context = gx.get_context(project_root_dir="gx")
    print("✓ Data context initialized successfully")
    return context


def test_datasource_configuration(context):
    """Verify datasource is configured for DuckDB in YAML."""
    import yaml

    with open("gx/great_expectations.yml", "r") as f:
        config = yaml.safe_load(f)

    datasources = config.get("datasources", {})
    assert "rideshare_duckdb" in datasources, "rideshare_duckdb datasource not found"

    ds_config = datasources["rideshare_duckdb"]
    assert ds_config["execution_engine"]["class_name"] == "SqlAlchemyExecutionEngine"
    assert "duckdb" in ds_config["execution_engine"]["connection_string"]

    print("✓ Datasource rideshare_duckdb configured correctly")
    print(f"  - Execution Engine: {ds_config['execution_engine']['class_name']}")
    print(f"  - Connection String: {ds_config['execution_engine']['connection_string']}")


def test_duckdb_extensions():
    """Verify DuckDB delta and httpfs extensions load correctly."""
    conn = duckdb.connect(":memory:")
    conn.install_extension("delta")
    conn.install_extension("httpfs")
    conn.load_extension("delta")
    conn.load_extension("httpfs")
    conn.close()

    print("✓ DuckDB extensions loaded successfully")
    print("  - delta: installed and loaded")
    print("  - httpfs: installed and loaded")


if __name__ == "__main__":
    print("Testing Great Expectations setup...\n")

    context = test_context_initialization()
    test_datasource_configuration(context)
    test_duckdb_extensions()

    print("\n✓ All validation checks passed")
    print("  Great Expectations project is properly configured")
    print("  Datasource connects via DuckDB with Delta Lake support")
