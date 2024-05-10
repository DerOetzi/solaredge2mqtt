from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDB
from solaredge2mqtt.core.influxdb.events import InfluxDBAggregatedEvent
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.services.energy.events import EnergyReadEvent
from solaredge2mqtt.services.energy.models import (
    HistoricEnergy,
    HistoricPeriod,
    HistoricQuery,
)


class EnergyService:
    def __init__(
        self,
        event_bus: EventBus,
        influxdb: InfluxDB,
    ):
        self.influxdb = influxdb

        self.event_bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(InfluxDBAggregatedEvent, self.read_historic_energy)

    async def read_historic_energy(self, _) -> None:
        for period in HistoricPeriod:
            record = self.influxdb.query_timeunit(period, "energy")
            if record is None:
                if period.query == HistoricQuery.LAST:
                    logger.info(
                        "No data found for {period}, skipping this loop", period=period
                    )
                else:
                    raise InvalidDataException(f"No energy data for {period}")

                continue

            energy = HistoricEnergy(record, period)

            logger.info(
                "Read from influxdb {period} energy: {energy.pv_production} kWh",
                period=period,
                energy=energy,
            )

            await self.event_bus.emit(EnergyReadEvent(energy))
            await self.event_bus.emit(MQTTPublishEvent(energy.mqtt_topic(), energy))
