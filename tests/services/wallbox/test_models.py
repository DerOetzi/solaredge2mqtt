"""Tests for wallbox models module."""

import pytest

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.services.wallbox.models import WallboxAPI, WallboxInfo


def make_wallbox_data() -> dict:
    """Create wallbox data for testing."""
    return {
        "model": "EV Charger",
        "firmwareVersion": "2.5.0",
        "serialNumber": "WB123456",
        "state": "charging",
        "vehiclePlugged": True,
        "maxCurrent": 32.0,
        "meter": {
            "totalActivePower": 7200000,  # Value in milliwatts (= 7200W)
        },
    }


class TestWallboxInfo:
    """Tests for WallboxInfo class."""

    def test_wallbox_info_creation(self):
        """Test WallboxInfo creation."""
        data = make_wallbox_data()

        info = WallboxInfo.from_http_response(data)

        assert info.manufacturer == "SolarEdge"
        assert info.model == "EV Charger"
        assert info.version == "2.5.0"
        assert info.serialnumber == "WB123456"

    def test_wallbox_info_homeassistant_device_info(self):
        """Test WallboxInfo homeassistant_device_info method."""
        data = make_wallbox_data()

        info = WallboxInfo.from_http_response(data)
        ha_info = info.homeassistant_device_info()

        assert ha_info["name"] == "SolarEdge Wallbox"
        assert ha_info["manufacturer"] == "SolarEdge"
        assert ha_info["model"] == "EV Charger"
        assert ha_info["hw_version"] == "2.5.0"
        assert ha_info["serial_number"] == "WB123456"

    @pytest.mark.parametrize(
        "missing_key", ["model", "firmwareVersion", "serialNumber"]
    )
    def test_wallbox_info_raises_invalid_data_on_missing_key(self, missing_key):
        """Test WallboxInfo raises InvalidDataException
        when required keys are missing."""
        invalid_response = make_wallbox_data()
        invalid_response.pop(missing_key)

        with pytest.raises(InvalidDataException) as exc_info:
            WallboxInfo.from_http_response(invalid_response)

        assert exc_info.value.message == (
            f"Missing key in Wallbox data: '{missing_key}'"
        )


class TestWallboxAPI:
    """Tests for WallboxAPI class."""

    def test_wallbox_api_creation(self):
        """Test WallboxAPI creation."""
        data = make_wallbox_data()

        wallbox = WallboxAPI.from_http_response(data)

        assert wallbox.info.model == "EV Charger"
        assert wallbox.power == pytest.approx(7200.0)  # Converted from milliwatts
        assert wallbox.state == "charging"
        assert wallbox.vehicle_plugged is True
        assert wallbox.max_current == pytest.approx(32.0)

    def test_wallbox_api_vehicle_not_plugged(self):
        """Test WallboxAPI with vehicle not plugged."""
        data = make_wallbox_data()
        data["vehiclePlugged"] = False

        wallbox = WallboxAPI.from_http_response(data)

        assert wallbox.vehicle_plugged is False

    def test_wallbox_api_zero_power(self):
        """Test WallboxAPI with zero power."""
        data = make_wallbox_data()
        data["meter"]["totalActivePower"] = 0

        wallbox = WallboxAPI.from_http_response(data)

        assert wallbox.power == pytest.approx(0.0)

    def test_wallbox_api_homeassistant_device_info(self):
        """Test WallboxAPI homeassistant_device_info method."""
        data = make_wallbox_data()

        wallbox = WallboxAPI.from_http_response(data)
        ha_info = wallbox.homeassistant_device_info()

        assert ha_info["name"] == "SolarEdge Wallbox"
        assert ha_info["manufacturer"] == "SolarEdge"

    def test_wallbox_api_model_json_schema_excludes_info(self):
        """Test model_json_schema excludes info field."""
        schema = WallboxAPI.model_json_schema()

        assert "info" not in schema["properties"]

    def test_wallbox_api_serialize_vehicle_plugged_true(self):
        """Test serialize_vehicle_plugged returns 'true' string."""
        data = make_wallbox_data()
        data["vehiclePlugged"] = True

        wallbox = WallboxAPI.from_http_response(data)
        serialized = wallbox.model_dump()

        assert serialized["vehicle_plugged"] == "true"

    def test_wallbox_api_serialize_vehicle_plugged_false(self):
        """Test serialize_vehicle_plugged returns 'false' string."""
        data = make_wallbox_data()
        data["vehiclePlugged"] = False

        wallbox = WallboxAPI.from_http_response(data)
        serialized = wallbox.model_dump()

        assert serialized["vehicle_plugged"] == "false"

    def test_wallbox_api_component_constants(self):
        """Test WallboxAPI component constants."""
        assert WallboxAPI.COMPONENT == "wallbox"
        assert WallboxAPI.SOURCE == "api"

    def test_wallbox_api_different_states(self):
        """Test WallboxAPI with different states."""
        states = ["idle", "charging", "error", "waiting"]

        for state in states:
            data = make_wallbox_data()
            data["state"] = state

            wallbox = WallboxAPI.from_http_response(data)

            assert wallbox.state == state

    @pytest.mark.parametrize("invalid_response", [None, [], "invalid", 123])
    def test_wallbox_api_raises_invalid_data_on_non_dict(self, invalid_response):
        """Test WallboxAPI raises InvalidDataException for non-dict responses."""
        with pytest.raises(InvalidDataException) as exc_info:
            WallboxAPI.from_http_response(invalid_response)

        assert exc_info.value.message == "Invalid Wallbox data"

    @pytest.mark.parametrize(
        "missing_key", ["state", "vehiclePlugged", "maxCurrent", "meter"]
    )
    def test_wallbox_api_raises_invalid_data_on_missing_top_level_key(
        self, missing_key
    ):
        """Test WallboxAPI raises InvalidDataException when payload keys are missing."""
        invalid_response = make_wallbox_data()
        invalid_response.pop(missing_key)

        with pytest.raises(InvalidDataException) as exc_info:
            WallboxAPI.from_http_response(invalid_response)

        assert exc_info.value.message == (
            f"Missing key in Wallbox data: '{missing_key}'"
        )

    def test_wallbox_api_raises_invalid_data_on_missing_nested_meter_key(self):
        """Test WallboxAPI raises InvalidDataException
        when meter power key is missing."""
        invalid_response = make_wallbox_data()
        invalid_response["meter"] = {}

        with pytest.raises(InvalidDataException) as exc_info:
            WallboxAPI.from_http_response(invalid_response)

        assert exc_info.value.message == (
            "Missing key in Wallbox data: 'totalActivePower'"
        )
