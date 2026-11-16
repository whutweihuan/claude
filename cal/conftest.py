import os
import sys

# Ensure the project root (this directory) is importable so tests can
# `import src.calculator` / `import src.ui` regardless of pytest's import
# mode or the directory pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
