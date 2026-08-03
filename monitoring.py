#!/usr/bin/env python3

import argparse
import asyncio

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.services.monitoring import MonitoringSite


async def _run(config_dir: str) -> None:
    settings = service_settings(config_dir)
    initialize_logging(settings.logging_level)

    if not settings.monitoring.is_configured:
        logger.error("Monitoring is not configured")
        return

    monitoring = MonitoringSite(settings.monitoring, None)

    try:
        modules = await monitoring.get_modules()

        for identifier, module in modules.items():
            logger.info(
                "{identifier}: energy={energy} power_slots={power_slots}",
                identifier=f"{identifier} ({module.info.name})",
                energy=module.energy,
                power_slots=len(module.power) if module.power else 0,
            )
    finally:
        await monitoring.close()


def run(config_dir: str = "config") -> None:
    try:
        asyncio.run(_run(config_dir))
    except ConfigurationException:
        logger.error("Configuration error")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


def main():
    parser = argparse.ArgumentParser(
        description="Run the SolarEdge2MQTT monitoring service once (single shot)"
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default="config",
        help="Path to configuration directory (default: config)",
    )
    args = parser.parse_args()

    run(config_dir=args.config_dir)


if __name__ == "__main__":
    main()
