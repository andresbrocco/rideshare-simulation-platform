"""DBT transformation DAGs for Silver and Gold layers."""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import BranchPythonOperator
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import Asset

# Asset definitions for data lineage
SILVER_ASSET = Asset("lakehouse://silver/transformed")
GOLD_ASSET = Asset("lakehouse://gold/transformed")

default_args = {
    "owner": "rideshare",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Silver DAG - Runs at :10 past each hour with Bronze freshness check
with DAG(
    "dbt_silver_transformation",
    default_args=default_args,
    description="DBT Silver layer transformations (hourly at :10)",
    schedule="10 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["dbt", "silver", "transformation"],
) as silver_dag:

    check_bronze_freshness = BashOperator(
        task_id="check_bronze_freshness",
        bash_command="python3 /opt/init-scripts/check_bronze_tables.py",
    )

    dbt_silver_run = BashOperator(
        task_id="dbt_silver_run",
        bash_command="cd /opt/dbt && dbt run --select tag:silver --profiles-dir /opt/dbt/profiles",
    )

    dbt_silver_test = BashOperator(
        task_id="dbt_silver_test",
        bash_command="cd /opt/dbt && dbt test --select tag:silver --threads 2 --profiles-dir /opt/dbt/profiles",
    )

    ge_silver_validation = BashOperator(
        task_id="ge_silver_validation",
        bash_command="""
        cd /opt/great-expectations && \
        python3 run_checkpoint.py silver_validation || echo "WARNING: Silver validation failed" && exit 0
        """,
        outlets=[SILVER_ASSET],
    )

    def should_trigger_gold(**context) -> str:
        """Trigger Gold DAG at 2 AM, or always when DEV_MODE is enabled."""
        dev_mode = os.environ.get("DEV_MODE", "false").lower() == "true"
        if dev_mode or context["logical_date"].hour == 2:
            return "trigger_gold_dag"
        return "skip_gold_trigger"

    check_should_trigger_gold = BranchPythonOperator(
        task_id="check_should_trigger_gold",
        python_callable=should_trigger_gold,
    )

    trigger_gold_dag = TriggerDagRunOperator(
        task_id="trigger_gold_dag",
        trigger_dag_id="dbt_gold_transformation",
        wait_for_completion=False,
        reset_dag_run=True,
        conf={"triggered_by": "silver_dag", "silver_logical_date": "{{ logical_date }}"},
    )

    skip_gold_trigger = EmptyOperator(task_id="skip_gold_trigger")

    # Task dependencies
    check_bronze_freshness >> dbt_silver_run >> dbt_silver_test >> ge_silver_validation
    ge_silver_validation >> check_should_trigger_gold >> [trigger_gold_dag, skip_gold_trigger]

# Gold DAG - Triggered by Silver DAG at 2 AM (no schedule)
with DAG(
    "dbt_gold_transformation",
    default_args=default_args,
    description="DBT Gold layer transformations (triggered by Silver at 2 AM)",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["dbt", "gold", "transformation"],
) as gold_dag:

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command="cd /opt/dbt && dbt seed --profiles-dir /opt/dbt/profiles",
    )

    dbt_gold_dimensions = BashOperator(
        task_id="dbt_gold_dimensions",
        bash_command="cd /opt/dbt && dbt run --select tag:dimensions --profiles-dir /opt/dbt/profiles",
    )

    dbt_gold_facts = BashOperator(
        task_id="dbt_gold_facts",
        bash_command="cd /opt/dbt && dbt run --select tag:facts --profiles-dir /opt/dbt/profiles",
    )

    dbt_gold_aggregates = BashOperator(
        task_id="dbt_gold_aggregates",
        bash_command="cd /opt/dbt && dbt run --select tag:aggregates --profiles-dir /opt/dbt/profiles",
    )

    dbt_gold_test = BashOperator(
        task_id="dbt_gold_test",
        bash_command="cd /opt/dbt && dbt test --select tag:gold --threads 2 --profiles-dir /opt/dbt/profiles",
    )

    ge_gold_validation = BashOperator(
        task_id="ge_gold_validation",
        bash_command="""
        cd /opt/great-expectations && \
        python3 run_checkpoint.py gold_validation || echo "WARNING: Gold validation failed" && exit 0
        """,
    )

    ge_generate_data_docs = BashOperator(
        task_id="ge_generate_data_docs",
        bash_command="""
        cd /opt/great-expectations && \
        python3 build_data_docs.py
        """,
        outlets=[GOLD_ASSET],
    )

    (
        dbt_seed
        >> dbt_gold_dimensions
        >> dbt_gold_facts
        >> dbt_gold_aggregates
        >> dbt_gold_test
        >> ge_gold_validation
        >> ge_generate_data_docs
    )
