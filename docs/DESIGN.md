# Design Document — eSim Automated Tool Manager

## 1. Problem framing

eSim depends on several external, independently-versioned tools (Ngspice,
KiCad, GHDL, ...) that users currently install and configure by hand. The
failure modes this causes are predictable: wrong versions, missing build
dependencies, tools not on `PATH`, and no record of what was done when
something breaks. The Tool Manager's job is to make "get eSim's tools
into a working state" a single, repeatable, logged operation instead of a
manual checklist.

## 2. Design goals, in priority order

1. **Correctness over cleverness.** Every install/update path should be
   verifiable by actually running it, not just by reading the code.
2. **Adding a tool should not require writing code.** Tool-specific
   knowledge (which package manager, which command, what dependencies)
   lives in data (JSON), not in `if tool_name == "ngspice"` branches.
3. **Fail loud, fail specific.** If a dependency is missing or a package
   manager isn't available, tell the user exactly what's missing and
   what to do about it — never a silent no-op or a bare traceback.
4. **Idempotency.** Running `install` on an already-installed tool, or
   `update` on an already-current tool, should be a safe no-op, not an
   error or a redundant reinstall.
5. **Testability without root or network.** Core logic (version parsing,
   comparison, dependency resolution) is unit-tested with mocked
   subprocess calls, so correctness doesn't depend on having a live Linux
   box with sudo access in CI.

## 3. Architecture overview

```
                     ┌─────────────────────┐
                     │        cli.py        │   (Requirement 5: UI)
                     │  argparse subcommands │
                     └──────────┬───────────┘
                                │
        ┌───────────┬──────────┼───────────┬──────────────┐
        ▼           ▼          ▼           ▼              ▼
  ┌──────────┐┌───────────┐┌──────────┐┌────────────┐┌──────────┐
  │ installer││  updater  ││dependency││   config   ││  logger  │
  │   .py    ││    .py    ││checker.py││ manager.py ││   .py    │
  │  (Req 1) ││  (Req 2)  ││ (Req 4)  ││  (Req 3)   ││ (Req 5)  │
  └────┬─────┘└─────┬─────┘└────┬─────┘└─────┬──────┘└────┬─────┘
       │            │           │            │            │
       └────────────┴─────┬─────┴────────────┴────────────┘
                           ▼
                 ┌───────────────────┐
                 │  system_utils.py   │  OS detection, subprocess wrapper
                 └─────────┬──────────┘
                           ▼
                 ┌───────────────────┐
                 │ tools_registry.json│  Single source of truth per tool
                 └────────────────────┘
```

**Data flow for a typical `install` command:**

`cli.py` parses args → asks `DependencyChecker` to verify OS-level deps →
warns and confirms with the user if anything's missing → calls
`ToolInstaller.install()`, which reads the tool's OS-specific recipe from
the registry, checks whether it's already installed (via
`get_installed_version`), and if not, runs the install command through
`system_utils.run_command()` → every step is logged via `logger.py`.

## 4. Module breakdown and responsibilities

### 4.1 `tools_registry.json` — the single source of truth
Each tool entry declares:
- `check_command` / `version_regex`: how to detect what's installed
- `required_version`: what eSim needs
- per-OS (`linux` / `darwin` / `windows`) blocks with `manager`,
  `install_cmd`, `update_cmd`
- `dependencies`: OS packages the tool needs to build/run
- `binary`: actual executable name (may differ from the registry key,
  e.g. `ngveri` → `ghdl`)

This is the core design decision of the whole project: **tool-specific
knowledge is data, not code**. Supporting a fourth or fifth tool is a
JSON diff, not a pull request touching five Python files. The trade-off
is that anything the registry format can't express (e.g. a tool needing
a multi-step install with intermediate user input) would need a schema
extension — acceptable for a prototype covering package-manager-installable
tools, which is the common case for Ngspice/KiCad/GHDL.

### 4.2 `installer.py` (Requirement 1)
Owns:
- **Version detection** — runs each tool's check command, regex-extracts
  the version, independent of install state (works whether or not the
  manager itself did the installing).
- **Version comparison** — a simple tuple-based comparison
  (`(38, 2) >= (38, 2)`), sufficient for the numeric versions these tools
  use.
- **OS compatibility check** — `is_platform_supported()` refuses to
  attempt an install if the registry has no recipe for the current OS,
  rather than guessing.
- **Privilege handling** — `_with_privilege_escalation()` prepends `sudo`
  only when not already root and `sudo` exists on `PATH`. This was found
  and fixed during testing: naively hardcoding `sudo` in every install
  command breaks on root-only environments (containers, some CI images)
  where `sudo` isn't installed at all.

### 4.3 `updater.py` (Requirement 2)
Thin layer over `installer.py`: reuses its version detection so "is this
outdated" and "is this installed" can never disagree with each other.
Provides both single-tool and `update_all()` batch operation.

### 4.4 `dependency_checker.py` (Requirement 4)
Checks OS-level dependencies (e.g. `bison`, `flex`, `libx11-dev` for
building Ngspice) via `dpkg -s` on Linux or `brew list` on macOS. Reports
`{"satisfied": [...], "missing": [...]}` rather than a boolean, so the CLI
can show the user exactly what to fix.

### 4.5 `config_manager.py` (Requirement 3)
Two jobs:
- Persist user preferences (`user_config.json` — install root, preferred
  package manager, env file location).
- **Path resolution + env file generation**: finds each installed tool's
  binary via `shutil.which()`, and writes a `source`-able `env.sh` (or
  `.bat` on Windows) so eSim can pick up the right `PATH` without the
  user hand-editing `.bashrc`.

### 4.6 `logger.py` (Requirement 5, supporting)
Single logger configured once, writing to both console (INFO+) and
`logs/tool_manager.log` (DEBUG+), so there's always a persistent record
of what the manager did, even for actions the user didn't watch happen
live.

### 4.7 `cli.py` (Requirement 5)
`argparse`-based subcommands (`list`, `status`, `install`, `update`,
`deps`, `configure`). Chosen over a GUI because:
- it's scriptable (CI, other tools can shell out to it)
- it's testable without a display server
- eSim's own installer flow is already terminal-driven, so this fits the
  existing user mental model

A GUI (e.g. Tkinter or a small Flask/PyQt front-end) is a natural
Phase 2 — the CLI's subcommands map 1:1 to what would become button
actions, so it wouldn't require restructuring the core modules.

### 4.8 `system_utils.py`
Deliberately tiny and dependency-free: `get_os()` (normalizes
`platform.system()` into `linux`/`darwin`/`windows`), `which()`,
`package_manager_available()`, and `run_command()` (subprocess wrapper
that always returns a `CommandResult` rather than raising, so callers
decide what "command failed" means in their context — e.g. exit code 127
from a version-check command means "not installed", not "error").

## 5. Design decisions and trade-offs

| Decision | Why | Trade-off accepted |
|---|---|---|
| JSON registry over hardcoded logic | New tools = data change, not code change | Registry format has to anticipate the shapes tools need (handled by per-OS blocks + optional `binary` override) |
| Native package managers (apt/brew/choco) instead of manual downloads | Correctness and security (signed repos, dependency resolution) come for free | Less control over exact install location; version pinning is limited to what the OS repo offers |
| CLI instead of GUI | Faster to build, test, and verify for a screening task; scriptable | No visual polish; acceptable since the task explicitly allows CLI |
| `subprocess.run` with list args, never `shell=True` | Avoids shell-injection risk entirely | Slightly more verbose command construction |
| Never raise on subprocess failure inside `run_command` | Callers can distinguish "not installed" from "real error" cleanly | Callers must remember to check `.ok` |

## 6. Known limitations / what a v2 would add

- **Windows/macOS are implemented but not tested** in this submission —
  no such machine was available. The design isolates OS-specific
  behavior into registry blocks + `get_os()`, so this is a testing gap,
  not an architectural one.
- **Version comparison is naive.** Works for the numeric-only versions of
  Ngspice/KiCad/GHDL; would need `packaging.version` or similar for tools
  using pre-release/build-metadata versioning.
- **No rollback.** If an update breaks a tool, there's no automatic
  revert; v2 could snapshot the previous package version before
  upgrading.
- **No GUI**, as noted above — CLI was chosen deliberately for this
  submission.
- **Dependency checking on Windows is stubbed** (assumes satisfied) since
  Windows dependency management is package-specific (vcredist, etc.) and
  out of scope for a 3-tool prototype.

## 7. Why this satisfies more than the required 2/6 requirements

The task requires meeting any 2. This design fully implements 1
(installation), 2 (updates), 3 (configuration), 4 (dependencies), and 5
(CLI + logging) — all backed by a real, verified install of GHDL via
`apt` (not just mocked), specifically to demonstrate that the "basic
prototype" deliverable is genuinely functional rather than illustrative
pseudocode.
