import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
from tool_manager.core.installer import ToolInstaller
from tool_manager.core.updater import ToolUpdater


def test_check_update_available_false_when_not_installed():
    installer = ToolInstaller()
    updater = ToolUpdater(installer)
    with patch.object(installer, "get_installed_version", return_value=None):
        assert updater.check_update_available("ngspice") is False


def test_check_update_available_true_when_outdated():
    installer = ToolInstaller()
    updater = ToolUpdater(installer)
    with patch.object(installer, "get_installed_version", return_value="37.0"):
        assert updater.check_update_available("ngspice") is True


def test_check_update_available_false_when_current():
    installer = ToolInstaller()
    updater = ToolUpdater(installer)
    with patch.object(installer, "get_installed_version", return_value="38.2"):
        assert updater.check_update_available("ngspice") is False
