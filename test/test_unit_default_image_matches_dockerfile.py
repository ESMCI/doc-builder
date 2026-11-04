#!/usr/bin/env python3

"""Unit test checking that DEFAULT_IMAGE's tag matches the doc-build-container Dockerfile version"""

import os
import subprocess

# pylint: disable=import-error
from doc_builder.build_commands import DEFAULT_IMAGE

GET_VERSION_SCRIPT = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        os.pardir,
        "doc-build-container",
        "get_version.sh",
    )
)


def test_default_image_matches_dockerfile_version():
    """DEFAULT_IMAGE's tag should match the version label in doc-build-container/Dockerfile"""
    result = subprocess.run([GET_VERSION_SCRIPT], capture_output=True, text=True, check=False)
    assert (
        result.returncode == 0
    ), f"{GET_VERSION_SCRIPT} exited with code {result.returncode}:\n{result.stderr}"
    version = result.stdout.strip()

    assert DEFAULT_IMAGE.endswith(":" + version), (
        f"DEFAULT_IMAGE ({DEFAULT_IMAGE}) does not match the doc-build-container Dockerfile "
        f"version ({version}). Update DEFAULT_IMAGE in doc_builder/build_commands.py to use "
        f"tag {version}."
    )
