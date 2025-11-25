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
        timer = Timer(mock_event_bus, 5)

        # Mock datetime to return a timestamp divisible by 5
        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            mock_datetime.now.return_value.timestamp.return_value = 10

            await timer.loop()

            # Check that emit was called with IntervalBaseTriggerEvent
            emit_calls = mock_event_bus.emit.call_args_list
            assert any(
                isinstance(call.args[0], IntervalBaseTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_loop_emits_1min_event(self, mock_event_bus):
        """Test that timer loop emits 1 min event at correct interval."""
        timer = Timer(mock_event_bus, 5)

        # Mock datetime where timestamp % 60 == 0 after base_interval adjustment
        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            # timestamp = 64 -> (64 - 4) = 60 which is divisible by 60
            mock_datetime.now.return_value.timestamp.return_value = 64

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            assert any(
                isinstance(call.args[0], Interval1MinTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_loop_emits_5min_event(self, mock_event_bus):
        """Test that timer loop emits 5 min event at correct interval."""
        timer = Timer(mock_event_bus, 5)

        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            # Need timestamp where
            # (timestamp - base_interval - 1 - base_interval) % 300 == 0
            # (304 - 4 - 5) = 295, not divisible
            # (309 - 4 - 5) = 300, divisible by 300
            mock_datetime.now.return_value.timestamp.return_value = 309

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            assert any(
                isinstance(call.args[0], Interval5MinTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_loop_emits_10min_event(self, mock_event_bus):
        """Test that timer loop emits 10 min event at correct interval."""
        timer = Timer(mock_event_bus, 5)

        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            # Need (timestamp - 4 - 5 - 5) % 600 == 0
            # 614 - 14 = 600
            mock_datetime.now.return_value.timestamp.return_value = 614

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            assert any(
                isinstance(call.args[0], Interval10MinTriggerEvent)
                for call in emit_calls
            )

    @pytest.mark.asyncio
    async def test_timer_loop_does_not_emit_when_not_on_interval(self, mock_event_bus):
        """Test that timer doesn't emit base event when not on interval."""
        timer = Timer(mock_event_bus, 5)

        with patch("solaredge2mqtt.core.timer.datetime") as mock_datetime:
            # 11 % 5 != 0
            mock_datetime.now.return_value.timestamp.return_value = 11

            await timer.loop()

            emit_calls = mock_event_bus.emit.call_args_list
            # Base event should not be emitted
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
                mock_datetime.now.return_value.timestamp.return_value = interval * 10

                mock_event_bus.emit.reset_mock()
                await timer.loop()

                # Should emit at least base event on interval
                assert mock_event_bus.emit.called
