"""
installer.py
------------
Handles installation and version-checking of external tools required by
eSim (ngspice, kicad, ghdl, ...). Reads tool metadata from
tools_registry.json so adding a new tool never requires touching Python
code -- just add a JSON entry.

Covers Requirement 1 (Tool Installation Management):
  - download/install tools automatically via the OS's native package
    manager (apt / brew / choco)
  - OS compatibility check before attempting install
  - version control: compares installed version against the version
    required by eSim
"""

import json
import os
import re
from dataclasses import dataclass

from tool_manager.utils.system_utils import (
    get_os,
    package_manager_available,
    run_command,
)
from tool_manager.core.logger import get_logger

logger = get_logger(__name__)

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "tools_registry.json"
)


@dataclass
class ToolStatus:
    name: str
    installed: bool
    installed_version: str | None
    required_version: str | None
    up_to_date: bool
    description: str = ""
    error: str | None = None


class ToolInstaller:
    def __init__(self, registry_path: str = REGISTRY_PATH):
        self.registry_path = registry_path
        self.registry = self._load_registry()
        self.os_key = get_os()

    # ---------- registry ----------

    def _load_registry(self) -> dict:
        with open(self.registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_tools(self) -> list:
        return list(self.registry.keys())

    def get_tool_meta(self, tool_name: str) -> dict:
        if tool_name not in self.registry:
            raise KeyError(
                f"Unknown tool '{tool_name}'. Known tools: {self.list_tools()}"
            )
        return self.registry[tool_name]

    # ---------- version detection ----------

    def get_installed_version(self, tool_name: str) -> str | None:
        """
        Runs the tool's check_command and extracts the installed version.

        A tool may define a per-OS version_check_override in the registry.
        If present, that command and regex are used instead of the default
        check_command and version_regex.

        Returns None if the tool is not installed or the version cannot
        be determined.
        """

        meta = self.get_tool_meta(tool_name)
        platform_meta = meta.get(self.os_key, {})
        override = platform_meta.get("version_check_override")

        if override:
            check_cmd = override["command"]
            version_regex = override["regex"]
        else:
            check_cmd = meta["check_command"].split()
            version_regex = meta["version_regex"]

        result = run_command(check_cmd, timeout=15)

        # Some tools print version information to stderr instead of stdout.
        combined_output = (
            (result.stdout or "") + "\n" + (result.stderr or "")
        ).strip()

        # 127 is commonly used by shells to indicate command not found.
        if result.returncode == 127 or not combined_output:
            return None

        # First try the registry-defined regex.
        try:
            match = re.search(
                version_regex,
                combined_output,
                re.IGNORECASE,
            )

            if match:
                # The registry regex is expected to contain a capture group.
                if match.lastindex:
                    return match.group(1)

                # If no capture group exists, return the complete match.
                return match.group(0)

        except re.error as exc:
            logger.warning(
                f"[{tool_name}] Invalid version regex '{version_regex}': {exc}"
            )

        # ------------------------------------------------------------------
        # Fallback handling
        # ------------------------------------------------------------------
        # ngspice commonly reports its version in this form:
        #
        #     ngspice-38.2 : Circuit level simulation program
        #
        # Some registry versions may contain a regex intended for a
        # different ngspice output format. Handle the standard ngspice
        # format here so version detection remains reliable.
        # ------------------------------------------------------------------

        if tool_name.lower() == "ngspice":
            ngspice_match = re.search(
                r"\bngspice[-\s]?(\d+(?:\.\d+)+)",
                combined_output,
                re.IGNORECASE,
            )

            if ngspice_match:
                return ngspice_match.group(1)

        # Generic fallback for a simple version number such as:
        #
        #     version 1.2.3
        #     v1.2.3
        #
        generic_match = re.search(
            r"\bv?(\d+(?:\.\d+)+)\b",
            combined_output,
            re.IGNORECASE,
        )

        if generic_match:
            return generic_match.group(1)

        return None

    def is_up_to_date(self, installed: str | None, required: str) -> bool:
        if installed is None:
            return False

        return self._version_tuple(installed) >= self._version_tuple(required)

    @staticmethod
    def _version_tuple(version_str: str):
        parts = re.findall(r"\d+", version_str)
        return tuple(int(p) for p in parts) if parts else (0,)

    # ---------- status ----------

    def check_status(self, tool_name: str) -> ToolStatus:
        meta = self.get_tool_meta(tool_name)

        installed_version = self.get_installed_version(tool_name)
        required_version = meta.get("required_version")

        return ToolStatus(
            name=tool_name,
            installed=installed_version is not None,
            installed_version=installed_version,
            required_version=required_version,
            up_to_date=(
                self.is_up_to_date(installed_version, required_version)
                if installed_version
                else False
            ),
            description=meta.get("description", ""),
        )

    def check_all(self) -> list:
        return [self.check_status(tool) for tool in self.list_tools()]

    # ---------- installation ----------

    def is_platform_supported(self, tool_name: str) -> bool:
        meta = self.get_tool_meta(tool_name)
        return self.os_key in meta

    @staticmethod
    def _with_privilege_escalation(cmd: list) -> list:
        """
        On Linux/macOS, apt/brew-style installs typically need root.

        If we're already root, do not use sudo.
        Otherwise, prepend sudo for apt/apt-get when sudo is available.
        """

        if os.name != "posix":
            return cmd

        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return cmd

        if cmd and cmd[0] in ("apt-get", "apt"):
            from tool_manager.utils.system_utils import which

            if which("sudo"):
                return ["sudo"] + cmd

        return cmd

    def install(self, tool_name: str, dry_run: bool = False) -> bool:
        """
        Installs a tool using the appropriate package manager for the
        current OS. Returns True on success.
        """

        meta = self.get_tool_meta(tool_name)

        if not self.is_platform_supported(tool_name):
            logger.error(
                f"[{tool_name}] No install recipe for OS '{self.os_key}'."
            )
            return False

        platform_meta = meta[self.os_key]
        manager = platform_meta["manager"]

        if not package_manager_available(manager):
            logger.error(
                f"[{tool_name}] Package manager '{manager}' not found on PATH. "
                f"Please install {manager} first, or install {tool_name} manually."
            )
            return False

        already = self.get_installed_version(tool_name)

        if already:
            logger.info(
                f"[{tool_name}] Already installed "
                f"(version {already}). Skipping install."
            )
            return True

        cmd = self._with_privilege_escalation(
            platform_meta["install_cmd"]
        )

        logger.info(
            f"[{tool_name}] Installing via {manager}: {' '.join(cmd)}"
        )

        if dry_run:
            logger.info(
                f"[{tool_name}] (dry-run) Would run: {' '.join(cmd)}"
            )
            return True

        result = run_command(cmd, timeout=900)

        if result.ok:
            logger.info(
                f"[{tool_name}] Installed successfully."
            )
            return True

        logger.error(
            f"[{tool_name}] Install failed: "
            f"{result.stderr or result.stdout}"
        )
        return False