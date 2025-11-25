"""Tests for core timer module."""

from unittest.mock import patch

import pytest

from solaredge2mqtt.core.timer import Timer
from solaredge2mqtt.core.timer.events import (
    Interval1MinTriggerEvent,
    Interval5MinTriggerEvent,
    Interval10MinTriggerEvent,
    IntervalBaseTriggerEvent,
)


def calculate_timestamp_for_interval(base_interval: int, target_interval: int) -> int:
    """
    Calculate a timestamp that triggers the target interval.

    The timer logic subtracts offsets from the timestamp before checking
    divisibility by the target interval.
    """
    # Base event: timestamp % base_interval == 0
    # 1min event: (timestamp - base_interval + 1) % 60 == 0
    # 5min event: (timestamp - base_interval + 1 - base_interval) % 300 == 0
    # 10min event: (timestamp - offset) % 600 == 0
    #   where offset = base_interval - 1 + base_interval + base_interval

    if target_interval == base_interval:
        return target_interval * 2  # Simple multiple of base_interval
    if target_interval == 60:
        offset = base_interval - 1
        return 60 + offset  # Results in (timestamp - offset) % 60 == 0
    if target_interval == 300:
        offset = (base_interval - 1) + base_interval
        return 300 + offset  # Results in (timestamp - offset) % 300 == 0
    if target_interval == 600:
        offset = (base_interval - 1) + base_interval + base_interval
        return 600 + offset  # Results in (timestamp - offset) % 600 == 0
    return target_interval


class TestTimer:
    """Tests for Timer class."""

    def test_timer_initialization(self, event_bus):
        """Test Timer initializes with event_bus and base_interval."""
        timer = Timer(event_bus, 5)

        assert timer.event_bus is event_bus
        assert timer.base_interval == 5

    @pytest.mark.asyncio
    async def test_timer_loop_emits_base_event_on_interval(self, mock_event_bus):
        """Test that timer loop emits base event at correct interval."""
        base_interval = 5
        timer = Timer(mock_event_bus, base_interval)

        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            # Use a timestamp divisible by base_interval
            timestamp = calculate_timestamp_for_interval(base_interval, base_interval)
            mock_datetime.now.return_value.timestamp.return_value = timestamp

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            assert any(
                isinstance(call.args[0], IntervalBaseTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_loop_emits_1min_event(self, mock_event_bus):
        """Test that timer loop emits 1 min event at correct interval."""
        base_interval = 5
        timer = Timer(mock_event_bus, base_interval)

        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            timestamp = calculate_timestamp_for_interval(base_interval, 60)
            mock_datetime.now.return_value.timestamp.return_value = timestamp

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            assert any(
                isinstance(call.args[0], Interval1MinTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_loop_emits_5min_event(self, mock_event_bus):
        """Test that timer loop emits 5 min event at correct interval."""
        base_interval = 5
        timer = Timer(mock_event_bus, base_interval)

        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            timestamp = calculate_timestamp_for_interval(base_interval, 300)
            mock_datetime.now.return_value.timestamp.return_value = timestamp

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            assert any(
                isinstance(call.args[0], Interval5MinTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_loop_emits_10min_event(self, mock_event_bus):
        """Test that timer loop emits 10 min event at correct interval."""
        base_interval = 5
        timer = Timer(mock_event_bus, base_interval)

        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            timestamp = calculate_timestamp_for_interval(base_interval, 600)
            mock_datetime.now.return_value.timestamp.return_value = timestamp

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            assert any(
                isinstance(call.args[0], Interval10MinTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_loop_does_not_emit_when_not_on_interval(self, mock_event_bus):
        """Test that timer doesn't emit base event when not on interval."""
        base_interval = 5
        timer = Timer(mock_event_bus, base_interval)

        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            # Use a timestamp NOT divisible by base_interval
            timestamp = 11  # 11 % 5 != 0
            mock_datetime.now.return_value.timestamp.return_value = timestamp

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            assert not any(
                isinstance(call.args[0], IntervalBaseTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_with_different_base_intervals(self, mock_event_bus):
        """Test timer works with different base intervals."""
        for interval in [1, 5, 10, 15]:
            timer = Timer(mock_event_bus, interval)

            with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
                # Use a timestamp that is a multiple of the base interval
                timestamp = interval * 10
                mock_datetime.now.return_value.timestamp.return_value = timestamp

                mock_event_bus.emit.reset_mock()
                await timer.loop()

                assert mock_event_bus.emit.called
