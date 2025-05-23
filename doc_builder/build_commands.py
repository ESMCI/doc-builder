"""
Functions with the main logic needed to build the command to build the docs
"""

import os
import pathlib
import shutil
from doc_builder import sys_utils  # pylint: disable=import-error

DEFAULT_IMAGE = "ghcr.io/escomp/ctsm/ctsm-docs:v1.0.1"

# The path in the container's filesystem where the user's home directory is mounted
_CONTAINER_HOME = "/home/user/mounted_home"

# CLI tools we can try to use to run our container, in decreasing order of preference
COMPATIBLE_CLI_TOOLS = ["podman", "docker"]


def get_build_dir(build_dir=None, repo_root=None, version=None):
    """Return a string giving the path to the build directory.

    If build_dir is specified, simply use that.

    Otherwise, repo_root must be given. If version is also given, then
    the build directory will be:
        os.path.join(repo_root, "versions", version).
    If version is not given, then determine version by getting the
    current git branch; then use the above path specification.

    Error-checking on directory existence:
    - If build_dir is given, then no error checking is done
    - Otherwise, we ensure that repo_root/versions exists
      - If version is not given, then we also ensure that
        repo_root/versions/version exists, for the determined version.
    """

    if build_dir is not None:
        if repo_root is not None:
            raise RuntimeError("Cannot specify both build-dir and repo-root")
        if version is not None:
            raise RuntimeError("Cannot specify both build-dir and version")
        return build_dir, "None"

    if repo_root is None:
        raise RuntimeError("Must specify either build-dir or repo-root")

    version_explicit = version is not None
    if not version_explicit:
        branch_found, version = sys_utils.git_current_branch()
        if not branch_found:
            raise RuntimeError(
                "Problem determining version based on git branch; "
                "set --version on the command line."
            )

    build_dir_no_version = os.path.join(repo_root, "versions")
    if not os.path.isdir(build_dir_no_version):
        os.makedirs(build_dir_no_version)
    build_dir = os.path.join(build_dir_no_version, version)
    if not version_explicit:
        if not os.path.isdir(build_dir):
            message = f"""
Directory {build_dir} doesn't exist yet.
If this is where you really want to build the documentation, rerun adding the
command-line argument '--doc-version {version}'"""
            raise RuntimeError(message)

    return build_dir, version


def get_container_cli_tool():
    """
    Loop through our list of compatible CLI tools for running our container, checking whether user
    has them installed. Error if none found.
    """
    for tool in COMPATIBLE_CLI_TOOLS:
        if shutil.which(tool):
            return tool
    raise RuntimeError(f"No compatible container software found: {', '.join(COMPATIBLE_CLI_TOOLS)}")


def get_build_command(
    *,
    build_dir,
    run_from_dir,
    build_target,
    version,
    num_make_jobs,
    container_name=None,
    warnings_as_warnings=False,
    container_image=DEFAULT_IMAGE,
    conf_py_path=None,
    container_cli_tool=None,
):
    # pylint: disable=too-many-arguments,too-many-locals
    """Return a string giving the build command.

    Args:
    - build_dir: string giving path to directory in which we should build
        If this is a relative path, it is assumed to be relative to run_from_dir
    - run_from_dir: string giving absolute path from which the build_docs command was run
        This is needed when using container
    - build_target: string: target for the make command (e.g., "html")
    - num_make_jobs: int: number of parallel jobs
    - container_name: string or None: if not None, uses a container to do the build,
        with the given name. This is just a temporary name that ensures we never have two active
        containers with the same name.
    - container_image: If using a container, this is the image that will be used (and downloaded,
        if necessary). Typically named something like repository:version. See DEFAULT_IMAGE for an
        example.
    """
    if container_name is None:
        return _get_make_command(
            build_dir=build_dir,
            build_target=build_target,
            num_make_jobs=num_make_jobs,
            warnings_as_warnings=warnings_as_warnings,
            conf_py_path=conf_py_path,
        )

    # But if we're using a container, we have more work to do to create the command....

    # Mount the user's home directory in the container; this assumes that both
    # run_from_dir and build_dir reside somewhere under the user's home directory (we
    # check this assumption below).
    container_mountpoint = os.path.expanduser("~")

    errmsg_if_not_under_mountpoint = "build_docs must be run from somewhere in your home directory"
    container_workdir = _container_path_from_local_path(
        local_path=run_from_dir,
        container_mountpoint=container_mountpoint,
        errmsg_if_not_under_mountpoint=errmsg_if_not_under_mountpoint,
    )

    if os.path.isabs(build_dir):
        build_dir_abs = build_dir
    else:
        build_dir_abs = os.path.normpath(os.path.join(run_from_dir, build_dir))
    container_build_dir = _container_path_from_local_path(
        local_path=build_dir_abs,
        container_mountpoint=container_mountpoint,
        errmsg_if_not_under_mountpoint="build directory must reside under your home directory",
    )

    # Get current user's UID and GID
    uid = os.getuid()
    gid = os.getgid()

    make_command = _get_make_command(
        build_dir=container_build_dir,
        build_target=build_target,
        num_make_jobs=num_make_jobs,
        warnings_as_warnings=warnings_as_warnings,
        conf_py_path=conf_py_path,
    )

    # Get name of command to start container, if not provided
    if container_cli_tool is None:
        container_cli_tool = get_container_cli_tool()

    container_command = [
        container_cli_tool,
        "run",
        "--name",
        container_name,
        "--user",
        f"{uid}:{gid}",
        "--mount",
        f"type=bind,source={container_mountpoint},target={_CONTAINER_HOME}",
        "--workdir",
        container_workdir,
        "-t",  # "-t" is needed for colorful output
        "--rm",
        "-e",
        f"current_version={version}",
        container_image,
    ] + make_command
    return container_command


def _get_make_command(build_dir, build_target, num_make_jobs, warnings_as_warnings, conf_py_path):
    """Return the make command to run (as a list)

    Args:
    - build_dir: string giving path to directory in which we should build
    - build_target: string: target for the make command (e.g., "html")
    - num_make_jobs: int: number of parallel jobs
    """
    builddir_arg = f"BUILDDIR={build_dir}"
    sphinxopts = "SPHINXOPTS="
    if not warnings_as_warnings:
        sphinxopts += "-W --keep-going "
    if conf_py_path:
        if not os.path.exists(conf_py_path):
            raise FileNotFoundError(f"--conf-py-path not found: '{conf_py_path}'")
        if not os.path.isdir(conf_py_path):
            conf_py_path = os.path.dirname(conf_py_path)
        sphinxopts += f"-c '{conf_py_path}' "
    sphinxopts = sphinxopts.rstrip()
    return ["make", sphinxopts, builddir_arg, "-j", str(num_make_jobs), build_target]


def _container_path_from_local_path(
    local_path, container_mountpoint, errmsg_if_not_under_mountpoint
):
    """Given a path on the local file system, return the equivalent path in container space

    Args:
    - local_path: string: absolute path on local file system; this must reside under
        container_mountpoint
    - container_mountpoint: string: path on local file system that is mounted to _CONTAINER_HOME
    - errmsg_if_not_under_mountpoint: string: message to print if local_path does not
        reside under container_mountpoint
    """
    if not os.path.isabs(local_path):
        raise RuntimeError(f"Expect absolute path; got {local_path}")

    local_pathobj = pathlib.Path(local_path)
    try:
        relpath = local_pathobj.relative_to(container_mountpoint)
    except ValueError as err:
        raise RuntimeError(errmsg_if_not_under_mountpoint) from err

    # I think we need to do this conversion to a PosixPath for the sake of Windows
    # machines, where relpath is a Windows-style path, but we want Posix paths for
    # container. (But it may be that this is unnecessary.)
    relpath_posix = pathlib.PurePosixPath(relpath)

    # In the following, we deliberately hard-code "/" rather than using something like
    # os.path.join, because we need a path that works in the container's file system, not the
    # native file system (in case the native file system is Windows).
    return _CONTAINER_HOME + "/" + str(relpath_posix)
