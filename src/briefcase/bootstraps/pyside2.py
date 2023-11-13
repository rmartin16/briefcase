from briefcase.bootstraps.base import BaseGuiBootstrap


class PySide2GuiBootstrap(BaseGuiBootstrap):
    def app_source(self):
        return """\
import importlib.metadata
import sys

from PySide2 import QtWidgets


class {{ cookiecutter.class_name }}(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("{{ cookiecutter.app_name }}")
        self.show()


def main():
    # Linux desktop environments use app's .desktop file to integrate the app
    # to their application menus. The .desktop file of this app will include
    # StartupWMClass key, set to app's formal name, which helps associate
    # app's windows to its menu item.
    #
    # For association to work any windows of the app must have WMCLASS
    # property set to match the value set in app's desktop file. For PySide2
    # this is set with setApplicationName().

    # Find the name of the module that was used to start the app
    app_module = sys.modules["__main__"].__package__
    # Retrieve the app's metadata
    metadata = importlib.metadata.metadata(app_module)

    QtWidgets.QApplication.setApplicationName(metadata["Formal-Name"])

    app = QtWidgets.QApplication(sys.argv)
    main_window = {{ cookiecutter.class_name }}()
    sys.exit(app.exec_())
"""

    def pyproject_table_briefcase_app_extra_content(self):
        return """

requires = [
    "pyside2~=5.15",
]
test_requires = [
{%- if cookiecutter.test_framework == "pytest" %}
    "pytest",
{%- endif %}
]
"""

    def pyproject_table_macOS(self):
        return """
universal_build = true
requires = [
    "std-nslog~=1.0.0",
]
"""

    def pyproject_table_linux(self):
        return """
requires = [
]
"""

    def pyproject_table_linux_system_debian(self):
        return """
system_requires = [
]

system_runtime_requires = [
    # Derived from https://doc.qt.io/qt-6/linux-requirements.html
    "libxrender1",
    "libxcb-render0",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-randr0",
    "libxcb-xfixes0",
    "libxcb-xkb1",
    "libxcb-sync1",
    "libxcb-shm0",
    "libxcb-icccm4",
    "libxcb-keysyms1",
    "libxcb-image0",
    "libxcb-util1",
    "libxkbcommon0",
    "libxkbcommon-x11-0",
    "libfontconfig1",
    "libfreetype6",
    "libxext6",
    "libx11-6",
    "libxcb1",
    "libx11-xcb1",
    "libsm6",
    "libice6",
    "libglib2.0-0",
    "libgl1",
    "libegl1-mesa",
    "libdbus-1-3",
    "libgssapi-krb5-2",
]
"""

    def pyproject_table_linux_system_rhel(self):
        return """
system_requires = [
]

system_runtime_requires = [
    "qt5-qtbase-gui",
]
"""

    def pyproject_table_linux_system_suse(self):
        return """
system_requires = [
]

system_runtime_requires = [
    "libQt5Gui5",
]
"""

    def pyproject_table_linux_system_arch(self):
        return """
system_requires = [
]

system_runtime_requires = [
]
"""

    def pyproject_table_linux_appimage(self):
        return """
manylinux = "manylinux2014"
system_requires = [
# ?? FIXME
]

linuxdeploy_plugins = [
]
"""

    def pyproject_table_linux_flatpak(self):
        return """
flatpak_runtime = "org.kde.Platform"
flatpak_runtime_version = "6.4"
flatpak_sdk = "org.kde.Sdk"
"""

    def pyproject_table_windows(self):
        return """
requires = [
]
"""

    def pyproject_table_iOS(self):
        return """
supported = false
"""

    def pyproject_table_android(self):
        return """
supported = false
"""

    def pyproject_table_web(self):
        return """
supported = false
"""
