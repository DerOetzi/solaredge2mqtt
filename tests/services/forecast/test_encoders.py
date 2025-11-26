"""Tests for forecast encoders module."""

from datetime import datetime, timezone

import pytest
from numpy import isclose
from pandas import DataFrame, Series

from solaredge2mqtt.services.forecast.encoders import (
    BaseEncoder,
    CategoricalEncoder,
    CyclicalEncoder,
    SunEncoder,
    TimeEncoder,
)


class MockLocationSettings:
    """Mock LocationSettings for testing."""

    def __init__(self, latitude=52.52, longitude=13.405):
        self.latitude = latitude
        self.longitude = longitude


class TestBaseEncoder:
    """Tests for BaseEncoder class."""

    def test_base_encoder_init(self):
        """Test BaseEncoder initialization."""
        encoder = BaseEncoder()

        assert encoder.features is None
        assert encoder._feature_names_out == []

    def test_base_encoder_fit(self):
        """Test BaseEncoder fit method."""
        encoder = BaseEncoder()
        df = DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})

        result = encoder.fit(df)

        assert result is encoder
        assert encoder.features == ["col1", "col2"]

    def test_base_encoder_fit_no_columns_raises(self):
        """Test BaseEncoder fit raises when x_vector has no columns."""
        encoder = BaseEncoder()

        with pytest.raises(AttributeError, match="x_vector has no columns"):
            encoder.fit(Series([1, 2, 3]))

    def test_base_encoder_transform_not_fitted_raises(self):
        """Test _transform raises when encoder not fitted."""
        encoder = BaseEncoder()
        df = DataFrame({"col1": [1, 2, 3]})

        with pytest.raises(AttributeError, match="is not been fitted yet"):
            encoder._transform(df)

    def test_base_encoder_transform_no_columns_raises(self):
        """Test _transform raises when x_vector has no columns."""
        encoder = BaseEncoder()
        df = DataFrame({"col1": [1, 2, 3]})
        encoder.fit(df)

        with pytest.raises(AttributeError, match="x_vector has no columns"):
            encoder._transform(Series([1, 2, 3]))

    def test_base_encoder_transform_missing_features_raises(self):
        """Test _transform raises when vector is missing features."""
        encoder = BaseEncoder()
        df_fit = DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})
        df_transform = DataFrame({"col1": [1, 2, 3]})
        encoder.fit(df_fit)

        with pytest.raises(AttributeError, match="are not in the vector"):
            encoder._transform(df_transform)

    def test_base_encoder_transform_extra_features_raises(self):
        """Test _transform raises when vector has extra features."""
        encoder = BaseEncoder()
        df_fit = DataFrame({"col1": [1, 2, 3]})
        df_transform = DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})
        encoder.fit(df_fit)

        with pytest.raises(AttributeError, match="are not in the vector"):
            encoder._transform(df_transform)

    def test_base_encoder_get_feature_names_out(self):
        """Test get_feature_names_out method."""
        encoder = BaseEncoder()
        encoder._feature_names_out = ["feature1", "feature2"]

        result = encoder.get_feature_names_out()

        assert result == ["feature1", "feature2"]

    def test_base_encoder_save_feature_names_out(self):
        """Test _save_feature_names_out method."""
        encoder = BaseEncoder()
        df = DataFrame({"col1": [1, 2], "col2": [3, 4]})

        result = encoder._save_feature_names_out(df)

        assert encoder._feature_names_out == ["col1", "col2"]
        assert result is df


class TestCategoricalEncoder:
    """Tests for CategoricalEncoder class."""

    def test_categorical_encoder_transform(self):
        """Test CategoricalEncoder transform method."""
        encoder = CategoricalEncoder()
        df = DataFrame({"category": ["a", "b", "a", "c"]})
        encoder.fit(df)

        result = encoder.transform(df)

        assert result["category"].dtype.name == "category"
        assert encoder._feature_names_out == ["category"]

    def test_categorical_encoder_multiple_columns(self):
        """Test CategoricalEncoder with multiple columns."""
        encoder = CategoricalEncoder()
        df = DataFrame({
            "cat1": ["a", "b", "a"],
            "cat2": ["x", "y", "z"],
        })
        encoder.fit(df)

        result = encoder.transform(df)

        assert result["cat1"].dtype.name == "category"
        assert result["cat2"].dtype.name == "category"


class TestCyclicalEncoder:
    """Tests for CyclicalEncoder class."""

    def test_cyclical_encoder_init(self):
        """Test CyclicalEncoder initialization."""
        encoder = CyclicalEncoder(hour=24, month=12)

        assert encoder.cycle_lengths == {"hour": 24, "month": 12}

    def test_cyclical_encoder_transform(self):
        """Test CyclicalEncoder transform method."""
        encoder = CyclicalEncoder(hour=24)
        df = DataFrame({"hour": [0, 6, 12, 18]})
        encoder.fit(df)

        result = encoder.transform(df)

        assert "hour_cos" in result.columns
        assert "hour_sin" in result.columns
        assert "hour" not in result.columns

    def test_cyclical_encoder_values_at_boundaries(self):
        """Test CyclicalEncoder produces correct values at cycle boundaries."""
        encoder = CyclicalEncoder(hour=24)
        df = DataFrame({"hour": [0, 12, 24]})
        encoder.fit(df)

        result = encoder.transform(df)

        # At hour 0 and 24: cos should be 1, sin should be 0
        assert isclose(result["hour_cos"].iloc[0], 1.0)
        assert isclose(result["hour_sin"].iloc[0], 0.0)

        # At hour 12: cos should be -1, sin should be ~0
        assert isclose(result["hour_cos"].iloc[1], -1.0)
        assert isclose(result["hour_sin"].iloc[1], 0.0, atol=1e-10)

    def test_cyclical_encoder_unknown_feature_raises(self):
        """Test CyclicalEncoder raises for unknown feature."""
        encoder = CyclicalEncoder(known_feature=24)
        df = DataFrame({"unknown_feature": [1, 2, 3]})
        encoder.fit(df)

        with pytest.raises(ValueError, match="Unknown cyclical feature"):
            encoder.transform(df)

    def test_cyclical_encoder_get_params(self):
        """Test CyclicalEncoder get_params method."""
        encoder = CyclicalEncoder(hour=24, month=12)

        params = encoder.get_params()

        assert params == {"hour": 24, "month": 12}

    def test_cyclical_encoder_transform_cycle_columns_static(self):
        """Test transform_cycle_columns static method."""
        df = DataFrame({"value": [0, 6, 12, 18]})

        result = CyclicalEncoder.transform_cycle_columns(
            df, "test", df["value"], 24
        )

        assert "test_cos" in result.columns
        assert "test_sin" in result.columns
        assert isclose(result["test_cos"].iloc[0], 1.0)
        assert isclose(result["test_sin"].iloc[0], 0.0)


class TestTimeEncoder:
    """Tests for TimeEncoder class."""

    def test_time_encoder_init(self):
        """Test TimeEncoder initialization."""
        encoder = TimeEncoder()

        assert encoder.season_starts == {}

    def test_time_encoder_transform(self):
        """Test TimeEncoder transform method."""
        encoder = TimeEncoder()
        df = DataFrame({
            "timestamp": [
                datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 12, 15, 6, 0, tzinfo=timezone.utc),
            ]
        })
        encoder.fit(df)

        result = encoder.transform(df)

        # Check generated columns exist
        assert "timestamp_hour_cos" in result.columns
        assert "timestamp_hour_sin" in result.columns
        assert "timestamp_month_cos" in result.columns
        assert "timestamp_month_sin" in result.columns
        assert "timestamp_dst" in result.columns
        assert "timestamp_season" in result.columns
        assert "timestamp_day_of_year_cos" in result.columns
        assert "timestamp_day_of_year_sin" in result.columns

        # Original column should be dropped
        assert "timestamp" not in result.columns

    def test_time_encoder_map_season_spring(self):
        """Test _map_season returns spring for spring date."""
        encoder = TimeEncoder()
        # April 15 is typically in spring
        date = datetime(2024, 4, 15, 12, 0, tzinfo=timezone.utc)

        season = encoder._map_season(date)

        assert season == "spring"

    def test_time_encoder_map_season_summer(self):
        """Test _map_season returns summer for summer date."""
        encoder = TimeEncoder()
        # July 15 is typically in summer
        date = datetime(2024, 7, 15, 12, 0, tzinfo=timezone.utc)

        season = encoder._map_season(date)

        assert season == "summer"

    def test_time_encoder_map_season_autumn(self):
        """Test _map_season returns autumn for autumn date."""
        encoder = TimeEncoder()
        # October 15 is typically in autumn
        date = datetime(2024, 10, 15, 12, 0, tzinfo=timezone.utc)

        season = encoder._map_season(date)

        assert season == "autumn"

    def test_time_encoder_map_season_winter(self):
        """Test _map_season returns winter for winter date."""
        encoder = TimeEncoder()
        # January 15 is typically in winter
        date = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        season = encoder._map_season(date)

        assert season == "winter"

    def test_time_encoder_caches_season_starts(self):
        """Test TimeEncoder caches season_starts per year."""
        encoder = TimeEncoder()
        date1 = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
        date2 = datetime(2024, 7, 15, 12, 0, tzinfo=timezone.utc)

        encoder._map_season(date1)
        encoder._map_season(date2)

        assert 2024 in encoder.season_starts
        assert len(encoder.season_starts) == 1


class TestSunEncoder:
    """Tests for SunEncoder class."""

    def test_sun_encoder_init(self):
        """Test SunEncoder initialization."""
        location = MockLocationSettings(latitude=52.52, longitude=13.405)
        encoder = SunEncoder(location)

        assert encoder.location == location
        assert encoder._location is not None

    def test_sun_encoder_transform(self):
        """Test SunEncoder transform method."""
        location = MockLocationSettings(latitude=52.52, longitude=13.405)
        encoder = SunEncoder(location)

        df = DataFrame({
            "time": [
                datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 15, 14, 0, tzinfo=timezone.utc),
            ]
        })
        encoder.fit(df)

        result = encoder.transform(df)

        # Check generated columns exist
        assert "time_elevation" in result.columns
        assert "time_azimuth_cos" in result.columns
        assert "time_azimuth_sin" in result.columns
        assert "time_daylight" in result.columns
        assert "time_delta_sunrise" in result.columns
        assert "time_delta_sunset" in result.columns

        # Original column should be dropped
        assert "time" not in result.columns

    def test_sun_encoder_daylight_info(self):
        """Test daylight_info method returns Series."""
        location = MockLocationSettings(latitude=52.52, longitude=13.405)
        encoder = SunEncoder(location)

        time = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
        result = encoder.daylight_info(time)

        assert isinstance(result, Series)
        assert len(result) == 3
        # In June at Berlin (52.52), daylight should be around 16-17 hours
        assert result.iloc[0] > 15  # daylight hours

    def test_sun_encoder_elevation_at_noon(self):
        """Test elevation is positive at noon in summer."""
        location = MockLocationSettings(latitude=52.52, longitude=13.405)
        encoder = SunEncoder(location)

        df = DataFrame({
            "time": [datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)]
        })
        encoder.fit(df)

        result = encoder.transform(df)

        # At noon in summer, elevation should be positive
        assert result["time_elevation"].iloc[0] > 0
