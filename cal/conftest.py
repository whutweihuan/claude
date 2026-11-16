import os
import sys

# Ensure the project root (this directory) is importable so tests can
# `import src.calculator` / `import src.ui` regardless of pytest's import
# mode or the directory pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def tk_root():
    """One shared Tk root for the whole test session.

    Creating a separate `tk.Tk()` per test churns Tk/Tcl interpreters; on
    Windows that intermittently fails to load `tk.tcl` ("can't find a usable
    tk.tcl") once several have been created in one process. Sharing a single
    root keeps the suite deterministic while still exercising the real widget
    tree.
    """
    root = tk.Tk()
    yield root
    root.destroy()
