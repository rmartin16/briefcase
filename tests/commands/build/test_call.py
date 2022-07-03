import pytest

from briefcase.config import LinuxDeployPluginType, LinuxDeployPlugin


def test_specific_app(build_command, first_app, second_app):
    """If a specific app is requested, build it."""
    # Add two apps
    build_command.apps = {
        "first": first_app,
        "second": second_app,
    }

    # Configure no command line options
    options = build_command.parse_options([])

    # Run the build command
    build_command(first_app, **options)

    # The right sequence of things will be done
    assert build_command.actions == [
        # Tools are verified
        ("verify",),
        # Build the first app; no state
        ("build", "first", {}),
    ]


def test_multiple_apps(build_command, first_app, second_app):
    """If there are multiple apps, build all of them."""
    # Add two apps
    build_command.apps = {
        "first": first_app,
        "second": second_app,
    }

    # Configure no command line options
    options = build_command.parse_options([])

    # Run the build command
    build_command(**options)

    # The right sequence of things will be done
    assert build_command.actions == [
        # Tools are verified for first app
        ("verify",),
        # Build the first app; no state
        ("build", "first", {}),
        # Tools are verified for second app
        ("verify",),
        # Build the second apps; state from previous build.
        ("build", "second", {"build_state": "first"}),
    ]


def test_non_existent(build_command, first_app_config, second_app):
    """Requesting a build of a non-existent app causes a create."""
    # Add two apps; use the "config only" version of the first app.
    build_command.apps = {
        "first": first_app_config,
        "second": second_app,
    }

    # Configure no command line options
    options = build_command.parse_options([])

    # Run the build command
    build_command(**options)

    # The right sequence of things will be done
    assert build_command.actions == [
        # Tools are verified for first app
        ("verify",),
        # First App doesn't exist, so it will be created, then built
        ("create", "first", {}),
        ("build", "first", {"create_state": "first"}),
        # Tools are verified for second app
        ("verify",),
        # Second app *does* exist, so it only be built
        ("build", "second", {"create_state": "first", "build_state": "first"}),
    ]


def test_unbuilt(build_command, first_app_unbuilt, second_app):
    """Requesting a build of an app that has been created, but not build, just
    causes a build."""
    # Add two apps; use the "unbuilt" version of the first app.
    build_command.apps = {
        "first": first_app_unbuilt,
        "second": second_app,
    }

    # Configure no command line options
    options = build_command.parse_options([])

    # Run the build command
    build_command(**options)

    # The right sequence of things will be done
    assert build_command.actions == [
        # Tools are verified for first app
        ("verify",),
        # First App exists, but hasn't been built; it will be built.
        ("build", "first", {}),
        # Tools are verified for second app
        ("verify",),
        # Second app has been built before; it will be built again.
        ("build", "second", {"build_state": "first"}),
    ]


def test_update_app(build_command, first_app, second_app):
    """If an update is requested, app is updated before build."""
    # Add two apps
    build_command.apps = {
        "first": first_app,
        "second": second_app,
    }

    # Configure a -a command line option
    options = build_command.parse_options(["-u"])

    # Run the build command
    build_command(**options)

    # The right sequence of things will be done
    assert build_command.actions == [
        # Tools are verified for first app
        ("verify",),
        # Update then build the first app
        ("update", "first", {}),
        ("build", "first", {"update_state": "first"}),
        # Tools are verified for second app
        ("verify",),
        # Update then build the second app
        ("update", "second", {"update_state": "first", "build_state": "first"}),
        ("build", "second", {"update_state": "second", "build_state": "first"}),
    ]


def test_update_non_existent(build_command, first_app_config, second_app):
    """Requesting an update of a non-existent app causes a create."""
    # Add two apps; use the "config only" version of the first app.
    build_command.apps = {
        "first": first_app_config,
        "second": second_app,
    }

    # Configure no command line options
    options = build_command.parse_options(["-u"])

    # Run the build command
    build_command(**options)

    # The right sequence of things will be done
    assert build_command.actions == [
        # Tools are verified for first app
        ("verify",),
        # First App doesn't exist, so it will be created, then built
        ("create", "first", {}),
        ("build", "first", {"create_state": "first"}),
        # Tools are verified for second app
        ("verify",),
        # Second app *does* exist, so it will be updated, then built
        ("update", "second", {"create_state": "first", "build_state": "first"}),
        (
            "build",
            "second",
            {"create_state": "first", "build_state": "first", "update_state": "second"},
        ),
    ]


def test_update_unbuilt(build_command, first_app_unbuilt, second_app):
    """Requesting an update of an upbuilt app causes an update before build."""
    # Add two apps; use the "unbuilt" version of the first app.
    build_command.apps = {
        "first": first_app_unbuilt,
        "second": second_app,
    }

    # Configure no command line options
    options = build_command.parse_options(["-u"])

    # Run the build command
    build_command(**options)

    # The right sequence of things will be done
    assert build_command.actions == [
        # Tools are verified for first app
        ("verify",),
        # First App exists, but hasn't been built; it will updated then built.
        ("update", "first", {}),
        ("build", "first", {"update_state": "first"}),
        # Tools are verified for second app
        ("verify",),
        # Second app has been built before; it will be built again.
        ("update", "second", {"update_state": "first", "build_state": "first"}),
        ("build", "second", {"update_state": "second", "build_state": "first"}),
    ]


@pytest.mark.parametrize(
    "linuxdeploy_plugin,type,path,env_var,",
    [
        (["gtk"], LinuxDeployPluginType.GTK, "gtk", None),
        (
            ["https://briefcase.org/linuxdeploy-plugin-gtk.sh"],
            LinuxDeployPluginType.URL,
            "https://briefcase.org/linuxdeploy-plugin-gtk.sh",
            None,
        ),
        (
            ["DEPLOY_GTK_VERSION=3 https://briefcase.org/linuxdeploy-plugin-gtk.sh"],
            LinuxDeployPluginType.URL,
            "https://briefcase.org/linuxdeploy-plugin-gtk.sh",
            "DEPLOY_GTK_VERSION=3",
        ),
    ],
)
def test_app_with_linuxdeploy_plugin(
    build_command, first_app_config, linuxdeploy_plugin, type, path, env_var
):
    """Build an app with the GTK plugin for linuxdeploy."""
    first_app_config.linuxdeploy_plugins = linuxdeploy_plugin
    first_app_config.linuxdeploy_plugins_info = [
        LinuxDeployPlugin(type=type, path=path, env_var=env_var)
    ]
    build_command.apps = {
        "first": first_app_config,
    }

    # Configure no command line options
    options = build_command.parse_options([])

    # Run the build command
    build_command(first_app_config, **options)

    # The right sequence of things will be done
    assert build_command.actions == [
        # Tools are verified
        ("verify",),
        ("create", "first", {}),
        # First App exists, but hasn't been built; it will updated then built.
        ("build", "first", {"create_state": "first"}),
    ]
