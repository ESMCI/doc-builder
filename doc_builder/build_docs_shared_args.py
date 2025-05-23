"""
build_docs and build_docs_to_publish share some args. This module adds them to a parser or parser
group.
"""

# pylint: disable=import-error,no-name-in-module
from .build_commands import DEFAULT_DOCKER_IMAGE


def bd_parser(parser, site_root_required=False):
    """
    Add arguments that build_docs has in its overall parser.

    # site_root_required: Should be True from build_docs_to_publish, False from build_docs
    """
    parser.add_argument(
        "--site-root",
        required=site_root_required,
        help="URL or absolute file path that should contain the top-level index.html",
    )
    parser.add_argument(
        "-d",
        "--build-with-docker",
        action="store_true",
        help="Use a Docker container to build the documentation,\n"
        "rather than relying on locally-installed versions of Sphinx, etc.\n"
        "This assumes that Docker is installed and running on your system.\n"
        "\n"
        "NOTE: This mounts your home directory in the Docker image.\n"
        "Therefore, both the current directory (containing the Makefile for\n"
        "building the documentation) and the documentation build directory\n"
        "must reside somewhere within your home directory."
        "\n"
        f"Default image: {DEFAULT_DOCKER_IMAGE}\n"
        "This can be changed with -i/--docker-image.",
    )
    return parser


def bd_dir_group(parser_or_group, repo_root_default=None):
    """
    Add arguments that build_docs has in its dir_group
    """
    parser_or_group.add_argument(
        "-r",
        "--repo-root",
        default=repo_root_default,
        help="Root directory of the repository holding documentation builds.\n"
        "(If there are other path elements between the true repo root and\n"
        "the 'versions' directory, those should be included in this path.)",
    )
    return parser_or_group


def main(parser):
    """
    Add all arguments to parser, even if build_docs has them in dir_group
    """

    # Settings for build_docs_to_publish, because main() should only ever be called from there
    site_root_required = True
    repo_root_default = "_build"

    parser = bd_parser(parser, site_root_required)
    parser = bd_dir_group(parser, repo_root_default)

    return parser
