"""
dependency_checker.py
----------------------
Covers Requirement 4 (Dependency Checker):
  - checks OS-level dependencies declared per-tool in the registry
    (e.g. ngspice needs libx11-dev, bison, flex)
  - reports what's missing so the user gets actionable feedback instead
    of an opaque build failure
"""

from tool_manager.core.installer import ToolInstaller
from tool_manager.utils.system_utils import run_command, get_os
from tool_manager.core.logger import get_logger

logger = get_logger(__name__)


class DependencyChecker:
    def __init__(self, installer: ToolInstaller = None):
        self.installer = installer or ToolInstaller()

    def _dpkg_installed(self, package: str) -> bool:
        result = run_command(["dpkg", "-s", package], timeout=15)
        return result.ok

    def _brew_installed(self, package: str) -> bool:
        result = run_command(["brew", "list", package], timeout=15)
        return result.ok

    def is_dependency_installed(self, dependency: str) -> bool:
        os_key = get_os()
        if os_key == "linux":
            return self._dpkg_installed(dependency)
        if os_key == "darwin":
            return self._brew_installed(dependency)
        # Windows dependency checking is package-specific and out of scope
        # for this prototype; assume present and let install surface errors.
        return True

    def check_dependencies(self, tool_name: str) -> dict:
        """
        Returns {"satisfied": [...], "missing": [...]} for a given tool's
        declared dependency list.
        """
        meta = self.installer.get_tool_meta(tool_name)
        deps = meta.get("dependencies", [])

        satisfied, missing = [], []
        for dep in deps:
            if self.is_dependency_installed(dep):
                satisfied.append(dep)
            else:
                missing.append(dep)

        if missing:
            logger.warning(f"[{tool_name}] Missing dependencies: {', '.join(missing)}")
        else:
            logger.info(f"[{tool_name}] All dependencies satisfied.")

        return {"satisfied": satisfied, "missing": missing}

    def check_all(self) -> dict:
        return {t: self.check_dependencies(t) for t in self.installer.list_tools()}
