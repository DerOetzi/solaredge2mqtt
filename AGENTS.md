# SolarEdge2MQTT — Agent & AI Instructions

This file is the single source of truth for AI coding assistants (Claude Code, GitHub Copilot,
Cursor, etc.). Tool-specific configurations in `.github/` reference this file and add only
tool-specific syntax on top.

## Project Overview

- **Purpose:** Integrates SolarEdge inverters with MQTT for home automation, logging, and forecasting.
- **Language:** Python (>=3.11, <=3.13)
- **Package Manager:** pip with `pyproject.toml`

### Directory Structure

```
solaredge2mqtt/
├── core/           # Event bus, logging, settings, MQTT, InfluxDB, timer
├── services/       # Modular services (energy, forecast, homeassistant, modbus,
│                   #   monitoring, powerflow, wallbox, weather)
├── __main__.py     # Entrypoint for CLI/console mode
└── service.py      # Main service orchestration logic
tests/              # Unit and integration tests mirroring solaredge2mqtt/ structure
examples/           # Docker Compose, Grafana, and other example configs
```

### Architecture & Data Flow

- **Event-driven:** Internal event bus for cross-component communication (`core/events`,
  `core/timer/events`). Subscribe via `event_bus.subscribe()`, emit via `event_bus.emit()`.
- **Service boundaries:** Each service is isolated under `services/` with its own `settings.py`,
  `models.py`, and `events.py`.
- **Data flow:** Inverter data (Modbus, Monitoring, Wallbox) → aggregated → InfluxDB + MQTT.
  Forecasting uses historical InfluxDB data and OpenWeatherMap.

### Integration Points

| System | Role |
|---|---|
| MQTT | Publishes inverter/sensor data for home automation (`core/mqtt/`) |
| InfluxDB | Logs raw and aggregated time-series data (`core/influxdb/`) |
| Home Assistant | Auto-discovery support (`services/homeassistant/`) |
| Modbus | TCP/IP communication with SolarEdge inverters |
| OpenWeatherMap | Weather data for PV production forecasting |

---

## Developer Commands

```bash
# Install with all development dependencies
pip install -e ".[dev,forecast]"

# Lint (must pass before commit)
ruff check .
ruff check . --fix   # auto-fix
ruff format .

# Tests (run in parallel by default via pytest-xdist, -v --tb=short set in pyproject.toml)
pytest
pytest --cov=solaredge2mqtt --cov-report=xml:coverage.xml
pytest tests/path/to/test_file.py

# Run (development)
python -m solaredge2mqtt

# Docker
docker build -t solaredge2mqtt .
docker compose up -d
```

---

## Code Conventions

Python conventions (type hints, imports, code structure, formatting, and linting) are defined in
[`.github/instructions/python.instructions.md`](.github/instructions/python.instructions.md)
and applied automatically to `*.py` files.

Project-specific constraints:

- Use Python >=3.11, <=3.13 syntax and language features.
- All code comments and documentation must be in **English**.
- For diagrams use Mermaid.

### Project Patterns

**Settings:**
- Pydantic-based, environment-variable-driven with double-underscore nesting
  (e.g., `SE2MQTT_MODBUS__HOST`).
- Secrets can be injected via Docker secrets (`/run/secrets`).

**Logging:**
- Use `loguru` exclusively: `logger.debug()`, `logger.info()`, `logger.warning()`,
  `logger.error()`.

**Adding a new service:**
1. Create directory under `services/` with `__init__.py`, `service.py`, `settings.py`,
   `models.py`, `events.py`.
2. Register the service in `service.py`.

**Example – settings model:**
```python
from pydantic import Field
from pydantic_settings import BaseSettings

class MyServiceSettings(BaseSettings):
    enable: bool = Field(default=False, description="Enable the service")
    host: str = Field(default="localhost", description="Service host")

    model_config = {"env_prefix": "SE2MQTT_MYSERVICE__"}
```

**Example – event:**
```python
from dataclasses import dataclass
from solaredge2mqtt.core.events import BaseEvent

@dataclass
class MyServiceEvent(BaseEvent):
    data: dict
```

### Testing

- Test files mirror the source structure under `tests/`.
- Use `pytest` with `pytest-asyncio`; fixtures in `tests/conftest.py`.
- Test classes prefixed with `Test`; methods prefixed with `test_`.
- Async tests use `@pytest.mark.asyncio` (auto mode enabled).
- Mock all external services (MQTT, InfluxDB, Modbus, HTTP APIs).
- All new code must be covered by unit tests; minimum coverage threshold is **90 %**.

**Example mock pattern:**
```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_mqtt():
    with patch('solaredge2mqtt.core.mqtt.MQTTClient') as mock:
        mock.publish = AsyncMock()
        yield mock
```

---

## Security Guidelines

- Never commit secrets or credentials.
- Use environment variables or Docker secrets for sensitive configuration.
- Validate all external inputs through Pydantic models.
- Handle user-provided data in MQTT messages with care.
- Filter sensitive data (passwords, tokens) from log output.
- API communications use HTTPS; MQTT supports TLS/SSL configuration.

---

## Agent Roles

The following roles define specialized AI behavior for this project. Each role has a dedicated
instruction file under `.github/agents/`. When an AI assistant operates in one of these roles,
it follows the constraints and output format defined in the corresponding file.

| Role | File | Access | Triggers |
|---|---|---|---|
| **developer** | `agents/developer.md` | Full (`solaredge2mqtt/`, `tests/`) | implement, fix bug, add feature |
| **qa-engineer** | `agents/qa-engineer.md` | `tests/` only | test, testing, quality, coverage |
| **documentation-expert** | `agents/documentation-expert.md` | `*.md`, `examples/` only | docs, README, document |
| **reviewer** | `agents/reviewer.md` | Read-only | review, code review, PR |
| **business-analyst** | `agents/business-analyst.md` | Read-only | analyze issue, user story, requirements |
| **security-expert** | `agents/security-expert.md` | Read-only | security, vulnerability, audit |
| **ml-expert** | `agents/ml-expert.md` | Read-only | forecast, machine learning, ML |
| **pv-expert** | `agents/pv-expert.md` | Read-only | solar, inverter, PV, SolarEdge |

### Role Hierarchy

```
business-analyst  →  developer  →  qa-engineer  →  reviewer
     (analyze)       (implement)     (test)         (review)
                         ↑
          security-expert / ml-expert / pv-expert
                  (advisory, read-only)
          documentation-expert
                  (docs only)
```

**General rule:** Only `developer` writes production code. `qa-engineer` writes test code.
`documentation-expert` writes documentation. All other roles are read-only and provide analysis,
feedback, or domain expertise as text output only.
