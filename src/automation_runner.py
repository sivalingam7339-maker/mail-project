"""Run the existing customer-reply and Form-response workflows once, in order."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import subprocess
import sys

from automation_logger import get_automation_logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXECUTABLE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
CUSTOMER_EMAIL_WORKFLOW = PROJECT_ROOT / "src" / "form_reply_sender.py"
FORM_RESPONSE_WORKFLOW = PROJECT_ROOT / "src" / "new_form_response_processor.py"


@dataclass(frozen=True)
class WorkflowOutcome:
    result: subprocess.CompletedProcess[str] | None
    error: str | None = None

    @property
    def returncode(self) -> int:
        return self.result.returncode if self.result is not None else 1


def print_section(title: str) -> None:
    print("=" * 40)
    print(title)
    print("=" * 40)


def run_workflow(script: Path, workflow_name: str) -> WorkflowOutcome:
    """Run one existing workflow with project-root paths, independent of caller CWD."""
    logger = get_automation_logger()
    logger.info("workflow_start name=%s", workflow_name)
    try:
        result = subprocess.run(
            [str(PYTHON_EXECUTABLE), str(script)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        logger.exception("workflow_exception name=%s error=%s", workflow_name, error)
        return WorkflowOutcome(None, str(error))
    level = logging.INFO if result.returncode == 0 else logging.ERROR
    logger.log(level, "workflow_complete name=%s exit_code=%s", workflow_name, result.returncode)
    return WorkflowOutcome(result)


def print_workflow_output(outcome: WorkflowOutcome) -> None:
    """Print captured child output without concealing stderr or failure status."""
    if outcome.result is None:
        print(f"Workflow could not start: {outcome.error}")
        return
    result = outcome.result
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print("STDERR:")
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode != 0:
        print(f"Workflow failed with exit code {result.returncode}.")


def status_name(outcome: WorkflowOutcome) -> str:
    return "SUCCESS" if outcome.returncode == 0 else "FAILED"


def main() -> int:
    logger = get_automation_logger()
    logger.info("automation_start")
    if not PYTHON_EXECUTABLE.is_file():
        print(f"Error: project Python interpreter not found: {PYTHON_EXECUTABLE}")
        logger.error("automation_failed reason=python_interpreter_missing")
        return 1

    print_section("CUSTOMER EMAIL CHECK")
    customer_result = run_workflow(CUSTOMER_EMAIL_WORKFLOW, "customer_email")
    print_workflow_output(customer_result)

    # Always run Form processing once, even if the customer-email workflow failed.
    print_section("FORM RESPONSE CHECK")
    form_result = run_workflow(FORM_RESPONSE_WORKFLOW, "form_response")
    print_workflow_output(form_result)

    print_section("AUTOMATION RUN COMPLETE")
    print(f"Customer Email Workflow: {status_name(customer_result)}")
    print(f"Form Response Workflow: {status_name(form_result)}")
    overall_success = customer_result.returncode == 0 and form_result.returncode == 0
    print(f"Overall Automation: {'SUCCESS' if overall_success else 'FAILED'}")
    logger.log(
        logging.INFO if overall_success else logging.ERROR,
        "automation_complete overall=%s customer_email_exit_code=%s form_response_exit_code=%s",
        "SUCCESS" if overall_success else "FAILED",
        customer_result.returncode,
        form_result.returncode,
    )
    return 0 if overall_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
