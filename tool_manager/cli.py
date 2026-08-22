"""
cli.py
------
Command-line interface for the eSim Automated Tool Manager.
Covers Requirement 5 (User Interface):
  - list installed tools, versions, available updates
  - trigger install / update / dependency-check actions
  - every action is logged to logs/tool_manager.log

Usage:
    python -m tool_manager.cli list
    python -m tool_manager.cli status [tool]
    python -m tool_manager.cli install <tool> [--dry-run]
    python -m tool_manager.cli update <tool|--all> [--dry-run]
    python -m tool_manager.cli deps <tool|--all>
    python -m tool_manager.cli configure
"""

import argparse
import sys

from tool_manager.core.installer import ToolInstaller
from tool_manager.core.updater import ToolUpdater
from tool_manager.core.dependency_checker import DependencyChecker
from tool_manager.core.config_manager import ConfigManager
from tool_manager.core.logger import get_logger

logger = get_logger(__name__)


def print_status_table(statuses):
    header = f"{'TOOL':<12}{'INSTALLED':<12}{'VERSION':<12}{'REQUIRED':<12}{'STATUS':<15}"
    print(header)
    print("-" * len(header))
    for s in statuses:
        installed = "yes" if s.installed else "no"
        version = s.installed_version or "-"
        required = s.required_version or "-"
        if not s.installed:
            state = "NOT INSTALLED"
        elif s.up_to_date:
            state = "UP TO DATE"
        else:
            state = "UPDATE AVAILABLE"
        print(f"{s.name:<12}{installed:<12}{version:<12}{required:<12}{state:<15}")


def cmd_list(args, installer):
    print("Available tools in registry:")
    for t in installer.list_tools():
        meta = installer.get_tool_meta(t)
        supported = "supported" if installer.is_platform_supported(t) else "NOT supported on this OS"
        print(f"  - {t}: {meta['description']} [{supported}]")


def cmd_status(args, installer):
    if args.tool:
        statuses = [installer.check_status(args.tool)]
    else:
        statuses = installer.check_all()
    print_status_table(statuses)


def cmd_install(args, installer):
    checker = DependencyChecker(installer)
    dep_result = checker.check_dependencies(args.tool)
    if dep_result["missing"]:
        print(f"Warning: missing dependencies for {args.tool}: {', '.join(dep_result['missing'])}")
        if not args.yes:
            confirm = input("Continue with installation anyway? [y/N]: ").strip().lower()
            if confirm != "y":
                print("Installation cancelled.")
                return

    success = installer.install(args.tool, dry_run=args.dry_run)
    print("Installation succeeded." if success else "Installation failed. See logs for details.")


def cmd_update(args, installer):
    updater = ToolUpdater(installer)
    if args.all:
        results = updater.update_all(dry_run=args.dry_run)
        for tool, ok in results.items():
            print(f"  {tool}: {'OK' if ok else 'FAILED'}")
    elif args.tool:
        ok = updater.update(args.tool, dry_run=args.dry_run)
        print("Update succeeded." if ok else "Update failed. See logs for details.")
    else:
        print("Specify a tool name or --all")


def cmd_deps(args, installer):
    checker = DependencyChecker(installer)
    if args.all:
        results = checker.check_all()
        for tool, res in results.items():
            status = "OK" if not res["missing"] else f"MISSING: {', '.join(res['missing'])}"
            print(f"  {tool}: {status}")
    elif args.tool:
        res = checker.check_dependencies(args.tool)
        if res["missing"]:
            print(f"Missing: {', '.join(res['missing'])}")
        else:
            print("All dependencies satisfied.")
    else:
        print("Specify a tool name or --all")


def cmd_configure(args, installer):
    config = ConfigManager()
    tool_names = installer.list_tools()
    paths = config.resolve_tool_paths(tool_names, installer=installer)
    for name, path in paths.items():
        print(f"  {name}: {path or 'not found on PATH'}")
    env_path = config.write_env_file(paths)
    print(f"\nEnvironment file written to: {env_path}")
    print("Source this file (or add it to your shell profile) so eSim can locate the tools.")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="esim-tool-manager",
        description="Automated Tool Manager for eSim -- install, update, and configure "
        "external EDA tools (ngspice, kicad, ghdl, ...).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all tools known to the manager")

    p_status = sub.add_parser("status", help="Show installed/required version for one or all tools")
    p_status.add_argument("tool", nargs="?", help="Tool name (omit for all tools)")

    p_install = sub.add_parser("install", help="Install a tool")
    p_install.add_argument("tool", help="Tool name, e.g. ngspice")
    p_install.add_argument("--dry-run", action="store_true", help="Show what would run, without executing")
    p_install.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")

    p_update = sub.add_parser("update", help="Update a tool (or all tools)")
    p_update.add_argument("tool", nargs="?", help="Tool name")
    p_update.add_argument("--all", action="store_true", help="Update every tool with a pending update")
    p_update.add_argument("--dry-run", action="store_true", help="Show what would run, without executing")

    p_deps = sub.add_parser("deps", help="Check dependencies for a tool (or all tools)")
    p_deps.add_argument("tool", nargs="?", help="Tool name")
    p_deps.add_argument("--all", action="store_true", help="Check every tool")

    sub.add_parser("configure", help="Resolve tool paths and write an env file for eSim")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    installer = ToolInstaller()

    dispatch = {
        "list": cmd_list,
        "status": cmd_status,
        "install": cmd_install,
        "update": cmd_update,
        "deps": cmd_deps,
        "configure": cmd_configure,
    }

    try:
        dispatch[args.command](args, installer)
    except KeyError as e:
        logger.error(str(e))
        print(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error running command '{args.command}'")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
