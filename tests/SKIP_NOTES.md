# Opt-in and skipped tests

The default `pytest` run stays fast and offline. The cases below are gated or
skipped with an explicit reason; none is counted as a silent pass.

## Environment-gated (default skip, reason printed at runtime)

| Case | File | Gate / reason | How to run |
|---|---|---|---|
| ~10 MB and ~50 MB media decks (time + tracemalloc peak) | `performance/test_large_files.py` | Generates tens of MB of JPEGs; skipped to keep the default suite quick. | `$env:LAYOUTPROOF_PERF="1"; .venv\Scripts\python.exe -m pytest tests/performance/test_large_files.py -s` |
| Throwaway venv install → upgrade → uninstall cycle | `install/test_install_lifecycle.py::test_isolated_venv_install_upgrade_uninstall` | Fresh venv needs the `setuptools.build_meta` backend and dependency resolution; unavailable offline on this machine, so it skips instead of faking success. | `$env:LAYOUTPROOF_INSTALL_TEST="1"; .venv\Scripts\python.exe -m pytest tests/install/test_install_lifecycle.py::test_isolated_venv_install_upgrade_uninstall` |
| Offline `pip wheel` build | `install/test_install_lifecycle.py::test_offline_wheel_build_succeeds` | Current interpreter has no importable `setuptools.build_meta`; backend-unavailable causes a documented skip. | Install the build backend, then rerun. |
| LibreOffice rendering chain | existing `integration/test_render_chain.py` | Renderer optional; set `LAYOUTPROOF_SOFFICE` to the isolated `soffice.com` to enable. | Per existing test convention. |

## Always-on coverage for the install contract

Without the gates, the install suite still verifies: the declared
`layoutproof = layoutproof.cli:main` console entry point resolves to a callable,
`python -m layoutproof --version` works, and the project virtualenv console
script executes.

## Cross-platform note

Performance numbers were captured on Windows only (see
`performance/PERF_RESULTS.md`). Absolute time/memory caps are not asserted as
Linux/macOS guarantees.
