"""Tests for core MQTT models module."""


from solaredge2mqtt.core.mqtt.models import MAX_MQTT_PAYLOAD_SIZE


class TestMQTTModels:
    """Tests for MQTT models constants."""

    def test_max_mqtt_payload_size(self):
        """Test MAX_MQTT_PAYLOAD_SIZE constant."""
        assert MAX_MQTT_PAYLOAD_SIZE == 1024
        assert isinstance(MAX_MQTT_PAYLOAD_SIZE, int)
