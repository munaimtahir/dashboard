"""
App Ops Module

Implements safe, allowlisted operations script execution.
CRITICAL SAFETY RULES:
- No arbitrary shell commands
- No arbitrary script paths
- Only allowlisted actions: start, stop, restart, deploy, status, logs
- Scripts must exist at: /home/munaim/srv/apps/<app-folder>/ops/{action}.sh
- Deploy requires typed confirmation header
- Rate limiting on deploy operations
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


# Allowlisted actions
ALLOWED_ACTIONS = {"start", "stop", "restart", "deploy", "status", "logs"}

# Deploy rate limiting: 1 per app per 10 minutes
DEPLOY_RATE_LIMIT_SECONDS = 10 * 60

# Ops logs directory
OPS_LOGS_DIR = "/home/munaim/srv/ops/logs"

# Track running ops jobs per app
_running_jobs_lock = threading.Lock()
_running_jobs: Dict[str, str] = {}  # {app_key: action}

# Track last deploy time per app
_deploy_times_lock = threading.Lock()
_deploy_times: Dict[str, float] = {}  # {app_key: timestamp}


@dataclass
class OpsResult:
    """Result of an ops operation"""
    success: bool
    exit_code: int
    log_file: str
    tail: str
    message: str


class OpsError(Exception):
    """Custom exception for ops errors"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _validate_action(action: str) -> None:
    """Validate that action is allowlisted"""
    if action not in ALLOWED_ACTIONS:
        raise OpsError(f"Action '{action}' not allowed. Allowed: {', '.join(ALLOWED_ACTIONS)}", 400)


def _get_ops_script_path(app_folder: str, action: str) -> Path:
    """
    Get the ops script path for an app and action.
    Validates that folder and script exist.

    Raises:
        OpsError: If folder or script doesn't exist
    """
    folder_path = Path(app_folder)

    if not folder_path.exists():
        raise OpsError(f"App folder not found: {app_folder}", 404)

    ops_dir = folder_path / "ops"
    if not ops_dir.exists() or not ops_dir.is_dir():
        raise OpsError(f"Ops directory not configured for this app", 409)

    script_path = ops_dir / f"{action}.sh"
    if not script_path.exists() or not script_path.is_file():
        raise OpsError(f"Ops script not configured: {action}.sh", 409)

    return script_path


def _get_log_file_path(app_key: str, action: str) -> str:
    """Generate log file path for an ops operation"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{app_key}_{action}_{timestamp}.log"
    return os.path.join(OPS_LOGS_DIR, log_filename)


def _mark_job_running(app_key: str, action: str) -> None:
    """
    Mark a job as running for an app.

    Raises:
        OpsError: If another job is already running for this app
    """
    with _running_jobs_lock:
        if app_key in _running_jobs:
            running_action = _running_jobs[app_key]
            raise OpsError(
                f"Another ops job is already running for this app: {running_action}",
                409
            )
        _running_jobs[app_key] = action


def _mark_job_complete(app_key: str) -> None:
    """Mark a job as complete for an app"""
    with _running_jobs_lock:
        _running_jobs.pop(app_key, None)


def _check_deploy_rate_limit(app_key: str) -> None:
    """
    Check deploy rate limit for an app.

    Raises:
        OpsError: If deploy rate limit exceeded
    """
    now = time.time()

    with _deploy_times_lock:
        last_deploy = _deploy_times.get(app_key)

        if last_deploy:
            elapsed = now - last_deploy
            if elapsed < DEPLOY_RATE_LIMIT_SECONDS:
                remaining = int(DEPLOY_RATE_LIMIT_SECONDS - elapsed)
                raise OpsError(
                    f"Deploy rate limit exceeded. Please wait {remaining} seconds.",
                    429
                )

        _deploy_times[app_key] = now


def _execute_script(script_path: Path, log_file: str, app_key: str) -> Tuple[int, str]:
    """
    Execute an ops script safely.

    Args:
        script_path: Path to the script
        log_file: Path to log file
        app_key: App key for context

    Returns:
        Tuple of (exit_code, tail_output)
    """
    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Execute script WITHOUT shell=True for safety
    # Script must be executable
    try:
        with open(log_file, "w", encoding="utf-8") as log_f:
            # Write header
            log_f.write(f"=== Ops Script Execution ===\n")
            log_f.write(f"App: {app_key}\n")
            log_f.write(f"Script: {script_path}\n")
            log_f.write(f"Started: {datetime.now().isoformat()}\n")
            log_f.write(f"{'=' * 50}\n\n")
            log_f.flush()

            # Execute script
            result = subprocess.run(
                ["/bin/bash", str(script_path)],
                stdout=log_f,
                stderr=subprocess.STDOUT,
                cwd=script_path.parent.parent,  # Run from app folder
                timeout=300,  # 5 minute timeout
            )

            exit_code = result.returncode

            # Write footer
            log_f.write(f"\n{'=' * 50}\n")
            log_f.write(f"Completed: {datetime.now().isoformat()}\n")
            log_f.write(f"Exit Code: {exit_code}\n")

    except subprocess.TimeoutExpired:
        with open(log_file, "a", encoding="utf-8") as log_f:
            log_f.write("\n\n!!! TIMEOUT: Script exceeded 5 minute limit !!!\n")
        exit_code = 124  # Standard timeout exit code

    except Exception as e:
        with open(log_file, "a", encoding="utf-8") as log_f:
            log_f.write(f"\n\n!!! ERROR: {str(e)} !!!\n")
        exit_code = 1

    # Read tail of log
    try:
        with open(log_file, "r", encoding="utf-8") as log_f:
            lines = log_f.readlines()
            tail = "".join(lines[-50:])  # Last 50 lines
    except Exception:
        tail = ""

    return exit_code, tail


def execute_ops_action(
    app_key: str,
    app_folder: str,
    action: str,
    confirm_header: Optional[str] = None,
) -> OpsResult:
    """
    Execute an ops action for an app.

    Args:
        app_key: App key
        app_folder: App folder path
        action: Action to execute (must be allowlisted)
        confirm_header: Confirmation header for deploy action

    Returns:
        OpsResult with execution details

    Raises:
        OpsError: If validation fails or execution errors occur
    """
    # Validate action
    _validate_action(action)

    # Special handling for deploy
    if action == "deploy":
        # Check confirmation header
        expected_confirm = f"DEPLOY {app_key}"
        if confirm_header != expected_confirm:
            raise OpsError(
                f"Deploy requires confirmation header: X-Confirm: {expected_confirm}",
                403
            )

        # Check rate limit
        _check_deploy_rate_limit(app_key)

    # Get script path (validates folder and script exist)
    script_path = _get_ops_script_path(app_folder, action)

    # Check if another job is running
    _mark_job_running(app_key, action)

    try:
        # Generate log file path
        log_file = _get_log_file_path(app_key, action)

        # Execute script
        exit_code, tail = _execute_script(script_path, log_file, app_key)

        success = exit_code == 0
        message = "Success" if success else f"Failed with exit code {exit_code}"

        return OpsResult(
            success=success,
            exit_code=exit_code,
            log_file=log_file,
            tail=tail,
            message=message,
        )

    finally:
        # Always mark job as complete
        _mark_job_complete(app_key)


def get_ops_status(app_key: str, app_folder: str) -> Dict:
    """
    Get ops status for an app.

    Returns:
        Dict with ops configuration status
    """
    folder_path = Path(app_folder)

    if not folder_path.exists():
        return {
            "configured": False,
            "reason": "App folder not found",
            "available_actions": [],
        }

    ops_dir = folder_path / "ops"
    if not ops_dir.exists() or not ops_dir.is_dir():
        return {
            "configured": False,
            "reason": "Ops directory not found",
            "available_actions": [],
        }

    # Check which scripts are available
    available_actions = []
    for action in ALLOWED_ACTIONS:
        script_path = ops_dir / f"{action}.sh"
        if script_path.exists() and script_path.is_file():
            available_actions.append(action)

    # Check if any job is running
    with _running_jobs_lock:
        running_action = _running_jobs.get(app_key)

    return {
        "configured": len(available_actions) > 0,
        "available_actions": available_actions,
        "running_action": running_action,
    }


def get_ops_logs(log_file: str, lines: int = 200) -> str:
    """
    Get ops logs from a log file.

    Args:
        log_file: Path to log file
        lines: Number of lines to return (default 200)

    Returns:
        Log content (last N lines)

    Raises:
        OpsError: If log file doesn't exist
    """
    if not os.path.exists(log_file):
        raise OpsError("Log file not found", 404)

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:]
            return "".join(tail_lines)
    except Exception as e:
        raise OpsError(f"Failed to read log file: {str(e)}", 500)
