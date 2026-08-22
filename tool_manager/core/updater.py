"""
updater.py
----------
Covers Requirement 2 (Update and Upgrade System):
  - checks whether an installed tool is behind the version required by eSim
  - runs the platform's native update command with minimal user input

Delegates version detection to ToolInstaller so there's a single source
of truth for "what version is on this machine".
"""

from tool_manager.core.installer import ToolInstaller
from tool_manager.utils.system_utils import run_command, package_manager_available
from tool_manager.core.logger import get_logger

logger = get_logger(__name__)


class ToolUpdater:
    def __init__(self, installer: ToolInstaller = None):
        self.installer = installer or ToolInstaller()

    def check_update_available(self, tool_name: str) -> bool:
        status = self.installer.check_status(tool_name)
        if not status.installed:
            return False
        return not status.up_to_date

    def check_all_updates(self) -> dict:
        """Returns {tool_name: bool} indicating which tools have updates pending."""
        return {t: self.check_update_available(t) for t in self.installer.list_tools()}

    def update(self, tool_name: str, dry_run: bool = False) -> bool:
        meta = self.installer.get_tool_meta(tool_name)
        os_key = self.installer.os_key

        if os_key not in meta:
            logger.error(f"[{tool_name}] No update recipe for OS '{os_key}'.")
            return False

        platform_meta = meta[os_key]
        manager = platform_meta["manager"]

        if not package_manager_available(manager):
            logger.error(f"[{tool_name}] Package manager '{manager}' not available.")
            return False

        if not self.check_update_available(tool_name):
            logger.info(f"[{tool_name}] Already up to date.")
            return True

        cmd = self.installer._with_privilege_escalation(platform_meta["update_cmd"])
        logger.info(f"[{tool_name}] Updating via {manager}: {' '.join(cmd)}")

        if dry_run:
            logger.info(f"[{tool_name}] (dry-run) Would run: {' '.join(cmd)}")
            return True

        result = run_command(cmd, timeout=900)
        if result.ok:
            logger.info(f"[{tool_name}] Updated successfully.")
            return True
        logger.error(f"[{tool_name}] Update failed: {result.stderr or result.stdout}")
        return False

    def update_all(self, dry_run: bool = False) -> dict:
        results = {}
        for tool_name, needs_update in self.check_all_updates().items():
            if needs_update:
                results[tool_name] = self.update(tool_name, dry_run=dry_run)
            else:
                results[tool_name] = True
        return results
