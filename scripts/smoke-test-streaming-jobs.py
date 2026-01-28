#!/usr/bin/env python3
"""Smoke test for Spark streaming jobs - validates job submission readiness."""

import subprocess
import sys
from typing import List, Tuple


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    NC = "\033[0m"


SPARK_CONTAINER = "rideshare-spark-worker"
JOBS_PATH = "/opt/spark-scripts/jobs"

# Consolidated streaming jobs (as of 2026-01-26):
# - bronze_ingestion_high_volume.py: handles gps_pings topic (high throughput)
# - bronze_ingestion_low_volume.py: handles 7 other topics (trips, driver_status, etc.)
STREAMING_JOBS = [
    "bronze_ingestion_high_volume.py",
    "bronze_ingestion_low_volume.py",
]


def run_command(cmd: List[str], capture_output: bool = True) -> Tuple[int, str]:
    """Run shell command and return exit code and output."""
    try:
        result = subprocess.run(
            cmd, capture_output=capture_output, text=True, timeout=30
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Command timed out"
    except Exception as e:
        return 1, str(e)


def check_container_running() -> bool:
    """Check if Spark worker container is running."""
    exit_code, output = run_command(["docker", "ps"])
    return exit_code == 0 and SPARK_CONTAINER in output


def check_job_file_exists(job_file: str) -> bool:
    """Check if job file exists in container."""
    job_path = f"{JOBS_PATH}/{job_file}"
    exit_code, _ = run_command(
        ["docker", "exec", SPARK_CONTAINER, "test", "-f", job_path]
    )
    return exit_code == 0


def validate_job_syntax(job_file: str) -> Tuple[bool, str]:
    """Validate Python syntax of job file using AST parsing."""
    job_path = f"{JOBS_PATH}/{job_file}"

    syntax_check_script = f"""
import ast
with open('{job_path}', 'r') as f:
    try:
        ast.parse(f.read())
    except SyntaxError as e:
        print(f'SyntaxError: {{e}}')
        exit(1)
"""

    exit_code, output = run_command(
        ["docker", "exec", SPARK_CONTAINER, "python3", "-c", syntax_check_script]
    )

    if exit_code != 0 or "SyntaxError" in output or "IndentationError" in output:
        return False, output

    return True, ""


def validate_job_imports(job_file: str) -> Tuple[bool, str]:
    """Validate that job file has required framework imports."""
    job_path = f"{JOBS_PATH}/{job_file}"

    import_check_script = f"""
import sys
sys.path.insert(0, '/opt/spark-scripts')
try:
    with open('{job_path}', 'r') as f:
        code = f.read()
        if 'from spark_streaming.framework' not in code:
            print('Warning: No framework import found')
except Exception as e:
    print(f'Error: {{e}}')
    exit(1)
"""

    exit_code, output = run_command(
        ["docker", "exec", SPARK_CONTAINER, "python3", "-c", import_check_script]
    )

    if exit_code != 0 and output.startswith("Error:"):
        return False, output

    return True, ""


def test_streaming_job(job_file: str) -> Tuple[bool, str]:
    """Run smoke test for a single streaming job."""
    if not check_job_file_exists(job_file):
        return False, f"Job file not found at {JOBS_PATH}/{job_file}"

    syntax_valid, syntax_error = validate_job_syntax(job_file)
    if not syntax_valid:
        return False, syntax_error

    imports_valid, imports_error = validate_job_imports(job_file)
    if not imports_valid:
        return False, imports_error

    return True, ""


def main():
    """Run smoke tests for all streaming jobs."""
    print("=" * 40)
    print("  Spark Streaming Jobs Smoke Test")
    print("=" * 40)
    print()

    if not check_container_running():
        print(f"{Colors.RED}✗ Spark worker container not running{Colors.NC}")
        return 1

    print(f"{Colors.GREEN}✓ Spark worker container running{Colors.NC}")
    print()

    passed = 0
    failed = 0
    total = len(STREAMING_JOBS)

    for job_file in STREAMING_JOBS:
        job_name = job_file.replace("_streaming_job.py", "")
        print(f"Testing {job_name}... ", end="", flush=True)

        success, error_msg = test_streaming_job(job_file)

        if success:
            print(f"{Colors.GREEN}✓ PASSED{Colors.NC}")
            passed += 1
        else:
            print(f"{Colors.RED}✗ FAILED{Colors.NC}")
            if error_msg:
                for line in error_msg.split("\n"):
                    if line.strip():
                        print(f"  {line}")
            failed += 1

    print()
    print("=" * 40)
    print("  Test Results")
    print("=" * 40)
    print(f"Passed: {Colors.GREEN}{passed}/{total}{Colors.NC}")
    print(f"Failed: {Colors.RED}{failed}/{total}{Colors.NC}")
    print()

    if failed > 0:
        print(
            f"{Colors.RED}Smoke tests failed. Fix errors before running integration tests.{Colors.NC}"
        )
        return 1
    else:
        print(f"{Colors.GREEN}All smoke tests passed!{Colors.NC}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
