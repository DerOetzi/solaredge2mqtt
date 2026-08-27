from __future__ import annotations

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.storage import StorageService
from solaredge2mqtt.core.storage.events import StorageAggregatedEvent
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
        storage: StorageService,
    ):
        self.storage = storage
        self.settings = settings

        EventBus.register(self)

    @EventBus.subscribe(StorageAggregatedEvent)
    async def read_historic_energy(self, event: StorageAggregatedEvent | None) -> None:
        for period in HistoricPeriod:
            records = await self.storage.query_timeunit(period, "energy")
            if records is None:
                if period.query == HistoricQuery.LAST:
                    logger.info(
                        "No data found for {period}, skipping this loop", period=period
                    )
                else:
                    raise InvalidDataException(f"No energy data for {period}")

                continue

            for record in records:
                energy = HistoricEnergy.from_energy_data(record, period)

                logger.info(
                    "Read from storage {period} energy: {energy.pv_production} kWh",
                    period=period,
                    energy=energy,
                )

                await EventBus.emit(EnergyReadEvent(energy))
                await EventBus.emit(
                    MQTTPublishEvent(
                        energy.mqtt_topic(),
                        energy,
                        self.settings.retain,
                    )
                )
