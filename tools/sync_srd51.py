#!/usr/bin/env python3
"""ASCII entry point for the SRD 5.1 content database generator."""

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("同步_srd51.py")), run_name="__main__")
