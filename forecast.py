#!/usr/bin/env python3

import argparse
import asyncio
from datetime import datetime

from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDBAsync
from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.services.forecast import FORECAST_AVAILABLE, ForecastService
from solaredge2mqtt.services.forecast.models import Forecast, ForecasterType
from solaredge2mqtt.services.weather import WeatherClient
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent


async def _run(
    config_dir: str,
    battery_capacity_wh: float | None,
    battery_soc: float | None,
) -> None:
    settings = service_settings(config_dir)
    initialize_logging(settings.logging_level)

    if not FORECAST_AVAILABLE:
        logger.error(
            "Forecast dependencies are not installed, "
            "run: pip install -U solaredge2mqtt[forecast]"
        )
        return

    if not settings.is_forecast_enabled:
        logger.error("Forecast is not enabled/configured")
        return

    if not settings.influxdb.is_configured:
        logger.error("InfluxDB is not configured (required to read training data)")
        return

    influxdb = InfluxDBAsync(settings.influxdb, settings.prices)
    influxdb.init()

    weather = WeatherClient(settings)
    forecast = ForecastService(settings.forecast, settings.location, influxdb)

    try:
        logger.info("Reading current weather forecast from OpenWeatherMap")
        weather_data = await weather.get_weather()
        await forecast.weather_update(WeatherUpdateEvent(weather_data))

        logger.info("Training forecast models from InfluxDB history")
        await forecast.train()

        logger.info("Running prediction")
        predictions = await forecast.predict()

        power_period = {}
        for _, row in predictions[ForecasterType.POWER].iterrows():
            row_time, row_power = row["time"], row["power"]
            if not isinstance(row_time, datetime) or not isinstance(
                row_power, (int, float)
            ):
                raise InvalidDataException("Predicted power row is not valid")

            power_period[row_time] = int(round(row_power))

        energy_period = {}
        for _, row in predictions[ForecasterType.ENERGY].iterrows():
            row_time, row_energy = row["time"], row["energy"]
            if not isinstance(row_time, datetime) or not isinstance(
                row_energy, (int, float)
            ):
                raise InvalidDataException("Predicted energy row is not valid")

            energy_period[row_time] = int(round(row_energy * 1000))

        for period_time in power_period:
            logger.info(
                "{time}: power={power} W, energy={energy} Wh",
                time=period_time,
                power=power_period[period_time],
                energy=energy_period[period_time],
            )

        battery_charge_needed_wh = None
        if battery_capacity_wh is not None and battery_soc is not None:
            forecast.last_battery_capacity_wh = battery_capacity_wh
            forecast.last_battery_stored_energy_wh = (
                battery_capacity_wh * battery_soc / 100
            )
            battery_charge_needed_wh = forecast.battery_charge_needed_wh()

        result = Forecast(
            power_period=power_period,
            energy_period=energy_period,
            battery_charge_needed_wh=battery_charge_needed_wh,
        )

        logger.info("Energy today: {v} Wh", v=result.energy_today)
        logger.info("Energy remaining today: {v} Wh", v=result.energy_today_remaining)
        logger.info("Energy tomorrow: {v} Wh", v=result.energy_tomorrow)

        if battery_charge_needed_wh is not None:
            logger.info(
                "Battery charge needed: {v} Wh", v=round(battery_charge_needed_wh)
            )
            logger.info(
                "Optimal battery charge start time: {v}",
                v=result.battery_charge_optimal_start_time,
            )
    finally:
        await weather.close()
        await influxdb.close()


def run(
    config_dir: str = "config",
    battery_capacity_wh: float | None = None,
    battery_soc: float | None = None,
) -> None:
    try:
        asyncio.run(_run(config_dir, battery_capacity_wh, battery_soc))
    except ConfigurationException:
        logger.error("Configuration error")
    except InvalidDataException as error:
        logger.error("Invalid data: {error}", error=error)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Train and run the SolarEdge2MQTT forecast once, standalone from the "
            "main service, without writing anything to MQTT or InfluxDB"
        )
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default="config",
        help="Path to configuration directory (default: config)",
    )
    parser.add_argument(
        "--battery-capacity-wh",
        type=float,
        default=None,
        help="Battery capacity in Wh, to preview the optimal charge start time",
    )
    parser.add_argument(
        "--battery-soc",
        type=float,
        default=None,
        help="Currently battery state of charge in %%, to preview the optimal "
        "charge start time",
    )
    args = parser.parse_args()

    run(
        config_dir=args.config_dir,
        battery_capacity_wh=args.battery_capacity_wh,
        battery_soc=args.battery_soc,
    )


if __name__ == "__main__":
    main()
