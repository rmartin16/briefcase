import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import List

from briefcase.commands.create import _is_local_requirement
from briefcase.commands.open import OpenCommand
from briefcase.config import AppConfig
from briefcase.exceptions import BriefcaseCommandError, ParseError

DEFAULT_OUTPUT_FORMAT = "system"


class LinuxMixin:
    platform = "linux"

    def support_package_url(self, support_revision):
        """The URL of the support package to use for apps of this type.

        Linux builds that use a support package (AppImage, Flatpak) use indygreg's
        Standalone Python to provide system packages. See
        `https://github.com/indygreg/python-build-standalone` for details.

        System packages don't use a support package; this is defined by
        the template, so this method won't be invoked
        """
        python_download_arch = self.tools.host_arch
        # use a 32bit Python if using 32bit Python on 64bit hardware
        if self.tools.is_32bit_python and self.tools.host_arch == "aarch64":
            python_download_arch = "armv7"
        elif self.tools.is_32bit_python and self.tools.host_arch == "x86_64":
            python_download_arch = "i686"

        version, datestamp = support_revision.split("+")
        return (
            "https://github.com/indygreg/python-build-standalone/releases/download/"
            f"{datestamp}/cpython-{support_revision}-{python_download_arch}-unknown-linux-gnu-install_only.tar.gz"
        )


class LocalRequirementsMixin:  # pragma: no-cover-if-is-windows
    # A mixin that captures the process of compiling requirements that are specified
    # as local file references into sdists, and then installing those requirements
    # from the sdist.

    def local_requirements_path(self, app):
        return self.bundle_path(app) / "_requirements"

    def _install_app_requirements(
        self,
        app: AppConfig,
        requires: List[str],
        app_packages_path: Path,
    ):
        """Install requirements for the app with pip.

        This method pre-compiles any requirement defined using a local path reference
        into an sdist tarball. This will be used when installing under Docker, as local
        file references can't be accessed in the Docker container.

        :param app: The app configuration
        :param requires: The list of requirements to install
        :param app_packages_path: The full path of the app_packages folder into which
            requirements should be installed.
        """
        # If we're re-building requirements, purge any pre-existing local
        # requirements.
        local_requirements_path = self.local_requirements_path(app)
        if local_requirements_path.exists():
            self.tools.shutil.rmtree(local_requirements_path)
        self.tools.os.mkdir(local_requirements_path)

        # Iterate over every requirement, looking for local references
        for requirement in requires:
            if _is_local_requirement(requirement):
                if Path(requirement).is_dir():
                    # Requirement is a filesystem reference
                    # Build an sdist for the local requirement
                    with self.input.wait_bar(f"Building sdist for {requirement}..."):
                        try:
                            self.tools.subprocess.check_output(
                                [
                                    sys.executable,
                                    "-X",
                                    "utf8",
                                    "-m",
                                    "build",
                                    "--sdist",
                                    "--outdir",
                                    local_requirements_path,
                                    requirement,
                                ],
                                encoding="UTF-8",
                            )
                        except subprocess.CalledProcessError as e:
                            raise BriefcaseCommandError(
                                f"Unable to build sdist for {requirement}"
                            ) from e
                else:
                    try:
                        # Requirement is an existing sdist or wheel file.
                        self.tools.shutil.copy(requirement, local_requirements_path)
                    except OSError as e:
                        raise BriefcaseCommandError(
                            f"Unable to find local requirement {requirement}"
                        ) from e

        # Continue with the default app requirement handling.
        return super()._install_app_requirements(
            app,
            requires=requires,
            app_packages_path=app_packages_path,
        )

    def _pip_requires(self, app: AppConfig, requires: List[str]):
        """Convert the requirements list to an .deb project compatible format.

        Any local file requirements are converted into a reference to the file generated
        by _install_app_requirements().

        :param app: The app configuration
        :param requires: The user-specified list of app requirements
        :returns: The final list of requirement arguments to pass to pip
        """
        # Copy all the requirements that are non-local
        final = [
            requirement
            for requirement in super()._pip_requires(app, requires)
            if not _is_local_requirement(requirement)
        ]

        # Add in any local packages.
        # The sort is needed to ensure testing consistency
        for filename in sorted(self.local_requirements_path(app).iterdir()):
            final.append(filename)

        return final


class DockerOpenCommand(OpenCommand):  # pragma: no-cover-if-is-windows
    # A command that redirects Open to an interactive shell in the container
    # if Docker is being used. Relies on the final command to provide
    # verification that Docker is available, and verify the app context.

    def _open_app(self, app: AppConfig):
        # If we're using Docker, open an interactive shell in the container.
        # Rely on the default CMD statement in the image's Dockerfile to
        # define a default shell.
        if self.use_docker:
            self.tools[app].app_context.run([], interactive=True)
        else:
            super()._open_app(app)
