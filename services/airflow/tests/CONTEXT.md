# CONTEXT.md — Airflow Tests

## Purpose

Structural and behavioral tests for Airflow DAGs using Airflow's own `DagBag` introspection API. These tests validate DAG graph topology, task types, schedules, and command correctness without executing tasks in a live Airflow environment.

## Responsibility Boundaries

- **Owns**: Verification that DAG definitions are loadable, have correct task graphs, correct operator types, correct schedule expressions, and correct bash commands
- **Delegates to**: The `services/airflow/dags/` module for the actual DAG definitions being tested
- **Does not handle**: End-to-end pipeline integration testing, live task execution, or data correctness assertions

## Key Concepts

- **DagBag introspection**: Tests load DAGs via `airflow.models.DagBag` pointed at the `dags/` folder. This parses DAG Python files in-process, allowing graph structure inspection without a running Airflow scheduler.
- **Soft-failure GE validation**: Great Expectations validation tasks are intentionally non-blocking — tests assert that bash commands contain `exit 0` after a warning, ensuring GE failures log a warning but never halt the pipeline.
- **OPTIMIZE-before-VACUUM barrier**: The delta maintenance DAG enforces a global ordering: all `optimize_*` tasks fan out from `start`, converge at `optimize_complete`, then all `vacuum_*` tasks fan out, converge at `vacuum_complete`, then `summarize`. Tests verify this two-phase barrier pattern explicitly.
- **Conditional Gold trigger**: Silver DAG conditionally triggers the Gold DAG only after GE validation passes a threshold check (`check_should_trigger_gold` BranchPythonOperator). Tests verify both the branch task and both downstream arms (`trigger_gold_dag`, `skip_gold_trigger`) exist.

## Non-Obvious Details

- The `dagbag` fixture uses a **hardcoded absolute path** to the `dags/` folder. This means tests must be run from within the Docker container or an environment where that path resolves — not from the host machine's arbitrary working directory.
- GE tasks must run from `/opt/great-expectations` inside the container; tests assert the `cd /opt/great-expectations` prefix in bash commands.
- The DLQ monitoring schedule `"3,18,33,48 * * * *"` (every 15 minutes with a 3-minute offset) is deliberately offset from the top of the hour to avoid contention with the Silver DAG that runs at `:10`.
- `test_delta_maintenance_dag.py` counts exactly 16 OPTIMIZE and 16 VACUUM tasks (8 Bronze + 8 DLQ tables) and excludes barrier tasks (`optimize_complete`, `vacuum_complete`) from those counts.

## Related Modules

- [services/airflow/dags](../dags/CONTEXT.md) — Dependency — Airflow DAG definitions orchestrating the Bronze-to-Silver-to-Gold medallion pip...
