"""Tests for service module and Service lifecycle behavior."""

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # pyright: ignore[reportMissingImports]

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.service import Service, _run_service, run


def _build_service() -> Service:
    """Build a lightweight Service instance for method-level tests."""
    service = Service.__new__(Service)
    service.cancel_request = asyncio.Event()
    service.loops = set()
    service._run_task = None
    service.mqtt = None
    service.event_bus = MagicMock()
    service.event_bus.cancel_tasks = AsyncMock()
    service.influxdb = None
    service.powerflow = cast(Any, None)
    service.monitoring = None
    service.weather = None
    return service


def _build_settings(
    *,
    influx_configured: bool,
    monitoring_configured: bool,
    weather_enabled: bool,
    forecast_enabled: bool,
    homeassistant_enabled: bool,
) -> SimpleNamespace:
    """Create lightweight settings object for Service initialization tests."""
    return SimpleNamespace(
        logging_level="INFO",
        interval=5,
        influxdb=SimpleNamespace(is_configured=influx_configured),
        prices=SimpleNamespace(),
        energy=SimpleNamespace(),
        monitoring=SimpleNamespace(is_configured=monitoring_configured),
        is_weather_enabled=weather_enabled,
        forecast=SimpleNamespace(),
        location=SimpleNamespace(),
        is_forecast_enabled=forecast_enabled,
        homeassistant=SimpleNamespace(enable=homeassistant_enabled),
        mqtt=SimpleNamespace(),
    )


class TestRunService:
    """Tests for async service wrapper helper."""

    @pytest.mark.asyncio
    async def test_run_service_creates_service_and_awaits_run(self):
        """_run_service should instantiate Service and await run."""
        service_instance = MagicMock()
        service_instance.run = AsyncMock()

        with patch("solaredge2mqtt.service.Service", return_value=service_instance):
            await _run_service("config")

        service_instance.run.assert_awaited_once()


class TestRunWrapper:
    """Tests for top-level run wrapper behavior."""

    def test_run_handles_configuration_exception(self):
        """Run should log configuration errors and not raise."""

        def fake_asyncio_run(coroutine):
            coroutine.close()
            raise ConfigurationException("service", "invalid")

        with (
            patch("solaredge2mqtt.service.asyncio.run", side_effect=fake_asyncio_run),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            run("config")

        mock_logger.error.assert_called_once_with("Configuration error")

    def test_run_handles_cancelled_error(self):
        """Run should log cancellation and not raise."""

        def fake_asyncio_run(coroutine):
            coroutine.close()
            raise asyncio.CancelledError

        with (
            patch("solaredge2mqtt.service.asyncio.run", side_effect=fake_asyncio_run),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            run("config")

        mock_logger.debug.assert_called_once_with("Service cancelled")

    def test_run_handles_keyboard_interrupt(self):
        """Run should log keyboard interruption and not raise."""

        def fake_asyncio_run(coroutine):
            coroutine.close()
            raise KeyboardInterrupt

        with (
            patch("solaredge2mqtt.service.asyncio.run", side_effect=fake_asyncio_run),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            run("config")

        mock_logger.info.assert_called_once_with("Service interrupted by user")

    def test_run_success_path_calls_asyncio_run(self):
        """Run should execute asyncio.run in normal path."""

        def fake_asyncio_run(coroutine):
            coroutine.close()
            return None

        with patch(
            "solaredge2mqtt.service.asyncio.run", side_effect=fake_asyncio_run
        ) as mock_run:
            run("config")

        mock_run.assert_called_once()


class TestServiceInitialization:
    """Tests for Service initialization and optional service wiring."""

    def test_init_creates_all_optional_services_when_enabled(self):
        """Initialization should create optional services when configured."""
        settings = _build_settings(
            influx_configured=True,
            monitoring_configured=True,
            weather_enabled=True,
            forecast_enabled=True,
            homeassistant_enabled=True,
        )

        event_bus = MagicMock()
        influx = MagicMock()

        with (
            patch("solaredge2mqtt.service.service_settings", return_value=settings),
            patch("solaredge2mqtt.service.initialize_logging") as init_logging,
            patch("solaredge2mqtt.service.EventBus", return_value=event_bus),
            patch("solaredge2mqtt.service.Timer") as timer_cls,
            patch(
                "solaredge2mqtt.service.InfluxDBAsync", return_value=influx
            ) as influx_cls,
            patch("solaredge2mqtt.service.EnergyService") as energy_cls,
            patch("solaredge2mqtt.service.PowerflowService") as powerflow_cls,
            patch("solaredge2mqtt.service.MonitoringSite") as monitoring_cls,
            patch("solaredge2mqtt.service.WeatherClient") as weather_cls,
            patch("solaredge2mqtt.service.ForecastService") as forecast_cls,
            patch("solaredge2mqtt.service.HomeAssistantDiscovery") as homeassistant_cls,
            patch("solaredge2mqtt.service.FORECAST_AVAILABLE", True),
        ):
            service = Service("config")

        init_logging.assert_called_once_with("INFO")
        timer_cls.assert_called_once_with(event_bus, settings.interval)
        influx_cls.assert_called_once_with(
            settings.influxdb, settings.prices, event_bus
        )
        energy_cls.assert_called_once_with(settings.energy, event_bus, influx)
        powerflow_cls.assert_called_once_with(settings, event_bus, influx)
        monitoring_cls.assert_called_once_with(settings.monitoring, event_bus, influx)
        weather_cls.assert_called_once_with(settings, event_bus)
        forecast_cls.assert_called_once_with(
            settings.forecast, settings.location, event_bus, influx
        )
        homeassistant_cls.assert_called_once_with(settings, event_bus)
        assert service.forecast is forecast_cls.return_value

    def test_init_logs_warning_when_forecast_unavailable_but_enabled(self):
        """Initialization should warn when forecast is enabled but unavailable."""
        settings = _build_settings(
            influx_configured=False,
            monitoring_configured=False,
            weather_enabled=False,
            forecast_enabled=True,
            homeassistant_enabled=False,
        )

        with (
            patch("solaredge2mqtt.service.service_settings", return_value=settings),
            patch("solaredge2mqtt.service.initialize_logging"),
            patch("solaredge2mqtt.service.EventBus", return_value=MagicMock()),
            patch("solaredge2mqtt.service.Timer"),
            patch("solaredge2mqtt.service.PowerflowService"),
            patch("solaredge2mqtt.service.FORECAST_AVAILABLE", False),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            service = Service("config")

        mock_logger.warning.assert_called_once_with(
            "Forecast service not available, please refer to README"
        )
        assert service.influxdb is None
        assert service.energy is None
        assert service.monitoring is None
        assert service.weather is None
        assert service.forecast is None
        assert service.homeassistant is None

    def test_init_skips_warning_when_forecast_unavailable_and_disabled(self):
        """Initialization should not warn when forecast is unavailable and disabled."""
        settings = _build_settings(
            influx_configured=False,
            monitoring_configured=False,
            weather_enabled=False,
            forecast_enabled=False,
            homeassistant_enabled=False,
        )

        with (
            patch("solaredge2mqtt.service.service_settings", return_value=settings),
            patch("solaredge2mqtt.service.initialize_logging"),
            patch("solaredge2mqtt.service.EventBus", return_value=MagicMock()),
            patch("solaredge2mqtt.service.Timer"),
            patch("solaredge2mqtt.service.PowerflowService"),
            patch("solaredge2mqtt.service.FORECAST_AVAILABLE", False),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            Service("config")

        mock_logger.warning.assert_not_called()


class TestServiceControl:
    """Tests for task control and cancellation methods."""

    def test_register_signal_handlers_registers_sigint_and_sigterm(self):
        """Signal registration should register both expected signals."""
        service = _build_service()
        loop = MagicMock()

        service._register_signal_handlers(loop)

        assert loop.add_signal_handler.call_count == 2

    @pytest.mark.asyncio
    async def test_cancel_sets_cancel_request_and_cancels_tasks(self):
        """Cancel should set the flag and cancel run and loop tasks."""
        service = _build_service()

        run_task = asyncio.create_task(asyncio.sleep(60))
        loop_task = asyncio.create_task(asyncio.sleep(60))
        service._run_task = run_task
        service.loops.add(loop_task)

        service.cancel()

        assert service.cancel_request.is_set()
        assert run_task.cancelled() or run_task.cancelling() > 0
        assert loop_task.cancelled() or loop_task.cancelling() > 0

        await asyncio.gather(run_task, loop_task, return_exceptions=True)

    def test_cancel_is_idempotent_when_already_set(self):
        """Cancel should return early when cancellation was already requested."""
        service = _build_service()
        service.cancel_request.set()
        service._run_task = MagicMock()

        service.cancel()

        service._run_task.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_cancels_loops_when_run_task_is_none(self):
        """Cancel should still cancel loop tasks when _run_task is None."""
        service = _build_service()

        loop_task = asyncio.create_task(asyncio.sleep(60))
        service._run_task = None
        service.loops.add(loop_task)

        service.cancel()

        assert service.cancel_request.is_set()
        assert loop_task.cancelled() or loop_task.cancelling() > 0

        await asyncio.gather(loop_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_stop_loops_cancels_and_clears_loop_tasks(self):
        """Stop loops should cancel pending tasks and clear internal set."""
        service = _build_service()

        task_1 = asyncio.create_task(asyncio.sleep(60))
        task_2 = asyncio.create_task(asyncio.sleep(60))
        service.loops = {task_1, task_2}

        await service._stop_loops()

        assert service.loops == set()
        assert task_1.cancelled() or task_1.cancelling() > 0
        assert task_2.cancelled() or task_2.cancelling() > 0

    @pytest.mark.asyncio
    async def test_stop_loops_returns_early_when_empty(self):
        """Stop loops should return without gathering when no tasks exist."""
        service = _build_service()

        with patch(
            "solaredge2mqtt.service.asyncio.gather", new_callable=AsyncMock
        ) as gather:
            await service._stop_loops()

        gather.assert_not_called()


class TestServiceRun:
    """Tests for Service.run orchestration and shutdown guarantees."""

    @pytest.mark.asyncio
    async def test_run_registers_handlers_executes_main_loop_and_shutdown(self):
        """Run should call signal registration, main loop, and shutdown."""
        service = _build_service()
        service._register_signal_handlers = MagicMock()
        service.main_loop = AsyncMock()
        service.shutdown = AsyncMock()

        await service.run()

        service._register_signal_handlers.assert_called_once()
        service.main_loop.assert_awaited_once()
        service.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_still_calls_shutdown_when_main_loop_raises(self):
        """Run should always call shutdown even when main loop fails."""
        service = _build_service()
        service._register_signal_handlers = MagicMock()
        service.main_loop = AsyncMock(side_effect=RuntimeError("boom"))
        service.shutdown = AsyncMock()

        with pytest.raises(RuntimeError, match="boom"):
            await service.run()

        service.shutdown.assert_awaited_once()


class TestServiceLooping:
    """Tests for loop scheduling and MQTT listener startup."""

    def test_start_mqtt_listener_raises_without_client(self):
        """MQTT listener startup requires an initialized MQTT client."""
        service = _build_service()

        with pytest.raises(RuntimeError, match="MQTT client is not initialized"):
            service._start_mqtt_listener()

    @pytest.mark.asyncio
    async def test_start_mqtt_listener_creates_two_tasks(self):
        """MQTT listener startup should schedule both listener tasks."""
        service = _build_service()
        service.mqtt = MagicMock()
        service.mqtt.listen = AsyncMock(side_effect=asyncio.CancelledError)
        service.mqtt.process_queue = AsyncMock(side_effect=asyncio.CancelledError)

        service._start_mqtt_listener()

        assert len(service.loops) == 2

        for task in service.loops:
            task.cancel()

        await asyncio.gather(*list(service.loops), return_exceptions=True)

    @pytest.mark.asyncio
    async def test_schedule_loop_adds_task(self):
        """Scheduling a loop should create and track a task."""
        service = _build_service()
        service.run_loop = AsyncMock()

        service.schedule_loop(5, MagicMock())

        assert len(service.loops) == 1
        await asyncio.gather(*list(service.loops), return_exceptions=True)

    @pytest.mark.asyncio
    async def test_run_loop_executes_handle_and_sleeps_remaining_time(self):
        """Run loop should execute handles and wait based on execution duration."""
        service = _build_service()

        async def one_shot_handle() -> None:
            await asyncio.to_thread(lambda: None)
            service.cancel_request.set()

        mock_sleep = AsyncMock()
        with (
            patch("solaredge2mqtt.service.asyncio.sleep", mock_sleep),
            patch("solaredge2mqtt.service.time", side_effect=[0.0, 0.25]),
        ):
            await service.run_loop(1, one_shot_handle)

        mock_sleep.assert_any_await(0)
        mock_sleep.assert_any_await(0.75)
        assert mock_sleep.await_count == 2

    @pytest.mark.asyncio
    async def test_run_loop_sleeps_interval_when_execution_takes_longer(self):
        """Run loop should sleep full interval when execution exceeds interval."""
        service = _build_service()

        async def one_shot_handle() -> None:
            await asyncio.to_thread(lambda: None)
            service.cancel_request.set()

        mock_sleep = AsyncMock()
        with (
            patch("solaredge2mqtt.service.asyncio.sleep", mock_sleep),
            patch("solaredge2mqtt.service.time", side_effect=[0.0, 2.0]),
        ):
            await service.run_loop(1, one_shot_handle)

        mock_sleep.assert_any_await(0)
        mock_sleep.assert_any_await(1)
        assert mock_sleep.await_count == 2

    @pytest.mark.asyncio
    async def test_run_loop_with_handle_list_passes_args(self):
        """Run loop should execute a list of handles and forward arguments."""
        service = _build_service()

        first_handle = AsyncMock()

        async def second_handle(value: str) -> None:
            await asyncio.to_thread(lambda: None)
            assert value == "ok"
            service.cancel_request.set()

        mock_sleep = AsyncMock()
        with patch("solaredge2mqtt.service.asyncio.sleep", mock_sleep):
            await service.run_loop(
                1,
                [first_handle, second_handle],
                args=["ok"],
            )

        first_handle.assert_awaited_once_with("ok")
        mock_sleep.assert_any_await(0)


class TestServiceMainLoop:
    """Tests for main_loop control flow and error handling branches."""

    @pytest.mark.asyncio
    async def test_main_loop_initializes_services_and_exits_on_cancel(self):
        """Main loop should initialize dependencies and finalize cleanly."""
        service = _build_service()
        service.settings = cast(Any, SimpleNamespace(mqtt=SimpleNamespace()))
        service.influxdb = MagicMock()
        service.influxdb.init = MagicMock()
        service.homeassistant = MagicMock()
        service.homeassistant.async_init = AsyncMock()
        service.powerflow = MagicMock()
        service.powerflow.async_init = AsyncMock()
        service.timer = MagicMock()
        service.timer.loop = AsyncMock()
        service.finalize = AsyncMock()

        service._start_mqtt_listener = MagicMock()
        service.schedule_loop = MagicMock()

        mqtt_client = MagicMock()
        mqtt_client.publish_status_online = AsyncMock()
        mqtt_client.__aenter__ = AsyncMock(return_value=mqtt_client)
        mqtt_client.__aexit__ = AsyncMock(return_value=None)

        async def gather_side_effect(*_args, **_kwargs):
            await asyncio.to_thread(lambda: None)
            service.cancel_request.set()
            return None

        with (
            patch("solaredge2mqtt.service.MQTTClient", return_value=mqtt_client),
            patch(
                "solaredge2mqtt.service.asyncio.gather", side_effect=gather_side_effect
            ),
        ):
            await service.main_loop()

        service.influxdb.init.assert_called_once()
        mqtt_client.publish_status_online.assert_awaited_once()
        service.homeassistant.async_init.assert_awaited_once()
        service.powerflow.async_init.assert_awaited_once()
        service._start_mqtt_listener.assert_called_once()
        service.schedule_loop.assert_called_once_with(1, service.timer.loop)
        service.finalize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_loop_logs_reconnect_on_mqtt_error(self):
        """Main loop should log reconnect and sleep when MQTT errors occur."""
        service = _build_service()
        service.settings = cast(Any, SimpleNamespace(mqtt=SimpleNamespace()))
        service.influxdb = None
        service.homeassistant = None
        service.powerflow = MagicMock()
        service.powerflow.async_init = AsyncMock()
        service.timer = MagicMock()
        service.timer.loop = AsyncMock()
        service.finalize = AsyncMock()

        def mqtt_side_effect(*_args, **_kwargs):
            raise RuntimeError("mqtt down")

        async def sleep_side_effect(_seconds: float):
            await asyncio.to_thread(lambda: None)
            service.cancel_request.set()

        with (
            patch("solaredge2mqtt.service.MQTTClient", side_effect=mqtt_side_effect),
            patch("solaredge2mqtt.service.MqttError", Exception),
            patch(
                "solaredge2mqtt.service.asyncio.sleep", side_effect=sleep_side_effect
            ),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            await service.main_loop()

        service.finalize.assert_awaited_once()
        mock_logger.error.assert_called_once_with(
            "MQTT error, reconnecting in 5 seconds..."
        )

    @pytest.mark.asyncio
    async def test_main_loop_breaks_on_mqtt_error_when_cancelled(self):
        """Main loop should break immediately on MQTT error after cancellation."""
        service = _build_service()
        service.settings = cast(Any, SimpleNamespace(mqtt=SimpleNamespace()))
        service.influxdb = None
        service.homeassistant = None
        service.powerflow = MagicMock()
        service.powerflow.async_init = AsyncMock()
        service.timer = MagicMock()
        service.timer.loop = AsyncMock()
        service.finalize = AsyncMock()

        def mqtt_side_effect(*_args, **_kwargs):
            service.cancel_request.set()
            raise RuntimeError("stop now")

        with (
            patch("solaredge2mqtt.service.MQTTClient", side_effect=mqtt_side_effect),
            patch("solaredge2mqtt.service.MqttError", Exception),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            await service.main_loop()

        service.finalize.assert_awaited_once()
        mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_main_loop_reraises_cancelled_error(self):
        """Main loop should re-raise cancellation errors after logging."""
        service = _build_service()
        service.settings = cast(Any, SimpleNamespace(mqtt=SimpleNamespace()))
        service.influxdb = None
        service.homeassistant = None
        service.powerflow = MagicMock()
        service.powerflow.async_init = AsyncMock()
        service.timer = MagicMock()
        service.timer.loop = AsyncMock()
        service.finalize = AsyncMock()
        service._start_mqtt_listener = MagicMock()
        service.schedule_loop = MagicMock()

        mqtt_client = MagicMock()
        mqtt_client.publish_status_online = AsyncMock()
        mqtt_client.__aenter__ = AsyncMock(return_value=mqtt_client)
        mqtt_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("solaredge2mqtt.service.MQTTClient", return_value=mqtt_client),
            patch(
                "solaredge2mqtt.service.asyncio.gather",
                side_effect=asyncio.CancelledError,
            ),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            with pytest.raises(asyncio.CancelledError):
                await service.main_loop()

        service.finalize.assert_awaited_once()
        mock_logger.debug.assert_any_call("Loops cancelled")


class TestServiceShutdown:
    """Tests for finalization and close behavior."""

    @pytest.mark.asyncio
    async def test_finalize_stops_loops_publishes_offline_and_cancels_event_tasks(self):
        """Finalize should stop loops, set offline status, and cancel event tasks."""
        service = _build_service()
        service._stop_loops = AsyncMock()
        cancel_tasks_mock = AsyncMock()
        service.event_bus.cancel_tasks = cancel_tasks_mock
        mqtt = MagicMock()
        mqtt.publish_status_offline = AsyncMock()
        service.mqtt = mqtt

        await service.finalize()

        service._stop_loops.assert_awaited_once()
        mqtt.publish_status_offline.assert_awaited_once()
        cancel_tasks_mock.assert_awaited_once()
        assert service.mqtt is None

    @pytest.mark.asyncio
    async def test_finalize_ignores_mqtt_error_during_offline_publish(self):
        """Finalize should continue cleanup if offline status publish fails."""
        service = _build_service()
        service._stop_loops = AsyncMock()
        cancel_tasks_mock = AsyncMock()
        service.event_bus.cancel_tasks = cancel_tasks_mock
        service.mqtt = MagicMock()
        service.mqtt.publish_status_offline = AsyncMock(
            side_effect=Exception("unavailable")
        )

        with patch("solaredge2mqtt.service.MqttError", Exception):
            await service.finalize()

        cancel_tasks_mock.assert_awaited_once()
        assert service.mqtt is None

    @pytest.mark.asyncio
    async def test_finalize_with_no_mqtt_still_cancels_event_tasks(self):
        """Finalize should cancel event tasks even when mqtt is absent."""
        service = _build_service()
        service._stop_loops = AsyncMock()
        cancel_tasks_mock = AsyncMock()
        service.event_bus.cancel_tasks = cancel_tasks_mock
        service.mqtt = None

        await service.finalize()

        service._stop_loops.assert_awaited_once()
        cancel_tasks_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_calls_finalize_and_close(self):
        """Shutdown should always await finalize and close."""
        service = _build_service()
        service.finalize = AsyncMock()
        service.close = AsyncMock()

        await service.shutdown()

        service.finalize.assert_awaited_once()
        service.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_closes_available_services(self):
        """Close should await close on all configured service clients."""
        service = _build_service()
        service.influxdb = MagicMock()
        service.influxdb.close = AsyncMock()
        service.powerflow = MagicMock()
        service.powerflow.close = AsyncMock()
        service.monitoring = None
        service.weather = MagicMock()
        service.weather.close = AsyncMock()

        await service.close()

        service.influxdb.close.assert_awaited_once()
        service.powerflow.close.assert_awaited_once()
        service.weather.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_logs_warning_on_timeout(self):
        """Close should log timeout warning when close operations take too long."""
        service = _build_service()
        service.influxdb = None
        service.powerflow = cast(Any, None)
        service.monitoring = None
        service.weather = None

        with (
            patch(
                "solaredge2mqtt.service.asyncio.wait_for",
                side_effect=asyncio.TimeoutError,
            ),
            patch("solaredge2mqtt.service.logger") as mock_logger,
        ):
            await service.close()

        mock_logger.warning.assert_called_once_with(
            "Timeout while closing tasks, proceeding with shutdown."
        )
