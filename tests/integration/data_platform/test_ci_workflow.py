"""Tests for CI/CD workflow configuration."""

from pathlib import Path

import yaml


WORKFLOW_PATH = Path(".github/workflows/integration-tests.yml")


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
        """Workflow should trigger on push to main and pull requests."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        on_config = get_on_config(workflow)
        assert "push" in on_config, "Workflow should trigger on push"
        assert "pull_request" in on_config, "Workflow should trigger on pull_request"

        push_branches = on_config.get("push", {}).get("branches", [])
        assert "main" in push_branches, "Workflow should trigger on push to main"

    def test_workflow_has_timeout(self):
        """Workflow should have 30-minute timeout configured."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        jobs = workflow.get("jobs", {})
        assert len(jobs) > 0, "Workflow should have at least one job"

        for job_name, job_config in jobs.items():
            timeout = job_config.get("timeout-minutes")
            assert timeout == 30, f"Job '{job_name}' should have 30-minute timeout"

    def test_workflow_uses_large_runner(self):
        """Workflow should use runner with sufficient resources."""
        workflow = load_workflow()
        assert workflow is not None, "Workflow file not found"

        jobs = workflow.get("jobs", {})
        for job_name, job_config in jobs.items():
            runs_on = job_config.get("runs-on", "")
            # Accept ubuntu-latest or larger runners (8-core, 16-core)
            valid_runners = [
                "ubuntu-latest",
                "ubuntu-latest-8-cores",
                "ubuntu-latest-16-cores",
                "ubuntu-22.04",
            ]
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
                if (
                    "always()" in step_if
                    and "docker compose" in run_cmd
                    and "down" in run_cmd
                ):
                    found_cleanup = True
                    break

        assert found_cleanup, "Workflow should have cleanup step with 'if: always()'"
