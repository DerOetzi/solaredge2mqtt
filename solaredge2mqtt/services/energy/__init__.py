from __future__ import annotations

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDBAsync
from solaredge2mqtt.core.influxdb.events import InfluxDBAggregatedEvent
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.services.energy.events import EnergyReadEvent
from solaredge2mqtt.services.energy.models import (
    HistoricEnergy,
    HistoricPeriod,
    HistoricQuery,
)
from solaredge2mqtt.services.energy.settings import EnergySettings


class EnergyService:
    def __init__(
        self,
        settings: EnergySettings,
        event_bus: EventBus,
        influxdb: InfluxDBAsync,
    ):
        self.influxdb = influxdb
        self.settings = settings

        self.event_bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(
            InfluxDBAggregatedEvent, self.read_historic_energy)

    async def read_historic_energy(self, _) -> None:
        for period in HistoricPeriod:
            records = await self.influxdb.query_timeunit(period, "energy")
            if records is None:
                if period.query == HistoricQuery.LAST:
                    logger.info(
                        "No data found for {period}, skipping this loop", period=period
                    )
                else:
                    raise InvalidDataException(f"No energy data for {period}")

                continue

            for record in records:
                energy = HistoricEnergy(record, period)

                logger.info(
                    "Read from influxdb {period} energy: {energy.pv_production} kWh",
                    period=period,
                    energy=energy,
                )

                await self.event_bus.emit(EnergyReadEvent(energy))
                await self.event_bus.emit(
                    MQTTPublishEvent(
                        energy.mqtt_topic(),
                        energy,
                        self.settings.retain,
                    )
                )
