# Breezometer

Breezometer connector lets you request environment information like air quality, pollen forecast, current and forecasted weather and wildfires for a specific location.

## Prerequisites

- A Breezometer
- An `api_key`, that can be found on your Breezometer account home page.

## Supported sync modes

The Breezometer connector supports full sync refresh.

## Airbyte Open Source

- API Key
- Latitude
- Longitude
- Days to Forecast
- Hours to Forecast
- Historic Hours
- Radius

## Supported Streams

- [Air Quality - Current](https://docs.breezometer.com/api-documentation/air-quality-api/v2/#current-conditions)
- [Air Quality - Forecast](https://docs.breezometer.com/api-documentation/air-quality-api/v2/#hourly-forecast)
- [Air Quality - Historical](https://docs.breezometer.com/api-documentation/air-quality-api/v2/#hourly-history)
- [Pollen - Forecast](https://docs.breezometer.com/api-documentation/pollen-api/v2/#daily-forecast)
- [Weather - Current](https://docs.breezometer.com/api-documentation/weather-api/v1/#current-conditions)
- [Weather - Forecast](https://docs.breezometer.com/api-documentation/weather-api/v1/#hourly-forecast)
- [Wildfire - Burnt Area](https://docs.breezometer.com/api-documentation/wildfire-tracker-api/v1/#burnt-area-api)
- [Wildfire - Locate](https://docs.breezometer.com/api-documentation/wildfire-tracker-api/v1/#current-conditions)

## Changelog

<details>
  <summary>Expand to review</summary>

| Version | Date       | Pull Request                                             | Subject                                     |
| :------ | :--------- | :------------------------------------------------------- | :------------------------------------------ |
| 0.2.24 | 2025-05-10 | [59868](https://github.com/airbytehq/airbyte/pull/59868) | Update dependencies |
| 0.2.23 | 2025-05-03 | [59319](https://github.com/airbytehq/airbyte/pull/59319) | Update dependencies |
| 0.2.22 | 2025-04-26 | [58734](https://github.com/airbytehq/airbyte/pull/58734) | Update dependencies |
| 0.2.21 | 2025-04-19 | [58255](https://github.com/airbytehq/airbyte/pull/58255) | Update dependencies |
| 0.2.20 | 2025-04-12 | [57640](https://github.com/airbytehq/airbyte/pull/57640) | Update dependencies |
| 0.2.19 | 2025-04-05 | [57179](https://github.com/airbytehq/airbyte/pull/57179) | Update dependencies |
| 0.2.18 | 2025-03-29 | [56555](https://github.com/airbytehq/airbyte/pull/56555) | Update dependencies |
| 0.2.17 | 2025-03-22 | [56113](https://github.com/airbytehq/airbyte/pull/56113) | Update dependencies |
| 0.2.16 | 2025-03-08 | [55389](https://github.com/airbytehq/airbyte/pull/55389) | Update dependencies |
| 0.2.15 | 2025-03-01 | [54884](https://github.com/airbytehq/airbyte/pull/54884) | Update dependencies |
| 0.2.14 | 2025-02-22 | [54277](https://github.com/airbytehq/airbyte/pull/54277) | Update dependencies |
| 0.2.13 | 2025-02-15 | [53931](https://github.com/airbytehq/airbyte/pull/53931) | Update dependencies |
| 0.2.12 | 2025-02-08 | [52936](https://github.com/airbytehq/airbyte/pull/52936) | Update dependencies |
| 0.2.11 | 2025-01-25 | [52160](https://github.com/airbytehq/airbyte/pull/52160) | Update dependencies |
| 0.2.10 | 2025-01-18 | [51747](https://github.com/airbytehq/airbyte/pull/51747) | Update dependencies |
| 0.2.9 | 2025-01-11 | [51250](https://github.com/airbytehq/airbyte/pull/51250) | Update dependencies |
| 0.2.8 | 2024-12-28 | [50488](https://github.com/airbytehq/airbyte/pull/50488) | Update dependencies |
| 0.2.7 | 2024-12-21 | [50219](https://github.com/airbytehq/airbyte/pull/50219) | Update dependencies |
| 0.2.6 | 2024-12-14 | [49559](https://github.com/airbytehq/airbyte/pull/49559) | Update dependencies |
| 0.2.5 | 2024-12-12 | [49280](https://github.com/airbytehq/airbyte/pull/49280) | Update dependencies |
| 0.2.4 | 2024-12-11 | [48902](https://github.com/airbytehq/airbyte/pull/48902) | Starting with this version, the Docker image is now rootless. Please note that this and future versions will not be compatible with Airbyte versions earlier than 0.64 |
| 0.2.3 | 2024-11-04 | [48260](https://github.com/airbytehq/airbyte/pull/48260) | Update dependencies |
| 0.2.2 | 2024-10-29 | [47882](https://github.com/airbytehq/airbyte/pull/47882) | Update dependencies |
| 0.2.1 | 2024-10-28 | [43777](https://github.com/airbytehq/airbyte/pull/43777) | Update dependencies |
| 0.2.0 | 2024-08-22 | [44563](https://github.com/airbytehq/airbyte/pull/44563) | Refactor connector to manifest-only format |
| 0.1.1 | 2024-05-21 | [38529](https://github.com/airbytehq/airbyte/pull/38529) | [autopull] base image + poetry + up_to_date |
| 0.1.0 | 2022-10-29 | [18650](https://github.com/airbytehq/airbyte/pull/18650) | Initial version/release of the connector. |

</details>
