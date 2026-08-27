#!/usr/bin/env python3

import argparse
import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.core.storage import StorageService
from solaredge2mqtt.services.forecast import FORECAST_AVAILABLE, ForecastService
from solaredge2mqtt.services.forecast.models import Forecast
from solaredge2mqtt.services.forecast.service import LOCAL_TZ
from solaredge2mqtt.services.weather import WeatherClient
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent

if TYPE_CHECKING:
    from pandas import DataFrame


def _energy_period(predictions: "DataFrame") -> dict[datetime, int]:
    energy_period: dict[datetime, int] = {}

    for _, row in predictions.iterrows():
        row_time, row_energy = row["time"], row["energy"]
        if not isinstance(row_time, datetime) or not isinstance(
            row_energy, (int, float)
        ):
            raise InvalidDataException("Predicted energy row is not valid")

        energy_period[row_time] = int(round(row_energy))

    return energy_period


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

    if not settings.storage.is_configured:
        logger.error("Storage is not enabled (required to read training data)")
        return

    storage = StorageService(settings.storage, settings.prices, config_dir)
    await storage.async_init()

    weather = WeatherClient(settings)
    forecast = ForecastService(settings.forecast, settings.location, storage)

    try:
        logger.info("Reading current weather forecast from OpenWeatherMap")
        weather_data = await weather.get_weather()
        await forecast.weather_update(WeatherUpdateEvent(weather_data))

        logger.info("Training forecast models from stored history")
        await forecast.train()

        logger.info("Running prediction")
        elapsed_today = await forecast.predict_elapsed_today()
        predictions = await forecast.predict()

        energy_period = dict(
            sorted(
                (_energy_period(elapsed_today) | _energy_period(predictions)).items()
            )
        )

        for period_time, energy in energy_period.items():
            logger.info(
                "{time}: energy={energy} Wh",
                time=period_time,
                energy=energy,
            )

        battery_charge_needed_wh = None
        if battery_capacity_wh is not None and battery_soc is not None:
            forecast.last_battery_capacity_wh = battery_capacity_wh
            forecast.last_battery_stored_energy_wh = (
                battery_capacity_wh * battery_soc / 100
            )
            battery_charge_needed_wh = forecast.battery_charge_needed_wh()

        result = Forecast.from_energy_period(
            energy_period,
            timezone=str(LOCAL_TZ),
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
        await storage.close()


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
            "main service, without writing anything to MQTT or the storage"
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
