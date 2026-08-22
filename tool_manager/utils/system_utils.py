"""
system_utils.py
----------------
Small helpers for detecting the host OS, locating package managers,
and running shell commands safely (with captured output for logging).

Kept dependency-free (standard library only) so the tool manager has
no install-time bootstrap problem of its own.
"""

import platform
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Uniform result object returned by run_command()."""
    command: list
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def get_os() -> str:
    """
    Returns a normalized OS key: 'linux', 'darwin' (macOS) or 'windows'.
    This key is used to index into tools_registry.json.
    """
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "darwin"
    return "linux"


def which(executable: str) -> str | None:
    """Thin wrapper over shutil.which for easy mocking/testing."""
    return shutil.which(executable)


def package_manager_available(manager: str) -> bool:
    """
    Checks whether a given package manager binary (apt-get, brew, choco...)
    is available on PATH.
    """
    return which(manager) is not None


def run_command(command: list, timeout: int = 300) -> CommandResult:
    """
    Runs a command as a list of args (never via shell=True, to avoid
    injection issues) and captures stdout/stderr for the logger.

    Never raises on non-zero exit -- callers decide what a failure means
    for their context (e.g. "not installed" vs "real error").
    """
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            command=command,
            returncode=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
        )
    except FileNotFoundError as e:
        return CommandResult(command=command, returncode=127, stdout="", stderr=str(e))
    except subprocess.TimeoutExpired as e:
        return CommandResult(command=command, returncode=124, stdout="", stderr=str(e))
