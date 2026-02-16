"""Tests for CI/CD workflow configuration."""

from pathlib import Path

import pytest
import yaml


# Module-level marker: no Docker profiles required (file-based tests only)
pytestmark = pytest.mark.requires_profiles()


WORKFLOW_PATH = Path(".github/workflows/nightly-integration-tests.yml")


def load_workflow():
    """Load the workflow YAML file."""
    if not WORKFLOW_PATH.exists():
        return None
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def get_on_config(workflow):
    """Get the 'on' config, handling YAML's parsing of 'on' as boolean True."""
    # YAML 1.1 parses 'on' as boolean True
    return workflow.get("on") or workflow.get(True, {})


class TestWorkflowStructure:
    """Verify CI/CD workflow file structure and configuration."""

    def test_workflow_file_exists(self):
        """Workflow file should exist at expected path."""
        assert WORKFLOW_PATH.exists(), f"Workflow file not found at {WORKFLOW_PATH}"

    def test_workflow_has_required_triggers(self):
        """Workflow should trigger on schedule and manual dispatch."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        on_config = get_on_config(workflow)
        assert "schedule" in on_config, "Workflow should trigger on schedule"
        assert "workflow_dispatch" in on_config, "Workflow should support manual dispatch"

    def test_workflow_has_timeout(self):
        """Workflow should have timeout configured."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        jobs = workflow.get("jobs", {})
        integration_job = jobs.get("integration-tests")
        assert integration_job is not None, "Workflow should have integration-tests job"

        timeout = integration_job.get("timeout-minutes")
        assert timeout is not None, "Integration tests job should have a timeout"
        assert timeout >= 30, "Timeout should be at least 30 minutes"

    def test_workflow_uses_valid_runner(self):
        """Workflow should use runner with sufficient resources."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        jobs = workflow.get("jobs", {})
        valid_runners = [
            "ubuntu-latest",
            "ubuntu-latest-8-cores",
            "ubuntu-latest-16-cores",
            "ubuntu-22.04",
        ]
        for job_name, job_config in jobs.items():
            runs_on = job_config.get("runs-on", "")
            assert any(
                runner in runs_on for runner in valid_runners
            ), f"Job '{job_name}' should use a valid Ubuntu runner"

    def test_workflow_has_docker_steps(self):
        """Workflow should contain Docker Compose commands."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        jobs = workflow.get("jobs", {})
        found_docker_compose = False

        for job_config in jobs.values():
            steps = job_config.get("steps", [])
            for step in steps:
                run_cmd = step.get("run", "")
                if "docker compose" in run_cmd:
                    found_docker_compose = True
                    break

        assert found_docker_compose, "Workflow should contain 'docker compose' commands"

    def test_workflow_uploads_artifacts(self):
        """Workflow should upload test results as artifacts."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        jobs = workflow.get("jobs", {})
        found_upload = False

        for job_config in jobs.values():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "actions/upload-artifact" in uses:
                    found_upload = True
                    break

        assert found_upload, "Workflow should use 'actions/upload-artifact'"

    def test_workflow_has_cleanup_step(self):
        """Workflow should have cleanup step with if: always()."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        jobs = workflow.get("jobs", {})
        found_cleanup = False

        for job_config in jobs.values():
            steps = job_config.get("steps", [])
            for step in steps:
                step_if = step.get("if", "")
                run_cmd = step.get("run", "")
                if "always()" in step_if and "docker compose" in run_cmd and "down" in run_cmd:
                    found_cleanup = True
                    break

        assert found_cleanup, "Workflow should have cleanup step with 'if: always()'"
