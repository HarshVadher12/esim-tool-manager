# eSim Automated Tool Manager

A prototype command-line tool manager for [eSim](https://esim.fossee.in/), built for
**FOSSEE eSim Semester-Long Internship — Screening Task 5**.

It automates installation, version checking, updating, configuration, and
dependency checking for the external tools eSim depends on
(Ngspice, KiCad, GHDL), driven entirely by a JSON registry so new tools can
be added without touching Python code.

## Requirements covered

| # | Requirement                     | Status | Notes |
|---|----------------------------------|--------|-------|
| 1 | Tool Installation Management     | ✅ Full | Installs via native package manager, OS-aware, version-aware |
| 2 | Update and Upgrade System        | ✅ Full | Checks + applies updates with one command |
| 3 | Configuration Handling            | ✅ Full | Resolves tool paths, writes a sourceable env file |
| 4 | Dependency Checker                | ✅ Full | Checks OS-level deps (dpkg/brew) per tool, reports what's missing |
| 5 | User Interface                    | ✅ Full | CLI with status table, install/update/deps/configure subcommands, persistent log file |
| 6 | Cross-platform / package manager integration | ✅ Partial | apt (Linux) implemented and tested; brew (macOS) and choco (Windows) recipes included, untested on those OSes |

This exceeds the minimum of 2 requirements — the core deliverable
(**install + version checking**) is fully working end-to-end and was
verified against a real package (see "Verified demo" below).

## Project structure

```
esim-tool-manager/
├── tool_manager/
│   ├── cli.py                   # entry point / CLI (Requirement 5)
│   ├── config/
│   │   ├── tools_registry.json  # tool metadata: install/update cmds, deps, version regex
│   │   └── user_config.json     # user preferences (install root, env file path)
│   ├── core/
│   │   ├── installer.py         # Requirement 1
│   │   ├── updater.py           # Requirement 2
│   │   ├── config_manager.py    # Requirement 3
│   │   ├── dependency_checker.py# Requirement 4
│   │   └── logger.py            # action log (Requirement 5)
│   └── utils/
│       └── system_utils.py      # OS detection, safe subprocess runner
├── tests/                       # pytest unit tests (13 tests, mocked subprocess)
├── docs/
│   └── DESIGN.md                # architecture / design document (Deliverable 1)
├── logs/
│   └── tool_manager.log         # generated at runtime
├── requirements.txt
└── README.md
```

## Requirements to run

- Python 3.10+ (uses `X | None` type hints)
- Linux with `apt`/`apt-get` for the tested install path (macOS/`brew` and
  Windows/`choco` recipes are included but not exercised in this
  submission — see Design Document, "Known Limitations")
- No third-party Python packages needed to *run* the manager. `pytest` is
  only needed to run the test suite.

## Setup

```bash
git clone <this-repo-url>
cd esim-tool-manager
pip install -r requirements.txt   # only needed for running tests
```

No build step, no compiled artifacts — the CLI runs directly from source.

## Usage

Run all commands as a module from the repository root:

```bash
# 1. See what tools the manager knows about
python3 -m tool_manager.cli list

# 2. Check installed vs. required versions for every tool
python3 -m tool_manager.cli status

# 3. Check just one tool
python3 -m tool_manager.cli status ngspice

# 4. Check OS-level dependencies before installing
python3 -m tool_manager.cli deps ngspice
python3 -m tool_manager.cli deps --all

# 5. Install a tool (dry-run first to see exactly what will execute)
python3 -m tool_manager.cli install ngspice --dry-run
python3 -m tool_manager.cli install ngspice          # will prompt for sudo password if needed

# 6. Update a tool, or everything that's outdated
python3 -m tool_manager.cli update ngspice
python3 -m tool_manager.cli update --all

# 7. Resolve installed tool paths and generate an env file for eSim
python3 -m tool_manager.cli configure
source ~/.esim/env.sh
```

Every action (install, update, dependency check, error) is written to
`logs/tool_manager.log` with a timestamp, satisfying the "log of actions
taken" requirement.

## Verified demo (what was actually tested, not just written)

This submission was tested against a **real** Ubuntu/apt environment, not
just mocked:

```
$ python3 -m tool_manager.cli status
TOOL        INSTALLED   VERSION     REQUIRED    STATUS
---------------------------------------------------------------
ngspice     no          -           38.2        NOT INSTALLED
kicad       no          -           7.0         NOT INSTALLED
ngveri      no          -           1.0         NOT INSTALLED

$ python3 -m tool_manager.cli install ngveri -y
Installation succeeded.

$ python3 -m tool_manager.cli status
TOOL        INSTALLED   VERSION     REQUIRED    STATUS
---------------------------------------------------------------
ngspice     no          -           38.2        NOT INSTALLED
kicad       no          -           7.0         NOT INSTALLED
ngveri      yes         4.1.0       1.0         UP TO DATE

$ python3 -m tool_manager.cli install ngveri -y     # idempotency check
Installation succeeded.   # <- skipped re-install, already present

$ python3 -m tool_manager.cli configure
  ngveri: /usr/bin/ghdl
Environment file written to: /root/.esim/env.sh
```

`ngveri` maps to `ghdl` (GHDL, the VHDL simulator eSim integrates) — real
`apt-get install`, real version parsing from `ghdl --version` output, real
comparison against the required version, and a real generated env file.

## Running the tests

```bash
pip install pytest --break-system-packages   # or use a venv
python3 -m pytest tests/ -v
```

All installer/updater/dependency-checker logic is unit-tested with
`unittest.mock` so tests don't require network access or root privileges.

## Adding a new tool

No code changes needed — add an entry to
`tool_manager/config/tools_registry.json` following the existing shape
(`check_command`, `version_regex`, per-OS install/update commands,
`dependencies`, `binary`). This was a deliberate design choice — see
`docs/DESIGN.md` for rationale.

## Known limitations (being upfront about prototype scope)

- Windows/`choco` and macOS/`brew` install recipes are present in the
  registry but were not tested on those platforms in this submission
  (no such environment was available for testing).
- Dependency checking currently supports Linux (`dpkg`) and macOS
  (`brew list`) — Windows dependency checking is stubbed to always pass.
- No GUI is provided; requirement 5 asks for CLI *or* GUI, and CLI was
  chosen for speed of iteration and because it's easiest to demo/test
  reproducibly.
- Version comparison is a simple tuple compare, not a full semver parser.
  This is sufficient for the three tools in scope but would need
  hardening (e.g. `packaging.version`) for tools with pre-release tags.
