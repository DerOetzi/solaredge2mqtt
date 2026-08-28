# Weather

Pulls live weather data from OpenWeatherMap. On its own it publishes a weather topic; its real
purpose is feeding the [forecast](forecast.md) model.

```yaml
weather:
  api_key: !secret weather_api_key  # OpenWeatherMap API key

  # Optional, defaults shown
  # language: en                    # Language for the weather description
  # retain: false                  # Keep the last weather snapshot on the broker
  # debounce_cycles: 2  # Failed calls before the weather API is reported offline
```

`debounce_cycles` keeps a single failed API call from marking the weather service offline.

```yaml
# secrets.yml
weather_api_key: "your_openweathermap_api_key"
```

The [location](index.md#basic-settings) has to be set as well, the weather is fetched for those
coordinates.

## Getting an API key

You need an OpenWeatherMap account, an API key, and a
[subscription](https://home.openweathermap.org/subscriptions) to the One Call API. The free tier
covers the request volume this service produces. See
[openweathermap.org](https://openweathermap.org/) for details.

## The published payload

`weather/current` publishes the snapshot under the field names the forecast model uses, not the
provider's own:

`temperature`, `cloud_cover`, `relative_humidity`, `surface_pressure`, `wind_direction`, the WMO
`condition_code`, and the `weather_provider` that delivered it.

!!! warning "Renamed fields"

    Automations reading the older `temp`, `clouds` or `weather_id` fields need adjusting. Home
    Assistant discovery does not cover this topic, so nothing renames itself for you.

The reasoning is in
[decision 0008](../decisions/0008-the-weather-service-speaks-canonically.md), and the field
mapping in [decision 0002](../decisions/0002-canonical-weather-schema.md).
