from __future__ import annotations

import ast
import enum
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar

from briefcase.exceptions import BriefcaseCommandError, ParseError
from briefcase.integrations.base import Tool, ToolCache

DistributionT = TypeVar("DistributionT", bound="Distribution")

_distributions: dict[str, type[DistributionT]] = dict()


def parse_freedesktop_os_release(content: str) -> dict[str, str]:
    """Parse the content of an /etc/os-release file.

    Implementation adapted from Example 5 of
    https://www.freedesktop.org/software/systemd/man/os-release.html

    Remove this func once Python 3.10 is no longer supported.

    :param content: The text content of the /etc/os-release file.
    :returns: A dictionary of key-value pairs, in the same format returned by
        `platform.freedesktop_os_release()`.
    """
    values = {}
    for line_number, line in enumerate(content.split("\n"), start=1):
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([A-Z][A-Z_0-9]+)=(.*)", line)
        if m:
            name, val = m.groups()
            if val and val[0] in "\"'":
                try:
                    val = ast.literal_eval(val)
                except SyntaxError as e:
                    raise ParseError(
                        "Failed to parse output of FreeDesktop os-release file; "
                        f"Line {line_number}: {e}"
                    )
            values[name] = val
        else:
            raise ParseError(
                "Failed to parse output of FreeDesktop os-release file; "
                f"Line {line_number}: {line!r}"
            )

    return values


class PackageFormat(enum.Enum):
    DEB = "deb"
    PKG = "pkg"
    RPM = "rpm"

    def file_name(self):

class Distribution(ABC):
    name: str
    _base_distribution: type[DistributionT] | None = None

    freedesktop_id: str | None
    freedesktop_id_like: list[str] | None

    packaging_format: PackageFormat | None

    install_package_cmdline: list[str] | None
    verify_package_cmdline: list[str] | None

    python_packages: list[str] | None
    build_packages: list[str] | None

    def __init__(self, vendor: str | None, codename: str | None):
        # Capture details about the specific Linux install
        self.vendor = vendor  # ID from freedesktop info
        self.codename = codename  # VERSION_CODENAME from freedesktop info

    def __init_subclass__(cls, **kwargs):
        """Register each distribution when it is defined."""
        _distributions[cls.name] = cls

    @classmethod
    def base_distribution(cls) -> type[DistributionT]:
        """The distribution from which this distribution is derived; may be self.

        Distributions are commonly derived from others: for example, Ubuntu from Debian
        """
        return cls._base_distribution if cls._base_distribution is not None else cls

    @abstractmethod
    @property
    def package_file_name(self) -> str:
        """A properly formatted file name for a distribution package."""

    @classmethod
    def package_abi_cmdline(cls, format: PackageFormat | None = None) -> list[str]:
        format = cls.packaging_format if format is None else format
        return {
            PackageFormat.DEB: ["dpkg", "--print-architecture"],
            PackageFormat.RPM: ["rpm", "--eval", "%_target_cpu"],
            PackageFormat.PKG: ["pacman-conf", "Architecture"],
        }[format]

    @classmethod
    def from_freedesktop(cls, freedesktop_info: dict[str, str]) -> type[DistributionT]:
        """Identify a distribution from Freedesktop info."""
        distro = Distribution.from_freedesktop_id(freedesktop_info["ID"])
        if distro is Unknown:
            distro = Distribution.from_freedesktop_id_like(
                freedesktop_info.get("ID_LIKE", "").split()
            )
        return distro

    @classmethod
    def from_freedesktop_id(cls, freedesktop_id: str) -> type[DistributionT]:
        """Identifies a specific distribution for a name."""
        for distro in _distributions.values():
            if freedesktop_id == distro.freedesktop_id:
                return distro
        else:
            return Unknown

    @classmethod
    def from_freedesktop_id_like(
        cls,
        freedesktop_id_like: list[str],
    ) -> type[DistributionT]:
        """Identifies a related distribution for a list of names."""
        for distro in _distributions.values():
            if any(d in freedesktop_id_like for d in distro.freedesktop_id_like):
                return distro
        else:
            return Unknown


class Arch(Distribution):
    name = "Arch"

    freedesktop_id = "arch"
    freedesktop_id_like = [freedesktop_id]

    packaging_format = PackageFormat.PKG

    install_package_cmdline = ["pacman", "-Syu"]
    verify_package_cmdline = ["pacman", "-Q"]

    python_packages = ["python3"]
    build_packages = ["base-devel"]

    @property
    def package_file_name(self) -> str:
        return ""


class Debian(Distribution):
    name = "Debian"

    packaging_format = PackageFormat.DEB

    freedesktop_id = "debian"
    freedesktop_id_like = ["ubuntu", freedesktop_id]

    install_package_cmdline = ["apt", "install"]
    verify_package_cmdline = ["dpkg", "-s"]

    python_packages = ["python3-dev"]
    build_packages = ["build-essential"]

    @property
    def package_file_name(self) -> str:
        return (
            "{name}"
            "_{version}"
            "-{revision}"
            f"~{self.vendor}"
            f"-{self.codename}"
            "_{abi}"
            ".deb"
        )


class RHEL(Distribution):
    name = "RHEL"

    freedesktop_id = "rhel"
    freedesktop_id_like = ["fedora", freedesktop_id]

    packaging_format = PackageFormat.RPM

    install_package_cmdline = ["dnf", "install"]
    verify_package_cmdline = ["rpm", "-q"]

    python_packages = ["python3-devel"]
    build_packages = ["gcc", "make", "pkgconf-pkg-config"]

    @property
    def package_file_name(self) -> str:
        return (
            "{name}"
            "-{version}"
            "-{revision}"
            f".{'fc' if self.vendor == 'fedora' else 'el'}{self.codename}"
            ".{abi}"
            ".rpm"
        )


class SUSE(Distribution):
    name = "SUSE"

    freedesktop_id = "suse"
    freedesktop_id_like = [freedesktop_id]

    packaging_format = PackageFormat.RPM

    install_package_cmdline = ["zypper", "install"]
    verify_package_cmdline = ["rpm", "-q", "--whatprovides"]

    python_packages = ["python3-devel"]
    build_packages = ["patterns-devel-base-devel_basis"]

    @property
    def package_file_name(self) -> str:
        return (
            "{name}"
            "-{version}"
            "-{revision}"
            ".{abi}"
            ".rpm"
        )


class Unknown(Distribution):
    name = "Unknown"

    freedesktop_id = None
    freedesktop_id_like = None

    packaging_format = None

    install_package_cmdline = None
    verify_package_cmdline = None

    python_packages = None
    build_packages = None

    @property
    def package_file_name(self) -> str:
        return ""


class LinuxEnvironment(Tool):
    name: str = "linux"
    full_name: str = "Linux"

    ETC_OS_RELEASE: Path = Path("/etc/os-release")
    FREEDESKTOP_INFO_ERROR: str = (
        "Could not find the /etc/os-release file. "
        "Is this a Freedesktop-compliant Linux distribution?"
    )

    @classmethod
    def verify_install(cls, tools: ToolCache, **kwargs) -> LinuxEnvironment:
        """Add Linux environment generator to tools."""
        # short circuit since already verified and available
        if hasattr(tools, "linux"):
            return tools.linux

        tools.linux = LinuxEnvironment(tools=tools)
        return tools.linux

    def from_host(self) -> DistributionT:
        """Create Distribution from local host machine."""
        return self._identify_distribution(self._freedesktop_info_host())

    def from_image_tag(self, image_tag: str) -> DistributionT:
        """Create distribution from an image."""
        return self._identify_distribution(self._freedesktop_info_image(image_tag))

    def _identify_distribution(self, freedesktop_info: dict[str, str]) -> DistributionT:
        """Identify the Linux distribution from the Freedesktop os-release file.

        :param freedesktop_info: The parsed content of the Freedesktop /etc/os-release
            file. This is the same format returned by
            `platform.freedesktop_os_release()`.
        :returns: Distribution
        """
        if distro := Distribution.from_freedesktop(freedesktop_info):
            return distro(
                vendor=freedesktop_info["ID"],
                codename=self._freedesktop_info_codename(freedesktop_info),
            )
        else:
            return Unknown(vendor=None, codename=None)

    def _freedesktop_info_host(self) -> dict[str, str]:
        """Extract the Freedesktop info for the host's Linux environment."""
        try:
            if sys.version_info < (3, 10):  # pragma: no-cover-if-gte-py310
                # This reproduces the Python 3.10 platform.freedesktop_os_release() function
                with self.ETC_OS_RELEASE.open(encoding="utf-8") as f:
                    return parse_freedesktop_os_release(f.read())
            else:  # pragma: no-cover-if-lt-py310
                return self.tools.platform.freedesktop_os_release()
        except OSError as e:
            raise BriefcaseCommandError(self.FREEDESKTOP_INFO_ERROR) from e

    def _freedesktop_info_image(self, image_tag: str | None = None) -> dict[str, str]:
        """Extract the Freedesktop info for the Linux environment in the image."""
        with self.tools.input.wait_bar(f"Checking Docker image {image_tag}..."):
            try:
                output = self.tools.docker.check_output(
                    ["cat", self.ETC_OS_RELEASE],
                    image_tag=image_tag,
                )
                return parse_freedesktop_os_release(output)
            except subprocess.CalledProcessError as e:
                raise BriefcaseCommandError(self.FREEDESKTOP_INFO_ERROR) from e

    def _freedesktop_info_codename(self, freedesktop_info: dict[str, str]) -> str:
        """Extract a codename from the Freedesktop info."""
        try:
            if not (codename := freedesktop_info["VERSION_CODENAME"]):
                # Fedora *has* a VERSION_CODENAME key, but it is empty.
                # Treat it as missing.
                raise KeyError("VERSION_CODENAME")
        except KeyError:
            try:
                # Arch uses a specific constant in VERSION_ID
                # TODO:PR: this was actually an issue in how archlinux built their images
                # TODO:PR: https://gitlab.archlinux.org/archlinux/archlinux-docker/-/commit/74dc761af835b7fe091db387c5cdca472813dc6c
                # TODO:PR: should this check just be removed?
                if freedesktop_info["VERSION_ID"] == "TEMPLATE_VERSION_ID":
                    codename = "rolling"
                else:
                    codename = freedesktop_info["VERSION_ID"].split(".")[0]
            except KeyError:
                # Manjaro doesn't have a VERSION_ID key
                codename = "rolling"
        return codename
