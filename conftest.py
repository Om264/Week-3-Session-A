"""
pytest configuration and shared fixtures.

pytest will auto-discover this file. Add project-level fixtures or
configuration options here (e.g. custom markers, plugins).
"""
import logging
import sys
from pathlib import Path

import pytest

# Ensure the project root is on PYTHONPATH for editable installs
sys.path.insert(0, str(Path(__file__).parent.parent))

# Keep test output clean – set root logger to WARNING unless -v is used
logging.getLogger("scs_cn").setLevel(logging.WARNING)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with -m 'not slow')")
    config.addinivalue_line("markers", "integration: full pipeline integration tests")
