"""
Unit tests for ToolInstaller. Uses monkeypatching to avoid depending on
real package managers / network access, so these run anywhere.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
from tool_manager.core.installer import ToolInstaller
from tool_manager.utils.system_utils import CommandResult


def make_installer():
    return ToolInstaller()


def test_list_tools_returns_registry_keys():
    inst = make_installer()
    tools = inst.list_tools()
    assert "ngspice" in tools
    assert "kicad" in tools
    assert "ngveri" in tools


def test_version_tuple_parses_correctly():
    inst = make_installer()
    assert inst._version_tuple("38.2") == (38, 2)
    assert inst._version_tuple("4.1.0+dfsg") == (4, 1, 0)


def test_is_up_to_date_true_when_equal_or_newer():
    inst = make_installer()
    assert inst.is_up_to_date("38.2", "38.2") is True
    assert inst.is_up_to_date("39.0", "38.2") is True
    assert inst.is_up_to_date("38.1", "38.2") is False


def test_is_up_to_date_false_when_not_installed():
    inst = make_installer()
    assert inst.is_up_to_date(None, "38.2") is False


@patch("tool_manager.core.installer.run_command")
def test_get_installed_version_parses_output(mock_run):
    inst = make_installer()
    mock_run.return_value = CommandResult(
        command=["ngspice", "-v"],
        returncode=0,
        stdout="ngspice-38.2 : Circuit level simulation program",
        stderr="",
    )
    version = inst.get_installed_version("ngspice")
    assert version == "38.2"


@patch("tool_manager.core.installer.run_command")
def test_get_installed_version_returns_none_when_absent(mock_run):
    inst = make_installer()
    mock_run.return_value = CommandResult(
        command=["ngspice", "-v"], returncode=127, stdout="", stderr="not found"
    )
    assert inst.get_installed_version("ngspice") is None


def test_unknown_tool_raises_keyerror():
    inst = make_installer()
    try:
        inst.get_tool_meta("not_a_real_tool")
        assert False, "expected KeyError"
    except KeyError:
        pass


@patch("tool_manager.core.installer.package_manager_available", return_value=True)
@patch("tool_manager.core.installer.run_command")
def test_install_dry_run_does_not_execute(mock_run, _mock_pm):
    inst = make_installer()
    with patch.object(inst, "get_installed_version", return_value=None):
        result = inst.install("ngspice", dry_run=True)
    assert result is True
    mock_run.assert_not_called()
