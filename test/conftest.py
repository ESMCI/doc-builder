"""
pytest fixtures etc. for use in testing
"""

import os

import pytest

@pytest.fixture(name="conf_py_path")
def fixture_conf_py_path():
    """Default absolute path to conf.py file"""
    return os.path.join(os.path.dirname(__file__), os.pardir, "conf.py")
