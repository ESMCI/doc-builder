"""
Check whether the container image that build_docs pulls by default (DEFAULT_IMAGE) has been
published to its registry, and tell a GitHub Actions workflow whether to build the docs.

If the image exists, the docs should be built. If it doesn't, what happens depends on whether this
is doc-builder itself, i.e., the top level of its own git checkout and not a submodule:
- doc-builder itself (including forks): The image for a version bump only gets published when the
  PR that bumps it merges, so skip the docs build with a warning rather than failing.
- Downstream repo (doc-builder is a submodule of it or copied into it): Fail, because doc-builder
  is at a version whose container image isn't available.
Any other outcome of the registry check is an error, regardless of repo type.
"""

import argparse
import enum
import os
import subprocess
import sys

# pylint: disable=import-error
from doc_builder.build_commands import DEFAULT_IMAGE

_DOC_BUILDER_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
)

# What `docker manifest inspect` prints when the registry doesn't have the tag
_MANIFEST_UNKNOWN = "manifest unknown"

EXIT_OK = 0
EXIT_MISSING_DOWNSTREAM = 1
EXIT_CHECK_ERROR = 3  # Avoid 2, which argparse uses for usage errors


class ManifestStatus(enum.Enum):
    """Result of classifying `docker manifest inspect` output"""

    EXISTS = "exists"
    MISSING = "missing"
    UNKNOWN = "unknown"


def classify_manifest_output(output):
    """Classify the combined stdout/stderr of `docker manifest inspect`.

    Matches the classification in .github/workflows/docker-image-get-version.yml.
    """
    if "schemaVersion" in output:
        return ManifestStatus.EXISTS
    if output == _MANIFEST_UNKNOWN:
        return ManifestStatus.MISSING
    return ManifestStatus.UNKNOWN


def inspect_manifest(image):
    """Run `docker manifest inspect` on image.

    Returns a tuple (returncode, output), where output is the combined stdout and stderr with
    trailing newlines removed (like bash's command substitution does).
    """
    # Decode leniently: undecodable output should be reported as unrecognized, not raise
    result = subprocess.run(
        ["docker", "manifest", "inspect", image],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode, result.stdout.rstrip("\n")


def _git_rev_parse(repo_dir, option):
    """Return the output of `git -C repo_dir rev-parse option`, stripped of whitespace"""
    result = subprocess.run(
        ["git", "-C", repo_dir, "rev-parse", option],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def is_downstream(doc_builder_root):
    """Return True if the doc-builder at doc_builder_root is part of some other repo.

    Raises subprocess.CalledProcessError if git fails (e.g., it isn't in a git repo).
    """
    toplevel = _git_rev_parse(doc_builder_root, "--show-toplevel")
    if os.path.realpath(toplevel) != os.path.realpath(doc_builder_root):
        return True
    return bool(_git_rev_parse(doc_builder_root, "--show-superproject-working-tree"))


def _not_found_header(image):
    """First lines of the messages for when the image is missing"""
    return f"ERROR: Container image not found on registry:\n    {image}\n\n"


def missing_downstream_message(image):
    """Error message for when the image is missing in a downstream repo.

    This may be posted as the body of a PR comment, inside a code block, so lines are wrapped by
    hand.
    """
    return _not_found_header(image) + (
        "The version of doc-builder in this repo uses a container version that\n"
        "hasn't been published yet. Likely causes:\n"
        "\n"
        "- This repo's doc-builder is from an unmerged doc-builder pull request.\n"
        "  The image is only published once that PR merges. Update doc-builder\n"
        "  (the submodule or the copied-in files) to a merged version instead.\n"
        "- This repo's doc-builder is from a merged doc-builder version whose\n"
        "  image wasn't published when this check ran, either because publishing\n"
        "  hadn't finished yet or because it failed. To see which, check the\n"
        '  "Build and publish doc-build-container image" workflow runs in\n'
        "  doc-builder's GitHub Actions. If it hadn't finished, rerunning this\n"
        "  check later should work. If it failed, rerunning won't help until the\n"
        "  publishing is fixed on the doc-builder side.\n"
    )


def unknown_layout_message(image, detail):
    """Error message for when the image is missing but we couldn't tell whether we're downstream"""
    return _not_found_header(image) + (
        "Could not determine whether this is doc-builder itself or a downstream\n"
        "repo containing doc-builder (as a submodule or a copied-in directory),\n"
        "so could not decide whether to skip the docs build or fail.\n"
        "\n"
        f"Error from git:\n{detail}\n"
    )


def check_error_message(image, detail):
    """Error message for when we couldn't determine whether the image exists"""
    return f"ERROR: Could not check whether container image {image} exists:\n{detail}\n"


def _write_github_output(build):
    """Append build=true/false to $GITHUB_OUTPUT, if set"""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        return
    with open(github_output, "a", encoding="utf-8") as file:
        file.write(f"build={'true' if build else 'false'}\n")


def _report_error(msg, log_file):
    """Print msg to stderr and, if log_file is given, append it there too"""
    print(msg, file=sys.stderr, end="")
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as file:
            file.write(msg)


def commandline_options(cmdline_args=None):
    """Process the command-line arguments"""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--log-file",
        help="Also write any error message to this file (appending). Its directory is created if "
        "needed.",
    )
    return parser.parse_args(cmdline_args)


def main(cmdline_args=None, image=DEFAULT_IMAGE):
    """Check whether image is published and report what the workflow should do.

    Returns the exit code.
    """
    options = commandline_options(cmdline_args)

    try:
        returncode, output = inspect_manifest(image)
    except OSError as exception:
        _report_error(
            check_error_message(image, f"Could not run docker: {exception}"), options.log_file
        )
        return EXIT_CHECK_ERROR
    status = classify_manifest_output(output)

    if status == ManifestStatus.EXISTS:
        print(f"Container image {image} is published; docs should be built.")
        print("build=true")
        _write_github_output(build=True)
        return EXIT_OK

    if status == ManifestStatus.UNKNOWN:
        detail = f"`docker manifest inspect` exited with code {returncode} and output:\n{output}"
        _report_error(check_error_message(image, detail), options.log_file)
        return EXIT_CHECK_ERROR

    # The image is missing
    try:
        downstream = is_downstream(_DOC_BUILDER_ROOT)
    except (OSError, subprocess.CalledProcessError) as exception:
        detail = str(exception)
        stderr = getattr(exception, "stderr", None)
        if stderr:
            detail += "\n" + stderr.rstrip("\n")
        _report_error(unknown_layout_message(image, detail), options.log_file)
        return EXIT_CHECK_ERROR

    if downstream:
        _report_error(missing_downstream_message(image), options.log_file)
        return EXIT_MISSING_DOWNSTREAM

    print(
        f"::warning::Container image {image} has not been published yet. "
        "Skipping the docs build until that image is published."
    )
    print("build=false")
    _write_github_output(build=False)
    return EXIT_OK
