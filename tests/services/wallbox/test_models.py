"""Tests for wallbox models module."""


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

        info = WallboxInfo(data)

        assert info.manufacturer == "SolarEdge"
        assert info.model == "EV Charger"
        assert info.version == "2.5.0"
        assert info.serialnumber == "WB123456"

    def test_wallbox_info_homeassistant_device_info(self):
        """Test WallboxInfo homeassistant_device_info method."""
        data = make_wallbox_data()

        info = WallboxInfo(data)
        ha_info = info.homeassistant_device_info()

        assert ha_info["name"] == "SolarEdge Wallbox"
        assert ha_info["manufacturer"] == "SolarEdge"
        assert ha_info["model"] == "EV Charger"
        assert ha_info["hw_version"] == "2.5.0"
        assert ha_info["serial_number"] == "WB123456"


class TestWallboxAPI:
    """Tests for WallboxAPI class."""

    def test_wallbox_api_creation(self):
        """Test WallboxAPI creation."""
        data = make_wallbox_data()

        wallbox = WallboxAPI(data)

        assert wallbox.info.model == "EV Charger"
        assert wallbox.power == 7200.0  # Converted from milliwatts
        assert wallbox.state == "charging"
        assert wallbox.vehicle_plugged is True
        assert wallbox.max_current == 32.0

    def test_wallbox_api_vehicle_not_plugged(self):
        """Test WallboxAPI with vehicle not plugged."""
        data = make_wallbox_data()
        data["vehiclePlugged"] = False

        wallbox = WallboxAPI(data)

        assert wallbox.vehicle_plugged is False

    def test_wallbox_api_zero_power(self):
        """Test WallboxAPI with zero power."""
        data = make_wallbox_data()
        data["meter"]["totalActivePower"] = 0

        wallbox = WallboxAPI(data)

        assert wallbox.power == 0.0

    def test_wallbox_api_homeassistant_device_info(self):
        """Test WallboxAPI homeassistant_device_info method."""
        data = make_wallbox_data()

        wallbox = WallboxAPI(data)
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

        wallbox = WallboxAPI(data)
        serialized = wallbox.model_dump()

        assert serialized["vehicle_plugged"] == "true"

    def test_wallbox_api_serialize_vehicle_plugged_false(self):
        """Test serialize_vehicle_plugged returns 'false' string."""
        data = make_wallbox_data()
        data["vehiclePlugged"] = False

        wallbox = WallboxAPI(data)
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

            wallbox = WallboxAPI(data)

            assert wallbox.state == state
