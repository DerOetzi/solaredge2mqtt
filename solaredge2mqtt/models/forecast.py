from solaredge2mqtt.models.base import EnumModel


class ForecastQuery(EnumModel):
    ACTUAL = "actual_unit"
    NEXT = "forecast_unit"

    def __init__(self, query: str) -> None:
        self._query: str = query

    @property
    def query(self) -> str:
        return self._query


class ForecastPeriod(EnumModel):
    TODAY = "today", "1d", ForecastQuery.ACTUAL
    TOMORROW = "tomorrow", "1d", ForecastQuery.NEXT
    CURRENT_HOUR = "current_hour", "1h", ForecastQuery.ACTUAL
    NEXT_HOUR = "next_hour", "1h", ForecastQuery.NEXT

    def __init__(self, topic: str, unit: str, query: ForecastQuery) -> None:
        self._topic: str = topic
        self._unit: str = unit
        self._query: ForecastQuery = query

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def query(self) -> ForecastQuery:
        return self._query
