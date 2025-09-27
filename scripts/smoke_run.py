#!/usr/bin/env python3
"""Smoke runner for MediaStack Doctor - minimal test without external dependencies."""

import sys
import os

# Add the project to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mediastack_doctor import __version__
from mediastack_doctor.cli import main

print("mediastack-doctor version:", __version__)

# Run a minimal no-network, no-docker probe path
# This should only run host checks which don't require external dependencies
exit_code = main(["--output-dir", "./outputs", "run", "--sections", "host"])

print(f"Smoke run completed with exit code: {exit_code}")
raise SystemExit(exit_code)
