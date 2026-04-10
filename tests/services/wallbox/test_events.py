"""Tests for wallbox events module."""

from solaredge2mqtt.services.wallbox.events import WallboxReadEvent
from solaredge2mqtt.services.wallbox.models import WallboxAPI, WallboxInfo


def create_wallbox_info() -> WallboxInfo:
    """Create a test WallboxInfo."""
    return WallboxInfo(
        manufacturer="SolarEdge", model="Wallbox", version="1.0", serialnumber="WB12345"
    )


class TestWallboxReadEvent:
    """Tests for WallboxReadEvent class."""

    def test_event_creation(self):
        """Test creating WallboxReadEvent."""
        # Create a WallboxAPI instance for testing
        wallbox_api = WallboxAPI(
            info=create_wallbox_info(),
            power=6600,
            state="WAITING",
            vehicle_plugged=False,
            max_current=32.0,
        )
        event = WallboxReadEvent(wallbox_api)

        assert event.component == wallbox_api
        assert event.component.power == 6600
        assert event.component.state == "WAITING"

    def test_event_with_different_wallbox_status(self):
        """Test WallboxReadEvent with different status."""
        wallbox_api = WallboxAPI(
            info=create_wallbox_info(),
            power=3680,
            state="CHARGING",
            vehicle_plugged=True,
            max_current=16.0,
        )
        event = WallboxReadEvent(wallbox_api)

        assert event.component.state == "CHARGING"
        assert event.component.power == 3680
        assert event.component.vehicle_plugged is True
