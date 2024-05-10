from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import ephem
from astral import LocationInfo
from astral.sun import azimuth, elevation, sun
from numpy import cos, pi, sin
from pandas import DataFrame, Series
from sklearn.base import BaseEstimator, TransformerMixin
from tzlocal import get_localzone_name

from solaredge2mqtt.core.logging import logger

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import LocationSettings


LOCAL_TZ = get_localzone_name()


class BaseEncoder(BaseEstimator, TransformerMixin):
    def __init__(self) -> None:
        self.features: list[str] | None = None
        self._feature_names_out: list[str] = []

    def fit(self, x_vector: DataFrame, *_) -> BaseEncoder:
        if not hasattr(x_vector, "columns"):
            raise AttributeError("x_vector has no columns")

        self.features = x_vector.columns.tolist()
        return self

    def _transform(self, x_vector: DataFrame) -> DataFrame:
        if self.features is None:
            raise AttributeError(f"Encoder {self.__class__} is not been fitted yet.")

        if not hasattr(x_vector, "columns"):
            raise AttributeError("x_vector has no columns")

        if not all(feature in self.features for feature in x_vector.columns):
            raise AttributeError(f"Columns {x_vector.columns} are not in the vector")

        if not all(feature in x_vector.columns for feature in self.features):
            raise AttributeError(f"Columns {self.features} are not in the vector")

        return x_vector

    def _save_feature_names_out(self, x_vector: DataFrame) -> DataFrame:
        self._feature_names_out = x_vector.columns.to_list()
        return x_vector

    def get_feature_names_out(self, *_) -> list[str]:
        return self._feature_names_out


class CategoricalEncoder(BaseEncoder):
    def transform(self, x_vector: DataFrame) -> DataFrame:
        x_vector = self._transform(x_vector).astype("category")
        return self._save_feature_names_out(x_vector)


class CyclicalEncoder(BaseEncoder):
    def __init__(self, **cycle_lengths: dict[str, int]) -> None:
        super().__init__()
        self.cycle_lengths: dict[str, int] = cycle_lengths

    def transform(self, x_vector: DataFrame) -> DataFrame:
        x_vector = self._transform(x_vector)
        for feature in self.features:
            cycle = self.cycle_lengths.get(feature, None)
            if not cycle:
                raise ValueError(f"Unknown cyclical feature {feature}")

            x_vector = self.transform_cycle_columns(
                x_vector, feature, x_vector[feature], cycle
            )
            x_vector.drop(feature, axis=1, inplace=True)

        return self._save_feature_names_out(x_vector)

    def get_params(self, deep=True) -> dict[str, int]:
        return self.cycle_lengths

    @staticmethod
    def transform_cycle_columns(
        x_vector: DataFrame, prefix: str, cycle_vector: DataFrame, cycle_length: float
    ) -> DataFrame:
        x_vector[f"{prefix}_cos"] = cos(2 * pi * cycle_vector / cycle_length)
        x_vector[f"{prefix}_sin"] = sin(2 * pi * cycle_vector / cycle_length)

        return x_vector


class TimeEncoder(BaseEncoder):
    def __init__(self) -> None:
        super().__init__()
        self.season_starts: dict[int, dict[str, datetime]] = {}

    def transform(self, x_vector: DataFrame) -> DataFrame:
        x_vector = self._transform(x_vector)
        for feature in self.features:
            x_vector = CyclicalEncoder.transform_cycle_columns(
                x_vector, f"{feature}_hour", x_vector[feature].dt.hour, 24
            )

            x_vector = CyclicalEncoder.transform_cycle_columns(
                x_vector, f"{feature}_month", x_vector[feature].dt.month, 12
            )

            x_vector[f"{feature}_dst"] = (
                x_vector[feature]
                .apply(lambda x: x.dst() != timedelta(0))
                .astype("category")
            )

            x_vector[f"{feature}_season"] = (
                x_vector[feature].apply(self._map_season).astype("category")
            )
            x_vector = CyclicalEncoder.transform_cycle_columns(
                x_vector,
                f"{feature}_day_of_year",
                x_vector[feature].dt.dayofyear,
                365.25,
            )

            x_vector.drop(feature, axis=1, inplace=True)

        logger.trace(x_vector.head(30))
        return self._save_feature_names_out(x_vector)

    def _map_season(self, date: datetime) -> str:
        year = date.year
        if year not in self.season_starts:
            equinox_mar = ephem.next_vernal_equinox(str(year))
            solstice_jun = ephem.next_summer_solstice(equinox_mar)
            equinox_sep = ephem.next_autumnal_equinox(solstice_jun)
            solstice_dec = ephem.next_winter_solstice(equinox_sep)

            self.season_starts[year] = {
                "spring": equinox_mar.datetime().astimezone(),
                "summer": solstice_jun.datetime().astimezone(),
                "autumn": equinox_sep.datetime().astimezone(),
                "winter": solstice_dec.datetime().astimezone(),
            }

        starts = self.season_starts[year]

        season = "winter"

        if date >= starts["spring"]:
            if date < starts["summer"]:
                season = "spring"
            elif date < starts["autumn"]:
                season = "summer"
            elif date < starts["winter"]:
                season = "autumn"

        return season


class SunEncoder(BaseEncoder):
    def __init__(self, location: LocationSettings) -> None:
        super().__init__()
        self.location = location
        self._location = LocationInfo(
            "name",
            "region",
            timezone=LOCAL_TZ,
            latitude=location.latitude,
            longitude=location.longitude,
        )

    def transform(self, x_vector: DataFrame) -> DataFrame:
        x_vector = self._transform(x_vector)

        for feature in self.features:
            time_key = f"{feature}_time"

            x_vector[time_key] = x_vector[feature].apply(
                lambda x: x + timedelta(minutes=30)
            )

            x_vector[f"{feature}_elevation"] = x_vector[time_key].apply(
                lambda x: elevation(self._location.observer, x)
            )

            x_vector = CyclicalEncoder.transform_cycle_columns(
                x_vector,
                f"{feature}_azimuth",
                x_vector[time_key].apply(lambda x: azimuth(self._location.observer, x)),
                360,
            )

            x_vector[
                [
                    f"{feature}_daylight",
                    f"{feature}_delta_sunrise",
                    f"{feature}_delta_sunset",
                ]
            ] = x_vector[time_key].apply(self.daylight_info)

            x_vector.drop([feature, time_key], axis=1, inplace=True)

        return self._save_feature_names_out(x_vector)

    def daylight_info(self, row_time: datetime) -> Series:
        s = sun(self._location.observer, row_time)
        daylight = (s["sunset"] - s["sunrise"]).total_seconds() / 3600

        delta_sunrise = (row_time - s["sunrise"]).total_seconds() / 3600
        delta_sunset = (s["sunset"] - row_time).total_seconds() / 3600

        return Series([daylight, delta_sunrise, delta_sunset])
