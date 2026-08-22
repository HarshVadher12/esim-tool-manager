import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
from tool_manager.core.installer import ToolInstaller
from tool_manager.core.dependency_checker import DependencyChecker


def test_check_dependencies_reports_missing():
    installer = ToolInstaller()
    checker = DependencyChecker(installer)

    def fake_is_installed(dep):
        return dep == "bison"  # only "bison" is "installed"

    with patch.object(checker, "is_dependency_installed", side_effect=fake_is_installed):
        result = checker.check_dependencies("ngspice")

    assert "bison" in result["satisfied"]
    assert "flex" in result["missing"]


def test_check_dependencies_all_satisfied():
    installer = ToolInstaller()
    checker = DependencyChecker(installer)
    with patch.object(checker, "is_dependency_installed", return_value=True):
        result = checker.check_dependencies("ngveri")
    assert result["missing"] == []
