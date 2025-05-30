#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#


import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping
from unittest import TestCase

import pytest
from source_amazon_seller_partner.config_migrations import MigrateAccountType, MigrateReportOptions, MigrateStreamNameOption
from source_amazon_seller_partner.source import SourceAmazonSellerPartner

from airbyte_cdk.models import OrchestratorType, Type
from airbyte_cdk.sources import Source
from airbyte_cdk.test.state_builder import StateBuilder


MIGRATIONS_TEST_DIRECTORY = Path(__file__).parent / "test_migrations"

CMD = "check"
SOURCE: Source = SourceAmazonSellerPartner(
    None,
    {
        "replication_start_date": "2021-07-01T00:00:00Z",
        "refresh_token": "<refresh_token>",
        "lwa_app_id": "<lwa_app_id>",
        "lwa_client_secret": "<lwa_client_secret>",
        "aws_access_key": "<aws_access_key>",
        "aws_secret_key": "<aws_secret_key>",
        "role_arn": "<role_arn>",
        "aws_environment": "PRODUCTION",
        "region": "US",
    },
    StateBuilder().build(),
)


def load_config(config_path: Path) -> Mapping[str, Any]:
    with config_path.open() as config:
        return json.load(config)


class TestMigrateAccountType:
    test_not_migrated_config_path = MIGRATIONS_TEST_DIRECTORY / "account_type_migration/not_migrated_config.json"
    test_migrated_config_path = MIGRATIONS_TEST_DIRECTORY / "account_type_migration/migrated_config.json"

    def test_migrate_config(self, capsys):
        config = load_config(self.test_not_migrated_config_path)
        assert "account_type" not in config
        migration_instance = MigrateAccountType()
        migration_instance.migrate([CMD, "--config", self.test_not_migrated_config_path.as_posix()], SOURCE)
        control_msg = json.loads(capsys.readouterr().out)
        assert control_msg["type"] == Type.CONTROL.value
        assert control_msg["control"]["type"] == OrchestratorType.CONNECTOR_CONFIG.value
        migrated_config = control_msg["control"]["connectorConfig"]["config"]
        assert migrated_config["account_type"] == "Seller"

    def test_should_not_migrate(self):
        config = load_config(self.test_migrated_config_path)
        assert config["account_type"]
        migration_instance = MigrateAccountType()
        assert not migration_instance._should_migrate(config)


class TestMigrateReportOptions:
    test_not_migrated_config_path = MIGRATIONS_TEST_DIRECTORY / "report_options_migration/not_migrated_config.json"
    test_migrated_config_path = MIGRATIONS_TEST_DIRECTORY / "report_options_migration/migrated_config.json"

    @pytest.mark.parametrize(
        ("input_config", "expected_report_options_list"),
        (
            (
                {"report_options": '{"GET_REPORT": {"reportPeriod": "WEEK"}}'},
                [{"stream_name": "GET_REPORT", "options_list": [{"option_name": "reportPeriod", "option_value": "WEEK"}]}],
            ),
            ({"report_options": None}, []),
            ({"report_options": "{{}"}, []),
            ({}, []),
        ),
    )
    def test_transform_report_options(self, input_config, expected_report_options_list):
        expected_config = {**input_config, "report_options_list": expected_report_options_list}
        assert MigrateReportOptions._transform(input_config) == expected_config

    def test_migrate_config(self, capsys):
        config = load_config(self.test_not_migrated_config_path)
        assert "report_options_list" not in config
        migration_instance = MigrateReportOptions()
        migration_instance.migrate([CMD, "--config", self.test_not_migrated_config_path.as_posix()], SOURCE)
        control_msg = json.loads(capsys.readouterr().out)
        assert control_msg["type"] == Type.CONTROL.value
        assert control_msg["control"]["type"] == OrchestratorType.CONNECTOR_CONFIG.value
        migrated_config = control_msg["control"]["connectorConfig"]["config"]
        expected_report_options_list = [
            {"stream_name": "GET_REPORT", "options_list": [{"option_name": "reportPeriod", "option_value": "WEEK"}]},
        ]
        assert migrated_config["report_options_list"] == expected_report_options_list

    def test_should_not_migrate(self):
        config = load_config(self.test_migrated_config_path)
        assert config["report_options_list"]
        migration_instance = MigrateReportOptions()
        assert not migration_instance._should_migrate(config)


class TestMigrateStreamNameOption:
    test_not_migrated_config_path = MIGRATIONS_TEST_DIRECTORY / "stream_name_option_migration/not_migrated_config.json"
    test_migrated_config_path = MIGRATIONS_TEST_DIRECTORY / "stream_name_option_migration/migrated_config.json"

    def test_migrate_config(self, capsys):
        config = load_config(self.test_not_migrated_config_path)
        for options_list in config["report_options_list"]:
            assert "report_name" not in options_list

        migration_instance = MigrateStreamNameOption()
        migration_instance.migrate([CMD, "--config", self.test_not_migrated_config_path.as_posix()], SOURCE)
        control_msg = json.loads(capsys.readouterr().out)
        assert control_msg["type"] == Type.CONTROL.value
        assert control_msg["control"]["type"] == OrchestratorType.CONNECTOR_CONFIG.value
        migrated_config = control_msg["control"]["connectorConfig"]["config"]
        for options_list in migrated_config["report_options_list"]:
            assert options_list["report_name"] == options_list["stream_name"]

    def test_should_not_migrate(self):
        config = load_config(self.test_migrated_config_path)
        migration_instance = MigrateStreamNameOption()
        assert not migration_instance._should_migrate(config)
        for options_list in config["report_options_list"]:
            assert options_list["stream_name"]
