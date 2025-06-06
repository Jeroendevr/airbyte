#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#


import logging
import random
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock

import mock
import pendulum
import pytest
from source_hubspot.errors import HubspotRateLimited, InvalidStartDateConfigError
from source_hubspot.helpers import APIv3Property
from source_hubspot.source import SourceHubspot
from source_hubspot.streams import API, BaseStream, Companies, Deals, Products

from airbyte_cdk.models import ConfiguredAirbyteCatalog, ConfiguredAirbyteCatalogSerializer, SyncMode, Type
from airbyte_cdk.test.entrypoint_wrapper import read
from airbyte_cdk.test.state_builder import StateBuilder
from airbyte_cdk.utils.traced_exception import AirbyteTracedException

from .conftest import find_stream
from .utils import read_full_refresh, read_incremental


NUMBER_OF_PROPERTIES = 2000

logger = logging.getLogger("test_client")


@pytest.fixture(autouse=True)
def time_sleep_mock(mocker):
    time_mock = mocker.patch("time.sleep", lambda x: None)
    yield time_mock


def test_check_connection_ok(requests_mock, config):
    responses = [
        {"json": [], "status_code": 200},
    ]

    requests_mock.register_uri("GET", "/properties/v2/contact/properties", responses)
    ok, error_msg = SourceHubspot(config, None, None).check_connection(logger, config=config)

    assert ok
    assert not error_msg


def test_check_connection_empty_config(config):
    config = {}

    with pytest.raises(KeyError):
        SourceHubspot(config, None, None).check_connection(logger, config=config)


def test_check_connection_invalid_config(config):
    config.pop("credentials")

    with pytest.raises(KeyError):
        SourceHubspot(config, None, None).check_connection(logger, config=config)


def test_check_connection_exception(config):
    ok, error_msg = SourceHubspot(config, None, None).check_connection(logger, config=config)

    assert not ok
    assert error_msg


def test_check_connection_bad_request_exception(requests_mock, config_invalid_client_id):
    responses = [
        {"json": {"message": "invalid client_id"}, "status_code": 400},
    ]
    requests_mock.register_uri("POST", "/oauth/v1/token", responses)
    ok, error_msg = SourceHubspot(config_invalid_client_id, None, None).check_connection(logger, config=config_invalid_client_id)
    assert not ok
    assert error_msg


def test_check_connection_invalid_start_date_exception(config_invalid_date):
    with pytest.raises(InvalidStartDateConfigError):
        ok, error_msg = SourceHubspot(config_invalid_date, None, None).check_connection(logger, config=config_invalid_date)
        assert not ok
        assert error_msg


@mock.patch("source_hubspot.source.SourceHubspot.get_custom_object_streams")
def test_streams(requests_mock, config):
    streams = SourceHubspot(config, None, None).streams(config)

    assert len(streams) == 32


@mock.patch("source_hubspot.source.SourceHubspot.get_custom_object_streams")
def test_streams_incremental(requests_mock, config_experimental):
    streams = SourceHubspot(config_experimental, None, None).streams(config_experimental)

    assert len(streams) == 44


def test_custom_streams(config_experimental):
    custom_object_stream_instances = [MagicMock()]
    streams = SourceHubspot(config_experimental, None, None).get_web_analytics_custom_objects_stream(
        custom_object_stream_instances=custom_object_stream_instances,
        common_params={"api": MagicMock(), "start_date": "2021-01-01T00:00:00Z", "credentials": config_experimental["credentials"]},
    )
    assert len(list(streams)) == 1


def test_check_credential_title_exception(config):
    config["credentials"].pop("credentials_title")

    with pytest.raises(Exception):
        SourceHubspot(config, None, None).check_connection(logger, config=config)


def test_parse_and_handle_errors(some_credentials):
    response = MagicMock()
    response.status_code = HTTPStatus.TOO_MANY_REQUESTS

    with pytest.raises(HubspotRateLimited):
        API(some_credentials)._parse_and_handle_errors(response)


def test_convert_datetime_to_string():
    pendulum_time = pendulum.now()

    assert BaseStream._convert_datetime_to_string(pendulum_time, declared_format="date")
    assert BaseStream._convert_datetime_to_string(pendulum_time, declared_format="date-time")


def test_cast_datetime(common_params, caplog):
    field_value = pendulum.now()
    field_name = "current_time"

    Companies(**common_params)._cast_datetime(field_name, field_value)

    expected_warning_message = {
        "type": "LOG",
        "log": {
            "level": "WARN",
            # if you find some diff locally try using "Ex: argument of type 'DateTime' is not iterable in the message". There could be a
            # difference in local environment when pendulum.parsing.__init__.py importing parse_iso8601. Anyway below is working fine
            # in container for now and I am not sure if this diff was just a problem with my setup.
            "message": f"Couldn't parse date/datetime string in {field_name}, trying to parse timestamp... Field value: {field_value}",
        },
    }
    assert expected_warning_message["log"]["message"] in caplog.text


def test_check_connection_backoff_on_limit_reached(requests_mock, config):
    """Error once, check that we retry and not fail"""
    responses = [
        {"json": {"error": "limit reached"}, "status_code": 429, "headers": {"Retry-After": "0"}},
        {"json": [], "status_code": 200},
    ]

    requests_mock.register_uri("GET", "/properties/v2/contact/properties", responses)
    source = SourceHubspot(config, None, None)
    alive, error = source.check_connection(logger=logger, config=config)

    assert alive
    assert not error


def test_check_connection_backoff_on_server_error(requests_mock, config):
    """Error once, check that we retry and not fail"""
    responses = [
        {"json": {"error": "something bad"}, "status_code": 500},
        {"json": [], "status_code": 200},
    ]
    requests_mock.register_uri("GET", "/properties/v2/contact/properties", responses)
    source = SourceHubspot(config, None, None)
    alive, error = source.check_connection(logger=logger, config=config)

    assert alive
    assert not error


def test_stream_forbidden(requests_mock, config, caplog, mock_dynamic_schema_requests):
    json = {
        "status": "error",
        "message": "This access_token does not have proper permissions!",
    }
    requests_mock.get("https://api.hubapi.com/automation/v3/workflows", json=json, status_code=403)
    requests_mock.get("https://api.hubapi.com/crm/v3/schemas", json=json, status_code=403)

    catalog = ConfiguredAirbyteCatalogSerializer.load(
        {
            "streams": [
                {
                    "stream": {
                        "name": "workflows",
                        "json_schema": {},
                        "supported_sync_modes": ["full_refresh"],
                    },
                    "sync_mode": "full_refresh",
                    "destination_sync_mode": "overwrite",
                }
            ]
        }
    )
    with pytest.raises(AirbyteTracedException):
        records = list(SourceHubspot(config, None, None).read(logger, config, catalog, {}))
        records = [r for r in records if r.type == Type.RECORD]
        assert not records
    assert json["message"] in caplog.text
    assert "The authenticated user does not have permissions to access the URL" in caplog.text


def test_parent_stream_forbidden(requests_mock, config, caplog, fake_properties_list, mock_dynamic_schema_requests):
    json = {
        "status": "error",
        "message": "This access_token does not have proper permissions!",
    }
    requests_mock.get("https://api.hubapi.com/marketing/v3/forms", json=json, status_code=403)
    properties_response = [
        {
            "json": [
                {"name": property_name, "type": "string", "updatedAt": 1571085954360, "createdAt": 1565059306048}
                for property_name in fake_properties_list
            ],
            "status_code": 200,
        }
    ]
    requests_mock.get("https://api.hubapi.com/properties/v2/form/properties", properties_response)
    requests_mock.get("https://api.hubapi.com/crm/v3/schemas", json=json, status_code=403)

    catalog = ConfiguredAirbyteCatalogSerializer.load(
        {
            "streams": [
                {
                    "stream": {
                        "name": "form_submissions",
                        "json_schema": {},
                        "supported_sync_modes": ["full_refresh"],
                    },
                    "sync_mode": "full_refresh",
                    "destination_sync_mode": "overwrite",
                }
            ]
        }
    )

    with pytest.raises(AirbyteTracedException):
        records = list(SourceHubspot(config, None, None).read(logger, config, catalog, {}))
        records = [r for r in records if r.type == Type.RECORD]
        assert not records
    assert json["message"] in caplog.text
    assert "The authenticated user does not have permissions to access the URL" in caplog.text


class TestSplittingPropertiesFunctionality:
    BASE_OBJECT_BODY = {
        "createdAt": "2020-12-10T07:58:09.554Z",
        "updatedAt": "2021-07-31T08:18:58.954Z",
        "archived": False,
    }

    @staticmethod
    def set_mock_properties(requests_mock, url, fake_properties_list):
        properties_response = [
            {
                "json": [
                    {"name": property_name, "type": "string", "updatedAt": 1571085954360, "createdAt": 1565059306048}
                    for property_name in fake_properties_list
                ],
                "status_code": 200,
            },
        ]
        requests_mock.register_uri("GET", url, properties_response)

    # Mock the getter method that handles requests.
    def get(self, url, api, params=None):
        response = api._session.get(api.BASE_URL + url, params=params)
        return api._parse_and_handle_errors(response)

    def test_stream_with_splitting_properties(self, requests_mock, api, fake_properties_list, common_params):
        """
        Check working stream `companies` with large list of properties using new functionality with splitting properties
        """
        test_stream = Companies(**common_params)

        parsed_properties = list(APIv3Property(fake_properties_list).split())
        self.set_mock_properties(requests_mock, "/properties/v2/company/properties", fake_properties_list)

        record_ids_paginated = [list(map(str, range(100))), list(map(str, range(100, 150, 1)))]

        test_stream._sync_mode = SyncMode.full_refresh
        test_stream_url = test_stream.url
        test_stream._sync_mode = None

        after_id = None
        for id_list in record_ids_paginated:
            for property_slice in parsed_properties:
                record_responses = [
                    {
                        "json": {
                            "results": [
                                {**self.BASE_OBJECT_BODY, **{"id": id, "properties": {p: "fake_data" for p in property_slice.properties}}}
                                for id in id_list
                            ],
                            "paging": {"next": {"after": id_list[-1]}} if len(id_list) == 100 else {},
                        },
                        "status_code": 200,
                    }
                ]
                prop_key, prop_val = next(iter(property_slice.as_url_param().items()))
                requests_mock.register_uri(
                    "GET",
                    f"{test_stream_url}?limit=100&{prop_key}={prop_val}{f'&after={after_id}' if after_id else ''}",
                    record_responses,
                )
            after_id = id_list[-1]

        # Read preudo-output from generator object
        stream_records = read_full_refresh(test_stream)

        # check that we have records for all set ids, and that each record has 2000 properties (not more, and not less)
        assert len(stream_records) == sum([len(ids) for ids in record_ids_paginated])
        for record in stream_records:
            assert len(record["properties"]) == NUMBER_OF_PROPERTIES
            properties = [field for field in record if field.startswith("properties_")]
            assert len(properties) == NUMBER_OF_PROPERTIES

    def test_stream_with_splitting_properties_with_pagination(self, requests_mock, common_params, api, fake_properties_list):
        """
        Check working stream `products` with large list of properties using new functionality with splitting properties
        """

        parsed_properties = list(APIv3Property(fake_properties_list).split())
        self.set_mock_properties(requests_mock, "/properties/v2/product/properties", fake_properties_list)

        test_stream = Products(**common_params)

        for property_slice in parsed_properties:
            record_responses = [
                {
                    "json": {
                        "results": [
                            {**self.BASE_OBJECT_BODY, **{"id": id, "properties": {p: "fake_data" for p in property_slice.properties}}}
                            for id in ["6043593519", "1092593519", "1092593518", "1092593517", "1092593516"]
                        ],
                        "paging": {},
                    },
                    "status_code": 200,
                }
            ]
            prop_key, prop_val = next(iter(property_slice.as_url_param().items()))
            requests_mock.register_uri("GET", f"{test_stream.url}?{prop_key}={prop_val}", record_responses)

        stream_records = list(test_stream.read_records(sync_mode=SyncMode.incremental))

        assert len(stream_records) == 5
        for record in stream_records:
            assert len(record["properties"]) == NUMBER_OF_PROPERTIES
            properties = [field for field in record if field.startswith("properties_")]
            assert len(properties) == NUMBER_OF_PROPERTIES

    def test_stream_with_splitting_properties_with_new_record(self, requests_mock, common_params, api, fake_properties_list):
        """
        Check working stream `workflows` with large list of properties using new functionality with splitting properties
        """

        parsed_properties = list(APIv3Property(fake_properties_list).split())
        self.set_mock_properties(requests_mock, "/properties/v2/deal/properties", fake_properties_list)

        test_stream = Deals(**common_params)

        ids_list = ["6043593519", "1092593519", "1092593518", "1092593517", "1092593516"]
        for property_slice in parsed_properties:
            record_responses = [
                {
                    "json": {
                        "results": [
                            {**self.BASE_OBJECT_BODY, **{"id": id, "properties": {p: "fake_data" for p in property_slice.properties}}}
                            for id in ids_list
                        ],
                        "paging": {},
                    },
                    "status_code": 200,
                }
            ]
            test_stream._sync_mode = SyncMode.full_refresh
            prop_key, prop_val = next(iter(property_slice.as_url_param().items()))
            requests_mock.register_uri("GET", f"{test_stream.url}?{prop_key}={prop_val}", record_responses)
            test_stream._sync_mode = None
            ids_list.append("1092593513")

        stream_records = read_full_refresh(test_stream)

        assert len(stream_records) == 6


@pytest.fixture(name="configured_catalog")
def configured_catalog_fixture():
    configured_catalog = {
        "streams": [
            {
                "stream": {
                    "name": "quotes",
                    "json_schema": {},
                    "supported_sync_modes": ["full_refresh", "incremental"],
                    "source_defined_cursor": True,
                    "default_cursor_field": ["updatedAt"],
                },
                "sync_mode": "incremental",
                "cursor_field": ["updatedAt"],
                "destination_sync_mode": "append",
            }
        ]
    }
    return ConfiguredAirbyteCatalog.parse_obj(configured_catalog)


def test_search_based_stream_should_not_attempt_to_get_more_than_10k_records(requests_mock, common_params, fake_properties_list):
    """
    If there are more than 10,000 records that would be returned by the Hubspot search endpoint,
    the CRMSearchStream instance should stop at the 10Kth record
    """

    responses = [
        {
            "json": {
                "results": [{"id": f"{y}", "updatedAt": "2022-02-25T16:43:11Z"} for y in range(100)],
                "paging": {
                    "next": {
                        "after": f"{x * 100}",
                    }
                },
            },
            "status_code": 200,
        }
        for x in range(1, 101)
    ]
    # After reaching 10K records, it performs a new search query.
    responses.extend(
        [
            {
                "json": {
                    "results": [{"id": f"{y}", "updatedAt": "2022-03-01T00:00:00Z"} for y in range(100)],
                    "paging": {
                        "next": {
                            "after": f"{x * 100}",
                        }
                    },
                },
                "status_code": 200,
            }
            for x in range(1, 10)
        ]
    )
    # Last page... it does not have paging->next->after
    responses.append(
        {
            "json": {"results": [{"id": f"{y}", "updatedAt": "2022-03-01T00:00:00Z"} for y in range(100)], "paging": {}},
            "status_code": 200,
        }
    )

    properties_response = [
        {
            "json": [
                {"name": property_name, "type": "string", "updatedAt": 1571085954360, "createdAt": 1565059306048}
                for property_name in fake_properties_list
            ],
            "status_code": 200,
        }
    ]

    # Create test_stream instance with some state
    test_stream = Companies(**common_params)
    test_stream._init_sync = pendulum.parse("2022-02-24T16:43:11Z")
    test_stream.state = {"updatedAt": "2022-02-24T16:43:11Z"}

    # Mocking Request
    test_stream._sync_mode = SyncMode.incremental
    requests_mock.register_uri("POST", test_stream.url, responses)
    test_stream._sync_mode = None
    requests_mock.register_uri("GET", "/properties/v2/company/properties", properties_response)
    requests_mock.register_uri(
        "POST",
        "/crm/v4/associations/company/contacts/batch/read",
        [{"status_code": 200, "json": {"results": [{"from": {"id": "1"}, "to": [{"toObjectId": "2"}]}]}}],
    )

    records, _ = read_incremental(test_stream, {})
    # The stream should not attempt to get more than 10K records.
    # Instead, it should use the new state to start a new search query.
    assert len(records) == 11000
    assert test_stream.state["updatedAt"] == test_stream._init_sync.to_iso8601_string()


def test_search_based_incremental_stream_should_sort_by_id(requests_mock, common_params, fake_properties_list):
    """
    If there are more than 10,000 records that would be returned by the Hubspot search endpoint,
    the CRMSearchStream instance should stop at the 10Kth record
    """
    # Create test_stream instance with some state
    test_stream = Companies(**common_params)
    test_stream._init_sync = pendulum.parse("2022-02-24T16:43:11Z")
    test_stream.state = {"updatedAt": "2022-01-24T16:43:11Z"}
    test_stream.associations = []

    def random_date(start, end):
        return pendulum.from_timestamp(random.randint(start, end) / 1000).to_iso8601_string()

    after = 0

    # Custom callback to mock search endpoint filter and sort behavior, returns 100 records per request.
    # See _process_search in stream.py for details on the structure of the filter amd sort parameters.
    # The generated records will have an id that is the sum of the current id and the current "after" value
    # and the updatedAt field will be a random date between min_time and max_time.
    # Store "after" value in the record to check if it resets after 10k records.
    def custom_callback(request, context):
        post_data = request.json()  # Access JSON data from the request body
        after = int(post_data.get("after", 0))
        filters = post_data.get("filters", [])
        min_time = int(filters[0].get("value", 0))
        max_time = int(filters[1].get("value", 0))
        id = int(filters[2].get("value", 0))
        next = int(after) + 100
        results = [
            {"id": f"{y + id}", "updatedAt": random_date(min_time, max_time), "after": after} for y in range(int(after) + 1, next + 1)
        ]
        context.status_code = 200
        if (id + next) < 11000:
            return {"results": results, "paging": {"next": {"after": f"{next}"}}}
        else:
            return {"results": results, "paging": {}}  # Last page

    properties_response = [
        {
            "json": [],
            "status_code": 200,
        }
    ]

    # Mocking Request
    test_stream._sync_mode = SyncMode.incremental
    requests_mock.register_uri("POST", test_stream.url, json=custom_callback)
    # test_stream._sync_mode = None
    requests_mock.register_uri("GET", "/properties/v2/company/properties", properties_response)
    records, _ = read_incremental(test_stream, {})
    # The stream should not attempt to get more than 10K records.
    # Instead, it should use the new state to start a new search query.
    assert len(records) == 11000
    # Check that the records are sorted by id and that "after" resets after 10k records
    assert records[0]["id"] == "1"
    assert records[0]["after"] == 0
    assert records[10000 - 1]["id"] == "10000"
    assert records[10000 - 1]["after"] == 9900
    assert records[10000]["id"] == "10001"
    assert records[10000]["after"] == 0
    assert records[-1]["id"] == "11000"
    assert records[-1]["after"] == 900
    assert test_stream.state["updatedAt"] == test_stream._init_sync.to_iso8601_string()


def test_engagements_stream_pagination_works(requests_mock, common_params, config):
    """
    Tests the engagements stream handles pagination correctly, for both
    full_refresh and incremental sync modes.
    """

    requests_mock.get("https://api.hubapi.com/crm/v3/schemas", json={}, status_code=200)

    # Mocking Request
    requests_mock.register_uri(
        "GET",
        "/engagements/v1/engagements/paged?count=250",
        [
            {
                "json": {
                    "results": [{"engagement": {"id": f"{y}", "lastUpdated": 1641234593251}} for y in range(250)],
                    "hasMore": True,
                    "offset": 250,
                },
                "status_code": 200,
            },
            {
                "json": {
                    "results": [{"engagement": {"id": f"{y}", "lastUpdated": 1641234593251}} for y in range(250, 500)],
                    "hasMore": True,
                    "offset": 500,
                },
                "status_code": 200,
            },
            {
                "json": {
                    "results": [{"engagement": {"id": f"{y}", "lastUpdated": 1641234595251}} for y in range(500, 600)],
                    "hasMore": False,
                },
                "status_code": 200,
            },
        ],
    )

    requests_mock.register_uri(
        "GET",
        "/engagements/v1/engagements/recent/modified?count=250",
        [
            {
                "json": {
                    "results": [{"engagement": {"id": f"{y}", "lastUpdated": 1641234595252}} for y in range(100)],
                    "hasMore": True,
                    "offset": 100,
                },
                "status_code": 200,
            },
            {
                "json": {
                    "results": [{"engagement": {"id": f"{y}", "lastUpdated": 1641234595252}} for y in range(100, 200)],
                    "hasMore": True,
                    "offset": 200,
                },
                "status_code": 200,
            },
            {
                "json": {
                    "results": [{"engagement": {"id": f"{y}", "lastUpdated": 1641234595252}} for y in range(200, 250)],
                    "hasMore": False,
                },
                "status_code": 200,
            },
        ],
    )

    # Create test_stream instance for full refresh.
    test_stream = find_stream("engagements", config)

    records = read_full_refresh(test_stream)
    # The stream should handle pagination correctly and output 600 records.
    assert len(records) == 600

    test_stream = find_stream("engagements", config)
    records, _ = read_incremental(test_stream, {})
    # The stream should handle pagination correctly and output 250 records.
    assert len(records) == 100


def test_engagements_stream_since_old_date(mock_dynamic_schema_requests, requests_mock, common_params, fake_properties_list, config):
    """
    Connector should use 'All Engagements' API for old dates (more than 30 days)
    """
    requests_mock.get("https://api.hubapi.com/crm/v3/schemas", json={}, status_code=200)

    old_date = 1614038400000  # Tuesday, 23 February 2021, 0:00:00
    recent_date = 1645315200000
    responses = [
        {
            "json": {
                "results": [{"engagement": {"id": f"{y}", "lastUpdated": recent_date}} for y in range(100)],
                "hasMore": False,
                "offset": 0,
                "total": 100,
            },
            "status_code": 200,
        }
    ]

    # Mocking Request
    requests_mock.register_uri("GET", "/engagements/v1/engagements/paged?count=250", responses)
    catalog = ConfiguredAirbyteCatalogSerializer.load(
        {
            "streams": [
                {
                    "stream": {
                        "name": "engagements",
                        "json_schema": {},
                        "supported_sync_modes": ["full_refresh", "incremental"],
                    },
                    "sync_mode": "incremental",
                    "destination_sync_mode": "append",
                }
            ]
        }
    )
    state = (
        StateBuilder()
        .with_stream_state(
            "engagements",
            {"lastUpdated": old_date},
        )
        .build()
    )
    output = read(SourceHubspot(config=config, catalog=catalog, state=state), config=config, catalog=catalog, state=state)

    assert len(output.records) == 100
    assert int(output.state_messages[0].state.stream.stream_state.lastUpdated) == recent_date


def test_engagements_stream_since_recent_date(mock_dynamic_schema_requests, requests_mock, common_params, fake_properties_list, config):
    """
    Connector should use 'Recent Engagements' API for recent dates (less than 30 days)
    """
    requests_mock.get("https://api.hubapi.com/crm/v3/schemas", json={}, status_code=200)

    recent_date = pendulum.now() - timedelta(days=10)  # 10 days ago
    recent_date = int(recent_date.timestamp() * 1000)
    responses = [
        {
            "json": {
                "results": [{"engagement": {"id": f"{y}", "lastUpdated": recent_date}} for y in range(100)],
                "hasMore": False,
                "offset": 0,
                "total": 100,
            },
            "status_code": 200,
        }
    ]

    # Create test_stream instance with some state
    catalog = ConfiguredAirbyteCatalogSerializer.load(
        {
            "streams": [
                {
                    "stream": {
                        "name": "engagements",
                        "json_schema": {},
                        "supported_sync_modes": ["full_refresh", "incremental"],
                    },
                    "sync_mode": "incremental",
                    "destination_sync_mode": "overwrite",
                }
            ]
        }
    )
    state = StateBuilder().with_stream_state("engagements", {"lastUpdated": recent_date}).build()

    # Mocking Request
    requests_mock.register_uri("GET", f"/engagements/v1/engagements/recent/modified?count=250&since={recent_date}", responses)

    output = read(SourceHubspot(config=config, catalog=catalog, state=state), config=config, catalog=catalog, state=state)
    # The stream should not attempt to get more than 10K records.
    assert len(output.records) == 100
    assert int(output.state_messages[0].state.stream.stream_state.lastUpdated) == recent_date


def test_engagements_stream_since_recent_date_more_than_10k(
    mock_dynamic_schema_requests, requests_mock, common_params, fake_properties_list, config
):
    """
    Connector should use 'Recent Engagements' API for recent dates (less than 30 days).
    If response from 'Recent Engagements' API returns 10k records, it means that there more records,
    so 'All Engagements' API should be used.
    """
    requests_mock.get("https://api.hubapi.com/crm/v3/schemas", json={}, status_code=200)

    recent_date = pendulum.now() - timedelta(days=10)  # 10 days ago
    recent_date = int(recent_date.timestamp() * 1000)
    responses = [
        {
            "json": {
                "results": [{"engagement": {"id": f"{y}", "lastUpdated": recent_date}} for y in range(100)],
                "hasMore": False,
                "offset": 0,
                "total": 10001,
            },
            "status_code": 200,
        }
    ]

    # Create test_stream instance with some state
    catalog = ConfiguredAirbyteCatalogSerializer.load(
        {
            "streams": [
                {
                    "stream": {
                        "name": "engagements",
                        "json_schema": {},
                        "supported_sync_modes": ["full_refresh", "incremental"],
                    },
                    "sync_mode": "incremental",
                    "destination_sync_mode": "overwrite",
                }
            ]
        }
    )
    state = StateBuilder().with_stream_state("engagements", {"lastUpdated": recent_date}).build()

    # Mocking Request
    requests_mock.register_uri("GET", f"/engagements/v1/engagements/recent/modified?count=250&since={recent_date}", responses)
    requests_mock.register_uri("GET", "/engagements/v1/engagements/paged?count=250", responses)

    output = read(SourceHubspot(config=config, catalog=catalog, state=state), config=config, catalog=catalog, state=state)
    assert len(output.records) == 100
    assert int(output.state_messages[0].state.stream.stream_state.lastUpdated) == recent_date


@mock.patch("source_hubspot.source.SourceHubspot.get_custom_object_streams")
def test_pagination_marketing_emails_stream(mock_get_custom_objects_stream, requests_mock, common_params, config):
    """
    Test pagination for Marketing Emails stream
    """

    requests_mock.register_uri(
        "GET",
        "/marketing-emails/v1/emails/with-statistics?limit=250",
        [
            {
                "json": {
                    "objects": [{"id": f"{y}", "updated": 1641234593251} for y in range(250)],
                    "limit": 250,
                    "offset": 0,
                    "total": 600,
                },
                "status_code": 200,
            },
            {
                "json": {
                    "objects": [{"id": f"{y}", "updated": 1641234593251} for y in range(250, 500)],
                    "limit": 250,
                    "offset": 250,
                    "total": 600,
                },
                "status_code": 200,
            },
            {
                "json": {
                    "objects": [{"id": f"{y}", "updated": 1641234595251} for y in range(500, 600)],
                    "limit": 250,
                    "offset": 500,
                    "total": 600,
                },
                "status_code": 200,
            },
        ],
    )
    test_stream = find_stream("marketing_emails", config)

    records = read_full_refresh(test_stream)
    # The stream should handle pagination correctly and output 600 records.
    assert len(records) == 600


def test_get_granted_scopes(requests_mock, mocker):
    authenticator = mocker.Mock()
    authenticator.get_access_token.return_value = "the-token"

    expected_scopes = ["a", "b", "c"]
    response = [
        {"json": {"scopes": expected_scopes}, "status_code": 200},
    ]
    requests_mock.register_uri("GET", "https://api.hubapi.com/oauth/v1/access-tokens/the-token", response)

    actual_scopes = SourceHubspot({}, None, None).get_granted_scopes(authenticator)

    assert expected_scopes == actual_scopes


def test_get_granted_scopes_retry(requests_mock, mocker):
    authenticator = mocker.Mock()
    expected_token = "the-token"
    authenticator.get_access_token.return_value = expected_token
    mock_url = f"https://api.hubapi.com/oauth/v1/access-tokens/{expected_token}"
    response = [
        {"json": {}, "status_code": 500},
    ]

    requests_mock.register_uri("GET", mock_url, response)
    actual_scopes = SourceHubspot({}, None, None).get_granted_scopes(authenticator)
    assert len(requests_mock.request_history) > 1


def test_streams_oauth_2_auth_no_suitable_scopes(requests_mock, mocker, config):
    authenticator = mocker.Mock()
    authenticator.get_access_token.return_value = "the-token"

    mocker.patch("source_hubspot.streams.API.is_oauth2", return_value=True)
    mocker.patch("source_hubspot.streams.API.get_authenticator", return_value=authenticator)

    requests_mock.get("https://api.hubapi.com/crm/v3/schemas", json={}, status_code=200)

    expected_scopes = ["no.scopes.granted"]
    response = [
        {"json": {"scopes": expected_scopes}, "status_code": 200},
    ]
    requests_mock.register_uri("GET", "https://api.hubapi.com/oauth/v1/access-tokens/the-token", response)

    streams = SourceHubspot(config, None, None).streams(config)

    assert len(streams) == 0
