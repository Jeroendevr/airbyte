#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


import pytest


pytest_plugins = ("source_acceptance_test.plugin",)


@pytest.fixture(scope="session", autouse=True)
def connector_setup():
    """This fixture is a placeholder for external resources that acceptance test might require."""
    yield
