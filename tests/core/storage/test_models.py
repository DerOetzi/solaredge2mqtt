"""Tests for the storage Point model."""

from datetime import datetime, timezone

from solaredge2mqtt.core.storage.models import Point, canonical_tags


class TestCanonicalTags:
    """Tests for the canonical tag representation."""

    def test_sorts_keys(self):
        """Tag order must not create a second series for the same tag set."""
        assert canonical_tags({"b": "2", "a": "1"}) == "a=1,b=2"

    def test_empty_tags(self):
        """An untagged point has an empty canonical representation."""
        assert canonical_tags({}) == ""


class TestPoint:
    """Tests for the fluent Point API."""

    def test_fluent_api_returns_self(self):
        """field, tag and time have to stay chainable."""
        moment = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
        point = Point("powerflow_raw").tag("unit", "a").field("pv", 1.0).time(moment)

        assert point.measurement == "powerflow_raw"
        assert point.tags == {"unit": "a"}
        assert point.fields == {"pv": 1.0}
        assert point.timestamp == moment

    def test_tags_canonical(self):
        """The canonical tags of a point are used as its series key."""
        point = Point("m").tag("unit", "a").tag("agg_type", "min")

        assert point.tags_canonical == "agg_type=min,unit=a"

    def test_epoch_seconds_uses_timestamp(self):
        """An explicit timestamp is converted to unix seconds."""
        point = Point("m").time(datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc))

        assert point.epoch_seconds() == 1787133600

    def test_epoch_seconds_defaults_to_now(self):
        """Without a timestamp the point is stamped with the current time."""
        before = int(datetime.now(tz=timezone.utc).timestamp())

        assert Point("m").epoch_seconds() >= before

    def test_epoch_seconds_assumes_utc_for_naive_values(self):
        """A naive timestamp is read as UTC, never as local time."""
        point = Point("m").time(datetime(2026, 8, 19, 10, 0))

        assert point.epoch_seconds() == 1787133600

    def test_repr_contains_measurement(self):
        """The representation helps when a write fails."""
        assert "powerflow_raw" in repr(Point("powerflow_raw"))
