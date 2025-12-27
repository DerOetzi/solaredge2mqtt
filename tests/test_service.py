"""Tests for solaredge2mqtt.service.Service lifecycle helpers."""

import asyncio
import signal
from types import SimpleNamespace

import pytest

import solaredge2mqtt.service as service_module


class DummyEventBus:
    def __init__(self):
        self.cancelled = False

    async def cancel_tasks(self):
        self.cancelled = True


class DummyTimer:
    def __init__(self, event_bus, interval):
        self.event_bus = event_bus
        self.interval = interval
        self.loop_calls = 0

    async def loop(self):
        self.loop_calls += 1


class DummyPowerflowService:
    def __init__(self, *args, **kwargs):
        self.async_init_calls = 0
        self.closed = False

    async def async_init(self):
        self.async_init_calls += 1

    async def close(self):
        self.closed = True


class DummyHomeAssistant:
    def __init__(self, *args, **kwargs):
        self.initialized = False
        self.closed = False

    async def async_init(self):
        self.initialized = True

    async def close(self):
        self.closed = True


class DummyMonitoringSite:
    def __init__(self, *args, **kwargs):
        self.closed = False

    async def close(self):
        self.closed = True


class DummyWeatherClient:
    def __init__(self, *args, **kwargs):
        self.closed = False

    async def close(self):
        self.closed = True


class DummyEnergyService:
    def __init__(self, *args, **kwargs):
        self.closed = False

    async def close(self):
        self.closed = True


class DummyInfluxDB:
    def __init__(self, *args, **kwargs):
        self.initialized = False
        self.closed = False

    def init(self):
        self.initialized = True

    async def close(self):
        self.closed = True


class DummyMQTTClient:
    def __init__(self, settings, event_bus):
        self.settings = settings
        self.event_bus = event_bus
        self.online = False
        self.offline = False
        self.listen_calls = 0
        self.process_calls = 0
        self.fail_offline = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def publish_status_online(self):
        self.online = True

    async def publish_status_offline(self):
        if self.fail_offline:
            raise service_module.MqttError("offline failure")
        self.offline = True

    async def listen(self):
        self.listen_calls += 1
        await asyncio.sleep(0)

    async def process_queue(self):
        self.process_calls += 1
        await asyncio.sleep(0)


async def wait_for_background_tasks(service: service_module.Service):
    for _ in range(5):
        if not service.loops:
            return
        await asyncio.sleep(0)
    raise AssertionError("Background tasks did not finish")


class LoggerSpy:
    def __init__(self):
        self.calls = []

    def _record(self, level, message, kwargs):
        self.calls.append((level, message, kwargs))

    def error(self, message, **kwargs):
        self._record("error", message, kwargs)

    def debug(self, message, **kwargs):
        self._record("debug", message, kwargs)

    def info(self, message, **kwargs):
        self._record("info", message, kwargs)

    def warning(self, message, **kwargs):
        self._record("warning", message, kwargs)

    def messages(self, level):
        return [msg for lvl, msg, _ in self.calls if lvl == level]


def build_settings(**overrides):
    defaults = {
        "logging_level": "INFO",
        "interval": 1,
        "influxdb": SimpleNamespace(),
        "prices": SimpleNamespace(),
        "energy": SimpleNamespace(),
        "monitoring": SimpleNamespace(),
        "weather": SimpleNamespace(),
        "forecast": SimpleNamespace(),
        "location": SimpleNamespace(),
        "mqtt": SimpleNamespace(),
        "is_influxdb_configured": False,
        "is_monitoring_configured": False,
        "is_weather_configured": False,
        "is_forecast_configured": False,
        "is_homeassistant_configured": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture(autouse=True)
def patch_service_dependencies(monkeypatch):
    monkeypatch.setattr(
        service_module, "initialize_logging", lambda level: None)
    monkeypatch.setattr(service_module, "EventBus", DummyEventBus)
    monkeypatch.setattr(service_module, "Timer", DummyTimer)
    monkeypatch.setattr(service_module, "PowerflowService",
                        DummyPowerflowService)
    monkeypatch.setattr(
        service_module, "HomeAssistantDiscovery", DummyHomeAssistant
    )
    monkeypatch.setattr(service_module, "MonitoringSite", DummyMonitoringSite)
    monkeypatch.setattr(service_module, "WeatherClient", DummyWeatherClient)
    monkeypatch.setattr(service_module, "EnergyService", DummyEnergyService)
    monkeypatch.setattr(service_module, "InfluxDBAsync", DummyInfluxDB)
    monkeypatch.setattr(service_module, "MQTTClient", DummyMQTTClient)


@pytest.fixture
def settings_factory(monkeypatch):
    def factory(**overrides):
        settings = build_settings(**overrides)
        monkeypatch.setattr(
            service_module, "service_settings", lambda: settings)
        return settings

    return factory


def test_service_skips_forecast_when_unavailable(monkeypatch, settings_factory):
    settings_factory(is_forecast_configured=True)
    monkeypatch.setattr(service_module, "FORECAST_AVAILABLE", False)
    logger_spy = LoggerSpy()
    monkeypatch.setattr(service_module, "logger", logger_spy)

    service = service_module.Service()

    assert service.forecast is None
    assert any(
        "Forecast service not available" in msg
        for msg in logger_spy.messages("warning")
    )


@pytest.mark.asyncio
async def test__run_service_invokes_service_run(monkeypatch):
    lifecycle = {}

    class StubService:
        def __init__(self):
            lifecycle["created"] = True

        async def run(self):
            lifecycle["run"] = True

    monkeypatch.setattr(service_module, "Service", StubService)

    await service_module._run_service()

    assert lifecycle == {"created": True, "run": True}


def test_run_invokes_asyncio_run(monkeypatch):
    captured = {}

    async def dummy_run():
        return None

    monkeypatch.setattr(service_module, "_run_service", dummy_run)

    def fake_asyncio_run(coro):
        captured["coroutine_name"] = coro.cr_code.co_name
        coro.close()

    monkeypatch.setattr(service_module.asyncio, "run", fake_asyncio_run)

    service_module.run()

    assert captured["coroutine_name"] == "dummy_run"


@pytest.mark.parametrize(
    ("exception_factory", "level", "message"),
    [
        (
            lambda: service_module.ConfigurationException("service", "cfg"),
            "error",
            "Configuration error",
        ),
        (lambda: asyncio.CancelledError(), "debug", "Service cancelled"),
        (lambda: KeyboardInterrupt(), "info", "Service interrupted by user"),
    ],
)
def test_run_handles_exceptions(monkeypatch, exception_factory, level, message):
    logger_spy = LoggerSpy()
    monkeypatch.setattr(service_module, "logger", logger_spy)

    def fake_asyncio_run(coro):
        coro.close()
        raise exception_factory()

    monkeypatch.setattr(service_module.asyncio, "run", fake_asyncio_run)

    service_module.run()

    assert any(
        logged_level == level and logged_message == message
        for logged_level, logged_message, _ in logger_spy.calls
    )


@pytest.mark.asyncio
async def test_service_run_invokes_main_loop_and_shutdown(
    monkeypatch,
    settings_factory
):
    settings_factory()
    captured_handlers = []

    class DummyLoop:
        def add_signal_handler(self, signum, callback):
            captured_handlers.append((signum, callback))

    monkeypatch.setattr(
        service_module.asyncio,
        "get_running_loop",
        lambda: DummyLoop(),
    )

    service = service_module.Service()
    sequence = []

    async def fake_main_loop():
        sequence.append("main")

    async def fake_shutdown():
        sequence.append("shutdown")

    service.main_loop = fake_main_loop
    service.shutdown = fake_shutdown

    await service.run()

    assert [sig for sig, _ in captured_handlers] == [
        signal.SIGINT,
        signal.SIGTERM,
    ]
    assert all(
        cb.__self__ is service and cb.__func__ is service.cancel.__func__
        for _, cb in captured_handlers
    )
    assert sequence == ["main", "shutdown"]


@pytest.mark.asyncio
async def test_cancel_sets_flag_and_cancels_tasks(settings_factory):
    settings_factory()
    service = service_module.Service()

    async def pending():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Task cancellation is expected in this test; ignore the exception.
            pass

    task = asyncio.create_task(pending())
    service.loops.add(task)

    service.cancel()

    await asyncio.sleep(0)
    assert service.cancel_request.is_set()
    assert all(loop.cancelled() for loop in service.loops)
    await asyncio.gather(*service.loops, return_exceptions=True)
    service.loops.clear()


@pytest.mark.asyncio
async def test_cancel_is_idempotent(settings_factory):
    settings_factory()
    service = service_module.Service()

    async def pending():
        await asyncio.sleep(0)

    task = asyncio.create_task(pending())
    service.loops.add(task)
    service.cancel_request.set()

    service.cancel()

    assert service.cancel_request.is_set()
    assert not task.cancelled()

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    service.loops.clear()


@pytest.mark.asyncio
async def test_schedule_loop_creates_task(settings_factory, monkeypatch):
    settings_factory()
    service = service_module.Service()

    recorded = {}

    async def fake_run_loop(self, interval, handles, delay, args):
        recorded["params"] = (interval, handles, delay, args)

    monkeypatch.setattr(
        service_module.Service, "run_loop", fake_run_loop, raising=False
    )

    async def dummy_handle():
        return None

    service.schedule_loop(2, dummy_handle, delay_start=1, args=["a", "b"])

    assert len(service.loops) == 1

    await wait_for_background_tasks(service)

    assert recorded["params"] == (2, dummy_handle, 1, ["a", "b"])
    assert not service.loops


@pytest.mark.asyncio
async def test_run_loop_uses_args_and_short_sleep(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()

    calls = []

    async def handler(value):
        calls.append(value)
        service.cancel_request.set()

    times = iter([0, 0])
    monkeypatch.setattr(service_module, "time", lambda: next(times))

    sleeps = []

    async def fake_sleep(duration):
        if duration:
            sleeps.append(duration)

    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    await service.run_loop(2, handler, args=["payload"])

    assert calls == ["payload"]
    assert sleeps == [2]


@pytest.mark.asyncio
async def test_run_loop_handles_long_execution(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()

    async def handler():
        service.cancel_request.set()

    times = iter([0, 5])
    monkeypatch.setattr(service_module, "time", lambda: next(times))

    sleeps = []

    async def fake_sleep(duration):
        if duration:
            sleeps.append(duration)

    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    await service.run_loop(1, handler)

    assert sleeps == [1]


@pytest.mark.asyncio
async def test_start_mqtt_listener_adds_and_removes_tasks(settings_factory):
    settings_factory()
    service = service_module.Service()
    service.mqtt = DummyMQTTClient({}, service.event_bus)

    service._start_mqtt_listener()

    assert len(service.loops) == 2

    await wait_for_background_tasks(service)
    assert not service.loops
    assert service.mqtt.listen_calls == 1
    assert service.mqtt.process_calls == 1


@pytest.mark.asyncio
async def test_run_loop_respects_initial_delay(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()

    original_sleep = service_module.asyncio.sleep
    sleeps = []

    async def fake_sleep(duration):
        sleeps.append(duration)
        await original_sleep(0)

    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    async def handler():
        service.cancel_request.set()

    await service.run_loop(1, handler, delay_start=2)

    assert sleeps[0] == 2


@pytest.mark.asyncio
async def test_finalize_cancels_loops_and_handles_mqtt_errors(settings_factory):
    settings_factory()
    service = service_module.Service()

    async def pending():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Task cancellation is expected in this test; ignore the exception.
            pass

    task = asyncio.create_task(pending())
    service.loops.add(task)

    mqtt = DummyMQTTClient({}, service.event_bus)
    mqtt.fail_offline = True
    service.mqtt = mqtt

    await service.finalize()

    assert not service.loops
    assert service.mqtt is None
    assert service.event_bus.cancelled


@pytest.mark.asyncio
async def test_finalize_publishes_offline_status_and_clears_mqtt(settings_factory):
    settings_factory()
    service = service_module.Service()
    service.mqtt = DummyMQTTClient({}, service.event_bus)

    await service.finalize()

    assert service.mqtt is None
    assert service.event_bus.cancelled


@pytest.mark.asyncio
async def test_close_handles_timeout(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()
    service.influxdb = DummyInfluxDB()
    service.powerflow = DummyPowerflowService()
    service.monitoring = DummyMonitoringSite()
    service.weather = DummyWeatherClient()

    async def fake_wait_for(awaitable, timeout):
        await awaitable
        raise asyncio.TimeoutError

    monkeypatch.setattr(service_module.asyncio, "wait_for", fake_wait_for)

    await service.close()

    assert service.powerflow.closed
    assert service.monitoring.closed
    assert service.weather.closed
    assert service.influxdb.closed


@pytest.mark.asyncio
async def test_close_shuts_down_services(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()
    service.influxdb = DummyInfluxDB()
    service.powerflow = DummyPowerflowService()
    service.monitoring = DummyMonitoringSite()
    service.weather = DummyWeatherClient()

    async def fake_wait_for(awaitable, timeout):
        return await awaitable

    monkeypatch.setattr(service_module.asyncio, "wait_for", fake_wait_for)

    await service.close()

    assert service.powerflow.closed
    assert service.monitoring.closed
    assert service.weather.closed
    assert service.influxdb.closed


@pytest.mark.asyncio
async def test_shutdown_calls_finalize_and_close(settings_factory):
    settings_factory()
    service = service_module.Service()
    sequence = []

    async def fake_finalize():
        sequence.append("finalize")

    async def fake_close():
        sequence.append("close")

    service.finalize = fake_finalize
    service.close = fake_close

    await service.shutdown()

    assert sequence == ["finalize", "close"]


@pytest.mark.asyncio
async def test_main_loop_runs_once_on_cancel(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()

    async def trigger_cancel():
        service.powerflow.async_init_calls += 1
        service.cancel_request.set()

    service.powerflow.async_init = trigger_cancel

    monkeypatch.setattr(
        service_module.Service,
        "_start_mqtt_listener",
        lambda self: None,
    )
    monkeypatch.setattr(
        service_module.Service,
        "schedule_loop",
        lambda self, *args, **kwargs: None,
    )

    await service.main_loop()

    assert service.powerflow.async_init_calls == 1
    assert service.cancel_request.is_set()


@pytest.mark.asyncio
async def test_main_loop_initializes_influxdb_when_configured(monkeypatch, settings_factory):
    settings_factory(is_influxdb_configured=True)
    service = service_module.Service()

    async def trigger_cancel():
        service.powerflow.async_init_calls += 1
        service.cancel_request.set()

    service.powerflow.async_init = trigger_cancel

    monkeypatch.setattr(
        service_module.Service,
        "_start_mqtt_listener",
        lambda self: None,
    )
    monkeypatch.setattr(
        service_module.Service,
        "schedule_loop",
        lambda self, *args, **kwargs: None,
    )

    await service.main_loop()

    assert service.influxdb.initialized


@pytest.mark.asyncio
async def test_main_loop_initializes_homeassistant_when_configured(monkeypatch, settings_factory):
    settings_factory(is_homeassistant_configured=True)
    service = service_module.Service()

    async def trigger_cancel():
        service.powerflow.async_init_calls += 1
        service.cancel_request.set()

    service.powerflow.async_init = trigger_cancel

    monkeypatch.setattr(
        service_module.Service,
        "_start_mqtt_listener",
        lambda self: None,
    )
    monkeypatch.setattr(
        service_module.Service,
        "schedule_loop",
        lambda self, *args, **kwargs: None,
    )

    await service.main_loop()

    assert service.homeassistant.initialized


@pytest.mark.asyncio
async def test_main_loop_mqtt_error_breaks_when_already_cancelled(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()

    class CancelledMQTT(DummyMQTTClient):
        async def __aenter__(self):
            service.cancel_request.set()
            raise service_module.MqttError("boom")

    monkeypatch.setattr(service_module, "MQTTClient", CancelledMQTT)
    real_sleep = service_module.asyncio.sleep
    durations = []

    async def fake_sleep(duration):
        durations.append(duration)
        await real_sleep(0)

    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    await service.main_loop()

    assert durations == []


@pytest.mark.asyncio
async def test_main_loop_reraises_cancelled_error(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()

    async def faulty_task():
        await asyncio.sleep(0)
        raise asyncio.CancelledError()

    def inject_faulty_task(self):
        task = asyncio.create_task(faulty_task())
        self.loops.add(task)

    monkeypatch.setattr(
        service_module.Service,
        "_start_mqtt_listener",
        inject_faulty_task,
    )
    monkeypatch.setattr(
        service_module.Service,
        "schedule_loop",
        lambda self, *args, **kwargs: None,
    )

    with pytest.raises(asyncio.CancelledError):
        await service.main_loop()


@pytest.mark.asyncio
async def test_main_loop_retries_after_mqtt_error(monkeypatch, settings_factory):
    settings_factory()
    service = service_module.Service()

    class FailingMQTT:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise service_module.MqttError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def publish_status_offline(self):
            pass

    monkeypatch.setattr(service_module, "MQTTClient", FailingMQTT)

    real_sleep = service_module.asyncio.sleep
    durations = []

    async def fake_sleep(duration):
        durations.append(duration)
        service.cancel_request.set()
        await real_sleep(0)

    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    await service.main_loop()

    assert durations == [5]
